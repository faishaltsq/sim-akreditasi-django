# Implementation Plan: Patient Admission KTP Scan OCR & UI/UX Upgrade

**Goal:** Implement automated KTP scanning/OCR, flexible birthdate manual input (`DD/MM/YYYY` / `YYYY-MM-DD`), real-time NIK & phone number validation, sticky submit button, and STARKES SKP 1 / MRMIK identity verification compliance for the Admission & Registration Dashboard (`/pasien/pendaftaran/`), as specified in `Input data pasien menggunakan scan ktp pendaftaran.docx`.

**Target Architecture:**
1. **Model & Storage:** Add `foto_ktp` (`FileField`) to `Pasien` model to retain KTP scans for medical record verification (STARKES SKP 1 & MRMIK).
2. **KTP OCR Service:** `pasien/services/ktp_ocr.py` using DeepSeek Vision API (`_call_deepseek`) with base64 data URLs + local regex heuristic fallback, extracting NIK, full name, birthplace, birthdate, gender, blood type, full address, RT/RW, kelurahan, kecamatan, kota/kab, religion, and marital status.
3. **Flexible Date & NIK Decoding:** `pasien/services/ktp_validator.py` supporting `DD/MM/YYYY`, `MM/DD/YYYY`, and `YYYY-MM-DD` manual inputs, plus 16-digit Indonesian NIK structure validation and demographic cross-referencing.
4. **API Endpoints:**
   - `POST /pasien/api/ocr-ktp/`: extracts KTP fields from image file or webcam base64 stream.
   - `GET /pasien/api/cek-nik/?nik=...`: live NIK duplicate check and SatuSehat validation status.
5. **UI/UX Upgrade:**
   - Shortcut "Scan / Upload KTP" button with modal supporting webcam snapshot and file drag-and-drop.
   - KTP photo thumbnail preview inside the form.
   - Flexible birthdate input with live calculated age display.
   - Live 16-digit NIK counter and demographic mismatch warning.
   - Sticky card footer ensuring the "Simpan Pasien Baru & Daftarkan Kunjungan" button is always visible.
   - STARKES SKP 1 dual-identity verification badge.

---

### Task 1: Database Model & Migration for Patient KTP Scan (`foto_ktp`)
- **Files:**
  - Modify: `pasien/models.py` (add `foto_ktp` field to `Pasien` model)
  - Create: `pasien/migrations/0018_pasien_foto_ktp.py`
  - Create: `pasien/tests_ktp_model.py`
- **Verification:**
  - Unit test verifying `foto_ktp` upload and URL generation.
  - `.venv/Scripts/python manage.py test pasien.tests_ktp_model --keepdb` passes.

---

### Task 2: Backend Flexible Date Parser & Indonesian NIK Decoder
- **Files:**
  - Create: `pasien/services/ktp_validator.py`
  - Create: `pasien/tests_ktp_validator.py`
- **Features:**
  - `parse_flexible_date(raw_str)`: parses `DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY-MM-DD`, `DD-MM-YYYY` into Python `date`.
  - `decode_nik(nik_str)`: decodes province, regency, birthdate (accounting for female day +40), and gender from 16-digit NIK.
  - `validate_nik(nik_str, expected_gender=None, expected_dob=None)`: returns validation tuple and warnings.
- **Verification:**
  - Unit test covering standard, female, leap year, and invalid NIKs.
  - `.venv/Scripts/python manage.py test pasien.tests_ktp_validator --keepdb` passes.

---

### Task 3: KTP OCR Service & Extraction API Endpoints
- **Files:**
  - Create: `pasien/services/ktp_ocr.py`
  - Modify: `pasien/views.py` (add `api_ocr_ktp`, `api_cek_nik`, and update `kunjungan_baru` to save `foto_ktp` and parse flexible birthdate)
  - Modify: `pasien/urls.py` (register routes `api/ocr-ktp/` and `api/cek-nik/`)
  - Create: `pasien/tests_pendaftaran_ocr_api.py`
- **Features:**
  - `extract_ktp_pasien(image_bytes)`: returns structured patient dictionary.
  - `api_ocr_ktp`: handles multipart and base64 JSON payload, returning structured fields + thumbnail + NIK decoding.
  - `api_cek_nik`: checks for existing patient with identical NIK to prevent duplicate records.
- **Verification:**
  - Unit tests for OCR endpoint with mocked DeepSeek responses, error fallbacks, and NIK checks.
  - `.venv/Scripts/python manage.py test pasien.tests_pendaftaran_ocr_api --keepdb` passes.

---

### Task 4: Frontend UI/UX Enhancement on `pendaftaran_dashboard.html`
- **Files:**
  - Modify: `templates/pasien/pendaftaran_dashboard.html`
- **Features:**
  - Top shortcut button in Kotak 2: `<button id="btnScanKtp" class="btn btn-outline-success btn-sm">Scan / Upload KTP</button>`.
  - KTP Scanner Modal: webcam snapshot (`navigator.mediaDevices.getUserMedia`) and file drag-and-drop.
  - KTP thumbnail card in Section A with clear/replace capability.
  - Manual flexible birthdate input (`DD/MM/YYYY`) with real-time age calculation indicator (`... tahun ... bulan`).
  - Real-time 16-digit NIK formatter, counter badge, and demographic mismatch alert.
  - Real-time phone number sanitization (`08xxxxxxxxxx`).
  - Sticky bottom footer for Kotak 2 submit button (`.card-footer-sticky`).
  - STARKES SKP 1 badge (Dual-identity verified).
- **Verification:**
  - Template tests in `pasien/tests_pendaftaran_ktp_ui.py`.
  - `.venv/Scripts/python manage.py test pasien.tests_pendaftaran_ktp_ui --keepdb` passes.

---

### Task 5: EMR KTP Display Integration & STARKES MRMIK Compliance
- **Files:**
  - Modify: `templates/pasien/kunjungan_detail.html`
  - Modify: `templates/pasien/pasien_detail.html`
  - Modify: `templates/pasien/cetak_formulir_pendaftaran.html`
- **Features:**
  - Display KTP scan thumbnail with lightbox/modal preview in patient clinical record.
  - Indicate STARKES SKP 1 & MRMIK verification status on printed admission form.
- **Verification:**
  - Template tests verifying KTP badge and thumbnail render when `foto_ktp` exists.

---

### Task 6: Full Regression, End-to-End Verification & Static Assets
- **Verification:**
  - Run all patient test suites (`pasien.tests_*`).
  - Run smoke test on admission endpoints.
  - Run `collectstatic --noinput`.

---

## Execution Status
- **Task 1 (Model `foto_ktp` & Migrations):** DONE (`pasien/migrations/0018_pasien_foto_ktp.py`, unit test passing). Commit `998f996`.
- **Task 2 (Flexible Date Parser & 16-Digit NIK Decoder):** DONE (`pasien/services/ktp_validator.py`, 7 unit tests passing). Commit `3af2990`.
- **Task 3 (KTP OCR DeepSeek Vision & API Endpoints):** DONE (`pasien/services/ktp_ocr.py`, `POST /pasien/api/ocr-ktp/`, `GET /pasien/api/cek-nik/`). Commit `cff2daf`.
- **Task 4 (Frontend UI/UX, Webcam Modal, Sticky Footer, Realtime Calc):** DONE (`templates/pasien/pendaftaran_dashboard.html`, unit test `pasien.tests_pendaftaran_ktp_ui` passing). Commit `9f2134f`.
- **Task 5 (EMR KTP Integration & STARKES SKP 1 / MRMIK Compliance):** DONE (`templates/pasien/pasien_detail.html`, `templates/pasien/kunjungan_detail.html`, `templates/pasien/cetak_formulir_pendaftaran.html`, unit test `pasien.tests_ktp_emr_integration` passing). Commit `9f2134f`.
- **Task 6 (Regression & Verification):** DONE (274 test cases passed in 264.8s, smoke test HTTP 200 OK, `collectstatic` 386 files processed).

