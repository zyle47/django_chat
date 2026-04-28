from django.db import models
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone


class ChatRoom(models.Model):
    name = models.SlugField(max_length=80, unique=True)
    password_hash = models.CharField(max_length=255, default="")
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
