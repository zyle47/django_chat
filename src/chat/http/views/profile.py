import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from chat.models import UpgradeRequest, UserProfile
from chat.services.avatar import process_avatar
from chat.services.tiers import can_animate_avatar


@login_required
@require_POST
def edit_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.POST.get("action") == "remove":
        if profile.avatar:
            try:
                if os.path.isfile(profile.avatar.path):
                    os.remove(profile.avatar.path)
            except Exception:
                pass
            profile.avatar = None
            profile.save()
        return JsonResponse({"ok": True, "avatar_url": None})

    uploaded = request.FILES.get("avatar")
    if not uploaded:
        return JsonResponse({"ok": False, "error": "No file provided."}, status=400)

    try:
        content_file = process_avatar(
            uploaded, allow_animation=can_animate_avatar(request.user)
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    # Delete old avatar file from disk before saving new one.
    if profile.avatar:
        try:
            if os.path.isfile(profile.avatar.path):
                os.remove(profile.avatar.path)
        except Exception:
            pass
        profile.avatar = None
        profile.save()

    filename = f"{request.user.id}.webp"
    profile.avatar.save(filename, content_file, save=True)

    avatar_url = reverse("serve-avatar", args=[request.user.id])
    return JsonResponse({"ok": True, "avatar_url": avatar_url})


@login_required
def serve_avatar(request, user_id):
    try:
        profile = UserProfile.objects.get(user_id=user_id)
    except UserProfile.DoesNotExist:
        raise Http404

    if not profile.avatar:
        raise Http404

    if not os.path.isfile(profile.avatar.path):
        raise Http404

    response = FileResponse(
        open(profile.avatar.path, "rb"),
        content_type="image/webp",
    )
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def upgrade_account(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "GET":
        return JsonResponse(
            {
                "current_level": profile.level,
                "tiers": settings.UPGRADE_TIERS,
                "addresses": settings.CRYPTO_ADDRESSES,
            }
        )

    # POST
    requested_level = request.POST.get("requested_level", "").strip()
    if requested_level not in settings.UPGRADE_TIERS:
        return JsonResponse({"ok": False, "error": "Invalid tier."}, status=400)

    UpgradeRequest.objects.create(
        user=request.user,
        requested_level=requested_level,
    )
    return JsonResponse({"ok": True})
