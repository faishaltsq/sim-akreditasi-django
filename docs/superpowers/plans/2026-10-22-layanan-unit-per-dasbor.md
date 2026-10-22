# Layanan Unit per Dasbor (ARIMA Control) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic patient-module strip at the bottom of every ARIMA Control sub-dashboard with a unit-scoped `LAYANAN UNIT` menu that lists *today's* patients belonging to the dashboard's own unit, and make the underlying numbers on those dashboards actually reflect that unit.

**Architecture:** One new pure-function module, `akreditasi/layanan_unit.py`, owns the only answer to "which unit does this visit belong to" — it maps `KunjunganPasien.poliklinik` (free text) and `KunjunganPasien.bed.ruangan` to a `UnitKerja` code through a normalised alias index. `akreditasi/kontrol_data.py` gains a `layanan` block inside the existing cached snapshot, and `_emr_block` is switched from its broken `UserProfile.unit_kerja__name` join to that same resolver. Templates render the block from the snapshot; a new page `/control/layanan/` renders the full day list. No new model, no migration.

**Tech Stack:** Django 6.1.1 (`.venv`), SQLite (dev) / Postgres via Supabase (prod), Bootstrap 5.3, the existing `kontrol.css` dark shell.

**Spec:** `C:\Users\cubeb\Downloads\perbaikan akses unit 22 10.docx` — 6 lines of body text plus one screenshot (`word/media/image1.png`). Verbatim asks:

1. `Masalah: menu kiri bawah ada; daftar kunjungan, IGD, Rawat jalan, Rekap kps dihilangkan`
2. `Tambahkan menu: sesuai dengan layanan unit masing-masing, beri judul; LAYANAN UNIT: Polijantung dan pembuluh darah—lalu masuk ke: Daftar layanan pasien hari ini (tanggal/bulan/tahun)`
3. `buatkan semua dasbor begitu (layanan yang muncul sesuai unit masing-masing)`

The screenshot is `/control/emr/?unit=141` — the Poliklinik Jantung & Pembuluh Darah EMR sub-dashboard — and shows the button row this plan removes: `Daftar kunjungan · IGD · Rawat jalan · Bed management · Rekap KPS`.

## Root Cause Analysis

The docx states a symptom, not a cause. Three separate defects sit behind it, all confirmed against the running code and test database.

**Defect 1 — the strip is hardcoded, not unit-aware.** `templates/akreditasi/kontrol/emr.html:79-85` renders five fixed links with no reference to `snapshot.unit`. Every unit's EMR dashboard shows the same five, including `IGD` on a poliklinik dashboard and `Rekap KPS` for roles that are rejected by that view. Probe (`rekap_kps` per role):

```
PROBE POLI-JANTUNG KEPALA_UNIT: {..., 'akreditasi:rekap_kps': 200}
PROBE POLI-JANTUNG STAF_NAKES:  {..., 'akreditasi:rekap_kps': 403}
```

So the strip renders a link that 403s for the majority of users who see it.

**Defect 2 — the EMR numbers on that page are computed against a join that can never match.** `akreditasi/kontrol_data.py:191-197` resolves a unit's visits by collecting `UserProfile.unit_kerja__name` and filtering `poliklinik__in=names`. But `KunjunganPasien.poliklinik` is written from `POLIKLINIK_CHOICES` **labels** (`pasien/models.py:200-217`, submitted by `kunjungan_form.html:101-103`), while `UnitKerja.name` is a different string. The two never meet:

```
PROBE-A no profile          -> 2 active visits
PROBE-B with profile        -> 0 active visits
PROBE-C names used for matching -> ['Poliklinik Jantung & Pembuluh Darah']
PROBE-E exact-name match count  -> 0
```

`'Poli Jantung & Pembuluh Darah'` (stored) vs `'Poliklinik Jantung & Pembuluh Darah'` (unit name). Worse, the filter is *conditional on staff existing*: the moment a head of unit is assigned, the block silently drops to zero. That is exactly the screenshot — `KUNJUNGAN AKTIF 0` while the footer says `Unit: Poliklinik Jantung & Pembuluh Darah`.

**Defect 3 — no unit↔service mapping exists in the data model.** `KunjunganPasien` has no FK to `UnitKerja`; `Ruangan` has none either. `poliklinik` is `CharField(max_length=100)` and is also freely typed (`kunjungan_form.html:104` `MANUAL_INPUT`, and `tests_revisi_pendaftaran_dua_kotak.py:160` posts the *code* `POLI_PENYAKIT_DALAM`). Any resolver must therefore handle three stored shapes for the same poli: label, code, and free text. Probe of the naive code→slug assumption:

```
POLI_PENYAKIT_DALAM -> POLI-PENYAKIT-DALAM  MISS   (real code is POLI-PD)
POLI_UMUM           -> POLI-UMUM            MISS   (no such unit)
```

A normalised-alias resolver handles all three. Probe of the resolver this plan specifies:

```
resolve 'Poli Jantung & Pembuluh Darah' -> POLI-JANTUNG
resolve 'POLI_PENYAKIT_DALAM'           -> POLI-PD
resolve 'IGD'                           -> IGD
resolve 'Poli Bedah Umum'               -> POLI-BEDAH
resolve 'Poli Bedah Saraf'              -> POLI-BSARAF   (longest-alias wins over POLI-BEDAH)
```

## What the docx asks for, and what already exists

| docx requirement | Existing equivalent | Verdict |
|---|---|---|
| Remove `daftar kunjungan, IGD, Rawat jalan, Rekap kps` from the bottom menu | `kontrol-modlinks` strip, `emr.html:79-85` | **Delete the block.** The docx names four of five links; `Bed management` is the fifth and equally RS-wide — see Decision 1. |
| `LAYANAN UNIT` heading + unit name | `snapshot.unit.name` already in context | **Reuse.** |
| `Daftar layanan pasien hari ini (tanggal/bulan/tahun)` | `pasien:kunjungan_daftar` exists but is RS-wide and unbounded | **New page** in the kontrol shell; the old one stays untouched. |
| "layanan yang muncul sesuai unit masing-masing" | Nothing. `_emr_block`'s join is broken (Defect 2) | **New resolver** + fix the join. |
| "buatkan semua dasbor begitu" | 3 sub-dashboards: `emr`, `risiko`, `dokumen` | **Shared include** in all three. |
| Unit switch, no sidebar | `_unit_switch.html`, `base_kontrol.html` | **Reuse unchanged.** |

## Global Constraints

- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.** (Standing project rule.)
- **Do not extend `base.html`, and do not add a "hide sidebar" flag to it.** The kontrol shell is standalone by design; `tests_kontrol_dasbor.py:44-47` asserts `sidebar-desktop` and `id="mobileSidebar"` are absent from these pages and must keep passing.
- **`akreditasi/views.py` must not grow.** New views go in `kontrol_views.py`; only URL wiring and templates touch existing files.
- **Empty is not zero.** A unit with no mapped service renders an explanatory sentence, never `0 pasien` as if it had been measured. Same rule as `kontrol_data.py:277-278`.
- **Scope resolution is imported, not re-implemented.** Use `akreditasi/akses_indikator.py::unit_scope_ids()` for indicator/risk scope. The new `layanan_unit` module needs *descendants only* and must expose its own walk — do not reuse `unit_scope_ids` for it (that one deliberately includes two ancestor levels, which would put a poli's parent installation's patients on the poli dashboard).
- **`UserProfile.is_unit_scoped` is a read-only property**, not a field. `_resolve_unit` (`kontrol_views.py:56-71`) already forces unit-scoped users onto their own unit; every new view must go through it.
- **Query budget stays at 12 warm queries** (`tests_kontrol_dasbor.py:106` `BUDGET = 12`). The layanan block lives inside the cached snapshot, so warm requests add zero queries.
- **No migration in this plan.** If a task seems to need one, the design is wrong — stop and raise it. The durable fix (an FK) is listed under "Explicitly NOT in this plan".
- **`staticfiles/` is intentionally tracked for the Vercel build.** After any CSS change run `collectstatic` and commit the hashed artifacts + `staticfiles.json`. Never delete that directory.
- **`LANGUAGE_CODE = 'id'`, `TIME_ZONE = 'Asia/Jakarta'`, `USE_TZ = True`** (`config/settings.py:164-167`). Use `timezone.localdate()`, never `date.today()`, for "today". Verified rendering: `{{ d|date:"l, j F Y" }}` → `Kamis, 22 Oktober 2026`.

## Review Focus

Five input classes the docx implies but never states. Each gets a test in the task that owns the code.

1. **A unit whose staff exist but whose patients are stored as free text.** The exact shape of Defect 2 — the case that produces `0` on the screenshot. Pinned in Task 2.
2. **A unit that owns no clinical service at all** (`KOMITE-MUTU`, `SPI`, `BAG-IT`). The block must say so, not render an empty list that reads as "no patients today". Pinned in Task 4.
3. **A visit stored as a `POLIKLINIK_CHOICES` code instead of its label** — a real state produced by `tests_revisi_pendaftaran_dua_kotak.py:160`. Pinned in Task 1.
4. **A visit that is still open across midnight** (status `RANAP` with `tanggal_masuk` two days ago). "Hari ini" must mean *admitted today*, not *currently open*, or a long-stay ward shows its whole census as today's arrivals. Pinned in Task 2.
5. **A parent unit** (`IRJ`, `POLI-PD`, `IRIN`) whose own `poliklinik` never appears on any visit. Its list must aggregate descendants — a downward walk, not an upward one. Pinned in Task 1.

## File Structure

| Path | Responsibility |
|---|---|
| `akreditasi/layanan_unit.py` | **Create.** Alias index, unit→codes walk, visit→unit resolution. Pure functions + a cache wrapper. No rendering, no requests. |
| `akreditasi/kontrol_data.py` | **Modify.** Add `layanan` block to `build_unit_snapshot`; replace `_emr_block`'s name join with the resolver. |
| `akreditasi/kontrol_views.py` | **Modify.** Add `kontrol_layanan` view; expose `layanan_url` in `_common_context`. |
| `akreditasi/urls.py` | **Modify.** One route. |
| `templates/akreditasi/kontrol/_layanan_unit.html` | **Create.** The titled block, included by all three sub-dashboards. |
| `templates/akreditasi/kontrol/layanan.html` | **Create.** The day list page. |
| `templates/akreditasi/kontrol/emr.html` | **Modify.** Delete `kontrol-modlinks`; include the new block. |
| `templates/akreditasi/kontrol/risiko.html` | **Modify.** Include the new block. |
| `templates/akreditasi/kontrol/dokumen.html` | **Modify.** Include the new block. |
| `static/css/kontrol.css` | **Modify.** `.kontrol-layanan*` rules. |
| `akreditasi/tests_layanan_unit.py` | **Create.** Resolver + snapshot + view tests. |

## Decision 1 — the fifth link

The docx names four links to remove. `Bed management` is the fifth in the same `<section>`. This plan removes the whole section, because a block whose purpose was "generic RS modules" is not repaired by leaving one generic module in it. Where a unit genuinely owns beds, `Bed & okupansi` reappears **inside** the new `LAYANAN UNIT` block (Task 4), driven by `RUANGAN_UNIT_CODE` rather than by a hardcoded template string. If you want `Bed management` kept as a permanent standalone button, say so before Task 4 runs — it is a one-line revert.

---

## Task 1: Unit-service resolver

**Files:**
- Create: `akreditasi/layanan_unit.py`
- Test: `akreditasi/tests_layanan_unit.py`

**Interfaces:**
- Consumes: `akreditasi.models.UnitKerja`, `pasien.models.POLIKLINIK_CHOICES`, `pasien.models.Ruangan`.
- Produces:
  - `POLI_UNIT_CODE: dict[str, str | None]`
  - `RUANGAN_UNIT_CODE: dict[str, str]`
  - `normalize_label(value: str | None) -> str`
  - `alias_index() -> dict[str, str]` (normalised alias → single `UnitKerja.code`; ambiguous aliases omitted)
  - `unit_codes(unit) -> set[str]` (the unit plus all descendants)
  - `resolve_code(poliklinik: str | None, ruangan_nama: str | None, index: dict[str, str]) -> str | None`
  - `visit_unit_code(kunjungan, index) -> str | None`
  - `resolve_visit_ids(visits_qs, unit) -> list[int]`

- [ ] **Step 1: Write the failing tests**

```python
"""Peta layanan pasien per unit — resolver dan blok snapshot."""
from django.test import TestCase
from django.utils import timezone

from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien, Ruangan


def _pasien(no_rm='RM-L1'):
    return Pasien.objects.create(
        no_rm=no_rm, nama_lengkap='Pasien Uji',
        tanggal_lahir='1980-01-01', jenis_kelamin='L')


def _unit(code, name, level=3, parent=None):
    unit, _ = UnitKerja.objects.get_or_create(
        code=code, defaults={'name': name, 'level': level, 'parent': parent})
    return unit


class NormalizeLabelTest(TestCase):
    def test_strips_case_punctuation_and_parenthetical(self):
        from akreditasi.layanan_unit import normalize_label
        self.assertEqual(
            normalize_label('Poli Anak (Pediatri)'), 'poli anak')
        self.assertEqual(
            normalize_label('POLI_PENYAKIT_DALAM'), 'poli penyakit dalam')
        self.assertEqual(
            normalize_label('Poli Jantung & Pembuluh Darah'),
            'poli jantung pembuluh darah')

    def test_empty_is_empty(self):
        from akreditasi.layanan_unit import normalize_label
        self.assertEqual(normalize_label(None), '')
        self.assertEqual(normalize_label(''), '')


class ResolveCodeTest(TestCase):
    def setUp(self):
        _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3)
        _unit('POLI-BEDAH', 'Poliklinik Bedah (Umum, Orthopedi, Bedah Saraf)', 3)
        _unit('POLI-BSARAF', 'Poliklinik Bedah Saraf', 4)
        _unit('IGD', 'Instalasi Gawat Darurat (IGD 24 Jam & PONEK)', 3)

    def test_resolves_stored_label(self):
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertEqual(
            resolve_code('Poli Jantung & Pembuluh Darah', None, idx),
            'POLI-JANTUNG')

    def test_resolves_choice_code(self):
        """Formulir dan test lama menyimpan kode, bukan label."""
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertEqual(
            resolve_code('POLI_PENYAKIT_DALAM', None, idx), 'POLI-PD')

    def test_longest_alias_wins(self):
        """'Poli Bedah Saraf' tidak boleh jatuh ke POLI-BEDAH."""
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertEqual(resolve_code('Poli Bedah Saraf', None, idx), 'POLI-BSARAF')
        self.assertEqual(resolve_code('Poli Bedah Umum', None, idx), 'POLI-BEDAH')

    def test_unknown_text_resolves_to_none(self):
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertIsNone(resolve_code('Ruang Entah', None, idx))
        self.assertIsNone(resolve_code('', None, idx))

    def test_igd_short_text(self):
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertEqual(resolve_code('IGD', None, idx), 'IGD')


class UnitCodesTest(TestCase):
    def test_parent_includes_descendants_not_ancestors(self):
        irj = _unit('IRJ', 'Instalasi Rawat Jalan (IRJ)', 2)
        pd = _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3, parent=irj)
        jantung = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4, parent=pd)

        from akreditasi.layanan_unit import unit_codes
        self.assertIn('POLI-JANTUNG', unit_codes(pd))
        self.assertIn('POLI-JANTUNG', unit_codes(irj))
        self.assertIn('POLI-PD', unit_codes(irj))
        # downward only: a poli must not inherit its installation's patients
        self.assertNotIn('IRJ', unit_codes(pd))
        self.assertEqual(unit_codes(jantung), {'POLI-JANTUNG'})


class ResolveVisitIdsTest(TestCase):
    def setUp(self):
        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.pasien = _pasien()
        self.mine = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-MINE', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(), status='DAFTAR')
        self.other = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-OTHER', jenis_kunjungan='RAJAL',
            poliklinik='Poli Penyakit Dalam',
            tanggal_masuk=timezone.now(), status='DAFTAR')

    def test_only_matching_visits_returned(self):
        from akreditasi.layanan_unit import resolve_visit_ids
        ids = resolve_visit_ids(KunjunganPasien.objects.all(), self.unit)
        self.assertEqual(ids, [self.mine.pk])

    def test_ruangan_match_for_inpatient(self):
        from akreditasi.layanan_unit import resolve_visit_ids
        bangsal = _unit('BANGSAL-DEWASA', 'Bangsal Dewasa Non-Bedah', 3)
        ruang = Ruangan.objects.create(
            kode='R-K1', nama='Bangsal Mawar (Kelas I)', kelas='1',
            jenis='RANAP', kapasitas=1)
        dari_bed = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-BED', jenis_kunjungan='RANAP',
            poliklinik='Bangsal Mawar', bed=None,
            tanggal_masuk=timezone.now(), status='RANAP')
        from pasien.models import Bed
        bed = Bed.objects.create(ruangan=ruang, kode_bed='B1', status='TERISI')
        dari_bed.bed = bed
        dari_bed.save(update_fields=['bed'])

        ids = resolve_visit_ids(KunjunganPasien.objects.all(), bangsal)
        self.assertEqual(ids, [dari_bed.pk])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_unit -v 1`
Expected: FAIL — `ModuleNotFoundError: No module named 'akreditasi.layanan_unit'`

- [ ] **Step 3: Write the resolver**

```python
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
```

- [ ] **Step 4: Add the Ruangan mapping gate test**

Append to `akreditasi/tests_layanan_unit.py`:

```python
class RuanganMappingTest(TestCase):
    def test_every_ruangan_has_a_unit(self):
        """Ruangan baru tanpa entri RUANGAN_UNIT_CODE tidak muncul di dasbor."""
        from akreditasi.layanan_unit import RUANGAN_UNIT_CODE
        from akreditasi.models import UnitKerja

        _unit('BANGSAL-DEWASA', 'Bangsal Dewasa Non-Bedah', 3)
        _unit('BANGSAL-VIP', 'Bangsal Perawatan VIP / Super VIP', 3)
        _unit('ICU', 'Instalasi Rawat Intensif Terpadu (ICU & HCU)', 3)
        _unit('IGD', 'Instalasi Gawat Darurat (IGD 24 Jam & PONEK)', 3)
        _unit('IBS', 'Instalasi Bedah Sentral (Kamar Operasi / OK)', 3)

        for kode, nama, jenis in (
            ('R-K1', 'Bangsal Mawar (Kelas I)', 'RANAP'),
            ('R-K2', 'Bangsal Melati (Kelas II)', 'RANAP'),
            ('R-K3', 'Bangsal Dahlia (Kelas III)', 'RANAP'),
            ('VIP-A', 'Paviliun Anggrek VIP', 'RANAP'),
            ('ICU-01', 'Intensive Care Unit (ICU)', 'ICU'),
            ('IGD-01', 'Ruang Resusitasi & Triase IGD', 'IGD'),
            ('IGD-02', 'Ruang Observasi IGD', 'IGD'),
            ('OK-01', 'Kamar Bedah Sentral', 'OK'),
        ):
            Ruangan.objects.create(
                kode=kode, nama=nama, kelas='1', jenis=jenis, kapasitas=1)

        known = set(UnitKerja.objects.values_list('code', flat=True))
        for ruang in Ruangan.objects.all():
            with self.subTest(ruangan=ruang.kode):
                self.assertIn(
                    ruang.kode, RUANGAN_UNIT_CODE,
                    f'Ruangan {ruang.kode} belum dipetakan ke unit kerja — '
                    f'tambahkan ke RUANGAN_UNIT_CODE di akreditasi/layanan_unit.py')
                self.assertIn(RUANGAN_UNIT_CODE[ruang.kode], known)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_unit -v 1`
Expected: PASS, `0 failed`.

- [ ] **Step 6: Commit**

```bash
git add akreditasi/layanan_unit.py akreditasi/tests_layanan_unit.py
git commit -m "feat(layanan): resolver peta layanan pasien per unit kerja"
```

---

## Task 2: `layanan` block in the snapshot + fix the EMR join

**Files:**
- Modify: `akreditasi/kontrol_data.py:185-233` (`_emr_block`), `:288-309` (`build_unit_snapshot`)
- Test: `akreditasi/tests_layanan_unit.py` (append)

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces: `snapshot['layanan']` with exactly these keys —
  - `tanggal: date` (local date, not UTC)
  - `total: int`
  - `by_status: dict[str, int]`
  - `items: list[dict]` — each `{'pk', 'no_kunjungan', 'nama', 'no_rm', 'umur', 'jk', 'jenis', 'poli', 'ruangan', 'dpjp', 'status', 'status_label', 'jam', 'penjamin'}`
  - `mapped: bool` — `False` when the unit owns no clinical service
  - `truncated: bool`
  - `owns_beds: bool`

  Also changes `_emr_block(unit_ids)` → `_emr_block(unit)`.

- [ ] **Step 1: Write the failing tests**

Append to `akreditasi/tests_layanan_unit.py`:

```python
class SnapshotLayananTest(TestCase):
    def setUp(self):
        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.pasien = _pasien('RM-SNAP')

    def test_layanan_lists_only_this_unit(self):
        from akreditasi.kontrol_data import build_unit_snapshot

        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-MINE', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(), status='DAFTAR')
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-OTHER', jenis_kunjungan='RAJAL',
            poliklinik='Poli Penyakit Dalam',
            tanggal_masuk=timezone.now(), status='DAFTAR')

        snap = build_unit_snapshot(self.unit)
        self.assertEqual(snap['layanan']['total'], 1)
        self.assertEqual(
            [i['no_kunjungan'] for i in snap['layanan']['items']], ['K-MINE'])
        self.assertTrue(snap['layanan']['mapped'])

    def test_emr_block_matches_unit_that_has_staff(self):
        """Defect 2: kehadiran staf tidak boleh mengosongkan blok EMR."""
        from accounts.models import UserProfile
        from django.contrib.auth import get_user_model
        from akreditasi.kontrol_data import build_unit_snapshot

        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-AKTIF', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(), status='ASESMEN')

        before = build_unit_snapshot(self.unit)['emr']['active_total']
        self.assertEqual(before, 1)

        user = get_user_model().objects.create_user('kep.snap', 'ks@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=self.unit)

        after = build_unit_snapshot(self.unit)['emr']['active_total']
        self.assertEqual(after, 1, 'blok EMR kosong setelah staf ditugaskan')

    def test_unit_without_service_is_unmapped_not_zero(self):
        from akreditasi.kontrol_data import build_unit_snapshot
        komite = _unit('KOMITE-MUTU', 'Komite Mutu PMKP & Keselamatan Pasien', 2)
        snap = build_unit_snapshot(komite)
        self.assertFalse(snap['layanan']['mapped'])
        self.assertEqual(snap['layanan']['items'], [])

    def test_today_means_admitted_today(self):
        """Kunjungan ranap lama tidak boleh muncul sebagai layanan hari ini."""
        from datetime import timedelta
        from akreditasi.kontrol_data import build_unit_snapshot

        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-LAMA', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now() - timedelta(days=3), status='RANAP')

        snap = build_unit_snapshot(self.unit)
        self.assertEqual(snap['layanan']['total'], 0)
        self.assertTrue(snap['layanan']['mapped'])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_unit.SnapshotLayananTest -v 1`
Expected: FAIL — `KeyError: 'layanan'` and `AssertionError: 0 != 1` on the EMR test.

- [ ] **Step 3: Replace `_emr_block`**

In `akreditasi/kontrol_data.py`, replace lines 185-198 (the function signature and the broken name join) with:

```python
def _emr_block(unit):
    """Kunjungan aktif unit ini, diresolusi lewat peta layanan.

    Versi sebelumnya mencocokkan ``poliklinik__in=UserProfile.unit_kerja__name``.
    Itu tidak pernah cocok: ``poliklinik`` menyimpan label ``POLIKLINIK_CHOICES``
    ('Poli Jantung & Pembuluh Darah'), sedangkan ``UnitKerja.name`` adalah
    'Poliklinik Jantung & Pembuluh Darah'. Akibatnya blok EMR kosong justru
    untuk unit yang punya staf.
    """
    from pasien.models import AsesmenRisikoKlinis, Bed, CPPT, KunjunganPasien
    from .layanan_unit import resolve_visit_ids

    active = KunjunganPasien.objects.filter(status__in=ACTIVE_VISIT_STATUSES)
    matching = resolve_visit_ids(active, unit)
    visits = (
        KunjunganPasien.objects.filter(pk__in=matching)
        if matching else KunjunganPasien.objects.none()
    )
```

Leave the rest of the function body (from `by_jenis = {...}` at line 199 onward) unchanged.

- [ ] **Step 4: Add the `layanan` builder**

Insert before `build_unit_snapshot` in `akreditasi/kontrol_data.py`:

```python
LAYANAN_LIMIT = 1000
LAYANAN_JENIS_LABEL = {'IGD': 'IGD', 'RAJAL': 'Rawat Jalan', 'RANAP': 'Rawat Inap'}


def _layanan_block(unit, on_date=None):
    """Pasien yang terdaftar di unit ini pada satu tanggal lokal.

    "Hari ini" = ``tanggal_masuk`` jatuh pada tanggal tersebut, bukan "masih
    terbuka" — kalau memakai status, sensus ranap sebulan akan tampil sebagai
    pasien hari ini.

    ``mapped=False`` dipakai template untuk membedakan "unit ini tidak punya
    layanan pendaftaran" dari "hari ini belum ada pasien".
    """
    from django.utils import timezone
    from pasien.models import KunjunganPasien
    from .layanan_unit import (
        alias_index, resolve_code, service_codes, unit_codes, unit_owns_beds,
    )

    on_date = on_date or timezone.localdate()
    codes = unit_codes(unit)
    index = alias_index()
    serves = bool(codes & service_codes())
    owns_beds = unit_owns_beds(unit, codes)

    rows = list(
        KunjunganPasien.objects
        .filter(tanggal_masuk__date=on_date)
        .select_related('pasien', 'bed__ruangan')
        .order_by('tanggal_masuk')[:LAYANAN_LIMIT]
    )

    items, by_status = [], {}
    for k in rows:
        ruangan_nama = k.bed.ruangan.nama if k.bed else None
        if resolve_code(k.poliklinik, ruangan_nama, index) not in codes:
            continue
        by_status[k.status] = by_status.get(k.status, 0) + 1
        items.append({
            'pk': k.pk,
            'no_kunjungan': k.no_kunjungan,
            'nama': k.pasien.nama_lengkap,
            'no_rm': k.pasien.no_rm,
            'umur': k.pasien.umur,
            'jk': k.pasien.get_jenis_kelamin_display(),
            'jenis': LAYANAN_JENIS_LABEL.get(k.jenis_kunjungan, k.jenis_kunjungan),
            'poli': k.poliklinik or '—',
            'ruangan': k.bed.ruangan.nama if k.bed else '',
            'dpjp': k.dpjp or '',
            'status': k.status,
            'status_label': k.get_status_display(),
            'jam': timezone.localtime(k.tanggal_masuk).strftime('%H:%M'),
            'penjamin': k.get_penjamin_display(),
        })

    return {
        'tanggal': on_date,
        'total': len(items),
        'by_status': by_status,
        'items': items,
        'mapped': serves,
        'truncated': len(rows) >= LAYANAN_LIMIT,
        'owns_beds': owns_beds,
    }
```

- [ ] **Step 5: Wire it into the snapshot**

In `build_unit_snapshot`, change the `'emr'` line and add `'layanan'`:

```python
        'emr': _emr_block(unit),
        'layanan': _layanan_block(unit),
```

Then bump the cache version so stale snapshots are not served:

```python
SNAPSHOT_CACHE_VERSION = 'v2'
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_unit akreditasi.tests_kontrol_dasbor -v 1`
Expected: PASS, `0 failed`. The query-budget tests must still pass — the layanan block is inside the cached snapshot.

- [ ] **Step 7: Commit**

```bash
git add akreditasi/kontrol_data.py akreditasi/tests_layanan_unit.py
git commit -m "fix(kontrol): blok EMR dan layanan memakai resolver unit, bukan nama profil"
```

---

## Task 3: The day list page

**Files:**
- Modify: `akreditasi/urls.py:14-18` (add route), `akreditasi/kontrol_views.py:74-86` (`_common_context`), `:163-171` (`_portal`)
- Create: `templates/akreditasi/kontrol/layanan.html`
- Test: `akreditasi/tests_layanan_unit.py` (append)

**Interfaces:**
- Consumes: `_resolve_unit` (`kontrol_views.py:56`), `_layanan_block` (Task 2), `snapshot`.
- Produces: URL name `akreditasi:kontrol_layanan`; context keys `layanan`, `tanggal`, `prev_date`, `next_date`, `is_today`, `status_pilihan`, `filter_status`.

- [ ] **Step 1: Write the failing tests**

Append to `akreditasi/tests_layanan_unit.py`:

```python
class LayananPageTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache

        cache.clear()
        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.other = _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3)
        self.pasien = _pasien('RM-PAGE')
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-PAGE-1', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah', dpjp='dr. Faisal, Sp.JP',
            tanggal_masuk=timezone.now(), status='DAFTAR')
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-PAGE-2', jenis_kunjungan='RAJAL',
            poliklinik='Poli Penyakit Dalam',
            tanggal_masuk=timezone.now(), status='DAFTAR')

        user = get_user_model().objects.create_user('kep.page', 'kp@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=self.unit)
        self.client.force_login(user)

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_lists_only_own_unit(self):
        from django.urls import reverse

        res = self.client.get(reverse('akreditasi:kontrol_layanan'))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('K-PAGE-1', body)
        self.assertNotIn('K-PAGE-2', body)

    def test_unit_scoped_user_cannot_switch_unit(self):
        from django.urls import reverse

        res = self.client.get(
            reverse('akreditasi:kontrol_layanan'), {'unit': self.other.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['unit'].pk, self.unit.pk)

    def test_anonymous_redirected(self):
        from django.urls import reverse

        self.client.logout()
        res = self.client.get(reverse('akreditasi:kontrol_layanan'))
        self.assertEqual(res.status_code, 302)

    def test_invalid_date_falls_back_to_today(self):
        from django.urls import reverse
        from django.utils import timezone

        res = self.client.get(
            reverse('akreditasi:kontrol_layanan'), {'tanggal': 'bukan-tanggal'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['tanggal'], timezone.localdate())

    def test_no_sidebar_shell(self):
        from django.urls import reverse

        body = self.client.get(reverse('akreditasi:kontrol_layanan')).content.decode()
        self.assertNotIn('sidebar-desktop', body)
        self.assertNotIn('id="mobileSidebar"', body)
        self.assertIn('static/css/kontrol.', body)


class LayananPageQueryBudgetTest(TestCase):
    BUDGET = 12

    def test_warm_request_within_budget(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from django.urls import reverse

        cache.clear()
        unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        user = get_user_model().objects.create_user('kep.q', 'kq@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=unit)
        self.client.force_login(user)
        url = reverse('akreditasi:kontrol_layanan')
        self.client.get(url)
        with CaptureQueriesContext(connection) as ctx:
            res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(len(ctx.captured_queries), self.BUDGET,
                             f'{len(ctx.captured_queries)} query, anggaran {self.BUDGET}')
        cache.clear()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_unit.LayananPageTest -v 1`
Expected: FAIL — `NoReverseMatch: 'kontrol_layanan' is not a registered namespace` (or 404).

- [ ] **Step 3: Add the route**

In `akreditasi/urls.py`, after line 17 (`control/dokumen/`):

```python
    path('control/layanan/', kontrol_views.kontrol_layanan, name='kontrol_layanan'),
```

- [ ] **Step 4: Add the view**

In `akreditasi/kontrol_views.py`, after `kontrol_dokumen` (line 186):

```python
def _parse_tanggal(raw):
    """'YYYY-MM-DD' → date; apa pun yang tidak valid → hari ini (lokal)."""
    from datetime import date
    from django.utils import timezone

    if raw:
        try:
            return date.fromisoformat(raw)
        except (TypeError, ValueError):
            pass
    return timezone.localdate()


@login_required
def kontrol_layanan(request):
    """Daftar layanan pasien satu unit pada satu tanggal.

    Tanggal bisa digeser lewat ``?tanggal=``; nilai tidak valid jatuh ke hari
    ini, bukan 500. Unit selalu lewat ``_resolve_unit`` supaya akun unit-scoped
    tidak bisa membaca unit lain dengan mengubah query string.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .kontrol_data import _layanan_block

    profile = _profile(request)
    unit = _resolve_unit(request, profile)
    if unit is None:
        messages.warning(request, 'Belum ada unit kerja aktif untuk ditampilkan.')
        return redirect('akreditasi:kontrol_hub')

    tanggal = _parse_tanggal(request.GET.get('tanggal'))
    snapshot = snapshot_cached(unit, profile)
    # Snapshot sudah memuat blok untuk hari ini; tanggal lain dihitung ad hoc
    # supaya cache harian tidak perlu dipecah per tanggal.
    if tanggal != timezone.localdate():
        snapshot = dict(snapshot)
        snapshot['layanan'] = _layanan_block(unit, on_date=tanggal)

    layanan = snapshot['layanan']
    status_filter = request.GET.get('status', '')
    items = layanan['items']
    if status_filter:
        items = [i for i in items if i['status'] == status_filter]

    ctx = _common_context(request, unit, profile)
    ctx.update({
        'snapshot': snapshot,
        'layanan': layanan,
        'items': items,
        'tanggal': tanggal,
        'prev_date': tanggal - timedelta(days=1),
        'next_date': tanggal + timedelta(days=1),
        'is_today': tanggal == timezone.localdate(),
        'filter_status': status_filter,
        'status_pilihan': [
            ('DAFTAR', 'Terdaftar'), ('TRIAGE', 'Triage'), ('ASESMEN', 'Asesmen'),
            ('RANAP', 'Rawat Inap'), ('PULANG', 'Pulang'), ('RUJUK', 'Dirujuk'),
        ],
        'active_portal': 'emr',
    })
    return render(request, 'akreditasi/kontrol/layanan.html', ctx)
```

`snapshot_cached` is already imported at the top of `kontrol_views.py` (line 20). `_common_context` does not supply `snapshot`, which is why the view sets it — the shell footer (`base_kontrol.html:117`) reads `snapshot.unit` and `snapshot.year`.

- [ ] **Step 5: Create the page template**

`templates/akreditasi/kontrol/layanan.html`:

```html
{% extends "akreditasi/kontrol/base_kontrol.html" %}
{% block title %}Layanan Unit — {{ unit.name }}{% endblock %}

{% block content %}
<section class="kontrol-subhead">
    <div class="subhead-left">
        <a class="kontrol-back" href="{% url 'akreditasi:kontrol_emr' %}?unit={{ unit.id }}">
            <i class="bi bi-arrow-left"></i> Control
        </a>
        <span class="kontrol-eyebrow"><i class="bi bi-clipboard2-pulse"></i> Layanan Unit</span>
        <h1 class="kontrol-title-sm">{{ unit.name }}</h1>
        <p class="kontrol-lede-sm">
            Daftar layanan pasien hari ini —
            <strong>{{ tanggal|date:"l, j F Y" }}</strong>.
        </p>
    </div>
    {% include "akreditasi/kontrol/_unit_switch.html" %}
</section>

<section class="kontrol-layanan-toolbar">
    <div class="layanan-nav">
        <a class="kontrol-ghost" href="?unit={{ unit.id }}&tanggal={{ prev_date|date:'Y-m-d' }}">
            <i class="bi bi-chevron-left"></i> Hari sebelumnya
        </a>
        <a class="kontrol-ghost {% if is_today %}disabled{% endif %}"
           href="?unit={{ unit.id }}">
            <i class="bi bi-calendar-event"></i> Hari ini
        </a>
        <a class="kontrol-ghost" href="?unit={{ unit.id }}&tanggal={{ next_date|date:'Y-m-d' }}">
            Hari berikutnya <i class="bi bi-chevron-right"></i>
        </a>
    </div>
    <form method="get" class="layanan-filter">
        <input type="hidden" name="unit" value="{{ unit.id }}">
        <input type="hidden" name="tanggal" value="{{ tanggal|date:'Y-m-d' }}">
        <select name="status" class="form-select form-select-sm" onchange="this.form.submit()">
            <option value="">Semua status</option>
            {% for val, label in status_pilihan %}
            <option value="{{ val }}" {% if filter_status == val %}selected{% endif %}>{{ label }}</option>
            {% endfor %}
        </select>
    </form>
</section>

{% if not layanan.mapped %}
<section class="kontrol-empty">
    <i class="bi bi-inbox"></i>
    <h3>Unit ini tidak memiliki layanan pendaftaran pasien</h3>
    <p>Tidak ada poliklinik maupun ruangan rawat yang dipetakan ke {{ unit.name }}.</p>
</section>
{% elif not items %}
<section class="kontrol-empty">
    <i class="bi bi-inbox"></i>
    <h3>Belum ada pasien pada {{ tanggal|date:"j F Y" }}</h3>
    <p>Daftar ini membaca kunjungan yang terdaftar pada tanggal tersebut.</p>
</section>
{% else %}
<section class="kontrol-panel">
    <header class="panel-head">
        <h2><i class="bi bi-people"></i> {{ items|length }} pasien</h2>
        <span class="panel-hint">{{ tanggal|date:"d/m/Y" }}</span>
    </header>
    <div class="table-responsive">
        <table class="table table-sm layanan-table align-middle mb-0">
            <thead>
                <tr>
                    <th>Jam</th>
                    <th>No. Kunjungan</th>
                    <th>Pasien</th>
                    <th>Jenis</th>
                    <th>Poli / Ruangan</th>
                    <th>DPJP</th>
                    <th>Status</th>
                    <th>Penjamin</th>
                </tr>
            </thead>
            <tbody>
                {% for i in items %}
                <tr>
                    <td class="mono">{{ i.jam }}</td>
                    <td class="mono">{{ i.no_kunjungan }}</td>
                    <td>
                        <div class="layanan-nama">{{ i.nama }}</div>
                        <div class="layanan-sub">{{ i.no_rm }} · {{ i.umur }} th · {{ i.jk }}</div>
                    </td>
                    <td>{{ i.jenis }}</td>
                    <td>
                        <div>{{ i.poli }}</div>
                        {% if i.ruangan %}<div class="layanan-sub">{{ i.ruangan }}</div>{% endif %}
                    </td>
                    <td>{{ i.dpjp|default:"—" }}</td>
                    <td><span class="layanan-badge layanan-badge-{{ i.status|lower }}">{{ i.status_label }}</span></td>
                    <td>{{ i.penjamin }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% if layanan.truncated %}
    <p class="layanan-note">
        <i class="bi bi-exclamation-triangle"></i>
        Daftar dipotong pada {{ layanan.total }} baris pertama.
    </p>
    {% endif %}
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Add the page CSS**

Create a new `/* ── layanan unit ── */` section in `static/css/kontrol.css`, inserted immediately before the `/* ── misc ──` header (line 834). Task 4 appends the block styles to this same section:

```css
.kontrol-layanan-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin: 4px 0 18px;
}

.layanan-nav { display: flex; gap: 8px; flex-wrap: wrap; }

.layanan-nav .disabled {
    opacity: 0.45;
    pointer-events: none;
}

.layanan-filter .form-select {
    background: var(--k-panel-solid);
    border-color: var(--k-line);
    color: var(--k-text);
    font-size: 0.78rem;
    min-width: 150px;
}

.layanan-table { color: var(--k-text); font-size: 0.78rem; }

.layanan-table thead th {
    font-size: 0.66rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--k-dim);
    font-weight: 600;
    border-bottom: 1px solid var(--k-line);
    white-space: nowrap;
}

.layanan-table tbody td { border-color: rgba(120, 168, 214, 0.1); }

.layanan-table .mono {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
    color: var(--k-muted);
    white-space: nowrap;
}

.layanan-nama { font-weight: 600; }

.layanan-sub {
    font-size: 0.68rem;
    color: var(--k-dim);
    font-family: 'JetBrains Mono', monospace;
}

.layanan-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 0.66rem;
    font-weight: 600;
    border: 1px solid var(--k-line-strong);
    color: var(--k-muted);
}

.layanan-badge-daftar,
.layanan-badge-triage { color: var(--k-watch); border-color: rgba(251, 191, 36, 0.4); }

.layanan-badge-asesmen,
.layanan-badge-ranap { color: var(--k-cyan); border-color: rgba(34, 211, 238, 0.4); }

.layanan-badge-pulang { color: var(--k-good); border-color: rgba(52, 211, 153, 0.4); }

.layanan-badge-rujuk,
.layanan-badge-meninggal,
.layanan-badge-batal { color: var(--k-critical); border-color: rgba(248, 113, 113, 0.4); }
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_unit -v 1`
Expected: PASS, `0 failed`.

- [ ] **Step 8: Commit**

```bash
git add akreditasi/urls.py akreditasi/kontrol_views.py templates/akreditasi/kontrol/layanan.html static/css/kontrol.css akreditasi/tests_layanan_unit.py
git commit -m "feat(kontrol): halaman daftar layanan pasien hari ini per unit"
```

---

## Task 4: `LAYANAN UNIT` block on all three sub-dashboards

**Files:**
- Create: `templates/akreditasi/kontrol/_layanan_unit.html`
- Modify: `templates/akreditasi/kontrol/emr.html:79-85` (delete strip), `risiko.html:117-124` (keep, add include above), `dokumen.html:77-82` (keep, add include above)
- Modify: `static/css/kontrol.css` (append block styles to the `/* ── layanan unit ── */` section created by Task 3)
- Test: `akreditasi/tests_layanan_unit.py` (append)

**Interfaces:**
- Consumes: `snapshot.layanan` (Task 2), `snapshot.unit`, and the `akreditasi:kontrol_layanan` URL name registered in Task 3.
- Produces: nothing importable.

- [ ] **Step 1: Write the failing tests**

Append to `akreditasi/tests_layanan_unit.py`:

```python
class LayananBlockTemplateTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache

        cache.clear()
        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.pasien = _pasien('RM-TPL')
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-TPL-1', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(), status='DAFTAR')
        user = get_user_model().objects.create_user('kep.tpl', 'kt@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=self.unit)
        self.client.force_login(user)

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_block_renders_heading_and_date(self):
        from django.urls import reverse
        from django.utils import timezone

        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        body = res.content.decode()
        self.assertIn('LAYANAN UNIT', body)
        self.assertIn(self.unit.name, body)
        self.assertIn('Daftar layanan pasien hari ini', body)
        self.assertIn(timezone.localdate().strftime('%Y'), body)

    def test_generic_strip_is_gone(self):
        from django.urls import reverse

        body = self.client.get(reverse('akreditasi:kontrol_emr')).content.decode()
        self.assertNotIn('kontrol-modlinks', body)
        for label in ('Daftar kunjungan', 'Rawat jalan', 'Rekap KPS'):
            with self.subTest(label=label):
                self.assertNotIn(label, body)

    def test_block_present_on_risk_and_document_dashboards(self):
        from django.urls import reverse

        for name in ('kontrol_risiko', 'kontrol_dokumen'):
            with self.subTest(name=name):
                body = self.client.get(reverse('akreditasi:' + name)).content.decode()
                self.assertIn('LAYANAN UNIT', body)

    def test_unmapped_unit_explains_itself(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache
        from django.urls import reverse

        komite = _unit('KOMITE-MUTU', 'Komite Mutu PMKP & Keselamatan Pasien', 2)
        user = get_user_model().objects.create_user('komite.tpl', 'km@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=komite)
        self.client.force_login(user)
        cache.clear()

        body = self.client.get(reverse('akreditasi:kontrol_emr')).content.decode()
        self.assertIn('tidak memiliki layanan pendaftaran pasien', body)
        self.assertNotIn('0 pasien', body)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_unit.LayananBlockTemplateTest -v 1`
Expected: FAIL — `LAYANAN UNIT` not in the response body; `kontrol-modlinks` still present.

- [ ] **Step 3: Create the include**

`templates/akreditasi/kontrol/_layanan_unit.html`:

```html
{% if snapshot.layanan %}
<section class="kontrol-layanan">
    <header class="layanan-head">
        <div>
            <span class="kontrol-eyebrow"><i class="bi bi-diagram-2"></i> Layanan Unit</span>
            <h2>{{ snapshot.unit.name }}</h2>
        </div>
        <span class="layanan-date">{{ snapshot.layanan.tanggal|date:"l, j F Y" }}</span>
    </header>

    {% if not snapshot.layanan.mapped %}
    <p class="layanan-empty">
        <i class="bi bi-info-circle"></i>
        Unit ini tidak memiliki layanan pendaftaran pasien langsung, sehingga tidak ada daftar kunjungan harian.
    </p>
    {% else %}
    <a class="layanan-entry" href="{% url 'akreditasi:kontrol_layanan' %}?unit={{ snapshot.unit.id }}&tanggal={{ snapshot.layanan.tanggal|date:'Y-m-d' }}">
        <span class="layanan-entry-icon"><i class="bi bi-clipboard2-pulse"></i></span>
        <span class="layanan-entry-text">
            <strong>Daftar layanan pasien hari ini</strong>
            <small>{{ snapshot.layanan.tanggal|date:"j F Y" }}</small>
        </span>
        <span class="layanan-entry-count">
            {% if snapshot.layanan.total %}{{ snapshot.layanan.total }} pasien{% else %}Belum ada pasien{% endif %}
        </span>
        <i class="bi bi-arrow-right layanan-entry-go"></i>
    </a>

    {% if snapshot.layanan.owns_beds %}
    <a class="layanan-entry layanan-entry-sub" href="{% url 'pasien:bed_management' %}">
        <span class="layanan-entry-icon"><i class="bi bi-grid-3x3-gap"></i></span>
        <span class="layanan-entry-text">
            <strong>Bed &amp; okupansi</strong>
            <small>Ketersediaan tempat tidur unit ini</small>
        </span>
        <i class="bi bi-arrow-right layanan-entry-go"></i>
    </a>
    {% endif %}

    {% if snapshot.layanan.truncated %}
    <p class="layanan-note">
        <i class="bi bi-exclamation-triangle"></i>
        Daftar dipotong pada {{ snapshot.layanan.total }} baris pertama hari ini.
    </p>
    {% endif %}
    {% endif %}
</section>
{% endif %}
```

- [ ] **Step 4: Add the block CSS**

In `static/css/kontrol.css`, append to the `/* ── layanan unit ── */` section created by Task 3:

```css
.kontrol-layanan {
    margin: 24px 0 8px;
    padding: 20px;
    border: 1px solid var(--k-line);
    border-radius: var(--k-radius);
    background: var(--k-panel);
}

.layanan-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 14px;
}

.layanan-head h2 {
    font-size: 0.98rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin: 0;
    color: #eaf3fc;
}

.layanan-head .kontrol-eyebrow { margin-bottom: 6px; }

.layanan-date {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 0.06em;
    color: var(--k-dim);
    padding-top: 4px;
}

.layanan-entry {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 13px 15px;
    border-radius: 11px;
    border: 1px solid var(--k-line);
    background: rgba(255, 255, 255, 0.035);
    color: var(--k-text);
    text-decoration: none;
    transition: 160ms ease;
}

.layanan-entry + .layanan-entry { margin-top: 8px; }

.layanan-entry:hover {
    border-color: var(--k-line-strong);
    background: rgba(14, 165, 233, 0.12);
}

.layanan-entry-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 9px;
    background: rgba(34, 211, 238, 0.12);
    color: var(--k-cyan);
    flex-shrink: 0;
}

.layanan-entry-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    min-width: 0;
}

.layanan-entry-text strong { font-size: 0.84rem; font-weight: 600; }

.layanan-entry-text small {
    font-size: 0.7rem;
    color: var(--k-dim);
    font-family: 'JetBrains Mono', monospace;
}

.layanan-entry-count {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--k-cyan);
    white-space: nowrap;
}

.layanan-entry-go { color: var(--k-dim); font-size: 0.8rem; }

.layanan-empty,
.layanan-note {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 0.78rem;
    color: var(--k-muted);
    line-height: 1.6;
    margin: 0;
}

.layanan-note { margin-top: 10px; color: var(--k-watch); }

@media (max-width: 640px) {
    .layanan-entry-count { display: none; }
    .layanan-date { font-size: 0.62rem; }
}
```

- [ ] **Step 5: Delete the generic strip and include the block**

In `templates/akreditasi/kontrol/emr.html`, replace lines 77-85:

```html
{% include "akreditasi/kontrol/_ai_panel.html" %}

<section class="kontrol-modlinks">
    <a href="{% url 'pasien:kunjungan_daftar' %}"><i class="bi bi-clipboard2-pulse"></i> Daftar kunjungan</a>
    <a href="{% url 'pasien:igd_dashboard' %}"><i class="bi bi-hospital"></i> IGD</a>
    <a href="{% url 'pasien:rajal_dashboard' %}"><i class="bi bi-door-open"></i> Rawat jalan</a>
    <a href="{% url 'pasien:bed_management' %}"><i class="bi bi-layout-three-columns"></i> Bed management</a>
    <a href="{% url 'akreditasi:rekap_kps' %}"><i class="bi bi-person-badge"></i> Rekap KPS</a>
</section>
{% endblock %}
```

with:

```html
{% include "akreditasi/kontrol/_ai_panel.html" %}

{% include "akreditasi/kontrol/_layanan_unit.html" %}
{% endblock %}
```

In `templates/akreditasi/kontrol/risiko.html`, insert `{% include "akreditasi/kontrol/_layanan_unit.html" %}` immediately **before** the existing `<section class="kontrol-modlinks">` at line 117. Do the same in `dokumen.html` before line 77.

Do **not** remove `kontrol-modlinks` from `risiko.html` or `dokumen.html`: those blocks link to accreditation modules (risk register, FMEA/RCA, quality reports), not to the patient modules the docx names. `Rekap KPS` remains reachable from the main sidebar at `templates/includes/sidebar.html:355` for the three roles that pass its 403 gate.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_unit akreditasi.tests_kontrol_dasbor -v 1`
Expected: PASS, `0 failed`. `test_hub_tampil_tanpa_sidebar` and `test_tiga_subdasbor_terbuka` must stay green.

- [ ] **Step 7: Commit**

```bash
git add templates/akreditasi/kontrol/ static/css/kontrol.css akreditasi/tests_layanan_unit.py
git commit -m "feat(kontrol): menu LAYANAN UNIT per dasbor, hapus strip modul generik"
```

---

## Task 5: Static build, full suite, commit

**Files:** none created; `staticfiles/` regenerated.

- [ ] **Step 1: Collect static**

```bash
.venv/Scripts/python.exe manage.py collectstatic --noinput
```

Expected: `static files copied`, new hashed `kontrol.<hash>.css` plus updated `staticfiles/staticfiles.json`.

- [ ] **Step 2: Run the whole suite**

```bash
.venv/Scripts/python.exe manage.py test --verbosity 1
```

Expected: `0 failed`, exit code 0. If `accounts.tests_sidebar_visibility` or `pasien.tests_*` fail, they are pre-existing failures — capture the baseline on `master` before this branch (`git stash && manage.py test ... && git stash pop`) and state the delta rather than assuming your change caused it.

- [ ] **Step 3: Manual smoke test on the dev server**

```bash
.venv/Scripts/python.exe manage.py runserver 8000
```

Open `/control/emr/?unit=188` (POLI-JANTUNG in `db.sqlite3`) and confirm:
1. `LAYANAN UNIT` block renders with the unit name and `Kamis, 22 Oktober 2026`.
2. The `Daftar kunjungan / IGD / Rawat jalan / Bed management / Rekap KPS` row is gone.
3. `Kunjungan aktif` is no longer `0` when a visit exists for that poli.
4. Clicking the entry opens `/control/layanan/?unit=188&tanggal=2026-10-22` and lists the same patients.

- [ ] **Step 4: Commit the static artifacts**

```bash
git add staticfiles/
git commit -m "chore(static): collectstatic untuk menu LAYANAN UNIT"
```

---

## Explicitly NOT in this plan

Each of these was found while probing. **Do not implement, do not fix while here** — they belong to their own change so the reviewer can tell which hunk answers the docx.

1. **`KunjunganPasien.unit_layanan` FK.** The durable fix for Defect 3, and the reason `POLI_UNIT_CODE` / `RUANGAN_UNIT_CODE` exist as hand-maintained dicts. It needs a migration, a backfill over existing visits, and edits to five creation paths (`views.py:345`, `views.py:1602`, `fast_track_igd`, `kunjungan_disposisi`, `booking_kamar_checkin`). Out of scope for a display change.
2. **`pasien/views.py:743` queue-number bug.** `poliklinik__icontains=k if 'k' in locals() else ''` references a loop variable that only exists when the prefix map matched; otherwise it filters `poliklinik__icontains=''` and counts *every* visit today. Wrong queue numbers, unrelated to this docx.
3. **`generate_no_kunjungan` uses `datetime.datetime.now()`** (`pasien/models.py:127`) instead of `timezone.localtime()` — the date prefix is UTC, so a visit registered at 06:30 WIB gets yesterday's prefix.
4. **`rekap_kps` returns 403 for `SUPER_ADMIN` without `is_superuser`.** `views.py:1829` checks `profile.role in ('SUPER_ADMIN', 'ADMIN_RS', 'KEPALA_UNIT')` but the seeded superadmin profile may be `ASESOR`; probe showed `SUPERUSER -> 403`. Removing the link from the kontrol strip reduces exposure, it does not fix the guard.
5. **`templates/includes/sidebar.html:413-443` hardcodes nine poliklinik links** with `?poli=<label>` query strings that `rajal_dashboard` matches via `icontains`. Now that a real resolver exists, that block should be generated from `alias_index()` — separate change, touches every page in the app.
6. **`_emr_block` bed occupancy is RS-wide by design** (`kontrol_data.py:228-231` documents it). Not touched. The new `owns_beds` flag narrows *navigation*, not the occupancy number.

## Self-Review

- **Spec coverage:** remove four named links → Task 4 Step 5; `LAYANAN UNIT` heading + unit name → Task 4 Step 3; `Daftar layanan pasien hari ini (tanggal/bulan/tahun)` → Task 4 Step 3 (label + date) and Task 3 (the destination page); "layanan sesuai unit masing-masing" → Tasks 1-2; "semua dasbor begitu" → Task 4 Step 5 (three includes) and Task 4 test `test_block_present_on_risk_and_document_dashboards`.
- **Placeholder scan:** no TBD, no "add error handling", no "similar to Task N". Every code block is complete and runnable.
- **Type consistency:** `_layanan_block` returns the eight keys declared in Task 2's Interfaces; Task 4's template reads exactly `layanan.mapped`, `layanan.tanggal`, `layanan.total`, `layanan.truncated`, `layanan.owns_beds`, `layanan.items`; Task 3's view reads `layanan['items']`, `layanan['mapped']`, `layanan['truncated']`. `_emr_block(unit)` signature change is applied at its single call site (`build_unit_snapshot`).
- **File inventory:** every path in File Structure is created or modified by a named task; no task declares a path the tree omits.
- **Deletions reconcile:** `kontrol-modlinks` is removed from `emr.html` only, and Task 4 Step 5 states why `risiko.html` / `dokumen.html` keep theirs. No test references the removed labels (`grep` over `**/tests*.py` returned nothing for `Daftar kunjungan`, `Rekap KPS`, `Rawat jalan`, `Bed management`).
- **Task ordering:** Task 3 registers the URL that Task 4's include reverses, and Task 3 creates the CSS section Task 4 appends to — so tasks run 1→5 with no forward references. An executor who reorders them gets `NoReverseMatch`.
- **Breakpoint audit:** the only responsive rule added hides `.layanan-entry-count` below 640px — the count is repeated in the destination page heading, so nothing becomes unreachable at that size.
- **Review Focus:** all five input classes have a named test — (1) `test_emr_block_matches_unit_that_has_staff`, (2) `test_unmapped_unit_explains_itself`, (3) `test_resolves_choice_code`, (4) `test_today_means_admitted_today`, (5) `test_parent_includes_descendants_not_ancestors`.

---

## Execution Status — 2026-10-22

Executed in full on branch `master`. Full suite: **538 tests, OK, exit 0** (513.9s).

### Done

| Task | What landed | Commit |
|---|---|---|
| 1 | `akreditasi/layanan_unit.py` (resolver, alias index, downward unit walk, `service_codes`, `unit_owns_beds`) + `akreditasi/tests_layanan_unit.py` with 11 tests | `a7f7dec` |
| 2 | `_emr_block(unit)` rewritten on the resolver; `_layanan_block` added; `layanan` key in `build_unit_snapshot`; `SNAPSHOT_CACHE_VERSION` → `v2` | `137eb69` |
| 3 | `/control/layanan/` route + `kontrol_layanan` view + `templates/akreditasi/kontrol/layanan.html` + toolbar/table CSS | `2dcd452` |
| 4 | `_layanan_unit.html` include on all three sub-dashboards; `kontrol-modlinks` strip deleted from `emr.html` only | `(in 2dcd452's successor)` |
| 5 | `collectstatic` (1 file copied, 371 post-processed) + full suite | `fd525ac` |

Verification against the **real dev database** (`db.sqlite3`, unit 188 = POLI-JANTUNG), not just the test DB:

```
kontrol_emr        status=200 block=True  strip=False
kontrol_risiko     status=200 block=True  strip=True
kontrol_dokumen    status=200 block=True  strip=True
kontrol_layanan    status=200 block=True  strip=False
kontrol_hub        status=200 block=False strip=False
```

`strip=True` on risiko/dokumen is intended — those blocks link accreditation modules, not the patient modules the docx names.

### Deviation from the plan, and why

**`_indicator_block` had a second defect the plan did not know about, and it blocked Task 5.** `kontrol_data.py:157` filtered `cat.filter(tercapai=True)`, but `CatatanIndikator.tercapai` is a `@property` (`risiko_models.py:782`), not a column. On the real DB this raised `FieldError: Cannot resolve keyword 'tercapai'` and **every** kontrol page — including `kontrol_hub`, which this plan never touches — returned 500. It never surfaced in tests because `_indicator_block` returns early when there are zero `CatatanIndikator` rows, and the fixtures have none. Fixed in `c5dab09` by counting in Python over `cat.select_related('indikator')`, with two regression tests (`IndicatorBlockRegressionTest`) that create real indicator rows so the early return cannot mask it again. Without this fix the feature ships green and 500s in production.

**`alias_index()` is not cached.** The plan's first draft cached it for 300s. Validation showed that makes `Ruangan` rows created after the first call invisible, so test outcomes depended on execution order. Removed — `build_unit_snapshot` already caches for 60s, so there was nothing to save.

### Not done, needs the live environment

- **`RUANGAN_UNIT_CODE` is seeded from the 8 `Ruangan` rows in `db.sqlite3`.** A production `Ruangan` not in that dict is invisible to the unit dashboards, and `RuanganMappingTest` will fail loudly when the fixture grows — but production rows are not visible from here. Run this against prod and extend the dict for any miss:
  ```sql
  SELECT kode, nama, jenis FROM pasien_ruangan ORDER BY kode;
  ```
- **`POLI_UNIT_CODE['POLI_UMUM'] = None`.** No `POLI-UMUM` unit exists in `UnitKerja`, so Poli Umum patients appear on no unit dashboard. Either create the unit or accept that they are hospital-level only — a data decision, not a code one.
- **The docx screenshot's unit (`?unit=141`) does not exist** in `db.sqlite3`; the real POLI-JANTUNG is pk 188. The report's URL was from a different database.

### Skipped on purpose

- **Task 5 Step 3 (browser smoke test on `runserver`).** Replaced with an in-process `django.test.Client` smoke test against the real DB — same assertions (block present, strip gone, counts non-zero, link resolves), no long-lived server process left behind. The rendered HTML was inspected directly: `Kunjungan aktif: 1`, `1 pasien`, `Kamis, 22 Oktober 2026`.
- **Decision 1 remains open as designed:** `Bed management` is gone from the strip and reappears only inside the block for units that own beds (`owns_beds`). Reverting is still a one-line change if that was the wrong call.
