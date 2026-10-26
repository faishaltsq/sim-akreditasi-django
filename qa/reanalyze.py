"""Analisis ulang shard yang sudah ada dengan aturan ekspektasi terbaru.

Dipakai ketika aturan findings berubah tapi data mentah (rows) masih valid.
Tidak menjalankan request apa pun.
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    from qa import expectations

    accounts = 0
    requests = 0
    by_status = Counter()
    by_role = defaultdict(Counter)
    findings = defaultdict(lambda: {'count': 0, 'units': set(), 'samples': []})
    url_role_status = defaultdict(Counter)

    for f in sorted(glob.glob(os.path.join(args.dir, 'shard*.json'))):
        if os.path.basename(f).startswith('_'):
            continue
        d = json.load(open(f, encoding='utf-8'))
        accounts += d.get('accounts', 0)
        for row in d.get('rows', []):
            un, role, unit, url, status = row[0], row[1], row[2], row[3], row[4]
            requests += 1
            by_status[str(status)] += 1
            by_role[role][str(status)] += 1
            url_role_status[url][role] += 1

            if expectations.is_finding(role, url, status, None, unit):
                key = (url, role, str(status))
                e = findings[key]
                e['count'] += 1
                e['units'].add(unit)
                if len(e['samples']) < 3:
                    e['samples'].append(un)

    out = {
        'accounts': accounts,
        'requests': requests,
        'by_status': dict(sorted(by_status.items())),
        'by_role': {r: dict(sorted(c.items())) for r, c in sorted(by_role.items())},
        'findings': [
            {'url': u, 'role': r, 'status': s, 'count': v['count'],
             'units_affected': len(v['units']), 'samples': v['samples']}
            for (u, r, s), v in sorted(findings.items(),
                                       key=lambda kv: (-kv[1]['count'], kv[0]))
        ],
    }

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(out, open(args.out, 'w', encoding='utf-8'), indent=1)

    print(json.dumps({k: v for k, v in out.items() if k != 'findings'}, indent=1))
    print(f"\n--- TEMUAN: {len(out['findings'])} jenis ---")
    for x in out['findings'][:30]:
        print(f"  {x['count']:>5}x  {x['role']:<18} {x['status']:<5} "
              f"{x['url']}  ({x['units_affected']} unit)")


if __name__ == '__main__':
    main()
