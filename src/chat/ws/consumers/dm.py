import json
import time
from collections import deque

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from chat.models import DirectMessage, DMRead, Friendship
from chat.services.realtime import FRIENDS_GROUP_NAME

User = get_user_model()


def dm_group_name(user_a_id: int, user_b_id: int) -> str:
    low, high = DirectMessage.sort_pair(user_a_id, user_b_id)
    return f"dm_{low}_{high}"


class DMConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or user.is_anonymous:
            await self.close(code=4401)
            return

        self.peer_username = self.scope["url_route"]["kwargs"]["peer_username"]
        self.user_id = user.id
        self.username = user.username

        peer = await self._get_peer()
        if peer is None or not peer.is_active:
            await self.close(code=4404)
            return
        if peer.id == user.id:
            await self.close(code=4400)
            return

        if not await self._are_friends(peer.id):
            await self.close(code=4403)
            return

        self.peer_id = peer.id
        self.group_name = dm_group_name(self.user_id, self.peer_id)
        self._msg_times = deque()

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add(FRIENDS_GROUP_NAME, self.channel_name)
        await self.accept()
        # User just opened the conversation — mark read and notify peer.
        read_at = await self._mark_read()
        await self.channel_layer.group_send(self.group_name, {
            "type": "dm_read", "user_id": self.user_id, "last_read_at": read_at.isoformat(),
        })

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.channel_layer.group_discard(FRIENDS_GROUP_NAME, self.channel_name)

    async def friends_changed(self, event):
        # Friend list / user state changed somewhere. Re-validate that we still
        # have a valid conversation; if not, kick the socket so the UI shows a notice.
        if not hasattr(self, "peer_id"):
            return
        if not await self._peer_still_valid():
            await self.close(code=4410)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = payload.get("type", "message")
        if msg_type == "message":
            await self._handle_send(payload)
        elif msg_type == "message.delete":
            await self._handle_delete(payload)
        elif msg_type == "message.edit":
            await self._handle_edit(payload)

    def _is_rate_limited(self):
        now = time.monotonic()
        while self._msg_times and now - self._msg_times[0] > 10:
            self._msg_times.popleft()
        if len(self._msg_times) >= 15:
            return True
        self._msg_times.append(now)
        return False

    async def _handle_send(self, payload):
        if self._is_rate_limited():
            return
        text = str(payload.get("message", "")).strip()
        if not text:
            return
        if len(text) > 2000:
            text = text[:2000]

        if not await self._are_friends(self.peer_id):
            await self.close(code=4403)
            return

        msg = await self._save_message(text)
        await self.channel_layer.group_send(self.group_name, {
            "type": "dm_message",
            "id": msg.id,
            "from_user_id": msg.from_user_id,
            "from_username": self.username,
            "message": msg.message,
            "created_at": msg.created_at.isoformat(),
            "expires_at": msg.expires_at.isoformat(),
        })
        # Refresh unread badge for the recipient (and re-render lists in general).
        await self.channel_layer.group_send(FRIENDS_GROUP_NAME, {"type": "friends_changed"})

    async def _handle_delete(self, payload):
        msg_id = payload.get("message_id")
        if not isinstance(msg_id, int):
            return
        deleted = await self._soft_delete(msg_id)
        if deleted:
            await self.channel_layer.group_send(self.group_name, {
                "type": "dm_deleted", "id": msg_id,
            })

    async def _handle_edit(self, payload):
        msg_id = payload.get("message_id")
        new_text = str(payload.get("message", "")).strip()
        if not isinstance(msg_id, int) or not new_text:
            return
        if len(new_text) > 2000:
            new_text = new_text[:2000]
        edited_at = await self._edit(msg_id, new_text)
        if edited_at:
            await self.channel_layer.group_send(self.group_name, {
                "type": "dm_edited",
                "id": msg_id,
                "message": new_text,
                "edited_at": edited_at.isoformat(),
            })

    # ── Group event handlers ──

    async def dm_message(self, event):
        # If this consumer's user is the recipient and they're actively viewing,
        # mark the conversation as read immediately, refresh badges, and notify peer.
        if event["from_user_id"] != self.user_id:
            read_at = await self._mark_read()
            await self.channel_layer.group_send(
                FRIENDS_GROUP_NAME, {"type": "friends_changed"}
            )
            await self.channel_layer.group_send(self.group_name, {
                "type": "dm_read", "user_id": self.user_id, "last_read_at": read_at.isoformat(),
            })
        await self.send(text_data=json.dumps({
            "type": "dm_message",
            "id": event["id"],
            "from_user_id": event["from_user_id"],
            "from_username": event["from_username"],
            "message": event["message"],
            "created_at": event["created_at"],
            "expires_at": event["expires_at"],
        }))

    async def dm_deleted(self, event):
        await self.send(text_data=json.dumps({"type": "dm_deleted", "id": event["id"]}))

    async def dm_edited(self, event):
        await self.send(text_data=json.dumps({
            "type": "dm_edited",
            "id": event["id"],
            "message": event["message"],
            "edited_at": event["edited_at"],
        }))

    async def dm_read(self, event):
        # Only forward when the OTHER user did the reading (don't echo to self).
        if event["user_id"] == self.user_id:
            return
        await self.send(text_data=json.dumps({
            "type": "dm_read",
            "last_read_at": event["last_read_at"],
        }))

    # ── DB helpers ──

    @database_sync_to_async
    def _get_peer(self):
        return User.objects.filter(username=self.peer_username).first()

    @database_sync_to_async
    def _are_friends(self, peer_id):
        return Friendship.exists_between(self.user_id, peer_id)

    @database_sync_to_async
    def _peer_still_valid(self):
        peer = User.objects.filter(id=self.peer_id, is_active=True).only("id").first()
        if peer is None:
            return False
        return Friendship.exists_between(self.user_id, self.peer_id)

    @database_sync_to_async
    def _save_message(self, text):
        expires_at = timezone.now() + timezone.timedelta(
            seconds=settings.DM_MESSAGE_EXPIRY_SECONDS
        )
        return DirectMessage.objects.create(
            from_user_id=self.user_id,
            to_user_id=self.peer_id,
            message=text,
            expires_at=expires_at,
        )

    @database_sync_to_async
    def _soft_delete(self, msg_id):
        return DirectMessage.objects.filter(
            id=msg_id, from_user_id=self.user_id, is_deleted=False
        ).update(is_deleted=True) > 0

    @database_sync_to_async
    def _mark_read(self):
        now = timezone.now()
        DMRead.objects.update_or_create(
            user_id=self.user_id,
            peer_id=self.peer_id,
            defaults={"last_read_at": now},
        )
        return now

    @database_sync_to_async
    def _edit(self, msg_id, new_text):
        msg = DirectMessage.objects.filter(
            id=msg_id, from_user_id=self.user_id, is_deleted=False
        ).first()
        if msg is None:
            return None
        msg.message = new_text
        msg.edited_at = timezone.now()
        msg.save(update_fields=["message", "edited_at"])
        return msg.edited_at
