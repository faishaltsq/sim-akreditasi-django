"""Helpers shared by the akreditasi test modules."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from akreditasi.models import UnitKerja
from akreditasi.security_utils import _rate_store_fallback
from accounts.models import UserProfile
from pasien.models import KunjunganPasien, Pasien

DEFAULT_TEST_PASSWORD = 'pass123-rahasia'


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


def make_user(username, role, *, unit=None, profesi='', password=DEFAULT_TEST_PASSWORD,
              **profile_kwargs):
    """Create a User plus its UserProfile with the given role/unit/profesi.

    ``profile_kwargs`` are applied to the profile (e.g. ``is_active_member``);
    ``custom_permissions`` is a plain JSONField so it can be passed directly.
    """
    user = get_user_model().objects.create_user(
        username=username, email=f'{username}@rs.test', password=password,
    )
    UserProfile.objects.create(
        user=user, role=role, unit_kerja=unit, profesi=profesi, **profile_kwargs,
    )
    return user


def login(client, user, password=DEFAULT_TEST_PASSWORD):
    """Log the user in through the session backend, asserting success."""
    assert client.login(username=user.username, password=password), (
        f'login gagal untuk {user.username}'
    )


def make_unit(code, name, *, level=3, parent=None, **kwargs):
    """Create a UnitKerja row. ``code`` drives get_allowed_patient_modules()."""
    return UnitKerja.objects.create(
        code=code, name=name, level=level, parent=parent, **kwargs,
    )


def make_pasien(no_rm, nama, *, nik='', **kwargs):
    """Create a patient with the minimum required fields filled in."""
    defaults = {
        'tanggal_lahir': timezone.localdate() - timedelta(days=365 * 40),
        'jenis_kelamin': 'L',
        'alamat': 'Jl. Rahasia No. 1',
        'no_hp': '081234567890',
        'no_bpjs': '0001234567890',
    }
    defaults.update(kwargs)
    return Pasien.objects.create(
        no_rm=no_rm, nik=nik, nama_lengkap=nama, **defaults,
    )


def make_kunjungan(pasien, no_kunjungan, *, jenis='RANAP', **kwargs):
    """Create a visit attached to ``pasien``."""
    defaults = {'tanggal_masuk': timezone.now(), 'status': 'DAFTAR'}
    defaults.update(kwargs)
    return KunjunganPasien.objects.create(
        pasien=pasien, no_kunjungan=no_kunjungan, jenis_kunjungan=jenis, **defaults,
    )
