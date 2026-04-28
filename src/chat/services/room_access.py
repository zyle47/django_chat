ROOM_ACCESS_SESSION_KEY = "room_access_permissions"


def has_room_access(session, room_name):
    return room_name in session.get(ROOM_ACCESS_SESSION_KEY, [])


def grant_room_access(session, room_name):
    allowed_rooms = set(session.get(ROOM_ACCESS_SESSION_KEY, []))
    allowed_rooms.add(room_name)
    session[ROOM_ACCESS_SESSION_KEY] = sorted(allowed_rooms)
    session.modified = True
