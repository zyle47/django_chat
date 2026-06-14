"""
Tests for PV — tier-perk wiring in HTTP views.

Covers:
- upload_image: per-tier image cap (bronze=5, superuser=100), freeing a slot
- room view: items include "tier" per author, no N+1 (batch resolve)
- enter_room: eligible user's room_color/room_icon stored; non-eligible silently dropped;
  invalid color/icon dropped (not errored)
- index context includes can_customize_room
- list_friends JSON includes "tier" for each friend
- edit_profile: process_avatar called with allow_animation matching tier
"""

import io
import json
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from chat.models import ChatImage, ChatMessage, ChatRoom, UserProfile
from chat.models.friendship import Friendship
from chat.services.room_access import grant_room_access

User = get_user_model()

_TIER_SETTINGS = {
    "CHAT_IMAGE_MAX_PER_USER": 25,
    "CHAT_IMAGE_MAX_PER_USER_BY_TIER": {
        "bronze": 5,
        "silver": 25,
        "gold": 50,
        "platinum": 100,
    },
    "CHAT_IMAGE_MAX_BYTES": 5 * 1024 * 1024,
    "CHAT_IMAGE_MAX_PIXELS": 40_000_000,
    "CHAT_IMAGE_EXPIRY_SECONDS": 43200,
    "ROOM_CREATION_LIMITS": {"bronze": 1, "silver": 5, "gold": 15, "platinum": None},
    "AVATAR_SIZE_PX": 64,
    "AVATAR_MAX_BYTES": 5 * 1024 * 1024,
}


def _make_png_bytes(width=4, height=4):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _make_png_file(name="test.png"):
    from django.core.files.uploadedfile import InMemoryUploadedFile

    data = _make_png_bytes()
    buf = io.BytesIO(data)
    return InMemoryUploadedFile(buf, "image", name, "image/png", len(data), None)


def _create_room_and_grant(client, session_key=None):
    """Create a test room and return it."""
    room = ChatRoom(name="testroom-pv")
    room.set_password("Secret99!")
    room.save()
    return room


def _grant_session_access(client, room):
    """Force session to grant access to this room."""
    session = client.session
    grant_room_access(session, room.name)
    session.save()


def _create_image_rows(room, user, count, *, expired=False):
    """Create ChatImage rows (non-expired by default) to simulate cap."""
    if expired:
        exp = timezone.now() - timezone.timedelta(hours=1)
    else:
        exp = timezone.now() + timezone.timedelta(hours=12)
    images = []
    for i in range(count):
        img = ChatImage.objects.create(
            room=room,
            user=user,
            username=user.username,
            color="#fff",
            expires_at=exp,
        )
        images.append(img)
    return images


# ──────────────────────────────────────────────────────────────────────────────
# upload_image — tier cap
# ──────────────────────────────────────────────────────────────────────────────


@override_settings(**_TIER_SETTINGS)
class UploadImageTierCapTests(TestCase):
    def setUp(self):
        self.bronze_user = User.objects.create_user(
            username="bronze_uploader", password="Pass123!", is_active=True
        )
        # Profile auto-created at bronze by signal; no changes needed
        self.room = ChatRoom(name="img-test-room")
        self.room.set_password("Secret99!")
        self.room.save()

    def _login_and_grant(self, user):
        self.client.force_login(user)
        _grant_session_access(self.client, self.room)

    def test_bronze_blocked_at_cap(self):
        """A bronze user with 5 active images should be rejected on the 6th."""
        self._login_and_grant(self.bronze_user)
        _create_image_rows(self.room, self.bronze_user, 5)

        with patch("chat.http.views.room.get_channel_layer") as mock_cl:
            mock_cl.return_value = MagicMock()
            response = self.client.post(
                reverse("upload-image", kwargs={"public_id": self.room.public_id}),
                {"image": _make_png_file()},
            )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)
        self.assertIn("5", data["error"])

    def test_bronze_accepts_within_cap(self):
        """A bronze user with 4 active images should succeed on the 5th."""
        self._login_and_grant(self.bronze_user)
        _create_image_rows(self.room, self.bronze_user, 4)

        # We mock the channel layer so the group_send doesn't blow up in tests
        with patch("chat.http.views.room.get_channel_layer") as mock_cl:
            mock_cl.return_value = MagicMock()
            mock_cl.return_value.group_send = MagicMock()
            with patch(
                "chat.http.views.room.async_to_sync", lambda fn: lambda *a, **kw: None
            ):
                with patch("chat.http.views.room.publish_room_activity"):
                    response = self.client.post(
                        reverse(
                            "upload-image", kwargs={"public_id": self.room.public_id}
                        ),
                        {"image": _make_png_file()},
                    )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["ok"])

    def test_superuser_not_blocked_at_bronze_cap(self):
        """A superuser (platinum) should not be blocked at the bronze cap of 5."""
        superuser = User.objects.create_superuser(
            username="suimg", password="Admin99!", email="su@ex.com"
        )
        self._login_and_grant(superuser)
        # Give the superuser 5 images (what would block a bronze user)
        _create_image_rows(self.room, superuser, 5)

        with patch("chat.http.views.room.get_channel_layer") as mock_cl:
            mock_cl.return_value = MagicMock()
            with patch(
                "chat.http.views.room.async_to_sync", lambda fn: lambda *a, **kw: None
            ):
                with patch("chat.http.views.room.publish_room_activity"):
                    response = self.client.post(
                        reverse(
                            "upload-image", kwargs={"public_id": self.room.public_id}
                        ),
                        {"image": _make_png_file()},
                    )

        # Superuser cap is 100, so with only 5 images they should be allowed
        self.assertEqual(response.status_code, 200)

    def test_expired_images_do_not_count_toward_cap(self):
        """Expired images do not consume a slot — a new upload should be allowed."""
        self._login_and_grant(self.bronze_user)
        # Create 5 EXPIRED images
        _create_image_rows(self.room, self.bronze_user, 5, expired=True)

        with patch("chat.http.views.room.get_channel_layer") as mock_cl:
            mock_cl.return_value = MagicMock()
            with patch(
                "chat.http.views.room.async_to_sync", lambda fn: lambda *a, **kw: None
            ):
                with patch("chat.http.views.room.publish_room_activity"):
                    response = self.client.post(
                        reverse(
                            "upload-image", kwargs={"public_id": self.room.public_id}
                        ),
                        {"image": _make_png_file()},
                    )

        self.assertEqual(response.status_code, 200)

    def test_deleting_image_frees_slot(self):
        """After deleting 1 of 5 active images, an upload should succeed."""
        self._login_and_grant(self.bronze_user)
        imgs = _create_image_rows(self.room, self.bronze_user, 5)
        # Delete one
        with patch("chat.http.views.room.get_channel_layer") as mock_cl:
            mock_cl.return_value = MagicMock()
            with patch(
                "chat.http.views.room.async_to_sync", lambda fn: lambda *a, **kw: None
            ):
                del_response = self.client.post(
                    reverse("delete-image", kwargs={"image_id": imgs[0].id})
                )
        self.assertEqual(del_response.status_code, 200)

        # Now 4 active remain; uploading the 5th should succeed
        with patch("chat.http.views.room.get_channel_layer") as mock_cl:
            mock_cl.return_value = MagicMock()
            with patch(
                "chat.http.views.room.async_to_sync", lambda fn: lambda *a, **kw: None
            ):
                with patch("chat.http.views.room.publish_room_activity"):
                    response = self.client.post(
                        reverse(
                            "upload-image", kwargs={"public_id": self.room.public_id}
                        ),
                        {"image": _make_png_file()},
                    )
        self.assertEqual(response.status_code, 200)


# ──────────────────────────────────────────────────────────────────────────────
# room view — items contain "tier", batch resolve is correct
# ──────────────────────────────────────────────────────────────────────────────


@override_settings(**_TIER_SETTINGS)
class RoomItemTierTests(TestCase):
    def setUp(self):
        self.bronze_user = User.objects.create_user(
            username="bronze_rv", password="Pass123!", is_active=True
        )
        self.silver_user = User.objects.create_user(
            username="silver_rv", password="Pass123!", is_active=True
        )
        UserProfile.objects.filter(user=self.silver_user).update(level="silver")
        self.platinum_user = User.objects.create_user(
            username="plat_rv", password="Pass123!", is_active=True
        )
        UserProfile.objects.filter(user=self.platinum_user).update(level="platinum")
        self.superuser = User.objects.create_superuser(
            username="su_rv", password="Admin99!", email="su_rv@ex.com"
        )

        self.room = ChatRoom(name="rv-room")
        self.room.set_password("Secret!")
        self.room.save()

    def _login_and_grant(self, user):
        self.client.force_login(user)
        _grant_session_access(self.client, self.room)

    def _add_message(self, user, text="hello"):
        return ChatMessage.objects.create(
            room=self.room,
            user=user,
            username=user.username,
            message=text,
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )

    def test_items_include_tier_per_author(self):
        """Each item in the room context has the correct 'tier' for its author."""
        self._add_message(self.bronze_user, "bronze msg")
        self._add_message(self.silver_user, "silver msg")
        self._add_message(self.platinum_user, "plat msg")
        self._add_message(self.superuser, "super msg")

        self._login_and_grant(self.bronze_user)
        response = self.client.get(
            reverse("room", kwargs={"public_id": self.room.public_id})
        )
        self.assertEqual(response.status_code, 200)
        items = response.context["items"]

        tier_by_username = {item["username"]: item["tier"] for item in items}
        self.assertEqual(tier_by_username["bronze_rv"], "bronze")
        self.assertEqual(tier_by_username["silver_rv"], "silver")
        self.assertEqual(tier_by_username["plat_rv"], "platinum")
        self.assertEqual(tier_by_username["su_rv"], "platinum")

    def test_item_tier_bronze_for_null_user(self):
        """A message whose user FK is null (deleted user) should get 'bronze'."""
        ChatMessage.objects.create(
            room=self.room,
            user=None,
            username="gone_user",
            message="orphan",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        self._login_and_grant(self.bronze_user)
        response = self.client.get(
            reverse("room", kwargs={"public_id": self.room.public_id})
        )
        self.assertEqual(response.status_code, 200)
        items = response.context["items"]
        orphan = next(i for i in items if i["username"] == "gone_user")
        self.assertEqual(orphan["tier"], "bronze")

    def test_batch_resolve_uses_two_queries_not_n_plus_1(self):
        """The tier batch resolution should use at most 2 DB queries regardless of authors."""
        for u in [self.bronze_user, self.silver_user, self.platinum_user]:
            self._add_message(u, f"msg from {u.username}")

        self._login_and_grant(self.bronze_user)

        # The room view as a whole will do some queries for messages, images,
        # UserRoomRead, etc. We track extra queries by checking the batch logic
        # in isolation via _batch_resolve_tiers.
        from chat.http.views.room import _batch_resolve_tiers

        user_ids = [
            self.bronze_user.id,
            self.silver_user.id,
            self.platinum_user.id,
            self.superuser.id,
        ]
        with self.assertNumQueries(2):
            result = _batch_resolve_tiers(user_ids)

        self.assertEqual(result[self.bronze_user.id], "bronze")
        self.assertEqual(result[self.silver_user.id], "silver")
        self.assertEqual(result[self.platinum_user.id], "platinum")
        self.assertEqual(result[self.superuser.id], "platinum")

    def test_room_display_uses_custom_color_and_icon(self):
        """When room has custom_color/custom_icon, the room view uses them."""
        self.room.custom_color = "#aabbcc"
        self.room.custom_icon = "🔥"
        self.room.save()

        self._login_and_grant(self.bronze_user)
        response = self.client.get(
            reverse("room", kwargs={"public_id": self.room.public_id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["room_color"], "#aabbcc")
        self.assertEqual(response.context["room_icon"], "🔥")


# ──────────────────────────────────────────────────────────────────────────────
# enter_room — custom color/icon wiring
# ──────────────────────────────────────────────────────────────────────────────


@override_settings(**_TIER_SETTINGS)
class EnterRoomCustomizationTests(TestCase):
    ENTER_URL = None

    def setUp(self):
        self.ENTER_URL = reverse("enter-room")
        self.platinum_user = User.objects.create_user(
            username="plat_enter", password="Pass123!", is_active=True
        )
        UserProfile.objects.filter(user=self.platinum_user).update(level="platinum")
        self.bronze_user = User.objects.create_user(
            username="bronze_enter", password="Pass123!", is_active=True
        )
        self.superuser = User.objects.create_superuser(
            username="su_enter", password="Admin99!", email="su_enter@ex.com"
        )

    def test_platinum_creator_custom_color_and_icon_stored(self):
        """A platinum user creating a room gets their color/icon stored on the room."""
        self.client.force_login(self.platinum_user)
        response = self.client.post(
            self.ENTER_URL,
            {
                "room_name": "plat-room-1",
                "room_password": "Secret99!",
                "room_color": "#1a2b3c",
                "room_icon": "🔥",
            },
        )
        self.assertEqual(response.status_code, 302)
        room = ChatRoom.objects.get(name="plat-room-1")
        self.assertEqual(room.custom_color, "#1a2b3c")
        self.assertEqual(room.custom_icon, "🔥")

    def test_superuser_creator_custom_color_and_icon_stored(self):
        """A superuser creating a room also gets their color/icon stored."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            self.ENTER_URL,
            {
                "room_name": "su-room-1",
                "room_password": "Secret99!",
                "room_color": "#ff0000",
                "room_icon": "💀",
            },
        )
        self.assertEqual(response.status_code, 302)
        room = ChatRoom.objects.get(name="su-room-1")
        self.assertEqual(room.custom_color, "#ff0000")
        self.assertEqual(room.custom_icon, "💀")

    def test_non_eligible_user_custom_fields_silently_ignored(self):
        """A bronze user's forged room_color/room_icon POST is silently dropped."""
        self.client.force_login(self.bronze_user)
        response = self.client.post(
            self.ENTER_URL,
            {
                "room_name": "bronze-room-1",
                "room_password": "Secret99!",
                "room_color": "#ff0000",
                "room_icon": "🔥",
            },
        )
        self.assertEqual(response.status_code, 302)
        room = ChatRoom.objects.get(name="bronze-room-1")
        self.assertEqual(room.custom_color, "")
        self.assertEqual(room.custom_icon, "")

    def test_eligible_user_invalid_color_dropped(self):
        """An eligible user posting an invalid hex color gets it dropped (no error)."""
        self.client.force_login(self.platinum_user)
        response = self.client.post(
            self.ENTER_URL,
            {
                "room_name": "plat-room-2",
                "room_password": "Secret99!",
                "room_color": "notacolor",
                "room_icon": "🔥",
            },
        )
        self.assertEqual(response.status_code, 302)
        room = ChatRoom.objects.get(name="plat-room-2")
        self.assertEqual(room.custom_color, "")  # dropped
        self.assertEqual(room.custom_icon, "🔥")  # icon was valid

    def test_eligible_user_invalid_icon_dropped(self):
        """An eligible user posting an icon not in ICON_CHOICES gets it dropped."""
        self.client.force_login(self.platinum_user)
        response = self.client.post(
            self.ENTER_URL,
            {
                "room_name": "plat-room-3",
                "room_password": "Secret99!",
                "room_color": "#aabbcc",
                "room_icon": "INVALID_ICON",
            },
        )
        self.assertEqual(response.status_code, 302)
        room = ChatRoom.objects.get(name="plat-room-3")
        self.assertEqual(room.custom_color, "#aabbcc")  # color was valid
        self.assertEqual(room.custom_icon, "")  # icon dropped


# ──────────────────────────────────────────────────────────────────────────────
# index context — can_customize_room
# ──────────────────────────────────────────────────────────────────────────────


@override_settings(**_TIER_SETTINGS)
class IndexCanCustomizeRoomTests(TestCase):
    def test_bronze_user_gets_false(self):
        user = User.objects.create_user(
            username="bronze_idx", password="Pass123!", is_active=True
        )
        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_customize_room"])

    def test_platinum_user_gets_true(self):
        user = User.objects.create_user(
            username="plat_idx", password="Pass123!", is_active=True
        )
        UserProfile.objects.filter(user=user).update(level="platinum")
        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_customize_room"])

    def test_superuser_gets_true(self):
        superuser = User.objects.create_superuser(
            username="su_idx", password="Admin99!", email="su_idx@ex.com"
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_customize_room"])


# ──────────────────────────────────────────────────────────────────────────────
# index lobby room cards — custom display used
# ──────────────────────────────────────────────────────────────────────────────


@override_settings(**_TIER_SETTINGS)
class IndexRoomCardCustomDisplayTests(TestCase):
    def test_lobby_room_card_reflects_custom_color(self):
        """A room with custom_color should have that color in the lobby display."""
        room = ChatRoom(name="custom-lobby-room")
        room.set_password("Secret!")
        room.custom_color = "#123456"
        room.save()

        user = User.objects.create_user(
            username="lobby_user", password="Pass123!", is_active=True
        )
        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)

        rooms = response.context["rooms"]
        room_in_ctx = next((r for r in rooms if r.name == "custom-lobby-room"), None)
        self.assertIsNotNone(room_in_ctx)
        self.assertEqual(room_in_ctx.color, "#123456")


# ──────────────────────────────────────────────────────────────────────────────
# list_friends — tier in each friend dict
# ──────────────────────────────────────────────────────────────────────────────


@override_settings(**_TIER_SETTINGS)
class ListFriendsTierTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice_tf", password="Pass123!", is_active=True
        )
        self.bob = User.objects.create_user(
            username="bob_tf", password="Pass123!", is_active=True
        )
        self.carol = User.objects.create_user(
            username="carol_tf", password="Pass123!", is_active=True
        )
        UserProfile.objects.filter(user=self.bob).update(level="gold")
        # carol stays at bronze

        Friendship.create_between(self.alice.id, self.bob.id)
        Friendship.create_between(self.alice.id, self.carol.id)

    def test_friend_dict_has_tier(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("api-friends-list"))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        friends = data["friends"]

        tier_by_name = {f["username"]: f["tier"] for f in friends}
        self.assertIn("bob_tf", tier_by_name)
        self.assertIn("carol_tf", tier_by_name)
        self.assertEqual(tier_by_name["bob_tf"], "gold")
        self.assertEqual(tier_by_name["carol_tf"], "bronze")

    def test_superuser_friend_shows_platinum(self):
        superuser = User.objects.create_superuser(
            username="su_friend", password="Admin99!", email="su_f@ex.com"
        )
        Friendship.create_between(self.alice.id, superuser.id)

        self.client.force_login(self.alice)
        response = self.client.get(reverse("api-friends-list"))
        data = json.loads(response.content)
        friends = data["friends"]
        tier_by_name = {f["username"]: f["tier"] for f in friends}
        self.assertEqual(tier_by_name["su_friend"], "platinum")


# ──────────────────────────────────────────────────────────────────────────────
# edit_profile — process_avatar called with correct allow_animation kwarg
# ──────────────────────────────────────────────────────────────────────────────


@override_settings(
    AVATAR_SIZE_PX=64,
    AVATAR_MAX_BYTES=5 * 1024 * 1024,
    CHAT_IMAGE_MAX_PIXELS=40_000_000,
)
class EditProfileAnimationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore

        self._session_class = SessionStore
        self._messages_class = FallbackStorage
        # edit_profile saves the avatar to disk; isolate it to a throwaway
        # MEDIA_ROOT so the test never writes into the real media/ dir.
        self._tmp_media = tempfile.mkdtemp()
        self._media_override = override_settings(MEDIA_ROOT=self._tmp_media)
        self._media_override.enable()

    def tearDown(self):
        self._media_override.disable()
        shutil.rmtree(self._tmp_media, ignore_errors=True)

    def _make_request(self, user, files=None):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore

        request = self.factory.post("/profile/edit/", files or {})
        if files:
            request.FILES.update(files)
        request.user = user
        session = SessionStore()
        session.create()
        request.session = session
        request._messages = FallbackStorage(request)
        return request

    def _png_upload(self):
        from django.core.files.uploadedfile import InMemoryUploadedFile

        data = _make_png_bytes()
        buf = io.BytesIO(data)
        return InMemoryUploadedFile(
            buf, "avatar", "a.png", "image/png", len(data), None
        )

    def test_bronze_user_process_avatar_called_without_animation(self):
        """process_avatar must be called with allow_animation=False for bronze user."""
        from django.core.files.base import ContentFile

        user = User.objects.create_user(
            username="bronze_pa", password="Pass123!", is_active=True
        )
        request = self._make_request(user, {"avatar": self._png_upload()})

        fake_content = ContentFile(b"\x00" * 10, name="a.webp")

        with patch(
            "chat.http.views.profile.process_avatar", return_value=fake_content
        ) as mock_pa:
            with patch("chat.http.views.profile.reverse", return_value="/avatar/1/"):
                from chat.http.views.profile import edit_profile

                edit_profile(request)

        mock_pa.assert_called_once()
        _, kwargs = mock_pa.call_args
        self.assertFalse(kwargs.get("allow_animation", True))

    def test_platinum_user_process_avatar_called_with_animation(self):
        """process_avatar must be called with allow_animation=True for platinum user."""
        from django.core.files.base import ContentFile

        user = User.objects.create_user(
            username="plat_pa", password="Pass123!", is_active=True
        )
        UserProfile.objects.filter(user=user).update(level="platinum")
        # refresh profile cache
        user.refresh_from_db()
        request = self._make_request(user, {"avatar": self._png_upload()})

        fake_content = ContentFile(b"\x00" * 10, name="a.webp")

        with patch(
            "chat.http.views.profile.process_avatar", return_value=fake_content
        ) as mock_pa:
            with patch("chat.http.views.profile.reverse", return_value="/avatar/1/"):
                from chat.http.views.profile import edit_profile

                edit_profile(request)

        mock_pa.assert_called_once()
        _, kwargs = mock_pa.call_args
        self.assertTrue(kwargs.get("allow_animation", False))

    def test_superuser_process_avatar_called_with_animation(self):
        """process_avatar must be called with allow_animation=True for superuser."""
        from django.core.files.base import ContentFile

        superuser = User.objects.create_superuser(
            username="su_pa", password="Admin99!", email="su_pa@ex.com"
        )
        request = self._make_request(superuser, {"avatar": self._png_upload()})

        fake_content = ContentFile(b"\x00" * 10, name="a.webp")

        with patch(
            "chat.http.views.profile.process_avatar", return_value=fake_content
        ) as mock_pa:
            with patch("chat.http.views.profile.reverse", return_value="/avatar/1/"):
                from chat.http.views.profile import edit_profile

                edit_profile(request)

        mock_pa.assert_called_once()
        _, kwargs = mock_pa.call_args
        self.assertTrue(kwargs.get("allow_animation", False))
