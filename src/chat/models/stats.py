from django.db import models


class DailyStats(models.Model):
    date = models.DateField(unique=True)
    message_count = models.PositiveIntegerField(default=0)
    image_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"{self.date}: {self.message_count} msgs"
