import os
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from chat.models import ChatImage, ChatRoom


class TestPurgeDeactivatedRoomsCommand(TestCase):
    def _make_room(self, name, is_deleted=False, deleted_at=None):
        room = ChatRoom.objects.create(name=name)
        if is_deleted:
            room.is_deleted = True
            room.deleted_at = deleted_at or timezone.now()
            room.save(update_fields=["is_deleted", "deleted_at"])
        return room

    def _attach_image(self, room):
        img = ChatImage(
            room=room,
            username="tester",
            color="#fff",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        img.image.save("test.webp", ContentFile(b"fake-image-bytes"), save=True)
        return img

    def test_stale_room_is_purged(self):
        cutoff_days = settings.ROOM_PURGE_AFTER_DEACTIVATION_DAYS
        old_deleted_at = timezone.now() - timedelta(days=cutoff_days + 1)
        room = self._make_room("stale-room", is_deleted=True, deleted_at=old_deleted_at)
        img = self._attach_image(room)
        img_path = img.image.path
        self.assertTrue(os.path.isfile(img_path))

        room_id = room.id
        call_command("purge_deactivated_rooms", verbosity=0)

        self.assertFalse(ChatRoom.objects.filter(id=room_id).exists())
        self.assertFalse(os.path.isfile(img_path))

    def test_recently_deactivated_room_is_not_purged(self):
        # Deleted just now — within the grace period
        room = self._make_room(
            "fresh-deleted", is_deleted=True, deleted_at=timezone.now()
        )
        room_id = room.id

        call_command("purge_deactivated_rooms", verbosity=0)

        self.assertTrue(ChatRoom.objects.filter(id=room_id).exists())

    def test_active_room_is_not_purged(self):
        room = self._make_room("active-room", is_deleted=False)
        room_id = room.id

        call_command("purge_deactivated_rooms", verbosity=0)

        self.assertTrue(ChatRoom.objects.filter(id=room_id).exists())

    def test_command_purges_multiple_stale_rooms(self):
        cutoff_days = settings.ROOM_PURGE_AFTER_DEACTIVATION_DAYS
        old_deleted_at = timezone.now() - timedelta(days=cutoff_days + 2)
        room_a = self._make_room("stale-a", is_deleted=True, deleted_at=old_deleted_at)
        room_b = self._make_room("stale-b", is_deleted=True, deleted_at=old_deleted_at)
        recent_room = self._make_room(
            "recent", is_deleted=True, deleted_at=timezone.now()
        )

        call_command("purge_deactivated_rooms", verbosity=0)

        self.assertFalse(ChatRoom.objects.filter(id=room_a.id).exists())
        self.assertFalse(ChatRoom.objects.filter(id=room_b.id).exists())
        self.assertTrue(ChatRoom.objects.filter(id=recent_room.id).exists())
