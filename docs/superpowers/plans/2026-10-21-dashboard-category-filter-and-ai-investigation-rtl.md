# Dashboard Category Filter Fix + AI Investigation & RTL Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the dashboard's "Indikator Mutu" dropdown from acting on an indicator outside the selected category, and add an AI generator that drafts the investigation summary (G.4) and follow-up plan / RTL (G.5) of a risk evaluation.

**Architecture:** Two independent workstreams. (A) One server-side correctness fix in the shared dashboard context builder plus a client-side filter-reset hook. (B) One new AI capability built along the exact seams the existing eight AI features already use: a prompt constant in `ai_prompts.py`, a `generate_*` function in `ai_service.py` with a deterministic rule-based fallback, a `@login_required @require_POST @rate_limit` endpoint in `ai_views.py`, and buttons in the two risk templates. No new models, no migrations.

**Tech Stack:** Django 6.1.2, server-rendered templates, Bootstrap 5.3.3 (CDN), vanilla JS, DeepSeek chat-completions API (backend-only, key never reaches the browser).

**Spec:** `C:\Users\cubeb\Downloads\Masalah.docx` — user-supplied problem report (screenshot + suggested fix). The report's diagnosis is partially wrong; see "Root Cause Analysis" below. This plan implements the *reported symptom*, not the report's proposed code.

## Global Constraints

- Python for every `manage.py` command: `C:/Users/cubeb/orca/workspaces/sim-akreditasi-django/medaka/.venv/Scripts/python.exe` (Django 6.1.2). The system `python` has no Django.
- Working directory for all commands: `C:/Users/cubeb/orca/workspaces/sim-akreditasi-django/larvacean`.
- All user-visible copy, prompts, and fallback strings are **Bahasa Indonesia**. Code comments and this plan are English.
- The DeepSeek API key must never appear in any JSON response, template, or log line. `_call_deepseek` already enforces this; do not bypass it.
- Every new AI endpoint must be gated by `@login_required`, `@require_POST`, `@rate_limit(max_calls=12, window=60, scope='ai')`, and the `SystemConfig` module toggle, matching the existing eight endpoints.
- Every new AI function must return a usable `fallback` payload when AI is disabled or has no key — never a 500, never an empty form. Tests run with no API key.
- Do not touch `staticfiles/` in the tasks. `collectstatic` runs once in the final gate (Task 8) and its `admin/*` churn is reverted there.
- Do not add migrations. Both workstreams are view/template/service only.

## Root Cause Analysis

### Reported symptom
User selects **Kategori Indikator = IMRS** on the dashboard; the quality-indicator panel still shows INM data. URL in the screenshot: `?mutu_jenis=INM&mutu_indikator=287&mutu_tahun=2026`.

### What the report claims
That `onChange` does not reset the `mutu_indikator` param and that the Django view does not filter the indicator queryset by `mutu_jenis`.

### What the code actually does (verified by probe)
The backend **already** filters correctly, and the dropdown **already** drops the stale id. `akreditasi/views.py:153-167`:

```python
if mutu_jenis:
    _JENIS_MAP = {'INM': ['INM', 'NASIONAL'], 'IMRS': ['IMRS', 'IMP_RS'], 'IMU': ['IMU', 'IMP_UNIT']}
    ind_qs = ind_qs.filter(jenis__in=_JENIS_MAP.get(mutu_jenis, [mutu_jenis]))
...
mutu_indikator_choices = list(_choices_qs.order_by('jenis', 'kode_indikator'))
selected_indikator = next((i for i in mutu_indikator_choices if i.pk == mutu_indikator_id), None)
```

Live probe with a seeded INM indicator (pk=1) and IMRS indicators (pk=3,4):

```
--- /?mutu_jenis=INM&mutu_tahun=2026&mutu_indikator=1
   mutu_jenis    : ('INM', 'Indikator Nasional Mutu (INM)')
   mutu_indikator: ('1', '[INM-01] Kepatuhan Hand Hygiene Nasional')
   MUTU_IND_ID   : 1
--- /?mutu_jenis=IMRS&mutu_tahun=2026&mutu_indikator=1   <-- the reported bug
   mutu_jenis    : ('IMRS', 'Indikator Mutu Rumah Sakit (IMRS)')
   mutu_indikator: ('(none selected)', '4 options')
   MUTU_IND_ID   : 1
```

So: the `<select>` correctly shows no selection and the chart correctly falls back to aggregate — **but `MUTU_IND_ID` is still `1`**.

### The real defect
`_get_mutu_renstra_charts_context` returns the raw request value, not the resolved one:

```python
'filter_mutu_indikator': mutu_indikator_id,   # akreditasi/views.py:301 — raw, unvalidated
```

That value is consumed by the template as `const MUTU_IND_ID = "{{ filter_mutu_indikator|default:'' }}"` (`templates/akreditasi/dashboard.html:941`), which drives:
1. the month drill-down modal's indicator label (`[ ]` with an empty name, because `mutu_indikator_terpilih` is `None`), and
2. the drill-down's **"Buat PDCA"** link: `PDCA_URL_BASE + '?indikator=' + MUTU_IND_ID + ...` — which navigates to the **INM** indicator while the page header says IMRS.

That is the visible "pilih IMRS masih muncul INM": not the chart, the drill-down. A stale id therefore leaks across categories through a value the server had already determined to be invalid.

### Secondary defect
The category `<select>` submits the whole GET form. Nothing clears the indicator selection when the category, unit, or year changes, so a *still-valid-in-the-new-set* selection silently carries over and a stale one survives in the URL. The reset must be explicit.

## Scope Boundaries

**In scope:** the dashboard indicator-filter consistency fix; an AI generator for G.4 (Ringkasan Investigasi Lanjutan RCA) and G.5 (Rencana Tindak Lanjut) in `risiko_evaluasi.html`; a one-click bridge from the MONEV table.

**Explicitly NOT in this plan** (do not implement, do not "fix while here"):
- The hardcoded `100%` in the "Status Pelaksanaan (Do)" KPI card of `risiko_monitoring_evaluasi.html` — real bug, separate plan.
- The `deadline_rtl`/`status_rtl` write path in `risiko_edit` (`risiko_views.py:590-651`) — it does not persist `deadline_rtl`/`status_rtl`/`bukti_rtl`. Separate plan.
- Any change to `indikator_dashboard.html` (the `/indikator-mutu/` page). It uses `?jenis=`/`?indikator=` and a different view; the reported bug is on `/` (dashboard).
- Regenerating `staticfiles/` outside Task 8.

## Review Focus

The failure modes most likely to bite a real user of this change, each pinned by a test in the owning task:

1. **A stale indicator id from another category survives into client-side actions.** → Task 2, `test_stale_indicator_id_is_cleared_from_client_context`.
2. **A legitimate selection is thrown away by an over-aggressive reset.** → Task 2, `test_valid_indicator_in_same_category_stays_selected`.
3. **AI disabled / no API key turns the button into a dead click or a 500.** → Task 5, `test_ai_disabled_returns_fallback_not_error`.
4. **The model returns prose instead of the contract keys, leaving fields empty.** → Task 4, `test_service_fills_missing_contract_keys`.
5. **The generated RTL overwrites text the user already typed.** → Task 6, `test_ai_does_not_clobber_filled_fields` (JS-level guard: only fill a field when it is empty, except the field the button owns).

## File Structure

```
akreditasi/
  views.py                          MODIFY  lines 153-167 + 297-306  (resolved indicator id)
  ai_prompts.py                     MODIFY  append 2 prompt constants
  ai_service.py                     MODIFY  append 1 generator + 2 fallback builders
  ai_views.py                       MODIFY  append 1 endpoint
  urls.py                           MODIFY  append 1 route after ai/evaluasi-risiko/
  tests_indikator_mutu_charts.py    MODIFY  append 1 test class
  tests_ai.py                       MODIFY  append 1 test class
templates/akreditasi/
  dashboard.html                    MODIFY  select onchange hooks + global reset fn
  risiko_evaluasi.html              MODIFY  G.4 + G.5 button groups, AI JS
  risiko_monitoring_evaluasi.html   MODIFY  action column: AI button
```

---

### Task 1: Record the baseline

**Files:** none (measurement only)

**Interfaces:**
- Produces: the measured pass/fail counts every later task compares against. Nothing else consumes this task.

- [ ] **Step 1: Run the full suite and record the exact numbers**

```bash
cd C:/Users/cubeb/orca/workspaces/sim-akreditasi-django/larvacean
P="C:/Users/cubeb/orca/workspaces/sim-akreditasi-django/medaka/.venv/Scripts/python.exe"
$P manage.py test --no-input 2>&1 | tail -5
```

Expected on the untouched tree: `Ran 234 tests` … `OK`. Write the actual numbers into your task report. If the tree is not green before you start, stop and report — do not build on a red baseline.

- [ ] **Step 2: Confirm the defect is present**

```bash
$P manage.py shell -c "
from django.test import Client
from django.contrib.auth.models import User
from akreditasi.risiko_models import IndikatorMutu
u,_=User.objects.get_or_create(username='probe', defaults={'is_staff':True,'is_superuser':True})
u.is_staff=u.is_superuser=True; u.set_password('probe12345'); u.save()
c=Client(); c.force_login(u)
inm=IndikatorMutu.objects.filter(jenis__in=['INM','NASIONAL']).first()
h=c.get(f'/?mutu_jenis=IMRS&mutu_tahun=2026&mutu_indikator={inm.pk}').content.decode()
import re; print('MUTU_IND_ID =', re.search(r'MUTU_IND_ID\s*=\s*\"([^\"]*)\"', h).group(1))
"
```

Expected: prints the INM pk (a non-empty number) while the page is filtered to IMRS. That non-empty value is the bug.

- [ ] **Step 3: Commit nothing**

This task produces no diff. Report the two numbers (baseline test count, leaking id) and continue.

---

### Task 2: Fix the dashboard indicator filter

**Files:**
- Modify: `akreditasi/views.py:153-167` and `:297-306`
- Modify: `templates/akreditasi/dashboard.html:467` and `:941`
- Test: `akreditasi/tests_indikator_mutu_charts.py` (append a new class)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `_get_mutu_renstra_charts_context` now returns `filter_mutu_indikator` as `int` — either the pk of the resolved `selected_indikator` or `0`. The template contract `MUTU_IND_ID` is a string: `""` when nothing is selected, else the decimal pk. `window.arimaMutuFilterChange(el)` is a global JS function taking the changed `<select>`.

- [ ] **Step 1: Write the failing tests**

Append to `akreditasi/tests_indikator_mutu_charts.py`:

```python
class DashboardCategoryIndicatorConsistencyTest(TestCase):
    """A category change must not leave the dashboard acting on a foreign indicator."""

    def setUp(self):
        self.user = User.objects.create_superuser('admin_filter', 'admin_filter@rs.id', 'secret123')
        self.client = Client()
        self.client.force_login(self.user)
        self.unit = UnitKerja.objects.create(name='IGD Filter', code='IGD-F', tipe_unit='RUANGAN')

        self.inm = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Hand Hygiene', kode_indikator='INM-F1',
            unit=self.unit, jenis='NASIONAL', dimensi_mutu='AMAN',
            numerator='Patuh', denominator='Total peluang',
            target_nilai=Decimal('85.00'), satuan='%', aktif=True,
        )
        self.imrs = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Identifikasi Pasien', kode_indikator='IMRS-F1',
            unit=self.unit, jenis='IMRS', dimensi_mutu='AMAN',
            numerator='Patuh', denominator='Total kunjungan',
            target_nilai=Decimal('100.00'), satuan='%', aktif=True,
        )
        for ind in (self.inm, self.imrs):
            CatatanIndikator.objects.create(
                indikator=ind, bulan=1, tahun=2026,
                nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'),
            )

    def _indikator_select(self, html):
        m = re.search(r'<select name="mutu_indikator".*?</select>', html, re.S)
        self.assertIsNotNone(m, 'select mutu_indikator tidak dirender')
        return m.group(0)

    def _mutu_ind_id(self, html):
        m = re.search(r'MUTU_IND_ID\s*=\s*"([^"]*)"', html)
        self.assertIsNotNone(m, 'const MUTU_IND_ID tidak dirender')
        return m.group(1)

    def test_stale_indicator_id_is_cleared_from_client_context(self):
        """An INM id carried into an IMRS view must not reach the drill-down/PDCA link."""
        url = (reverse('akreditasi:dashboard')
               + f'?mutu_jenis=IMRS&mutu_tahun=2026&mutu_indikator={self.inm.pk}')
        html = self.client.get(url).content.decode()
        self.assertEqual(self._mutu_ind_id(html), '',
                         'MUTU_IND_ID masih memuat indikator dari kategori lain')
        self.assertNotIn(f'value="{self.inm.pk}"', self._indikator_select(html),
                         'indikator INM masih ditawarkan di bawah filter IMRS')

    def test_valid_indicator_in_same_category_stays_selected(self):
        """The fix must not throw away a legitimate selection."""
        url = (reverse('akreditasi:dashboard')
               + f'?mutu_jenis=IMRS&mutu_tahun=2026&mutu_indikator={self.imrs.pk}')
        html = self.client.get(url).content.decode()
        self.assertEqual(self._mutu_ind_id(html), str(self.imrs.pk))
        self.assertRegex(self._indikator_select(html),
                         rf'<option value="{self.imrs.pk}"[^>]*\bselected\b')

    def test_category_select_clears_indicator_before_submit(self):
        """The category/unit/year selects must reset the indicator selection explicitly."""
        html = self.client.get(reverse('akreditasi:dashboard')).content.decode()
        self.assertRegex(html, r'name="mutu_jenis"[^>]*onchange="arimaMutuFilterChange\(this\)"')
        self.assertRegex(html, r'name="mutu_tahun"[^>]*onchange="arimaMutuFilterChange\(this\)"')
        self.assertIn('window.arimaMutuFilterChange', html)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
$P manage.py test akreditasi.tests_indikator_mutu_charts.DashboardCategoryIndicatorConsistencyTest --no-input
```

Expected: 3 failures. `test_stale_indicator_id_is_cleared_from_client_context` fails with `'' != '<pk>'`; `test_category_select_clears_indicator_before_submit` fails on the missing `arimaMutuFilterChange`. `test_valid_indicator_in_same_category_stays_selected` may already pass — that is fine, it is the regression guard.

- [ ] **Step 3: Fix the view**

In `akreditasi/views.py`, replace the resolution block (currently lines 166-167):

```python
    mutu_indikator_choices = list(_choices_qs.order_by('jenis', 'kode_indikator'))
    selected_indikator = next((i for i in mutu_indikator_choices if i.pk == mutu_indikator_id), None)
```

with:

```python
    mutu_indikator_choices = list(_choices_qs.order_by('jenis', 'kode_indikator'))
    selected_indikator = next((i for i in mutu_indikator_choices if i.pk == mutu_indikator_id), None)
    # A stale id carried over from another category/unit/year must not survive into the
    # client context: MUTU_IND_ID drives the drill-down modal and its "Buat PDCA" link,
    # so an unresolved id would make the page act on an indicator the filter excludes.
    filter_mutu_indikator = selected_indikator.pk if selected_indikator else 0
```

Then in the same function's return dict, change:

```python
        'filter_mutu_indikator': mutu_indikator_id,
```

to:

```python
        'filter_mutu_indikator': filter_mutu_indikator,
```

`chart_qs` and everything downstream already key off `selected_indikator`, so nothing else changes.

- [ ] **Step 4: Add the filter-reset hook to the template**

In `templates/akreditasi/dashboard.html`, change the three dependent selects (lines 467, 477, 500) from `onchange="this.form.submit()"` to `onchange="arimaMutuFilterChange(this)"`. Leave the `mutu_indikator` select (line 489) as `this.form.submit()` — choosing an indicator must keep the category.

Line 467:
```html
                    <select name="mutu_jenis" class="form-select form-select-sm" onchange="arimaMutuFilterChange(this)">
```
Line 477:
```html
                    <select name="mutu_unit" class="form-select form-select-sm" onchange="arimaMutuFilterChange(this)">
```
Line 500:
```html
                    <select name="mutu_tahun" class="form-select form-select-sm" onchange="arimaMutuFilterChange(this)">
```

Then, in `{% block extra_js %}` immediately after `<script>` (before the `document.addEventListener('DOMContentLoaded', ...)` line at 939), insert:

```javascript
    // Changing category/unit/year invalidates the indicator selection: clear it before
    // the GET submit so the URL never carries an id from the previous filter set.
    window.arimaMutuFilterChange = function (el) {
        const form = el.form;
        const ind = form ? form.querySelector('[name="mutu_indikator"]') : null;
        if (ind) { ind.value = ''; }
        if (form) { form.submit(); }
    };
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
$P manage.py test akreditasi.tests_indikator_mutu_charts --no-input
```

Expected: all tests in the module pass, `0 failed`.

- [ ] **Step 6: Re-run the manual probe from Task 1 Step 2**

Expected: `MUTU_IND_ID = ` (empty). The reported symptom is gone.

- [ ] **Step 7: Commit**

```bash
git add akreditasi/views.py templates/akreditasi/dashboard.html akreditasi/tests_indikator_mutu_charts.py
git commit -m "fix(dashboard): clear stale quality-indicator id when category filter changes"
```

---

### Task 3: Add the investigation + RTL prompts

**Files:**
- Modify: `akreditasi/ai_prompts.py` (append at end, after `PROMPT_RCA_SUGGESTION`)

**Interfaces:**
- Consumes: nothing.
- Produces: `PROMPT_INVESTIGASI_RTL`, a `str.format` template with exactly these named placeholders, all of which Task 4 must supply: `unit_name`, `jenis_risiko`, `masalah`, `data_pendukung`, `dampak`, `probabilitas`, `skor`, `level`, `evaluasi_capaian`, `capaian_nilai`, `target_capaian`, `fishbone_terisi`, `metode_evaluasi`. Every literal `{` and `}` inside the JSON example must be doubled (`{{` / `}}`).

- [ ] **Step 1: Append the prompt constant**

Add to the end of `akreditasi/ai_prompts.py`:

```python

# ── Section G: RINGKASAN INVESTIGASI LANJUTAN (G.4) & RENCANA TINDAK LANJUT (G.5) ──
PROMPT_INVESTIGASI_RTL = """Konteks Evaluasi Risiko Rumah Sakit (STARKES PMKP 7 & 12):
- Unit Kerja: {unit_name}
- Jenis Risiko: {jenis_risiko}
- Pernyataan Masalah: {masalah}
- Data Pendukung / Bukti: {data_pendukung}
- Skor Risiko Awal: {skor} (Dampak {dampak} x Probabilitas {probabilitas}) — Tingkat: {level}
- Metode Evaluasi Mendalam: {metode_evaluasi}
- Uraian Evaluasi Capaian yang Sudah Diisi: {evaluasi_capaian}
- Capaian Indikator Realisasi: {capaian_nilai}
- Target Indikator: {target_capaian}
- Analisis Fishbone yang Sudah Diisi User: {fishbone_terisi}

Tugas: Susun DUA bagian berikut sekaligus, saling konsisten.

BAGIAN 1 — RINGKASAN INVESTIGASI LANJUTAN (untuk kolom G.4):
Tulis narasi investigasi akar masalah yang siap ditempel ke dokumen akreditasi, memakai
5-Whys dan kerangka Fishbone (Manpower, Process/Method, Material, Machine, Environment,
System). Pisahkan penyebab langsung dari akar masalah sistemik. Jangan mengulang kalimat
template; gunakan bahasa faktual khas rumah sakit.

BAGIAN 2 — RENCANA TINDAK LANJUT / RTL (untuk kolom G.5):
Susun RTL yang SMART (Specific, Measurable, Achievable, Relevant, Time-bound), berupa
langkah bernomor yang benar-benar menyelesaikan akar masalah sistemik di Bagian 1 — bukan
sekadar quick fix. Sertakan saran PIC dan tenggat dalam hari.

Format Output JSON (tanpa markdown code block):
{{
  "analisis_investigasi": "1. Kronologi & Dampak: ...\\n2. Analisis 5-Whys: 1) Mengapa ... 2) Mengapa ... 3) Mengapa ... 4) Mengapa ... 5) Akar masalah: ...\\n3. Akar Masalah Sistemik: ...\\n4. Penyebab Langsung: ...\\n5. Kesimpulan Investigasi: ...",
  "fishbone": {{
    "manpower": "Kontributor dari sisi SDM / kompetensi / beban kerja",
    "process": "Kontributor dari sisi metode / SPO / alur kerja",
    "material": "Kontributor dari sisi bahan / sarana / dokumen",
    "machine": "Kontributor dari sisi alat / fasilitas / SIMRS",
    "environment": "Kontributor dari sisi lingkungan kerja / budaya keselamatan",
    "system": "Kontributor dari sisi kebijakan / tata kelola / sistem RS"
  }},
  "akar_masalah_sistemik": "Satu paragraf akar masalah tingkat sistem",
  "verifikasi_efektivitas": "Cara membuktikan perbaikan berhasil (indikator, frekuensi, ambang)",
  "rencana_tindak_lanjut": "1. [Langkah perbaikan konkret]\\n2. [Revisi SPO / sarana]\\n3. [Pelatihan & sosialisasi]\\n4. [Audit kepatuhan berkala]\\n5. [Pelaporan hasil ke Komite Mutu]",
  "pj_saran": "Jabatan PIC yang paling tepat (mis. Kepala Instalasi / Ka. Unit / Komite Mutu)",
  "target_hari": 30,
  "indikator_keberhasilan": "Indikator terukur yang menandakan RTL berhasil",
  "status_rtl_saran": "BELUM / PROSES / SELESAI"
}}"""
```

- [ ] **Step 2: Verify the template formats without KeyError**

```bash
$P manage.py shell -c "
from akreditasi.ai_prompts import PROMPT_INVESTIGASI_RTL
keys = ['unit_name','jenis_risiko','masalah','data_pendukung','dampak','probabilitas','skor','level','evaluasi_capaian','capaian_nilai','target_capaian','fishbone_terisi','metode_evaluasi']
print(PROMPT_INVESTIGASI_RTL.format(**{k: 'X' for k in keys})[:120])
print('FORMAT OK')
"
```

Expected: prints the prompt head then `FORMAT OK`. A `KeyError` means a placeholder name is misspelled; a `ValueError: unexpected '{'` means an unescaped brace in the JSON example.

- [ ] **Step 3: Commit**

```bash
git add akreditasi/ai_prompts.py
git commit -m "feat(ai): add investigation-summary and RTL prompt template"
```

---

### Task 4: Add the AI service function with a rule-based fallback

**Files:**
- Modify: `akreditasi/ai_service.py` (import the new prompt; append two fallback builders and one generator, after `generate_rca_suggestion`)

**Interfaces:**
- Consumes: `PROMPT_INVESTIGASI_RTL` from Task 3; existing `_call_deepseek`, `_log_ai_call`, `sanitize_hospital_prompt`.
- Produces: `generate_investigasi_rtl(user, *, unit_name, jenis_risiko, masalah, data_pendukung, dampak, probabilitas, evaluasi_capaian='', capaian_nilai='', target_capaian='', fishbone=None, metode_evaluasi='RCA') -> dict` returning `{'success': bool, 'data': dict, 'fallback': bool, 'error': str|None}` where `data` always carries all nine contract keys: `analisis_investigasi`, `fishbone` (dict with six keys), `akar_masalah_sistemik`, `verifikasi_efektivitas`, `rencana_tindak_lanjut`, `pj_saran`, `target_hari` (int), `indikator_keberhasilan`, `status_rtl_saran`.

- [ ] **Step 1: Write the failing test**

Append to `akreditasi/tests_ai.py`:

```python
class InvestigasiRTLServiceTest(TestCase):
    """The investigation/RTL generator must always return the full contract."""

    CONTRACT = (
        'analisis_investigasi', 'fishbone', 'akar_masalah_sistemik',
        'verifikasi_efektivitas', 'rencana_tindak_lanjut', 'pj_saran',
        'target_hari', 'indikator_keberhasilan', 'status_rtl_saran',
    )
    FISHBONE_KEYS = ('manpower', 'process', 'material', 'machine', 'environment', 'system')

    def setUp(self):
        self.user = User.objects.create_superuser('admin_inv', 'admin_inv@rs.id', 'password123')
        self.config = SystemConfig.get_solo()
        self.config.ai_enabled = True
        self.config.ai_enable_risiko = True
        self.config.ai_api_key = "sk-test-fake-key-for-testing"
        self.config.save()

    def _call(self, **over):
        from akreditasi.ai_service import generate_investigasi_rtl
        kw = dict(
            unit_name='IGD', jenis_risiko='Keterlambatan penanganan pasien kritis',
            masalah='Waktu tunggu triase melebihi 5 menit pada jam sibuk',
            data_pendukung='Rata-rata 8 menit pada shift sore', dampak=4, probabilitas=3,
            evaluasi_capaian='Target tidak tercapai pada 3 bulan terakhir',
            capaian_nilai='62%', target_capaian='90%',
        )
        kw.update(over)
        return generate_investigasi_rtl(self.user, **kw)

    @patch('akreditasi.ai_service.requests.post')
    def test_service_returns_full_contract(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'choices': [{'message': {'content': json.dumps({
            'analisis_investigasi': '1. Kronologi ...',
            'fishbone': {k: f'penyebab {k}' for k in self.FISHBONE_KEYS},
            'akar_masalah_sistemik': 'Belum ada SPO triase berbasis beban kerja',
            'verifikasi_efektivitas': 'Audit waktu tunggu mingguan',
            'rencana_tindak_lanjut': '1. Revisi SPO triase',
            'pj_saran': 'Kepala Instalasi Gawat Darurat',
            'target_hari': 21,
            'indikator_keberhasilan': 'Waktu tunggu triase <= 5 menit',
            'status_rtl_saran': 'PROSES',
        })}}]}
        mock_post.return_value = mock_response

        res = self._call()
        self.assertTrue(res['success'])
        for key in self.CONTRACT:
            self.assertIn(key, res['data'], f'kontrak "{key}" hilang dari respons')
        for key in self.FISHBONE_KEYS:
            self.assertIn(key, res['data']['fishbone'])
        self.assertNotIn('test-fake-key', json.dumps(res))

    @patch('akreditasi.ai_service.requests.post')
    def test_service_fills_missing_contract_keys(self, mock_post):
        """A model that returns only prose must still yield a usable form payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'choices': [{'message': {'content': json.dumps({
            'analisis_investigasi': 'Hanya narasi investigasi tanpa field lain.',
        })}}]}
        mock_post.return_value = mock_response

        res = self._call()
        self.assertTrue(res['success'])
        data = res['data']
        for key in self.CONTRACT:
            self.assertIn(key, data, f'kontrak "{key}" tidak diisi saat model tidak lengkap')
        self.assertTrue(str(data['rencana_tindak_lanjut']).strip())
        self.assertIsInstance(data['target_hari'], int)

    def test_ai_disabled_returns_fallback_not_error(self):
        self.config.ai_enabled = False
        self.config.save()
        res = self._call()
        self.assertTrue(res['success'], 'AI nonaktif tidak boleh menghasilkan error')
        self.assertTrue(res.get('fallback'))
        for key in self.CONTRACT:
            self.assertIn(key, res['data'])
        self.assertIn('IGD', res['data']['analisis_investigasi'])

    def test_timeout_returns_fallback_not_error(self):
        import requests
        with patch('akreditasi.ai_service.requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout('timeout')
            res = self._call()
        self.assertTrue(res['success'])
        self.assertTrue(res.get('fallback'))
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
$P manage.py test akreditasi.tests_ai.InvestigasiRTLServiceTest --no-input
```

Expected: 4 errors, all `ImportError: cannot import name 'generate_investigasi_rtl'`.

- [ ] **Step 3: Implement the fallbacks and the generator**

Add `PROMPT_INVESTIGASI_RTL` to the existing `from .ai_prompts import (...)` block in `akreditasi/ai_service.py`.

Then append at the end of the file:

```python
# ── SECTION G: RINGKASAN INVESTIGASI LANJUTAN & RENCANA TINDAK LANJUT (RTL) ──

_INVESTIGASI_CONTRACT = (
    'analisis_investigasi', 'fishbone', 'akar_masalah_sistemik', 'verifikasi_efektivitas',
    'rencana_tindak_lanjut', 'pj_saran', 'target_hari', 'indikator_keberhasilan',
    'status_rtl_saran',
)
_FISHBONE_KEYS = ('manpower', 'process', 'material', 'machine', 'environment', 'system')


def _fallback_fishbone(unit: str) -> dict:
    return {
        'manpower': f'Beban kerja dan variasi kompetensi staf {unit} belum terpetakan per shift.',
        'process': 'Alur kerja dan SPO belum mengatur titik verifikasi ulang saat kondisi sibuk.',
        'material': 'Ketersediaan bahan, formulir, dan dokumen pendukung belum dijamin per shift.',
        'machine': 'Sarana, alat, dan dukungan SIMRS belum sepenuhnya mendukung pencatatan real-time.',
        'environment': f'Lingkungan kerja {unit} dan budaya keselamatan belum konsisten antar shift.',
        'system': 'Kebijakan, monitoring berjenjang, dan umpan balik hasil audit belum berjalan rutin.',
    }


def _generate_fallback_investigasi_rtl(unit_name: str, jenis_risiko: str, masalah: str,
                                       dampak: int, probabilitas: int,
                                       capaian_nilai: str = '', target_capaian: str = '',
                                       fishbone: dict = None) -> dict:
    """Payload deterministik saat AI eksternal tidak tersedia — form tidak boleh kosong."""
    unit = (unit_name or 'unit kerja').strip()
    issue = (masalah or jenis_risiko or 'masalah mutu').strip().rstrip('.')
    skor = (dampak or 3) * (probabilitas or 3)
    fb = _fallback_fishbone(unit)
    if isinstance(fishbone, dict):
        for k in _FISHBONE_KEYS:
            v = fishbone.get(k)
            if v and str(v).strip():
                fb[k] = str(v).strip()

    analisis = (
        f"1. Kronologi & Dampak: {issue} teridentifikasi di {unit} dengan skor risiko {skor} "
        f"(D{dampak or 3} x P{probabilitas or 3}), berdampak langsung pada mutu dan keselamatan pasien.\n"
        f"2. Analisis 5-Whys: 1) Mengapa terjadi? Karena {issue.lower()}. "
        f"2) Mengapa hal itu terjadi? Karena alur kerja belum mengunci titik verifikasi. "
        f"3) Mengapa alur belum mengunci? Karena SPO belum direvisi mengikuti beban kerja nyata. "
        f"4) Mengapa SPO belum direvisi? Karena hasil audit belum menjadi agenda rutin. "
        f"5) Akar masalah: lemahnya siklus umpan balik audit ke perbaikan kebijakan di {unit}.\n"
        f"3. Akar Masalah Sistemik: tata kelola monitoring berjenjang dan peninjauan SPO di {unit} "
        f"belum berjalan periodik, sehingga deviasi berulang tidak terkoreksi di tingkat sistem.\n"
        f"4. Penyebab Langsung: {issue.lower()} pada kondisi beban kerja tinggi.\n"
        f"5. Kesimpulan Investigasi: diperlukan perbaikan sistemik pada SPO, kompetensi, dan "
        f"mekanisme audit internal {unit}, bukan sekadar koreksi individual."
    )

    rtl = (
        f"1. Revisi SPO dan alur kerja {unit} untuk menutup titik kegagalan yang ditemukan.\n"
        f"2. Penyesuaian sarana/prasarana dan dukungan SIMRS agar pencatatan berjalan real-time.\n"
        f"3. Pelatihan ulang dan sertifikasi kompetensi staf {unit} sesuai kebutuhan per shift.\n"
        f"4. Audit kepatuhan berkala (mingguan) dengan umpan balik langsung ke kepala unit.\n"
        f"5. Pelaporan hasil perbaikan ke Komite Mutu dan penetapan target capaian berikutnya."
    )

    return {
        'analisis_investigasi': analisis,
        'fishbone': fb,
        'akar_masalah_sistemik': (
            f'Lemahnya siklus umpan balik audit ke perbaikan kebijakan di {unit} '
            f'sehingga deviasi pada {jenis_risiko or issue} berulang.'
        ),
        'verifikasi_efektivitas': (
            f'Pantau capaian indikator terkait secara bulanan terhadap target '
            f'{target_capaian or "yang ditetapkan"}; dinyatakan efektif bila capaian '
            f'kembali ke ambang target selama 3 bulan berturut-turut.'
        ),
        'rencana_tindak_lanjut': rtl,
        'pj_saran': f'Kepala {unit} bersama Komite Mutu',
        'target_hari': 30,
        'indikator_keberhasilan': (
            f'Capaian indikator membaik dari {capaian_nilai or "kondisi awal"} menuju '
            f'target {target_capaian or "yang ditetapkan"} tanpa deviasi berulang.'
        ),
        'status_rtl_saran': 'PROSES',
    }


def generate_investigasi_rtl(user, unit_name: str, jenis_risiko: str, masalah: str,
                             data_pendukung: str, dampak: int, probabilitas: int,
                             evaluasi_capaian: str = '', capaian_nilai: str = '',
                             target_capaian: str = '', fishbone: dict = None,
                             metode_evaluasi: str = 'RCA') -> dict:
    """Hasilkan Ringkasan Investigasi Lanjutan (G.4) + Rencana Tindak Lanjut (G.5)."""
    from .system_models import SystemConfig
    config = SystemConfig.get_solo()

    dampak = int(dampak or 3)
    probabilitas = int(probabilitas or 3)
    skor = dampak * probabilitas
    level_map = {range(1, 6): 'RENDAH', range(6, 11): 'SEDANG',
                 range(11, 16): 'TINGGI', range(16, 26): 'SANGAT TINGGI'}
    level = next((v for k, v in level_map.items() if skor in k), 'SEDANG')

    fallback_data = _generate_fallback_investigasi_rtl(
        unit_name=unit_name, jenis_risiko=jenis_risiko, masalah=masalah,
        dampak=dampak, probabilitas=probabilitas,
        capaian_nilai=capaian_nilai, target_capaian=target_capaian, fishbone=fishbone,
    )

    if not config.ai_enabled or not config.ai_enable_risiko or not config.get_deepseek_api_key():
        _log_ai_call(user, 'INVESTIGASI_RTL', f'{unit_name} | {(jenis_risiko or masalah)[:60]}', True)
        return {'success': True, 'data': fallback_data, 'fallback': True, 'error': None}

    fishbone_txt = '(belum diisi)'
    if isinstance(fishbone, dict) and fishbone:
        fishbone_txt = '; '.join(
            f'{k}: {v}' for k, v in fishbone.items() if v and str(v).strip()
        ) or '(belum diisi)'

    prompt = PROMPT_INVESTIGASI_RTL.format(
        unit_name=sanitize_hospital_prompt(unit_name or 'Unit Kerja'),
        jenis_risiko=sanitize_hospital_prompt(jenis_risiko or '(belum diisi)'),
        masalah=sanitize_hospital_prompt(masalah or '(belum diisi)'),
        data_pendukung=sanitize_hospital_prompt(data_pendukung or '(belum diisi)'),
        dampak=dampak, probabilitas=probabilitas, skor=skor, level=level,
        evaluasi_capaian=sanitize_hospital_prompt(evaluasi_capaian or '(belum diisi)'),
        capaian_nilai=capaian_nilai or '(belum diisi)',
        target_capaian=target_capaian or '(belum diisi)',
        fishbone_terisi=sanitize_hospital_prompt(fishbone_txt),
        metode_evaluasi=metode_evaluasi or 'RCA',
    )

    result = _call_deepseek(prompt, max_tokens=2500)
    if not result.get('success') or not isinstance(result.get('data'), dict):
        _log_ai_call(user, 'INVESTIGASI_RTL', f'{unit_name} | {(jenis_risiko or masalah)[:60]}', False)
        return {'success': True, 'data': fallback_data, 'fallback': True, 'error': None}

    data = result['data']
    # A partial model answer must not leave a form field empty: fill each missing
    # contract key from the deterministic fallback instead of dropping it.
    for key in _INVESTIGASI_CONTRACT:
        if key == 'fishbone':
            fb = data.get('fishbone') if isinstance(data.get('fishbone'), dict) else {}
            merged = dict(fallback_data['fishbone'])
            for k in _FISHBONE_KEYS:
                v = fb.get(k)
                if v and str(v).strip():
                    merged[k] = str(v).strip()
            data['fishbone'] = merged
        elif not data.get(key):
            data[key] = fallback_data[key]
    try:
        data['target_hari'] = int(str(data['target_hari']).strip()[:3] or 30)
    except (ValueError, TypeError):
        data['target_hari'] = 30

    _log_ai_call(user, 'INVESTIGASI_RTL', f'{unit_name} | {(jenis_risiko or masalah)[:60]}', True)
    return {'success': True, 'data': data, 'fallback': False, 'error': None}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
$P manage.py test akreditasi.tests_ai.InvestigasiRTLServiceTest --no-input
```

Expected: `Ran 4 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add akreditasi/ai_service.py akreditasi/tests_ai.py
git commit -m "feat(ai): add investigation-summary and RTL generator with rule-based fallback"
```

---

### Task 5: Expose the endpoint

**Files:**
- Modify: `akreditasi/ai_views.py` (import + append endpoint after `api_ai_rca_saran`)
- Modify: `akreditasi/urls.py` (append route after the `ai/evaluasi-risiko/` line)
- Test: `akreditasi/tests_ai.py` (append a new class)

**Interfaces:**
- Consumes: `generate_investigasi_rtl` from Task 4.
- Produces: URL name `akreditasi:ai_investigasi_rtl` at path `ai/investigasi-rtl/`. Accepts JSON body `{mode, unit_name, jenis_risiko, masalah, data_pendukung, dampak, probabilitas, evaluasi_capaian, capaian_nilai, target_capaian, fishbone, metode_evaluasi}` where `mode ∈ {'investigasi','rtl','both'}`. Returns `{'success': True, 'data': {...nine keys...}, 'fallback': bool}` or `{'success': False, 'error': str}` with 400.

- [ ] **Step 1: Write the failing tests**

Append to `akreditasi/tests_ai.py`:

```python
class EndpointInvestigasiRTLTest(TestCase):
    """HTTP contract of the investigation/RTL endpoint."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('admin_inv_http', 'admin_inv_http@rs.id', 'password123')
        self.config = SystemConfig.get_solo()
        self.config.ai_enabled = True
        self.config.ai_enable_risiko = True
        self.config.ai_api_key = "sk-test-fake-key-for-testing"
        self.config.save()
        self.url = reverse('akreditasi:ai_investigasi_rtl')

    def _payload(self, **over):
        p = {
            'mode': 'both', 'unit_name': 'IGD',
            'jenis_risiko': 'Keterlambatan penanganan pasien kritis',
            'masalah': 'Waktu tunggu triase melebihi 5 menit',
            'data_pendukung': 'Rata-rata 8 menit shift sore',
            'dampak': 4, 'probabilitas': 3,
            'evaluasi_capaian': 'Target tidak tercapai 3 bulan',
            'capaian_nilai': '62%', 'target_capaian': '90%',
            'fishbone': {'manpower': 'Beban kerja shift sore tinggi'},
            'metode_evaluasi': 'RCA',
        }
        p.update(over)
        return p

    def test_anon_gets_401_json(self):
        resp = self.client.post(self.url, data=json.dumps(self._payload()),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.json()['success'])

    def test_both_mode_returns_full_contract(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, data=json.dumps(self._payload()),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['success'])
        for key in ('analisis_investigasi', 'rencana_tindak_lanjut', 'fishbone',
                    'pj_saran', 'target_hari', 'indikator_keberhasilan'):
            self.assertIn(key, body['data'])
        self.assertNotIn('test-fake-key', resp.content.decode())

    def test_invalid_mode_returns_400(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, data=json.dumps(self._payload(mode='hapus-semua')),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])

    def test_missing_context_returns_400(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            self.url,
            data=json.dumps({'mode': 'both', 'unit_name': 'IGD'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])

    def test_non_json_body_returns_400(self):
        self.client.force_login(self.admin)
        resp = self.client.post(self.url, data='bukan json',
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
$P manage.py test akreditasi.tests_ai.EndpointInvestigasiRTLTest --no-input
```

Expected: `NoReverseMatch: Reverse for 'ai_investigasi_rtl' not found` in setUp (5 errors).

- [ ] **Step 3: Add the endpoint**

In `akreditasi/ai_views.py`, add `generate_investigasi_rtl` to the existing `from .ai_service import (...)` block, then append after `api_ai_rca_saran`:

```python
# ── 7. RINGKASAN INVESTIGASI LANJUTAN (G.4) & RENCANA TINDAK LANJUT (G.5) ──

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_investigasi_rtl(request):
    """Endpoint tombol '✨ AI' pada G.4 (investigasi) dan G.5 (RTL) halaman evaluasi risiko."""
    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_permission('can_view_risiko'):
        return JsonResponse({'success': False, 'error': 'Anda tidak memiliki hak akses melihat data risiko.'}, status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload request tidak valid (bukan JSON).'}, status=400)

    mode = (data.get('mode') or 'both').strip().lower()
    if mode not in ('investigasi', 'rtl', 'both'):
        return JsonResponse({'success': False, 'error': 'Mode harus investigasi, rtl, atau both.'}, status=400)

    jenis_risiko = (data.get('jenis_risiko') or '').strip()
    masalah = (data.get('masalah') or '').strip()
    if not jenis_risiko and not masalah:
        return JsonResponse({
            'success': False,
            'error': 'Harap isi Jenis Risiko atau Pernyataan Masalah sebelum meminta analisis AI.',
        }, status=400)

    fishbone = data.get('fishbone')
    if not isinstance(fishbone, dict):
        fishbone = None

    res = generate_investigasi_rtl(
        user=request.user,
        unit_name=(data.get('unit_name') or 'Unit Kerja').strip(),
        jenis_risiko=jenis_risiko,
        masalah=masalah,
        data_pendukung=(data.get('data_pendukung') or '').strip(),
        dampak=int(data.get('dampak') or 3),
        probabilitas=int(data.get('probabilitas') or 3),
        evaluasi_capaian=(data.get('evaluasi_capaian') or '').strip(),
        capaian_nilai=str(data.get('capaian_nilai') or ''),
        target_capaian=str(data.get('target_capaian') or ''),
        fishbone=fishbone,
        metode_evaluasi=(data.get('metode_evaluasi') or 'RCA').strip(),
    )
    if res.get('success'):
        res['mode'] = mode
    return JsonResponse(res, status=200 if res['success'] else 400)
```

- [ ] **Step 4: Add the route**

In `akreditasi/urls.py`, immediately after the `ai/evaluasi-risiko/` line:

```python
    path('ai/investigasi-rtl/', ai_views.api_ai_investigasi_rtl, name='ai_investigasi_rtl'),
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
$P manage.py test akreditasi.tests_ai --no-input
```

Expected: `0 failed`, `0 errors`.

- [ ] **Step 6: Commit**

```bash
git add akreditasi/ai_views.py akreditasi/urls.py akreditasi/tests_ai.py
git commit -m "feat(ai): expose investigation and RTL generation endpoint"
```

---

### Task 6: Wire the buttons into G.4 and G.5

**Files:**
- Modify: `templates/akreditasi/risiko_evaluasi.html` (G.4 header ~518-521, G.5 header ~567-570, `{% block extra_js %}` ~632)

**Interfaces:**
- Consumes: `{% url 'akreditasi:ai_investigasi_rtl' %}` from Task 5.
- Produces: DOM ids `btn-ai-investigasi`, `ai-inv-status`, `btn-ai-rtl`, `ai-rtl-status`; a JS function `arimaGenerateInvestigasiRTL(mode, opts)` reachable from the `?ai=` query bridge that Task 7 links into.

- [ ] **Step 1: Add the G.4 button group**

Replace the G.4 heading block (currently):

```html
                        <h6 class="fw-bold mb-3 pb-1 border-bottom pt-2" style="color:#0f172a; font-size:.82rem;">
                            <i class="bi bi-diagram-3-fill text-danger me-1"></i>G.4 Root Cause Analysis (RCA) Terstruktur — Metode Fishbone / 5-Whys
                        </h6>
```

with:

```html
                        <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 pb-1 border-bottom pt-2 gap-2">
                            <h6 class="fw-bold mb-0" style="color:#0f172a; font-size:.82rem;">
                                <i class="bi bi-diagram-3-fill text-danger me-1"></i>G.4 Root Cause Analysis (RCA) Terstruktur — Metode Fishbone / 5-Whys
                            </h6>
                            <div class="d-flex align-items-center gap-2">
                                <span id="ai-inv-status" class="small" style="font-size:.72rem;"></span>
                                <button type="button" class="btn btn-outline-primary btn-sm py-0 px-2 fw-semibold" id="btn-ai-investigasi" style="font-size:.72rem;">
                                    <i class="bi bi-stars me-1 text-warning"></i>✨ AI Ringkasan Investigasi
                                </button>
                            </div>
                        </div>
```

- [ ] **Step 2: Add the G.5 button group**

Replace the G.5 heading block (currently):

```html
                        <h6 class="fw-bold mb-3 pb-1 border-bottom pt-2" style="color:#0f172a; font-size:.82rem;">
                            <i class="bi bi-calendar2-check text-primary me-1"></i>G.5 Rencana Tindak Lanjut (RTL) &amp; Bukti Penyelesaian
                        </h6>
```

with:

```html
                        <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 pb-1 border-bottom pt-2 gap-2">
                            <h6 class="fw-bold mb-0" style="color:#0f172a; font-size:.82rem;">
                                <i class="bi bi-calendar2-check text-primary me-1"></i>G.5 Rencana Tindak Lanjut (RTL) &amp; Bukti Penyelesaian
                            </h6>
                            <div class="d-flex align-items-center gap-2">
                                <span id="ai-rtl-status" class="small" style="font-size:.72rem;"></span>
                                <button type="button" class="btn btn-outline-primary btn-sm py-0 px-2 fw-semibold" id="btn-ai-rtl" style="font-size:.72rem;">
                                    <i class="bi bi-stars me-1 text-warning"></i>✨ AI Rencana Tindak Lanjut
                                </button>
                            </div>
                        </div>
```

- [ ] **Step 3: Add the generator JS**

In `{% block extra_js %}` of `templates/akreditasi/risiko_evaluasi.html`, immediately after `<script>` and before the existing `(function() {` at line 634, insert:

```javascript
// ── G.4/G.5 AI: Ringkasan Investigasi & Rencana Tindak Lanjut ──────────
window.arimaGenerateInvestigasiRTL = async function (mode, opts) {
    opts = opts || {};
    const invBtn = document.getElementById('btn-ai-investigasi');
    const rtlBtn = document.getElementById('btn-ai-rtl');
    const invMsg = document.getElementById('ai-inv-status');
    const rtlMsg = document.getElementById('ai-rtl-status');
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrf) { return null; }

    const setMsg = (el, cls, html) => {
        if (!el) { return; }
        el.className = 'small ' + cls;
        el.style.fontSize = '.72rem';
        el.innerHTML = html;
    };
    const restore = () => {
        if (invBtn) { invBtn.disabled = false; invBtn.innerHTML = '<i class="bi bi-stars me-1 text-warning"></i>✨ AI Ringkasan Investigasi'; }
        if (rtlBtn) { rtlBtn.disabled = false; rtlBtn.innerHTML = '<i class="bi bi-stars me-1 text-warning"></i>✨ AI Rencana Tindak Lanjut'; }
    };
    if (invBtn) { invBtn.disabled = true; }
    if (rtlBtn) { rtlBtn.disabled = true; }
    setMsg(invMsg, 'text-muted', '<i class="bi bi-hourglass-split me-1"></i>Menyusun analisis…');
    setMsg(rtlMsg, 'text-muted', '<i class="bi bi-hourglass-split me-1"></i>Menyusun analisis…');

    const fishbone = {};
    ['manpower', 'process', 'material', 'machine', 'environment', 'system'].forEach(function (k) {
        const el = document.querySelector('[name="rca_' + k + '"]');
        if (el && el.value.trim()) { fishbone[k] = el.value.trim(); }
    });

    const targetEl = document.getElementById('target_capaian_indikator');
    const capaianEl = document.getElementById('capaian_nilai');

    const payload = {
        mode: mode,
        unit_name: "{{ risiko.unit.name|escapejs }}",
        jenis_risiko: "{{ risiko.jenis_risiko|escapejs }}",
        masalah: "{{ risiko.masalah|default:risiko.deskripsi_risiko|escapejs }}",
        data_pendukung: "{{ risiko.data_pendukung|escapejs }}",
        dampak: {{ risiko.dampak|default:3 }},
        probabilitas: {{ risiko.probabilitas|default:3 }},
        evaluasi_capaian: (document.getElementById('evaluasi_capaian') || {}).value || '',
        capaian_nilai: capaianEl ? capaianEl.value : '',
        target_capaian: targetEl ? targetEl.value : '',
        fishbone: fishbone,
        metode_evaluasi: "{{ risiko.metode_evaluasi|default:'RCA'|escapejs }}"
    };

    try {
        const resp = await fetch("{% url 'akreditasi:ai_investigasi_rtl' %}", {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf.value },
            body: JSON.stringify(payload)
        });
        const res = await resp.json();
        if (!res.success || !res.data) { throw new Error(res.error || 'Respon AI tidak valid'); }
        const d = res.data;
        const applied = [];

        const fillIfEmpty = (el, val) => {
            if (!el || !val) { return false; }
            if (el.value && el.value.trim() && !opts.overwrite) { return false; }
            el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            return true;
        };

        if (mode === 'investigasi' || mode === 'both') {
            if (d.analisis_investigasi && fillIfEmpty(document.getElementById('rca_ulang'), d.analisis_investigasi)) {
                applied.push('ringkasan investigasi');
            }
            if (d.fishbone) {
                Object.keys(d.fishbone).forEach(function (k) {
                    if (fillIfEmpty(document.querySelector('[name="rca_' + k + '"]'), d.fishbone[k])) {
                        applied.push('fishbone ' + k);
                    }
                });
            }
        }
        if (mode === 'rtl' || mode === 'both') {
            if (d.rencana_tindak_lanjut && fillIfEmpty(document.getElementById('rencana_tindak_lanjut'), d.rencana_tindak_lanjut)) {
                applied.push('RTL');
            }
            if (fillIfEmpty(document.getElementById('pj_rtl'), d.pj_saran)) { applied.push('PIC'); }
            const dl = document.getElementById('deadline_rtl');
            if (dl && !dl.value && d.target_hari) {
                const t = new Date();
                t.setDate(t.getDate() + parseInt(d.target_hari, 10));
                dl.value = t.toISOString().slice(0, 10);
                applied.push('tenggat');
            }
            const st = document.getElementById('status_rtl');
            if (st && d.status_rtl_saran) { st.value = d.status_rtl_saran; }
        }

        const note = res.fallback
            ? '<i class="bi bi-info-circle me-1"></i>Draf dasar (AI eksternal nonaktif) — periksa & lengkapi.'
            : '<i class="bi bi-check-circle me-1"></i>Draf AI siap — periksa sebelum menyimpan.';
        const detail = applied.length
            ? ' Terisi: ' + applied.join(', ') + '.'
            : ' Semua kolom tujuan sudah berisi teks; kosongkan dulu bila ingin ditimpa.';
        if (mode === 'investigasi' || mode === 'both') { setMsg(invMsg, 'text-success fw-semibold', note + detail); }
        if (mode === 'rtl' || mode === 'both') { setMsg(rtlMsg, 'text-success fw-semibold', note + detail); }
        return d;
    } catch (err) {
        setMsg(invMsg, 'text-danger', '<i class="bi bi-exclamation-triangle me-1"></i>Gagal AI: ' + err.message);
        setMsg(rtlMsg, 'text-danger', '<i class="bi bi-exclamation-triangle me-1"></i>Gagal AI: ' + err.message);
        return null;
    } finally {
        restore();
    }
};

document.addEventListener('DOMContentLoaded', function () {
    const invBtn = document.getElementById('btn-ai-investigasi');
    const rtlBtn = document.getElementById('btn-ai-rtl');
    if (invBtn) { invBtn.addEventListener('click', function () { window.arimaGenerateInvestigasiRTL('investigasi'); }); }
    if (rtlBtn) { rtlBtn.addEventListener('click', function () { window.arimaGenerateInvestigasiRTL('rtl'); }); }

    // Bridge from the MONEV table (?ai=both|investigasi|rtl): generate once on load.
    const want = new URLSearchParams(window.location.search).get('ai');
    if (want && ['investigasi', 'rtl', 'both'].indexOf(want) !== -1) {
        window.arimaGenerateInvestigasiRTL(want);
    }
});
```

- [ ] **Step 4: Verify the template renders and the wiring is present**

```bash
$P manage.py shell -c "
from django.test import Client
from django.contrib.auth.models import User
from akreditasi.risiko_models import RisikoUnit
u=User.objects.get(username='probe')
c=Client(); c.force_login(u)
r=RisikoUnit.objects.first()
h=c.get(f'/risiko/{r.pk}/evaluasi/').content.decode()
for t in ['btn-ai-investigasi','btn-ai-rtl','ai-inv-status','ai-rtl-status','arimaGenerateInvestigasiRTL','/ai/investigasi-rtl/']:
    print(t, '->', t in h)
print('status', c.get(f'/risiko/{r.pk}/evaluasi/').status_code)
"
```

Expected: every line `-> True` and `status 200`.

- [ ] **Step 5: Commit**

```bash
git add templates/akreditasi/risiko_evaluasi.html
git commit -m "feat(risiko): add AI investigation and RTL buttons to evaluation G.4/G.5"
```

---

### Task 7: Add the one-click bridge from the MONEV table

**Files:**
- Modify: `templates/akreditasi/risiko_monitoring_evaluasi.html` (action column, ~lines 414-450)

**Interfaces:**
- Consumes: the `?ai=` bridge installed in Task 6 (`/risiko/<id>/evaluasi/?ai=both`).
- Produces: nothing other tasks use.

- [ ] **Step 1: Add the button**

In the KOLOM 8 action cell, inside the `<div class="d-flex flex-column gap-1 w-100 justify-content-center" style="min-width: 125px;">`, immediately after the closing `</div>` of the existing inner `d-flex gap-1 w-100 justify-content-between` group and before the cell's `</div>`, insert:

```html
                                <a href="{% url 'akreditasi:risiko_evaluasi' risiko_id=r.pk %}?ai=both"
                                   class="btn btn-sm btn-outline-warning w-100 py-1 px-2 d-flex align-items-center justify-content-center gap-1 shadow-sm monev-action-btn"
                                   style="font-size:.72rem; font-weight:600;"
                                   title="Buat draf AI: Ringkasan Investigasi (RCA) &amp; Rencana Tindak Lanjut">
                                    <i class="bi bi-stars text-warning"></i>
                                    <span>AI Analisis &amp; RTL</span>
                                </a>
```

- [ ] **Step 2: Verify the button renders**

```bash
$P manage.py shell -c "
from django.test import Client
from django.contrib.auth.models import User
u=User.objects.get(username='probe')
c=Client(); c.force_login(u)
h=c.get('/risiko/monitoring-evaluasi/').content.decode()
print('AI button ->', '?ai=both' in h)
print('label ->', 'AI Analisis &amp; RTL' in h or 'AI Analisis & RTL' in h)
print('status ->', c.get('/risiko/monitoring-evaluasi/').status_code)
"
```

Expected: `AI button -> True`, `label -> True`, `status -> 200`.

- [ ] **Step 3: Commit**

```bash
git add templates/akreditasi/risiko_monitoring_evaluasi.html
git commit -m "feat(monev): add one-click AI analysis and RTL entry from the monitoring table"
```

---

### Task 8: Final gate

**Files:** `staticfiles/` (collectstatic output only)

**Interfaces:**
- Consumes: every previous task.
- Produces: a green full suite and a clean diff.

- [ ] **Step 1: Run the full suite**

```bash
$P manage.py test --no-input 2>&1 | tail -5
```

Expected: `OK`, `0 failed`, `0 errors`, and a test count greater than the Task 1 baseline. If any pre-existing failure reappears, report it — do not "fix" it inside this branch.

- [ ] **Step 2: Django system check**

```bash
$P manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Rebuild static assets**

```bash
$P manage.py collectstatic --no-input 2>&1 | tail -3
```

- [ ] **Step 4: Revert unrelated collectstatic churn**

```bash
git status --porcelain staticfiles | head -30
git checkout -- staticfiles/admin/ 2>/dev/null || true
git status --porcelain staticfiles
```

Keep only the hashed `css/style.*` / `js/main.*` artefacts and `staticfiles.json` if this branch changed them (it should not — no CSS/JS source was edited, so `git status --porcelain staticfiles` must be empty after the revert). If files remain modified, inspect each one; revert anything not produced by this branch's source changes.

- [ ] **Step 5: Browser verification**

Start the dev server and verify the two user-visible outcomes with a real browser session:

```bash
$P manage.py runserver 8765 --noreload
```

In the browser, logged in as a superuser:

1. Dashboard: pick **Kategori = IMRS**, then click a month bar and open the drill-down. The indicator line must read **"Rata-rata semua indikator terfilter"** (not a `[ ]` blank name), and the **Buat PDCA** button must be hidden with the hint shown. Then pick a specific IMRS indicator and confirm its name appears and the PDCA link carries *that* id.
2. Risk evaluation page for any risk: click **✨ AI Ringkasan Investigasi** → G.4 textarea and any empty fishbone inputs fill, the status line reports the applied fields. Click **✨ AI Rencana Tindak Lanjut** → G.5 textarea, PIC, and tenggat fill.
3. MONEV table: click **AI Analisis & RTL** → lands on the evaluation page and the draft appears without a second click.

Stop the server afterwards (`Ctrl+C` / kill the process) and delete any local `db.sqlite3` you created for the check.

- [ ] **Step 6: Report the diff**

```bash
git status --short
git log --oneline -7
```

Expected files changed across the branch: `akreditasi/views.py`, `akreditasi/ai_prompts.py`, `akreditasi/ai_service.py`, `akreditasi/ai_views.py`, `akreditasi/urls.py`, `akreditasi/tests_indikator_mutu_charts.py`, `akreditasi/tests_ai.py`, `templates/akreditasi/dashboard.html`, `templates/akreditasi/risiko_evaluasi.html`, `templates/akreditasi/risiko_monitoring_evaluasi.html`. Anything else is a scope violation — report it instead of committing.
