"""Pure, source-aware STARKES extraction; no Django setup or database writes."""
from __future__ import annotations

import re


CHAPTERS = (
    'TKRS', 'KPS', 'MFK', 'PMKP', 'MRMIK', 'PPI', 'PPK', 'AKP',
    'HPK', 'PP', 'PAP', 'PAB', 'PKPO', 'KE', 'SKP', 'PROGNAS',
)
HEADER_RE = re.compile(
    r'Elemen\s+Peni(?:laian|alian|alaian)\s+(?:dari\s+)?'
    r'(?:Standar\s+)?([A-Za-z]+)\s*[.]?\s*(\d+(?:\.\d+)*)',
    re.IGNORECASE,
)
FURNITURE_RE = re.compile(
    r'^\s*(?:-\s*\d+\s*-|KEMENTERIAN\s+KESEHATAN|jdih\.kemkes\.go\.id)\s*$',
    re.IGNORECASE,
)
SECTION_RE = re.compile(
    r'^\s*(?:(?:\d+|[a-zA-Z])[.)]\s*)?'
    r'(?:Standar[d]?\s+(?:' + '|'.join(CHAPTERS) + r')\b|Maksud\s+dan\s+Tujuan\s+(?:' + '|'.join(CHAPTERS) + r')\b|Gambaran\s+Umum\b)'
    r'|^\s*\d+\.\s+.*\((?:' + '|'.join(CHAPTERS) + r')\)\s*$'
    r'|^\s*(?:BAB\s+[IVXLCDM]+\b|[A-Z]\.\s+(?:Kelompok\b|Program\s+Nasional\b))',
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _extract_block(lines: list[tuple[int, str]], *, standard_code='') -> tuple[list[dict], list[dict]]:
    import hashlib

    items = []
    anomalies = []
    current = None
    mode = None
    root_indent = None
    root_style = None
    seen = set()
    lines = [(page, line) for page, line in lines if line.strip() and not FURNITURE_RE.match(line)]
    for index, (page, line) in enumerate(lines):
        if FURNITURE_RE.match(line) or HEADER_RE.search(line):
            continue
        if SECTION_RE.search(line):
            break
        match = re.match(r'^(\s*)([a-z]|\d+)([.)])\s+(.+)', line)
        label = match.group(2) if match else None
        indent = len(match.group(1)) if match else None
        is_numeric = bool(label and label.isdigit())
        content = match.group(4) if match else ''
        if match and match.group(3) == '.' and index + 1 < len(lines):
            following = lines[index + 1][1]
            if SECTION_RE.search(following) and 'Standar' in following and len(content) < 100:
                break
        if current and match and (re.match(r'^[–—-]\s*[a-z]\)', content) or re.search(r'\b[a-z]\)?\s*(?:[–—-]|hingga|sampai(?:\s+dengan)?)\s*$', current['_parts'][-1])):
            current['_parts'].append(line.strip())
            current['source_pages'].add(page)
            continue
        if current is None and match:
            mode = 'numeric' if is_numeric else 'letter'
            root_indent = indent
            root_style = match.group(3)
        same_mode = match and (is_numeric == (mode == 'numeric'))
        if current and match and match.group(3) == '.' and root_style != '.' and indent <= root_indent:
            break
        is_root = bool(same_mode and indent <= root_indent + 6)
        if current is not None and match and is_numeric and mode == 'letter' and indent <= root_indent:
            if re.match(r'^\s*\d+\.\s+[A-Z]', line):
                break
        if is_root:
            if len(content) < 25 and re.match(r'^(pada|dalam|di)\b', content):
                if current:
                    current['_parts'].append(line.strip())
                    current['source_pages'].add(page)
                continue
            if label in seen:
                anomalies.append({'kind': 'repeated_ep_label', 'standard_code': standard_code, 'page': page, 'letter': label})
                break
            seen.add(label)
            current = {'letter': label, '_parts': [content], 'source_pages': {page}}
            items.append(current)
        elif current and line.strip():
            current['_parts'].append(line.strip())
            current['source_pages'].add(page)
    for item in items:
        item['description'] = normalize_text(' '.join(item.pop('_parts')))
        item['source_pages'] = sorted(item['source_pages'])
        item['evidence_types'] = []
        item['description_sha256'] = hashlib.sha256(item['description'].encode('utf-8')).hexdigest()
        if standard_code:
            item['standard_code'] = standard_code
            item['code'] = standard_code + ' EP ' + item['letter']
    return items, anomalies


def extract_ep_items(block: str) -> list[dict]:
    items, _ = _extract_block([(1, line) for line in block.splitlines()])
    return [{'letter': item['letter'], 'description': item['description'], 'evidence_types': []} for item in items]


def extract_survey_cells(page_number, rectangles, fragments):
    from .starkes_survey import extract_survey_cells as extract_cells

    return extract_cells(page_number, rectangles, fragments)


def parse_decree_pages(pages: list[dict]) -> dict:
    sections = []
    current = None
    for page in pages:
        for line in page['text'].splitlines():
            match = HEADER_RE.search(line)
            if match and match.group(1).upper() in CHAPTERS:
                current = {'standard_code': match.group(1).upper() + ' ' + match.group(2), 'page': page['page'], 'lines': []}
                sections.append(current)
            elif current is not None:
                current['lines'].append((page['page'], line))
    items = []
    anomalies = []
    codes = set()
    for section in sections:
        extracted, issues = _extract_block(section['lines'], standard_code=section['standard_code'])
        anomalies.extend(issues)
        if not extracted:
            anomalies.append({'kind': 'empty_ep_section', 'standard_code': section['standard_code'], 'page': section['page']})
        labels = [item['letter'] for item in extracted]
        if labels:
            expected = [str(index + 1) for index in range(len(labels))] if labels[0].isdigit() else [chr(97 + index) for index in range(len(labels))]
            if labels != expected:
                anomalies.append({'kind': 'nonsequential_ep_labels', 'standard_code': section['standard_code'], 'page': section['page'], 'source_labels': labels})
        for item in extracted:
            if item['code'] in codes:
                anomalies.append({'kind': 'duplicate_ep', 'code': item['code'], 'page': section['page']})
                continue
            codes.add(item['code'])
            items.append(item)
    return {'items': items, 'anomalies': anomalies, 'heading_count': len(sections)}
