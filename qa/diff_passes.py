"""Bandingkan dua pass regression dan laporkan pasangan flaky.

Flaky = pasangan (akun, url) yang statusnya berbeda antara pass 1 dan pass 2.
"""
import argparse
import glob
import json
import os
from collections import defaultdict


def load_pass(shard_dir, tag):
    data = {}
    for f in sorted(glob.glob(os.path.join(shard_dir, f'{tag}_shard*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        for row in d.get('rows', []):
            un, url, status = row[0], row[3], row[4]
            data[(un, url)] = status
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='qa/shards/regression')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    p1 = load_pass(args.dir, 'p1')
    p2 = load_pass(args.dir, 'p2')

    common = set(p1) & set(p2)
    only1 = set(p1) - set(p2)
    only2 = set(p2) - set(p1)

    flaky = []
    for key in common:
        if p1[key] != p2[key]:
            flaky.append({'account': key[0], 'url': key[1],
                          'pass1': p1[key], 'pass2': p2[key]})

    by_url = defaultdict(int)
    for f in flaky:
        by_url[f['url']] += 1

    result = {
        'pairs_pass1': len(p1),
        'pairs_pass2': len(p2),
        'pairs_common': len(common),
        'missing_in_pass2': len(only1),
        'missing_in_pass1': len(only2),
        'flaky_pairs': len(flaky),
        'flaky_by_url': dict(sorted(by_url.items(), key=lambda kv: -kv[1])),
        'flaky_samples': flaky[:30],
        'gate_no_flaky': len(flaky) == 0,
        'gate_same_coverage': len(only1) == 0 and len(only2) == 0,
    }

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(result, open(args.out, 'w', encoding='utf-8'), indent=1)

    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
