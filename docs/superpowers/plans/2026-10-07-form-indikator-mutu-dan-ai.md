# Form Indikator Mutu & AI Assistance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide full user management of Quality Indicators (`IndikatorMutu`) directly in ARIMA: a dedicated CRUD form (`/indikator-mutu/baru/` and `/indikator-mutu/<id>/edit/`), sidebar navigation link, quick-action button on dashboard, and DeepSeek AI assistance for generating indicator formulas, dimensions, standards, and action plans.

**Architecture:**
- **Backend View & Form:** Dedicated views `indikator_form` (create/update) in `akreditasi/indikator_views.py` with validation and audit logging.
- **Frontend Template:** `templates/akreditasi/indikator_form.html` adhering to ARIMA design system (Bootstrap 5.3.3, teal accents, clear responsive layout, non-overlapping action buttons).
- **AI Service & Prompts:** New prompt `PROMPT_INDIKATOR_MUTU` in `akreditasi/ai_prompts.py`, backend endpoint `/ai/indikator-mutu/` in `akreditasi/ai_views.py` using `generate_indicator_draft()`.
- **Frontend AI Assist Integration:** Connect "✨ AI Bantu Rumuskan Indikator" button with dynamic field autofill (`numerator`, `denominator`, `target_nilai`, `satuan`, `dimensi_mutu`, `rencana_aksi`).
- **Sidebar & Dashboard Links:** Fix placeholder `{% url 'akreditasi:indikator_dashboard' %}?add=1` to use `{% url 'akreditasi:indikator_tambah' %}` and add "+ Tambah Indikator" button on dashboard header.

**Tech Stack:** Django 5.x, Python 3.12, Bootstrap 5.3.3, DeepSeek Chat API.

**Spec:** User request: "tambahkan menu, untuk bisa mengisi langsung user terkait indikator mutu, dan tambahkan ai seperti yang lain, buat plan".

## Global Constraints

- **Language:** Code, comments, prompts, and plan in English. User UI and messages in Bahasa Indonesia.
- **Security:** DeepSeek API Key stays on the Django backend; sensitive patient data is never forwarded; permissions checked (`can_manage_indikator` or manager/admin role).
- **Design System:** Responsive, standard padding, non-clashing buttons, teal primary accents (`#0f766e` / `var(--accent)`), clean card layouts.
- **TDD:** Write tests for views and AI endpoint before/alongside implementation; keep test suite 100% green.

## Review Focus

1. **Permission Boundaries:** Unit-scoped users may only associate indicators with their assigned unit; non-unit managers can assign to any unit.
2. **Duplicate Code Collision:** `kode_indikator` is `unique=True` in the database; editing must not fail its own unique check, and creating must handle collisions with a friendly validation error.
3. **AI Fallback Resilience:** When DeepSeek API is offline or unconfigured, the AI endpoint must return a structured fallback response or informative error, not a 500 error.
4. **Auto-fill Usability:** AI response format must be reliably parsed JSON so the frontend script can fill the fields accurately with an undo/clear option.
5. **EP Terkait Filtering:** Selection of `StandardItem` (EP) should be optional, cleanly searchable/selectable by chapter.

---

### Task 1: Backend Views, URL Routing & Tests for Indikator Form

**Files:**
- Modify: `akreditasi/indikator_views.py`
- Modify: `akreditasi/urls.py`
- Create: `akreditasi/tests_indikator_form.py`

**Interfaces:**
- Views: `indikator_tambah(request)`, `indikator_edit(request, indikator_id)`
- Consumes: POST form data (`nama_indikator`, `kode_indikator`, `unit`, `jenis`, `dimensi_mutu`, `numerator`, `denominator`, `target_nilai`, `satuan`, `ep_terkait`, `rencana_aksi`, `pj`).
- Produces: Saved or updated `IndikatorMutu` object; redirect to `indikator_detail`.

- [ ] **Step 1: Write failing tests for indicator creation and edit views**

```python
# akreditasi/tests_indikator_form.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu

User = get_user_model()

class IndikatorFormViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_test', 'admin@rs.id', 'password123')
        self.client = Client()
        self.client.force_login(self.user)
        self.unit = UnitKerja.objects.create(name='Instalasi Farmasi', code='FARM-TEST', tipe_unit='DEPO')

    def test_get_tambah_indikator_page(self):
        url = reverse('akreditasi:indikator_tambah')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_post_create_indikator_success(self):
        url = reverse('akreditasi:indikator_tambah')
        payload = {
            'nama_indikator': 'Kepatuhan Waktu Tunggu Resep Racikan',
            'kode_indikator': 'IMP-FARM-TEST-01',
            'unit': self.unit.id,
            'jenis': 'IMP_UNIT',
            'dimensi_mutu': 'TEPAT_WAKTU',
            'numerator': 'Jumlah resep racikan selesai <= 60 menit',
            'denominator': 'Total seluruh resep racikan',
            'target_nilai': '85.00',
            'satuan': '%',
            'rencana_aksi': 'Evaluasi alur compounding harian',
            'pj': 'Kepala Farmasi',
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(IndikatorMutu.objects.filter(kode_indikator='IMP-FARM-TEST-01').exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_form`
Expected: FAIL (Reverse for 'indikator_tambah' not found)

- [ ] **Step 3: Implement views in `akreditasi/indikator_views.py` and register in `akreditasi/urls.py`**

Add `indikator_tambah` and `indikator_edit` views with proper validation and redirect.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_form`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add akreditasi/indikator_views.py akreditasi/urls.py akreditasi/tests_indikator_form.py
git commit -m "feat(indikator): add indikator_tambah and indikator_edit views with tests"
```

---

### Task 2: AI Assistance Prompt & Endpoint for Indikator Mutu

**Files:**
- Modify: `akreditasi/ai_prompts.py`
- Modify: `akreditasi/ai_service.py`
- Modify: `akreditasi/ai_views.py`
- Modify: `akreditasi/urls.py`
- Modify: `akreditasi/tests_indikator_form.py`

**Interfaces:**
- Prompt: `PROMPT_RUMUS_INDIKATOR` in `ai_prompts.py`
- Service: `generate_indicator_draft(user, nama_indikator, unit_name, jenis, fokus_masalah)` -> dict
- View: `api_ai_rumus_indikator(request)` POST endpoint returning JSON

- [ ] **Step 1: Write test for AI indicator endpoint**

```python
    def test_api_ai_rumus_indikator_validation(self):
        url = reverse('akreditasi:api_ai_rumus_indikator')
        res = self.client.post(url, {}, content_type='application/json')
        self.assertEqual(res.status_code, 400)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_form.IndikatorFormViewTest.test_api_ai_rumus_indikator_validation`
Expected: FAIL

- [ ] **Step 3: Implement prompt, service function, and view endpoint**

Implement structured response containing:
`{ "numerator": "...", "denominator": "...", "target_nilai": 85.0, "satuan": "%", "dimensi_mutu": "TEPAT_WAKTU", "rencana_aksi": "..." }`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_form`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add akreditasi/ai_prompts.py akreditasi/ai_service.py akreditasi/ai_views.py akreditasi/urls.py akreditasi/tests_indikator_form.py
git commit -m "feat(ai): add AI assistant endpoint for drafting quality indicators"
```

---

### Task 3: UI Form Template & AI Integration (`indikator_form.html`)

**Files:**
- Create: `templates/akreditasi/indikator_form.html`
- Modify: `templates/includes/sidebar.html`
- Modify: `templates/akreditasi/indikator_dashboard.html`
- Modify: `templates/akreditasi/indikator_detail.html`

**Interfaces:**
- UI components:
  1. Card form with all `IndikatorMutu` fields.
  2. "✨ AI Bantu Rumuskan Indikator" banner/modal with loading spinner and 1-click auto-fill.
  3. Edit button in `indikator_detail.html`.
  4. "+ Tambah Indikator" button on `indikator_dashboard.html`.
  5. Corrected sidebar link to `{% url 'akreditasi:indikator_tambah' %}`.

- [ ] **Step 1: Create `templates/akreditasi/indikator_form.html` with AI assistant integration**
- [ ] **Step 2: Update sidebar and dashboard links**
- [ ] **Step 3: Update `indikator_detail.html` to add edit button**
- [ ] **Step 4: Verify rendering and test suite pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_form`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/akreditasi/indikator_form.html templates/includes/sidebar.html templates/akreditasi/indikator_dashboard.html templates/akreditasi/indikator_detail.html
git commit -m "feat(indikator-ui): add indicator form UI with DeepSeek AI auto-formulation"
```

---

### Task 4: Full Regression Testing & Remote Push

**Files:**
- Run full Django test suite (`manage.py test`).

- [ ] **Step 1: Run complete test suite**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: All tests PASS with zero errors.

- [ ] **Step 2: Push changes to GitHub repository**

```bash
git push origin master
```
