# Alur Integrasi Indikator Mutu (INM, IMRS, IMU) & Renstra Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the hierarchical integration workflow where Hospital Strategic Goals (Renstra) drive three tiers of Quality Indicators (INM, IMRS, IMU), visualized via interactive trend & comparison charts, with an automated trigger generating Risk Register entries and PDCA action items when indicator targets are missed.

**Architecture:**
1. **Indicator Classification**: Standardize `IndikatorMutu.JENIS_CHOICES` to clean 3-tier codes (`INM` = Nasional, `IMRS` = Rumah Sakit / Prioritas, `IMU` = Unit Kerja).
2. **Renstra Alignment**: Link indicators to Strategic Objectives (SS / `RenstraRoadmap` / `RenstraFokusItem`).
3. **Automated Risk & PDCA Trigger**: Hook on `CatatanIndikator` save — if actual achievement (`nilai_capaian`) < target, auto-generate a draft `Risiko` (Risk Register) with pre-filled root cause context and an initial PDCA item.
4. **Enhanced Visualizations**:
   - Real-time / monthly trend line charts with explicit dashed target lines.
   - Unit comparison bar charts (colored green $\ge$ target, red < target) with click-through actions to the RCA/PDCA view.
5. **Quality & Evidence Export**: Auto-tagging of achieved indicators as verified RDWOS evidence for accreditation standards.

**Tech Stack:** Django 5.x, SQLite/PostgreSQL, Chart.js / ApexCharts, Bootstrap 5.3, Django Test Runner.

**Spec:** `Downloads/tambahan grafik mengenai Alur Integrasi Indikator Mutu.docx`

## Global Constraints
- Python 3.11+ / Django 5.x.
- All secrets and API keys remain in backend environment variables (`settings.py`), never exposed to clients.
- Multi-tenant data isolation: Each unit accesses only their respective `IMU` while `INM` and `IMRS` remain hospital-wide.
- All tests must pass: `python manage.py test akreditasi`.
- Strictly backward compatible: existing `IndikatorMutu` records with legacy choices (`IMP_RS`, `IMP_UNIT`, `NASIONAL`) must be seamlessly migrated without data loss.

## Review Focus
1. Backward compatibility: existing indicator records must cleanly map `NASIONAL` -> `INM`, `IMP_RS` -> `IMRS`, `IMP_UNIT` -> `IMU`.
2. Target directionality: some indicators are "the lower the better" (e.g., patient falls = 0%, waiting time $\le$ 30 min) while others are "the higher the better" (hand hygiene $\ge$ 85%). The threshold logic must account for `arah_target` (MINIMAL vs MAKSIMAL).
3. Risk duplicate prevention: auto-creating a Risk Register draft must not generate duplicate risk entries if an indicator fails in consecutive months.
4. Unit permission scoping: unit users should only view/edit their own IMU indicators and PDCA actions.
5. Chart responsiveness: the unit comparison and trend charts must scale properly on mobile and desktop viewports.

---

### Task 1: Update Data Model for Indicator Types & Target Direction

**Files:**
- Modify: `akreditasi/risiko_models.py`
- Create migration: `akreditasi/migrations/00XX_indikator_mutu_renstra_integration.py`
- Test: `akreditasi/tests_indikator_alur_integrasi.py`

**Interfaces:**
- `IndikatorMutu.JENIS_CHOICES`: `('INM', 'Indikator Nasional Mutu (INM)'), ('IMRS', 'Indikator Mutu Rumah Sakit (IMRS)'), ('IMU', 'Indikator Mutu Unit (IMU)')`
- `IndikatorMutu.ARAH_CHOICES`: `('MAX', 'Maksimal / Lebih Rendah Lebih Baik (≤ Target)'), ('MIN', 'Minimal / Lebih Tinggi Lebih Baik (≥ Target)')`
- Field `arah_target`: CharField default `'MIN'`
- Field `sasaran_strategis`: ForeignKey to `RenstraRoadmap` (or CharField code `SS-1`, `SS-2`, etc.)

- [ ] **Step 1: Write the failing tests**
Create `akreditasi/tests_indikator_alur_integrasi.py` testing the 3-tier indicator types, `arah_target` logic in `CatatanIndikator.tercapai`, and Renstra linkage.

- [ ] **Step 2: Run test to verify it fails**
Run: `python manage.py test akreditasi.tests_indikator_alur_integrasi`
Expected: FAIL (missing fields or methods)

- [ ] **Step 3: Update `IndikatorMutu` and `CatatanIndikator` in `akreditasi/risiko_models.py`**
Add `arah_target`, update `JENIS_CHOICES` with fallback compatibility, update `CatatanIndikator.tercapai` property to evaluate based on `arah_target` (if `MIN`: `nilai >= target`, if `MAX`: `nilai <= target`).

- [ ] **Step 4: Create and apply Django migration**
Run: `python manage.py makemigrations akreditasi` and `python manage.py migrate`

- [ ] **Step 5: Run tests to verify they pass**
Run: `python manage.py test akreditasi.tests_indikator_alur_integrasi`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add akreditasi/risiko_models.py akreditasi/migrations/* akreditasi/tests_indikator_alur_integrasi.py
git commit -m "feat(mutu): standardize INM, IMRS, IMU indicator tiers and target direction"
```

---

### Task 2: Implement Automated Risk Register & PDCA Trigger on Failed Targets

**Files:**
- Modify: `akreditasi/risiko_models.py` (or signal in `akreditasi/signals.py`)
- Modify: `akreditasi/forms.py`
- Test: `akreditasi/tests_indikator_alur_integrasi.py`

**Interfaces:**
- Hook: On `CatatanIndikator.save()` when `tercapai == False`
- Logic: Check if draft `Risiko` already exists for this `(indikator, tahun, periode)`. If not, create a `Risiko` instance with:
  - `status = 'DRAFT'`
  - `masalah = f"Capaian {indikator.nama_indikator} di bawah target ({nilai_capaian:.1f}% vs {indikator.target_nilai}%)"`
  - `jenis_risiko = "Risiko Kegagalan Mutu & Layanan"`
  - `rencana_aksi = indikator.rencana_aksi or "Lakukan analisis akar masalah (Fishbone/5-Why) dan susun PDCA"`
  - `indikator_mutu_terkait = indikator`
  - `unit = indikator.unit`

- [ ] **Step 1: Write test for automated risk generation**
Test in `akreditasi/tests_indikator_alur_integrasi.py` checking that inputting a failing `CatatanIndikator` automatically creates a corresponding `Risiko` entry, and doesn't duplicate if saved again.

- [ ] **Step 2: Run test to verify it fails**
Run: `python manage.py test akreditasi.tests_indikator_alur_integrasi::test_auto_risk_trigger`
Expected: FAIL

- [ ] **Step 3: Implement post-save logic in `CatatanIndikator.save`**
Add automatic draft risk trigger with idempotency check.

- [ ] **Step 4: Run test to verify it passes**
Run: `python manage.py test akreditasi.tests_indikator_alur_integrasi::test_auto_risk_trigger`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add akreditasi/risiko_models.py akreditasi/tests_indikator_alur_integrasi.py
git commit -m "feat(mutu): auto-trigger risk register and PDCA action when indicator fails target"
```

---

### Task 3: Build Trend Line & Unit Comparison Chart Views

**Files:**
- Modify: `akreditasi/indikator_views.py`
- Modify: `akreditasi/views.py`
- Create template component: `templates/akreditasi/partials/chart_indikator_tren.html`
- Create template component: `templates/akreditasi/partials/chart_indikator_komparasi_unit.html`
- Test: `akreditasi/tests_indikator_alur_integrasi.py`

**Interfaces:**
- `indikator_tren_json(request, indikator_id)`: returns JSON series of monthly achievements and target line for Chart.js.
- `indikator_komparasi_unit_json(request, jenis='IMU')`: returns unit-by-unit achievements compared to RS target.

- [ ] **Step 1: Write API/View tests**
Test that trend JSON and comparison JSON endpoints return correct datasets, threshold lines, and color statuses (`green` for $\ge$ target, `red` for < target).

- [ ] **Step 2: Run test to verify it fails**
Run: `python manage.py test akreditasi.tests_indikator_alur_integrasi::test_chart_data_endpoints`
Expected: FAIL

- [ ] **Step 3: Implement view logic in `indikator_views.py`**
Add helper methods calculating achievement percentages, threshold flags, and target series.

- [ ] **Step 4: Run test to verify it passes**
Run: `python manage.py test akreditasi.tests_indikator_alur_integrasi::test_chart_data_endpoints`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add akreditasi/indikator_views.py akreditasi/urls.py akreditasi/tests_indikator_alur_integrasi.py
git commit -m "feat(mutu): add trend and unit comparison chart endpoints"
```

---

### Task 4: Enhance Dashboard UI with Interactive Tabs (INM, IMRS, IMU) & Bar Click Actions

**Files:**
- Modify: `templates/akreditasi/indikator_mutu_dashboard.html`
- Modify: `templates/akreditasi/indikator_detail.html`
- Test: `akreditasi/tests_indikator_alur_integrasi.py`

**Interfaces:**
- 3 distinct tabs or filter pills:
  1. `INM (Nasional)`
  2. `IMRS (Strategis RS)`
  3. `IMU (Unit Kerja)`
- Chart cards showing real-time trend line with warning badges.
- Unit comparison bar chart with click listener: clicking a red bar redirects directly to the Risk Register / PDCA entry for that unit & indicator.

- [ ] **Step 1: Write template test checking rendered tabs and charts**
Verify template contains tab elements for INM, IMRS, and IMU, and embeds Chart.js canvas with appropriate data attributes.

- [ ] **Step 2: Run test to verify it fails**
Run: `python manage.py test akreditasi.tests_indikator_alur_integrasi::test_dashboard_ui_elements`
Expected: FAIL

- [ ] **Step 3: Update `indikator_mutu_dashboard.html`**
Implement the visual layout according to the spec: Renstra header banner, INM/IMRS/IMU filter pills, interactive Chart.js line and bar charts with click-through navigation to PDCA/Fishbone.

- [ ] **Step 4: Run test to verify it passes**
Run: `python manage.py test akreditasi.tests_indikator_alur_integrasi::test_dashboard_ui_elements`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add templates/akreditasi/indikator_mutu_dashboard.html akreditasi/tests_indikator_alur_integrasi.py
git commit -m "feat(mutu): interactive INM/IMRS/IMU dashboard with click-to-PDCA navigation"
```

---

### Task 5: End-to-End Verification & Production Migration

**Files:**
- Verify: Full test suite (`python manage.py test`)
- Run production database migration on Supabase.
- Test production deployment via Vercel.

- [x] **Step 1: Run full test suite**
  Run: `python manage.py test akreditasi`
  Result: **64/64 PASS** ✅

- [x] **Step 2: Deploy to Vercel and apply Supabase migration**
  Migration `0037_indikatormutu_arah_target_alter_indikatormutu_jenis` applied.
  Commits `b8facaf`, `6c9cb59`, `51dd3e0` pushed and deployed.

- [x] **Step 3: Verify live dashboard**
Confirm HTTP 200/302 responses and UI elements rendering cleanly on production URL.
