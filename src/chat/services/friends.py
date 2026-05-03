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

from chat.models import (
    DirectMessage,
    DMRead,
    FriendBlock,
    FriendRequest,
    Friendship,
)

User = get_user_model()

DEFAULT_REQUEST_TTL_SECONDS = 5 * 60


def _ttl_seconds() -> int:
    return getattr(settings, "FRIEND_REQUEST_EXPIRY_SECONDS", DEFAULT_REQUEST_TTL_SECONDS)


def lookup_user(username: str):
    return User.objects.filter(username=username, is_active=True).first()


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
    # If the target has blocked us, behave as if they don't exist (don't leak).
    if FriendBlock.is_blocked(target.id, from_user_id):
        return {"ok": False, "code": "no_such_user"}
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


def _purge_pair(actor_id: int, peer_id: int) -> None:
    """Tear down all friend-related state between two users."""
    low, high = Friendship.sort_pair(actor_id, peer_id)
    Friendship.objects.filter(user_low_id=low, user_high_id=high).delete()
    FriendRequest.objects.filter(
        from_user_id__in=(actor_id, peer_id),
        to_user_id__in=(actor_id, peer_id),
    ).delete()
    DirectMessage.objects.filter(pair_low=low, pair_high=high).delete()
    DMRead.objects.filter(
        user_id__in=(actor_id, peer_id), peer_id__in=(actor_id, peer_id)
    ).delete()


def remove_friend(actor_id: int, peer_username: str):
    """
    Codes: ok=True "removed" | ok=False "self" | "no_such_user" | "not_friends"
    """
    peer = lookup_user(peer_username)
    if peer is None:
        return {"ok": False, "code": "no_such_user"}
    if peer.id == actor_id:
        return {"ok": False, "code": "self"}
    with transaction.atomic():
        if not Friendship.exists_between(actor_id, peer.id):
            return {"ok": False, "code": "not_friends", "peer_username": peer.username}
        _purge_pair(actor_id, peer.id)
    return {
        "ok": True,
        "code": "removed",
        "peer_user_id": peer.id,
        "peer_username": peer.username,
    }


def unban_friend(actor_id: int, peer_username: str):
    """
    Codes: ok=True "unbanned" | ok=False "self" | "no_such_user" | "not_banned"
    """
    peer = lookup_user(peer_username)
    if peer is None:
        return {"ok": False, "code": "no_such_user"}
    if peer.id == actor_id:
        return {"ok": False, "code": "self"}
    deleted, _ = FriendBlock.objects.filter(
        blocker_id=actor_id, blocked_id=peer.id
    ).delete()
    if deleted == 0:
        return {"ok": False, "code": "not_banned", "peer_username": peer.username}
    return {
        "ok": True,
        "code": "unbanned",
        "peer_user_id": peer.id,
        "peer_username": peer.username,
    }


def ban_friend(actor_id: int, peer_username: str):
    """
    Tear down friendship (if any) AND record a one-way block from actor → peer.
    Codes: ok=True "banned" | ok=False "self" | "no_such_user"
    """
    peer = lookup_user(peer_username)
    if peer is None:
        return {"ok": False, "code": "no_such_user"}
    if peer.id == actor_id:
        return {"ok": False, "code": "self"}
    with transaction.atomic():
        _purge_pair(actor_id, peer.id)
        FriendBlock.objects.get_or_create(blocker_id=actor_id, blocked_id=peer.id)
    return {
        "ok": True,
        "code": "banned",
        "peer_user_id": peer.id,
        "peer_username": peer.username,
    }
