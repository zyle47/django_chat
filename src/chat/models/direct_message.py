from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class DirectMessage(models.Model):
    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_direct_messages"
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="received_direct_messages"
    )
    pair_low = models.PositiveIntegerField()   # min(from_user_id, to_user_id) for fast pair lookup
    pair_high = models.PositiveIntegerField()  # max(...)
    message = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_deleted = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["pair_low", "pair_high", "created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    @staticmethod
    def sort_pair(a_id: int, b_id: int) -> tuple[int, int]:
        return (a_id, b_id) if a_id < b_id else (b_id, a_id)

    def save(self, *args, **kwargs):
        low, high = self.sort_pair(self.from_user_id, self.to_user_id)
        self.pair_low, self.pair_high = low, high
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DM {self.from_user_id} → {self.to_user_id}"
