from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import ChatRoom
from chat.services.rooms import purge_room


class Command(BaseCommand):
    help = "Permanently delete rooms that have been soft-deleted for too long."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(
            days=settings.ROOM_PURGE_AFTER_DEACTIVATION_DAYS
        )
        stale = ChatRoom.objects.filter(is_deleted=True, deleted_at__lte=cutoff)
        count = 0
        for room in stale:
            purge_room(room)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Purged {count} deactivated room(s)."))
