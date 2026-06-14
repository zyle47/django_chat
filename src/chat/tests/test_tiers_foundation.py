import io
import os

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image

from chat.models import ChatImage, ChatRoom, UserProfile
from chat.services.avatar import process_avatar
from chat.services.rooms import purge_room, room_creation_limit


class TestUserProfileAutoCreate(TestCase):
    def test_profile_created_with_default_bronze(self):
        user = User.objects.create_user(username="alice", password="Pass123")
        self.assertTrue(hasattr(user, "profile"))
        self.assertIsInstance(user.profile, UserProfile)
        self.assertEqual(user.profile.level, UserProfile.BRONZE)


class TestRoomCreationLimit(TestCase):
    def _user(self, level):
        user = User.objects.create_user(username=f"u_{level}", password="Pass123")
        user.profile.level = level
        user.profile.save(update_fields=["level"])
        user.refresh_from_db()
        return user

    def test_bronze_limit(self):
        self.assertEqual(room_creation_limit(self._user("bronze")), 1)

    def test_silver_limit(self):
        self.assertEqual(room_creation_limit(self._user("silver")), 5)

    def test_platinum_unlimited(self):
        self.assertIsNone(room_creation_limit(self._user("platinum")))

    def test_superuser_unlimited(self):
        admin = User.objects.create_superuser(
            username="admin", password="Pass123", email=""
        )
        self.assertIsNone(room_creation_limit(admin))


class TestPurgeRoom(TestCase):
    def test_purge_deletes_file_then_row(self):
        room = ChatRoom.objects.create(name="purgeme")
        img = ChatImage(
            room=room,
            username="alice",
            color="#fff",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        img.image.save("tiny.webp", ContentFile(b"not-really-an-image"), save=True)
        path = img.image.path
        self.assertTrue(os.path.isfile(path))

        room_id = room.id
        purge_room(room)

        self.assertFalse(os.path.isfile(path))
        self.assertFalse(ChatRoom.objects.filter(id=room_id).exists())


class TestProcessAvatar(TestCase):
    def _png_bytes(self, size=(64, 48)):
        img = Image.new("RGB", size, (10, 120, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_returns_square_webp_content_file(self):
        upload = ContentFile(self._png_bytes(), name="x.png")
        result = process_avatar(upload)
        self.assertIsInstance(result, ContentFile)

        from django.conf import settings

        decoded = Image.open(io.BytesIO(result.read()))
        self.assertEqual(decoded.format, "WEBP")
        self.assertEqual(
            decoded.size, (settings.AVATAR_SIZE_PX, settings.AVATAR_SIZE_PX)
        )

    def test_non_image_raises_value_error(self):
        upload = ContentFile(b"this is plainly not an image", name="x.txt")
        with self.assertRaises(ValueError):
            process_avatar(upload)

    def test_oversized_raises_value_error(self):
        from django.conf import settings

        big = ContentFile(self._png_bytes(), name="big.png")
        big.size = settings.AVATAR_MAX_BYTES + 1
        with self.assertRaises(ValueError):
            process_avatar(big)
