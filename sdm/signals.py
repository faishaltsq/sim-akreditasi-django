"""Invalidate Human Capital dashboard caches when scoped data changes."""
from django.contrib.auth.signals import user_logged_in
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from sdm.models import (
    DokumenPegawai,
    HcGrant,
    HasilFormasi,
    Pegawai,
    PenempatanPegawai,
    VersiDokumen,
)

CACHE_VERSION_KEY = 'hc-dashboard-version'


def bump_dashboard_version(**kwargs):
    """Rotate the cache namespace so every scoped key becomes stale at once."""
    try:
        cache.incr(CACHE_VERSION_KEY)
    except ValueError:
        cache.set(CACHE_VERSION_KEY, 1, None)


def _connect(model):
    post_save.connect(bump_dashboard_version, sender=model, dispatch_uid=f'hc-cache-save-{model.__name__}')
    post_delete.connect(bump_dashboard_version, sender=model, dispatch_uid=f'hc-cache-del-{model.__name__}')


for _model in (HcGrant, Pegawai, PenempatanPegawai, DokumenPegawai, VersiDokumen, HasilFormasi):
    _connect(_model)


@receiver(user_logged_in)
def log_staff_login(sender, request, user, **kwargs):
    """Sesi login dicatat sebagai aktivitas SYSTEM pada akun pegawai."""
    from akreditasi.security_utils import extract_client_ip

    from sdm.models import PeristiwaSDM
    employee = getattr(user, 'pegawai_hc', None)
    if employee is None:
        return
    PeristiwaSDM.objects.create(
        actor=user,
        jenis_peristiwa='login',
        kategori='LOGIN',
        judul='Login ke ARIMA',
        modul='Akun',
        status='SUCCESS',
        ip_address=extract_client_ip(request) if request is not None else '',
        user_agent=(
            request.META.get('HTTP_USER_AGENT', '')[:2000]
            if request is not None else ''
        ),
        target_tipe='employee',
        target_id=str(employee.pk),
    )
