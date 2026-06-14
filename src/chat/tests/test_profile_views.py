"""
Tests for chat.http.views.profile — uses RequestFactory; no URL reversals.
"""

import io
import os
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from PIL import Image

from chat.http.views.profile import edit_profile, serve_avatar, upgrade_account
from chat.models import UpgradeRequest, UserProfile

User = get_user_model()


def make_png_upload(width=64, height=64, name="test.png"):
    """Create a small in-memory PNG upload."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    img.save(buf, format="PNG")
    buf.seek(0)
    size = buf.getbuffer().nbytes
    return InMemoryUploadedFile(buf, "image", name, "image/png", size, None)


def make_non_image_upload(name="bad.txt"):
    """Create an upload that is definitely not a valid image."""
    buf = io.BytesIO(b"this is not an image at all, just text bytes 0000")
    size = buf.getbuffer().nbytes
    return InMemoryUploadedFile(buf, "avatar", name, "text/plain", size, None)


def _attach_session_and_messages(request):
    """Attach session + messages middleware shims to a factory request."""
    session = SessionStore()
    session.create()
    request.session = session
    messages = FallbackStorage(request)
    request._messages = messages


UPGRADE_TIERS_FAKE = {
    "silver": {"label": "Silver", "btc": "0.005", "eth": "0.05"},
    "gold": {"label": "Gold", "btc": "0.01", "eth": "0.1"},
}
CRYPTO_ADDRESSES_FAKE = {"btc": "bc1qfakebtcaddress", "eth": "0xFakeEthAddress"}


@override_settings(
    UPGRADE_TIERS=UPGRADE_TIERS_FAKE,
    CRYPTO_ADDRESSES=CRYPTO_ADDRESSES_FAKE,
    AVATAR_SIZE_PX=64,
    AVATAR_MAX_BYTES=5 * 1024 * 1024,
)
class EditProfileViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="tester", password="pass")

    def _post(self, data=None, files=None):
        request = self.factory.post("/profile/edit/", data=data or {})
        if files:
            request.FILES.update(files)
        request.user = self.user
        _attach_session_and_messages(request)
        return request

    def test_save_valid_png_creates_webp_avatar(self):
        """Uploading a valid PNG should produce a WebP avatar on the profile."""
        from unittest.mock import patch

        upload = make_png_upload()
        request = self._post(files={"avatar": upload})

        with patch("chat.http.views.profile.reverse", return_value="/avatar/1/"):
            response = edit_profile(request)

        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertTrue(data["ok"])
        self.assertIn("avatar_url", data)

        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(bool(profile.avatar))
        self.assertTrue(profile.avatar.name.endswith(".webp"))

        # Clean up the saved file
        try:
            if os.path.isfile(profile.avatar.path):
                os.remove(profile.avatar.path)
        except Exception:
            pass

    def test_non_image_returns_400(self):
        """A non-image file should return 400 with ok=False."""
        upload = make_non_image_upload()
        request = self._post(files={"avatar": upload})
        response = edit_profile(request)

        self.assertEqual(response.status_code, 400)
        import json

        data = json.loads(response.content)
        self.assertFalse(data["ok"])
        self.assertIn("error", data)

    def test_remove_action_clears_avatar(self):
        """action=remove should clear the avatar field."""
        from unittest.mock import patch

        # First save a real avatar
        upload = make_png_upload()
        request1 = self._post(files={"avatar": upload})
        with patch("chat.http.views.profile.reverse", return_value="/avatar/1/"):
            edit_profile(request1)

        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(bool(profile.avatar))
        saved_path = None
        try:
            saved_path = profile.avatar.path
        except Exception:
            pass

        # Now remove it
        request2 = self._post(data={"action": "remove"})
        response = edit_profile(request2)

        import json

        data = json.loads(response.content)
        self.assertTrue(data["ok"])

        profile.refresh_from_db()
        self.assertFalse(bool(profile.avatar))

        # File should be gone too
        if saved_path:
            self.assertFalse(os.path.exists(saved_path))

    def test_remove_with_no_avatar_is_fine(self):
        """action=remove when there is no avatar should still return ok=True."""
        UserProfile.objects.get_or_create(user=self.user)
        request = self._post(data={"action": "remove"})
        response = edit_profile(request)
        import json

        data = json.loads(response.content)
        self.assertTrue(data["ok"])

    def test_no_file_returns_400(self):
        """POST with no file and no action should return 400."""
        request = self._post()
        response = edit_profile(request)
        self.assertEqual(response.status_code, 400)


@override_settings(
    AVATAR_SIZE_PX=64,
    AVATAR_MAX_BYTES=5 * 1024 * 1024,
)
class ServeAvatarViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="avataruser", password="pass")

    def test_404_when_no_profile_row(self):
        """serve_avatar should 404 when no UserProfile row exists for the user_id."""
        from django.http import Http404

        # Use a non-existent user_id (large number unlikely to exist)
        nonexistent_user_id = 999999
        request = self.factory.get(f"/avatar/{nonexistent_user_id}/")
        request.user = self.user
        with self.assertRaises(Http404):
            serve_avatar(request, user_id=nonexistent_user_id)

    def test_404_when_profile_has_no_avatar(self):
        """serve_avatar should 404 when the profile has no avatar."""
        from django.http import Http404

        # Signal auto-creates the profile; just ensure avatar is cleared
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.avatar = None
        profile.save()
        request = self.factory.get(f"/avatar/{self.user.id}/")
        request.user = self.user
        with self.assertRaises(Http404):
            serve_avatar(request, user_id=self.user.id)

    def test_streams_bytes_when_avatar_present(self):
        """serve_avatar should return a FileResponse streaming the avatar bytes."""
        profile, _ = UserProfile.objects.get_or_create(user=self.user)

        # Write a tiny real WebP via the avatar service so the path actually exists
        from chat.services.avatar import process_avatar

        upload = make_png_upload()
        content_file = process_avatar(upload)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save the content file to a temporary location then point the field at it
            tmp_path = os.path.join(tmpdir, f"{self.user.id}.webp")
            with open(tmp_path, "wb") as fh:
                fh.write(content_file.read())

            # Manually assign the avatar field to point at the tmp file.
            # We use the field's .name attribute; Django's FieldFile reads .path via storage.
            # It's simpler to save via the field API into MEDIA_ROOT and clean up.
            import shutil

            from django.conf import settings as djsettings

            media_avatars = os.path.join(djsettings.MEDIA_ROOT, "avatars")
            os.makedirs(media_avatars, exist_ok=True)
            dest = os.path.join(media_avatars, f"{self.user.id}.webp")
            shutil.copy(tmp_path, dest)

            profile.avatar = f"avatars/{self.user.id}.webp"
            profile.save()

            try:
                request = self.factory.get(f"/avatar/{self.user.id}/")
                request.user = self.user
                response = serve_avatar(request, user_id=self.user.id)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/webp")
                self.assertIn("private", response["Cache-Control"])
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")

                # Verify the response actually has bytes
                content = b"".join(response.streaming_content)
                self.assertGreater(len(content), 0)
            finally:
                # Clean up
                profile.avatar = None
                profile.save()
                try:
                    os.remove(dest)
                except Exception:
                    pass
                response.close()


@override_settings(
    UPGRADE_TIERS=UPGRADE_TIERS_FAKE,
    CRYPTO_ADDRESSES=CRYPTO_ADDRESSES_FAKE,
)
class UpgradeAccountViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="upgrader", password="pass")

    def test_get_returns_tiers_addresses_and_level(self):
        """GET /upgrade/ should return current_level, tiers, addresses."""
        request = self.factory.get("/upgrade/")
        request.user = self.user
        response = upgrade_account(request)

        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertIn("current_level", data)
        self.assertIn("tiers", data)
        self.assertIn("addresses", data)
        self.assertEqual(data["tiers"], UPGRADE_TIERS_FAKE)
        self.assertEqual(data["addresses"], CRYPTO_ADDRESSES_FAKE)
        # Default level is bronze
        self.assertEqual(data["current_level"], "bronze")

    def test_post_creates_upgrade_request(self):
        """POST with a valid tier should create an UpgradeRequest row."""
        request = self.factory.post("/upgrade/", {"requested_level": "silver"})
        request.user = self.user
        response = upgrade_account(request)

        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertTrue(data["ok"])

        self.assertTrue(
            UpgradeRequest.objects.filter(
                user=self.user, requested_level="silver"
            ).exists()
        )

    def test_post_invalid_tier_returns_400(self):
        """POST with a tier not in UPGRADE_TIERS should return 400."""
        request = self.factory.post("/upgrade/", {"requested_level": "diamond"})
        request.user = self.user
        response = upgrade_account(request)

        self.assertEqual(response.status_code, 400)
        import json

        data = json.loads(response.content)
        self.assertFalse(data["ok"])

    def test_post_does_not_change_level_automatically(self):
        """Submitting an upgrade request must NOT change the user's level."""
        request = self.factory.post("/upgrade/", {"requested_level": "gold"})
        request.user = self.user
        upgrade_account(request)

        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.assertEqual(profile.level, "bronze")
