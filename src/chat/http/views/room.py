import io
import json
import mimetypes
import os

from asgiref.sync import async_to_sync
from PIL import Image
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from chat.models import ChatImage, ChatMessage, ChatRoom
from chat.services.room_access import has_room_access
from chat.services.room_colors import room_color_for_username


def _is_valid_image(f):
    header = f.read(12)
    f.seek(0)
    if header[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if header[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'webp'
    return None


@login_required
def room(request, room_name):
    normalized_room_name = slugify(room_name)
    if not normalized_room_name:
        messages.error(request, "Invalid room name.")
        return redirect("index")

    room_obj = ChatRoom.objects.filter(name=normalized_room_name, is_deleted=False).first()
    if room_obj is None:
        messages.error(request, "Room does not exist or is unavailable.")
        return redirect("index")

    if not has_room_access(request.session, room_obj.name):
        messages.error(request, "Enter room password from the lobby to access this room.")
        return redirect("index")

    now = timezone.now()

    recent_messages = list(
        room_obj.messages.filter(is_deleted=False)
        .exclude(expires_at__lte=now)
        .order_by("created_at")
    )
    recent_images = list(
        ChatImage.objects.filter(room=room_obj, expires_at__gt=now).order_by("uploaded_at")
    )

    items = []
    for entry in recent_messages:
        items.append({
            "type": "message",
            "id": entry.id,
            "username": entry.username,
            "message": entry.message,
            "edited_at": entry.edited_at,
            "time": entry.created_at,
            "expires_at": entry.expires_at,
            "color": room_color_for_username(room_obj.name, entry.username),
            "is_mine": entry.username == request.user.username,
        })
    for img in recent_images:
        items.append({
            "type": "image",
            "id": img.id,
            "username": img.username,
            "color": img.color,
            "time": img.uploaded_at,
            "expires_at": img.expires_at,
            "is_mine": img.user_id == request.user.id,
        })
    items.sort(key=lambda x: x["time"])

    context = {
        "room_name": room_obj.name,
        "items": items,
        "username": request.user.username,
    }
    return render(request, "chat/room.html", context)


@login_required
@require_POST
def upload_image(request, room_name):
    room_obj = ChatRoom.objects.filter(name=room_name, is_deleted=False).first()
    if room_obj is None:
        return JsonResponse({"error": "Room not found."}, status=404)
    if not has_room_access(request.session, room_obj.name):
        return JsonResponse({"error": "No access."}, status=403)

    f = request.FILES.get("image")
    if not f:
        return JsonResponse({"error": "No file provided."}, status=400)
    if f.size > settings.CHAT_IMAGE_MAX_BYTES:
        return JsonResponse({"error": "File too large (max 5 MB)."}, status=400)

    ext = _is_valid_image(f)
    if not ext:
        return JsonResponse({"error": "Not a supported image (JPEG/PNG/GIF/WebP)."}, status=400)

    active_count = ChatImage.objects.filter(
        room=room_obj, user=request.user, expires_at__gt=timezone.now()
    ).count()
    if active_count >= settings.CHAT_IMAGE_MAX_PER_USER:
        return JsonResponse({"error": f"Max {settings.CHAT_IMAGE_MAX_PER_USER} images per user."}, status=400)

    color = room_color_for_username(room_obj.name, request.user.username)
    expires_at = timezone.now() + timezone.timedelta(seconds=settings.CHAT_IMAGE_EXPIRY_SECONDS)

    # Compress to WebP via Pillow (decompression bomb guard applied first)
    try:
        Image.MAX_IMAGE_PIXELS = settings.CHAT_IMAGE_MAX_PIXELS
        pil_img = Image.open(f)
        pil_img.verify()   # raises on corrupt files
        f.seek(0)
        pil_img = Image.open(f)
        pil_img = pil_img.convert("RGBA") if pil_img.mode in ("RGBA", "LA", "P") else pil_img.convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, format="WEBP", quality=82, method=4)
        buf.seek(0)
        compressed = buf
    except Exception:
        f.seek(0)
        compressed = f

    img = ChatImage(
        room=room_obj,
        user=request.user,
        username=request.user.username[:40],
        color=color,
        expires_at=expires_at,
    )
    img.image.save(f"{request.user.username}.webp", compressed, save=True)

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{room_obj.name}",
        {
            "type": "chat_image",
            "image_id": img.id,
            "image_url": f"/chat/image/{img.id}/",
            "username": img.username,
            "color": color,
            "expires_at": img.expires_at.isoformat(),
        },
    )
    return JsonResponse({
        "ok": True,
        "image_id": img.id,
        "expires_at": img.expires_at.isoformat(),
    })


@login_required
def serve_image(request, image_id):
    img = get_object_or_404(ChatImage, id=image_id)
    if not has_room_access(request.session, img.room.name):
        raise Http404
    if timezone.now() > img.expires_at:
        raise Http404
    if not img.image or not os.path.isfile(img.image.path):
        raise Http404
    content_type, _ = mimetypes.guess_type(img.image.name)
    response = FileResponse(open(img.image.path, "rb"), content_type=content_type or "application/octet-stream")
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def delete_image(request, image_id):
    img = get_object_or_404(ChatImage, id=image_id, user=request.user)
    room_name = img.room.name
    try:
        if img.image and os.path.isfile(img.image.path):
            os.remove(img.image.path)
    except Exception:
        pass
    img.delete()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{room_name}",
        {"type": "image_deleted", "image_id": image_id},
    )
    return JsonResponse({"ok": True})
