from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class DMRead(models.Model):
    """When a user last read their conversation with a peer."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dm_reads")
    peer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dm_reads_as_peer")
    last_read_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "peer"], name="unique_dmread_user_peer"),
        ]
        indexes = [models.Index(fields=["user", "last_read_at"])]

    def __str__(self):
        return f"{self.user_id} read DM with {self.peer_id} @ {self.last_read_at}"
