# Modul Logbook Harian Unit Diklat & Rekapitulasi Kinerja (Bulanan, Tahunan, 5 Tahunan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-AGENT EXECUTION PATTERN:
> 1. You MUST operate strictly in TDD cycle (Red-Green-Refactor).
> 2. Execute tests using `.venv/Scripts/python manage.py test <test_label> --keepdb`.
> 3. Never introduce new external dependencies. Use existing Django ORM, Bootstrap 5.3.3, and standard library.
> 4. Keep all test suites passing without regressions.

**Goal:** Implement the specialized daily logbook workflow for hospital education and training (Unit Diklat / Diklit) and non-medical units based on `logbook untuk unit Diklat.docx` with all 9 gap closures:
1. Auto-login read-only staff executor identity (`pelaksana_nama`) and unit selector.
2. Structured daily activity table with time intervals (`jam_mulai` - `jam_selesai`), master data activity selection (13 standardized Diklat activities), freeform editable activity details, per-row direct document evidence upload (`dokumen_bukti`, `nama_bukti`), and automatic STARKES EP linking (`KPS 8`, `KPS 8.1`, `TKRS 9`, `IPKP 1-3`, `PPI`, `SKP`, `MFK`).
3. JavaScript auto-fill interaction: selecting a master activity auto-fills default operational details into the editable textarea and sets the STARKES EP badge.
4. Comprehensive aggregation and performance evaluation dashboard with 4 tabs:
   - Monthly recap: days worked, total hours, activity counts, head of unit validation, and incentive / remuneration baseline recommendation.
   - Annual recap: cumulative training hours per staff (20 JPL threshold), mandatory training compliance (BHD, PPI, K3RS, SKP), and SKP/DP3 & SPMI internal audit alignment.
   - 5-Year accreditation cycle recap: 5-year staff competency growth trend, 5-year unit risk & mitigation registry, and digital surveyor evidence portfolio categorized by STARKES EP.
   - Integrated Control Dashboard & Staff KPI: automated composite performance scoring ($0 - 100$) based on quantity (30%), on-time filing (25%), evidence completeness (25%), and EP match (20%).
5. Integration into executive `/control/` (Hospital Integrated Control Hub & Navigation) allowing unit heads and directors to view Diklat productivity and 5-year trends.
6. Detailed PDF printout for itemized daily activities and monthly/annual staff performance summaries.

**Architecture:**
- **App**: `akreditasi`
- **Models**:
  - `MasterAktivitasNonMedis`: Standardized operational activities with `kode`, `kategori_unit` (default `'DIKLAT'`), `nama`, `deskripsi`, `ep_rekomendasi`, `standar_terkait`, and `urutan`.
  - `AktivitasNonMedis`: Child entity of `LogbookNonMedis` with `logbook`, `master`, `urutan`, `jam_mulai`, `jam_selesai`, `nama_aktivitas`, `detail_uraian` (editable), `ep_starkes`, `pelaksana_nama`, `dokumen_bukti`, `nama_bukti`.
  - `LogbookNonMedis` (extended): `jam_mulai`, `jam_selesai`, computed properties for total duration, completeness, EP adherence, on-time filing rate, and KPI score.
- **Service**:
  - `akreditasi/services/diklat_rekap.py`: Aggregation engine for monthly, annual, 5-year accreditation cycles, and weighted staff performance scoring.
- **Views**:
  - `logbook_nonmedis_buat`: Enforces read-only logged-in user binding and default unit assignment.
  - `logbook_nonmedis_detail`: Enhanced with dynamic interactive activity table (modal/inline add, edit, delete, auto-fill template & EP from master, per-row file upload).
  - `logbook_nonmedis_rekap`: Multi-tab aggregation dashboard (Monthly, Annual, 5-Year Cycle, KPI Dashboard).
  - `logbook_nonmedis_pdf`: Upgraded PDF template rendering itemized activities and monthly performance summary.
- **Executive Navigation**:
  - Add Diklat logbook / KPI action link to `akreditasi/kontrol_navigation.py` and `akreditasi/kontrol_views.py`.
- **Tech Stack**: Python 3.14 / Django 5.x, SQLite/PostgreSQL (Supabase), Bootstrap 5.3.3, Vanilla JS.

---

## Global Constraints
- Python binary: Always use `.venv/Scripts/python`.
- Test command: `.venv/Scripts/python manage.py test <target> --keepdb`.
- Database migrations: Versioned migrations under `akreditasi/migrations/`.
- Styling: Bootstrap 5.3.3 classes matching existing ARIMA light/dark theme.
- Communication: Plan in English, user interaction in Bahasa Indonesia.

---

## Review Focus
- **Input Validation & Integrity**: Ensuring time ranges (`jam_mulai` <= `jam_selesai`) and non-empty activity names.
- **Authorization & Immutability**: `pelaksana_nama` must strictly resolve to the authenticated user and cannot be spoofed in POST payloads.
- **STARKES Alignment**: Verified lookup against `StandardItem` for KPS 8, KPS 8.1, TKRS 9, and IPKP 1-3.
- **Performance & Aggregation**: Efficient ORM queries with `select_related` and `prefetch_related` avoiding N+1 overhead during multi-year aggregations.

---

## Bite-Sized Implementation Tasks

### Task 1: Model `MasterAktivitasNonMedis` & Child Model `AktivitasNonMedis` with Per-Row Proof Upload & Time Range
- **File**: `akreditasi/logbook_nonmedis_models.py`
- **Tests**: `akreditasi/tests_diklat_models.py`
- **Step 1 (Red)**: Write unit tests verifying creation, foreign key constraints, file upload handling, and ordering of `MasterAktivitasNonMedis` and `AktivitasNonMedis`.
- **Step 2**: Run test to verify failure (`.venv/Scripts/python manage.py test akreditasi.tests_diklat_models --keepdb`).
- **Step 3 (Green)**: Implement `MasterAktivitasNonMedis` and `AktivitasNonMedis` in `akreditasi/logbook_nonmedis_models.py`, register in `akreditasi/models.py`. Add `jam_mulai` and `jam_selesai` to `LogbookNonMedis`.
- **Step 4**: Generate and execute migration (`0060_master_aktivitas_nonmedis_and_child.py`).
- **Step 5**: Run test to verify pass.
- **Step 6**: Commit `feat(diklat): master aktivitas non-medis and aktivitas logbook child model with per-row proof upload`.

### Task 2: Management Command Seeder for 13 Verbatim Diklat Activities
- **File**: `akreditasi/management/commands/seed_master_aktivitas_diklat.py`
- **Tests**: `akreditasi/tests_diklat_seeder.py`
- **Step 1 (Red)**: Write unit tests asserting that running the command populates exactly 13 active activities for category `'DIKLAT'` with accurate descriptions and EP recommendations (KPS 8, KPS 8.1, TKRS 9, IPKP 1-3) and is idempotent.
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Implement `seed_master_aktivitas_diklat.py` containing the 13 catalog items from `logbook untuk unit Diklat.docx`.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): seeder 13 master aktivitas harian unit diklat`.

### Task 3: Performance Scoring Formula & Logbook Metrics Properties
- **File**: `akreditasi/logbook_nonmedis_models.py`
- **Tests**: `akreditasi/tests_diklat_scoring.py`
- **Step 1 (Red)**: Write unit tests calculating:
  - `durasi_jam`: difference between `jam_mulai` and `jam_selesai`.
  - `total_jam_aktivitas`: sum of activity durations for a logbook.
  - `kelengkapan_bukti_persen`: percentage of activities having evidence attached.
  - `kepatuhan_ep_persen`: percentage of activities with non-empty EP link.
  - `skor_ketepatan_waktu`: 100 for same-day submission, 70 for 1-2 days, 40 for >= 3 days.
  - `skor_kinerja_harian`: weighted calculation (30% quantity, 25% on-time submission, 25% evidence, 20% EP match).
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Implement properties and helper methods on `AktivitasNonMedis` and `LogbookNonMedis`.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): calculation helper methods and performance scoring formula`.

### Task 4: Form View Auto-Pelaksana & Read-Only Identity Enforcement
- **File**: `akreditasi/logbook_nonmedis.py`, `templates/akreditasi/logbook_nonmedis_form.html`
- **Tests**: `akreditasi/tests_diklat_form_views.py`
- **Step 1 (Red)**: Write test verifying `logbook_nonmedis_buat`:
  - Enforces `pelaksana_nama` derived from `request.user.get_full_name()` or `pegawai_hc`.
  - Rejects attempts to forge another user's name in POST payload.
  - Renders read-only badge/display of executor name in HTML form.
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Update `logbook_nonmedis_buat` view and `templates/akreditasi/logbook_nonmedis_form.html` to lock the executor to current session user.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): auto-login read-only executor identity on logbook creation`.

### Task 5: Dynamic Itemized Activities CRUD in Logbook Detail View with Auto-Fill JS
- **File**: `akreditasi/logbook_nonmedis.py`, `templates/akreditasi/logbook_nonmedis_detail.html`, `akreditasi/urls.py`
- **Tests**: `akreditasi/tests_diklat_detail_crud.py`
- **Step 1 (Red)**: Write tests for endpoints:
  - `POST /logbook-nonmedis/<pk>/tambah-aktivitas/`: Adds a new activity row with master template resolution, start/end time, and file upload.
  - `POST /logbook-nonmedis/<pk>/hapus-aktivitas/<aktivitas_id>/`: Deletes an activity row.
  - Permission checks: only owner or unit head can modify draft logbook activities.
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Implement views in `logbook_nonmedis.py`, update URLs, and inject interactive table markup into `logbook_nonmedis_detail.html` with JavaScript auto-fill for operational details and EP badges upon selecting master data.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): interactive daily activity table with master auto-fill and evidence upload`.

### Task 6: Aggregation Engine Service (Monthly, Annual, 5-Year Cycle & Staff KPI)
- **File**: `akreditasi/services/diklat_rekap.py`
- **Tests**: `akreditasi/tests_diklat_rekap_service.py`
- **Step 1 (Red)**: Write tests verifying aggregation functions:
  - `rekap_bulanan(unit, bulan, tahun)`: aggregates days worked, activities count, hours worked, activity category distribution, approval rate, incentive tier.
  - `rekap_tahunan(unit, tahun)`: aggregates total training hours per staff against 20 JPL threshold, mandatory training checklist (BHD, PPI, K3RS, SKP), and annual program realization for SKP/SPMI.
  - `rekap_lima_tahunan(unit, tahun_mulai, tahun_selesai)`: aggregates 5-year accreditation cycle metrics, risk & mitigation timeline, and STARKES EP evidence portfolio.
  - `hitung_skor_kinerja_staf(unit, bulan, tahun)`: ranks staff by composite KPI score with descriptive predicates (Sangat Baik / Baik / Cukup / Kurang).
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Implement service methods in `akreditasi/services/diklat_rekap.py`.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): aggregation engine for monthly, annual, 5-year cycles and staff KPIs`.

### Task 7: Comprehensive Rekapitulasi & Integrated Control Dashboard View
- **File**: `akreditasi/logbook_nonmedis.py`, `templates/akreditasi/logbook_nonmedis_rekap.html`, `akreditasi/urls.py`
- **Tests**: `akreditasi/tests_diklat_rekap_views.py`
- **Step 1 (Red)**: Write tests verifying:
  - Access to `/logbook-nonmedis/rekap/` returns HTTP 200 for staff and unit leaders.
  - Tab navigation renders all 4 sections (Monthly, Annual, 5-Year Cycle, Performance Control).
  - Filters by unit, employee, year, and month appropriately scope the results.
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Implement `logbook_nonmedis_rekap` view, author `templates/akreditasi/logbook_nonmedis_rekap.html`, register URL route.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): multi-tab aggregation and integrated control dashboard UI`.

### Task 8: Enhanced PDF Output for Daily Activities and Monthly Staff Summary
- **File**: `akreditasi/logbook_nonmedis.py`, `templates/akreditasi/logbook_nonmedis_pdf.html`
- **Tests**: `akreditasi/tests_diklat_pdf.py`
- **Step 1 (Red)**: Write tests asserting:
  - Daily logbook PDF renders table with sequential time rows, master name, custom details, proof, and EP badges.
  - Monthly summary export endpoint returns valid application/pdf with staff performance score and incentive tier.
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Update PDF view and template to support activity table and monthly summary.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): pdf export for itemized daily logbook and monthly summary`.

### Task 9: Integrated Control Link, Sidebar Integration, End-to-End Regression & Vercel Verification
- **File**: `akreditasi/kontrol_navigation.py`, `akreditasi/kontrol_views.py`, `templates/includes/sidebar.html`
- **Step 1**: Add Diklat Logbook and Performance KPI shortcut to `kontrol_navigation.py` under the appropriate portal (Dokumen/Human Capital).
- **Step 2**: Add "Rekap Kinerja Unit" menu item under Logbook Non-Medis section in the sidebar.
- **Step 3**: Run all test suites: `.venv/Scripts/python manage.py test akreditasi --keepdb` and verify 100% pass.
- **Step 4**: Run `.venv/Scripts/python manage.py collectstatic --noinput`.
- **Step 5**: Commit and push to `origin/master`.
- **Step 6**: Verify Vercel deployment health via curl.
- **Step 7**: Commit `feat(diklat): complete integration of logbook diklat and performance aggregation`.
