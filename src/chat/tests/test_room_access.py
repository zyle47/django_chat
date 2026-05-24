from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from chat.models import ChatRoom
from chat.services.room_access import ROOM_ACCESS_SESSION_KEY, grant_room_access, has_room_access


class _FakeSession(dict):
    """Minimal session stand-in: supports .modified like Django's SessionStore."""
    modified = False


class TestRoomAccessService(TestCase):
    def test_empty_session_has_no_access(self):
        self.assertFalse(has_room_access(_FakeSession(), "general"))

    def test_grant_then_check_returns_true(self):
        session = _FakeSession()
        grant_room_access(session, "general")
        self.assertTrue(has_room_access(session, "general"))

    def test_grant_does_not_leak_to_other_rooms(self):
        session = _FakeSession()
        grant_room_access(session, "general")
        self.assertFalse(has_room_access(session, "support"))

    def test_grant_is_idempotent(self):
        session = _FakeSession()
        grant_room_access(session, "general")
        grant_room_access(session, "general")
        self.assertEqual(session[ROOM_ACCESS_SESSION_KEY].count("general"), 1)

    def test_multiple_rooms_can_be_granted(self):
        session = _FakeSession()
        grant_room_access(session, "general")
        grant_room_access(session, "support")
        self.assertTrue(has_room_access(session, "general"))
        self.assertTrue(has_room_access(session, "support"))


class TestRoomViewAccessEnforcement(TestCase):
    def test_room_without_session_access_redirects_to_lobby(self):
        user = User.objects.create_user(username="alice", password="Pass123", is_active=True)
        self.client.force_login(user)
        room = ChatRoom(name="vault")
        room.set_password("Secret123")
        room.save()

        response = self.client.get(reverse("room", kwargs={"public_id": room.public_id}))
        self.assertRedirects(response, reverse("index"))

    def test_superuser_bypasses_session_access_check(self):
        superuser = User.objects.create_superuser(username="root", password="Admin123", email="root@test.com")
        self.client.force_login(superuser)
        room = ChatRoom.objects.create(name="hidden")

        response = self.client.get(reverse("room", kwargs={"public_id": room.public_id}))
        self.assertEqual(response.status_code, 200)

    def test_nonexistent_room_redirects_to_lobby(self):
        user = User.objects.create_user(username="alice", password="Pass123", is_active=True)
        self.client.force_login(user)

        response = self.client.get(reverse("room", kwargs={"public_id": "a" * 64}))
        self.assertRedirects(response, reverse("index"))
