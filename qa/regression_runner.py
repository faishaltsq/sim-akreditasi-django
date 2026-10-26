"""Regression baca: 2 pass pada sampel akun, deteksi flaky per (akun,url).

Sampel 130 akun (10 per shard) sudah cukup: flaky adalah properti endpoint
(cache, singleton config, feature flag), bukan properti akun individual.
Menguji 1.295 akun dua kali hanya menambah waktu, bukan sinyal.

Pemakaian:
    python -m qa.regression_runner --limit 10 --pass 1
    python -m qa.regression_runner --limit 10 --pass 2
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qa.runner import bootstrap, clone_db, pick_accounts, PROJECT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=10, help='akun per shard')
    ap.add_argument('--pass', dest='pass_no', type=int, required=True)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    outdir = 'qa/shards/regression'
    os.makedirs(outdir, exist_ok=True)
    import time as _t
    db_copy = os.path.join(outdir, f'_reg_p{args.pass_no}_{int(_t.time())}.sqlite3')
    clone_db(os.path.join(PROJECT, 'db.sqlite3'), db_copy)
    bootstrap(db_copy)

    from django.contrib.auth import get_user_model
    from django.test import Client
    from qa import endpoints

    U = get_user_model()
    urls = endpoints.discover_smoke_urls()

    # sampel merata: 10 akun pertama dari tiap shard dari 13 shard
    sample = []
    for shard in range(13):
        sample.extend(pick_accounts(shard, 13, args.limit))

    rows = []
    t0 = time.time()
    for un in sample:
        user = U.objects.select_related('profile__unit_kerja').get(username=un)
        profile = getattr(user, 'profile', None)
        role = profile.role if profile else '-'
        unit = profile.unit_kerja.code if profile and profile.unit_kerja else '-'
        c = Client()
        c.force_login(user)
        for url in urls:
            try:
                r = c.get(url)
                status = r.status_code
            except Exception as e:
                status = f'EXC:{type(e).__name__}'
            rows.append([un, role, unit, url, status])

    out = args.out or os.path.join(outdir, f'pass{args.pass_no}.json')
    json.dump({'pass': args.pass_no, 'accounts': len(sample),
               'urls': len(urls), 'requests': len(rows),
               'sec': round(time.time() - t0, 1), 'rows': rows},
              open(out, 'w', encoding='utf-8'))
    print(json.dumps({'pass': args.pass_no, 'accounts': len(sample),
                      'requests': len(rows), 'sec': round(time.time() - t0, 1),
                      'out': out}))
    try:
        os.remove(db_copy)
    except OSError:
        pass


if __name__ == '__main__':
    main()
