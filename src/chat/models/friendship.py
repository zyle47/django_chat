from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, Q

User = get_user_model()


class FriendRequest(models.Model):
    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_friend_requests"
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="received_friend_requests"
    )
    room = models.ForeignKey(
        "chat.ChatRoom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="friend_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                name="unique_pending_friend_request",
            ),
        ]
        indexes = [models.Index(fields=["expires_at"])]

    def __str__(self):
        return f"{self.from_user_id} → {self.to_user_id}"


class Friendship(models.Model):
    """Symmetric friendship stored as a sorted user pair (user_low.id < user_high.id)."""

    user_low = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="friendships_low"
    )
    user_high = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="friendships_high"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_low", "user_high"], name="unique_friendship_pair"
            ),
            models.CheckConstraint(
                condition=Q(user_low__lt=F("user_high")),
                name="friendship_user_low_lt_high",
            ),
        ]

    @staticmethod
    def sort_pair(a_id: int, b_id: int) -> tuple[int, int]:
        return (a_id, b_id) if a_id < b_id else (b_id, a_id)

    @classmethod
    def exists_between(cls, a_id: int, b_id: int) -> bool:
        if a_id == b_id:
            return False
        low, high = cls.sort_pair(a_id, b_id)
        return cls.objects.filter(user_low_id=low, user_high_id=high).exists()

    @classmethod
    def create_between(cls, a_id: int, b_id: int) -> "Friendship":
        low, high = cls.sort_pair(a_id, b_id)
        return cls.objects.create(user_low_id=low, user_high_id=high)

    def __str__(self):
        return f"{self.user_low_id} ↔ {self.user_high_id}"
