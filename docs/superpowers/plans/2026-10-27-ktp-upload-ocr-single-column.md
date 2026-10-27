# KTP Upload + OCR Auto-Fill & Single-Column Document Form — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Simplify the document upload flows into one vertical column per "Masalah unggah dokumen ganda.docx" — Jenis Dokumen dropdown, Judul Dokumen, Tanggal Terbit (optional), Berlaku Sampai (optional), Pilih Berkas. (2) Add KTP upload with automatic OCR ("Tambahkan Unggah KTP.docx"): when a KTP scan is staged, the backend extracts NIK, Nama, Tempat/Tanggal Lahir, Jenis Kelamin, and Alamat, pre-fills the draft's step-1 personal data, and the operator reviews/corrects before finalization.

**Architecture:** Reuse the existing staged-artifact pipeline instead of building a parallel KTP feature. The intake wizard already stages KTP scans (`stage_intake_attachment`, kind `KTP`), stores per-step JSON in `DrafInputPegawai.draft_data`, and binds staged files into canonical `DokumenPegawai`/`VersiDokumen` (IDENTITY/KTP) at finalization. OCR therefore only pre-fills draft data: it travels the same version-guarded draft-update path, and persistence keeps flowing through `validate_personal_data` → `finalize_staff_intake` unchanged. The review-then-save requirement is satisfied structurally: OCR output lands in an editable draft step. OCR runs over the existing DeepSeek channel (`akreditasi.ai_service._call_deepseek` with a base64 image data URL) — no Tesseract, no new dependency, no extra storage. The HC-side `DokumenForm` template is re-laid-out to one column; no model changes anywhere.

**Tech Stack:** Django 6 forms/views/templates, existing DeepSeek client, existing Supabase private storage, PIL only via existing photo normalizer.

**Spec:** `C:\Users\cubeb\Downloads\Masalah unggah dokumen ganda.docx` and `C:\Users\cubeb\Downloads\Tambahkan Unggah KTP.docx` (user-provided).

## Global Constraints

- Repo layout: templates live at project-level `templates/sdm/...`, not per-app.
- Private binary access only through `sdm/storage.py` (`get_private_storage` / `SupabasePrivateStorage`); never construct storage elsewhere.
- OCR gate: only when `SystemConfig.get_solo().ai_enabled` AND `config.get_deepseek_api_key()`. Without either, upload works exactly as today (OCR silently skipped).
- KTP OCR specifics: the KTP image **is** the payload — do NOT route it through `sanitize_hospital_prompt` (that helper masks NIK/dates out of prompts; here they are the extraction target).
- OCR results are suggestions only. They may only write into `DrafInputPegawai.draft_data['1']`; canonical validation stays `validate_personal_data` at finalize time.
- Bahasa Indonesia for user-facing strings; code identifiers English (repo convention).
- No new Python dependencies. No model/migration changes.
- Test command: `.venv/Scripts/python.exe manage.py test sdm.tests.<module>` from repo root.
- **Measured baseline (2026-10-27): `sdm.tests.test_dokumen` + `sdm.tests.test_intake_uploads` = 45 tests, OK.**

## Review Focus

1. **Blurry/low-quality scans** — OCR returns empty per-field strings. Expectation: empty values never overwrite data the operator already typed, and the upload still succeeds. Pinned by Task 2 `test_ocr_empty_fields_leave_draft_untouched`.
2. **Wrong image staged as KTP** (random photo, receipt) — AI returns nonsense. Expectation: treated like case 1; nothing crashes, no garbage lands in NIK. Pinned by Task 1 `test_garbage_mapping_is_tolerated` (non-digit/oversized NIK dropped).
3. **Duplicate-staged-KTP race** — two tabs stage a KTP concurrently. Existing partial-unique constraint `sdm_lampiran_singleton_staged_uniq` must keep refusing the loser with the existing friendly error, not a 500. Pinned by existing Task 1 test `test_second_staged_ktp_is_refused_before_upload` (must stay green untouched).
4. **OCR timeout / quota / malformed JSON / exception** — service or call raises or returns `success: False`. Expectation: file still stages, user sees a `messages.warning`, flow continues. Pinned by Task 2 `test_ocr_failure_still_stages_file`.
5. **OCR must not bypass finalize validation** — OCR writes raw strings into `draft_data['1']`; a bad read must fail exactly where a manual typo fails (17-digit NIK rejected at finalize). Pinned by Task 1 `test_oversized_nik_is_returned_as_is` (extractor returns raw; validation happens at finalize, unchanged code).

---

### Task 1: KTP OCR extractor + private-object reader

**Files:**
- Create: `sdm/services/ktp_ocr.py`
- Modify: `sdm/storage.py` (append `read_artifact_bytes`)
- Test: `sdm/tests/test_ktp_ocr.py`

**Interfaces:**
- Consumes: `akreditasi.ai_service._call_deepseek(prompt, system_prompt=…, temperature=…, max_tokens=…)` → `{'success': bool, 'data': dict|None, 'error': str|None}` (existing signature, call-compat verified); `sdm.storage.get_private_storage()`.
- Produces: `extract_ktp_fields(image_bytes: bytes, *, actor) -> dict` with keys `('nik','nama_lengkap','tempat_lahir','tanggal_lahir','gender','alamat')` — all plain strings, `''` when unreadable; `tanggal_lahir` normalized `YYYY-MM-DD` or `''`; `gender` ∈ `{'LAKI_LAKI','PEREMPUAN',''}`. Later tasks mock this name — signature is frozen.

- [ ] **Step 1: Write the failing tests**

```python
# sdm/tests/test_ktp_ocr.py
"""Unit tests for the DeepSeek-backed KTP OCR field extractor."""
from unittest import mock

from django.test import TestCase

from sdm.services import ktp_ocr


class ExtractKtpFieldsTests(TestCase):
    def _ai(self, data):
        return {'success': True, 'data': data, 'error': None}

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_happy_path_maps_all_fields(self, ai):
        ai.return_value = self._ai({
            'nik': '3204012509880003',
            'nama': 'Rina Kartika',
            'ttl': 'Bandung, 25-09-1988',
            'gender': 'P',
            'alamat': 'Jl. Melati No. 3 RT/RW 002/005, Cibaduyut, Bandung, Jawa Barat',
        })
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        self.assertEqual(fields['nik'], '3204012509880003')
        self.assertEqual(fields['nama_lengkap'], 'Rina Kartika')
        self.assertEqual(fields['tempat_lahir'], 'Bandung')
        self.assertEqual(fields['tanggal_lahir'], '1988-09-25')
        self.assertEqual(fields['gender'], 'PEREMPUAN')
        self.assertIn('Melati', fields['alamat'])

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_failure_returns_empty_strings(self, ai):
        ai.return_value = {'success': False, 'data': None, 'error': 'timeout'}
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        self.assertEqual(fields, {key: '' for key in ktp_ocr.KTP_OCR_FIELDS})

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_garbage_mapping_is_tolerated(self, ai):
        ai.return_value = self._ai({'nik': 12345, 'unexpected': 'x'})
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        self.assertEqual(fields['nik'], '')            # non-16-digit dropped
        self.assertEqual(fields['nama_lengkap'], '')

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_oversized_nik_is_returned_as_is(self, ai):
        """17 digits pass through raw; finalize validation is the gate, not OCR."""
        ai.return_value = self._ai({'nik': '32040125098800031'})
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        self.assertEqual(fields['nik'], '32040125098800031')

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_disabled_ai_short_circuits(self, ai):
        from akreditasi.system_models import SystemConfig
        config = SystemConfig.get_solo()
        config.ai_enabled = False
        config.save()
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        ai.assert_not_called()
        self.assertEqual(fields, {key: '' for key in ktp_ocr.KTP_OCR_FIELDS})
```

- [ ] **Step 2: Run tests, expect failure**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_ktp_ocr`
Expected: FAIL — `ModuleNotFoundError: No module named 'sdm.services.ktp_ocr'`.

- [ ] **Step 3: Implement**

Append to `sdm/storage.py` (it already owns private-object reads; mirror the hash/size verification idiom of the photo-stream helper around line 390, but read the FULL object):

```python
def read_artifact_bytes(attachment, user):
    """Full private-object bytes for a staged or bound document version.

    Authorization mirrors the download endpoints before any byte is read.
    """
    import hashlib

    from django.core.exceptions import PermissionDenied

    if hasattr(attachment, 'draft'):  # LampiranDrafPegawai
        employee = attachment.draft.finalized_employee
        storage_key, sha256, size = (
            attachment.storage_key, attachment.sha256, attachment.size_bytes,
        )
        if employee is None:
            # Staged-only artifact: stage/remove services have already checked
            # the exact actor; re-check cheaply at read time.
            require_hc_capability(user, 'can_view_hc')
        else:
            require_hc_capability(
                user, 'can_manage_hc_documents', employee=employee,
            )
    else:  # VersiDokumen
        authorize_document_download(user, attachment)  # raises PermissionDenied
        storage_key, sha256, size = (
            attachment.storage_key, attachment.sha256, attachment.size_bytes,
        )
    data = get_private_storage().read(storage_key)
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
        raise PermissionDenied('Objek privat tidak cocok dengan metadata.')
    return data
```

(If `SupabasePrivateStorage.read` does not yet exist, look for the read method the photo helper uses — e.g. `_read_object` / `download` — and call that; do not add a new storage method unless none exists.)

Create `sdm/services/ktp_ocr.py`:

```python
"""OCR extraction of Indonesian KTP fields via the existing DeepSeek channel.

Runs on demand after a KTP is staged; raw OCR text is never stored. Returned
fields are suggestions only — persistence still flows through
validate_personal_data, so a bad read fails exactly where a manual typo would,
and the operator reviews everything before saving (spec step Vrifikasi).
"""
import base64
import re

from akreditasi.ai_service import _call_deepseek

KTP_OCR_FIELDS = (
    'nik', 'nama_lengkap', 'tempat_lahir', 'tanggal_lahir', 'gender', 'alamat',
)

_DDMMYYYY = re.compile(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$')

SYSTEM_PROMPT = (
    'Anda mesin ekstraksi data dari gambar KTP Indonesia. '
    'Balas HANYA JSON sesuai skema yang diminta, tanpa penjelasan.'
)


def _normalize_tanggal(raw):
    if not isinstance(raw, str):
        return ''
    match = _DDMMYYYY.match(raw.strip())
    if not match:
        return ''
    day, month, year = match.groups()
    return f'{year}-{int(month):02d}-{int(day):02d}'


def _normalize_gender(raw):
    token = (raw or '').strip().upper()
    if token.startswith('L'):
        return 'LAKI_LAKI'
    if token.startswith('P'):
        return 'PEREMPUAN'
    return ''


def extract_ktp_fields(image_bytes: bytes, *, actor) -> dict:
    fields = {key: '' for key in KTP_OCR_FIELDS}
    from akreditasi.system_models import SystemConfig

    config = SystemConfig.get_solo()
    if not config.ai_enabled or not config.get_deepseek_api_key():
        return fields
    data_url = 'data:image/jpeg;base64,' + base64.b64encode(image_bytes).decode()
    prompt = (
        f'Gambar KTP (data URL): {data_url}\n'
        'Baca KTP Indonesia di atas dan kembalikan JSON persis dengan kunci: '
        '{"nik": str, "nama": str, "ttl": str, "gender": str, "alamat": str}. '
        'nik = 16 digit NIK. ttl = "Tempat, DD-MM-YYYY". gender = "L" atau "P". '
        'alamat = satu baris lengkap termasuk RT/RW, Kelurahan, Kecamatan, '
        'Kabupaten/Kota, Provinsi. Gunakan "" untuk bagian tidak terbaca.'
    )
    result = _call_deepseek(prompt, system_prompt=SYSTEM_PROMPT,
                            temperature=0.0, max_tokens=600)
    if not result.get('success') or not isinstance(result.get('data'), dict):
        return fields
    data = result['data']
    nik = str(data.get('nik') or '').strip()
    fields['nik'] = nik if nik.isdigit() else ''
    fields['nama_lengkap'] = str(data.get('nama') or '').strip()[:100]
    ttl = str(data.get('ttl') or '').strip()
    if ',' in ttl:
        place, _, raw_date = ttl.partition(',')
        fields['tempat_lahir'] = place.strip()[:100]
    else:
        raw_date = ttl
    fields['tanggal_lahir'] = _normalize_tanggal(raw_date)
    fields['gender'] = _normalize_gender(data.get('gender'))
    fields['alamat'] = str(data.get('alamat') or '').strip()[:500]
    return fields
```

- [ ] **Step 4: Run tests, expect pass**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_ktp_ocr`
Expected: PASS (5 tests, exit 0).

- [ ] **Step 5: Commit**

```bash
git add sdm/services/ktp_ocr.py sdm/tests/test_ktp_ocr.py sdm/storage.py
git commit -m "feat(sdm): KTP OCR field extraction via DeepSeek + private artifact reader"
```

---

### Task 2: Intake step 5 — single-column form + OCR auto-fill of draft step 1

**Files:**
- Modify: `sdm/forms/intake.py:321-356` (`IntakeStep5Form`)
- Modify: `sdm/intake_views.py:110-240` (step-5 POST path)
- Modify: `templates/sdm/pegawai/wizard.html` (step-5 layout only)
- Modify: `static/js/hc-intake-attachments.js` (one announce hook)
- Test: `sdm/tests/test_intake_uploads.py` (extend, reuse its fixture idiom)

**Interfaces:**
- Consumes: `extract_ktp_fields` (Task 1); `stage_intake_attachment` (existing); `DrafInputPegawai.draft_data['1']` (existing).
- Produces: after a successful KTP stage with OCR success, the view redirects to step 1 with OCR values pre-filled in the form initial; nothing else in the wizard changes. Form field names `jenis_berkas`, `judul`, `tanggal_terbit`, `berlaku_sampai`, `berkas` are frozen for the template.

- [ ] **Step 1: Write failing tests** — append to `sdm/tests/test_intake_uploads.py`, copying that module's existing setup idiom (it builds a draft via `stage_intake_attachment` with `SimpleUploadedFile` JPEG bytes and `expected_version`; mirror `test_stage_persists_object_and_metadata`):

```python
def test_ktp_upload_writes_ocr_fields_into_draft_step1(self):
    faked = {'nik': '3204012509880003', 'nama_lengkap': 'Rina Kartika',
             'tempat_lahir': 'Bandung', 'tanggal_lahir': '1988-09-25',
             'gender': 'PEREMPUAN', 'alamat': 'Jl. Melati No. 3'}
    with mock.patch('sdm.intake_views.extract_ktp_fields', return_value=faked):
        self._stage_ktp()  # helper posting the wizard step-5 form
    self.draft.refresh_from_db()
    step1 = self.draft.draft_data.get('1') or {}
    self.assertEqual(step1.get('nik'), '3204012509880003')
    self.assertEqual(step1.get('nama_depan'), 'Rina Kartika')

def test_ocr_empty_fields_leave_draft_untouched(self):
    from sdm.services import ktp_ocr
    self.draft.draft_data['1'] = {'nama_depan': 'Sudah', 'nik': '3204012509880003'}
    self.draft.save()
    blank = {key: '' for key in ktp_ocr.KTP_OCR_FIELDS}
    with mock.patch('sdm.intake_views.extract_ktp_fields', return_value=blank):
        self._stage_ktp()
    self.draft.refresh_from_db()
    self.assertEqual(self.draft.draft_data['1'].get('nama_depan'), 'Sudah')
    self.assertEqual(self.draft.draft_data['1'].get('nik'), '3204012509880003')

def test_ocr_failure_still_stages_file(self):
    with mock.patch('sdm.intake_views.extract_ktp_fields',
                    side_effect=ValueError('boom')):
        response = self._stage_ktp()
    self.assertEqual(response.status_code, 302)  # staged; OCR error never blocks
    self.assertEqual(
        self.draft.attachments.filter(artifact_kind='KTP', state='STAGED').count(),
        1,
    )
```

Adjust the helper name to what exists in the module (read it first; the stage call shape is `stage_intake_attachment(actor=…, draft_id=…, expected_version=…, file_obj=…, artifact_kind='KTP')` posted through the step-5 view).

- [ ] **Step 2: Run, expect the three new tests to fail**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_intake_uploads`
Expected: 3 new FAIL (no OCR wiring yet); existing 14 stay green.

- [ ] **Step 3: Implement**

`sdm/forms/intake.py` — replace the `IntakeStep5Form` field block (`scan_ktp`, `dokumen_berkas`, `dokumen_judul`, `dokumen_jenis_berkas`) with the spec's single flow:

```python
class IntakeStep5Form(forms.Form):
    """Dokumen Pendukung — one vertical flow ("Masalah unggah dokumen ganda")."""

    JENIS_PENDUKUNG_CHOICES = [
        ('KTP', 'KTP'), ('FOTO', 'Foto'), ('IJAZAH', 'Ijazah'),
        ('TRANSKRIP', 'Transkrip Nilai'), ('STR', 'STR'), ('SIP', 'SIP'),
        ('SIPA', 'SIPA'), ('KONTRAK', 'Kontrak Kerja'),
        ('SK_PENGANGKATAN', 'SK Pengangkatan'), ('SPK_RKK', 'SPK RKK'),
        ('URAIAN_TUGAS', 'Uraian Tugas'), ('SERTIFIKAT', 'Sertifikat'),
        ('OTHER', 'Lainnya'),
    ]

    jenis_berkas = forms.ChoiceField(
        label='Jenis Dokumen', choices=JENIS_PENDUKUNG_CHOICES, required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    judul = forms.CharField(
        label='Judul Dokumen', max_length=250, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    tanggal_terbit = forms.DateField(
        label='Tanggal Terbit', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    berlaku_sampai = forms.DateField(
        label='Berlaku Sampai', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    foto_profil = forms.FileField(
        label='Pas Foto Resmi', required=False,
        help_text='JPG/JPEG, minimal 200×200 piksel.',
        widget=forms.ClearableFileInput(attrs={'class': FIELD_CLASS, 'accept': 'image/jpeg'}),
    )
    berkas = forms.FileField(
        label='Pilih Berkas', required=False,
        help_text='PDF atau JPG, maksimal 5 MiB.',
        widget=forms.ClearableFileInput(attrs={'class': FIELD_CLASS, 'accept': '.pdf,image/jpeg'}),
    )
```

`sdm/intake_views.py` — in the step-5 POST block replace the `uploads = [...]` construction (lines ~148-156) with:

```python
from sdm.services.ktp_ocr import extract_ktp_fields  # top of module

uploads = [('foto_profil', 'FOTO_PROFIL')]
selected_kind = (cleaned.get('jenis_berkas') or '').strip()
if form.cleaned_data.get('berkas'):
    kind = selected_kind if selected_kind in dict(
        IntakeStep5Form.JENIS_PENDUKUNG_CHOICES
    ) else 'OTHER'
    uploads.append(('berkas', kind))
```

Keep the existing stage loop, roll-back-on-error, and `INTAKE_ARTIFACT_EXTENSIONS` validation untouched. Right after a successful stage loop (still inside the `with transaction.atomic():` + version check), run OCR for the staged KTP:

```python
if any(kind == 'KTP' for _field, kind in uploads):
    staged_ktp = next(
        (a for a in staged if a.artifact_kind == 'KTP'), None)
    if staged_ktp is not None:
        try:
            with staged_ktp.open() as handle:
                image_bytes = handle.read()
            fields = extract_ktp_fields(image_bytes, actor=request.user)
        except Exception:
            fields = None
        if fields:
            merged = dict(locked.draft_data or {})
            step1 = dict(merged.get('1') or {})
            for key in ('nik', 'nama_lengkap', 'tanggal_lahir', 'gender', 'alamat'):
                value = (fields.get(key) or '').strip()
                if value and not (step1.get(key) or '').strip():
                    target = 'nama_depan' if key == 'nama_lengkap' else key
                    step1.setdefault(target, value)
            merged['1'] = step1
            locked.draft_data = merged
            locked.save(update_fields=['draft_data', 'updated_at'])
        else:
            messages.warning(
                request,
                'KTP tersimpan, namun pembacaan otomatis (OCR) tidak '
                'berhasil. Lengkapi data identitas secara manual.',
            )
```

OCR is best-effort: any exception leaves the staged file intact. A barcode of `messages.warning` belongs after the redirect branch so it survives the GET.

On step-5 success redirect, send the operator to step 1 for review when OCR found anything:

```python
if step < 5:
    if any(kind == 'KTP' for _f, kind in uploads) and step1_merged:
        return redirect('sdm:pegawai_wizard_resume', step=1, draft_id=draft.pk)
    return redirect('sdm:pegawai_wizard_resume', step=step + 1, draft_id=draft.pk)
```

(`step1_merged` = bool captured where draft_data was updated. `DrafInputPegawai` stage-1 initial rendering at `intake_views.py:242` already re-hydrates from `draft_data['1']`, which is why no extra template work is required for auto-fill.)

`templates/sdm/pegawai/wizard.html` — inside the step-5 `{% if step == 5 and draft %}` region keep the attachments panel; ensure the form fields render one per full-width row in spec order (jenis, judul, tanggal_terbit, berlaku_sampai, foto, berkas). The generic `{% for field in form %}` loop uses `col-12 col-md-6`; override to `col-12` for step 5 only:

```html
<div class="row g-3">
    {% for field in form %}
    <div class="col-12 {% if step != 5 %}col-md-6{% endif %}">
        …existing field rendering…
    </div>
    {% endfor %}
</div>
```

Also add below the jenis dropdown a one-line hint only on step 5:

```html
{% if step == 5 %}
<div class="form-text small">Pilih <strong>KTP</strong> untuk pengisian otomatis NIK, nama, dan alamat via OCR.</div>
{% endif %}
```

`static/js/hc-intake-attachments.js` — after `announce(zone, files[0]);` add:

```js
document.dispatchEvent(new CustomEvent('hc-attachment-picked', {detail: {name: file.name}}));
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_intake_uploads`
Expected: PASS (14 existing + 3 new = 17, exit 0; existing stale-version/PNG/oversize tests untouched-green).

- [ ] **Step 5: Whole-app regression** — `grep -rn "dokumen_judul\|dokumen_jenis_berkas\|scan_ktp" sdm/ templates/` must return only matches inside `draft_data` JSON consumers or nothing; update any straggler in this commit.

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_intake sdm.tests.test_intake_uploads sdm.tests.test_dokumen`
Expected: PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add sdm/forms/intake.py sdm/intake_views.py templates/sdm/pegawai/wizard.html static/js/hc-intake-attachments.js sdm/tests/test_intake_uploads.py
git commit -m "feat(sdm): KTP OCR auto-fill of intake step 1 + single-column step-5 form"
```

---

### Task 3: HC upload form (DokumenForm) — single-column layout with dates + kind

**Files:**
- Modify: `templates/sdm/dokumen/form.html` (layout only)
- Test: `sdm/tests/test_dokumen.py::DocumentKindFieldTests` (must stay green, no field changes)

**Interfaces:**
- Consumes: existing `DokumenForm` fields: `document_type`, `jenis_berkas`, `title`, `sensitivity`, `file`, `issued_date`, `valid_until`.
- Produces: purely presentational change; no route, model, or form signature change.

- [ ] **Step 1: Baseline gate (already measured)**

`sdm.tests.test_dokumen` currently passes (included in the 45-test baseline). If it is not green before edits, stop and report the tree state — do not build on a red baseline.

- [ ] **Step 2: Re-layout the template**

Replace the generic two-column loop in `templates/sdm/dokumen/form.html` (lines 23-31) with the spec's single-column vertical order — Jenis Dokumen (`jenis_berkas` first, per spec item 1), Judul (`title`), Tanggal Terbit (`issued_date`), Berlaku Sampai (`valid_until`), then Pilih Berkas (`file`); keep `document_type` and `sensitivity` as collapsed advanced selects at the bottom (they remain required by the model — hiding them would break `test_health_document_without_health_capability_is_a_form_error`):

```html
<div class="row g-3">
    {% for field in form %}
    <div class="col-12">
        <label class="form-label small fw-semibold" for="{{ field.id_for_label }}">{{ field.label }}{% if field.field.required %} <span class="text-danger" aria-hidden="true">*</span>{% endif %}</label>
        {{ field }}
        {% if field.help_text %}<div class="form-text small">{{ field.help_text }}</div>{% endif %}
        {% for error in field.errors %}<div class="invalid-feedback d-block small">{{ error }}</div>{% endfor %}
    </div>
    {% endfor %}
</div>
```

Field ORDER comes from the form: reorder `DokumenForm.Meta.fields` to `['jenis_berkas', 'title', 'issued_date', 'valid_until', 'file', 'document_type', 'sensitivity']` (declared extra fields `file`, `issued_date`, `valid_until` must move before `Meta` selects only by widget order in the template loop — Django renders in `Meta.fields` order plus declared-before-Meta fields first; verify with `DokumenForm().fields.keys()` in a shell and adjust declaration order, not the template, if the sequence is off).

- [ ] **Step 3: Run tests**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_dokumen`
Expected: PASS (same count as its share of the baseline; exit 0).

- [ ] **Step 4: Commit**

```bash
git add templates/sdm/dokumen/form.html sdm/forms/dokumen.py
git commit -m "feat(sdm): single-column HC document upload form layout"
```

---

### Task 4: Final gate

- [ ] **Step 1: Full HC regression**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_dokumen sdm.tests.test_intake sdm.tests.test_intake_uploads sdm.tests.test_ktp_ocr sdm.tests.test_private_documents sdm.tests.test_dokumen_kredensial`
Expected: PASS, exit 0.

- [ ] **Step 2: Reconcile counts**

Compare `Ran N tests` against the baseline (45 for the two baseline modules) plus the new test files' counts printed by their own runs. Any unexplained drop is a stop-and-report.

- [ ] **Step 3: Manual proof of spec conformance (browser)**

1. Log in as an HC manager; open Input Pegawai step 5; choose Jenis Dokumen = KTP; upload a JPG KTP scan.
2. Confirm redirect to step 1 with NIK/nama/alamat pre-filled; correct one field; continue to finalize.
3. Open Unggah Dokumen from an employee profile; confirm single-column order and successful personnel upload.

## Explicitly NOT in this plan

- **Do not** switch OCR to Tesseract/PaddleOCR or add any local ML runtime.
- **Do not** store raw OCR text or send KTP images anywhere but the existing DeepSeek endpoint.
- **Do not** touch `store_private_document`, `bind_intake_attachments`, `validate_personal_data`, or the version-conflict machinery — reuse as-is.
- **Do not** implement live camera capture; `<input type="file" accept>` already covers mobile gallery/camera.
- Adjacent known gaps observed but not addressed here (recorded, not fixed): `dokumen_upload` still writes `jenis_berkas` via a second `document.save()` after `store_private_document` returns (acceptable; noted for a future signature extension of `store_private_document`).

---

## Execution Status (2026-10-27)

**Done**

- **Task 1** — `sdm/services/ktp_ocr.py` (`extract_ktp_fields`, DeepSeek vision via data-URL, AI gate `SystemConfig.ai_enabled` + API key), 5 unit tests in `sdm/tests/test_ktp_ocr.py`, all green. Plan snippet defects fixed during implementation: (a) tests need `SystemConfig.ai_enabled=True` AND `ai_api_key` set — default test DB has both off/empty; (b) `mock.patch.object(ktp_ocr, '_call_deepseek')` requires the patched attribute name, an earlier `_call_deepseek`-rename artifact. `read_artifact_bytes` from the plan was NOT built: the OCR helper reuses the existing `SupabasePrivateStorage.fetch_object` + the view's staged artifact `storage_key` directly — the plan's reader duplicated an existing capability (redundant abstraction, cut).
- **Task 2** — `IntakeStep5Form` flattened to spec single-flow (`jenis_berkas`,`judul`,`tanggal_terbit`,`berlaku_sampai`,`foto_profil`,`berkas`); step-5 staging loop builds uploads from the single `berkas` + dropdown; `bind_intake_attachments` now consumes `step5.judul` (was `dokumen_judul`) and sets `issued_date`/`valid_until` on `VersiDokumen` from the new date fields; wizard template renders step 5 one-column with OCR hint; drop-zone JS emits `hc-attachment-picked`. 18 tests green in `test_intake_uploads` incl. 4 new OCR tests.
- **Task 3** — `DokumenForm` Meta.fields reordered to spec (kind, title, issued, valid, file, then model-required `document_type`+`sensitivity`), template one-column. 31 tests green in `test_dokumen`.
- **Task 4 (partial)** — `manage.py check` clean; 42 tests green across test_intake + test_intake_uploads + test_ktp_ocr; wide regression batch launched (result pending notification).

**Plan deviation (correction, recorded):** the plan placed OCR + pre-fill INSIDE the step-5 `transaction.atomic()` while the draft row was `select_for_update`-locked. DeepSeek latency (seconds) inside that lock would stall any concurrent draft save. Implemented instead as `_run_ktp_ocr` running AFTER the draft-save transaction commits, re-guarding on `pk + version` before the draft_data write — same version-guard invariant, no lock-held network I/O.

**Invariant preserved:** OCR values fill EMPTY step-1 fields only (`fill-empty-only`); existing operator input (`Budi` vs OCR name) is never clobbered — pinned by `test_ktp_upload_writes_ocr_fields_into_draft_step1`.

**Not done, needs live environment**

- DeepSeek OCR against a REAL KTP scan (spec says vision-capable model required — `deepseek-chat` is text-only; a vision model (e.g. a multimodal model behind the same chat/completions API) must be configured in SystemConfig `ai_model_name` or the call will 4xx and the warning path shows). No real key/scan available in this session; go test with one real scan before rollout.
- Manual browser proof of the wizard flow (Task 4 step 3 of the plan).

**Skipped on purpose**

- Worktree execution attempted and abandoned: the Supabase private-storage env vars exist only in the root repo `.env` flow; the worktree had no storage config and its baseline failed (3 failures = environment, not code). Execution continued on feature branch `feat/ktp-ocr-single-column` in the root checkout instead (baseline re-measured there: 45 OK).
