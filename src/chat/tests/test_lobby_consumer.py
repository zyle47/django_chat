from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.test import TransactionTestCase

from chat.services.realtime import FRIENDS_GROUP_NAME, LOBBY_GROUP_NAME
from chat.ws.consumers.lobby import LobbyConsumer


def _communicator(user=None):
    c = WebsocketCommunicator(LobbyConsumer.as_asgi(), "/ws/lobby/")
    c.scope["type"] = "websocket"
    c.scope["user"] = user or AnonymousUser()
    return c


class TestLobbyConsumerConnect(TransactionTestCase):
    async def test_anonymous_user_can_connect(self):
        c = _communicator()
        connected, _ = await c.connect()
        self.assertTrue(connected)
        await c.disconnect()

    async def test_authenticated_user_can_connect(self):
        user = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        c = _communicator(user)
        connected, _ = await c.connect()
        self.assertTrue(connected)
        await c.disconnect()


class TestLobbyConsumerEvents(TransactionTestCase):
    async def _connected(self, username=None):
        user = None
        if username:
            user = await database_sync_to_async(User.objects.create_user)(
                username=username, password="Pass123", is_active=True
            )
        c = _communicator(user)
        await c.connect()
        return c, user

    async def test_room_created_event_is_forwarded(self):
        c, _ = await self._connected()
        await get_channel_layer().group_send(
            LOBBY_GROUP_NAME,
            {
                "type": "lobby_room_created",
                "room_hash": "abc",
                "room_display": "abc",
                "room_icon": "x",
                "room_color": "hsl(0,0%,50%)",
            },
        )
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "room_created")
        self.assertEqual(msg["room_hash"], "abc")
        await c.disconnect()

    async def test_room_activity_from_other_user_is_forwarded(self):
        c, user = await self._connected("alice")
        await get_channel_layer().group_send(
            LOBBY_GROUP_NAME,
            {
                "type": "lobby_room_activity",
                "room_hash": "abc",
                "from_user_id": user.id + 999,
            },
        )
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "room_activity")
        await c.disconnect()

    async def test_room_activity_from_self_is_suppressed(self):
        c, user = await self._connected("alice")
        layer = get_channel_layer()
        await layer.group_send(
            LOBBY_GROUP_NAME,
            {
                "type": "lobby_room_activity",
                "room_hash": "abc",
                "from_user_id": user.id,
            },
        )
        # Probe — if the first event was correctly dropped, only the probe arrives.
        await layer.group_send(
            LOBBY_GROUP_NAME,
            {"type": "lobby_room_recompute", "room_hash": "probe"},
        )
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "room_recompute")
        await c.disconnect()

    async def test_room_recompute_event_is_forwarded(self):
        c, _ = await self._connected()
        await get_channel_layer().group_send(
            LOBBY_GROUP_NAME,
            {"type": "lobby_room_recompute", "room_hash": "abc"},
        )
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "room_recompute")
        await c.disconnect()

    async def test_friends_changed_event_is_forwarded(self):
        c, _ = await self._connected()
        await get_channel_layer().group_send(
            FRIENDS_GROUP_NAME,
            {"type": "friends_changed"},
        )
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "friends_changed")
        await c.disconnect()
