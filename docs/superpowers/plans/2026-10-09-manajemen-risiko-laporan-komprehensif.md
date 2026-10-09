# Implementation Plan: Comprehensive Risk Management Report Page

**Source document:** `Buatkan menu tampilan manajemen resiko seperti ini.docx`
**New URL:** `/risiko/laporan/` (or `/risiko/laporan/<unit_id>/`)

---

## Problem Analysis

The user wants a dedicated **Manajemen Risiko Unit** report/display page that mirrors the document structure:
5 major sections, displayed as a rich per-unit dashboard covering the full risk management lifecycle:

```
Section 1: IDENTIFIKASI RISIKO — Masalah & Data grouped by Kategori
Section 2: ANALISIS RISIKO — Risk Score Matrix table (D × P = Skor)
Section 3: PENANGANAN / MITIGASI RISIKO — per-risk mitigation action list
Section 4: RENCANA AKSI (ACTION PLAN MATRIX) — table with PIC, timeline, cost, target
Section 5: PEMANTAUAN, ANALISIS, DAN TINDAK LANJUT — monitoring, KPIs, escalation
```

**Key insight:** All data already exists in `RisikoUnit` model. This is purely a **new view + template** that aggregates and presents the existing `RisikoUnit` records for a given unit in the structured 5-section report format. No new model or migration needed.

---

## Data Mapping (docx → RisikoUnit fields)

| Docx Section | RisikoUnit Field(s) |
|---|---|
| Kategori (A/B/C/D headers) | `kategori_risiko` |
| Masalah (Issue Statement) | `masalah` |
| Data / Bukti Pendukung | `data_pendukung` |
| Deskripsi Risiko Utama | `deskripsi_risiko` |
| D (Dampak) | `dampak` |
| P (Probabilitas) | `probabilitas` |
| Skor Risiko | `skor_inherent` (property = dampak × probabilitas) |
| Tingkat Risiko | `risk_level` property |
| Prioritas | ordering by `skor_inherent DESC` |
| Kode Risiko | auto-generate: `R-{KAT}-{id:02d}` from kategori + pk |
| Tindakan Pengendalian (Rencana Aksi) | `rencana_aksi` |
| PIC | `pj_mitigasi` |
| Target Waktu | `target_selesai` |
| Biaya | `biaya_mitigasi` |
| Target Capaian Indikator | `target_capaian_indikator` + `indikator_mutu_terkait` |
| Strategi Mitigasi | `strategi_mitigasi` |
| Status PDCA | `status` |
| Skor Residual (post-mitigasi) | `dampak_residual × probabilitas_residual` |

---

## Architecture

### New files to create:
1. `akreditasi/risiko_laporan_views.py` — view logic (or add to `risiko_views.py`)
2. `templates/akreditasi/risiko_laporan.html` — full 5-section report template

### Existing files to modify:
3. `akreditasi/urls.py` — add 2 new URL patterns
4. `templates/includes/sidebar.html` — add submenu link under "Manajemen Risiko"

---

## Detailed Tasks

### Task 1: Add View `risiko_laporan` in `akreditasi/risiko_views.py`

```python
# GET /risiko/laporan/          → filter by user's unit, or show unit selector for superadmin
# GET /risiko/laporan/<unit_id>/  → show report for specific unit
```

Logic:
- Accept query params: `?unit=<id>&tahun=2026&periode=TAHUNAN`
- Retrieve all `RisikoUnit` for the selected unit + filters
- Group by `kategori_risiko` for Section 1
- Order by `skor_inherent` descending for Section 2 (Risk Matrix table)
- Compute auto risk code: `R-{short_kat}-{rank:02d}` where short_kat maps KLINIS→KLN, OPERASIONAL→OPS, FINANSIAL→FIN, REPUTASI→REP, HUKUM_KEPATUHAN→HKM, FASILITAS_LINGKUNGAN→FAL
- Compute monitoring summary (counts by status, KPIs from `indikator_mutu_terkait`)
- Pass `unit`, `tahun`, `periode`, `units` (for filter selector), `risiko_list`, `grouped_by_kategori`, `ranked_with_kode`, `scoring_standar`, `kpi_list` to template

### Task 2: Create Template `templates/akreditasi/risiko_laporan.html`

**Header:**
- Title: "MANAJEMEN RISIKO UNIT {unit.name}" + RS name + periode
- Subtitle: "STANDAR STARKES 2026 — ARIMA"
- Filter bar: unit selector (superadmin only), tahun, periode, Print/Export button

**Section 1 — IDENTIFIKASI RISIKO (MASALAH & DATA BUKTI PENDUKUNG):**
- Sub-header: "Matriks Identifikasi Risiko Berdasarkan Kategori:"
- For each kategori group (KLINIS → A, OPERASIONAL → B, PPI/FASILITAS → C, FINANSIAL/HUKUM → D):
  - Show kategori label as bold header (e.g., "A. Masalah dan Data & Keselamatan Pasien")
  - For each risiko in group: render bulleted list of `masalah` + `data_pendukung` items
  - Use colored left-border cards per kategori (danger=KLINIS, primary=OPS, teal=PPI, warning=HUKUM)

**Section 2 — ANALISIS RISIKO DAN PENETAPAN PRIORITAS (RISK SCORE MATRIX):**
- Scoring legend: D 1–5, P 1–5, Skor = D×P, warna Hijau/Kuning/Oranye/Merah
- Table columns: No | Kode Risiko | Deskripsi Risiko | D | P | Skor | Tingkat | Prioritas
- Rows sorted by skor_inherent DESC, colored by risk level
- If `dampak_residual` filled: show residual skor in parentheses

**Section 3 — PENANGANAN / MITIGASI RISIKO:**
- For each risk (by kode): show kode + jenis_risiko as bold header
- Render `rencana_aksi` as bullet-point list (split by newline)
- Show `strategi_mitigasi` badge

**Section 4 — RENCANA AKSI (ACTION PLAN MATRIX):**
- Table: No | Tindakan | PIC | Target Waktu | Sumber Daya | Biaya | Target Capaian
- Map from: `rencana_aksi.split('\n')[0]` | `pj_mitigasi` | `target_selesai` | — | `biaya_mitigasi` | `target_capaian_indikator` + indikator name

**Section 5 — PEMANTAUAN, ANALISIS, DAN TINDAK LANJUT:**
- A. Mekanisme Pemantauan: static content (harian/mingguan/bulanan framework)
- B. KPI Indikator: list from `indikator_mutu_terkait` with capaian target
- C. Tindak Lanjut: static content + escalation criteria
- Status summary: count by PDCA status (badge pills for IDENTIFIKASI/PLAN/DO/EVALUASI/SELESAI)

**Print / Export:**
- `window.print()` button → CSS `@media print` hides sidebar/navbar/filter, shows full 5-section report as clean A4 document

### Task 3: URL Patterns in `akreditasi/urls.py`

```python
path('risiko/laporan/',             views.risiko_laporan, name='risiko_laporan'),
path('risiko/laporan/<int:unit_id>/', views.risiko_laporan, name='risiko_laporan_unit'),
```

### Task 4: Sidebar Entry in `templates/includes/sidebar.html`

Add under "Manajemen Risiko" section:
```html
<a href="{% url 'akreditasi:risiko_laporan' %}" class="nav-link ...">
    <span class="nav-icon"><i class="bi bi-file-earmark-bar-graph-fill"></i></span>
    <span class="nav-text">
        <span class="nav-title">Laporan Manajemen Risiko</span>
        <span class="nav-desc">5-Seksi STARKES 5.15</span>
    </span>
</a>
```

### Task 5: Test + Deploy

- Add 2 tests to `akreditasi/tests_manajemen_risiko_515.py`:
  - `test_risiko_laporan_get_200` — GET `/risiko/laporan/` returns 200
  - `test_risiko_laporan_unit_filter` — GET `/risiko/laporan/?unit=X&tahun=2026` contains sections
- Run full test suite `manage.py test`
- Git commit + push → Vercel auto-deploy

---

## Execution Order

1. Add view function `risiko_laporan` to `risiko_views.py`
2. Add URL patterns to `urls.py`
3. Create `risiko_laporan.html` template (5 sections)
4. Add sidebar link
5. Add + run tests
6. Commit + push + verify live

---

## Constraints

- No new model / migration needed — all data already in `RisikoUnit`
- Auto-generate risk codes (R-KLN-01 etc.) in view context, not stored
- Print CSS: sidebar hidden, full-width A4 landscape for section 2 table
- Risk code prefix map: KLINIS→KLN, OPERASIONAL→OPS, FINANSIAL→FIN, REPUTASI→REP, HUKUM_KEPATUHAN→HKM, FASILITAS_LINGKUNGAN→FAL, MANAJERIAL→MAN
- Empty state: if no `RisikoUnit` for selected unit, show empty-state card per section
- superadmin sees all units; KEPALA_UNIT sees only their unit (reuse `_collect_ids` from `risiko_daftar`)
