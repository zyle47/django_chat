import json
import time
from collections import deque

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.utils import timezone

from chat.models import ChatImage, ChatMessage, ChatRoom, UserRoomRead
from chat.services import friends as friend_svc
from chat.services import presence
from chat.services.realtime import FRIENDS_GROUP_NAME, LOBBY_GROUP_NAME
from chat.services.room_access import has_room_access
from chat.services.room_colors import room_color_for_username

FRIEND_COMMANDS = {"/add", "/accept", "/reject"}


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"
        self.username = user.username.strip()[:40] or "Anonymous"
        self.user_id = user.id

        session = self.scope.get("session")
        if not user.is_superuser:
            if session is None or not has_room_access(session, self.room_name):
                await self.close(code=4403)
                return

        if not await self._room_is_available():
            await self.close(code=4404)
            return

        self._msg_times = deque()   # sliding window for rate limiting
        self._friend_cmd_times = deque()

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add(FRIENDS_GROUP_NAME, self.channel_name)
        await self.accept()
        presence.join(self.room_name, self.user_id, self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.channel_layer.group_discard(FRIENDS_GROUP_NAME, self.channel_name)
        if hasattr(self, "user_id") and hasattr(self, "room_name"):
            presence.leave(self.room_name, self.user_id, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = payload.get("type", "message")

        if msg_type == "message.delete":
            await self._handle_delete(payload)
        elif msg_type == "message.edit":
            await self._handle_edit(payload)
        else:
            await self._handle_chat(payload)

    def _is_rate_limited(self):
        now = time.monotonic()
        while self._msg_times and now - self._msg_times[0] > 10:
            self._msg_times.popleft()
        if len(self._msg_times) >= 15:   # max 15 events per 10 seconds
            return True
        self._msg_times.append(now)
        return False

    def _is_friend_cmd_rate_limited(self):
        now = time.monotonic()
        while self._friend_cmd_times and now - self._friend_cmd_times[0] > 60:
            self._friend_cmd_times.popleft()
        if len(self._friend_cmd_times) >= 8:   # max 8 friend commands per minute
            return True
        self._friend_cmd_times.append(now)
        return False

    async def _handle_chat(self, payload):
        message = str(payload.get("message", "")).strip()
        if not message:
            return

        first = message.split(maxsplit=1)[0] if message else ""
        if first in FRIEND_COMMANDS:
            await self._handle_friend_command(message)
            return

        if self._is_rate_limited():
            return
        if len(message) > 1000:
            message = message[:1000]

        try:
            msg_id, created_at, expires_at = await self._save_message(message=message)
        except ChatRoom.DoesNotExist:
            await self.close(code=4404)
            return

        color = room_color_for_username(self.room_name, self.username)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message_id": msg_id,
                "username": self.username,
                "message": message,
                "timestamp": created_at.isoformat(),
                "color": color,
                "expires_at": expires_at.isoformat(),
            },
        )
        await self.channel_layer.group_send(
            LOBBY_GROUP_NAME,
            {
                "type": "lobby_room_activity",
                "room_name": self.room_name,
                "from_user_id": self.user_id,
            },
        )

    async def _handle_delete(self, payload):
        if self._is_rate_limited():
            return
        msg_id = payload.get("message_id")
        if not isinstance(msg_id, int):
            return
        deleted = await self._soft_delete_message(msg_id)
        if deleted:
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "message_deleted", "message_id": msg_id},
            )
            await self.channel_layer.group_send(
                LOBBY_GROUP_NAME,
                {"type": "lobby_room_recompute", "room_name": self.room_name},
            )

    async def _handle_edit(self, payload):
        if self._is_rate_limited():
            return
        msg_id = payload.get("message_id")
        new_text = str(payload.get("message", "")).strip()
        if not isinstance(msg_id, int) or not new_text:
            return
        if len(new_text) > 1000:
            new_text = new_text[:1000]
        edited_at = await self._edit_message(msg_id, new_text)
        if edited_at:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_edited",
                    "message_id": msg_id,
                    "message": new_text,
                    "edited_at": edited_at.isoformat(),
                },
            )

    # ── Friend commands ──

    async def _handle_friend_command(self, message):
        if self._is_friend_cmd_rate_limited():
            await self._whisper_self("// rate limit — wait a moment")
            return

        parts = message.split(maxsplit=1)
        cmd = parts[0]
        target = parts[1].strip() if len(parts) > 1 else ""
        if not target:
            await self._whisper_self(f"// usage: {cmd} <username>")
            return
        if len(target) > 40 or " " in target:
            await self._whisper_self("// invalid username")
            return

        if cmd == "/add":
            await self._cmd_add(target)
        elif cmd == "/accept":
            await self._cmd_accept(target)
        elif cmd == "/reject":
            await self._cmd_reject(target)

    async def _cmd_add(self, target_username):
        room_obj = await self._get_room()
        if room_obj is None:
            return
        result = await database_sync_to_async(friend_svc.send_request)(
            self.user_id, target_username, room_obj
        )
        if not result["ok"]:
            await self._whisper_self(self._friend_error_text(result, target_username))
            return

        if result["code"] == "auto_accepted":
            who = result["to_username"]
            await self._whisper_self(f"// you are now friends with {who}")
            await self._whisper_user(
                result["to_user_id"],
                f"// you are now friends with {self.username}",
                kind="friend_accepted",
            )
            return

        target_id = result["to_user_id"]
        target_name = result["to_username"]
        if not presence.is_user_in_room(self.room_name, target_id):
            await database_sync_to_async(friend_svc.lookup_user)(target_name)
            await self._whisper_self(f"// {target_name} is not in this room")
            await database_sync_to_async(self._delete_pending_request)(target_id)
            return

        await self._whisper_self(f"// friend request sent to {target_name}")
        await self._whisper_in_room(
            target_id,
            f"// {self.username} wants to add you as a friend. "
            f"Type /accept {self.username} or /reject {self.username}",
            kind="friend_request",
            from_username=self.username,
        )

    async def _cmd_accept(self, sender_username):
        result = await database_sync_to_async(friend_svc.accept_request)(
            self.user_id, sender_username
        )
        if not result["ok"]:
            await self._whisper_self(self._friend_error_text(result, sender_username))
            return
        await self._whisper_self(f"// you are now friends with {result['from_username']}")
        await self._whisper_user(
            result["from_user_id"],
            f"// {self.username} accepted your friend request",
            kind="friend_accepted",
        )

    async def _cmd_reject(self, sender_username):
        result = await database_sync_to_async(friend_svc.reject_request)(
            self.user_id, sender_username
        )
        if not result["ok"]:
            await self._whisper_self(self._friend_error_text(result, sender_username))
            return
        await self._whisper_self(f"// rejected friend request from {result['from_username']}")

    @staticmethod
    def _friend_error_text(result, name):
        code = result.get("code")
        if code == "self":
            return "// you can't friend yourself"
        if code == "no_such_user":
            return f"// no user named {name}"
        if code == "already_friends":
            return f"// already friends with {result.get('to_username') or result.get('from_username') or name}"
        if code == "already_pending":
            return f"// request already pending to {result.get('to_username') or name}"
        if code == "no_pending":
            return f"// no pending request from {result.get('from_username') or name}"
        return "// command failed"

    @database_sync_to_async
    def _get_room(self):
        return ChatRoom.objects.filter(name=self.room_name, is_deleted=False).first()

    @database_sync_to_async
    def _delete_pending_request(self, target_user_id):
        from chat.models import FriendRequest
        FriendRequest.objects.filter(
            from_user_id=self.user_id, to_user_id=target_user_id
        ).delete()

    # ── Whisper helpers ──

    async def _whisper_self(self, text, kind="info"):
        await self.send(text_data=json.dumps({
            "type": "whisper",
            "text": text,
            "kind": kind,
        }))

    async def _whisper_in_room(self, target_user_id, text, kind="info", **extra):
        for ch in presence.channels_in_room_for_user(self.room_name, target_user_id):
            await self.channel_layer.send(ch, {
                "type": "whisper",
                "text": text,
                "kind": kind,
                **extra,
            })

    async def _whisper_user(self, target_user_id, text, kind="info", **extra):
        for ch in presence.channels_for_user(target_user_id):
            await self.channel_layer.send(ch, {
                "type": "whisper",
                "text": text,
                "kind": kind,
                **extra,
            })

    async def whisper(self, event):
        payload = {"type": "whisper", "text": event["text"], "kind": event.get("kind", "info")}
        if "from_username" in event:
            payload["from_username"] = event["from_username"]
        await self.send(text_data=json.dumps(payload))

    async def friends_changed(self, event):
        await self.send(text_data=json.dumps({"type": "friends_changed"}))

    # ── Group event handlers (broadcast to this socket) ──

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message_id": event["message_id"],
            "username": event["username"],
            "message": event["message"],
            "timestamp": event["timestamp"],
            "color": event["color"],
            "expires_at": event["expires_at"],
        }))
        await self._mark_room_read()

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_deleted",
            "message_id": event["message_id"],
        }))

    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_edited",
            "message_id": event["message_id"],
            "message": event["message"],
            "edited_at": event["edited_at"],
        }))

    async def chat_image(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat_image",
            "image_id": event["image_id"],
            "image_url": event["image_url"],
            "username": event["username"],
            "color": event["color"],
            "expires_at": event["expires_at"],
        }))

    async def image_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "image_deleted",
            "image_id": event["image_id"],
        }))

    # ── DB helpers ──

    @database_sync_to_async
    def _save_message(self, message):
        room_obj = ChatRoom.objects.filter(name=self.room_name, is_deleted=False).first()
        if room_obj is None:
            raise ChatRoom.DoesNotExist
        lifetime = room_obj.message_lifetime or settings.CHAT_MESSAGE_EXPIRY_SECONDS
        expires_at = timezone.now() + timezone.timedelta(seconds=lifetime)
        msg = ChatMessage.objects.create(
            room=room_obj,
            user_id=self.user_id,
            username=self.username,
            message=message,
            expires_at=expires_at,
        )
        return msg.id, msg.created_at, msg.expires_at

    @database_sync_to_async
    def _soft_delete_message(self, msg_id):
        updated = ChatMessage.objects.filter(
            id=msg_id, username=self.username, is_deleted=False
        ).update(is_deleted=True)
        return updated > 0

    @database_sync_to_async
    def _edit_message(self, msg_id, new_text):
        msg = ChatMessage.objects.filter(
            id=msg_id, username=self.username, is_deleted=False
        ).first()
        if msg is None:
            return None
        msg.message = new_text
        msg.edited_at = timezone.now()
        msg.save(update_fields=["message", "edited_at"])
        return msg.edited_at

    @database_sync_to_async
    def _room_is_available(self):
        return ChatRoom.objects.filter(name=self.room_name, is_deleted=False).exists()

    @database_sync_to_async
    def _mark_room_read(self):
        room_obj = ChatRoom.objects.filter(name=self.room_name, is_deleted=False).first()
        if room_obj:
            UserRoomRead.objects.update_or_create(
                user_id=self.user_id,
                room=room_obj,
                defaults={"last_read_at": timezone.now()},
            )
