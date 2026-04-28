from django.test import TestCase

from chat.services.room_colors import ROOM_USER_COLORS, room_color_for_username


class TestColorMapping(TestCase):
    def test_room_color_for_username_is_stable(self):
        color_one = room_color_for_username("general", "nemanja")
        color_two = room_color_for_username("general", "nemanja")
        self.assertEqual(color_one, color_two)

    def test_room_color_for_username_uses_known_palette(self):
        color = room_color_for_username("support", "alice")
        self.assertIn(color, ROOM_USER_COLORS)
