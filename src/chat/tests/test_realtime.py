from unittest.mock import Mock, patch

from django.test import TestCase

from chat.services.realtime import LOBBY_GROUP_NAME, publish_room_created
from chat.services.room_display import room_display as _room_display


class TestRealtime(TestCase):
    def test_publish_room_created_broadcasts_to_lobby_group(self):
        fake_group_send = Mock()
        fake_layer = Mock(group_send=fake_group_send)
        d = _room_display("general")

        with patch("chat.services.realtime.get_channel_layer", return_value=fake_layer):
            with patch("chat.services.realtime.async_to_sync", side_effect=lambda fn: fn):
                publish_room_created("general")

        fake_group_send.assert_called_once_with(
            LOBBY_GROUP_NAME,
            {
                "type": "lobby_room_created",
                "room_hash": d["hash"],
                "room_display": d["display"],
                "room_icon": d["icon"],
                "room_color": d["color"],
            },
        )
