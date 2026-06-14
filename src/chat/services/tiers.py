"""Tier (perk) gating helpers.

Levels are graduated: bronze < silver < gold < platinum. A superuser always
counts as platinum for every gate, so a bronze-labelled superuser still gets
every perk without any DB change.

These helpers are deliberately defensive: they are called from many places
(views, consumers, templates) and may receive AnonymousUser, a user with no
``.profile``, or ``None``. Such inputs degrade to "bronze".
"""

from django.conf import settings

# Single source of truth for the custom-icon set lives in room_display.
from chat.services.room_display import _ICONS

ICON_CHOICES = _ICONS

_DEFAULT_LEVEL = "bronze"


def effective_level(user) -> str:
    """Return the tier level that should govern perks for ``user``.

    Superuser -> "platinum" (even if their profile says bronze).
    Otherwise the profile level, defaulting to "bronze" for anonymous users,
    users with no profile, or a profile with no level set.
    """
    if getattr(user, "is_superuser", False):
        return "platinum"
    level = getattr(getattr(user, "profile", None), "level", None)
    return level or _DEFAULT_LEVEL


def active_image_cap(user) -> int:
    """Return the per-user active-image cap for ``user``'s effective tier."""
    level = effective_level(user)
    return settings.CHAT_IMAGE_MAX_PER_USER_BY_TIER.get(
        level, settings.CHAT_IMAGE_MAX_PER_USER
    )


def can_customize_room(user) -> bool:
    """Whether ``user`` may set a custom room color/icon (platinum-only)."""
    return effective_level(user) == "platinum"


def can_animate_avatar(user) -> bool:
    """Whether ``user`` may upload an animated avatar (platinum-only)."""
    return effective_level(user) == "platinum"
