import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from chat.models import ChatMessage, ChatRoom
from chat.services.room_access import has_room_access
from chat.services.room_colors import room_color_for_username


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"
        self.username = user.username.strip()[:40] or "Anonymous"

        session = self.scope.get("session")
        if session is None or not has_room_access(session, self.room_name):
            await self.close(code=4403)
            return

        if not await self._room_is_available():
            await self.close(code=4404)
            return

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

        message = str(payload.get("message", "")).strip()
        if not message:
            return

        if len(message) > 1000:
            message = message[:1000]

        try:
            created_at = await self._save_message(username=self.username, message=message)
        except ChatRoom.DoesNotExist:
            await self.close(code=4404)
            return
        color = room_color_for_username(self.room_name, self.username)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "username": self.username,
                "message": message,
                "timestamp": created_at.isoformat(),
                "color": color,
            },
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "username": event["username"],
                    "message": event["message"],
                    "timestamp": event["timestamp"],
                    "color": event["color"],
                }
            )
        )

    @database_sync_to_async
    def _save_message(self, username, message):
        room_obj = ChatRoom.objects.filter(name=self.room_name, is_deleted=False).first()
        if room_obj is None:
            raise ChatRoom.DoesNotExist

        chat_message = ChatMessage.objects.create(
            room=room_obj,
            username=username,
            message=message,
        )
        return chat_message.created_at

    @database_sync_to_async
    def _room_is_available(self):
        return ChatRoom.objects.filter(name=self.room_name, is_deleted=False).exists()
