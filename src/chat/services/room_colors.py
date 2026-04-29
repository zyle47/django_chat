import hashlib

ROOM_USER_COLORS = [
    "#e07878",  # muted red
    "#d4936a",  # muted orange
    "#c8b45a",  # muted yellow
    "#78c07a",  # muted green
    "#5abca8",  # muted teal
    "#60aac8",  # muted sky blue
    "#7890d4",  # muted blue
    "#9870c8",  # muted purple
    "#c06ab0",  # muted magenta
    "#d07090",  # muted rose
]


def room_color_for_username(room_name, username):
    normalized_key = f"{room_name.strip().lower()}::{username.strip().lower()}".encode("utf-8")
    digest = hashlib.sha256(normalized_key).digest()
    return ROOM_USER_COLORS[digest[0] % len(ROOM_USER_COLORS)]
