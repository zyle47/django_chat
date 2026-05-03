from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

LOBBY_GROUP_NAME = "lobby"
FRIENDS_GROUP_NAME = "friends_global"


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


def publish_friends_changed():
    """Tell every connected lobby/chat socket that friend lists may have changed."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        FRIENDS_GROUP_NAME,
        {"type": "friends_changed"},
    )


def publish_room_activity(room_name, from_user_id):
    """Notify lobby clients that a room got a new message (excluding the sender)."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        LOBBY_GROUP_NAME,
        {
            "type": "lobby_room_activity",
            "room_name": room_name,
            "from_user_id": from_user_id,
        },
    )
