import uuid

from django.contrib.auth import get_user_model
from django.db import models

from .room import ChatRoom


def _image_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"chat_images/{instance.room.name}/{uuid.uuid4().hex}.{ext}"


class ChatImage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="images")
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name="chat_images")
    username = models.CharField(max_length=40)
    color = models.CharField(max_length=20)
    image = models.FileField(upload_to=_image_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"{self.username} image in {self.room.name}"
