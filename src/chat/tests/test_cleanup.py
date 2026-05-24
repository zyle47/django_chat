from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from chat.models import ChatImage, ChatMessage, ChatRoom, DirectMessage, FriendRequest


class TestCleanupExpiredMessages(TestCase):
    def setUp(self):
        self.room = ChatRoom.objects.create(name="general")
        self.user = User.objects.create_user(username="alice", password="Pass123", is_active=True)
        now = timezone.now()
        ChatMessage.objects.create(
            room=self.room, user=self.user, username="alice",
            message="expired-msg", expires_at=now - timezone.timedelta(hours=1),
        )
        ChatMessage.objects.create(
            room=self.room, user=self.user, username="alice",
            message="active-msg", expires_at=now + timezone.timedelta(hours=1),
        )

    def test_expired_messages_are_deleted(self):
        call_command("cleanup_expired_messages", stdout=StringIO())
        messages = list(ChatMessage.objects.values_list("message", flat=True))
        self.assertNotIn("expired-msg", messages)

    def test_active_messages_are_preserved(self):
        call_command("cleanup_expired_messages", stdout=StringIO())
        messages = list(ChatMessage.objects.values_list("message", flat=True))
        self.assertIn("active-msg", messages)

    def test_daily_stats_populated_for_expired_messages(self):
        from datetime import date
        from chat.models import DailyStats
        call_command("cleanup_expired_messages", stdout=StringIO())
        today = date.today()
        stat = DailyStats.objects.filter(date=today).first()
        self.assertIsNotNone(stat)
        self.assertGreaterEqual(stat.message_count, 1)


class TestCleanupExpiredImages(TestCase):
    def setUp(self):
        self.room = ChatRoom.objects.create(name="gallery")
        self.user = User.objects.create_user(username="bob", password="Pass123", is_active=True)
        now = timezone.now()
        # image='' is falsy, so the command skips the file-system delete and only removes the DB row
        ChatImage.objects.create(
            room=self.room, user=self.user, username="bob", color="#fff",
            image="", expires_at=now - timezone.timedelta(hours=1),
        )
        ChatImage.objects.create(
            room=self.room, user=self.user, username="bob", color="#fff",
            image="", expires_at=now + timezone.timedelta(hours=1),
        )

    def test_expired_images_are_deleted(self):
        call_command("cleanup_expired_images", stdout=StringIO())
        self.assertEqual(ChatImage.objects.count(), 1)

    def test_active_images_are_preserved(self):
        call_command("cleanup_expired_images", stdout=StringIO())
        surviving = ChatImage.objects.first()
        self.assertGreater(surviving.expires_at, timezone.now())


class TestCleanupExpiredDMs(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="Pass123", is_active=True)
        self.bob = User.objects.create_user(username="bob", password="Pass123", is_active=True)
        now = timezone.now()
        DirectMessage.objects.create(
            from_user=self.alice, to_user=self.bob,
            message="expired-dm", expires_at=now - timezone.timedelta(hours=1),
        )
        DirectMessage.objects.create(
            from_user=self.alice, to_user=self.bob,
            message="active-dm", expires_at=now + timezone.timedelta(hours=1),
        )

    def test_expired_dms_are_deleted(self):
        call_command("cleanup_expired_dms", stdout=StringIO())
        dms = list(DirectMessage.objects.values_list("message", flat=True))
        self.assertNotIn("expired-dm", dms)

    def test_active_dms_are_preserved(self):
        call_command("cleanup_expired_dms", stdout=StringIO())
        dms = list(DirectMessage.objects.values_list("message", flat=True))
        self.assertIn("active-dm", dms)


class TestCleanupExpiredFriendRequests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="Pass123", is_active=True)
        self.bob = User.objects.create_user(username="bob", password="Pass123", is_active=True)
        now = timezone.now()
        FriendRequest.objects.create(
            from_user=self.alice, to_user=self.bob,
            expires_at=now - timezone.timedelta(minutes=10),
        )
        FriendRequest.objects.create(
            from_user=self.bob, to_user=self.alice,
            expires_at=now + timezone.timedelta(minutes=5),
        )

    def test_expired_friend_requests_are_deleted(self):
        call_command("cleanup_expired_friend_requests", stdout=StringIO())
        self.assertEqual(FriendRequest.objects.count(), 1)

    def test_active_friend_requests_are_preserved(self):
        call_command("cleanup_expired_friend_requests", stdout=StringIO())
        surviving = FriendRequest.objects.first()
        self.assertGreater(surviving.expires_at, timezone.now())
