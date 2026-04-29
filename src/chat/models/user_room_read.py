from django.contrib.auth import get_user_model
from django.db import models

from .room import ChatRoom


class UserRoomRead(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name="room_reads")
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="user_reads")
    last_read_at = models.DateTimeField()

    class Meta:
        unique_together = [("user", "room")]
