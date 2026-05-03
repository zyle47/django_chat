import json

from channels.generic.websocket import AsyncWebsocketConsumer

from chat.services.realtime import FRIENDS_GROUP_NAME, LOBBY_GROUP_NAME


class LobbyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        self.user_id = getattr(user, "id", None) if user and not user.is_anonymous else None
        await self.channel_layer.group_add(LOBBY_GROUP_NAME, self.channel_name)
        await self.channel_layer.group_add(FRIENDS_GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(LOBBY_GROUP_NAME, self.channel_name)
        await self.channel_layer.group_discard(FRIENDS_GROUP_NAME, self.channel_name)

    async def lobby_room_created(self, event):
        await self.send(text_data=json.dumps({
            "type": "room_created",
            "room_hash": event["room_hash"],
            "room_display": event["room_display"],
            "room_icon": event["room_icon"],
            "room_color": event["room_color"],
        }))

    async def lobby_room_activity(self, event):
        # Don't blink the user's own activity.
        if self.user_id is not None and event.get("from_user_id") == self.user_id:
            return
        await self.send(text_data=json.dumps({
            "type": "room_activity",
            "room_hash": event["room_hash"],
        }))

    async def lobby_room_recompute(self, event):
        await self.send(text_data=json.dumps({
            "type": "room_recompute",
            "room_hash": event["room_hash"],
        }))

    async def friends_changed(self, event):
        await self.send(text_data=json.dumps({"type": "friends_changed"}))
