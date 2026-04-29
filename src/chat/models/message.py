from django.contrib.auth import get_user_model
from django.db import models

from .room import ChatRoom


class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(get_user_model(), null=True, on_delete=models.SET_NULL, related_name="chat_messages")
    username = models.CharField(max_length=40, default="Anonymous")
    message = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.username} in {self.room.name}"
