"""Sinkronisasi Indikator Mutu <-> Elemen Penilaian (EP) <-> Dokumen Bukti.

Dua mekanisme, sengaja dipisah:

* **Tier A — rule boost.** `UnitKerja.standar_terkait` sudah memetakan tiap unit ke
  sub-standar (``{"HPK": ["HPK 1", "HPK 4"]}``). Dipakai sebagai *bobot*, bukan
  filter keras: pemetaan itu hanya menutup 39 dari 138 indikator yang belum
  tertaut, dan median kandidatnya 114 EP — terlalu lebar untuk jadi gerbang.
  Kunci pokja yang sudah basi (mis. ``ARK``, ``IPKP``) diabaikan, bukan error.

* **Tier B — prefilter lexical.** Skor kata murni-Python di atas seluruh katalog
  EP (1053 baris) menjadi top-k. Tanpa dependency baru dan tanpa fitur
  khusus Postgres, karena DB bisa SQLite.

Tier C (DeepSeek re-rank) ada di :mod:`akreditasi.ai_service`.
"""

import re
from django.db.models import Count, Max

_TOKEN_RE = re.compile(r'[a-z0-9]+')

_STOPWORDS = frozenset(
    'yang dan di ke dari untuk pada dengan adalah ini itu tidak ada dalam oleh '
    'per saat lebih dapat dilakukan secara serta atau juga karena antar yaitu '
    'harus para seluruh setiap sebelum sesudah hingga agar namun bagi menjadi '
    'no umur laki laki-laki perempuan pasien rs unit tahun bulan hari jumlah '
    'angka nilai hasil target standar indikator rumah sakit'.split()
)

# Singkatan klinis yang berulang di data indikator RS. Sengaja kecil: peta
# sinonim yang terlalu besar malah menambah bobot pada kata yang salah.
_SINONIM = {
    'ecg': 'elektrokardiografi', 'ekg': 'elektrokardiografi',
    'igd': 'gawat darurat', 'er': 'gawat darurat',
    'icu': 'perawatan intensif', 'iccu': 'perawatan intensif',
    'hcu': 'perawatan intensif',
    'vap': 'ventilator', 'clabsi': 'kateter', 'isk': 'kemih',
    'dekubitus': 'luka tekan', 'decubitus': 'luka tekan',
    'lama': 'rawat', 'rawatinap': 'rawat inap',
    'hand': 'tangan', 'higiene': 'tangan', 'hygiene': 'tangan',
    'praoperasi': 'pra bedah', 'preoperasi': 'pra bedah',
    'tindakan': 'prosedur',
}


def _expand(tokens: set) -> set:
    """Tambahkan sinonim sebagai token ekstra (token asli tetap dipertahankan)."""
    extra = set()
    for t in tokens:
        s = _SINONIM.get(t)
        if s:
            extra.update(_TOKEN_RE.findall(s))
    return tokens | extra


def normalize_str(text: str) -> str:
    """Lowercase + strip tanda baca + rapikan spasi. Untuk pencocokan frasa."""
    if not text:
        return ''
    return ' '.join(_TOKEN_RE.findall(str(text).lower()))


def normalize(text: str) -> set:
    """Set token siap-pakai: huruf kecil, tanpa tanda baca, tanpa stopword.

    Token tunggal karakter dan angka murni dibuang (tahun, nomor register)
    karena menimpa skor tanpa membawa makna.
    """
    if not text:
        return set()
    raw = _TOKEN_RE.findall(str(text).lower())
    return {t for t in raw if len(t) > 1 and t not in _STOPWORDS and not t.isdigit()}


# ── indeks EP (lazy, tervalidasi fingerprint) ────────────────────────────────

_EP_INDEX = None
_EP_FINGERPRINT = None
_IDF = {}          # token -> bobot informasi (diisi saat build index)
_VOCAB = set()     # seluruh token yang pernah muncul di katalog EP


def _current_fingerprint() -> tuple:
    from .models import StandardItem
    agg = StandardItem.objects.aggregate(n=Count('id'), mx=Max('id'))
    return (agg['n'] or 0, agg['mx'] or 0)


def _build_index() -> list:
    from .models import StandardItem
    rows = StandardItem.objects.select_related('category').order_by('id')
    index = []
    for s in rows:
        cat = s.category
        index.append({
            'id': s.id,
            'code': s.code,
            'sub_standard': s.sub_standard or '',
            'sub_title': s.sub_title or '',
            'description': s.description or '',
            'desc_lower': (s.description or '').lower(),
            'cat_id': cat.id if cat else None,
            'cat_code': cat.code if cat else '',
            'cat_name': cat.name if cat else '',
            'kelompok': cat.kelompok if cat else '',
            'tok_desc': normalize(s.description or ''),
            'tok_title': normalize(s.sub_title or ''),
            'tok_code': normalize(f'{s.code} {s.sub_standard}'),
            'tok_cat': normalize(f'{cat.code if cat else ""} {cat.name if cat else ""} '
                                 f'{cat.kelompok if cat else ""}'),
        })

    # IDF: token yang muncul di banyak EP ("pasien", "mutu") nyaris tak
    # berguna membedakan; token langka ("hepatitis", "serokonversi") sangat
    # berguna. Tanpa ini, indikator bernama klinis tak pernah menembus ranking.
    import math
    from collections import Counter
    df = Counter()
    for e in index:
        df.update(e['tok_desc'] | e['tok_title'] | e['tok_code'] | e['tok_cat'])
    n = max(len(index), 1)
    idf = {t: math.log(n / c) + 1.0 for t, c in df.items() if c > 0}
    _IDF.clear()
    _IDF.update(idf)
    _VOCAB.clear()
    _VOCAB.update(df.keys())
    return index


def get_ep_index() -> list:
    """Indeks EP siap-skor. Fingerprint COUNT+MAX memastikan tidak basi.

    Satu query murah per panggilan, dan membuat cache otomatis tervalidasi di
    test yang memakai transaksi terpisah.
    """
    global _EP_INDEX, _EP_FINGERPRINT
    fp = _current_fingerprint()
    if _EP_INDEX is None or _EP_FINGERPRINT != fp:
        _EP_INDEX = _build_index()
        _EP_FINGERPRINT = fp
    return _EP_INDEX


def clear_ep_index() -> None:
    """Panggil dari test setup bila fixture EP di-seed ulang."""
    global _EP_INDEX, _EP_FINGERPRINT
    _EP_INDEX = None
    _EP_FINGERPRINT = None


# ── Tier A: rule boost dari unit ─────────────────────────────────────────────

def rule_boost_map(unit) -> dict:
    """``{pokja_code: set(sub_standards)}`` milik unit, sudah bersih.

    Kunci pokja yang tidak dikenal dan sub-standard yang tidak ada di katalog
    dibuang diam-diam — pemetaan historis memuat ``ARK``/``IPKP`` yang sudah
    tidak ada, dan itu bukan alasan untuk gagal.
    """
    if unit is None:
        return {}
    from .models import StandardItem
    valid = set(StandardItem.objects.values_list('sub_standard', flat=True))
    out = {}
    for key, values in (getattr(unit, 'standar_terkait', None) or {}).items():
        keep = {s for s in (values or []) if s in valid}
        if keep:
            out[key] = keep
    return out


def boost_sets(unit) -> tuple:
    """(set semua sub-standard unit, set kode pokja unit) — sekali query."""
    m = rule_boost_map(unit)
    subs = set()
    for values in m.values():
        subs |= values
    return subs, set(m.keys())


# ── Tier B: skoring ──────────────────────────────────────────────────────────

_WEIGHT_CODE = 2.0
_WEIGHT_TITLE = 1.5
_WEIGHT_DESC = 1.0
_WEIGHT_CAT = 0.75
_BOOST_SUBSTANDARD = 0.25
_BOOST_CATEGORY = 0.10
_BOOST_PHRASE = 0.30


def _coverage(tokens: set) -> float:
    """Berapa banyak token indikator yang benar-benar ada di kosakata EP.

    Konstanta per indikator (tidak memengaruhi urutan antar EP), tapi membuat
    skor absolut antar-indikator bisa dibandingkan: indikator yang kosakatanya
    asing bagi katalog tidak boleh mendapat skor setinggi yang kita pahami.
    """
    if not tokens:
        return 0.0
    return len(tokens & _VOCAB) / len(tokens)


def score_entry(entry: dict, tokens: set, name_str: str,
                unit_subs: set, unit_cats: set, coverage: float = 1.0) -> float:
    """Skor kecocokan satu EP terhadap token indikator, ter-clamp di [0, 1].

    Berbobot IDF: pembilang memakai bobot informasi tiap token yang cocok,
    penyebut memakai total bobot seluruh token indikator. Token di luar
    kosakata EP tidak menambah penyebut, sehingga tidak menekan skor secara
    artifisial.
    """
    if not tokens:
        return 0.0
    num = 0.0
    den = 0.0
    for t in tokens:
        w = _IDF.get(t, 0.0)
        den += w
        if t in entry['tok_code']:
            num += w * _WEIGHT_CODE
        elif t in entry['tok_title']:
            num += w * _WEIGHT_TITLE
        elif t in entry['tok_desc']:
            num += w * _WEIGHT_DESC
        elif t in entry['tok_cat']:
            num += w * _WEIGHT_CAT
    if den <= 0:
        return 0.0
    score = (num / den) * coverage

    if entry['sub_standard'] and entry['sub_standard'] in unit_subs:
        score += _BOOST_SUBSTANDARD
    elif entry['cat_code'] and entry['cat_code'] in unit_cats:
        score += _BOOST_CATEGORY

    if name_str and len(name_str) >= 12 and name_str in entry['desc_lower']:
        score += _BOOST_PHRASE

    return min(score, 1.0)


def indicator_tokens(ind) -> set:
    """Token indikator: nama + numerator + denominator + nama unit."""
    parts = [getattr(ind, 'nama_indikator', ''), getattr(ind, 'numerator', ''),
             getattr(ind, 'denominator', '')]
    unit = getattr(ind, 'unit', None)
    if unit is not None:
        parts.append(unit.name)
    return _expand(normalize(' '.join(p for p in parts if p)))


def prefilter_candidates(ind, top_k: int = 40) -> list:
    """Ranking EP untuk satu indikator. Return ``[{entry..., 'skor': f,
    'dari_unit': bool}]`` sepanjang ``top_k``, terurut menurun.

    Tidak bergantung pada unit: indikator tanpa unit tetap mendapat kandidat.
    """
    tokens = indicator_tokens(ind)
    name_str = normalize_str(getattr(ind, 'nama_indikator', ''))
    unit = getattr(ind, 'unit', None)
    unit_subs, unit_cats = boost_sets(unit)
    cov = _coverage(tokens)

    scored = []
    for entry in get_ep_index():
        s = score_entry(entry, tokens, name_str, unit_subs, unit_cats, cov)
        if s > 0:
            entry['_skor'] = s
            entry['_dari_unit'] = bool(
                entry['sub_standard'] and entry['sub_standard'] in unit_subs)
            scored.append(entry)
    scored.sort(key=lambda e: (-e['_skor'], e['code']))
    top = scored[:top_k]

    if not top:
        return []

    from .models import StandardItem
    order = [e['id'] for e in top]
    objs = {s.id: s for s in StandardItem.objects.select_related('category')
            .filter(id__in=order)}

    out = []
    for e in top:
        obj = objs.get(e['id'])
        if obj is None:
            continue
        out.append({
            'ep': obj,
            'code': e['code'],
            'skor': e['_skor'],
            'dari_unit': e['_dari_unit'],
            'pokja': e['cat_code'],
            'pokja_nama': e['cat_name'],
            'deskripsi': e['description'],
            'sub_title': e['sub_title'],
        })
    return out


def lexical_top(ind, n: int = 5) -> list:
    """Fallback Tier B murni — dipakai saat DeepSeek gagal/tidak aktif."""
    return prefilter_candidates(ind, top_k=n)


# ── katalog untuk Tier C (satu panggilan AI) ────────────────────────────────

# 90 karakter deskripsi: terukur 111 KB (~32k token) untuk 1053 EP, masih
# lega di bawah konteks deepseek-chat 64k bahkan dengan perkiraan token
# paling boros (~2.5 karakter/token -> ~45k). 120 karakter dipakai bila
# dinaikkan harus diperiksa ulang terhadap batas konteks.
EP_TEXT_CHARS = 90


def build_ep_catalog(max_chars: int = EP_TEXT_CHARS) -> tuple:
    """``(baris, set_kode, jumlah)`` untuk disuntik ke prompt Tier C.

    Format per baris: ``KODE | POKJA | BUNYI EP``. Kode dipertahankan utuh dan
    jadi satu-satunya cara membalas, sehingga validasi anti-halusinasi bisa
    membandingkan balasan model terhadap ``set_kode`` asli.
    """
    lines = []
    codes = set()
    for e in get_ep_index():
        text = ' '.join((e['sub_title'], e['description'])).strip() or e['description']
        text = ' '.join(text.split())[:max_chars]
        lines.append(f"{e['code']} | {e['cat_code']} | {text}")
        codes.add(e['code'])
    return lines, codes, len(lines)


def resolve_ep_by_code(code: str):
    """``StandardItem`` untuk kode yang dipilih AI, atau ``None`` bila tidak ada.

    Kode yang balasan AI sudah lolos validasi katalog di
    :func:`akreditasi.ai_service.generate_ep_rekomendasi`; fungsi ini dipakai
    lagi untuk memastikan kita tidak menulis tautan ke baris yang tidak ada.
    """
    from .models import StandardItem
    code = (code or '').strip()
    if not code:
        return None
    return StandardItem.objects.filter(code=code).first()


# ── dokumen bukti untuk EP terpilih (Tier: leg dokumen) ──────────────────────

def bukti_ringkas(ep) -> dict:
    """Ringkasan ``EvidenceReq`` untuk satu EP, termasuk jumlah berkas terunggah.

    ``None`` bila EP kosong, supaya template bisa guard sekali.
    """
    if ep is None:
        return None
    from .models import EvidenceReq
    reqs = (EvidenceReq.objects.filter(standard_item=ep)
            .annotate(terunggah=Count('files'))
            .order_by('category_type', 'id'))
    items = [{
        'id': r.id,
        'category_type': r.category_type,
        'title': r.title,
        'is_mandatory': r.is_mandatory,
        'terunggah': r.terunggah or 0,
    } for r in reqs]
    return {
        'total': len(items),
        'wajib': sum(1 for i in items if i['is_mandatory']),
        'terunggah': sum(1 for i in items if i['terunggah']),
        'reqs': items,
    }
