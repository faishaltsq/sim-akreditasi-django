"""Uji jalur tulis pada DB ASLI, di dalam transaksi yang selalu di-rollback.

Berbeda dari fase lain yang memakai salinan DB: di sini kita ingin membuktikan
perilaku persistensi, jadi harus DB asli. Setiap blok dibungkus rolled_back()
dan jumlah baris diverifikasi tidak berubah setelahnya.

Pemakaian:
    python -m qa.write_tests
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

import logging
logging.disable(logging.CRITICAL)

from django.contrib.auth import get_user_model
from django.test import Client

from qa.rollback_guard import rolled_back, table_counts

U = get_user_model()

TABLES = [
    'akreditasi_qualityrecord',
    'akreditasi_auditlog',
    'accounts_nakescredential',
    'sdm_versidokumen',
    'sdm_peristiw asdm'.replace(' ', ''),
]


def one(role):
    return U.objects.filter(profile__role=role, is_active=True,
                            email__endswith='@arima.local').first()


def probe(label, client, method, url, data=None, expect=None):
    """Kirim request, kembalikan (label, status, ok)."""
    try:
        if method == 'POST':
            r = client.post(url, data or {})
        else:
            r = client.get(url)
        status = r.status_code
    except Exception as e:
        status = f'EXC:{type(e).__name__}:{str(e)[:60]}'
    ok = True
    if expect is not None:
        ok = status in expect if isinstance(expect, (set, list, tuple)) else status == expect
    return {'label': label, 'method': method, 'url': url,
            'status': status, 'expected': list(expect) if isinstance(expect, (set, list, tuple)) else expect,
            'ok': ok}


def main():
    results = []
    before = table_counts(TABLES)

    cases = [
        # (label, role, method, url, data, expected)
        ('kontrol_permissions_update_non_admin', 'KEPALA_UNIT', 'POST',
         '/accounts/kontrol/permissions/update/', {}, {302, 403}),
        ('kontrol_permissions_update_admin', 'SUPER_ADMIN', 'POST',
         '/accounts/kontrol/permissions/update/', {}, {200, 302, 400}),
        ('toggle_freeze_non_admin', 'STAF_NAKES', 'POST',
         '/accounts/kontrol/system/toggle-freeze/', {}, {302, 403}),
        ('user_create_non_admin', 'ASESOR', 'POST',
         '/accounts/users/baru/', {}, {302, 403}),
        ('unit_delete_non_admin', 'KOORDINATOR_POKJA', 'POST',
         '/unit/999999/hapus/', {}, {302, 403, 404}),
        ('ep_delete_non_admin', 'STAF_NAKES', 'POST',
         '/ep/999999/hapus/', {}, {302, 403, 404}),
        ('risiko_hapus_non_admin', 'ASESOR', 'POST',
         '/risiko/999999/hapus/', {}, {302, 403, 404}),
        ('kunjungan_batal_non_admin', 'ASESOR', 'POST',
         '/pasien/kunjungan/999999/batal/', {}, {302, 403, 404}),
        ('quick_score_non_admin', 'ASESOR', 'POST',
         '/ep/record/999999/quick-score/', {'score': '5'}, {302, 403, 404}),
        # F-1: jalur yang memakai ValidationError. Harus TIDAK 500.
        ('verify_kredensial_tanpa_grant', 'KEPALA_UNIT', 'POST',
         '/rekap-kps/verifikasi/999999/', {'status': 'VERIFIED'}, {302, 403, 404}),
        ('verify_kredensial_admin', 'ADMIN_RS', 'POST',
         '/rekap-kps/verifikasi/999999/', {'status': 'VERIFIED'}, {302, 403, 404}),
    ]

    for label, role, method, url, data, expect in cases:
        user = one(role)
        if user is None:
            results.append({'label': label, 'skipped': f'tidak ada akun {role}'})
            continue
        with rolled_back():
            c = Client()
            c.force_login(user)
            results.append(probe(label, c, method, url, data, expect))

    after = table_counts(TABLES)

    print('=== HASIL UJI TULIS (semua dalam transaksi rollback) ===')
    for r in results:
        if 'skipped' in r:
            print(f"  SKIP  {r['label']:<38} {r['skipped']}")
            continue
        mark = 'OK  ' if r['ok'] else 'GAGAL'
        print(f"  {mark} {r['label']:<38} {r['method']} {r['url']:<44} "
              f"-> {r['status']} (harap {r['expected']})")

    print()
    print('=== VERIFIKASI ROLLBACK ===')
    changed = []
    for t in TABLES:
        b, a = before[t], after[t]
        status = 'sama' if a == b else f'BERUBAH {b} -> {a}'
        if a != b:
            changed.append(t)
        print(f'  {t:<32} {status}')

    print()
    if changed:
        print(f'ROLLBACK GAGAL pada: {changed}')
    else:
        print('ROLLBACK OK — tidak ada perubahan permanen.')

    fails = [r for r in results if 'skipped' not in r and not r['ok']]
    print(f'\nKasus gagal: {len(fails)} dari {len([r for r in results if "skipped" not in r])}')
    return 0 if (not changed and not fails) else 1


if __name__ == '__main__':
    sys.exit(main())
