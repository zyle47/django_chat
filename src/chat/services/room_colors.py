import hashlib

ROOM_USER_COLORS = [
    "#ffe3e3",
    "#ffdfe8",
    "#ffe9cc",
    "#fff4c2",
    "#e5ffd9",
    "#d9fff4",
    "#dff2ff",
    "#e6e4ff",
    "#f1e4ff",
    "#ffdff7",
]


def room_color_for_username(room_name, username):
    normalized_key = f"{room_name.strip().lower()}::{username.strip().lower()}".encode("utf-8")
    digest = hashlib.sha256(normalized_key).digest()
    return ROOM_USER_COLORS[digest[0] % len(ROOM_USER_COLORS)]
