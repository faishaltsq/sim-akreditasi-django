# Implementation Plan: Enhancements for Risk Evaluation & Quality Indicator Monitoring (Seksi G)

- **Date:** 2026-10-15
- **Branch:** `master`
- **Specification Source:** `Downloads/Tambahan perbaikan untuk input evaluasi Indikator mutu 12.18.docx`
- **Application:** ARIMA (Hospital Risk Management & Quality Accreditation System)

---

## 1. Executive Summary & Problem Analysis

Based on `Downloads/Tambahan perbaikan untuk input evaluasi Indikator mutu 12.18.docx`, the current risk evaluation interface (**Seksi G. Monitoring dan Evaluasi Risiko** in `templates/akreditasi/risiko_evaluasi.html`) needs upgrades across three key areas to align with hospital quality standards (PMKP/STARKES/PDCA):

1. **Seksi G.1 (Input Indikator Mutu & Dokumen Bukti):**
   - *Current issue:* Indicator target is only displayed as small helper text without the full indicator name or standard unit.
   - *Current issue:* Users must manually calculate compliance and gap percentages.
   - *Current issue:* Uploaded evidence files lack document categorization (e.g., whether it is a monthly report, safety incident report, or audit form).
   - *Solution:*
     - Explicit read-only callout banner with indicator name, code, type (INM/IMRS/IMU), and target criteria (e.g., $\ge 100\%$ or $\le 5\text{ min}$).
     - Real-time client-side calculation badge showing achievement status: `🟢 Tercapai (Gap: +X%)` vs `🔴 Belum Tercapai (Gap: -X%)`.
     - File type dropdown for evidence files (`jenis_dokumen_capaian`: Laporan Bulanan, Laporan Insiden, Form Audit, Foto Bukti, SOP, Lainnya).

2. **Seksi G.1 (Evaluasi Capaian & AI Assistance):**
   - *Current issue:* Head of Unit writes free-form narrative in `evaluasi_capaian` without standardized PDCA structure.
   - *Solution:*
     - "📋 Sisipkan Template Panduan" button with 3-part structured format:
       1. *Analisis Capaian*
       2. *Evaluasi Barrier/Mitigasi*
       3. *Kendala di Lapangan*
     - "✨ Buatkan Draf Analisis AI" button calling the DeepSeek AI backend (`api_ai_evaluasi_risiko`) with indicator and realization context, plus a robust rule-based fallback if the API is offline.

3. **Seksi G.2 & G.3 (Status Pelaksanaan per Item & Kalkulator Risiko Sisa):**
   - *Current issue:* Execution status in G.2 is only a single radio button for the entire risk, even when multiple mitigation steps exist.
   - *Current issue:* Residual risk calculation in G.3 requires mental math without immediate visual comparison against inherent risk.
   - *Solution:*
     - Per-action-item execution status radios (`SELESAI`, `SEDANG`, `BELUM`) mapped to `TindakLanjutRisiko` or parsed `rencana_aksi`, with automatic aggregation into overall `status_pelaksanaan`.
     - Inline interactive residual risk calculation card in G.3 with real-time score, color badge, risk reduction percentage, and a clickable 5×5 matrix.

---

## 2. Proposed Changes by Layer

### 2.1 Database & Models (`akreditasi/risiko_models.py`)
- Add `JENIS_DOKUMEN_BUKTI_CHOICES` on `RisikoUnit`:
  - `('LAPORAN_BULANAN', 'Laporan Bulanan Unit')`
  - `('LAPORAN_INSIDEN', 'Laporan Insiden Keselamatan (IKP)')`
  - `('FORM_AUDIT', 'Form Audit / Monitoring Kepatuhan')`
  - `('FOTO_BUKTI', 'Foto Bukti Implementasi / Dokumentasi')`
  - `('SOP_KEBIJAKAN', 'SOP / Kebijakan Terkait')`
  - `('LAINNYA', 'Dokumen Pendukung Lainnya')`
- Add field `jenis_dokumen_capaian = models.CharField('Jenis Dokumen Bukti Capaian', max_length=50, blank=True, default='', choices=JENIS_DOKUMEN_BUKTI_CHOICES)` to `RisikoUnit`.
- Add `@property def rencana_aksi_list(self)` to parse numbered or bulleted action steps into clean item dictionaries `[{'urutan': 1, 'text': '...'}]`.
- Generate migration `0039_risikounit_jenis_dokumen_capaian.py`.

### 2.2 Backend AI Service & Views (`akreditasi/ai_prompts.py`, `akreditasi/ai_service.py`, `akreditasi/ai_views.py`)
- In `akreditasi/ai_prompts.py`:
  - Update `PROMPT_EVALUASI_RISIKO` to incorporate indicator context (`nama_indikator`, `target_capaian`, `capaian_nilai`, `gap_persen`).
  - Request 3-part structured JSON output (`analisis_capaian`, `efektivitas_barrier`, `kendala_lapangan`, `draf_evaluasi`).
- In `akreditasi/ai_service.py`:
  - Enhance `generate_evaluasi_risiko` to pass indicator parameters.
  - Implement smart rule-based fallback generation when DeepSeek API is disabled or unavailable.
- In `akreditasi/ai_views.py`:
  - Pass indicator data from request payload into `generate_evaluasi_risiko`.

### 2.3 Evaluation View & Controller (`akreditasi/risiko_views.py`)
- In `risiko_evaluasi(request, risiko_id)`:
  - Fetch existing `TindakLanjutRisiko` objects via `tindak_lanjut.all().order_by('urutan')`.
  - Handle `jenis_dokumen_capaian` in POST processing.
  - In POST: handle per-item status updates (`tl_status_<id>` or create/update `TindakLanjutRisiko` from `rencana_aksi_list`) and synchronize `risiko.status_pelaksanaan`.
  - Pass `tindak_lanjut_list`, `rencana_aksi_items`, and document choices to context.

### 2.4 Presentation & Frontend (`templates/akreditasi/risiko_evaluasi.html`)
- **Header:** Fix `risiko.nomor_risiko` evaluation to use `risiko.jenis_risiko` and unit name.
- **Section G.1:**
  - Read-only card with indicator name, badge, and explicit target.
  - Real-time gap and achievement badge beside `capaian_nilai`.
  - Category select dropdown for `jenis_dokumen_capaian`.
  - Action buttons: "📋 Sisipkan Template Panduan" and "✨ Buatkan Draf Analisis AI" (with spinner and alert).
- **Section G.2:**
  - Interactive table/list of action items with per-item status radios (`SELESAI`, `SEDANG`, `BELUM`).
  - Auto-calculation of overall `status_pelaksanaan`.
- **Section G.3:**
  - Prominent residual risk calculation card showing:
    `Skor Inherent ➔ Skor Residual | Penurunan Risiko (-X%)`
  - Interactive mini 5×5 matrix where clicking sets slider values.

---

## 3. Step-by-Step Execution Plan

### Task 1: Model & Migration Update (`RisikoUnit`)
- [x] Add `JENIS_DOKUMEN_BUKTI_CHOICES` and `jenis_dokumen_capaian` field to `RisikoUnit` in `akreditasi/risiko_models.py`.
- [x] Add `rencana_aksi_list` property to `RisikoUnit` in `akreditasi/risiko_models.py`.
- [x] Run `python manage.py makemigrations akreditasi` -> generate migration `0039_risikounit_jenis_dokumen_capaian.py`.
- [x] Run `python manage.py migrate akreditasi` on local SQLite.

### Task 2: AI Backend Enhancement (`ai_prompts.py`, `ai_service.py`, `ai_views.py`)
- [x] Update `PROMPT_EVALUASI_RISIKO` in `akreditasi/ai_prompts.py` to accept indicator fields and output 3-part structured narrative.
- [x] Update `generate_evaluasi_risiko` in `akreditasi/ai_service.py` to accept indicator parameters and provide deterministic PDCA fallback if API call fails.
- [x] Update `api_ai_evaluasi_risiko` in `akreditasi/ai_views.py` to extract indicator parameters from JSON body.

### Task 3: View Logic for Per-Item Action Status & Evidence Category (`risiko_views.py`)
- [x] Update `risiko_evaluasi` in `akreditasi/risiko_views.py` to pass action items (`tindak_lanjut` and `rencana_aksi_list`) and document categories.
- [x] In `risiko_evaluasi` POST: save `jenis_dokumen_capaian` and update/create `TindakLanjutRisiko` statuses with auto-synchronization of `risiko.status_pelaksanaan`.

### Task 4: Template Overhaul (`templates/akreditasi/risiko_evaluasi.html`)
- [x] Implement Indicator Callout Card in Seksi G.1.
- [x] Add real-time target comparison & gap badge in Seksi G.1.
- [x] Add document category selector in Seksi G.1.
- [x] Add "Sisipkan Template Panduan" & "Buatkan Draf Analisis AI" buttons and JS in Seksi G.1.
- [x] Implement per-action item status cards/radios in Seksi G.2 with auto-aggregation.
- [x] Implement interactive residual risk calculation card and 5×5 matrix in Seksi G.3.

### Task 5: Testing, Verification, & Quality Gates
- [x] Write unit tests in `akreditasi/tests_evaluasi_indikator.py`:
  - Test model field `jenis_dokumen_capaian` and choices.
  - Test `rencana_aksi_list` parsing.
  - Test `generate_evaluasi_risiko` with indicator context & smart fallback.
  - Test `api_ai_evaluasi_risiko` endpoint.
  - Test `risiko_evaluasi` GET and POST (saving document category and per-item action statuses).
- [x] Run full test suite: `python manage.py test`.
- [x] Run system checks: `python manage.py check`.

---

## 4. Verification Checkpoints

1. **Schema Check:** `python manage.py check` passes with 0 errors.
2. **Unit Tests:** `python manage.py test akreditasi.tests_evaluasi_indikator` passes 100%.
3. **Full Suite:** Existing 69 tests pass with 0 regressions.
4. **Git Hygiene:** Atomic commits per logical layer.
