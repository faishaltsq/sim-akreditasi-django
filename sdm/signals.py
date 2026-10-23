"""Invalidate Human Capital dashboard caches when scoped data changes."""
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
