from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import FriendRequest


class Command(BaseCommand):
    help = "Delete expired friend requests."

    def handle(self, *args, **options):
        count, _ = FriendRequest.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired friend request(s)."))
