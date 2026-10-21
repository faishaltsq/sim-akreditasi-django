# Implementation Plan: Laporan Capaian Indikator Mutu (Bulanan / Semesteran / Tahunan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Produce the formal quality-achievement reports described in the guideline — Model A (unit-level monthly report with PDSA analysis of every indicator that misses target), Model B (semester report: executive summary, six-month trend per indicator with a trend chart, kendala + rekomendasi), and Model C (annual report, six BAB, including IKP incident recap and benchmarking) — as frozen, verifiable, approvable documents with a print/PDF output that matches the document's tables, plus the reporting calendar (bulanan ≤ tgl 10, semesteran ≤ tgl 20 Jul/Jan, tahunan ≤ tgl 31 Jan) and the five-tier verification/approval chain.

**Architecture:** Nothing about the *numbers* is invented. Every value in every report row is a snapshot of what `CatatanIndikator.nilai_capaian` / `IndikatorMutu.agregat_capaian` and `CatatanIndikator.tercapai` already compute, captured into a new `LaporanMutuBaris` row when the report is created so that an approved document never silently rewrites itself when a monthly figure is corrected later. A new module `akreditasi/mutu_laporan.py` owns the calendar helper, the snapshot builder, the workflow, and both renderers (print HTML + reportlab PDF), keeping the 2.8k-line `akreditasi/views.py` from growing further — the same split the codebase already uses for `indikator_views.py` and `risiko_views.py`.

**Status:** Implemented 2026-10-20 — Tasks 1–9 done. `akreditasi.tests_mutu_laporan` = 45 tests green (calendar, models, views, workflow, IKP recap, benchmarking, trend series + reportlab chart, narrative sections, print/PDF incl. text-layer extraction). Full suite: 336 tests OK on `master` @ `86d7979` (291 existing + 45 here); `makemigrations --check` reports no changes. Two deviations from the sketch below, recorded here: (a) `build_baris` updates existing rows in place instead of delete+recreate, so PDSA analysis survives a regeneration; (b) benchmarking matches indicators by `nama_indikator`, not `kode_indikator`, because the code is unique per unit and INM indicators repeat across units under an identical name.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3, Chart.js (screen), reportlab (PDF — already a dependency, see `pasien/pdf_utils.py`), one migration, no new pip package.

**Spec:** `C:\Users\cubeb\Downloads\model laporan capaian indikator mutu rs monsiskami  arima.docx` — four sections: (1) Model A monthly unit report incl. PDSA analysis + P-Plan/D-Do/S-Study/A-Act fields and the ≤ tgl 10 deadline; (2) Model B semester report, executive summary + six-month trend table + chart with target threshold line, kendala & rekomendasi; (3) Model C annual report, six BAB, IKP recap (KTD/KNC/KTC/KPC/Sentinel) and benchmarking; (4) reporting calendar, level hierarchy L5→L1 and the verification/approval table.

## What the docx asks for, and what already exists

| docx requirement | Existing equivalent | Verdict |
|---|---|---|
| Target attainment (✅ / ❌) | `CatatanIndikator.tercapai` (`risiko_models.py:778`) resolves `arah_target` MIN/MAX vs `target_nilai` | **Reuse.** Never re-derive the comparator. |
| "Rerata Bulan", "Rerata Sem I", "Rerata Tahun" | `IndikatorMutu.agregat_capaian(tahun)` = Σnum/Σden × faktor (`risiko_models.py:692`), deliberately ratio-of-sums, **not** a mean of monthly percentages | **Reuse, with a documented deviation** — see "Known deviations" item 3. |
| 12-month capaian series | `CatatanIndikator` rows, `unique_together (indikator, bulan, tahun)` | **Reuse.** |
| Trend chart + target threshold line | Chart.js trend on the dashboard (plan `2026-10-14-quality-indicators-monthly-trend-and-renstra-charts.md`, COMPLETED) | **Screen already covered.** PDF needs a static chart → reportlab `VerticalBarChart` + a dashed threshold `Line`. |
| Indicator polarity `sifat_indikator` / `operator_target` | `IndikatorMutu.arah_target` (`MIN`/`MAX`, `risiko_models.py:596`) + `operator_target` | **Already done.** Rendered as `≥`/`≤`; never stored. |
| Penanggung Jawab column | `IndikatorMutu.pj` (CharField, free text) | **Reuse**, with fallback (see gap 6). |
| EP-EP terkait | `IndikatorMutu.ep_terkait` → `StandardItem` | **Reuse**, with fallback (see gap 6). |
| IKP incident recap | `InsidenKeselamatan` (`jenis_insiden`, `tingkat_keparahan`, `tanggal_kejadian`) | **Reuse + one new choice** — `KPC` does not exist in the DB (gap 4). |
| Unit-scope for unit-level reports | `akreditasi/akses_indikator.py` → `unit_scope_ids(unit)`, `indikator_aktif_scoped(profile)` | **Reuse.** Do not write a second scope resolver. |
| Level hierarchy L5→L1 | `UserProfile.ROLE_CHOICES` — exactly 6 roles | **Reuse, mapped** — see gap 5. No new roles. |

## Global Constraints

- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `85,0`; one comma inside `<script>` kills the block (bugs `84c20ce`, `c4c2a3c`). Every template touched here loads `{% load l10n %}`.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.** (Standing project rule.)
- **`UserProfile.is_unit_scoped` is a read-only property, not a field** (`accounts/models.py`). Tests arrange it via `user.is_superuser`, `profile.role`, `profile.unit_kerja`.
- **`HOSPITAL_WIDE_ROLES` already exists and must not be padded** with roles that do not exist. `ROLE_CHOICES` is exactly `SUPER_ADMIN, ADMIN_RS, KOORDINATOR_POKJA, KEPALA_UNIT, STAF_NAKES, ASESOR`. `DIREKTUR` appears only as a stale literal; `SURVEYOR_INTERNAL` likewise.
- **Do not touch the capaian arithmetic.** `CatatanIndikator.nilai_capaian` hard-codes literal `100` for percentage indicators; `faktor_pengali` governs only `rate_absolut` (commit `c9bbfe4`). A report that "fixes" this reintroduces a deleted bug.
- **Saving a `CatatanIndikator` below target auto-creates a `RisikoUnit` draft** (`risiko_models.py:788`). Report rows must *read* that fact, not create it — snapshot code never calls `CatatanIndikator.save()`.
- **`akreditasi/views.py` is ~2832 lines.** New views go in `akreditasi/mutu_laporan.py`; only URL wiring and sidebar nav go into the existing files.
- **`staticfiles/` is intentionally tracked for the Vercel build** — after any CSS/JS change, run `collectstatic` and commit the hashed artifacts + `staticfiles.json`. Never delete that directory.
- **Migrations do not run on deploy.** Note it in the deployment section; they must be applied manually.
- **Vercel deploy is JS-only**, but this repo is the Django app served elsewhere (`Procfile` = `gunicorn config.wsgi`) — the report code ships with the app, not with the static build.

## Known deviations from the docx (documented, not silently "fixed")

1. **Indicator counts are computed, never hardcoded.** The docx's example shows 13 INM / 5 IMP-RS / 25 IMP-Unit. The live DB (2026-10-20) has **210 active indicators: 36 NASIONAL→INM, 98 IMP_RS→IMRS, 76 IMP_UNIT→IMU**. Grouping uses `IndikatorMutu.jenis_standar` (canonical 3-tier mapping, `risiko_models.py:682`), so legacy `jenis` values keep working.
2. **The `$\le 10$` / `$\ge 85\%$` LaTeX fragments in the source Word file are artifacts of the document generator.** Report output renders plain `≤` / `≥` / `%`. No TeX ever reaches a template.
3. **"Rerata Sem I / Rerata Tahun" is rendered as the canonical ratio `ΣN/ΣD × faktor`, not an arithmetic mean of the six monthly percentages.** The arithmetic mean would give a 1-case January the same weight as a 400-case June; `agregat_capaian` exists precisely to avoid that and is already the basis for Renstra achievement and every CSV export. Status (tercapai / belum) is derived from the ratio, so the report cannot disagree with the dashboard for the same data. The column header says `Capaian (Σ N / Σ D)` so the reader knows which definition was used.
4. **`KPC` (Kejadian Pasien Cedera) is added as a new `jenis_insiden` choice.** The docx's IKP recap requires KTD, KNC, KTC, KPC and Sentinel; the DB today contains only `KNC, KTC, KTD, SENTINEL` (measured 2026-10-20). One migration line, zero backfill, and the recap table lists all five rows with a zero count for the empty one rather than dropping it.
5. **Levels L1–L5 map onto the six roles that exist.** No `DIREKTUR` / `KETUA_KOMITE` / `DEWAS` roles are created (a role migration would also change `_is_unit_scoped` blast radius, which plan `2026-10-19-unit-relevance-indicator-filter.md` pins). Mapping: L5 PJ data = `STAF_NAKES`/`STAF_NAKES`+ creator; L4 Kepala Unit = `KEPALA_UNIT` (verifier); L3 Komite Mutu / Tim Mutu = `KOORDINATOR_POKJA` (approver 1); L2 Direksi = `ADMIN_RS`/`SUPER_ADMIN` (approver 2, terbit); L1 Dewan Pengawas = `ASESOR`, read-only view of a `TERBIT` report. The mapping lives in one constant `LEVEL_LAPORAN_MUTU` so it can be retargeted in a single edit.
6. **Empty fields are surfaced, not hidden.** 78/210 active indicators have an empty `pj` and 138/210 have no `ep_terkait` (measured 2026-10-20). The report prints `—` in the cell *and* a header note `N indikator belum memiliki PJ / EP` so the quality committee sees the data-quality gap instead of a silently blank column.
7. **`CatatanIndikator` data exists only for 2026** (2520 rows = 210 × 12; no 2025/2024 rows). An annual report for `tahun < 2026` is creatable but renders an explicit `Belum ada data capaian untuk tahun <n>` empty state, and the trend chart block is omitted rather than drawn empty. The 2024–2026 multi-year trend in BAB VI simply renders the years that have data.
8. **The docx's "Penanggung Jawab" is the indicator's PJ** (`IndikatorMutu.pj`), not a per-report person; per-report roles are the L5–L1 signatories.

## Tasks

### 1. Reporting calendar (helper + RED/GREEN test)

- [x] **RED:** `akreditasi/tests_mutu_laporan.py` → class `BatasWaktuLaporanTest` (case: 4) asserting:
  - `batas_waktu_laporan('BULANAN', tahun=2026, bulan=12) == date(2027, 1, 10)`
  - `batas_waktu_laporan('SEMESTER', tahun=2026, semester=1) == date(2026, 7, 20)`
  - `batas_waktu_laporan('SEMESTER', tahun=2026, semester=2) == date(2027, 1, 20)`
  - `batas_waktu_laporan('TAHUNAN', tahun=2026) == date(2027, 1, 31)`
- [x] **GREEN:** new module `akreditasi/mutu_laporan.py`:

```python
def batas_waktu_laporan(jenis, tahun, bulan=None, semester=None):
    """Batas waktu pelaporan dari matriks BAB I.

    BULANAN : maksimum tanggal 10 bulan berikutnya (Des 2026 → 10/01/2027)
    SEMESTER: Semester I → 20 Juli tahun sama; Semester II → 20 Januari tahun berikut
    TAHUNAN : maksimum 31 Januari tahun berikut
    """
    if jenis == 'BULANAN':
        return date(tahun + 1, 1, 10) if bulan == 12 else date(tahun, bulan + 1, 10)
    if jenis == 'SEMESTER':
        return date(tahun, 7, 20) if semester == 1 else date(tahun + 1, 1, 20)
    return date(tahun + 1, 1, 31)          # TAHUNAN
```

- [x] `terlambat(laporan, hari_ini)` → `hari_ini > batas_waktu_laporan(...)`, plus `sisa_hari` for the dashboard badge. Test both a bulan-12 rollover and an on-time report.

### 2. Report models + migration

- [x] Append to `akreditasi/risiko_models.py` (new section, after `CatatanIndikator`):

```python
# ---------------------------------------------------------------------------
# 6. Laporan Mutu — dokumen formal bulanan / semester / tahunan
# ---------------------------------------------------------------------------

class LaporanMutu(models.Model):
    """Header satu dokumen laporan. Angka di dalamnya dibekukan saat pembuatan."""
    JENIS_CHOICES = [
        ('BULANAN', 'Laporan Capaian Indikator Mutu Bulanan'),
        ('SEMESTER', 'Laporan Capaian Indikator Mutu Semester'),
        ('TAHUNAN', 'Laporan Capaian Indikator Mutu Tahunan'),
    ]
    SCOPE_CHOICES = [('UNIT', 'Unit Kerja'), ('RS', 'Seluruh Rumah Sakit')]
    STATUS_CHOICES = [
        ('DRAF', 'Draf'),
        ('DIVERIFIKASI', 'Diverifikasi Kepala Unit'),
        ('DISETUJUI', 'Disetujui Komite Mutu'),
        ('TERBIT', 'Diterbitkan Direksi'),
    ]

    jenis              = models.CharField('Jenis Laporan', max_length=10, choices=JENIS_CHOICES)
    tahun              = models.PositiveIntegerField('Tahun Laporan', default=2026)
    bulan              = models.PositiveSmallIntegerField('Bulan', null=True, blank=True,
                         validators=[MinValueValidator(1), MaxValueValidator(12)])
    semester           = models.PositiveSmallIntegerField('Semester', null=True, blank=True,
                         validators=[MinValueValidator(1), MaxValueValidator(2)])
    scope              = models.CharField('Cakupan', max_length=5, choices=SCOPE_CHOICES, default='UNIT')
    unit               = models.ForeignKey(UnitKerja, on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='laporan_mutu')
    nomor              = models.CharField('Nomor Dokumen', max_length=60, blank=True, default='')
    status             = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAF')
    pembuat            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                         null=True, related_name='laporan_mutu_dibuat')
    dibuat_pada        = models.DateTimeField(auto_now_add=True)
    diverifikasi_oleh  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                         null=True, blank=True, related_name='laporan_mutu_diverifikasi')
    diverifikasi_pada  = models.DateTimeField(null=True, blank=True)
    disetujui_oleh     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                         null=True, blank=True, related_name='laporan_mutu_disetujui')
    disetujui_pada     = models.DateTimeField(null=True, blank=True)
    terbit_pada        = models.DateTimeField(null=True, blank=True)
    catatan_verifikasi = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-tahun', '-bulan', '-semester']
        constraints = [
            models.UniqueConstraint(
                fields=['jenis', 'tahun', 'semester', 'bulan', 'scope', 'unit'],
                name='uniq_laporan_mutu_periode', nulls_distinct=True,
            ),
        ]
```

- [x] `LaporanMutuBaris` — one frozen row per indicator: `laporan` (FK, `related_name='baris'`), `indikator` (`SET_NULL`, kept only for the EP link), and the snapshot columns `kode`, `nama`, `jenis`, `unit_nama`, `numerator`, `denominator`, `satuan`, `arah`, `target` (Decimal 5,2), `nilai_capaian` (Decimal 10,2, `null`), `status_tercapai` (`BooleanField(null=True)`), `bulan_terisi` (smallint), then the analysis columns `analisis`, `tindak_lanjut` (TextField), and the per-row verification `status_verifikasi` (`BELUM`/`SETUJU`/`REVISI`), `verifikator` (FK user), `verifikasi_pada`, `catatan_verifikasi`.
- [x] `LaporanMutuSeksi` — narrative key/value per header (`laporan` FK `related_name='seksi'`, `kunci` CharField(40), `judul` CharField(120), `isi` TextField, `unique_together (laporan, kunci)`). Keys: `RINGKASAN_EKSEKUTIF`, `KENDALA`, `REKOMENDASI`, `BAB_I`…`BAB_VI`, `KESIMPULAN`, `PENUTUP`.
- [x] Model methods: `periode_label` (`Januari 2026` / `Semester I 2026` / `Tahun 2026`), `batas_waktu`, `terlambat`, `boleh_ubah` (`status == 'DRAF'`).
- [x] Migration + `manage.py makemigrations && manage.py migrate` locally. (Deploy does **not** run migrations — apply manually.)
- [x] Model tests: unique constraint rejects a second `BULANAN` for the same unit/periode; `nulls_distinct` allows two RS-scope reports with `unit=NULL` of different jenis.

### 3. Snapshot builder + create view

- [x] `akreditasi/mutu_laporan.py` → `build_baris(laporan, queryset)` with the period resolution:

```python
PERIODE_BULAN = {  # BULANAN → (bulan, tahun), SEMESTER → (bulan_awal..bulan_akhir), TAHUNAN → 1..12
}
```

- `BULANAN`: read `CatatanIndikator(indikator, bulan, tahun)` → `nilai_capaian`, `tercapai`.
- `SEMESTER` / `TAHUNAN`: `IndikatorMutu.agregat_capaian(tahun)` (or a new `agregat_capaian_rentang(tahun, bulan_mulai, bulan_akhir)` helper next to it that filters the same Sum over a month range — same formula, no new arithmetic) + `bulan_terisi`.
- Indicator set: `indikator_aktif_scoped(request.profile)` for `scope='UNIT'`, `IndikatorMutu.objects.filter(aktif=True)` for `scope='RS'`, grouped by `jenis_standar` so INM/IMRS/IMU render as three sections in the same order as the dashboard.
- Every row keeps the polarity: `arah=ind.arah_target`, `status_tercapai` from `CatatanIndikator.tercapai` / the range aggregate compared with the same MIN/MAX rule.
- [x] `laporan_mutu_create(request)` — GET shows the period picker (jenis, tahun, bulan/semester, scope) with `batas_waktu` previewed; POST builds the snapshot and redirects to detail. RBAC: `scope='RS'` requires `_is_manager_role(request.user)`; `scope='UNIT'` requires the user's unit scope (`unit_scope_ids`), else 403.
- [x] Tests: create monthly unit report → 36 INM + 98 IMRS + 76 IMU rows for a full-scope admin; a `KEPALA_UNIT` creates only its own/parent indicators; a `STAF_NAKES` gets 403; a second identical report POST returns the existing one with a message instead of raising.
- [x] Tests: freeze — after creation, change a `CatatanIndikator` value and assert the `LaporanMutuBaris` value is unchanged.

### 4. Detail view: analysis, PDSA, per-row verification

- [x] `laporan_mutu_detail(request, pk)` — renders the three-tier table exactly like Model A of the docx: `No | Kode | Indikator | N | D | Capaian | Target | Status | Analisa PDSA | Tindak Lanjut | PJ | Verifikasi`, plus Model B extras (trend mini-chart, kendala/rekomendasi sections) and Model C sections (BAB I–VI textareas) selected by `laporan.jenis`.
- [x] POST handler writes `analisis`/`tindak_lanjut`/`tindak_lanjut` only when `boleh_ubah`; otherwise redirect back with a `messages.warning` (`'Laporan sudah diverifikasi — ubah melalui proses revisi.'`). Never 500 on a locked report.
- [x] Missing-data note (deviation 6): compute `tanpa_pj` / `tanpa_ep` counts in the view, pass as context, print as an amber alert above the table.
- [x] Tests: edit on `DRAF` persists; edit on `TERBIT` does not (row value unchanged, 302, message present); RBAC — a `STAF_NAKES` from another unit gets 404, not 500.

### 5. Workflow L5 → L1

- [x] One constant in `mutu_laporan.py`:

```python
LEVEL_LAPORAN_MUTU = {          # docx BAB I — hierarki pelaporan
    'L5': ('STAF_NAKES',    'Pelaksana / PJ data'),
    'L4': ('KEPALA_UNIT',   'Kepala Unit — verifikator'),
    'L3': ('KOORDINATOR_POKJA', 'Komite Mutu — persetujuan I'),
    'L2': ('ADMIN_RS',      'Direksi — persetujuan II / penerbitan'),
    'L1': ('ASESOR',        'Dewan Pengawas — penerima laporan'),
}
APPROVER_L3 = ('KOORDINATOR_POKJA', 'ADMIN_RS', 'SUPER_ADMIN')
APPROVER_L2 = ('ADMIN_RS', 'SUPER_ADMIN')
```

- [x] `laporan_mutu_verifikasi(request, pk)` (L4) and `laporan_mutu_setujui(request, pk)` (L3/L2), each `@require_POST`, each writing the `*_oleh` / `*_pada` fields, an `AuditLog` line via the existing `_log()` helper (`indikator_views.py:115`), and rejecting an illegal jump (`DRAF → TERBIT` directly → 400 with a message naming the missing step).
- [x] `ASESOR` (L1) sees only `TERBIT` reports and has no action buttons — enforce in the view, not only by hiding them.
- [x] Tests: a full happy-path chain; each wrong-role attempt returns 403; illegal transition returns 400; `AuditLog` row count grows by one per transition; a verified report no longer accepts row edits.

### 6. Print layout (`templates/akreditasi/mutu_laporan_cetak.html`)

- [x] A4 print template, `{% extends %}` nothing (self-contained, like `cetak_dokumen.html`): kop surat from `RumahSakitProfile`, document number line, `periode_label`, the three-tier tables, the PDSA block per unachieved indicator (Plan/Do/Study/Act as four labeled paragraphs from `analisis` + `tindak_lanjut`), the IKP recap table (five rows incl. `KPC`), the lembar verifikasi/persetujuan with four signature columns (L4, L3, L2, L1) printing `diverifikasi_oleh.get_full_name` etc. and the date.
- [x] Trend chart for `SEMESTER`/`TAHUNAN`: Chart.js on screen (`/cetak` is print-only, so also provide the six-month/12-month table that the chart is drawn from — a chart is never the only carrier of the number).
- [x] `{% load l10n %}` before any JS, and `|unlocalize` on every float.
- [x] Tests: `cetak` returns 200 for each `jenis`; contains the header, one indicator kode, the signature labels; an `ASESOR` can print a `TERBIT` report; a `STAF_NAKES` gets 403 on an RS-scope report.

### 7. PDF export (reportlab)

- [x] `laporan_mutu_pdf(request, pk)` in `mutu_laporan.py`, modelled on `pasien/pdf_utils.py` (`_style`, `_kv_table`, `_text_box`); landscape A4 for the wide tables.
- [x] Trend chart as a real chart object, not a screenshot:

```python
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Line, String
```

Bar series = the six (or twelve) monthly `nilai_capaian`, plus a dashed horizontal `Line` at `target_nilai` labelled `Target ≥ 85%` (`≤` when `arah_target == 'MAX'`). No TeX, no float-to-string concatenation without formatting.
- [x] Tests: response is `application/pdf`, body starts with `%PDF`, and the same period/indicator kode text is reachable from the PDF's text layer.

### 8. Navigation + URLs

- [x] `akreditasi/urls.py`:

```python
path('laporan-mutu/', views.laporan_mutu_daftar, name='laporan_mutu_daftar'),
path('laporan-mutu/buat/', views.laporan_mutu_create, name='laporan_mutu_create'),
path('laporan-mutu/<int:pk>/', views.laporan_mutu_detail, name='laporan_mutu_detail'),
path('laporan-mutu/<int:pk>/cetak/', views.laporan_mutu_cetak, name='laporan_mutu_cetak'),
path('laporan-mutu/<int:pk>/pdf/', views.laporan_mutu_pdf, name='laporan_mutu_pdf'),
path('laporan-mutu/<int:pk>/verifikasi/', views.laporan_mutu_verifikasi, name='laporan_mutu_verifikasi'),
path('laporan-mutu/<int:pk>/setujui/', views.laporan_mutu_setujui, name='laporan_mutu_setujui'),
```

- [x] Thin wrappers in `akreditasi/views.py` re-exporting from `mutu_laporan` (matches how `indikator_views` is wired today).
- [x] `templates/includes/sidebar.html` — under the existing `Capaian Indikator Mutu & Renstra` section (`sidebar.html:247`), add a `Laporan Mutu` link with an active-state check that must not catch `indikator` pages (use `startswith 'laporan_mutu'`).

### 9. Data-quality + IKP recap polish

- [x] IKP recap helper `rekap_ikp(tahun)` → counts by `jenis_insiden` for the five documented values (adding `KPC`), grouped by month for the annual report, with `0` for categories that have no rows.
- [x] `KPC` added to the `InsidenKeselamatan` jenis choices with a `choices`-only migration; `tests_insiden.py` extended so a form still saves with the new choice.
- [x] Empty-state for `tahun` with no `CatatanIndikator` rows: report renders `Belum ada data capaian untuk tahun <n>` instead of 210 rows of dashes.

## Verification

- [x] `manage.py test akreditasi.tests_mutu_laporan akreditasi.tests_insiden` — RED first, GREEN after each task.
- [x] `manage.py test` — the whole suite (363 tests before this plan) must stay green; the capaian/polarity tests (`tests_evaluasi_indikator.py`) are the canary for accidental arithmetic changes.
- [x] `manage.py check` clean; `makemigrations --check --dry-run` reports no missing migration.
- [x] `collectstatic` and commit the hashed `staticfiles/` artifacts if any CSS/JS changed (tracked for the Vercel build).

## Deployment notes

- Apply the migration manually after deploy; the platform does not run migrations automatically.
- No new pip package — `reportlab` and `openpyxl` are already in `requirements.txt`.
- One migration (three new models + the `KPC` choice). No data backfill; the first report for any period builds its snapshot from whatever `CatatanIndikator` rows exist at that moment.

## Spec Compliance

| Requirement | Where implemented |
|---|---|
| Model A: unit monthly report, three indicator tiers | Task 2 (`LaporanMutu.scope='UNIT'`), Task 3 (grouped snapshot), Task 6 (print) |
| Model A: N, D, capaian, target, ✅/❌ | Task 3 snapshot columns, `CatatanIndikator.tercapai` |
| Model A: PDSA analysis for every unachieved indicator | Task 4 (`analisis` + `tindak_lanjut`, per-row, required by the table) |
| Model A: ≤ tgl 10 deadline | Task 1 helper + `terlambat` badge in Task 8 list view |
| Model B: executive summary, six-month trend + chart, kendala & rekomendasi | Task 4 sections (`RINGKASAN_EKSEKUTIF`, `KENDALA`, `REKOMENDASI`), Task 6/7 chart |
| Model C: six BAB, IKP recap, benchmarking | Task 4 (`BAB_I`…`BAB_VI`), Task 9 (`rekap_ikp`, `KPC`) |
| Model C: integrasi SIMRS percentage | Task 4 — a `LaporanMutuSeksi` numeric field rendered in BAB VI |
| Calendar: bulanan 10 / semesteran 20 Jul-Jan / tahunan 31 Jan | Task 1 |
| Five-tier verification & approval table | Task 5 (`LEVEL_LAPORAN_MUTU` + workflow + signature block) |
| Trend chart with target threshold line | Task 7 (reportlab) — screen chart already exists |
