import os

from django.conf import settings


def room_creation_limit(user):
    """Return the max number of rooms a user may create, or None for unlimited."""
    if getattr(user, "is_superuser", False):
        return None
    level = getattr(getattr(user, "profile", None), "level", "bronze")
    return settings.ROOM_CREATION_LIMITS.get(
        level, settings.ROOM_CREATION_LIMITS["bronze"]
    )


def purge_room(room):
    """Delete a room's image files from disk, then remove the room row."""
    for img in room.images.all():
        try:
            if img.image and os.path.isfile(img.image.path):
                os.remove(img.image.path)
        except Exception:
            pass
    room.delete()
