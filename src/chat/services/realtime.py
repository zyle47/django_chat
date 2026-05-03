from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from chat.services.room_display import room_display

LOBBY_GROUP_NAME = "lobby"


def publish_room_created(room_name):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    d = room_display(room_name)
    async_to_sync(channel_layer.group_send)(
        LOBBY_GROUP_NAME,
        {
            "type": "lobby_room_created",
            "room_hash": d['hash'],
            "room_display": d['display'],
            "room_icon": d['icon'],
            "room_color": d['color'],
        },
    )
