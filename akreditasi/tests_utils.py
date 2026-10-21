"""Helpers shared by the akreditasi test modules."""
from django.core.cache import cache

from akreditasi.security_utils import _rate_store_fallback


def reset_rate_limit(scope: str = 'ai'):
    """Flush rate-limiter state so one test cannot starve another.

    The limiter counts per user id, and TestCase reuses primary keys across
    tests in the same process, so the shared cache keeps accumulating calls
    from unrelated tests until a later one gets 429 instead of the response
    it is asserting.
    """
    cache.clear()
    prefix = f'rl:{scope}:'
    for key in [k for k in _rate_store_fallback if k.startswith(prefix)]:
        _rate_store_fallback.pop(key, None)
