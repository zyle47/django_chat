from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

LOBBY_GROUP_NAME = "lobby"


def publish_room_created(room_name):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        LOBBY_GROUP_NAME,
        {
            "type": "lobby_room_created",
            "room_name": room_name,
        },
    )
