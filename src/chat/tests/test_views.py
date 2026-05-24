import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chat.http.views.auth import SIGNUP_PENDING_SESSION_KEY
from chat.models import ChatMessage, ChatRoom


class TestChatViews(TestCase):
    def test_index_page_renders(self):
        user = User.objects.create_user(
            username="testuser", password="Pass123", is_active=True
        )
        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chat/index.html")
        self.assertContains(response, "room-name-input")

    def test_index_page_requires_login(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_room_page_requires_login(self):
        response = self.client.get(reverse("room", kwargs={"public_id": "fakehash123"}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_enter_room_creates_password_protected_room_and_grants_access(self):
        user = User.objects.create_user(username="nemanja", password="Password123")
        self.client.force_login(user)

        enter_response = self.client.post(
            reverse("enter-room"),
            {"room_name": "general", "room_password": "TopSecret123"},
        )
        self.assertEqual(enter_response.status_code, 302)

        room_obj = ChatRoom.objects.get(name="general")
        self.assertTrue(room_obj.check_password("TopSecret123"))
        self.assertEqual(
            enter_response.url,
            reverse("room", kwargs={"public_id": room_obj.public_id}),
        )

        room_response = self.client.get(
            reverse("room", kwargs={"public_id": room_obj.public_id})
        )
        self.assertEqual(room_response.status_code, 200)
        self.assertContains(room_response, "nemanja")

    def test_enter_existing_room_requires_correct_password(self):
        user = User.objects.create_user(username="member", password="Password123")
        self.client.force_login(user)
        room_obj = ChatRoom(name="support")
        room_obj.set_password("ValidPass123")
        room_obj.save()

        bad_response = self.client.post(
            reverse("enter-room"),
            {"room_name": "support", "room_password": "WrongPass"},
            follow=True,
        )
        self.assertEqual(bad_response.status_code, 200)
        self.assertContains(bad_response, "Invalid room password.")

        room_response = self.client.get(
            reverse("room", kwargs={"public_id": room_obj.public_id}),
            follow=True,
        )
        self.assertEqual(room_response.status_code, 200)
        self.assertContains(
            room_response, "Enter room password from the lobby to access this room."
        )

    def test_authenticated_user_sees_lobby_controls(self):
        user = User.objects.create_user(username="member", password="Password123")
        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertContains(response, "room-name-input")
        self.assertContains(response, "room-search")

    def test_signup_creates_inactive_user_and_redirects_pending(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newuser",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("signup-pending"))
        self.assertTrue(
            User.objects.filter(username="newuser", is_active=False).exists()
        )

    def test_inactive_user_cannot_log_in(self):
        User.objects.create_user(
            username="pendinguser", password="StrongPass123", is_active=False
        )

        response = self.client.post(
            reverse("login"),
            {"username": "pendinguser", "password": "StrongPass123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_signup_pending_page_requires_signup_session_flag(self):
        response = self.client.get(reverse("signup-pending"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("signup"))

    def test_signup_pending_page_is_one_time_after_signup(self):
        self.client.post(
            reverse("signup"),
            {
                "username": "pendingonce",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )

        first_visit = self.client.get(reverse("signup-pending"))
        self.assertEqual(first_visit.status_code, 200)

        second_visit = self.client.get(reverse("signup-pending"))
        self.assertEqual(second_visit.status_code, 302)
        self.assertEqual(second_visit.url, reverse("signup"))

    def test_signup_sets_pending_session_flag(self):
        self.client.post(
            reverse("signup"),
            {
                "username": "pendingflag",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertTrue(self.client.session.get(SIGNUP_PENDING_SESSION_KEY))

    def test_authenticated_user_visiting_signup_redirects_to_index(self):
        user = User.objects.create_user(
            username="loggedin", password="Pass123", is_active=True
        )
        self.client.force_login(user)
        response = self.client.get(reverse("signup"))
        self.assertRedirects(response, reverse("index"))

    def test_enter_room_with_empty_name_shows_error(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("enter-room"),
            {"room_name": "   ", "room_password": ""},
            follow=True,
        )
        self.assertContains(response, "Please enter a valid room name.")

    def test_enter_room_new_room_without_password_shows_error(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("enter-room"),
            {"room_name": "brandnew", "room_password": ""},
            follow=True,
        )
        self.assertContains(response, "New rooms must have a password.")
        self.assertFalse(ChatRoom.objects.filter(name="brandnew").exists())

    def test_enter_room_deleted_room_shows_error(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        self.client.force_login(user)
        room = ChatRoom.objects.create(name="zombie")
        room.soft_delete()
        room.save(update_fields=["is_deleted", "deleted_at"])

        response = self.client.post(
            reverse("enter-room"),
            {"room_name": "zombie", "room_password": "anything"},
            follow=True,
        )
        self.assertContains(response, "This room is currently unavailable.")


class TestRoomUnreadStateView(TestCase):
    def test_requires_login(self):
        response = self.client.get(
            reverse("api-room-unread", kwargs={"public_id": "a" * 64})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_nonexistent_room_returns_unread_false(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse("api-room-unread", kwargs={"public_id": "a" * 64})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.content)["unread"])

    def test_room_with_no_messages_returns_unread_false(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        self.client.force_login(user)
        room = ChatRoom.objects.create(name="emptyroom")
        response = self.client.get(
            reverse("api-room-unread", kwargs={"public_id": room.public_id})
        )
        self.assertFalse(json.loads(response.content)["unread"])

    def test_room_with_unread_message_returns_unread_true(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        other = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        self.client.force_login(user)
        room = ChatRoom.objects.create(name="chatroom")
        ChatMessage.objects.create(
            room=room,
            user=other,
            username="bob",
            message="hey",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        response = self.client.get(
            reverse("api-room-unread", kwargs={"public_id": room.public_id})
        )
        self.assertTrue(json.loads(response.content)["unread"])


class TestIndexHourlyStats(TestCase):
    def test_index_with_recent_messages_populates_hourly_slots(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        room = ChatRoom.objects.create(name="statsroom")
        ChatMessage.objects.create(
            room=room,
            username="alice",
            message="hi",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        stats = response.context["stats"]
        self.assertGreater(stats["messages_total"], 0)
        self.assertTrue(any(s > 0 for s in stats["hourly"]))
