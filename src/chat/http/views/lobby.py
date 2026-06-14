import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, DateTimeField, Sum
from django.db.models.expressions import OuterRef, Subquery
from django.db.models.functions import TruncHour
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from chat.forms import EnterRoomForm
from chat.models import (
    ChatImage,
    ChatMessage,
    ChatRoom,
    DailyStats,
    RoomFavorite,
    UserRoomRead,
)
from chat.services.rate_limit import is_rate_limited
from chat.services.room_access import grant_room_access
from chat.services.room_display import room_display
from chat.services.rooms import room_creation_limit
from chat.services.tiers import ICON_CHOICES, can_customize_room

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@login_required
def index(request):
    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    latest_msg_subq = (
        ChatMessage.objects.filter(
            room=OuterRef("pk"), is_deleted=False, expires_at__gt=now
        )
        .order_by("-created_at")
        .values("created_at")[:1]
    )
    user_read_subq = UserRoomRead.objects.filter(
        user=request.user, room=OuterRef("pk")
    ).values("last_read_at")[:1]
    rooms = list(
        ChatRoom.objects.filter(is_deleted=False).annotate(
            latest_msg_at=Subquery(latest_msg_subq, output_field=DateTimeField()),
            user_last_read_at=Subquery(user_read_subq, output_field=DateTimeField()),
        )
    )
    fav_rows = list(
        RoomFavorite.objects.filter(user=request.user, room__is_deleted=False)
        .order_by("-created_at")
        .values_list("room_id", "note")
    )
    fav_room_ids = [room_id for room_id, _ in fav_rows]
    fav_notes = {room_id: note for room_id, note in fav_rows}
    fav_set = set(fav_room_ids)
    for room in rooms:
        room.has_unread = room.latest_msg_at is not None and (
            room.user_last_read_at is None
            or room.latest_msg_at > room.user_last_read_at
        )
        room.is_favorite = room.id in fav_set
        d = room_display(
            room.name,
            custom_color=room.custom_color,
            custom_icon=room.custom_icon,
        )
        room.hash = d["hash"]
        room.display = d["display"]
        room.icon = d["icon"]
        room.color = d["color"]

    rooms_by_id = {room.id: room for room in rooms}
    favorites = []
    for rid in fav_room_ids:
        room = rooms_by_id.get(rid)
        if room is None:
            continue
        room.note = fav_notes.get(rid, "")
        favorites.append(room)

    hourly_qs = (
        ChatMessage.objects.filter(created_at__gte=last_24h, is_deleted=False)
        .annotate(hour=TruncHour("created_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    slots = [0] * 24
    for entry in hourly_qs:
        idx = 23 - int((now - entry["hour"]).total_seconds() // 3600)
        if 0 <= idx < 24:
            slots[idx] = entry["count"]

    msgs_24h = sum(slots)
    historical = DailyStats.objects.aggregate(total=Sum("message_count"))["total"] or 0

    stats = {
        "messages_24h": msgs_24h,
        "messages_total": historical + msgs_24h,
        "live_images": ChatImage.objects.filter(
            expires_at__gt=now, room__is_deleted=False
        ).count(),
        "rooms": len(rooms),
        "hourly": slots,
    }

    return render(
        request,
        "chat/index.html",
        {
            "rooms": rooms,
            "favorites": favorites,
            "stats": stats,
            "can_customize_room": can_customize_room(request.user),
        },
    )


@require_POST
@login_required
def enter_room(request):
    form = EnterRoomForm(request.POST)
    if not form.is_valid():
        first_error = str(next(iter(form.errors.values()))[0])
        messages.error(request, first_error)
        return redirect("index")

    room_name = form.cleaned_data["room_name"]
    room_password = form.cleaned_data["room_password"]
    message_lifetime = form.cleaned_data["message_lifetime"]

    room_obj = ChatRoom.objects.filter(name=room_name).first()
    if room_obj is None:
        if not room_password:
            messages.error(request, "New rooms must have a password.")
            return redirect("index")

        limit = room_creation_limit(request.user)
        if limit is not None:
            active_count = ChatRoom.objects.filter(
                creator=request.user, is_deleted=False
            ).count()
            if active_count >= limit:
                messages.error(
                    request,
                    f"Your tier allows {limit} active room(s). Upgrade to create more.",
                )
                return redirect("index")

        room_obj = ChatRoom(name=room_name, creator=request.user)
        room_obj.set_password(room_password)
        if message_lifetime is not None:
            room_obj.message_lifetime = message_lifetime

        if can_customize_room(request.user):
            raw_color = request.POST.get("room_color", "").strip()
            raw_icon = request.POST.get("room_icon", "").strip()
            if raw_color and _COLOR_RE.match(raw_color):
                room_obj.custom_color = raw_color
            if raw_icon and raw_icon in ICON_CHOICES:
                room_obj.custom_icon = raw_icon

        room_obj.save()
        grant_room_access(request.session, room_obj.name)
        return redirect(reverse("room", kwargs={"public_id": room_obj.public_id}))

    if room_obj.is_deleted:
        messages.error(request, "This room is currently unavailable.")
        return redirect("index")

    if request.user.is_superuser:
        grant_room_access(request.session, room_obj.name)
        return redirect(reverse("room", kwargs={"public_id": room_obj.public_id}))

    rl_key = f"rl:room:{request.session.session_key}:{room_name}"
    if is_rate_limited(rl_key, 10, 300):
        messages.error(request, "Too many attempts. Try again in 5 minutes.")
        return redirect("index")

    if not room_obj.check_password(room_password):
        messages.error(request, "Invalid room password.")
        return redirect("index")

    grant_room_access(request.session, room_obj.name)
    return redirect(reverse("room", kwargs={"public_id": room_obj.public_id}))


@require_GET
@login_required
def room_unread_state(request, public_id):
    room_obj = (
        ChatRoom.objects.filter(public_id=public_id, is_deleted=False)
        .only("id")
        .first()
    )
    if room_obj is None:
        return JsonResponse({"unread": False})
    now = timezone.now()
    latest_at = (
        ChatMessage.objects.filter(
            room_id=room_obj.id, is_deleted=False, expires_at__gt=now
        )
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    if latest_at is None:
        return JsonResponse({"unread": False})
    last_read = (
        UserRoomRead.objects.filter(user=request.user, room_id=room_obj.id)
        .values_list("last_read_at", flat=True)
        .first()
    )
    return JsonResponse({"unread": last_read is None or latest_at > last_read})


@require_POST
@login_required
def toggle_room_favorite(request, public_id):
    room_obj = (
        ChatRoom.objects.filter(public_id=public_id, is_deleted=False)
        .only("id")
        .first()
    )
    if room_obj is None:
        return JsonResponse({"error": "no such room"}, status=404)
    favorite, created = RoomFavorite.objects.get_or_create(
        user=request.user, room_id=room_obj.id
    )
    if not created:
        favorite.delete()
        return JsonResponse({"favorited": False})
    return JsonResponse({"favorited": True})


NOTE_MAX_LENGTH = 200


@require_POST
@login_required
def set_room_favorite_note(request, public_id):
    room_obj = (
        ChatRoom.objects.filter(public_id=public_id, is_deleted=False)
        .only("id")
        .first()
    )
    if room_obj is None:
        return JsonResponse({"error": "no such room"}, status=404)
    favorite = RoomFavorite.objects.filter(
        user=request.user, room_id=room_obj.id
    ).first()
    if favorite is None:
        return JsonResponse({"error": "not a favorite"}, status=404)
    note = (request.POST.get("note") or "").strip()[:NOTE_MAX_LENGTH]
    if note != favorite.note:
        favorite.note = note
        favorite.save(update_fields=["note"])
    return JsonResponse({"note": note})
