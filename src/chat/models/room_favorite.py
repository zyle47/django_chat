from django.contrib.auth import get_user_model
from django.db import models

from .room import ChatRoom


class RoomFavorite(models.Model):
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="room_favorites"
    )
    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Private, per-user note for a favourited room. Only ever shown to the
    # owning user in their favourites list, never in the public room browser.
    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = [("user", "room")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} ★ {self.room_id}"
