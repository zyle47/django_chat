import io

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase
from PIL import Image

from chat.models.profile import UserProfile
from chat.services.avatar import process_avatar
from chat.services.room_display import _ICONS, room_display
from chat.services.tiers import (
    ICON_CHOICES,
    active_image_cap,
    can_animate_avatar,
    can_customize_room,
    effective_level,
)


def _set_level(user, level):
    UserProfile.objects.filter(user=user).update(level=level)
    user.refresh_from_db()
    return user


class EffectiveLevelTests(TestCase):
    def test_plain_user_defaults_bronze(self):
        user = User.objects.create_user(username="plain", password="Pass123!")
        self.assertEqual(effective_level(user), "bronze")

    def test_reflects_explicit_levels(self):
        for level in ("silver", "gold", "platinum"):
            user = User.objects.create_user(username=f"u_{level}", password="Pass123!")
            _set_level(user, level)
            self.assertEqual(effective_level(user), level)

    def test_superuser_is_platinum_even_when_bronze(self):
        admin = User.objects.create_superuser(
            username="admin", password="Pass123!", email=""
        )
        _set_level(admin, "bronze")
        self.assertEqual(admin.profile.level, "bronze")
        self.assertEqual(effective_level(admin), "platinum")

    def test_anonymous_user_is_bronze(self):
        self.assertEqual(effective_level(AnonymousUser()), "bronze")

    def test_none_user_is_bronze(self):
        self.assertEqual(effective_level(None), "bronze")

    def test_user_without_profile_is_bronze(self):
        # A bare object with no `.profile` and no `.is_superuser` must not crash.
        class Bare:
            pass

        self.assertEqual(effective_level(Bare()), "bronze")


class ActiveImageCapTests(TestCase):
    def _user(self, level):
        user = User.objects.create_user(username=f"cap_{level}", password="Pass123!")
        return _set_level(user, level)

    def test_caps_per_level(self):
        self.assertEqual(active_image_cap(self._user("bronze")), 5)
        self.assertEqual(active_image_cap(self._user("silver")), 25)
        self.assertEqual(active_image_cap(self._user("gold")), 50)
        self.assertEqual(active_image_cap(self._user("platinum")), 100)

    def test_superuser_gets_platinum_cap(self):
        admin = User.objects.create_superuser(
            username="capadmin", password="Pass123!", email=""
        )
        _set_level(admin, "bronze")
        self.assertEqual(active_image_cap(admin), 100)

    def test_missing_tier_key_falls_back_to_default(self):
        with self.settings(
            CHAT_IMAGE_MAX_PER_USER_BY_TIER={"silver": 25},
            CHAT_IMAGE_MAX_PER_USER=7,
        ):
            # bronze key is absent in the patched mapping -> fallback default.
            self.assertEqual(active_image_cap(self._user("bronze")), 7)


class PerkGateTests(TestCase):
    def _user(self, level):
        user = User.objects.create_user(username=f"perk_{level}", password="Pass123!")
        return _set_level(user, level)

    def test_only_platinum_can_customize_and_animate(self):
        for level in ("bronze", "silver", "gold"):
            user = self._user(level)
            self.assertFalse(can_customize_room(user), level)
            self.assertFalse(can_animate_avatar(user), level)

        platinum = self._user("platinum")
        self.assertTrue(can_customize_room(platinum))
        self.assertTrue(can_animate_avatar(platinum))

    def test_superuser_can_customize_and_animate(self):
        admin = User.objects.create_superuser(
            username="perkadmin", password="Pass123!", email=""
        )
        _set_level(admin, "bronze")
        self.assertTrue(can_customize_room(admin))
        self.assertTrue(can_animate_avatar(admin))


class IconChoicesTests(SimpleTestCase):
    def test_icon_choices_is_room_display_icons(self):
        # Single source of truth: tiers re-exports room_display._ICONS.
        self.assertIs(ICON_CHOICES, _ICONS)


class RoomDisplayCustomTests(SimpleTestCase):
    def test_empty_customs_match_name_hash_default(self):
        default = room_display("general")
        self.assertEqual(room_display("general", "", ""), default)

    def test_custom_color_overrides_default(self):
        default = room_display("general")
        out = room_display("general", custom_color="#abcdef")
        self.assertEqual(out["color"], "#abcdef")
        # Icon untouched when only color is customised.
        self.assertEqual(out["icon"], default["icon"])
        # Hash is still name-derived.
        self.assertEqual(out["hash"], default["hash"])

    def test_custom_icon_overrides_default(self):
        default = room_display("general")
        out = room_display("general", custom_icon="🦄")
        self.assertEqual(out["icon"], "🦄")
        self.assertEqual(out["color"], default["color"])

    def test_both_customs_override(self):
        out = room_display("general", custom_color="#123456", custom_icon="🦄")
        self.assertEqual(out["color"], "#123456")
        self.assertEqual(out["icon"], "🦄")

    def test_empty_custom_falls_back_gracefully(self):
        # Falsy custom values (empty string) must not override.
        default = room_display("support")
        out = room_display("support", custom_color="", custom_icon="")
        self.assertEqual(out["color"], default["color"])
        self.assertEqual(out["icon"], default["icon"])


class AvatarAnimationTests(SimpleTestCase):
    def _gif_bytes(self, frames=2, size=(64, 48)):
        imgs = []
        for i in range(frames):
            shade = 40 + i * 60
            imgs.append(Image.new("RGB", size, (shade, 120, 200)))
        buf = io.BytesIO()
        imgs[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=imgs[1:],
            loop=0,
            duration=120,
        )
        return buf.getvalue()

    def _png_bytes(self, size=(64, 48)):
        buf = io.BytesIO()
        Image.new("RGB", size, (10, 120, 200)).save(buf, format="PNG")
        return buf.getvalue()

    def _decode(self, content_file):
        return Image.open(io.BytesIO(content_file.read()))

    def test_animated_gif_with_animation_yields_animated_webp(self):
        upload = ContentFile(self._gif_bytes(frames=3), name="a.gif")
        result = process_avatar(upload, allow_animation=True)
        decoded = self._decode(result)
        self.assertEqual(decoded.format, "WEBP")
        self.assertTrue(getattr(decoded, "is_animated", False))
        self.assertGreater(decoded.n_frames, 1)
        self.assertEqual(
            decoded.size, (settings.AVATAR_SIZE_PX, settings.AVATAR_SIZE_PX)
        )

    def test_animated_gif_without_animation_yields_single_frame(self):
        upload = ContentFile(self._gif_bytes(frames=3), name="a.gif")
        result = process_avatar(upload, allow_animation=False)
        decoded = self._decode(result)
        self.assertEqual(decoded.format, "WEBP")
        self.assertFalse(getattr(decoded, "is_animated", False))
        self.assertEqual(getattr(decoded, "n_frames", 1), 1)
        self.assertEqual(
            decoded.size, (settings.AVATAR_SIZE_PX, settings.AVATAR_SIZE_PX)
        )

    def test_default_call_is_single_frame(self):
        # Existing callers pass no allow_animation -> default False preserved.
        upload = ContentFile(self._gif_bytes(frames=3), name="a.gif")
        result = process_avatar(upload)
        decoded = self._decode(result)
        self.assertEqual(getattr(decoded, "n_frames", 1), 1)

    def test_static_input_unaffected_by_allow_animation(self):
        upload = ContentFile(self._png_bytes(), name="s.png")
        result = process_avatar(upload, allow_animation=True)
        decoded = self._decode(result)
        self.assertEqual(decoded.format, "WEBP")
        self.assertEqual(getattr(decoded, "n_frames", 1), 1)
        self.assertEqual(
            decoded.size, (settings.AVATAR_SIZE_PX, settings.AVATAR_SIZE_PX)
        )

    def test_animated_webp_not_upscaled(self):
        # A tiny source must still target AVATAR_SIZE_PX exactly (no upscale beyond).
        upload = ContentFile(self._gif_bytes(frames=2, size=(16, 16)), name="t.gif")
        result = process_avatar(upload, allow_animation=True)
        decoded = self._decode(result)
        self.assertEqual(
            decoded.size, (settings.AVATAR_SIZE_PX, settings.AVATAR_SIZE_PX)
        )

    def test_non_image_raises(self):
        upload = ContentFile(b"definitely not an image", name="x.txt")
        with self.assertRaises(ValueError):
            process_avatar(upload, allow_animation=True)
