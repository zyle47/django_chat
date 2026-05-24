"""
Integration tests for DMConsumer.

TransactionTestCase is required because database_sync_to_async runs in a
thread pool that can only see committed data — TestCase's rolled-back
savepoint is invisible to those threads.

Single-connection tests are used wherever possible so there is no need to
drain an initial dm_read event (the connect handler sends one but the
consumer suppresses its own read receipts).
"""

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.test import TransactionTestCase
from django.utils import timezone

from chat.models import DirectMessage, Friendship
from chat.ws.consumers.dm import DMConsumer


def _communicator(peer_username, user):
    c = WebsocketCommunicator(DMConsumer.as_asgi(), f"/ws/dm/{peer_username}/")
    c.scope["type"] = "websocket"
    c.scope["user"] = user
    c.scope["url_route"] = {"kwargs": {"peer_username": peer_username}}
    return c


class TestDMConsumerConnect(TransactionTestCase):
    async def _users(self):
        alice = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        bob = await database_sync_to_async(User.objects.create_user)(
            username="bob", password="Pass123", is_active=True
        )
        return alice, bob

    async def test_anonymous_user_is_rejected(self):
        c = _communicator("bob", AnonymousUser())
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_nonexistent_peer_is_rejected(self):
        alice, _ = await self._users()
        c = _communicator("nobody", alice)
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_self_connection_is_rejected(self):
        alice, _ = await self._users()
        c = _communicator("alice", alice)
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_non_friends_are_rejected(self):
        alice, bob = await self._users()
        c = _communicator("bob", alice)
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_friends_can_connect(self):
        alice, bob = await self._users()
        await database_sync_to_async(Friendship.create_between)(alice.id, bob.id)
        c = _communicator("bob", alice)
        connected, _ = await c.connect()
        self.assertTrue(connected)
        await c.disconnect()


class TestDMConsumerMessaging(TransactionTestCase):
    async def _connected(self):
        alice = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        bob = await database_sync_to_async(User.objects.create_user)(
            username="bob", password="Pass123", is_active=True
        )
        await database_sync_to_async(Friendship.create_between)(alice.id, bob.id)
        c = _communicator("bob", alice)
        await c.connect()
        return c, alice, bob

    async def test_sent_message_is_received(self):
        c, alice, bob = await self._connected()
        await c.send_json_to({"type": "message", "message": "hello bob"})
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "dm_message")
        self.assertEqual(msg["message"], "hello bob")
        self.assertEqual(msg["from_user_id"], alice.id)
        await c.disconnect()

    async def test_sent_message_is_saved_to_db(self):
        c, alice, bob = await self._connected()
        await c.send_json_to({"type": "message", "message": "persist me"})
        await c.receive_json_from()
        count = await database_sync_to_async(
            DirectMessage.objects.filter(
                from_user=alice, to_user=bob, message="persist me"
            ).count
        )()
        self.assertEqual(count, 1)
        await c.disconnect()

    async def test_empty_message_is_ignored(self):
        c, alice, bob = await self._connected()
        await c.send_json_to({"type": "message", "message": "   "})
        await c.send_json_to({"type": "message", "message": "probe"})
        msg = await c.receive_json_from()
        self.assertEqual(msg["message"], "probe")
        await c.disconnect()

    async def test_message_over_2000_chars_is_truncated(self):
        c, alice, bob = await self._connected()
        await c.send_json_to({"type": "message", "message": "x" * 3000})
        msg = await c.receive_json_from()
        self.assertEqual(len(msg["message"]), 2000)
        await c.disconnect()

    async def test_delete_own_message_is_broadcast(self):
        c, alice, bob = await self._connected()
        await c.send_json_to({"type": "message", "message": "delete me"})
        sent = await c.receive_json_from()
        msg_id = sent["id"]

        await c.send_json_to({"type": "message.delete", "message_id": msg_id})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "dm_deleted")
        self.assertEqual(response["id"], msg_id)

        msg = await database_sync_to_async(DirectMessage.objects.get)(id=msg_id)
        self.assertTrue(msg.is_deleted)
        await c.disconnect()

    async def test_delete_other_users_message_is_silently_rejected(self):
        c, alice, bob = await self._connected()
        expires_at = timezone.now() + timezone.timedelta(hours=1)
        bob_msg = await database_sync_to_async(DirectMessage.objects.create)(
            from_user=bob, to_user=alice, message="bob's msg", expires_at=expires_at
        )
        await c.send_json_to({"type": "message.delete", "message_id": bob_msg.id})
        await c.send_json_to({"type": "message", "message": "probe"})
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "dm_message")

        refreshed = await database_sync_to_async(DirectMessage.objects.get)(
            id=bob_msg.id
        )
        self.assertFalse(refreshed.is_deleted)
        await c.disconnect()

    async def test_edit_own_message_is_broadcast(self):
        c, alice, bob = await self._connected()
        await c.send_json_to({"type": "message", "message": "original"})
        sent = await c.receive_json_from()
        msg_id = sent["id"]

        await c.send_json_to(
            {"type": "message.edit", "message_id": msg_id, "message": "edited"}
        )
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "dm_edited")
        self.assertEqual(response["message"], "edited")
        await c.disconnect()

    async def test_edit_other_users_message_is_silently_rejected(self):
        c, alice, bob = await self._connected()
        expires_at = timezone.now() + timezone.timedelta(hours=1)
        bob_msg = await database_sync_to_async(DirectMessage.objects.create)(
            from_user=bob, to_user=alice, message="bob's msg", expires_at=expires_at
        )
        await c.send_json_to(
            {"type": "message.edit", "message_id": bob_msg.id, "message": "hacked"}
        )
        await c.send_json_to({"type": "message", "message": "probe"})
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "dm_message")

        refreshed = await database_sync_to_async(DirectMessage.objects.get)(
            id=bob_msg.id
        )
        self.assertEqual(refreshed.message, "bob's msg")
        await c.disconnect()


class TestDMConsumerReadReceipt(TransactionTestCase):
    async def test_dm_read_from_peer_is_forwarded(self):
        alice = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        bob = await database_sync_to_async(User.objects.create_user)(
            username="bob", password="Pass123", is_active=True
        )
        await database_sync_to_async(Friendship.create_between)(alice.id, bob.id)

        c_alice = _communicator("bob", alice)
        c_bob = _communicator("alice", bob)
        await c_alice.connect()
        # bob connects → sends dm_read with user_id=bob.id to the DM group
        # alice is in the group and receives it (bob.id != alice.id) → forwarded to alice's socket
        await c_bob.connect()

        receipt = await c_alice.receive_json_from()
        self.assertEqual(receipt["type"], "dm_read")

        await c_alice.disconnect()
        await c_bob.disconnect()
