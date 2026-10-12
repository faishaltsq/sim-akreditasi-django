# Implementation Plan: Official Risk Planning Document View (Perencanaan Risiko Unit - Siklus Plan)

**Document Reference:** User attached Word document: `Buatkan tampilan Perencanaan yang sudah dibuat untuk input resiko 12 10.docx`  
**Target Application:** ARIMA v2.6 (Hospital Accreditation & Clinical Risk Management System)  
**Author:** Apex (All-Role Engineering Operator)  
**Date:** October 12, 2026  
**Status:** READY FOR REVIEW & IMPLEMENTATION  

---

## 1. Executive Summary & Problem Context

The user provided a formal specification document (`Buatkan tampilan Perencanaan yang sudah dibuat untuk input resiko 12 10.docx`) requiring an official, print-ready document view of the **Risk Planning Phase (Siklus Plan)** generated from risk input entries.

Under Indonesian hospital accreditation standards (**STARKES PMKP 12, Standar 5.15, and ISO 31000 Risk Management Cycle**), every hospital department (Unit Kerja) must document their initial risk assessment and mitigation plan before executing actions (Do) and monitoring outcomes (Check/Act).

Currently, ARIMA has:
1. Risk Input Form (`/risiko/input/` & `/risiko/tambah/`)
2. Risk Detail / PDCA Execution Page (`/risiko/<id>/`)
3. Monitoring & Evaluation Dashboard Table (`/risiko/monitoring-evaluasi/`)

**Gap Identified:**  
There is no dedicated, formatted **"Dokumen Perencanaan Risiko"** page that structures the output of the Plan phase into the hospital's official layout with official headers, objective statements, initial grade calculation, FMEA/RCA evaluation method, 5-column Quality Indicator table, 7-column Action Plan table, and formal signature endorsement block (`Kuwarasan, .... 2026 / Ka Unit Kerja`).

---

## 2. Document Specification Breakdown (Word vs. System Mapping)

The attached Word document specifies the following structure:

```
PERENCANAAN RESIKO RS MONSISKAMI ARIMA
JL. Candiwulan Kalibuntu Mangli Kuwarasan Kebumen Jawatengah

Identifikasi resiko
Tujuan
Penilaian resiko Awal, lengkap dengan perhitungan grade resiko
Pemilihan metode Evaluasi (FMEA atau RCA)
Indikator mutu dengan tabel:
[No | Masalah Resiko | Indikator mutu | Target | Jenis (INM, IM RS/IMUnit)]

Rencana Aksi (Mitigasi) dengan table:
[No | Masalah resiko | Indikator mutu | Rencana Aksi | waktu | Biaya | PJ]

Kuwarasan, …. 2026
Ka Unit kerja
(……………………)
```

### Attribute & Table Mapping Table

| Section in Document | Description / Data Source | Database / Model Source |
| :--- | :--- | :--- |
| **Kop Surat / Header** | RS MONSISKAMI ARIMA — Kebumen | Hospital Profile / Constant Header |
| **1. Identifikasi Risiko** | Unit Kerja, Periode, Kategori, Masalah, Bukti Pendukung, Jenis/Pernyataan Risiko | `RisikoUnit.unit`, `periode`, `kategori_risiko`, `masalah`, `data_pendukung`, `jenis_risiko` |
| **2. Tujuan** | Tujuan pengendalian risiko & mutu klinis | New field `RisikoUnit.tujuan` (with intelligent clinical default fallback) |
| **3. Penilaian Risiko Awal** | Dampak (1-5), Probabilitas (1-5), Skor Inherent (1-25), Grade/Tingkat Risiko | `RisikoUnit.dampak`, `probabilitas`, `skor_inherent`, `risk_level` (Sangat Tinggi / Tinggi / Sedang / Rendah) + 5x5 Matrix Badge |
| **4. Metode Evaluasi** | Pemilihan metode: FMEA (Proaktif) vs RCA (Reaktif) | `RisikoUnit.metode_evaluasi`, `tim_evaluasi`, RPN FMEA / Investigasi |
| **5. Tabel Indikator Mutu** | 5 Kolom: No, Masalah Risiko, Indikator Mutu, Target (%), Jenis (INM/IM-RS/IM-Unit) | `RisikoUnit.masalah`, `indikator_mutu_terkait.nama_indikator`, `target_capaian_indikator` (or `indikator_mutu_terkait.target_nilai`), `indikator_mutu_terkait.get_jenis_display` |
| **6. Tabel Rencana Aksi** | 7 Kolom: No, Masalah Risiko, Indikator Mutu, Rencana Aksi, Waktu (Timeline), Biaya (Rp), PJ | `RisikoUnit.masalah`, `indikator_mutu_terkait.nama_indikator`, `rencana_aksi` (or `tindak_lanjut.all`), `target_selesai`, `biaya_mitigasi`, `pj_mitigasi` |
| **7. Lembar Pengesahan** | Tanggal & Tanda Tangan Ka. Unit Kerja | `Kuwarasan, [Date] [Year]`, `Ka Unit Kerja [unit.name]`, `[Signature block]` |

---

## 3. Architecture & Implementation Plan

### 3.1 Database Schema Enhancement (`akreditasi/risiko_models.py`)

Add the missing `tujuan` field to `RisikoUnit`:
```python
# In akreditasi/risiko_models.py (RisikoUnit)
tujuan = models.TextField(
    'Tujuan Pengendalian Risiko',
    blank=True,
    default='',
    help_text='Tujuan mitigasi dan sasaran keselamatan/mutu klinis yang ingin dicapai'
)
```

Add helper properties:
```python
@property
def tujuan_display(self):
    if self.tujuan and self.tujuan.strip():
        return self.tujuan.strip()
    # Intelligent clinical fallback based on category
    kategori = self.get_kategori_risiko_display() if hasattr(self, 'get_kategori_risiko_display') else 'Klinis'
    return f"Mengendalikan dan memitigasi {kategori.lower()} guna mencegah insiden keselamatan pasien serta memastikan kepatuhan terhadap standar pelayanan di {self.unit.name}."
```

Run Django migrations:
- `python manage.py makemigrations akreditasi`
- `python manage.py migrate akreditasi`

---

### 3.2 Form & Input View Update (`akreditasi/risiko_views.py` & `risiko_form.html`)

1. In `templates/akreditasi/risiko_form.html`:
   - Add input textarea for `tujuan` right after "Masalah & Data Pendukung" in Section A.
   - Pre-populate placeholder: `"Contoh: Menurunkan angka kejadian infeksi daerah operasi dan mencegah insiden keselamatan pasien pasca bedah..."`.
2. In `akreditasi/risiko_views.py` (`risiko_input`):
   - Capture `tujuan=request.POST.get('tujuan', '').strip()` when creating `RisikoUnit`.

---

### 3.3 Dedicated Planning Document Views (`akreditasi/risiko_views.py`)

Implement two complementary views:
1. **Single Risk Planning Document**: `risiko_perencanaan_dokumen(request, risiko_id)`
   - Route: `/risiko/<int:risiko_id>/perencanaan/`
   - Shows the complete Planning Document for a specific risk entry.
   - Perfect for quick viewing and printing immediately after creating or reviewing a risk.
2. **Unit Aggregate Planning Document**: `risiko_perencanaan_unit(request, unit_id=None)`
   - Route: `/risiko/perencanaan/` and `/risiko/perencanaan/<int:unit_id>/`
   - Filter by Unit Kerja (supports RBAC unit-scoping for `KEPALA_UNIT` and `STAF_NAKES`) and Year (`tahun`).
   - Generates the official composite Planning Document for the entire department:
     - Header & Unit Identity
     - Purpose / Objectives
     - Initial Risk Matrix & Grade summary
     - Evaluation Methods (FMEA / RCA breakdown)
     - **Tabel 1 (Indikator Mutu)**: Aggregates all risks of that unit in the 5-column format.
     - **Tabel 2 (Rencana Aksi Mitigasi)**: Aggregates all mitigation actions of that unit in the 7-column format.
     - Official Endorsement & Signature Block.
3. **Export CSV / Spreadsheet**: `risiko_perencanaan_export_csv(request)`
   - Route: `/risiko/perencanaan/export-csv/`
   - Exports the 5-column and 7-column tables into Excel-ready CSV (with UTF-8 BOM).

---

### 3.4 Template Design (`templates/akreditasi/risiko_perencanaan.html`)

Create a clean, responsive, and print-optimized template adhering to the Word document:
1. **Hospital Official Letterhead (KOP SURAT)**:
   - Hospital Name: `PERENCANAAN RESIKO RS MONSISKAMI ARIMA`
   - Hospital Address: `JL. Candiwulan Kalibuntu Mangli Kuwarasan Kebumen Jawatengah`
   - Document Title: `DOKUMEN PERENCANAAN MANAJEMEN RISIKO (SIKLUS PLAN - STANDAR STARKES 5.15)`
2. **Toolbar (Screen View only / `no-print`)**:
   - Filter: Unit Kerja, Tahun, Mode Tampilan (Per-Risiko vs Seluruh Unit)
   - Action Buttons: `Cetak / Simpan PDF`, `Ekspor CSV`, `Kembali ke Detail / Daftar`
3. **Structured Content Blocks**:
   - **Section 1: Identifikasi Risiko**: Clean grid with Unit, Tahun, Periode, Kategori, Masalah, Bukti Pendukung, and Jenis Risiko.
   - **Section 2: Tujuan**: Highlighted callout box with purpose statement.
   - **Section 3: Penilaian Risiko Awal & Perhitungan Grade**:
     - Formula: `Skor Inherent = Dampak (D) × Probabilitas (P)`
     - Visual risk grade badge (Sangat Tinggi / Tinggi / Sedang / Rendah) with color codes.
     - Embedded 5x5 Matrix indicator.
   - **Section 4: Pemilihan Metode Evaluasi**:
     - FMEA (Proaktif) vs RCA (Reaktif) badge, tim evaluasi, and rationale.
   - **Section 5: Tabel Indikator Mutu (5 Kolom)**:
     - `No`, `Masalah Resiko`, `Indikator mutu`, `Target`, `Jenis (INM, IM RS/IMUnit)`
   - **Section 6: Tabel Rencana Aksi (Mitigasi) (7 Kolom)**:
     - `No`, `Masalah resiko`, `Indikator mutu`, `Rencana Aksi`, `waktu`, `Biaya`, `PJ`
   - **Section 7: Lembar Pengesahan (Signature Block)**:
     - `Kuwarasan, [Current Date] [Year]`
     - `Ka Unit kerja [Nama Unit]`
     - `(........................................)`
4. **Print Optimization (`@media print`)**:
   - Hide sidebar, navigation, search filters, and action buttons.
   - Set page size to A4 portrait / landscape.
   - Clean black/slate borders with crisp typography for surveyor evaluation.

---

### 3.5 System Navigation & Cross-Linking

1. **Detail Risiko (`templates/akreditasi/risiko_detail.html`)**:
   - Add a prominent button in the header:
     `<a href="{% url 'akreditasi:risiko_perencanaan_dokumen' risiko_id=risiko.pk %}" class="btn btn-sm btn-outline-teal"><i class="bi bi-file-earmark-text me-1"></i>Dokumen Perencanaan (Plan)</a>`
   - In Section E (Rencana Aksi), add a link to the planning sheet.
2. **Daftar Risiko (`templates/akreditasi/risiko_daftar.html`)**:
   - Add button in the top toolbar: `Dokumen Perencanaan Unit`.
3. **Sidebar Navigation (`templates/includes/sidebar.html`)**:
   - Under `Manajemen Risiko`, add:
     - `Perencanaan Risiko (Plan)` -> `/risiko/perencanaan/`
     - `Daftar Risiko (Do)` -> `/risiko/`
     - `Monitoring & Evaluasi (Check/Act)` -> `/risiko/monitoring-evaluasi/`

---

## 4. Verification & Testing Strategy

1. **Unit & Model Tests**:
   - Verify `tujuan` field persistence and `tujuan_display` property.
   - Test `risiko_input` form processing with `tujuan`.
2. **View & RBAC Tests**:
   - Verify superadmin can view planning documents for all units.
   - Verify unit-scoped users (`KEPALA_UNIT`, `STAF_NAKES`) can only view their assigned unit.
3. **Browser & UI Verification**:
   - Navigate to `/risiko/perencanaan/` and `/risiko/136/perencanaan/`.
   - Verify header, tables (5 cols and 7 cols), matrix badges, and signature block render correctly.
   - Test print preview (`window.print()`).
   - Test CSV export functionality.
4. **Production Deployment & Live Verification**:
   - Push to `master` and monitor Vercel deployment.
   - Test live endpoints on `sim-akreditasi-django.vercel.app`.

---

## 5. Implementation Steps Summary

- **Step 1:** Add `tujuan` field to `RisikoUnit` in `akreditasi/risiko_models.py` and run migrations.
- **Step 2:** Add `tujuan` field in `akreditasi/risiko_views.py` (`risiko_input`) and `templates/akreditasi/risiko_form.html`.
- **Step 3:** Implement views `risiko_perencanaan_dokumen`, `risiko_perencanaan_unit`, and `risiko_perencanaan_export_csv` in `akreditasi/risiko_views.py`.
- **Step 4:** Register URL patterns in `akreditasi/urls.py`.
- **Step 5:** Create template `templates/akreditasi/risiko_perencanaan.html` with exact Word document layout.
- **Step 6:** Add navigation links in `risiko_detail.html`, `risiko_daftar.html`, and `sidebar.html`.
- **Step 7:** Run tests, commit, push, and verify live on Vercel production.
