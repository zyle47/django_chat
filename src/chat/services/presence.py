"""
In-memory presence registry for ChatConsumer connections.

Tracks (room, user, channel) tuples so the friend-command system can answer
"is user X in this room?" and "what channel(s) is user X reachable on?"
without round-tripping through the channel layer.

Single-process only — works with InMemoryChannelLayer. When scaling to a
multi-process setup (Redis channel layer), replace with channel-layer-native
presence (heartbeated group, Redis sorted set with TTL, etc).
"""

from typing import Set

# room_name -> {user_id: set[channel_name]}
_room_members: dict[str, dict[int, set[str]]] = {}
# user_id -> set[channel_name]  (across all rooms)
_user_channels: dict[int, set[str]] = {}


def join(room: str, user_id: int, channel: str) -> None:
    _room_members.setdefault(room, {}).setdefault(user_id, set()).add(channel)
    _user_channels.setdefault(user_id, set()).add(channel)


def leave(room: str, user_id: int, channel: str) -> None:
    members = _room_members.get(room)
    if members:
        chans = members.get(user_id)
        if chans:
            chans.discard(channel)
            if not chans:
                members.pop(user_id, None)
        if not members:
            _room_members.pop(room, None)
    user_chans = _user_channels.get(user_id)
    if user_chans:
        user_chans.discard(channel)
        if not user_chans:
            _user_channels.pop(user_id, None)


def is_user_in_room(room: str, user_id: int) -> bool:
    return bool(_room_members.get(room, {}).get(user_id))


def channels_in_room_for_user(room: str, user_id: int) -> Set[str]:
    return set(_room_members.get(room, {}).get(user_id, ()))


def channels_for_user(user_id: int) -> Set[str]:
    return set(_user_channels.get(user_id, ()))
