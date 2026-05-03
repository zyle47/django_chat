import hashlib

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class ChatRoom(models.Model):
    name = models.SlugField(max_length=80, unique=True)
    public_id = models.CharField(max_length=64, unique=True, db_index=True, editable=False, default="")
    password_hash = models.CharField(max_length=255, default="")
    password_length = models.PositiveSmallIntegerField(default=0)
    message_lifetime = models.PositiveIntegerField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = hashlib.sha256(self.name.encode()).hexdigest()
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)
        self.password_length = len(raw_password)

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
