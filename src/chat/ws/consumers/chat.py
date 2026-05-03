import json
import time
from collections import deque

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.utils import timezone

from chat.models import ChatImage, ChatMessage, ChatRoom, UserRoomRead
from chat.services.room_access import has_room_access
from chat.services.room_colors import room_color_for_username


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        public_id = self.scope["url_route"]["kwargs"]["public_id"]
        self.username = user.username.strip()[:40] or "Anonymous"
        self.user_id = user.id

        room_obj = await self._get_room(public_id)
        if room_obj is None:
            await self.close(code=4404)
            return

        self.room_name = room_obj.name
        self.room_group_name = f"chat_{public_id}"

        session = self.scope.get("session")
        if not user.is_superuser:
            if session is None or not has_room_access(session, self.room_name):
                await self.close(code=4403)
                return

        self._msg_times = deque()   # sliding window for rate limiting

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

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

    async def _handle_chat(self, payload):
        if self._is_rate_limited():
            return
        message = str(payload.get("message", "")).strip()
        if not message:
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
        expires_at = timezone.now() + timezone.timedelta(seconds=settings.CHAT_MESSAGE_EXPIRY_SECONDS)
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
    def _get_room(self, public_id):
        return ChatRoom.objects.filter(public_id=public_id, is_deleted=False).first()

    @database_sync_to_async
    def _mark_room_read(self):
        room_obj = ChatRoom.objects.filter(name=self.room_name, is_deleted=False).first()
        if room_obj:
            UserRoomRead.objects.update_or_create(
                user_id=self.user_id,
                room=room_obj,
                defaults={"last_read_at": timezone.now()},
            )
