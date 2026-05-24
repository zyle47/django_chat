"""
Tests for ChatConsumer.

Unit tests (TestCase) cover pure-logic methods with no I/O.
Integration tests (TransactionTestCase) use WebsocketCommunicator to exercise
the full connect → send → receive cycle against a real in-memory SQLite DB.

TransactionTestCase is required (not TestCase) because the consumer's
database_sync_to_async calls run in a thread pool that can only see
*committed* data — TestCase wraps everything in a rolled-back savepoint that
other threads cannot see.
"""

from collections import deque

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from chat.models import ChatMessage, ChatRoom, FriendRequest
from chat.services import presence
from chat.services.room_access import ROOM_ACCESS_SESSION_KEY
from chat.ws.consumers.chat import ChatConsumer

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_communicator(public_id, user, room_name=None):
    """Build a communicator with user and optional session access pre-set."""
    session = {}
    if room_name:
        session = {ROOM_ACCESS_SESSION_KEY: [room_name]}
    c = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{public_id}/")
    c.scope["type"] = "websocket"
    c.scope["user"] = user
    c.scope["url_route"] = {"kwargs": {"public_id": public_id}}
    c.scope["session"] = session
    return c


# ── Pure unit tests (no WebSocket, no DB) ────────────────────────────────────


class TestChatConsumerRateLimiter(TestCase):
    def _consumer(self):
        c = ChatConsumer()
        c._msg_times = deque()
        return c

    def test_first_15_messages_are_not_rate_limited(self):
        consumer = self._consumer()
        results = [consumer._is_rate_limited() for _ in range(15)]
        self.assertFalse(any(results))

    def test_16th_message_is_rate_limited(self):
        consumer = self._consumer()
        for _ in range(15):
            consumer._is_rate_limited()
        self.assertTrue(consumer._is_rate_limited())

    def test_friend_cmd_rate_limiter_blocks_after_8(self):
        consumer = self._consumer()
        consumer._friend_cmd_times = deque()
        for _ in range(8):
            consumer._is_friend_cmd_rate_limited()
        self.assertTrue(consumer._is_friend_cmd_rate_limited())


class TestFriendErrorText(TestCase):
    def test_self_code(self):
        text = ChatConsumer._friend_error_text({"code": "self"}, "alice")
        self.assertIn("yourself", text)

    def test_no_such_user_code(self):
        text = ChatConsumer._friend_error_text({"code": "no_such_user"}, "alice")
        self.assertIn("alice", text)

    def test_already_friends_code(self):
        text = ChatConsumer._friend_error_text(
            {"code": "already_friends", "to_username": "alice"}, "alice"
        )
        self.assertIn("already friends", text)

    def test_already_pending_code(self):
        text = ChatConsumer._friend_error_text(
            {"code": "already_pending", "to_username": "alice"}, "alice"
        )
        self.assertIn("pending", text)

    def test_no_pending_code(self):
        text = ChatConsumer._friend_error_text(
            {"code": "no_pending", "from_username": "alice"}, "alice"
        )
        self.assertIn("no pending", text)

    def test_unknown_code_returns_generic_message(self):
        text = ChatConsumer._friend_error_text({"code": "unexpected"}, "alice")
        self.assertIn("failed", text)


# ── WS integration tests ─────────────────────────────────────────────────────


class TestChatConsumerConnect(TransactionTestCase):
    def setUp(self):
        presence._room_members.clear()
        presence._user_channels.clear()

    async def test_anonymous_user_is_rejected(self):
        room = await database_sync_to_async(ChatRoom.objects.create)(name="testroom")
        c = _make_communicator(room.public_id, AnonymousUser())
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_nonexistent_room_is_rejected(self):
        user = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        c = _make_communicator("a" * 64, user, room_name="ghost")
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_no_session_access_is_rejected(self):
        room = await database_sync_to_async(ChatRoom.objects.create)(name="locked")
        user = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        # room_name=None → no session entry → access denied
        c = _make_communicator(room.public_id, user)
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_superuser_bypasses_session_check(self):
        room = await database_sync_to_async(ChatRoom.objects.create)(name="locked")
        superuser = await database_sync_to_async(User.objects.create_superuser)(
            username="root", password="Pass123", email="root@test.com"
        )
        c = _make_communicator(room.public_id, superuser)  # no session access set
        connected, _ = await c.connect()
        self.assertTrue(connected)
        await c.disconnect()

    async def test_valid_user_with_session_is_accepted(self):
        room = await database_sync_to_async(ChatRoom.objects.create)(name="testroom")
        user = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        c = _make_communicator(room.public_id, user, room_name=room.name)
        connected, _ = await c.connect()
        self.assertTrue(connected)
        await c.disconnect()

    async def test_connect_registers_user_in_presence(self):
        room = await database_sync_to_async(ChatRoom.objects.create)(name="testroom")
        user = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        c = _make_communicator(room.public_id, user, room_name=room.name)
        await c.connect()
        self.assertTrue(presence.is_user_in_room(room.name, user.id))
        await c.disconnect()

    async def test_disconnect_removes_user_from_presence(self):
        room = await database_sync_to_async(ChatRoom.objects.create)(name="testroom")
        user = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        c = _make_communicator(room.public_id, user, room_name=room.name)
        await c.connect()
        await c.disconnect()
        self.assertFalse(presence.is_user_in_room(room.name, user.id))


class TestChatConsumerMessaging(TransactionTestCase):
    def setUp(self):
        presence._room_members.clear()
        presence._user_channels.clear()

    async def _connected(self, room_name="chatroom", username="alice"):
        room = await database_sync_to_async(ChatRoom.objects.create)(name=room_name)
        user = await database_sync_to_async(User.objects.create_user)(
            username=username, password="Pass123", is_active=True
        )
        c = _make_communicator(room.public_id, user, room_name=room.name)
        await c.connect()
        return c, room, user

    async def test_chat_message_is_broadcast_back(self):
        c, room, user = await self._connected()
        await c.send_json_to({"type": "message", "message": "hello"})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "chat_message")
        self.assertEqual(response["message"], "hello")
        self.assertEqual(response["username"], user.username)
        await c.disconnect()

    async def test_chat_message_is_saved_to_db(self):
        c, room, user = await self._connected()
        await c.send_json_to({"type": "message", "message": "persist me"})
        await c.receive_json_from()
        count = await database_sync_to_async(
            ChatMessage.objects.filter(room=room, message="persist me").count
        )()
        self.assertEqual(count, 1)
        await c.disconnect()

    async def test_empty_message_produces_no_response(self):
        c, room, user = await self._connected()
        # Send an empty message then a valid one — only the valid one should arrive.
        await c.send_json_to({"type": "message", "message": "   "})
        await c.send_json_to({"type": "message", "message": "probe"})
        response = await c.receive_json_from()
        self.assertEqual(response["message"], "probe")
        await c.disconnect()

    async def test_invalid_json_produces_no_response(self):
        c, room, user = await self._connected()
        # Send invalid JSON then a valid message — only the valid one should arrive.
        await c.send_to(text_data="not json at all {{")
        await c.send_json_to({"type": "message", "message": "probe"})
        response = await c.receive_json_from()
        self.assertEqual(response["message"], "probe")
        await c.disconnect()

    async def test_message_over_1000_chars_is_truncated(self):
        c, room, user = await self._connected()
        await c.send_json_to({"type": "message", "message": "x" * 2000})
        response = await c.receive_json_from()
        self.assertEqual(len(response["message"]), 1000)
        await c.disconnect()


class TestChatConsumerEditDelete(TransactionTestCase):
    def setUp(self):
        presence._room_members.clear()
        presence._user_channels.clear()

    async def _setup(self):
        room = await database_sync_to_async(ChatRoom.objects.create)(name="editroom")
        alice = await database_sync_to_async(User.objects.create_user)(
            username="alice", password="Pass123", is_active=True
        )
        bob = await database_sync_to_async(User.objects.create_user)(
            username="bob", password="Pass123", is_active=True
        )
        return room, alice, bob

    async def _bob_message(self, room, bob):
        return await database_sync_to_async(ChatMessage.objects.create)(
            room=room,
            user=bob,
            username="bob",
            message="bobs message",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )

    async def test_delete_own_message_is_broadcast(self):
        room, alice, bob = await self._setup()
        c = _make_communicator(room.public_id, alice, room_name=room.name)
        await c.connect()

        await c.send_json_to({"type": "message", "message": "delete me"})
        chat_event = await c.receive_json_from()
        msg_id = chat_event["message_id"]

        await c.send_json_to({"type": "message.delete", "message_id": msg_id})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "message_deleted")
        self.assertEqual(response["message_id"], msg_id)

        msg = await database_sync_to_async(ChatMessage.objects.get)(id=msg_id)
        self.assertTrue(msg.is_deleted)
        await c.disconnect()

    async def test_delete_other_users_message_is_silently_rejected(self):
        room, alice, bob = await self._setup()
        msg = await self._bob_message(room, bob)

        c = _make_communicator(room.public_id, alice, room_name=room.name)
        await c.connect()
        # Attempt delete, then send a probe to confirm the consumer is still alive
        # and that the delete event was dropped (not the probe).
        await c.send_json_to({"type": "message.delete", "message_id": msg.id})
        await c.send_json_to({"type": "message", "message": "probe"})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "chat_message")

        refreshed = await database_sync_to_async(ChatMessage.objects.get)(id=msg.id)
        self.assertFalse(refreshed.is_deleted)
        await c.disconnect()

    async def test_edit_own_message_is_broadcast(self):
        room, alice, bob = await self._setup()
        c = _make_communicator(room.public_id, alice, room_name=room.name)
        await c.connect()

        await c.send_json_to({"type": "message", "message": "original"})
        chat_event = await c.receive_json_from()
        msg_id = chat_event["message_id"]

        await c.send_json_to(
            {"type": "message.edit", "message_id": msg_id, "message": "edited"}
        )
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "message_edited")
        self.assertEqual(response["message"], "edited")

        msg = await database_sync_to_async(ChatMessage.objects.get)(id=msg_id)
        self.assertEqual(msg.message, "edited")
        await c.disconnect()

    async def test_edit_other_users_message_is_silently_rejected(self):
        room, alice, bob = await self._setup()
        msg = await self._bob_message(room, bob)

        c = _make_communicator(room.public_id, alice, room_name=room.name)
        await c.connect()
        # Attempt edit, then probe — the probe should be the first response.
        await c.send_json_to(
            {"type": "message.edit", "message_id": msg.id, "message": "hacked"}
        )
        await c.send_json_to({"type": "message", "message": "probe"})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "chat_message")

        refreshed = await database_sync_to_async(ChatMessage.objects.get)(id=msg.id)
        self.assertEqual(refreshed.message, "bobs message")
        await c.disconnect()


class TestChatConsumerChannelEvents(TransactionTestCase):
    """Tests for channel-layer events pushed directly to the chat room group."""

    def setUp(self):
        presence._room_members.clear()
        presence._user_channels.clear()

    async def _connected(self, room_name="evtroom", username="alice"):
        room = await database_sync_to_async(ChatRoom.objects.create)(name=room_name)
        user = await database_sync_to_async(User.objects.create_user)(
            username=username, password="Pass123", is_active=True
        )
        c = _make_communicator(room.public_id, user, room_name=room.name)
        await c.connect()
        return c, room, user

    async def test_chat_image_event_is_forwarded(self):
        c, room, user = await self._connected()
        await get_channel_layer().group_send(
            f"chat_{room.public_id}",
            {
                "type": "chat_image",
                "image_id": 1,
                "image_url": "/chat/image/1/",
                "username": "alice",
                "color": "hsl(0,50%,50%)",
                "caption": "a pic",
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
        )
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "chat_image")
        self.assertEqual(msg["image_id"], 1)
        await c.disconnect()

    async def test_image_deleted_event_is_forwarded(self):
        c, room, user = await self._connected()
        await get_channel_layer().group_send(
            f"chat_{room.public_id}",
            {"type": "image_deleted", "image_id": 42},
        )
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "image_deleted")
        self.assertEqual(msg["image_id"], 42)
        await c.disconnect()

    async def test_whisper_event_is_forwarded(self):
        c, room, user = await self._connected()
        await get_channel_layer().group_send(
            f"chat_{room.public_id}",
            {"type": "whisper", "text": "// hello", "kind": "info"},
        )
        msg = await c.receive_json_from()
        self.assertEqual(msg["type"], "whisper")
        self.assertEqual(msg["text"], "// hello")
        await c.disconnect()


class TestChatConsumerFriendCommands(TransactionTestCase):
    def setUp(self):
        presence._room_members.clear()
        presence._user_channels.clear()

    async def _setup(self, room_name, alice_name="alice", bob_name="bob"):
        room = await database_sync_to_async(ChatRoom.objects.create)(name=room_name)
        alice = await database_sync_to_async(User.objects.create_user)(
            username=alice_name, password="Pass123", is_active=True
        )
        bob = await database_sync_to_async(User.objects.create_user)(
            username=bob_name, password="Pass123", is_active=True
        )
        return room, alice, bob

    async def test_accept_no_pending_sends_error_whisper(self):
        room, alice, bob = await self._setup("cmd-room1")
        c = _make_communicator(room.public_id, alice, room_name=room.name)
        await c.connect()
        await c.send_json_to({"type": "message", "message": "/accept bob"})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "whisper")
        self.assertIn("no pending", response["text"])
        await c.disconnect()

    async def test_reject_no_pending_sends_error_whisper(self):
        room, alice, bob = await self._setup("cmd-room2")
        c = _make_communicator(room.public_id, alice, room_name=room.name)
        await c.connect()
        await c.send_json_to({"type": "message", "message": "/reject bob"})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "whisper")
        await c.disconnect()

    async def test_accept_pending_request_sends_success_whisper(self):
        room, alice, bob = await self._setup("cmd-room3")
        await database_sync_to_async(FriendRequest.objects.create)(
            from_user=bob,
            to_user=alice,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )
        c = _make_communicator(room.public_id, alice, room_name=room.name)
        await c.connect()
        await c.send_json_to({"type": "message", "message": "/accept bob"})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "whisper")
        self.assertIn("friends with", response["text"])
        await c.disconnect()

    async def test_reject_pending_request_sends_success_whisper(self):
        room, alice, bob = await self._setup("cmd-room4")
        await database_sync_to_async(FriendRequest.objects.create)(
            from_user=bob,
            to_user=alice,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )
        c = _make_communicator(room.public_id, alice, room_name=room.name)
        await c.connect()
        await c.send_json_to({"type": "message", "message": "/reject bob"})
        response = await c.receive_json_from()
        self.assertEqual(response["type"], "whisper")
        self.assertIn("rejected", response["text"])
        await c.disconnect()
