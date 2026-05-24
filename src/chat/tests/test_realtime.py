from unittest.mock import Mock, patch

from django.test import TestCase

from chat.services.realtime import (
    FRIENDS_GROUP_NAME,
    LOBBY_GROUP_NAME,
    publish_friends_changed,
    publish_room_activity,
    publish_room_created,
    publish_room_recompute,
)
from chat.services.room_display import room_display as _room_display


def _fake_layer():
    gs = Mock()
    return Mock(group_send=gs), gs


class TestRealtime(TestCase):
    def test_publish_room_created_broadcasts_to_lobby_group(self):
        layer, gs = _fake_layer()
        d = _room_display("general")

        with patch("chat.services.realtime.get_channel_layer", return_value=layer):
            with patch(
                "chat.services.realtime.async_to_sync", side_effect=lambda fn: fn
            ):
                publish_room_created("general")

        gs.assert_called_once_with(
            LOBBY_GROUP_NAME,
            {
                "type": "lobby_room_created",
                "room_hash": d["hash"],
                "room_display": d["display"],
                "room_icon": d["icon"],
                "room_color": d["color"],
            },
        )

    def test_publish_room_created_with_none_channel_layer_does_nothing(self):
        with patch("chat.services.realtime.get_channel_layer", return_value=None):
            publish_room_created("general")  # must not raise

    def test_publish_friends_changed_broadcasts_to_friends_group(self):
        layer, gs = _fake_layer()

        with patch("chat.services.realtime.get_channel_layer", return_value=layer):
            with patch(
                "chat.services.realtime.async_to_sync", side_effect=lambda fn: fn
            ):
                publish_friends_changed()

        gs.assert_called_once_with(FRIENDS_GROUP_NAME, {"type": "friends_changed"})

    def test_publish_room_activity_broadcasts_to_lobby_group(self):
        layer, gs = _fake_layer()
        d = _room_display("general")

        with patch("chat.services.realtime.get_channel_layer", return_value=layer):
            with patch(
                "chat.services.realtime.async_to_sync", side_effect=lambda fn: fn
            ):
                publish_room_activity("general", from_user_id=42)

        gs.assert_called_once_with(
            LOBBY_GROUP_NAME,
            {"type": "lobby_room_activity", "room_hash": d["hash"], "from_user_id": 42},
        )

    def test_publish_room_recompute_broadcasts_to_lobby_group(self):
        layer, gs = _fake_layer()
        d = _room_display("general")

        with patch("chat.services.realtime.get_channel_layer", return_value=layer):
            with patch(
                "chat.services.realtime.async_to_sync", side_effect=lambda fn: fn
            ):
                publish_room_recompute("general")

        gs.assert_called_once_with(
            LOBBY_GROUP_NAME,
            {"type": "lobby_room_recompute", "room_hash": d["hash"]},
        )
