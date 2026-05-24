import hashlib

from django.test import TestCase

from chat.services.room_display import _ICONS, room_display


class TestRoomDisplayService(TestCase):
    def test_hash_is_stable(self):
        self.assertEqual(
            room_display("general")["hash"], room_display("general")["hash"]
        )

    def test_different_names_produce_different_hashes(self):
        self.assertNotEqual(
            room_display("general")["hash"], room_display("support")["hash"]
        )

    def test_hash_matches_raw_sha256(self):
        name = "testroom"
        expected = hashlib.sha256(name.encode()).hexdigest()
        self.assertEqual(room_display(name)["hash"], expected)

    def test_hash_is_64_hex_chars(self):
        h = room_display("lobby")["hash"]
        self.assertEqual(len(h), 64)
        int(h, 16)  # raises ValueError if not valid hex

    def test_display_is_first_16_chars_of_hash(self):
        d = room_display("lobby")
        self.assertEqual(d["display"], d["hash"][:16])

    def test_icon_is_from_known_set(self):
        self.assertIn(room_display("lobby")["icon"], _ICONS)

    def test_color_is_hsl_string(self):
        color = room_display("lobby")["color"]
        self.assertTrue(color.startswith("hsl("))
        self.assertIn("%", color)
