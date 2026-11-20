"""Rate limiting kanal publik APM (BL-10 / RSK-APM-04).

Implementasi berbasis tabel (``ThrottleCounter``) agar bekerja sama di SQLite
(dev/test) dan PostgreSQL (produksi) tanpa dependensi tambahan.
"""
from functools import wraps

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from pasien.models import ThrottleCounter


def cek(scope, key, *, limit, window_detik):
    """True bila permintaan masih di bawah batas."""
    sekarang = timezone.now()
    with transaction.atomic():
        counter, _ = ThrottleCounter.objects.select_for_update().get_or_create(
            scope=scope, key=key, defaults={'window_start': sekarang, 'count': 0},
        )
        if (sekarang - counter.window_start).total_seconds() >= window_detik:
            counter.window_start = sekarang
            counter.count = 0
        counter.count += 1
        counter.save(update_fields=['window_start', 'count', 'updated_at'])
        jumlah = counter.count
    return jumlah <= limit


def kunci_ip(request):
    ip = request.META.get('REMOTE_ADDR', '') or 'unknown'
    return ip[:120]


def kunci_ip_identitas(request):
    identitas = (
        request.POST.get('identitas')
        or request.POST.get('q')
        or request.POST.get('kode')
        or ''
    ).strip()
    return f"{request.META.get('REMOTE_ADDR', 'unknown')}|{identitas}"[:120]


def throttle(scope, limit, window_detik, key_func=kunci_ip):
    """Decorator: 429 + ``Retry-After`` saat batas terlampaui."""

    def dekorator(view):
        @wraps(view)
        def pembungkus(request, *args, **kwargs):
            if not cek(scope, key_func(request), limit=limit, window_detik=window_detik):
                response = JsonResponse({
                    'success': False,
                    'message': 'Terlalu banyak percobaan. Silakan coba lagi beberapa saat lagi.',
                }, status=429)
                response['Retry-After'] = str(window_detik)
                return response
            return view(request, *args, **kwargs)

        return pembungkus

    return dekorator


__all__ = ['cek', 'kunci_ip', 'kunci_ip_identitas', 'throttle']