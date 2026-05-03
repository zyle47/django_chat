import json

from channels.generic.websocket import AsyncWebsocketConsumer

from chat.services.realtime import LOBBY_GROUP_NAME


class LobbyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(LOBBY_GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(LOBBY_GROUP_NAME, self.channel_name)

    async def lobby_room_created(self, event):
        await self.send(text_data=json.dumps({
            "type": "room_created",
            "room_hash": event["room_hash"],
            "room_display": event["room_display"],
            "room_icon": event["room_icon"],
            "room_color": event["room_color"],
        }))
