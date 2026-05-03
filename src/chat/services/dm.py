"""DM read-state and unread-count helpers."""

from datetime import datetime, timezone as dt_timezone

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from chat.models import DirectMessage, DMRead, Friendship


def mark_read(user_id: int, peer_id: int) -> None:
    DMRead.objects.update_or_create(
        user_id=user_id,
        peer_id=peer_id,
        defaults={"last_read_at": timezone.now()},
    )


def unread_counts_by_peer(user_id: int) -> dict[int, int]:
    """Return {peer_id: unread_message_count} for every conversation."""
    reads = {
        r.peer_id: r.last_read_at
        for r in DMRead.objects.filter(user_id=user_id)
    }
    epoch = datetime.min.replace(tzinfo=dt_timezone.utc)
    now = timezone.now()
    counts: dict[int, int] = {}
    incoming = DirectMessage.objects.filter(
        to_user_id=user_id,
        is_deleted=False,
        expires_at__gt=now,
    ).values_list("from_user_id", "created_at")
    for from_user_id, created_at in incoming:
        last_read = reads.get(from_user_id, epoch)
        if created_at > last_read:
            counts[from_user_id] = counts.get(from_user_id, 0) + 1
    return counts


def unread_conversation_count(user_id: int) -> int:
    """How many friend conversations contain at least one unread incoming DM."""
    friendships = Friendship.objects.filter(Q(user_low_id=user_id) | Q(user_high_id=user_id))
    if not friendships.exists():
        return 0

    reads = {
        r.peer_id: r.last_read_at
        for r in DMRead.objects.filter(user_id=user_id)
    }
    epoch = datetime.min.replace(tzinfo=dt_timezone.utc)

    count = 0
    for f in friendships:
        peer_id = f.user_high_id if f.user_low_id == user_id else f.user_low_id
        last_read = reads.get(peer_id, epoch)
        has_unread = DirectMessage.objects.filter(
            from_user_id=peer_id,
            to_user_id=user_id,
            is_deleted=False,
            created_at__gt=last_read,
        ).exists()
        if has_unread:
            count += 1
    return count
