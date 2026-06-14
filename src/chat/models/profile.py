from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    LEVEL_CHOICES = [
        (BRONZE, "Bronze"),
        (SILVER, "Silver"),
        (GOLD, "Gold"),
        (PLATINUM, "Platinum"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=BRONZE)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user_id} ({self.level})"


class UpgradeRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="upgrade_requests",
    )
    requested_level = models.CharField(max_length=10, choices=UserProfile.LEVEL_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} -> {self.requested_level}"
