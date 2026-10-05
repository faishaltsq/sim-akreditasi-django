# Implementation Plan: SIMRS IGD & Registration/Admission Revamp

**Specification Documents:**
- `Downloads/Revisi 02 di unit IGD.docx` (IGD Clinical Triage & TTV Refinements)
- `Downloads/Menu pendaftaran rev01.docx` (Comprehensive Front-Office Registration & Admission Menu Structure)

**Date:** 2026-10-05  
**Author:** AI Engineering & QA Team  
**Status:** DRAFT (Ready for Review & Execution)

---

## 1. Executive Summary & Objectives

This plan addresses clinical workflow gaps and UX issues identified in the emergency department (IGD) and front-office admission desk (Pendaftaran) of the ARIMA hospital management system (Permenkes 24/2022 & STARKES MRMIK/ARK standards):

1. **IGD Revamp (`Revisi 02 di unit IGD.docx`)**:
   - Fix table layout truncation where action buttons and header columns ("KEPUTUSAN...") clip at screen boundaries.
   - Accommodate **Priority 4 (Hitam / Expectant)** in triage filters and update descriptive clinical terminology (moribund/injuries incompatible with life, not just DoA/deceased).
   - Expand vital signs display beyond blood pressure to show a complete, color-coded vital sign block (BP, Heart Rate, Respiratory Rate, Temperature, SpO2, GCS, Pain Scale).
   - Disentangle ICD-10 (admission diagnoses) from ICD-9-CM (procedures/actions) in column headers and data modals.
   - Add pulsating critical value visual alerts on patient rows when diagnostic orders flag critical results.

2. **Admission & Registration Revamp (`Menu pendaftaran rev01.docx`)**:
   - Restructure `pendaftaran_dashboard.html` into 7 standardized clinical admission modules using responsive Bootstrap tabs:
     - **Tab 1: Patient Registration (Pendaftaran Pasien)**: Unified New Patient (NIK validation) & Returning Patient (quick revisit lookup).
     - **Tab 2: Outpatient Registration (Pelayanan Rawat Jalan)**: Clinic/Specialist routing, DPJP selection, automatic queue assignment (`A-xxx`), SEP printing.
     - **Tab 3: Emergency Fast-Track (Pelayanan Gawat Darurat IGD)**: Rapid admission form requiring minimal data (Name/Mr. X, triage tag, quick chief complaint) with deferred demographic completion.
     - **Tab 4: Inpatient Admission (Pelayanan Rawat Inap & SPRI)**: Bed booking integration, SPRI validation, General Consent form access, and SEP Rawat Inap.
     - **Tab 5: Queue & Bed Live Display (Manajemen Antrean & Ketersediaan Bed)**: Public TV display mode for queue calling and real-time Bed Occupancy Rate (BOR).
     - **Tab 6: Reports & Analytics (Laporan & Dasbor Kunjungan)**: Daily/monthly visit breakdowns, new vs. returning patient ratios, and waiting time telemetry.
     - **Tab 7: Utilities & Integration (Master Data & Dokumen)**: BPJS eligibility check simulation, visit cancellation/rescheduling, and 1-click reprinting (Tracer RM, Wristband, Label Barcode, SEP).

---

## 2. Architecture & File Impacts

| File Path | Nature | Description |
|---|---|---|
| `templates/pasien/igd_dashboard.html` | UI / Template | Add P4 filter button, expand TTV badges (HR, RR, Suhu, SpO2, GCS, Pain), separate ICD-10/ICD-9 headers, fix responsive table layout, add critical alert styling. |
| `pasien/views.py` | Controller | Update `igd_dashboard` context and query parameters; add `fast_track_igd`, `api_cek_bpjs`, `kunjungan_batal`, and `cetak_tracer` views; update `pendaftaran_dashboard` to compute reporting metrics. |
| `pasien/urls.py` | Routing | Register new routes for fast-track IGD admission, BPJS check, visit cancellation, and tracer printing. |
| `templates/pasien/pendaftaran_dashboard.html` | UI / Template | Comprehensive multi-tab restructuring into 7 clinical modules with quick actions, modals, and report widgets. |
| `templates/pasien/cetak_tracer.html` | Print Document | Clean printable thermal/A5 medical record tracer slip for physical archives. |
| `pasien/tests_revisi_igd.py` | Test Suite | Automated regression testing for IGD P4 filter, comprehensive TTV updates, and critical alert flags. |
| `pasien/tests_revisi_pendaftaran.py` | Test Suite | Automated testing for 7 registration modules, Fast-track admission, BPJS verification API, visit cancellation, and tracer printing. |

---

## 3. Step-by-Step Implementation Tasks

### Task 1: IGD Dashboard UI/UX & Clinical Triage Refinements

**Files to modify:**
- `templates/pasien/igd_dashboard.html`
- `pasien/views.py` (`igd_dashboard` view)

**Step 1.1: Add P4 (Hitam/Expectant) Filter Button and Update Triage Definition Card**
- In `templates/pasien/igd_dashboard.html`:
  - Locate `<div class="btn-group btn-group-sm">` in the table header.
  - Add the `HITAM` filter button:
    ```html
    <a href="?triage=HITAM" class="btn {% if triage_filter == 'HITAM' %}btn-dark{% else %}btn-outline-dark{% endif %}">
        <i class="bi bi-x-circle me-1"></i> Hitam ({{ count_hitam }})
    </a>
    ```
  - In the top card for P4 EXPECTANT, clarify description text:
    - Current: `"Meninggal / DoA"`
    - Revised: `"Prioritas IV — Cedera Kritis Fatal / Harapan Hidup Minimal / DoA"`

**Step 1.2: Expand Vital Signs (TTV) & Clarify ICD-10 vs ICD-9**
- In `templates/pasien/igd_dashboard.html`:
  - Change column header:
    ```html
    <th style="min-width: 170px;">TTV (Tanda Vital)</th>
    <th style="min-width: 150px;">Diagnosa (ICD-10) / Tindakan (ICD-9)</th>
    ```
  - In each row's TTV column, render a structured compact grid:
    - Blood Pressure (`TD: xx/xx mmHg`)
    - Heart Rate (`Nadi: xx bpm`)
    - Respiratory Rate (`RR: xx x/m`)
    - Temperature (`T: xx °C`)
    - Oxygen Saturation (`SpO2: xx%`)
    - GCS (`GCS: xx`) & Pain Scale (`Nyeri: x/10`)
    - Add color badges (e.g., text-danger if SpO2 < 95% or Suhu > 38.0°C).
  - In the Diagnosa column:
    - Display `k.diagnosa_masuk` as primary diagnosis (ICD-10).
    - If `k.icd9_tindakan` exists, render as badge `ICD-9: {{ k.icd9_tindakan }}`.

**Step 1.3: Fix Action Column Truncation & Table Responsiveness**
- Wrap table in `.table-responsive` with custom CSS `min-width: 1150px`.
- Set the actions column header to `<th class="text-center" style="min-width: 220px;">Keputusan DPJP & Tindakan</th>`.
- Ensure all modal triggers have proper margins (`gap-1` flex container) and prevent word clipping.

**Step 1.4: Critical Value Alert Integration**
- Highlight patient rows with a soft red background / warning border when `k.order_penunjang.filter(is_critical_value=True).exists()` is detected.
- Show an alert badge `<span class="badge bg-danger animate-pulse"><i class="bi bi-exclamation-triangle-fill"></i> CRITICAL VALUE</span>`.

**Verification:**
- Write and run `pasien.tests_revisi_igd` to assert filtering by `?triage=HITAM` returns black triage patients, TTV fields save and display properly, and critical value flags render alert badges.

---

### Task 2: Backend Endpoints for Registration & Admission Utilities

**Files to modify:**
- `pasien/views.py`
- `pasien/urls.py`

**Step 2.1: Emergency Fast-Track Admission View (`fast_track_igd`)**
- Allows admitting emergency patients immediately with minimal required info:
  - Patient Name (or default `"Mr. / Mrs. X"` if unknown)
  - Estimated Gender & Age
  - Initial Triage Category (`MERAH`, `KUNING`, `HIJAU`, `HITAM`)
  - Chief Complaint / Catatan Masuk
  - Auto-generate RM and unique `no_kunjungan` prefixed with `IGD-`.
  - Redirect directly to `igd_dashboard` with a success message.

**Step 2.2: Mock BPJS Eligibility Verification API (`api_cek_bpjs`)**
- Endpoint `/pasien/api/cek-bpjs/?no_kartu=xxx&nik=yyy`:
  - Returns simulated active/inactive BPJS V-Claim status, patient class hak rawat (Kelas 1, 2, 3), and faskes perujuk.

**Step 2.3: Visit Cancellation Endpoint (`kunjungan_batal`)**
- Endpoint `/pasien/kunjungan/<pk>/batal/`:
  - Allows admission staff to mark a visit as `BATAL` with reason logging, freeing any booked beds or reserved queue numbers.

**Step 2.4: Medical Record Tracer Slip Print View (`cetak_tracer`)**
- Endpoint `/pasien/kunjungan/<pk>/cetak-tracer/`:
  - Generates a thermal/A5 printable tracer containing: No RM, Patient Name, Destination Clinic/IGD, DPJP, Timestamp, and Barcode for physical medical record archive tracking.

**Verification:**
- Test all 4 endpoints with automated tests in `pasien/tests_revisi_pendaftaran.py`.

---

### Task 3: Comprehensive Pendaftaran Dashboard Restructuring (7 Modules)

**Files to modify:**
- `templates/pasien/pendaftaran_dashboard.html`
- `templates/pasien/cetak_tracer.html` (new file)
- `pasien/views.py` (`pendaftaran_dashboard` view)

**Step 3.1: Tabbed Interface Architecture**
Restructure `pendaftaran_dashboard.html` with clean Bootstrap 5 navigation tabs:
1. `nav-pasien-baru`: **Pendaftaran Pasien (Baru & Lama)**
   - NIK lookup auto-fill form for new patient registration.
   - Quick search input for existing patients with 1-click visit creation.
2. `nav-rajal`: **Pelayanan Rawat Jalan**
   - Poliklinik registration, DPJP selection, and queue number generator (`POLI_PD-001`, `POLI_JTG-001`).
   - Quick action to print SEP Rawat Jalan.
3. `nav-igd-fasttrack`: **Fast-Track IGD (Kondisi Gawat Darurat)**
   - Minimal input emergency registration form with triage selector.
4. `nav-ranap`: **Pelayanan Rawat Inap & SPRI**
   - SPRI input, bed reservation modal link, and General Consent print trigger.
5. `nav-antrean-bed`: **Display Antrean & Ketersediaan Bed**
   - Live Bed Occupancy matrix with room filter.
   - Fullscreen TV Queue display mode button for waiting room monitors.
6. `nav-laporan`: **Laporan & Dasbor Kunjungan**
   - Summary statistics: Today's visits, New vs. Returning ratio, Visits per clinic, Inpatient admissions.
   - Daily waiting time indicators.
7. `nav-utility`: **Utility & Cetak Ulang**
   - Quick BPJS card validity check tool.
   - 1-click reprinting buttons: Tracer Rekam Medis, Gelang Pasien, Label Barcode, SEP, SKDP.
   - Visit cancellation tool for mistaken entries.

**Step 3.2: Create Printable Tracer Template (`templates/pasien/cetak_tracer.html`)**
- Standard hospital physical document format with barcode, patient demographic, clinic destination, and archive sign-off box.

---

### Task 4: Automated Testing, Full Regression & Review

**Test Suites to Create / Run:**
1. `pasien.tests_revisi_igd`:
   - Test P4 triage filtering and count accuracy.
   - Test full TTV updates (Sistole, Diastole, Nadi, RR, Suhu, SpO2, GCS, Nyeri).
   - Test critical value indicator visibility.
2. `pasien.tests_revisi_pendaftaran`:
   - Test `fast_track_igd` creation for unknown/emergency patient.
   - Test `api_cek_bpjs` mock response.
   - Test `kunjungan_batal` visit cancellation and bed release.
   - Test `cetak_tracer` output.
3. Full regression:
   - Run `python manage.py test accounts pasien akreditasi.tests_ai`.
   - Ensure all 38 existing tests plus new test cases pass.

---

## 4. Acceptance Criteria

- [ ] **IGD Triage P4**: Filter button `Hitam (x)` is visible, clickable, and filters only P4 patients. P4 summary card reflects fatal injury / expectant definition.
- [ ] **IGD TTV & Diagnosis**: All 7 vital signs (BP, HR, RR, Temp, SpO2, GCS, Pain) render legibly. ICD-10 and ICD-9 are clearly demarcated.
- [ ] **IGD Table Layout**: No clipping or overflow on action buttons and table headers across screen widths.
- [ ] **Critical Alert**: Patients with critical laboratory/radiology findings show prominent visual alerts.
- [ ] **Pendaftaran 7 Modules**: All 7 sections from `Menu pendaftaran rev01.docx` are accessible via organized tabs.
- [ ] **Fast-Track IGD**: Registration desk can admit an emergency patient in under 5 seconds with minimal input.
- [ ] **Tracer & Document Printing**: Tracer slip, identity wristband, and SEP are directly printable.
- [ ] **Test Coverage**: 100% pass on all new unit and integration tests; zero regression on existing suites.
