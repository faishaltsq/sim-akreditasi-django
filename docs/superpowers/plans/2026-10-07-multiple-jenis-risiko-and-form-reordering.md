# Multiple Risk Types & Problem-First Form Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Risk Register input form (`risiko_form.html`) so that Problem statement (`masalah`) and Baseline data (`data_pendukung`) are positioned before Category & Risk Types, allow multiple Risk Types (`jenis_risiko`) per entry, interlink problem context with dynamic category/risk suggestions, and enhance AI assistance.

**Architecture:**
- **Model & Database Migration:** Upgrade `RisikoUnit.jenis_risiko` from `CharField(max_length=200)` to `TextField('Jenis Risiko')` to support multiple risk entries (newline or semicolon-separated) without truncation, keeping full backward compatibility with existing 345 imported records.
- **Form UI Reordering & Interconnection:** Reorder Section A:
  1. Header: Unit Kerja, Tahun, Periode.
  2. Problem Context First: `masalah` (Issue Statement) and `data_pendukung` (Baseline Data).
  3. Classification & Dynamic Multi-Select: `kategori_risiko` dropdown with interactive category guide.
  4. Multi-item `jenis_risiko`: Tag/chip input with pre-filled suggestions based on category, allowing users to pick multiple risk types or add custom ones.
  5. Interconnection Helper: "✨ AI Analisis Masalah & Sarankan Risiko" button that reads `masalah` + `data` and suggests category and risk types automatically.
- **Backend View & AI Enrichment:** Update `risiko_input` in `akreditasi/risiko_views.py` to process multiple `jenis_risiko` items from POST (array or comma/newline-separated list). Update `api_ai_mitigasi_risiko` and `ai-assist.js` to handle multi-risk contexts.
- **Display Layer:** Update `risiko_detail.html` and `risiko_daftar.html` to render multiple risk types gracefully as badge chips or bulleted list.

**Tech Stack:** Django 5.x, Python 3.12, PostgreSQL / SQLite, Bootstrap 5.3.3, Vanilla JS.

**Spec:** User prompt & attachment `Downloads/Lakukan perubahan di input resiko terkait masalah, data kategori dan jenis resiko.docx`.

## Global Constraints

- **Language:** Code, comments, prompts, and plans in English. User UI labels in Bahasa Indonesia.
- **Backward Compatibility:** All existing 345 `RisikoUnit` records must remain valid without data loss or breaking display.
- **Security:** DeepSeek API Key remains backend-only; patient data is sanitized before AI calls.
- **UI Integrity:** Responsive Bootstrap 5.3.3 layout; buttons must not clash or overlap; forms must support both mobile and desktop viewports.
- **TDD:** Write unit and integration tests covering multi-value risk inputs, form submissions, and AI payload handling.

## Review Focus

1. **Legacy String vs Multi-Value Handling:** Existing records store a single string like `"Kesalahan pemberian obat"`. The display helper must parse both legacy single strings and multi-item strings (comma, semicolon, or newline delimited) consistently.
2. **Length Overflow Protection:** When users select 4-5 risk items, the combined length could exceed 200 characters. Migrating to `TextField` prevents database errors.
3. **POST Payload Format:** If submitted as multiple form fields with the same name (`jenis_risiko[]` or newline-joined string), the backend must extract `request.POST.getlist('jenis_risiko')` or handle combined strings seamlessly.
4. **AI Mitigation Context:** AI prompt must handle multi-item risks clearly so the resulting action plan addresses each identified risk facet.
5. **Form Validation:** At least one `jenis_risiko` must still be required; empty submissions must be rejected gracefully with user-friendly alerts.

---

### Task 1: Model Upgrade & Migration for Multi-Item `jenis_risiko`

**Files:**
- Modify: `akreditasi/risiko_models.py`
- Test: `akreditasi/tests_manajemen_risiko_515.py`
- Auto-generate: `akreditasi/migrations/0030_...py`

**Interfaces:**
- `RisikoUnit.jenis_risiko`: Changed to `models.TextField('Jenis Risiko')`.
- Helper property `RisikoUnit.jenis_risiko_list`: Returns a list of trimmed risk items split by newline, comma, or semicolon.

- [ ] **Step 1: Write test for multi-item `jenis_risiko` handling and `jenis_risiko_list` property**

```python
# In akreditasi/tests_manajemen_risiko_515.py or a dedicated test
def test_multi_jenis_risiko_property(self):
    risiko = RisikoUnit(
        unit=self.unit,
        tahun=2026,
        periode='TRIWULAN_1',
        kategori_risiko='KLINIS',
        jenis_risiko='Medication Error; Keterlambatan Pelayanan Farmasi; Resep Tidak Terbaca',
        dampak=3,
        probabilitas=3,
        strategi_mitigasi='KURANGI',
    )
    items = risiko.jenis_risiko_list
    self.assertEqual(len(items), 3)
    self.assertIn('Medication Error', items)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: FAIL (AttributeError: 'RisikoUnit' object has no attribute 'jenis_risiko_list')

- [ ] **Step 3: Modify `RisikoUnit` in `akreditasi/risiko_models.py`**

Change `jenis_risiko` to `TextField` and add `jenis_risiko_list` property helper:
```python
jenis_risiko = models.TextField('Jenis Risiko')

@property
def jenis_risiko_list(self):
    if not self.jenis_risiko:
        return []
    # Split by newline or semicolon or bullet
    import re
    items = re.split(r'[\n;\r]+', self.jenis_risiko)
    return [item.strip() for item in items if item.strip()]
```

- [ ] **Step 4: Generate and apply migration**

```bash
.venv/Scripts/python.exe manage.py makemigrations akreditasi
.venv/Scripts/python.exe manage.py migrate akreditasi
```

- [ ] **Step 5: Run tests to verify PASS**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: PASS

---

### Task 2: Backend View Support for Multiple `jenis_risiko` & AI Analysis Endpoint

**Files:**
- Modify: `akreditasi/risiko_views.py`
- Modify: `akreditasi/ai_views.py`
- Modify: `akreditasi/ai_service.py`
- Modify: `akreditasi/ai_prompts.py`
- Modify: `akreditasi/urls.py`

**Interfaces:**
- View `risiko_input`: Reads `request.POST.getlist('jenis_risiko')` or `request.POST.get('jenis_risiko')`, joins multiple selections with newlines if needed, and validates.
- AI Endpoint `POST /ai/analisis-masalah-risiko/`: Accepts `masalah`, `data_pendukung`, and `unit_name`, returns recommended `kategori_risiko` and list of potential `jenis_risiko` candidates.

- [ ] **Step 1: Write test for multi-value POST handling in `risiko_input` and AI endpoint**

```python
def test_post_multi_jenis_risiko(self):
    url = reverse('akreditasi:risiko_input')
    payload = {
        'unit': self.unit.id,
        'tahun': 2026,
        'periode': 'TRIWULAN_1',
        'kategori_risiko': 'KLINIS',
        'masalah': 'Sering terjadi salah baca resep',
        'data': 'Ada 3 laporan KNC per bulan',
        'jenis_risiko': ['Salah dosis racikan', 'Keterlambatan penyerahan obat'],
        'deskripsi_risiko': 'Risiko kesalahan terapi obat',
        'dampak': 4,
        'probabilitas': 3,
        'strategi_mitigasi': 'KURANGI',
        'rencana_aksi': 'Double check resep',
        'pj_mitigasi': 'Ka Farmasi',
    }
    res = self.client.post(url, payload)
    self.assertEqual(res.status_code, 302)
    created = RisikoUnit.objects.latest('id')
    self.assertIn('Salah dosis racikan', created.jenis_risiko)
    self.assertIn('Keterlambatan penyerahan obat', created.jenis_risiko)
```

- [ ] **Step 2: Update `risiko_views.py` to extract list of `jenis_risiko`**

```python
jenis_raw = request.POST.getlist('jenis_risiko')
if len(jenis_raw) == 1 and ('\n' in jenis_raw[0] or ';' in jenis_raw[0] or ',' in jenis_raw[0]):
    jenis_str = jenis_raw[0].strip()
elif len(jenis_raw) > 1:
    jenis_str = '\n'.join([j.strip() for j in jenis_raw if j.strip()])
else:
    jenis_str = (jenis_raw[0] if jenis_raw else '').strip()
```

- [ ] **Step 3: Add `PROMPT_ANALISIS_MASALAH_RISIKO` and AI endpoint `/ai/analisis-masalah-risiko/`**

Create prompt in `ai_prompts.py` and service method in `ai_service.py` to classify problem statement and baseline data into category + risk items.

- [ ] **Step 4: Run test to verify PASS**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_manajemen_risiko_515`
Expected: PASS

---

### Task 3: Reorder Form Layout & Implement Multi-Risk Dynamic Chips in `risiko_form.html`

**Files:**
- Modify: `templates/akreditasi/risiko_form.html`
- Modify: `static/js/ai-assist.js`

**Interfaces:**
- Layout Order:
  1. Unit Kerja, Tahun, Periode
  2. **Masalah & Data / Bukti Pendukung** (prominently at top of Section A with AI helper button)
  3. **Kategori Risiko** (with updated responsive guide)
  4. **Jenis Risiko Multi-Input** (Interactive tag container where clicking chips adds to selection, plus text input to add custom risks; tags can be removed with a click; hidden inputs or structured text passed to form submission)
- AI helper button: "✨ AI Analisis Masalah & Sarankan Kategori/Risiko" directly next to Masalah & Data Pendukung.

- [ ] **Step 1: Update `risiko_form.html` layout structure**
  - Place `masalah` and `data` directly after `unit`/`tahun`/`periode`.
  - Add "✨ AI Sarankan Kategori & Risiko" button right beneath the problem fields.
  - Place `kategori_risiko` and `kategori-guide` below `masalah`.
  - Implement dynamic multi-select chip interface for `jenis_risiko`:
    - Shows category-specific risk templates as clickable badges.
    - Click badge -> adds to "Risiko Terpilih" chip list.
    - Free text input allows typing custom risk and pressing Enter or "+ Tambah".
    - Selected risks render with a badge and 'x' remove icon.
- [ ] **Step 2: Update `ai-assist.js`**
  - Adjust DOM queries to match new layout order.
  - Collect all selected `jenis_risiko` chips when requesting mitigation.
- [ ] **Step 3: Manual & Automated verification of form submission**
  - Test submitting form with multiple risk selections.
  - Ensure CSRF and validation operate smoothly.

---

### Task 4: Update Detail & Daftar Views for Multi-Risk Rendering

**Files:**
- Modify: `templates/akreditasi/risiko_detail.html`
- Modify: `templates/akreditasi/risiko_daftar.html`
- Modify: `templates/akreditasi/risiko_evaluasi.html`

**Interfaces:**
- In `risiko_detail.html`: Render `risiko.jenis_risiko_list` as distinct badge chips or bulleted list instead of a flat string.
- In `risiko_daftar.html`: Display items with badge pills or line-breaks so multiple risks are easily readable.
- In `risiko_evaluasi.html`: Display multiple risks cleanly.

- [ ] **Step 1: Update templates to iterate over `risiko.jenis_risiko_list`**
- [ ] **Step 2: Verify template rendering with tests**

---

### Task 5: Full Regression Testing & Remote Push

**Files:**
- Run full test suite (`manage.py test`).

- [ ] **Step 1: Run full test suite**
Run: `.venv/Scripts/python.exe manage.py test`
Expected: 111+ tests PASS with zero errors.

- [ ] **Step 2: Commit and push changes**
```bash
git add akreditasi/ templates/ static/ docs/
git commit -m "feat(risiko): reorder form to problem-first, allow multiple jenis_risiko with AI suggestions"
git push origin master
```
