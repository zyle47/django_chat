from django.test import TestCase

from chat.services import presence


class TestPresenceService(TestCase):
    def setUp(self):
        presence._room_members.clear()
        presence._user_channels.clear()

    def test_user_not_present_before_join(self):
        self.assertFalse(presence.is_user_in_room("general", 1))

    def test_join_makes_user_present_in_room(self):
        presence.join("general", user_id=1, channel="ws_a")
        self.assertTrue(presence.is_user_in_room("general", 1))

    def test_leave_removes_user_from_room(self):
        presence.join("general", 1, "ws_a")
        presence.leave("general", 1, "ws_a")
        self.assertFalse(presence.is_user_in_room("general", 1))

    def test_leave_nonexistent_does_not_raise(self):
        presence.leave("general", 99, "ws_ghost")

    def test_user_with_two_channels_stays_present_after_one_leaves(self):
        presence.join("general", 1, "ws_a")
        presence.join("general", 1, "ws_b")
        presence.leave("general", 1, "ws_a")
        self.assertTrue(presence.is_user_in_room("general", 1))

    def test_channels_in_room_for_user_returns_all_channels(self):
        presence.join("general", 1, "ws_a")
        presence.join("general", 1, "ws_b")
        self.assertEqual(presence.channels_in_room_for_user("general", 1), {"ws_a", "ws_b"})

    def test_channels_for_user_spans_multiple_rooms(self):
        presence.join("general", 1, "ws_a")
        presence.join("support", 1, "ws_b")
        self.assertEqual(presence.channels_for_user(1), {"ws_a", "ws_b"})

    def test_room_entry_removed_when_last_user_leaves(self):
        presence.join("general", 1, "ws_a")
        presence.leave("general", 1, "ws_a")
        self.assertNotIn("general", presence._room_members)

    def test_different_users_are_isolated(self):
        presence.join("general", 1, "ws_1")
        presence.join("general", 2, "ws_2")
        presence.leave("general", 1, "ws_1")
        self.assertFalse(presence.is_user_in_room("general", 1))
        self.assertTrue(presence.is_user_in_room("general", 2))

    def test_channels_in_room_for_absent_user_is_empty(self):
        self.assertEqual(presence.channels_in_room_for_user("general", 99), set())

    def test_channels_for_absent_user_is_empty(self):
        self.assertEqual(presence.channels_for_user(99), set())
