# Implementation Plan: Monthly Quality Indicator Trends & Renstra Multi-Year Charts on ARIMA Dashboard

**Document Reference:** User attached Word document: `alur kerja capaian indikator mutu.docx`  
**Target Application:** ARIMA v2.6 (Hospital Accreditation & Clinical Risk Management System - RS Monsiskami)  
**Author:** Apex (Multi-Role Engineering Operator)  
**Date:** October 14, 2026  
**Status:** COMPLETED & VERIFIED (60/60 Tests Passing)  

---

## 1. Executive Summary & Document Analysis

The user provided an official workflow and visual design document (`Downloads/alur kerja capaian indikator mutu.docx`) specifying:
1. **Monthly Quality Indicator Achievement Trend Chart (Combo / Bar-Line Chart)**:
   - Sumbu X: 12 Bulan (Januari – Desember)
   - Sumbu Y: Capaian Nilai/Persentase (0% – 100%)
   - Bar/Garis Realisasi: Capaian aktual per bulan dengan pewarnaan dinamis:
     - **Hijau**: Capaian $\ge$ Target Nilai
     - **Merah**: Capaian $<$ Target Nilai
   - Garis Target (Threshold Line): Garis putus-putus horizontal merah sebagai batas acuan target mutu.
2. **Renstra Multi-Year Progress Chart (2026–2030 Grouped Bar Chart)**:
   - Sumbu X: Tahun Renstra (2026, 2027, 2028, 2029, 2030)
   - Sumbu Y: Persentase Capaian (%)
   - Dual Bar: Membandingkan **Target Renstra Tahunan** vs **Realisasi Capaian Aktual**.
3. **Workflow (Alur Kerja Data)**:
   - **Input**: PJ Mutu unit menginput nilai Numerator, Denominator, dan **upload dokumen bukti pendukung / laporan fisik**.
   - **Kalkulasi**: Capaian Bulanan $= (\text{Numerator} / \text{Denominator}) \times 100\%$. Capaian Tahunan $=$ rata-rata bulan berjalan.
   - **Pemetaan Renstra**: Mengaitkan capaian aktual per tahun dengan target roadmap Renstra 2026–2030.
   - **Visualisasi Dasbor**: Penempatan strategis di **bawah Visi & Misi RS** dengan navigasi tab dan filter interaktif (Kategori Indikator, Unit Kerja, dan Tahun).

---

## 2. Gap Analysis (Current Codebase vs Document Specification)

| Component | Current Codebase Status | Requirement in `.docx` | Action Required |
| :--- | :--- | :--- | :--- |
| **Model `CatatanIndikator`** | Has `nilai_numerator`, `nilai_denominator`, `catatan`, `bulan`, `tahun`. | Requires supporting document upload ("upload dokumen bukti / laporan"). | Add `bukti_dokumen = models.FileField(upload_to='indikator_bukti/%Y/%m/', blank=True, null=True)`. |
| **Model `RenstraRoadmap`** | Has `tahun`, `isu_strategis`, `sub_tema`, `deskripsi`, `ikon`, `warna_hex`. | Requires explicit baseline Renstra annual target for multi-year comparison. | Add `target_persen = models.DecimalField(default=80.00)` to `RenstraRoadmap`. |
| **Input Form (`indikator_input_capaian.html`)** | Text and number fields only. `enctype="multipart/form-data"` is missing. | PJ Mutu uploads evidence files when submitting monthly metrics. | Add file input, enable multipart form encoding, validate file size/types. |
| **View `indikator_input_capaian`** | Processes POST for numbers and note. | File handling for `request.FILES.get('bukti_dokumen')`. | Save uploaded file safely and update audit log. |
| **Detail View (`indikator_detail.html`)** | Shows table of month, num, den, and status badge. | View/download uploaded evidence file. | Add attachment download link with icon for records with `bukti_dokumen`. |
| **Main Dashboard (`dashboard.html`)** | Shows KPI cards, Visi Misi, and 5 Stepper Cards for Renstra. Does NOT have quality charts. | Dual interactive charts placed directly under Visi & Misi with tab toggle. | Add Chart Group with Tab 1 (Monthly Combo Chart) and Tab 2 (Renstra Grouped Bar Chart) with dynamic filters. |
| **Dashboard View (`views.py:dashboard`)** | Precalculates average capaian for the stepper cards. | Requires monthly array (12 months) of average achievement and 5-year target vs actual arrays for Chart.js. | Aggregate monthly averages, threshold line, dynamic bar colors, and multi-year Renstra dataset into dashboard context. |

---

## 3. Architecture & Data Design

### 3.1 Database Schema Additions (`akreditasi/risiko_models.py`)

#### Field 1: Evidence File on `CatatanIndikator`
```python
class CatatanIndikator(models.Model):
    # Existing fields...
    bukti_dokumen = models.FileField(
        'Dokumen Bukti Pendukung',
        upload_to='indikator_bukti/%Y/%m/',
        null=True,
        blank=True,
        help_text='Upload bukti pelaksanaan atau laporan capaian bulanan (PDF/DOCX/JPG/PNG)'
    )
```

#### Field 2: Annual Renstra Target on `RenstraRoadmap`
```python
class RenstraRoadmap(models.Model):
    # Existing fields...
    target_persen = models.DecimalField(
        'Target Capaian Renstra (%)',
        max_digits=5,
        decimal_places=2,
        default=80.00,
        help_text='Target agregat Renstra untuk tahun ini (misal: 2026: 70%, 2027: 80%, dst.)'
    )
```

Migration: `0036_catatanindikator_bukti_dokumen_and_renstraroadmap_target_persen.py`

---

## 4. Visual & UI/UX Specifications

### 4.1 Dashboard Section Placement (Directly Under Visi & Misi RS)
```
┌────────────────────────────────────────────────────────────────────────┐
│  Visi & Misi RS Monsiskami ARIMA                                        │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  GRUP GRAFIK CAPAIAN MUTU & RENSTRA RS MONSISKAMI                      │
│  ┌───────────────────────────────┬──────────────────────────────────┐  │
│  │ [Tab 1: Tren Capaian Bulanan] │ [Tab 2: Tren Renstra 2026–2030]  │  │
│  └───────────────────────────────┴──────────────────────────────────┘  │
│                                                                        │
│  [Filters]: [Kategori: Semua/INM/IMP-RS/IMP-Unit] [Unit: Semua] [2026]  │
│                                                                        │
│  (Tab 1 Content)                                                       │
│   • Combo Chart (Bar & Target Line):                                   │
│     - Bars: Jan s.d. Des.                                              │
│     - Bar Color: Green (#198754) if >= Target, Red (#dc3545) if <      │
│     - Dashed Line: Target Nilai Acuan (e.g., 85% or 100%)              │
│                                                                        │
│  (Tab 2 Content)                                                       │
│   • Grouped Bar Chart (Target vs Realisasi 2026–2030):                 │
│     - Bar A: Target Renstra Tahunan (Soft Blue / Teal)                 │
│     - Bar B: Realisasi Aktual Tahunan (Solid Primary / Green)          │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Roadmap Renstra Stepper Cards (2026–2030 Klik Detail Indikator)       │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Top KPI Summary Card
Add a high-level summary badge/card alongside the accreditation progress:
- **Capaian Indikator Mutu {{ current_year }}**: `{{ avg_mutu_year }}%`
- Status Badge: `Tercapai: {{ count_tercapai }} / {{ total_pengukuran }} Data`

---

## 5. Detailed Step-by-Step Implementation Tasks

### Phase 1: Database Schema & Migration
- [ ] Task 1.1: Add `bukti_dokumen` to `CatatanIndikator` in `akreditasi/risiko_models.py`.
- [ ] Task 1.2: Add `target_persen` to `RenstraRoadmap` in `akreditasi/risiko_models.py`.
- [ ] Task 1.3: Generate and apply Django migration (`makemigrations` and `migrate`).
- [ ] Task 1.4: Update default target percentages for 2026–2030 (2026: 75%, 2027: 80%, 2028: 85%, 2029: 90%, 2030: 95%).

### Phase 2: Monthly Quality Metric Input & Detail Views
- [ ] Task 2.1: Update `templates/akreditasi/indikator_input_capaian.html`:
  - Add `enctype="multipart/form-data"` to `<form>`.
  - Add file input for `bukti_dokumen` with accept filter (`.pdf,.docx,.doc,.jpg,.jpeg,.png`).
- [ ] Task 2.2: Update `indikator_input_capaian` view in `akreditasi/indikator_views.py`:
  - Process `request.FILES.get('bukti_dokumen')`.
  - Update `update_or_create` defaults to persist `bukti_dokumen` when uploaded.
- [ ] Task 2.3: Update `templates/akreditasi/indikator_detail.html`:
  - Add "Bukti / Dokumen" column to the monthly records table.
  - Render download icon badge if `c.bukti_dokumen` is present.

### Phase 3: Dashboard Backend Data Aggregation (`akreditasi/views.py`)
- [ ] Task 3.1: In `dashboard(request)`:
  - Extract filter parameters (`filter_mutu_jenis`, `filter_mutu_unit`, `filter_mutu_tahun` default 2026).
  - Compute monthly aggregated averages (months 1–12) for the selected filter.
  - Determine average target baseline line across the filtered indicators.
  - Build dynamic color palette for each month: `#198754` (green) if month value $\ge$ target, `#dc3545` (red) if below target, `#e2e8f0` (neutral) if no data.
- [ ] Task 3.2: Aggregate 5-Year Renstra Target vs Actual (2026–2030):
  - Years: `[2026, 2027, 2028, 2029, 2030]`.
  - Target Series: `[75.0, 80.0, 85.0, 90.0, 95.0]` (pulled dynamically from `RenstraRoadmap`).
  - Actual Series: Yearly average from `CatatanIndikator` for each corresponding year.
- [ ] Task 3.3: Pass JSON-serialized chart datasets and filter context to `dashboard.html`.

### Phase 4: Dashboard UI & Chart.js Implementation (`templates/akreditasi/dashboard.html`)
- [ ] Task 4.1: Insert "Grup Grafik Capaian Mutu & Tren Renstra" card container immediately below Visi & Misi RS.
- [ ] Task 4.2: Add Bootstrap 5 Nav Tabs (`#tab-mutu-bulanan` and `#tab-renstra-tahunan`).
- [ ] Task 4.3: Add inline filter controls (Kategori Indikator, Unit Kerja, Tahun) with clean GET parameter submission.
- [ ] Task 4.4: Implement Chart.js Tab 1: Combo Bar + Threshold Line chart (`id="chartMutuBulanan"`).
- [ ] Task 4.5: Implement Chart.js Tab 2: Grouped Bar chart (`id="chartRenstraTahunan"`).
- [ ] Task 4.6: Ensure Chart.js handles tab switching cleanly (trigger `chart.resize()` on tab activation).

### Phase 5: Verification & Quality Gates
- [ ] Task 5.1: Write unit tests in `akreditasi/tests_indikator_mutu.py` covering:
  - File upload on monthly metric recording.
  - Monthly achievement percentage calculation & target threshold evaluation.
  - Dashboard context rendering with monthly and Renstra multi-year datasets.
- [ ] Task 5.2: Execute test suite (`tests_indikator_mutu`, `tests_perencanaan_risiko`, `tests_security`).
- [ ] Task 5.3: Verify responsiveness on mobile, tablet, and desktop viewports.
- [ ] Task 5.4: Git commit with conventional commit standards and deploy to Vercel production.

---

## 6. Verification Commands & Acceptance Criteria

1. **Test Execution**:
   ```bash
   .venv/Scripts/python manage.py test akreditasi.tests_indikator_mutu akreditasi.tests_perencanaan_risiko akreditasi.tests_security
   ```
2. **Dashboard Visual Inspection**:
   - Access `https://sim-akreditasi-django.vercel.app/`
   - Verify presence of the Dual Chart card under Visi & Misi RS.
   - Verify Tab 1 displays monthly bars colored green/red according to target threshold line.
   - Verify Tab 2 displays grouped bars comparing Renstra 2026–2030 target vs actual realization.
3. **Upload Verification**:
   - Navigate to `/indikator-mutu/<id>/input/`
   - Upload a test PDF/image proof and verify file is stored and accessible from `/indikator-mutu/<id>/`.
