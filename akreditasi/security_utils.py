"""
Rate limiter in-memory sederhana berbasis IP + User ID.
Tanpa dependency tambahan (menggunakan dict biasa + time).
"""
import time
import functools
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# In-memory store: {key: [timestamp, timestamp, ...]}
_rate_store: dict[str, list[float]] = {}
_MAX_STORE_SIZE = 5000  # Batas entri untuk mencegah memory leak


def _cleanup_old(window: int):
    """Buang entri lebih tua dari window terakhir."""
    cutoff = time.time() - window
    keys_to_delete = []
    for key, timestamps in _rate_store.items():
        _rate_store[key] = [t for t in timestamps if t > cutoff]
        if not _rate_store[key]:
            keys_to_delete.append(key)
    for key in keys_to_delete:
        del _rate_store[key]


def rate_limit(max_calls: int = 10, window: int = 60, scope: str = 'default'):
    """
    Decorator rate limiter per user/IP.

    Args:
        max_calls: Jumlah request maksimal dalam window.
        window: Durasi window dalam detik.
        scope: Namespace untuk membedakan antar endpoint.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Kunci unik: user_id jika login, IP jika tidak
            if request.user.is_authenticated:
                client_key = f"rl:{scope}:u:{request.user.id}"
            else:
                ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                ip = ip or request.META.get('REMOTE_ADDR', 'unknown')
                client_key = f"rl:{scope}:ip:{ip}"

            now = time.time()
            cutoff = now - window

            # Bersihkan entri lama secara periodik
            if len(_rate_store) > _MAX_STORE_SIZE:
                _cleanup_old(window)

            timestamps = _rate_store.get(client_key, [])
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= max_calls:
                logger.warning(f"Rate limit exceeded: {client_key} ({len(timestamps)}/{max_calls})")
                return JsonResponse({
                    'success': False,
                    'error': f'Terlalu banyak permintaan. Coba lagi setelah {window} detik.'
                }, status=429)

            timestamps.append(now)
            _rate_store[client_key] = timestamps

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
