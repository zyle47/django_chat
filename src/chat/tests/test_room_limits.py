from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from chat.models import ChatRoom
from chat.models.profile import UserProfile


class RoomCreationLimitTests(TestCase):
    """Tests for per-tier room creation caps enforced by enter_room."""

    ENTER_URL = None  # resolved in setUp

    def setUp(self):
        self.ENTER_URL = reverse("enter-room")

    # ------------------------------------------------------------------ helpers

    def _create_user(self, username, level="bronze"):
        user = User.objects.create_user(
            username=username, password="Pass123!", is_active=True
        )
        # A signal auto-creates the profile on user save; update level here.
        UserProfile.objects.filter(user=user).update(level=level)
        return user

    def _post_enter(self, room_name, room_password="Secret99!"):
        return self.client.post(
            self.ENTER_URL,
            {"room_name": room_name, "room_password": room_password},
            follow=True,
        )

    # ------------------------------------------------------------------ tests

    def test_bronze_user_can_create_first_room(self):
        user = self._create_user("bronze_user")
        self.client.force_login(user)

        response = self._post_enter("room-alpha")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ChatRoom.objects.filter(creator=user, is_deleted=False).count(), 1
        )

    def test_bronze_user_blocked_on_second_room(self):
        user = self._create_user("bronze_two")
        self.client.force_login(user)

        # First room — must succeed
        self._post_enter("room-b1")
        self.assertEqual(
            ChatRoom.objects.filter(creator=user, is_deleted=False).count(), 1
        )

        # Second room — must be blocked
        response = self._post_enter("room-b2")
        self.assertEqual(response.status_code, 200)
        # Room count stays at 1
        self.assertEqual(
            ChatRoom.objects.filter(creator=user, is_deleted=False).count(), 1
        )
        # An error message is present in the response
        messages = list(response.context["messages"])
        self.assertTrue(
            any("tier allows" in str(m) for m in messages),
            f"Expected tier-limit error, got: {[str(m) for m in messages]}",
        )

    def test_silver_user_can_create_up_to_five_rooms(self):
        user = self._create_user("silver_user", level="silver")
        self.client.force_login(user)

        for i in range(5):
            response = self._post_enter(f"room-s{i}")
            self.assertEqual(response.status_code, 200)

        self.assertEqual(
            ChatRoom.objects.filter(creator=user, is_deleted=False).count(), 5
        )

        # Sixth room must be blocked
        response = self._post_enter("room-s5")
        self.assertEqual(
            ChatRoom.objects.filter(creator=user, is_deleted=False).count(), 5
        )
        messages = list(response.context["messages"])
        self.assertTrue(
            any("tier allows" in str(m) for m in messages),
            f"Expected tier-limit error on 6th room, got: {[str(m) for m in messages]}",
        )

    def test_created_room_has_correct_creator(self):
        user = self._create_user("creator_check")
        self.client.force_login(user)

        self._post_enter("room-creator")
        room = ChatRoom.objects.get(name="room-creator")
        self.assertEqual(room.creator, user)

    def test_superuser_is_unrestricted(self):
        superuser = User.objects.create_superuser(
            username="superadmin", password="Admin99!", email="admin@example.com"
        )
        self.client.force_login(superuser)

        # Superusers have no profile / unlimited via room_creation_limit returning None
        for i in range(4):
            response = self._post_enter(f"room-su{i}")
            self.assertEqual(response.status_code, 200)

        self.assertEqual(
            ChatRoom.objects.filter(creator=superuser, is_deleted=False).count(), 4
        )
