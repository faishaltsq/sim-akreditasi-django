# Modul Logbook Harian Unit Diklat & Rekapitulasi Kinerja (Bulanan, Tahunan, 5 Tahunan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-AGENT EXECUTION PATTERN:
> 1. You MUST operate strictly in TDD cycle (Red-Green-Refactor).
> 2. Execute tests using `.venv/Scripts/python manage.py test <test_label> --keepdb`.
> 3. Never introduce new external dependencies. Use existing Django ORM, Bootstrap 5.3.3, and standard library.
> 4. Keep all test suites passing without regressions.

**Goal:** Implement the specialized daily logbook workflow for hospital education and training (Unit Diklat / Diklit) and non-medical units based on `logbook untuk unit Diklat.docx`. This includes:
1. Auto-login read-only staff executor identity (`pelaksana_nama`) and unit selector.
2. Structured daily activity table with time intervals (`jam_mulai` - `jam_selesai`), master data activity selection (13 standardized Diklat activities), freeform editable activity details, document evidence attachment, and automatic STARKES EP linking (KPS 8, KPS 8.1, TKRS 9, IPKP 1-3, PPI, SKP, MFK).
3. Comprehensive aggregation and performance evaluation dashboard with 4 tabs: Monthly recap (incentive/remuneration baseline), Annual recap (training hours & mandatory training compliance), 5-Year accreditation cycle recap (surveyor evidence portfolio & risk-mitigation trends), and Integrated Control Leadership Dashboard with automated staff KPI scoring (0-100).
4. Detailed daily activity printing and monthly performance summary export in PDF format.

**Architecture:**
- **App**: `akreditasi`
- **Models**:
  - `MasterAktivitasNonMedis`: Catalogs standardized operational activities with code, category/unit, name, standard operational description, recommended STARKES EP, and sort order.
  - `AktivitasNonMedis`: Child entity of `LogbookNonMedis` storing sequential activity rows with start/end time, master reference, activity title, editable custom description, linked EP code, and attached proof document.
  - `LogbookNonMedis` (extended): Auto-computed KPI score, total duration, evidence completeness, and EP compliance rate.
- **Service**:
  - `akreditasi/services/diklat_rekap.py`: Aggregation engine for monthly, annual, 5-year accreditation cycles, and weighted staff performance scoring:
    $$\text{Skor Kinerja} = (\text{Kuantitas} \times 30\%) + (\text{Ketepatan Waktu} \times 25\%) + (\text{Kelengkapan Bukti} \times 25\%) + (\text{Kepatuhan EP} \times 20\%)$$
- **Views**:
  - `logbook_nonmedis_buat`: Enhanced with read-only logged-in user binding and default unit assignment.
  - `logbook_nonmedis_detail`: Enhanced with dynamic interactive activity table (modal/inline add, edit, delete, auto-fill template & EP from master).
  - `logbook_nonmedis_rekap`: Multi-tab aggregation dashboard (Monthly, Annual, 5-Year Cycle, KPI Dashboard).
  - `logbook_nonmedis_pdf`: Upgraded PDF template rendering itemized activities.
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

### Task 1: Model `MasterAktivitasNonMedis` & Child Model `AktivitasNonMedis`
- **File**: `akreditasi/logbook_nonmedis_models.py`
- **Tests**: `akreditasi/tests_diklat_models.py`
- **Step 1 (Red)**: Write unit tests verifying creation, foreign key constraints, and ordering of `MasterAktivitasNonMedis` and `AktivitasNonMedis`.
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Implement `MasterAktivitasNonMedis` and `AktivitasNonMedis` in `akreditasi/logbook_nonmedis_models.py`, register in `akreditasi/models.py`.
- **Step 4**: Generate and execute migration (`0060_master_aktivitas_nonmedis_and_child.py`).
- **Step 5**: Run test to verify pass.
- **Step 6**: Commit `feat(diklat): master aktivitas non-medis and aktivitas logbook child model`.

### Task 2: Management Command Seeder for 13 Standard Diklat Activities
- **File**: `akreditasi/management/commands/seed_master_aktivitas_diklat.py`
- **Tests**: `akreditasi/tests_diklat_seeder.py`
- **Step 1 (Red)**: Write unit tests asserting that running the command populates exactly 13 active activities for category `'DIKLAT'` with accurate EP recommendations (KPS 8, KPS 8.1, TKRS 9, IPKP 1-3) and is idempotent.
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Implement `seed_master_aktivitas_diklat.py` containing the 13 catalog items from `logbook untuk unit Diklat.docx`.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): seeder 13 master aktivitas harian unit diklat`.

### Task 3: Performance Scoring & Logbook Metrics Properties
- **File**: `akreditasi/logbook_nonmedis_models.py`
- **Tests**: `akreditasi/tests_diklat_scoring.py`
- **Step 1 (Red)**: Write unit tests calculating:
  - `durasi_jam`: difference between `jam_mulai` and `jam_selesai`.
  - `total_jam_aktivitas`: sum of activity durations for a logbook.
  - `kelengkapan_bukti_persen`: percentage of activities having evidence attached.
  - `kepatuhan_ep_persen`: percentage of activities with non-empty EP link.
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

### Task 5: Dynamic Itemized Activities CRUD in Logbook Detail View
- **File**: `akreditasi/logbook_nonmedis.py`, `templates/akreditasi/logbook_nonmedis_detail.html`, `akreditasi/urls.py`
- **Tests**: `akreditasi/tests_diklat_detail_crud.py`
- **Step 1 (Red)**: Write tests for endpoints:
  - `POST /logbook-nonmedis/<pk>/tambah-aktivitas/`: Adds a new activity row with master template resolution.
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
  - `rekap_bulanan(unit, bulan, tahun)`: aggregates days worked, activities count, hours worked, activity category distribution, approval rate.
  - `rekap_tahunan(unit, tahun)`: aggregates total training hours per staff against 20 JPL threshold, mandatory training checklist (BHD, PPI, K3RS, SKP), and annual program realization.
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
  - Monthly summary export endpoint returns valid application/pdf.
- **Step 2**: Run test to verify failure.
- **Step 3 (Green)**: Update PDF view and template to support activity table and monthly summary.
- **Step 4**: Run test to verify pass.
- **Step 5**: Commit `feat(diklat): pdf export for itemized daily logbook and monthly summary`.

### Task 9: Sidebar Integration, End-to-End Regression & Vercel Verification
- **File**: `templates/includes/sidebar.html`
- **Step 1**: Add "Rekap Kinerja Unit" menu item under Logbook Non-Medis section in the sidebar.
- **Step 2**: Run all test suites: `.venv/Scripts/python manage.py test akreditasi --keepdb` and verify 100% pass.
- **Step 3**: Run `.venv/Scripts/python manage.py collectstatic --noinput`.
- **Step 4**: Commit and push to `origin/master`.
- **Step 5**: Verify Vercel deployment health via curl.
- **Step 6**: Commit `feat(diklat): complete integration of logbook diklat and performance aggregation`.
