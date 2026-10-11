"""
Rate limiter berbasis Django Cache Framework + In-Memory Fallback.
Mendukung persistence lintas cold-start Vercel via DatabaseCache / Redis,
serta mendukung endpoint JSON (API) dan views HTML biasa (Login).
"""
import time
import functools
import logging
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse

logger = logging.getLogger(__name__)

_RATE_PREFIX = 'rl:'
_rate_store_fallback: dict[str, list[float]] = {}
_MAX_STORE_SIZE = 5000


def _cleanup_fallback(window: int):
    """Buang entri lokal lebih tua dari window terakhir."""
    cutoff = time.time() - window
    keys_to_delete = [k for k, ts in _rate_store_fallback.items() if not any(t > cutoff for t in ts)]
    for k in keys_to_delete:
        _rate_store_fallback.pop(k, None)


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
            # Kunci unik: user_id jika login, IP jika anonim
            if getattr(request, 'user', None) and request.user.is_authenticated:
                client_key = f"{_RATE_PREFIX}{scope}:u:{request.user.id}"
            else:
                xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
                ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', 'unknown')
                client_key = f"{_RATE_PREFIX}{scope}:ip:{ip}"

            now = time.time()
            cutoff = now - window

            # 1. Coba ambil dari Django Cache
            using_cache = True
            try:
                raw_timestamps = cache.get(client_key)
                timestamps = list(raw_timestamps) if isinstance(raw_timestamps, (list, tuple)) else []
            except Exception as e:
                logger.warning("Cache access failed in rate_limit (%s), using memory fallback", e)
                using_cache = False
                timestamps = _rate_store_fallback.get(client_key, [])

            # Filter timestamp di dalam sliding window
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= max_calls:
                logger.warning("Rate limit exceeded: %s (%d/%d calls in %ds)", client_key, len(timestamps), max_calls, window)
                
                # Deteksi tipe respons: JSON vs HTML
                is_json = (
                    request.path.startswith('/ai/') or
                    request.path.startswith('/api/') or
                    request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                    'application/json' in request.headers.get('accept', '') or
                    getattr(request, 'content_type', '') == 'application/json'
                )

                if is_json:
                    return JsonResponse({
                        'success': False,
                        'error': f'Terlalu banyak permintaan. Coba lagi setelah {window} detik.'
                    }, status=429)
                else:
                    msg = (
                        f"<!DOCTYPE html><html><head><title>429 Terlalu Banyak Permintaan</title>"
                        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
                        f"<link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css' rel='stylesheet'>"
                        f"</head><body class='bg-light d-flex align-items-center min-vh-100'>"
                        f"<div class='container text-center' style='max-width: 480px;'>"
                        f"<div class='card shadow-sm p-4 border-0'>"
                        f"<div class='text-danger fs-1 mb-2'>⏳</div>"
                        f"<h4 class='fw-bold'>Akses Dibatasi Sementara</h4>"
                        f"<p class='text-muted small'>Terlalu banyak percobaan dalam waktu singkat. "
                        f"Demi keamanan sistem, harap tunggu <strong>{window} detik</strong> sebelum mencoba kembali.</p>"
                        f"<a href='javascript:location.reload()' class='btn btn-outline-secondary btn-sm mt-2'>Muat Ulang Halaman</a>"
                        f"</div></div></body></html>"
                    )
                    return HttpResponse(msg, status=429)

            # Catat timestamp baru
            timestamps.append(now)

            if using_cache:
                try:
                    cache.set(client_key, timestamps, timeout=max(window * 2, 300))
                except Exception as e:
                    logger.warning("Cache set failed in rate_limit (%s), falling back to memory", e)
                    _rate_store_fallback[client_key] = timestamps
            else:
                if len(_rate_store_fallback) > _MAX_STORE_SIZE:
                    _cleanup_fallback(window)
                _rate_store_fallback[client_key] = timestamps

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
