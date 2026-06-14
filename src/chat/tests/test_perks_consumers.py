"""
Integration tests for the sender-tier field carried in WS payloads.

The chat/DM consumers stamp the SENDER's effective perk tier onto every
outgoing message so receivers can render the author "glow". The tier is
computed ONCE per connection (an ORM read wrapped in database_sync_to_async)
and cached on the consumer — never re-queried per message and never run as a
blocking ORM call in async context.

TransactionTestCase is required (not TestCase): the consumer's
database_sync_to_async calls run in a thread pool that can only see
*committed* data, which TestCase's rolled-back savepoint hides.

Privacy note: a superuser must appear as "platinum" to clients — is_superuser
is never exposed. effective_level handles that mapping for us.
"""

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from chat.models import ChatRoom, Friendship, UserProfile
from chat.services import presence
from chat.services.room_access import ROOM_ACCESS_SESSION_KEY
from chat.ws.consumers.chat import ChatConsumer
from chat.ws.consumers.dm import DMConsumer

# ── Helpers ──────────────────────────────────────────────────────────────────


def _chat_communicator(public_id, user, room_name):
    session = {ROOM_ACCESS_SESSION_KEY: [room_name]} if room_name else {}
    c = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{public_id}/")
    c.scope["type"] = "websocket"
    c.scope["user"] = user
    c.scope["url_route"] = {"kwargs": {"public_id": public_id}}
    c.scope["session"] = session
    return c


def _dm_communicator(peer_username, user):
    c = WebsocketCommunicator(DMConsumer.as_asgi(), f"/ws/dm/{peer_username}/")
    c.scope["type"] = "websocket"
    c.scope["user"] = user
    c.scope["url_route"] = {"kwargs": {"peer_username": peer_username}}
    return c


def _make_user(username, *, level=None, superuser=False):
    """Create a user and set its (auto-created) profile level. Runs in a thread."""
    if superuser:
        user = User.objects.create_superuser(
            username=username, password="Pass123", email=f"{username}@test.com"
        )
    else:
        user = User.objects.create_user(
            username=username, password="Pass123", is_active=True
        )
    if level is not None:
        # The post_save signal already created a bronze profile; bump it, then
        # drop the cached reverse relation so effective_level reloads it fresh.
        UserProfile.objects.filter(user=user).update(level=level)
        if "profile" in user._state.fields_cache:
            del user._state.fields_cache["profile"]
    return user


# ── Chat consumer ─────────────────────────────────────────────────────────────


class TestChatMessageTier(TransactionTestCase):
    def setUp(self):
        presence._room_members.clear()
        presence._user_channels.clear()

    async def _connected(self, username, *, level=None, superuser=False):
        room = await database_sync_to_async(ChatRoom.objects.create)(name="tierroom")
        user = await database_sync_to_async(_make_user)(
            username, level=level, superuser=superuser
        )
        c = _chat_communicator(room.public_id, user, room.name)
        await c.connect()
        return c, room, user

    async def test_gold_user_message_carries_gold_tier(self):
        c, room, user = await self._connected("goldie", level=UserProfile.GOLD)
        await c.send_json_to({"type": "message", "message": "shiny"})
        resp = await c.receive_json_from()
        self.assertEqual(resp["type"], "chat_message")
        self.assertEqual(resp["tier"], "gold")
        await c.disconnect()

    async def test_platinum_user_message_carries_platinum_tier(self):
        c, room, user = await self._connected("platty", level=UserProfile.PLATINUM)
        await c.send_json_to({"type": "message", "message": "elite"})
        resp = await c.receive_json_from()
        self.assertEqual(resp["tier"], "platinum")
        await c.disconnect()

    async def test_bronze_user_message_carries_bronze_tier(self):
        # No explicit level → default bronze profile from the signal.
        c, room, user = await self._connected("brownie")
        await c.send_json_to({"type": "message", "message": "humble"})
        resp = await c.receive_json_from()
        self.assertEqual(resp["tier"], "bronze")
        await c.disconnect()

    async def test_superuser_message_carries_platinum_tier_not_superuser(self):
        # Superuser keeps a bronze-labelled profile but must read as platinum,
        # and is_superuser must never leak into the payload.
        c, room, user = await self._connected("root", superuser=True)
        await c.send_json_to({"type": "message", "message": "godmode"})
        resp = await c.receive_json_from()
        self.assertEqual(resp["tier"], "platinum")
        self.assertNotIn("is_superuser", resp)
        await c.disconnect()

    async def test_tier_is_stable_across_multiple_messages(self):
        # Tier is cached at connect; sending several messages keeps the same value
        # (and proves we don't accidentally degrade to bronze on the 2nd send).
        c, room, user = await self._connected("goldie2", level=UserProfile.GOLD)
        await c.send_json_to({"type": "message", "message": "one"})
        first = await c.receive_json_from()
        await c.send_json_to({"type": "message", "message": "two"})
        second = await c.receive_json_from()
        self.assertEqual(first["tier"], "gold")
        self.assertEqual(second["tier"], "gold")
        await c.disconnect()


# ── DM consumer ───────────────────────────────────────────────────────────────


class TestDMMessageTier(TransactionTestCase):
    async def _connected(self, *, sender_level=None, sender_superuser=False):
        alice = await database_sync_to_async(_make_user)(
            "alice", level=sender_level, superuser=sender_superuser
        )
        bob = await database_sync_to_async(_make_user)("bob")
        await database_sync_to_async(Friendship.create_between)(alice.id, bob.id)
        c = _dm_communicator("bob", alice)
        await c.connect()
        return c, alice, bob

    async def test_gold_sender_dm_carries_gold_tier(self):
        c, alice, bob = await self._connected(sender_level=UserProfile.GOLD)
        await c.send_json_to({"type": "message", "message": "hi bob"})
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "dm_message")
        self.assertEqual(msg["tier"], "gold")
        await c.disconnect()

    async def test_bronze_sender_dm_carries_bronze_tier(self):
        c, alice, bob = await self._connected()
        await c.send_json_to({"type": "message", "message": "hi bob"})
        msg = await c.receive_json_from()
        self.assertEqual(msg["tier"], "bronze")
        await c.disconnect()

    async def test_superuser_sender_dm_carries_platinum_tier(self):
        c, alice, bob = await self._connected(sender_superuser=True)
        await c.send_json_to({"type": "message", "message": "hi bob"})
        msg = await c.receive_json_from()
        self.assertEqual(msg["tier"], "platinum")
        self.assertNotIn("is_superuser", msg)
        await c.disconnect()
