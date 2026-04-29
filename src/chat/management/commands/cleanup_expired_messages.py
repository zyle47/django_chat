from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from chat.models import ChatMessage, DailyStats


class Command(BaseCommand):
    help = "Snapshot daily stats then delete expired messages."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_qs = ChatMessage.objects.filter(expires_at__lte=now)

        daily = (
            expired_qs
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(total=Count('id'))
        )
        for entry in daily:
            obj, _ = DailyStats.objects.get_or_create(date=entry['day'])
            obj.message_count += entry['total']
            obj.save(update_fields=['message_count'])

        count, _ = expired_qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired message(s)."))
