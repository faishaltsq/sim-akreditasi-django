"""Agregasi shard QA: gabungkan semua shard*.json menjadi ringkasan + temuan.

Aturan dedupe: satu temuan = satu pasangan (url, role, status) + jumlah akun
terdampak. BUKAN satu baris per akun.

Pemakaian:
    python -m qa.aggregate --dir qa/shards/smoke
    python -m qa.aggregate --dir qa/shards/smoke --out qa/reports/smoke.json
"""
import argparse
import glob
import json
import os
from collections import Counter, defaultdict


def load_shards(shard_dir):
    files = sorted(glob.glob(os.path.join(shard_dir, 'shard*.json')))
    # abaikan file probe bertanda garis bawah
    files = [f for f in files if not os.path.basename(f).startswith('_')]
    return files, [json.load(open(f, encoding='utf-8')) for f in files]


def aggregate(shard_dir, expected_accounts=None, expected_urls=None):
    files, shards = load_shards(shard_dir)

    accounts = 0
    requests = 0
    by_status = Counter()
    by_role = defaultdict(Counter)
    findings = defaultdict(lambda: {'count': 0, 'samples': [], 'units': set()})
    flaky = defaultdict(list)
    per_url_status = defaultdict(lambda: defaultdict(set))

    for sh in shards:
        accounts += sh.get('accounts', 0)
        for row in sh.get('rows', []):
            un, role, unit, url, status = row[0], row[1], row[2], row[3], row[4]
            requests += 1
            by_status[str(status)] += 1
            by_role[role][str(status)] += 1
            per_url_status[(un, url)][status].add(role)

        for f in sh.get('findings', []):
            un, role, unit, url, status = f[0], f[1], f[2], f[3], f[4]
            key = (url, role, str(status))
            entry = findings[key]
            entry['count'] += 1
            if unit not in entry['units']:
                entry['units'].add(unit)
            if len(entry['samples']) < 3:
                entry['samples'].append(un)

    # deteksi flaky: pasangan (akun,url) dengan >1 status berbeda
    for (un, url), statuses in per_url_status.items():
        if len(statuses) > 1:
            flaky[url].append({'account': un, 'statuses': sorted(map(str, statuses))})

    total_finding_instances = sum(v['count'] for v in findings.values())
    finding_list = [
        {
            'url': url, 'role': role, 'status': status,
            'count': v['count'], 'units_affected': len(v['units']),
            'samples': v['samples'],
        }
        for (url, role, status), v in sorted(
            findings.items(), key=lambda kv: (-kv[1]['count'], kv[0])
        )
    ]

    result = {
        'shards_found': len(files),
        'shards_expected': None,
        'accounts': accounts,
        'accounts_expected': expected_accounts,
        'requests': requests,
        'urls_expected': expected_urls,
        'by_status': dict(sorted(by_status.items())),
        'by_role': {r: dict(sorted(c.items())) for r, c in sorted(by_role.items())},
        'finding_instances': total_finding_instances,
        'findings': finding_list,
        'flaky_urls': len(flaky),
        'flaky': {k: v[:5] for k, v in list(flaky.items())[:20]},
    }

    # gate
    gates = {}
    gates['coverage'] = (
        accounts == expected_accounts if expected_accounts is not None else None
    )
    gates['requests_match'] = (
        requests == accounts * expected_urls
        if expected_urls is not None and accounts else None
    )
    gates['no_500'] = by_status.get('500', 0) == 0
    gates['no_exceptions'] = not any(k.startswith('EXC') for k in by_status)
    gates['no_flaky'] = len(flaky) == 0
    result['gates'] = gates

    return result


def main():
    ap = argparse.ArgumentParser(description='Agregasi shard QA')
    ap.add_argument('--dir', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--expect-accounts', type=int, default=None)
    ap.add_argument('--expect-urls', type=int, default=None)
    args = ap.parse_args()

    res = aggregate(args.dir, args.expect_accounts, args.expect_urls)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=1)

    brief = {k: v for k, v in res.items() if k not in ('findings', 'by_role', 'flaky')}
    print(json.dumps(brief, indent=1))
    if res['findings']:
        print('\n--- TEMUAN (top 20, didedupe) ---')
        for f in res['findings'][:20]:
            print(f"  {f['count']:>5}x  {f['role']:<18} {f['status']:<6} "
                  f"{f['url']}  ({f['units_affected']} unit)")


if __name__ == '__main__':
    main()
