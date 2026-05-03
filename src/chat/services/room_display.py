import hashlib

_ICONS = [
    '💀','🐉','🔥','💣','👻','🤖','☢️','☣️','🕷️','🧙',
    '☄️','💩','🐸','🦅','🔒','💾','🛰️','🐛','🚽','🦛',
    '🎲','🦦','🐱','🐠','🌶️','🦀','🐙','🦠','🧨','🪲',
]


def room_display(room_name):
    h = hashlib.sha256(room_name.encode()).hexdigest()
    hue = int(h[:4], 16) % 360
    return {
        'hash': h,
        'display': h[:16],
        'icon': _ICONS[int(h[:8], 16) % len(_ICONS)],
        'color': f'hsl({hue}, 100%, 60%)',
    }
