"""Extract survey EP and RDWOS cells from PDF clipping geometry, not prose letters."""
from __future__ import annotations

import re

RDWOS = frozenset('RDWOS')


def _normal(text):
    return re.sub(r'\s+', ' ', text).strip()


def _inside(fragment, rect):
    x, y, width, height = rect
    return x - 0.2 <= fragment['x'] <= x + width + 0.2 and y - 0.2 <= fragment['y'] <= y + height + 0.2


def _joined(fragments):
    lines = []
    for fragment in sorted(fragments, key=lambda f: (-round(f['y'], 1), f['x'])):
        if not _normal(fragment['text']):
            continue
        if not lines or abs(lines[-1][0] - fragment['y']) > 1.5:
            lines.append((fragment['y'], [fragment]))
        else:
            lines[-1][1].append(fragment)
    return _normal(' '.join(''.join(f['text'] for f in sorted(parts, key=lambda f: f['x'])) for _, parts in lines))


def _header_rect(fragment, rectangles):
    candidates = [r for r in rectangles if 60 <= r[2] <= 300 and 5 <= r[3] <= 60 and _inside(fragment, r)]
    return max(candidates, key=lambda r: r[2]) if candidates else None


def extract_survey_cells(page_number, rectangles, fragments):
    rectangles = sorted(set(tuple(float(v) for v in r) for r in rectangles), key=lambda r: (-r[1], r[0]))
    fragments = [f for f in fragments if _normal(f['text'])]
    headings = [f for f in fragments if _normal(f['text']) == 'Kelengkapan Bukti']
    headers = []
    anomalies = []
    for heading in headings:
        evidence = _header_rect(heading, rectangles)
        if evidence is None:
            anomalies.append({'kind': 'missing_survey_table_geometry', 'page': page_number})
            continue
        type_headers = [r for r in rectangles if abs(r[1] - evidence[1]) < 1 and abs(r[3] - evidence[3]) < 1 and 8 <= r[2] <= 40 and abs(r[0] + r[2] - evidence[0]) < 2]
        if type_headers:
            type_header = min(type_headers, key=lambda r: r[0])
            evidence = (type_header[0], evidence[1], evidence[0] + evidence[2] - type_header[0], evidence[3])
        peers = [r for r in rectangles if abs(r[1] - evidence[1]) < 1 and abs(r[3] - evidence[3]) < 1 and r[0] + r[2] <= evidence[0] + 1 and r[2] > 60]
        if not peers:
            anomalies.append({'kind': 'missing_ep_column', 'page': page_number})
            continue
        left = max(peers, key=lambda r: (r[2], r[0]))
        header = (left, evidence)
        if header not in headers:
            headers.append(header)
    headers.sort(key=lambda h: -h[0][1])
    rows = []
    for hindex, (left, evidence) in enumerate(headers):
        next_top = headers[hindex + 1][0][1] + headers[hindex + 1][0][3] if hindex + 1 < len(headers) else -1
        candidates = [r for r in rectangles if abs(r[0] + r[2] - left[0] - left[2]) < 0.3 and left[0] - 1 <= r[0] <= left[0] + 30 and r[3] > 5 and r[1] + r[3] <= left[1] + 1 and r[1] >= next_top - 1]
        candidates = [(left[0], r[1], left[2], r[3]) for r in candidates]
        for rect in sorted(candidates, key=lambda r: -(r[1] + r[3])):
            if any(abs(rect[1] - existing['_rect'][1]) < 1 and abs(rect[3] - existing['_rect'][3]) < 1 for existing in rows):
                continue
            left_fragments = [f for f in fragments if _inside(f, rect)]
            text = _joined(left_fragments)
            match = re.match(r'^([a-z]|\d+)[.)]\s*(.*)', text)
            label = match.group(1) if match else None
            description = match.group(2) if match else text
            small_cells = [r for r in rectangles if evidence[0] - 1 <= r[0] <= evidence[0] + 1 and 8 <= r[2] <= 40 and r[3] > 5 and r[1] < rect[1] + rect[3] and r[1] + r[3] > rect[1]]
            marker_right = evidence[0] + min((r[2] for r in small_cells), default=25)
            right_rect = (evidence[0], rect[1], evidence[2], rect[3])
            right_fragments = [f for f in fragments if _inside(f, right_rect)]
            markers = sorted([f for f in right_fragments if f['x'] < marker_right + 1 and _normal(f['text']) in RDWOS], key=lambda f: -f['y'])
            body = [f for f in right_fragments if f['x'] >= marker_right + 0.2]
            evidence_entries = []
            if not markers and body:
                evidence_entries.append({'category_type': None, 'instruction': _joined(body), 'source_pages': [page_number]})
            assigned = set()
            for mindex, marker in enumerate(markers):
                top = marker['y'] + 2
                bottom = markers[mindex + 1]['y'] + 2 if mindex + 1 < len(markers) else rect[1] - 1
                cells = [cell for cell in small_cells if _inside(marker, cell) and sum(_inside(other, cell) for other in markers) == 1]
                if cells:
                    cell = max(cells, key=lambda r: r[3])
                    bottom, top = max(rect[1] - 1, cell[1] - 0.2), min(rect[1] + rect[3], cell[1] + cell[3] + 0.2)
                parts = [f for f in body if bottom < f['y'] <= top]
                assigned.update(id(f) for f in parts)
                evidence_entries.append({'category_type': _normal(marker['text']), 'instruction': _joined(parts), 'source_pages': [page_number]})
            unassigned = [f for f in body if id(f) not in assigned]
            if markers and unassigned:
                evidence_entries.insert(0, {'category_type': None, 'instruction': _joined(unassigned), 'source_pages': [page_number]})
            if text or evidence_entries:
                rows.append({'letter': label, 'description': description, 'evidence': evidence_entries, 'source_pages': [page_number], '_rect': rect, 'top': rect[1] + rect[3]})
    for row in rows:
        row.pop('_rect')
    return {'rows': sorted(rows, key=lambda r: -r['top']), 'anomalies': anomalies}
