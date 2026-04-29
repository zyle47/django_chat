import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import ChatImage


class Command(BaseCommand):
    help = "Delete chat images whose expiry time has passed."

    def handle(self, *args, **options):
        expired = ChatImage.objects.filter(expires_at__lte=timezone.now())
        count = 0
        for img in expired:
            try:
                if img.image and os.path.isfile(img.image.path):
                    os.remove(img.image.path)
            except Exception:
                pass
            img.delete()
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired image(s)."))
