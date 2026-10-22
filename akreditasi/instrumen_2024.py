"""Deterministic extractor for the STARKES 2024 accreditation instrument (PDF).

The instrument is a typeset PDF.  Its Elemen-Penilaian tables are *ruled*
tables: every row band is delimited by horizontal rules, every column by
vertical rules, and those rules live in ``page.rects`` (thin filled
rectangles) — never in ``page.lines``.

That geometry is what disambiguates the facts the import needs:

* which text belongs to the description cell, the evidence cell, or the score
  cell — plain-text concatenation mixes all three, which is why the legacy
  fixture carries strings like ``"... oleh Pemilik. R ... 10 - 0"``;
* whether a lettered marker (``a)``) opens an EP row or is prose that merely
  contains ``a)``;
* whether an ``R``/``D``/``W``/``O``/``S`` is an evidence-type marker or a
  letter inside a sentence;
* where a row continues across a page break, because the next page repeats the
  column header and the grid restarts.

Table anatomy (four text columns, one of them narrow)::

    | Elemen Penilaian |  | Kelengkapan Bukti | Skoring |
    | a) statement...  |D | evidence detail   | 10      |
    |                  |  |                   | 5       |
    |                  |  |                   | 0       |

The narrow column between the description and the evidence detail carries the
RDWOS letters.  One logical EP is one band between two horizontal rules; its
description cell may wrap over several lines and its marker column may list
several evidence types, and both still belong to that single EP.

Everything here is pure and Django-free so it can be unit-tested without a
database, and so the management command can consume a pre-generated golden
fixture instead of re-parsing a 415-page PDF on every deploy.

Public API
----------
``extract_document(pdf_path)``  -> ``Document`` (pages of words + rules)
``save_document(doc, path)``    -> cache the extraction as JSON
``document_from_cache(path)``   -> ``Document`` from a cached extraction
``parse_document(document)``    -> ``OrderedDict[str, list[dict]]``
``extract_pdf(pdf_path)``       -> convenience wrapper around the two above
``build_fixture(standards)``    -> list of fixture records (repo format)
``dump_fixture(std, path)``     -> write that fixture deterministically
``validate(standards)``         -> audit report for a parsed document
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

# --------------------------------------------------------------------------
# Chapter (BAB) metadata — the 16 chapters of the 2024 instrument.
# --------------------------------------------------------------------------
BAB_ORDER = [
    'TKRS', 'KPS', 'MFK', 'PMKP', 'MRMIK', 'PPI', 'AKP', 'HPK',
    'PP', 'PAP', 'PAB', 'PKPO', 'KE', 'SKP', 'PROGNAS', 'PPK',
]

BAB_META = {
    'TKRS':    {'name': 'Tata Kelola Rumah Sakit',                 'order': 1,  'kelompok': 'MANAJEMEN'},
    'KPS':     {'name': 'Kualifikasi & Pendidikan Staf',           'order': 2,  'kelompok': 'MANAJEMEN'},
    'MFK':     {'name': 'Manajemen Fasilitas & Keselamatan',       'order': 3,  'kelompok': 'MANAJEMEN'},
    'PMKP':    {'name': 'Peningkatan Mutu & Keselamatan Pasien',   'order': 4,  'kelompok': 'MANAJEMEN'},
    'MRMIK':   {'name': 'Manajemen Informasi & Rekam Medis',       'order': 5,  'kelompok': 'MANAJEMEN'},
    'PPI':     {'name': 'Pencegahan & Pengendalian Infeksi',       'order': 6,  'kelompok': 'MANAJEMEN'},
    'AKP':     {'name': 'Akses dan Kontinuitas Pelayanan',         'order': 7,  'kelompok': 'PELAYANAN'},
    'HPK':     {'name': 'Hak Pasien dan Keluarga',                 'order': 8,  'kelompok': 'PELAYANAN'},
    'PP':      {'name': 'Pengkajian Pasien',                       'order': 9,  'kelompok': 'PELAYANAN'},
    'PAP':     {'name': 'Pelayanan dan Asuhan Pasien',             'order': 10, 'kelompok': 'PELAYANAN'},
    'PAB':     {'name': 'Pelayanan Anestesi dan Bedah',            'order': 11, 'kelompok': 'PELAYANAN'},
    'PKPO':    {'name': 'Pelayanan Kefarmasian & Penggunaan Obat', 'order': 12, 'kelompok': 'PELAYANAN'},
    'KE':      {'name': 'Komunikasi dan Edukasi',                  'order': 13, 'kelompok': 'PELAYANAN'},
    'SKP':     {'name': 'Sasaran Keselamatan Pasien',              'order': 14, 'kelompok': 'SASARAN_KP'},
    'PROGNAS': {'name': 'Program Nasional',                        'order': 15, 'kelompok': 'PROGNAS'},
    'PPK':     {'name': 'Pendidikan dalam Pelayanan Kesehatan',    'order': 16, 'kelompok': 'PENDIDIKAN'},
}

# Legacy prefix aliases: old code -> current code.
LEGACY_ALIASES = {
    'ARK': 'AKP',
    'IPKP': 'PPK',
    'MIRM': 'MRMIK',
}

BAB_CANON = {b: b for b in BAB_ORDER}

EVIDENCE_TYPES = ('R', 'D', 'W', 'O', 'S')

# --------------------------------------------------------------------------
# Regular expressions
# --------------------------------------------------------------------------
# "Standar" is sometimes typeset "Standard" and occasionally with a split
# word; the same happens to "Elemen Penilaian" and "Skoring".
_WORD_STANDAR = r'S\s*t\s*a\s*n\s*d\s*a\s*r\s*d?'
_WORD_ELEMEN = r'E\s*l\s*e\s*m\s*e\s*n'
_WORD_PENILAIAN = r'P\s*e\s*n\s*i\s*l\s*a\s*i\s*a\s*n'
_WORD_SKORING = r'S\s*k\s*o\s*r\s*i\s*n\s*g'
# The instrument also typesets "Eleman Penilaian" (missing "e"), which would
# otherwise lose that standard's whole EP table.
_WORD_ELEMEN_ALT = r'E\s*l\s*e\s*m\s*[ea]\s*n'

_NUM = r'\d+(?:\s*\.\s*\d+)*'
_ROMAN = r'[IVXL]{1,4}'

# A heading is "<marker> <keyword> <rest>" where the marker is 1-2 digits or a
# single lowercase letter followed by "." or ")".
_HEAD = r'(?:\d{1,2}|[a-z])\s*[\.\)]'

STD_RE = re.compile(r'^\s*' + _HEAD + r'\s*' + _WORD_STANDAR + r'\s+(.+?)\s*$', re.I)
EPHD_RE = re.compile(r'^\s*' + _HEAD + r'\s*(?:' + _WORD_ELEMEN + r'|' + _WORD_ELEMEN_ALT +
                     r')\s+' + _WORD_PENILAIAN +
                     r'\s*(?:' + _WORD_STANDAR + r'\s+)?(.+?)\s*$', re.I)
TUJU_RE = re.compile(r'^\s*' + _HEAD + r'\s*Maksud\s+dan\s+Tujuan\s+(.+?)\s*$', re.I)

# Code tails: "TKRS 1", "HPK.1.2", "PKPO 7 .1", "PP I 7.2", "3.9"
CODE_PREFIX_NUM = re.compile(r'^([A-Za-z]+)\s*\.?\s*(' + _NUM + r')\s*[:\-–]?\s*$')
CODE_PREFIX_ROMAN_NUM = re.compile(r'^([A-Za-z]+)\s+(' + _ROMAN + r')\s+(' + _NUM + r')\s*[:\-–]?\s*$')
CODE_NUM_ONLY = re.compile(r'^(' + _NUM + r')\s*[:\-–]?\s*$')
# "MRMIK 2.1 dan MRMIK 2.2" / "KPS 10 sampai KPS 10.1"
CODE_MULTI = re.compile(r'^\s*([A-Za-z]+)\s*\.?\s*(' + _NUM + r')\s+(?:dan|sampai)\s+'
                        r'([A-Za-z]+)?\s*\.?\s*(' + _NUM + r')\s*[:\-–]?\s*$', re.I)

# A standalone EP row marker: a single letter or a 1-2 digit number followed by
# ")" or ".".  It must be a whole token — "a) pada maksud" is prose.
ROW_MARK = re.compile(r'^([a-z]|\d{1,2})[\.\)]$')
# Evidence-type letters.
EV_MARK = re.compile(r'^[RDWOS]$')
# Score values.
SCORE_VAL = re.compile(r'^\d{1,2}$')

# Column header labels.
HDR_DESC = re.compile(r'^' + _WORD_ELEMEN + r'\s+' + _WORD_PENILAIAN + r'$', re.I)
HDR_EVID = re.compile(r'^Kelengkapan\s+Bukti$', re.I)
HDR_SCORE = re.compile(r'^' + _WORD_SKORING + r'$', re.I)

# Rule/word merge tolerances, in PDF points.
RULE_TOL = 2.0
WORD_TOL = 3.0
MIN_BAND = 4.0
# A column narrower than this, sitting between the description and
# "Kelengkapan Bukti", carries RDWOS marker letters rather than text.
MARKER_COL_MAX = 45.0


# --------------------------------------------------------------------------
# Document extraction
# --------------------------------------------------------------------------
class Document:
    """Pages of words and ruling lines, extracted once from the PDF."""

    __slots__ = ('pages', 'sha256', 'source')

    def __init__(self, pages, sha256='', source=''):
        self.pages = pages
        self.sha256 = sha256
        self.source = source

    def __len__(self):
        return len(self.pages)


def extract_document(pdf_path):
    """Extract words and ruling lines for every page of the PDF.

    Ruling lines come from ``page.rects``: the instrument draws its table
    borders as thin filled rectangles, so they never appear in ``page.lines``.
    """
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - environment issue
        raise RuntimeError('pdfplumber is required to parse the instrument PDF') from exc

    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            words = [(round(w['x0'], 1), round(w['x1'], 1),
                      round(w['top'], 1), round(w['bottom'], 1), w['text'])
                     for w in page.extract_words(keep_blank_chars=False)]
            hrules, vrules = [], []
            for r in page.rects:
                x0, top, x1, bottom = r['x0'], r['top'], r['x1'], r['bottom']
                if abs(x1 - x0) > 20 and abs(bottom - top) <= 2.5:
                    hrules.append((round(top, 1), round(x0, 1), round(x1, 1)))
                elif abs(bottom - top) > 8 and abs(x1 - x0) <= 2.5:
                    vrules.append((round(x0, 1), round(top, 1), round(bottom, 1)))
            pages.append({'words': words, 'h': hrules, 'v': vrules,
                          'width': round(page.width, 1),
                          'height': round(page.height, 1)})

    return Document(pages, sha256=file_sha256(pdf_path), source=str(pdf_path))


def save_document(document, path):
    """Cache an extracted document as JSON (used by tests and the command)."""
    Path(path).write_text(json.dumps({
        'sha256': document.sha256,
        'source': document.source,
        'pages': document.pages,
    }, ensure_ascii=False), encoding='utf-8')


def document_from_cache(cache_path):
    """Load a previously cached extraction (see :func:`save_document`)."""
    raw = json.loads(Path(cache_path).read_text(encoding='utf-8'))
    if isinstance(raw, dict) and 'pages' in raw:
        return Document(raw['pages'], raw.get('sha256', ''), raw.get('source', ''))
    return Document(raw)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Grid reconstruction
# --------------------------------------------------------------------------
def _merge(values, tol=RULE_TOL):
    """Collapse near-identical coordinates into one representative value."""
    groups = []
    for v in sorted(values):
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def _vertical_map(page):
    """``x -> [(y0, y1), ...]`` of vertical rules, grouped by merged x."""
    by_x = defaultdict(list)
    for (x, y0, y1) in page['v']:
        by_x[x].append((y0, y1))

    merged = OrderedDict()
    for x in _merge(by_x):
        segs = []
        for xx in by_x:
            if abs(xx - x) <= RULE_TOL:
                segs.extend(by_x[xx])
        segs.sort()
        runs = []
        for y0, y1 in segs:
            if runs and y0 - runs[-1][1] <= RULE_TOL:
                runs[-1] = (runs[-1][0], max(runs[-1][1], y1))
            else:
                runs.append((y0, y1))
        merged[x] = runs
    return merged


def _linked(vmap, ya, yb):
    """True when a vertical rule spans the gap between two horizontal rules."""
    mid = (ya + yb) / 2.0
    for segs in vmap.values():
        for (a, b) in segs:
            if a - RULE_TOL <= mid <= b + RULE_TOL:
                return True
    return False


def _spans(vmap, x, y0, y1):
    """True when the vertical rule at ``x`` covers most of ``[y0, y1]``.

    Only segments belonging to ``x`` are considered: a rule at another x that
    happens to cover the same y range belongs to a different table on the same
    page and must not add a column here.
    """
    covered = 0.0
    for (a, b) in vmap.get(x, ()):
        lo, hi = max(a, y0), min(b, y1)
        if hi > lo:
            covered = max(covered, hi - lo)
    return covered >= (y1 - y0) * 0.5


def page_tables(page):
    """Reconstruct the ruled tables on one page.

    Returns a list of ``{'rows': [y, ...], 'cols': [x, ...], 'y0', 'y1'}``
    where ``rows`` are horizontal rule positions and ``cols`` the vertical.
    """
    vmap = _vertical_map(page)
    rows = _merge([h[0] for h in page['h']])
    if len(rows) < 2 or len(vmap) < 3:
        return []

    tables = []
    i = 0
    while i < len(rows) - 1:
        j = i + 1
        while j < len(rows) and _linked(vmap, rows[j - 1], rows[j]):
            j += 1
        if j - i >= 2:
            y0, y1 = rows[i], rows[j - 1]
            cols = [x for x in vmap if _spans(vmap, x, y0, y1)]
            if len(cols) >= 3:
                tables.append({'rows': rows[i:j], 'cols': cols, 'y0': y0, 'y1': y1})
        i = j if j > i else i + 1
    return tables


def words_in(page, box):
    """Words whose centre falls inside ``box`` as ``[(top, cx, text), ...]``."""
    x0, y0, x1, y1 = box
    out = []
    for (wx0, wx1, wtop, wbot, txt) in page['words']:
        cx, cy = (wx0 + wx1) / 2.0, (wtop + wbot) / 2.0
        if x0 - 0.5 <= cx <= x1 + 0.5 and y0 - 0.5 <= cy <= y1 + 0.5:
            out.append((wtop, cx, txt))
    out.sort()
    return out


def cell_lines(page, box):
    """Rebuild the visual lines of a cell as ``[str, ...]``."""
    lines, cur, cur_y = [], [], None
    for y, x, text in words_in(page, box):
        if cur_y is None or abs(y - cur_y) <= WORD_TOL:
            cur.append((x, text))
            if cur_y is None:
                cur_y = y
        else:
            cur.sort()
            lines.append(' '.join(t for _, t in cur))
            cur, cur_y = [(x, text)], y
    if cur:
        cur.sort()
        lines.append(' '.join(t for _, t in cur))
    return lines


def page_lines(page):
    """All words of a page grouped into visual lines ``[(y, x, text), ...]``."""
    buckets = []
    for (wx0, wx1, wtop, wbot, txt) in page['words']:
        for b in buckets:
            if abs(b[0] - wtop) <= WORD_TOL:
                b[1].append((wx0, txt))
                break
        else:
            buckets.append([wtop, [(wx0, txt)]])
    out = []
    for y, parts in buckets:
        parts.sort()
        out.append((y, parts[0][0], ' '.join(t for _, t in parts)))
    out.sort()
    return out


def column_geometry(page, table):
    """Locate the text columns of a table from its header band.

    Returns ``(x_desc, x_mark, x_detail, x_score)``.  ``x_mark`` is the left
    edge of the narrow RDWOS column and equals ``x_detail`` when the table has
    no separate marker column.
    """
    cols = table['cols']
    hdr_y0, hdr_y1 = table['rows'][0], table['rows'][1]
    labels = [' '.join(cell_lines(page, (cols[i], hdr_y0, cols[i + 1], hdr_y1))).strip()
              for i in range(len(cols) - 1)]

    x_detail = x_score = None
    for i, label in enumerate(labels):
        if HDR_EVID.match(label):
            x_detail = cols[i]
        elif HDR_SCORE.match(label):
            x_score = cols[i]

    if x_detail is None:
        x_detail = cols[2] if len(cols) >= 3 else cols[-1]
    if x_score is None:
        x_score = cols[-2] if len(cols) >= 3 else cols[-1]

    # The narrow column immediately left of "Kelengkapan Bukti" holds the
    # RDWOS letters; a wide one there is the description itself.
    x_mark = x_detail
    if x_detail in cols:
        idx = cols.index(x_detail)
        if idx >= 1 and (x_detail - cols[idx - 1]) < MARKER_COL_MAX:
            x_mark = cols[idx - 1]

    return cols[0], x_mark, x_detail, x_score


def _band_cells(page, table, row_index):
    """Return the cell lines of one band keyed by column index."""
    a, b = table['rows'][row_index], table['rows'][row_index + 1]
    if b - a < MIN_BAND:
        return None
    cols = table['cols']
    return {i: cell_lines(page, (cols[i], a, cols[i + 1], b))
            for i in range(len(cols) - 1)}


def _clean(text):
    return re.sub(r'\s+', ' ', text).strip()


# --------------------------------------------------------------------------
# Code normalisation
# --------------------------------------------------------------------------
def canon_prefix(prefix):
    """Normalise a BAB prefix to its current code (``None`` when unknown)."""
    if not prefix:
        return None
    p = prefix.upper()
    p = LEGACY_ALIASES.get(p, p)
    return BAB_CANON.get(p)


def _strip_code_noise(text):
    text = re.sub(r'^\s*' + _WORD_STANDAR + r'\s+', '', text, flags=re.I)
    text = re.sub(r'^\s*dari\s+', '', text, flags=re.I)
    return text.strip(' :–-')


def parse_code_tail(text, current_prefix=None):
    """Parse the tail of a heading into ``[(prefix, number), ...]``.

    Handles ``"TKRS 1"``, ``"HPK.1.2"``, ``"PKPO 7 .1"``, ``"PP I 7.2"`` (a
    typesetting slip for PPI 7.2), ``"3.9"`` (prefix omitted) and the
    multi-code form ``"MRMIK 2.1 dan MRMIK 2.2"``.
    """
    text = _strip_code_noise(text)
    if not text:
        return []

    m = CODE_MULTI.match(text)
    if m:
        p1 = canon_prefix(m.group(1))
        p2 = canon_prefix(m.group(3)) or p1
        if p1:
            return [(p1, re.sub(r'\s+', '', m.group(2))),
                    (p2, re.sub(r'\s+', '', m.group(4)))]

    m = CODE_PREFIX_ROMAN_NUM.match(text)
    if m:
        prefix = canon_prefix(m.group(1))
        roman = m.group(2).upper()
        number = re.sub(r'\s+', '', m.group(3))
        if prefix == 'PP' and roman:
            # "Standar PP I 7.2" is a typesetting slip for PPI 7.2: the same
            # page's purpose block reads "Maksud dan Tujuan PPI 7.2".
            prefix = 'PPI'
        if prefix:
            return [(prefix, number)]

    m = CODE_PREFIX_NUM.match(text)
    if m:
        prefix = canon_prefix(m.group(1))
        if prefix:
            return [(prefix, re.sub(r'\s+', '', m.group(2)))]

    m = CODE_NUM_ONLY.match(text)
    if m and current_prefix:
        return [(current_prefix, re.sub(r'\s+', '', m.group(1)))]
    return []


def sort_code_key(code):
    """Sort key for standard codes: chapter order, then numeric parts."""
    parts = code.split()
    prefix = parts[0]
    num = parts[1] if len(parts) > 1 else '0'
    try:
        nums = tuple(float(x) for x in num.split('.'))
    except ValueError:
        nums = (0.0,)
    return (BAB_META.get(prefix, {}).get('order', 99), nums)


def natural_sort_key(code):
    """Sort key for a standard code like ``TKRS 3.1``.

    Splits the code into numeric and textual runs so that the numeric runs
    compare numerically and the textual ones alphabetically.  Plain string
    ordering puts "TKRS 10" before "TKRS 2" and "TKRS 3.1" before "TKRS 3",
    both of which are wrong for the 227 standards of STARKES 2024.
    """
    parts = re.split(r'(\d+)', str(code).strip())
    return [(1, int(p)) if p.isdigit() else (0, p.lower())
            for p in parts if p != '']


def sort_standards(codes):
    """Sort a list of standard codes naturally (see ``natural_sort_key``)."""
    return sorted(codes, key=natural_sort_key)


def classify_line(text, current_prefix):
    """-> ``(kind, codes)`` with kind in ``{'STD', 'EPHD', 'TUJU', None}``."""
    text = re.sub(r'\s+', ' ', text).strip()

    m = TUJU_RE.match(text)
    if m:
        codes = parse_code_tail(m.group(1), current_prefix)
        if codes:
            return 'TUJU', codes

    m = STD_RE.match(text)
    if m:
        codes = parse_code_tail(m.group(1), current_prefix)
        if codes:
            return 'STD', codes

    m = EPHD_RE.match(text)
    if m:
        codes = parse_code_tail(m.group(1), current_prefix)
        if codes:
            return 'EPHD', codes
    return None, []


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------
def _new_ep(letter):
    return {'letter': letter, 'description': '', 'evidence_types': [],
            'evidence_detail': '', 'score': ''}


def parse_document(document):
    """Parse a :class:`Document` into ``{standard_code: [ep, ...]}``.

    Each EP dict carries ``letter``, ``description``, ``evidence_types``,
    ``evidence_detail`` and ``score``.  Standards keep document order.
    """
    pages = document.pages if isinstance(document, Document) else document

    eps = OrderedDict()                # code -> OrderedDict(letter -> ep)
    cur_prefix = None
    cur_code = None
    cur_ep = None

    for page in pages:
        tables = page_tables(page)
        bands = [(t['y0'], t['y1']) for t in tables]

        def in_table(y, _bands=bands):
            for a, b in _bands:
                if a - RULE_TOL <= y <= b + RULE_TOL:
                    return True
            return False

        # Merge prose lines and table bands into one top-to-bottom stream so
        # ownership never depends on which pass sees a line first.
        stream = []
        for (y, _x, text) in page_lines(page):
            if not in_table(y):
                stream.append((y, 0, 'line', text))
        for t in tables:
            for ri in range(len(t['rows']) - 1):
                stream.append((t['rows'][ri], 1, 'band', (t, ri)))
        stream.sort(key=lambda r: (r[0], r[1]))

        for (_y, _pri, kind, payload) in stream:
            if kind == 'line':
                text = payload
                k, codes = classify_line(text, cur_prefix)
                if k:
                    cur_ep = None
                    if k in ('STD', 'EPHD'):
                        cur_prefix, number = codes[0]
                        cur_code = f'{cur_prefix} {number}'
                        eps.setdefault(cur_code, OrderedDict())
                    else:                       # TUJU keeps the current owner
                        for prefix, _number in codes:
                            cur_prefix = prefix
                    continue
                continue

            # ---- table band ------------------------------------------------
            t, ri = payload
            if cur_code is None:
                continue
            cells = _band_cells(page, t, ri)
            if cells is None:
                continue

            _x_desc, x_mark, x_detail, x_score = column_geometry(page, t)
            cols = t['cols']

            desc, mark, detail, score = [], [], [], []
            for i, lines in cells.items():
                if not lines:
                    continue
                left = cols[i]
                if left >= x_score - 1.0:
                    score.extend(lines)
                elif left >= x_detail - 1.0:
                    detail.extend(lines)
                elif left >= x_mark - 1.0:
                    mark.extend(lines)
                else:
                    desc.extend(lines)

            desc_text = _clean(' '.join(desc))
            mark_text = _clean(' '.join(mark))
            if not desc_text and not mark_text and not detail and not score:
                continue
            # A repeated column header continues a table across a page break;
            # it carries no EP data.  The header band also holds the literal
            # "Skoring" label, so detect it by its description text alone.
            if HDR_DESC.match(desc_text):
                continue

            marker = None
            if desc:
                tokens = desc[0].split()
                if tokens and ROW_MARK.fullmatch(tokens[0]):
                    marker = tokens[0][0]
                    desc_text = _clean(' '.join(tokens[1:] + desc[1:]))

            ev_types = [tok for tok in mark_text.split() if EV_MARK.fullmatch(tok)]
            ev_detail_lines = list(detail)
            # Tables that continue on a later page sometimes drop the narrow
            # marker column, leaving the RDWOS letter at the head of the
            # evidence cell ("D 1. Bukti ...").  Recover it there.
            if x_mark == x_detail:
                for li, line in enumerate(ev_detail_lines):
                    toks = line.split()
                    if toks and EV_MARK.fullmatch(toks[0]):
                        ev_types.append(toks[0])
                        ev_detail_lines[li] = ' '.join(toks[1:])
            ev_detail = _clean(' '.join(ev_detail_lines))
            scores = [ln.strip() for ln in score if SCORE_VAL.fullmatch(ln.strip())]

            if marker is not None:
                bucket = eps.setdefault(cur_code, OrderedDict())
                item = bucket.get(marker) or _new_ep(marker)
                bucket[marker] = item
                cur_ep = item
                if desc_text:
                    item['description'] = _clean(item['description'] + ' ' + desc_text)
            elif cur_ep is not None and desc_text:
                cur_ep['description'] = _clean(cur_ep['description'] + ' ' + desc_text)

            if cur_ep is None:
                continue
            if ev_types:
                cur_ep['evidence_types'] = list(dict.fromkeys(
                    cur_ep['evidence_types'] + ev_types))
            if ev_detail:
                cur_ep['evidence_detail'] = _clean(
                    cur_ep['evidence_detail'] + ' ' + ev_detail)
            if scores and not cur_ep['score']:
                cur_ep['score'] = ' '.join(scores)

    out = OrderedDict()
    for code in sorted(eps, key=sort_code_key):
        items = []
        for ep in eps[code].values():
            items.append({
                'letter': ep['letter'],
                'description': _clean(ep['description']),
                'evidence_types': sorted(set(t for t in ep['evidence_types']
                                             if t in EVIDENCE_TYPES)),
                'evidence_detail': _clean(ep['evidence_detail']),
                'score': ep['score'],
            })
        out[code] = items
    return out


def extract_pdf(pdf_path):
    """Parse the instrument PDF into ``{standard_code: [ep, ...]}``."""
    return parse_document(extract_document(pdf_path))


# --------------------------------------------------------------------------
# Fixture format
# --------------------------------------------------------------------------
def build_fixture(standards):
    """Convert parsed standards into the repo's fixture record format."""
    records = []
    for code in sorted(standards, key=sort_code_key):
        parts = code.split()
        prefix = parts[0]
        number = parts[1] if len(parts) > 1 else ''
        eps = standards[code]
        records.append({
            'bab_code': prefix,
            'standard_code': code,
            'standard_num': number,
            'ep_count': len(eps),
            'eps': [{
                'letter': ep['letter'],
                'description': ep['description'],
                'evidence_types': ep['evidence_types'],
            } for ep in eps],
        })
    return records


def dump_fixture(standards, path):
    """Write the fixture JSON (deterministic, sorted)."""
    Path(path).write_text(
        json.dumps(build_fixture(standards), ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8')


# --------------------------------------------------------------------------
# Audit report
# --------------------------------------------------------------------------
FRAGMENT_RE = re.compile(
    r'^(dalam|pada|di |yang |dan |untuk |dengan|seperti|sesuai|menjadi|telah|'
    r'Kebutuhan|Maksud|pengujian)', re.I)
TRAILING_SCORE_RE = re.compile(r'(?:^|\s)(?:10|5|0)(?:\s+(?:10|5|0))*\s*$')
HEADER_LEAK_RE = re.compile(r'(?i)elemen\s+penilaian|kelengkapan\s+bukti|skoring')


def validate(standards):
    """Return an audit report for a parsed document.

    The report is the contract the golden fixture and the import command are
    checked against: it flags empty descriptions, EPs with no evidence type,
    duplicated letters, and the contamination the legacy parser produced
    (score tokens or column headers leaking into a description).
    """
    per_bab = Counter()
    ep_per_bab = Counter()
    empty_desc = []
    no_evidence = []
    fragments = []
    long_desc = []
    duplicate_letters = []
    contaminated = []
    header_leak = []

    for code, eps in standards.items():
        prefix = code.split()[0]
        per_bab[prefix] += 1
        ep_per_bab[prefix] += len(eps)
        letters = [ep['letter'] for ep in eps]
        for letter, count in Counter(letters).items():
            if count > 1:
                duplicate_letters.append((code, letter))
        for ep in eps:
            desc = ep['description'].strip()
            if not desc:
                empty_desc.append((code, ep['letter']))
            elif len(desc) > 900:
                long_desc.append((code, ep['letter'], len(desc)))
            elif len(desc) < 40 and FRAGMENT_RE.match(desc):
                fragments.append((code, ep['letter'], desc))
            if not ep['evidence_types']:
                no_evidence.append((code, ep['letter']))
            if TRAILING_SCORE_RE.search(desc):
                contaminated.append((code, ep['letter'], desc[-40:]))
            if HEADER_LEAK_RE.search(desc):
                header_leak.append((code, ep['letter'], desc[:60]))

    return {
        'standards': len(standards),
        'eps': sum(len(v) for v in standards.values()),
        'per_bab': {b: {'standards': per_bab[b], 'eps': ep_per_bab[b]}
                    for b in BAB_ORDER},
        'empty_description': empty_desc,
        'no_evidence_types': no_evidence,
        'fragment_candidates': fragments,
        'long_description': long_desc,
        'duplicate_letters': duplicate_letters,
        'contaminated_description': contaminated,
        'header_leak': header_leak,
    }
