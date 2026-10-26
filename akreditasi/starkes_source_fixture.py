"""Build review-only STARKES source artifacts without importing Django or writing a DB."""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from .starkes_sources import CHAPTERS, HEADER_RE, normalize_text, parse_decree_pages
from .starkes_survey import _joined, extract_survey_cells


def assemble_survey_rows(pages):
    items, anomalies = [], []
    current, standard = None, None
    candidates = []
    for page in pages:
        number = page['page']
        anomalies.extend(page.get('anomalies', []))
        events = [(h['top'], 0, h) for h in page.get('headings', [])]
        events += [(row['top'], 1, row) for row in page.get('rows', [])]
        for _, kind, event in sorted(events, key=lambda e: (-e[0], e[1])):
            if kind == 0:
                if event['kind'] == 'standard':
                    if standard is not None:
                        candidates = []
                    standard, current = None, None
                    if event['standard_code'] not in candidates:
                        candidates.append(event['standard_code'])
                else:
                    new_standard = event['standard_code']
                    if new_standard != standard:
                        current = None
                    standard = new_standard
                continue
            label = event['letter']
            if label is not None:
                current = {
                    'survey_key': f'survey:{number}:{len(items) + 1}',
                    'standard_code': standard,
                    'standard_candidates': list(candidates),
                    'code': f'{standard} EP {label}' if standard else None,
                    'letter': label, 'description': '', 'source_pages': [], 'evidence': [],
                }
                items.append(current)
            if current is None:
                anomalies.append({'kind': 'orphan_survey_continuation', 'page': number, 'row': deepcopy(event)})
                continue
            current['description'] = normalize_text(current['description'] + ' ' + event['description'])
            current['source_pages'] = sorted(set(current['source_pages'] + [number]))
            for evidence in deepcopy(event['evidence']):
                if evidence['category_type'] is None and label is None and current['evidence']:
                    previous = current['evidence'][-1]
                    previous['instruction'] = normalize_text(previous['instruction'] + ' ' + evidence['instruction'])
                    previous['source_pages'] = sorted(set(previous['source_pages'] + evidence['source_pages']))
                else:
                    current['evidence'].append(evidence)
    seen = set()
    for item in items:
        item['description_sha256'] = hashlib.sha256(item['description'].encode()).hexdigest()
        item['evidence_types'] = sorted({e['category_type'] for e in item['evidence'] if e['category_type']})
        if item['code'] and item['code'] in seen:
            anomalies.append({'kind': 'duplicate_survey_code', 'code': item['code'], 'survey_key': item['survey_key']})
        seen.add(item['code'])
        for entry in item['evidence']:
            if entry['category_type'] is None or not entry['instruction']:
                anomalies.append({'kind': 'incomplete_evidence_cell', 'survey_key': item['survey_key'], 'source_pages': entry['source_pages']})
    return {'items': items, 'anomalies': anomalies}


def _fingerprint(text):
    text = text.casefold()
    parts = []
    for index, char in enumerate(text):
        previous_digit = index > 0 and text[index - 1].isdigit()
        next_digit = index + 1 < len(text) and text[index + 1].isdigit()
        if char.isalnum() or char in '<>=+%' or (char in '.,:/-–—−' and previous_digit and next_digit) or (char in '-−' and next_digit):
            parts.append(char)
    return ''.join(parts)


def reconcile_sources(decree, survey):
    by_text = defaultdict(list)
    by_code = {item['code']: item for item in decree['items']}
    for item in decree['items']:
        by_text[_fingerprint(item['description'])].append(item['code'])
    links, review = [], []
    for item in survey['items']:
        matches = by_text.get(_fingerprint(item['description']), [])
        declared = item.get('code')
        match = declared if declared in matches else matches[0] if len(matches) == 1 else None
        if match:
            links.append({'survey_key': item['survey_key'], 'decree_code': match,
                          'match_method': 'EXACT_NORMALIZED_TEXT', 'review_status': 'PENDING_OWNER_REVIEW'})
            if declared and declared != match:
                review.append({'kind': 'source_code_conflict', 'survey_key': item['survey_key'],
                               'declared_survey_code': declared, 'text_matched_decree_code': match})
        else:
            review.append({'kind': 'ambiguous_exact_text' if matches else 'source_text_diff' if declared in by_code else 'survey_ep_without_exact_decree_match',
                           'survey_key': item['survey_key'], 'suggested_decree_code': declared if declared in by_code else None,
                           'exact_text_candidates': matches})
    linked = {link['decree_code'] for link in links}
    for item in decree['items']:
        if item['code'] not in linked:
            review.append({'kind': 'decree_ep_without_exact_survey_match', 'decree_code': item['code']})
    return {'schema_version': 1, 'review_status': 'PENDING_OWNER_REVIEW', 'production_ready': False,
            'decree_items': deepcopy(decree['items']), 'survey_items': deepcopy(survey['items']),
            'links': links, 'review_queue': review,
            'parser_anomalies': {'decree': decree['anomalies'], 'survey': survey['anomalies']}}


def survey_page_headings(fragments):
    lines = defaultdict(list)
    for fragment in fragments:
        lines[round(fragment['y'])].append(fragment)
    headings = []
    standard_re = re.compile(r'^\s*(?:(?:\d+|[a-z])[.)]\s*)?Standar[d]?\s+([A-Za-z]+)\s*\.?\s*(\d+(?:\.\d+)*)', re.I)
    for top, parts in lines.items():
        text = _joined(parts)
        match = HEADER_RE.search(text)
        kind = 'ep'
        if not match:
            match = standard_re.search(text)
            kind = 'standard'
        if match and match.group(1).upper() in CHAPTERS:
            headings.append({'top': top, 'kind': kind, 'standard_code': match.group(1).upper() + ' ' + match.group(2)})
    return headings


def read_source_pdf(path, *, survey=False):
    from pypdf import PdfReader
    from pypdf.generic import ContentStream

    path = Path(path)
    source_bytes = path.read_bytes()
    reader = PdfReader(BytesIO(source_bytes))
    pages = []
    for number, page in enumerate(reader.pages, 1):
        record = {'page': number}
        if survey:
            fragments = []
            def visit(text, cm, tm, font, size):
                if text.strip():
                    fragments.append({'x': cm[4] + tm[4], 'y': cm[5] + tm[5], 'text': text})
            record['text'] = page.extract_text(visitor_text=visit) or ''
            rectangles = [tuple(float(v) for v in args) for args, op in ContentStream(page.get_contents(), page.pdf).operations if op == b're' and len(args) == 4]
            record.update(extract_survey_cells(number, rectangles, fragments))
            record['headings'] = survey_page_headings(fragments)
        else:
            record['text'] = page.extract_text() or ''
        pages.append(record)
    decree_number = 'HK.02.02/D/47104/2024' if survey else 'HK.01.07/MENKES/1596/2024'
    if decree_number not in re.sub(r'\s+', '', ''.join(p['text'] for p in pages[:10])):
        raise ValueError(f'Dokumen sumber tidak memuat nomor {decree_number}; tidak dapat diberi provenance STARKES 2024.')
    manifest = {'filename': path.name, 'sha256': hashlib.sha256(source_bytes).hexdigest(),
                'pages': len(pages), 'document_type': 'SURVEY_INSTRUMENT' if survey else 'STANDARD_DECREE',
                'decree_number': decree_number,
                'role': 'RDWOS_EVIDENCE' if survey else 'CANONICAL_EP_TEXT'}
    return pages, manifest


def artifact_manifest(artifact):
    return {'schema_version': 1, 'review_status': artifact['review_status'], 'production_ready': False,
            'sources': artifact['sources'],
            'inventory_is_official': False,
            'inventory': {'decree_eps': len(artifact['decree_items']), 'survey_eps': len(artifact['survey_items']),
                          'exact_text_links': len(artifact['links']),
                          'evidence_instructions': sum(len(i['evidence']) for i in artifact['survey_items']),
                          'chapters': dict(Counter(i['standard_code'].split()[0] for i in artifact['decree_items'])),
                          'evidence_types': dict(Counter(e['category_type'] or 'UNTYPED' for i in artifact['survey_items'] for e in i['evidence'])),
                          'review_reasons': dict(Counter(r['kind'] for r in artifact['review_queue'])),
                          'parser_anomalies': {kind: dict(Counter(a['kind'] for a in values)) for kind, values in artifact['parser_anomalies'].items()}}}


def render_review_csv(artifact):
    import csv
    from io import StringIO

    output = StringIO(newline='')
    fields = ['status', 'kind', 'decree_code', 'survey_key', 'declared_survey_code',
              'decree_pages', 'survey_pages', 'decree_text', 'survey_text', 'rdwos_instruction', 'detail']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    decree = {i['code']: i for i in artifact['decree_items']}
    survey = {i['survey_key']: i for i in artifact['survey_items']}
    links = {link['survey_key']: link['decree_code'] for link in artifact['links']}
    issues = artifact['review_queue'] + [issue for values in artifact['parser_anomalies'].values() for issue in values]
    for issue in issues:
        survey_key = issue.get('survey_key', '')
        survey_item = survey.get(survey_key, {})
        decree_code = issue.get('decree_code') or issue.get('suggested_decree_code') or issue.get('text_matched_decree_code') or links.get(survey_key, '')
        decree_item = decree.get(decree_code, {})
        writer.writerow({'status': 'PENDING_OWNER_REVIEW', 'kind': issue['kind'],
                         'decree_code': decree_code, 'survey_key': survey_key,
                         'declared_survey_code': survey_item.get('code') or '',
                         'decree_pages': ','.join(map(str, decree_item.get('source_pages', []))),
                         'survey_pages': ','.join(map(str, survey_item.get('source_pages', []))),
                         'decree_text': decree_item.get('description', ''),
                         'survey_text': survey_item.get('description', ''),
                         'rdwos_instruction': '\n'.join((e['category_type'] or '?') + ': ' + e['instruction'] for e in survey_item.get('evidence', [])),
                         'detail': json.dumps(issue, ensure_ascii=False, sort_keys=True)})
    return output.getvalue()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decree', required=True)
    parser.add_argument('--survey', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    decree_pages, decree_manifest = read_source_pdf(args.decree)
    survey_pages, survey_manifest = read_source_pdf(args.survey, survey=True)
    artifact = reconcile_sources(parse_decree_pages(decree_pages), assemble_survey_rows(survey_pages))
    artifact['sources'] = {'decree': decree_manifest, 'survey': survey_manifest}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(artifact, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    output.write_bytes(payload)
    review_payload = render_review_csv(artifact).encode('utf-8')
    review_path = output.with_suffix('.review.csv')
    review_path.write_bytes(review_payload)
    manifest = artifact_manifest(artifact)
    manifest['artifact_sha256'] = hashlib.sha256(payload).hexdigest()
    manifest['review_csv_sha256'] = hashlib.sha256(review_payload).hexdigest()
    manifest_path = output.with_suffix('.manifest.json')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
