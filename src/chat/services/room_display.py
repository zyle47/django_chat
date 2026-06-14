import hashlib

_ICONS = [
    "💀",
    "🐉",
    "🔥",
    "💣",
    "👻",
    "🤖",
    "☢️",
    "☣️",
    "🕷️",
    "🧙",
    "☄️",
    "💩",
    "🐸",
    "🦅",
    "🔒",
    "💾",
    "🛰️",
    "🐛",
    "🚽",
    "🦛",
    "🎲",
    "🦦",
    "🐱",
    "🐠",
    "🌶️",
    "🦀",
    "🐙",
    "🦠",
    "🧨",
    "🪲",
]


def room_display(room_name, custom_color="", custom_icon=""):
    """Return display metadata (hash/display/icon/color) for a room.

    The icon and color are derived from a stable hash of ``room_name`` by
    default. A truthy ``custom_color`` or ``custom_icon`` overrides the
    corresponding name-hash default (each independently). Empty values fall
    back to exactly the name-hash behaviour.
    """
    h = hashlib.sha256(room_name.encode()).hexdigest()
    hue = int(h[:4], 16) % 360
    return {
        "hash": h,
        "display": h[:16],
        "icon": custom_icon or _ICONS[int(h[:8], 16) % len(_ICONS)],
        "color": custom_color or f"hsl({hue}, 100%, 60%)",
    }
