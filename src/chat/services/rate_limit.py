from django.core.cache import cache


def is_rate_limited(key: str, limit: int, window: int) -> bool:
    """Increment hit counter for key. Return True if limit exceeded within window seconds."""
    count = cache.get(key, 0)
    if count >= limit:
        return True
    if count == 0:
        cache.set(key, 1, window)
    else:
        cache.incr(key)
    return False
