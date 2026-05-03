"""
Friend-request business logic. Pure DB work; no I/O with the channel layer
(consumer is responsible for sending whispers based on the result).

Each function returns a small dict result describing what happened so the
caller can render the appropriate whisper(s).
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from chat.models import FriendRequest, Friendship

User = get_user_model()

DEFAULT_REQUEST_TTL_SECONDS = 5 * 60


def _ttl_seconds() -> int:
    return getattr(settings, "FRIEND_REQUEST_EXPIRY_SECONDS", DEFAULT_REQUEST_TTL_SECONDS)


def lookup_user(username: str):
    return User.objects.filter(username=username).first()


def send_request(from_user_id: int, target_username: str, room_obj):
    """
    Result dict shape:
      {"ok": bool, "code": str, "to_user_id"?: int, "to_username"?: str, "auto_accepted"?: bool}
    Codes:
      ok=True:  "sent" | "auto_accepted"
      ok=False: "self" | "no_such_user" | "already_friends" | "already_pending"
    """
    target = lookup_user(target_username)
    if target is None:
        return {"ok": False, "code": "no_such_user"}
    if target.id == from_user_id:
        return {"ok": False, "code": "self"}
    if Friendship.exists_between(from_user_id, target.id):
        return {"ok": False, "code": "already_friends", "to_username": target.username}

    now = timezone.now()
    expires_at = now + timezone.timedelta(seconds=_ttl_seconds())

    with transaction.atomic():
        # Reverse direction already pending → auto-accept
        reverse = (
            FriendRequest.objects
            .select_for_update()
            .filter(from_user_id=target.id, to_user_id=from_user_id, expires_at__gt=now)
            .first()
        )
        if reverse is not None:
            Friendship.create_between(from_user_id, target.id)
            FriendRequest.objects.filter(
                from_user_id__in=(from_user_id, target.id),
                to_user_id__in=(from_user_id, target.id),
            ).delete()
            return {
                "ok": True,
                "code": "auto_accepted",
                "to_user_id": target.id,
                "to_username": target.username,
            }

        # Same-direction pending (not expired) → already pending
        existing = (
            FriendRequest.objects
            .select_for_update()
            .filter(from_user_id=from_user_id, to_user_id=target.id)
            .first()
        )
        if existing is not None:
            if existing.expires_at > now:
                return {"ok": False, "code": "already_pending", "to_username": target.username}
            existing.delete()  # expired stale row, replace below

        FriendRequest.objects.create(
            from_user_id=from_user_id,
            to_user_id=target.id,
            room=room_obj,
            expires_at=expires_at,
        )

    return {
        "ok": True,
        "code": "sent",
        "to_user_id": target.id,
        "to_username": target.username,
    }


def accept_request(to_user_id: int, from_username: str):
    """
    Codes: ok=True "accepted" | ok=False "self" | "no_such_user" | "already_friends" | "no_pending"
    """
    sender = lookup_user(from_username)
    if sender is None:
        return {"ok": False, "code": "no_such_user"}
    if sender.id == to_user_id:
        return {"ok": False, "code": "self"}
    if Friendship.exists_between(to_user_id, sender.id):
        return {"ok": False, "code": "already_friends", "from_username": sender.username}

    now = timezone.now()
    with transaction.atomic():
        req = (
            FriendRequest.objects
            .select_for_update()
            .filter(from_user_id=sender.id, to_user_id=to_user_id, expires_at__gt=now)
            .first()
        )
        if req is None:
            return {"ok": False, "code": "no_pending", "from_username": sender.username}
        Friendship.create_between(to_user_id, sender.id)
        req.delete()

    return {
        "ok": True,
        "code": "accepted",
        "from_user_id": sender.id,
        "from_username": sender.username,
    }


def reject_request(to_user_id: int, from_username: str):
    """
    Codes: ok=True "rejected" | ok=False "self" | "no_such_user" | "no_pending"
    Note: no notification is sent to the original sender (avoid reject-spam signal).
    """
    sender = lookup_user(from_username)
    if sender is None:
        return {"ok": False, "code": "no_such_user"}
    if sender.id == to_user_id:
        return {"ok": False, "code": "self"}

    deleted, _ = FriendRequest.objects.filter(
        from_user_id=sender.id, to_user_id=to_user_id
    ).delete()
    if deleted == 0:
        return {"ok": False, "code": "no_pending", "from_username": sender.username}

    return {"ok": True, "code": "rejected", "from_username": sender.username}
