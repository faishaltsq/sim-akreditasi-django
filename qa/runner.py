"""Runner QA: satu shard = satu proses = satu file output.

Alur: salin DB -> arahkan koneksi ke salinan -> force_login -> GET/POST ->
tulis JSON. Tidak pernah menulis ke db.sqlite3 asli.

Pemakaian:
    python -m qa.runner --shard 0 --total 13 --mode smoke --out qa/shards/smoke/shard0.json
    python -m qa.runner --shard 0 --total 13 --mode api    --out qa/shards/api/shard0.json
    python -m qa.runner --shard 0 --total 13 --mode sanity --out qa/shards/sanity/shard0.json
    python -m qa.runner --shard 0 --total 13 --mode regression --repeat 2 --out ...
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Assertion isi untuk fase sanity: URL -> substring yang WAJIB ada di <title>.
# Memakai <title>, bukan teks bebas: penanda seperti 'isiko' juga muncul di
# sidebar setiap halaman, sehingga lolos di halaman yang isinya rusak (false
# pass). <title> unik per halaman dan hanya terender bila view benar-benar
# mengirim konteks yang tepat.
SANITY_ASSERTIONS = {
    '/dashboard/': 'Aplikasi Terpadu Manajemen Risiko',
    '/control/': 'Hospital Integrated Control',
    '/control/risiko/': 'Integrated Risk &amp; Patient Safety Control',
    '/control/emr/': 'Smart EMR &amp; Clinical Quality',
    '/matriks/': 'Matriks PDCA',
    '/risiko/': 'Daftar Risiko Unit',
    '/rekap/': 'Rekapitulasi Akreditasi RS',
    '/indikator-mutu/': 'Capaian Indikator Mutu',
    '/laporan-mutu/': 'Laporan Capaian Indikator Mutu',
    '/logbook/': 'Logbook Harian IGD',
    '/pencarian/': 'Pencarian',
    '/human-capital/': 'Arima Human Capital',
}

FORBIDDEN_IN_BODY = ('Traceback (most recent call last)', 'django.core.exceptions')


def clone_db(src, dst):
    """Salin DB lewat backup API: konsisten walau ada penulis lain."""
    if os.path.exists(dst):
        os.remove(dst)
    s = sqlite3.connect(f'file:{src}?mode=ro', uri=True)
    d = sqlite3.connect(dst)
    with d:
        s.backup(d)
    s.close()
    d.close()


def bootstrap(db_path):
    """Setup Django lalu arahkan koneksi ke salinan DB milik worker ini."""
    sys.path.insert(0, PROJECT)
    os.chdir(PROJECT)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    import django
    from django.conf import settings

    django.setup()

    # setup() sudah mengonfigurasi logging, jadi menimpa settings.LOGGING di
    # sini tidak berpengaruh. Yang berpengaruh adalah mematikan logger yang
    # mencetak traceback untuk setiap 403/400 yang memang diharapkan.
    import logging
    logging.disable(logging.CRITICAL)

    settings.DATABASES['default']['NAME'] = db_path
    settings.SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

    from django.db import connections
    connections.close_all()  # wajib: setup() mungkin sudah membuka DB asli
    return settings


def pick_accounts(idx, total, limit, role=None):
    from django.contrib.auth import get_user_model
    U = get_user_model()
    qs = U.objects.filter(is_active=True, email__endswith='@arima.local')
    if role:
        qs = qs.filter(profile__role=role)
    names = list(qs.order_by('username').values_list('username', flat=True))
    # stride agar tiap shard tersebar merata lintas unit & role
    return names[idx::total][:limit] if limit else names[idx::total]


def urls_for_mode(mode):
    from qa import endpoints
    if mode == 'smoke':
        return endpoints.discover_smoke_urls()
    if mode == 'sanity':
        return list(endpoints.SANITY_URLS)
    if mode == 'api':
        return [u for _, u, _ in endpoints.API_ENDPOINTS]
    if mode == 'regression':
        return endpoints.discover_smoke_urls()
    raise ValueError(f'mode tidak dikenal: {mode}')


def run(args):
    outdir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(outdir, exist_ok=True)

    db_copy = os.path.join(outdir, f'_db_worker{args.shard}.sqlite3')
    clone_db(os.path.join(PROJECT, 'db.sqlite3'), db_copy)
    bootstrap(db_copy)

    from django.contrib.auth import get_user_model
    from django.test import Client
    from qa import endpoints, expectations

    U = get_user_model()
    accounts = pick_accounts(args.shard, args.total, args.limit, args.role)

    rows = []
    findings = []
    t0 = time.time()

    for un in accounts:
        user = U.objects.select_related('profile__unit_kerja').get(username=un)
        profile = getattr(user, 'profile', None)
        role = profile.role if profile else '-'
        unit = profile.unit_kerja.code if profile and profile.unit_kerja else '-'
        try:
            allowed = profile.get_allowed_patient_modules() if profile else set()
        except Exception:
            allowed = set()

        c = Client()
        c.force_login(user)

        if args.mode == 'api':
            # Fase API menguji kontrak JSON: GET untuk endpoint baca, POST
            # dengan body kosong untuk endpoint POST-only. Status 405 pada GET
            # tidak membuktikan apa pun tentang bentuk respons.
            for method, url, want_json in endpoints.API_ENDPOINTS:
                ts = time.time()
                try:
                    if method == 'POST':
                        r = c.post(url, data='{}', content_type='application/json')
                    else:
                        r = c.get(url)
                    status = r.status_code
                    ctype = r.headers.get('Content-Type', '')
                except Exception as e:
                    status = f'EXC:{type(e).__name__}'
                    ctype = ''
                ms = round((time.time() - ts) * 1000, 1)
                rows.append([un, role, unit, f'{method} {url}', status, ms])

                if isinstance(status, str) or status >= 500:
                    findings.append([un, role, unit, f'{method} {url}', status])
                elif want_json and status < 500 and 'application/json' not in ctype:
                    findings.append([un, role, unit, f'{method} {url}',
                                     'NOT_JSON:' + ctype[:40]])
            continue

        urls = urls_for_mode(args.mode)
        for url in urls:
            for _ in range(args.repeat):
                ts = time.time()
                try:
                    r = c.get(url)
                    status = r.status_code
                    body = r.content.decode('utf-8', 'replace') if args.mode == 'sanity' else ''
                except Exception as e:
                    status = f'EXC:{type(e).__name__}'
                    body = ''
                ms = round((time.time() - ts) * 1000, 1)
                rows.append([un, role, unit, url, status, ms])

                if args.mode == 'sanity' and status == 200:
                    needle = SANITY_ASSERTIONS.get(url)
                    if needle and needle.lower() not in body.lower():
                        findings.append([un, role, unit, url, 'CONTENT_MISSING:' + needle])
                    for bad in FORBIDDEN_IN_BODY:
                        if bad in body:
                            findings.append([un, role, unit, url, 'BODY_LEAK:' + bad])

                if expectations.is_finding(role, url, status, allowed, unit):
                    findings.append([un, role, unit, url, status])

    elapsed = time.time() - t0
    n_urls = len(endpoints.API_ENDPOINTS) if args.mode == 'api' else len(urls_for_mode(args.mode))
    summary = {
        'shard': args.shard, 'total_shards': args.total, 'mode': args.mode,
        'accounts': len(accounts), 'urls': n_urls,
        'requests': len(rows), 'sec': round(elapsed, 1),
        'rows': rows, 'findings': findings,
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(summary, f)

    # ringkas ke stdout saja; detail ada di file
    from collections import Counter
    dist = Counter(str(r[4]) for r in rows)
    print(json.dumps({
        'shard': args.shard, 'mode': args.mode, 'accounts': len(accounts),
        'requests': len(rows), 'sec': round(elapsed, 1),
        'by_status': dict(sorted(dist.items())),
        'findings': len(findings),
        'out': args.out,
    }))

    try:
        os.remove(db_copy)
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser(description='Runner QA shard')
    ap.add_argument('--shard', type=int, required=True)
    ap.add_argument('--total', type=int, required=True)
    ap.add_argument('--limit', type=int, default=0, help='0 = semua di shard ini')
    ap.add_argument('--mode', required=True,
                    choices=['smoke', 'api', 'sanity', 'regression'])
    ap.add_argument('--out', required=True)
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--role', default=None)
    run(ap.parse_args())


if __name__ == '__main__':
    main()
