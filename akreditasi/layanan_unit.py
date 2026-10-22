"""Peta layanan pasien per unit kerja.

Satu-satunya tempat yang menjawab "pasien ini milik unit mana". Dipakai
``kontrol_data`` untuk blok LAYANAN UNIT dan untuk angka EMR, supaya keduanya
tidak bisa memberi jawaban berbeda untuk unit yang sama.

Kenapa perlu peta manual: ``KunjunganPasien`` tidak punya FK ke ``UnitKerja``
dan ``Ruangan`` juga tidak. ``poliklinik`` adalah CharField bebas yang diisi
tiga bentuk berbeda oleh tiga jalur berbeda:

* label ``POLIKLINIK_CHOICES`` — ``kunjungan_form.html`` (bentuk normal);
* kode ``POLI_*`` — sebagian test dan klien lama;
* teks bebas — opsi ``MANUAL_INPUT`` dan seluruh nama bangsal.

Karena itu pencocokan dilakukan pada label yang sudah dinormalkan, bukan pada
kesamaan string. Tidak ada migration di sini; kalau kelak dibutuhkan ketepatan
permanen, tambahkan FK ``KunjunganPasien.unit_layanan``.
"""
import re

# POLIKLINIK_CHOICES (pasien/models.py:200) memakai kode yang tidak selalu sama
# dengan UnitKerja.code — POLI_PENYAKIT_DALAM adalah POLI-PD, bukan
# POLI-PENYAKIT-DALAM. ``None`` berarti poliklinik itu belum punya unit kerja,
# sehingga pasiennya tidak muncul di dasbor unit mana pun. Tambahkan baris di
# sini saat mendaftarkan poliklinik baru.
POLI_UNIT_CODE = {
    'POLI_JANTUNG': 'POLI-JANTUNG',
    'POLI_PARU': 'POLI-PARU',
    'POLI_PENYAKIT_DALAM': 'POLI-PD',
    'POLI_BEDAH': 'POLI-BEDAH',
    'POLI_ANAK': 'POLI-ANAK',
    'POLI_OBGYN': 'POLI-OBGYN',
    'POLI_MATA': 'POLI-MATA',
    'POLI_SARAF': 'POLI-SARAF',
    'POLI_THT': 'POLI-THT',
    'POLI_GIGI': 'POLI-GIGI',
    'POLI_ORTHO': 'POLI-ORTHO',
    'POLI_KULIT': 'POLI-KULIT',
    'POLI_JIWA': 'POLI-JIWA',
    'REHAB_MEDIK': 'REHAB-MEDIK',
    'POLI_ENDOKRIN': 'POLI-ENDOKRIN',
    'POLI_BSARAF': 'POLI-BSARAF',
    'POLI_UMUM': None,
}

# Ruangan fisik → unit kerja pemiliknya. Nama ruangan di ``pasien.Ruangan``
# (Bangsal Mawar, Paviliun Anggrek) tidak pernah sama dengan nama UnitKerja
# (Bangsal Dewasa Non-Bedah, Bangsal Perawatan VIP), jadi pemetaan ini tidak
# bisa diturunkan dari string. Test ``RuanganMappingTest`` gagal kalau ada
# Ruangan yang belum dipetakan.
RUANGAN_UNIT_CODE = {
    'R-K1': 'BANGSAL-DEWASA',
    'R-K2': 'BANGSAL-DEWASA',
    'R-K3': 'BANGSAL-DEWASA',
    'VIP-A': 'BANGSAL-VIP',
    'ICU-01': 'ICU',
    'IGD-01': 'IGD',
    'IGD-02': 'IGD',
    'OK-01': 'IBS',
}

# Alias yang bukan turunan label/kode — teks pendek yang lazim diketik manual.
EXTRA_ALIASES = {
    'IGD': 'IGD',
}

_WS = re.compile(r'[^a-z0-9]+')
_PARENS = re.compile(r'\([^)]*\)')


def normalize_label(value):
    """'Poli Anak (Pediatri)' → 'poli anak'; None → ''."""
    if not value:
        return ''
    text = _PARENS.sub(' ', str(value).lower())
    return ' '.join(_WS.sub(' ', text).split())


def _alias_sources():
    """(alias mentah, UnitKerja.code) untuk seluruh unit aktif."""
    from .models import UnitKerja
    from pasien.models import POLIKLINIK_CHOICES, Ruangan

    codes = set(UnitKerja.objects.filter(is_active=True).values_list('code', flat=True))
    pairs = []

    for code, label in POLIKLINIK_CHOICES:
        target = POLI_UNIT_CODE.get(code)
        if not target or target not in codes:
            continue
        pairs.append((label, target))
        pairs.append((code, target))

    for kode, target in RUANGAN_UNIT_CODE.items():
        if target not in codes:
            continue
        pairs.append((kode, target))
    for nama, kode in Ruangan.objects.filter(
            kode__in=list(RUANGAN_UNIT_CODE)).values_list('nama', 'kode'):
        target = RUANGAN_UNIT_CODE.get(kode)
        if target and target in codes:
            pairs.append((nama, target))

    for alias, target in EXTRA_ALIASES.items():
        if target in codes:
            pairs.append((alias, target))

    for name, code in UnitKerja.objects.filter(
            is_active=True).values_list('name', 'code'):
        pairs.append((name, code))

    return pairs


def alias_index():
    """alias ternormalkan → satu kode unit. Alias ambigu dibuang.

    Tidak di-cache. Pemanggilnya adalah ``build_unit_snapshot`` yang sudah
    di-cache 60 detik, jadi cache di sini tidak menghemat query apa pun dan
    hanya membuat index basi setelah Ruangan/poliklinik baru dibuat — yang
    membuat hasil test bergantung urutan.
    """
    buckets = {}
    for raw, code in _alias_sources():
        key = normalize_label(raw)
        if key:
            buckets.setdefault(key, set()).add(code)

    return {key: next(iter(codes))
            for key, codes in buckets.items() if len(codes) == 1}


def _candidate_keys(poliklinik, ruangan_nama):
    return [k for k in (normalize_label(poliklinik), normalize_label(ruangan_nama)) if k]


def resolve_code(poliklinik, ruangan_nama, index):
    """Kode unit untuk satu kunjungan, atau ``None`` bila tidak dikenali.

    Exact match menang; kalau tidak ada, alias terpanjang yang menjadi awalan
    salah satu kandidat yang dipakai — itu yang memisahkan 'Poli Bedah Saraf'
    (POLI-BSARAF) dari 'Poli Bedah Umum' (POLI-BEDAH).
    """
    keys = _candidate_keys(poliklinik, ruangan_nama)
    for key in keys:
        hit = index.get(key)
        if hit:
            return hit

    best, best_len = None, 0
    for key in keys:
        for alias, code in index.items():
            if key.startswith(alias + ' ') or alias.startswith(key + ' '):
                if len(alias) > best_len:
                    best, best_len = code, len(alias)
    return best


def visit_unit_code(kunjungan, index):
    bed = getattr(kunjungan, 'bed', None)
    ruangan_nama = bed.ruangan.nama if bed is not None else None
    return resolve_code(kunjungan.poliklinik, ruangan_nama, index)


def unit_codes(unit):
    """Kode unit ini + seluruh turunannya. Tidak pernah ke atas.

    Arah ke bawah saja: kepala Poliklinik Jantung tidak boleh melihat pasien
    Instalasi Rawat Jalan, sementara kepala IRJ memang harus melihat seluruh
    poliklinik di bawahnya.
    """
    from .models import UnitKerja

    if unit is None:
        return set()
    codes = {unit.code}
    frontier = {unit.pk}
    seen = {unit.pk}
    while frontier:
        frontier = set(
            UnitKerja.objects.filter(parent_id__in=frontier)
            .values_list('pk', flat=True)
        ) - seen
        if not frontier:
            break
        seen |= frontier
        codes |= set(
            UnitKerja.objects.filter(pk__in=frontier)
            .values_list('code', flat=True)
        )
    return codes


def resolve_visit_ids(visits_qs, unit):
    """PK kunjungan yang menjadi layanan ``unit`` (atau turunannya)."""
    codes = unit_codes(unit)
    if not codes:
        return []
    index = alias_index()
    rows = visits_qs.values_list('pk', 'poliklinik', 'bed__ruangan__nama')
    return [
        pk for pk, poliklinik, ruangan in rows
        if resolve_code(poliklinik, ruangan, index) in codes
    ]


def service_codes():
    """Kode unit yang benar-benar melayani pasien.

    Sengaja TIDAK memakai ``alias_index().values()``: index itu juga memuat nama
    setiap UnitKerja, sehingga komite dan bagian administratif akan ikut
    dianggap punya layanan. Yang dihitung hanya unit yang muncul di
    ``POLI_UNIT_CODE`` atau ``RUANGAN_UNIT_CODE``.
    """
    return {c for c in POLI_UNIT_CODE.values() if c} | set(RUANGAN_UNIT_CODE.values())


def unit_owns_beds(unit, codes=None):
    """True bila unit (atau turunannya) memiliki ruangan ber-bed."""
    codes = unit_codes(unit) if codes is None else codes
    if not codes:
        return False
    from pasien.models import Ruangan
    kode_ruangan = [k for k, v in RUANGAN_UNIT_CODE.items() if v in codes]
    return Ruangan.objects.filter(kode__in=kode_ruangan).exists()
