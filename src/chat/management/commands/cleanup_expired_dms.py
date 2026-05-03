from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import DirectMessage


class Command(BaseCommand):
    help = "Delete expired direct messages."

    def handle(self, *args, **options):
        count, _ = DirectMessage.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired DM(s)."))
