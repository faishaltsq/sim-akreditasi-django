# ARIMA System Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Integrate the Risk Register (ERM) cycle — Identifikasi → Plan → Do → Evaluasi → RTL — directly into the Unit Dashboard with live PDCA progress widgets and a shortcut button that bridges EP Akreditasi ↔ Risk Register navigation.

**Architecture:** Minimal additions to the existing `unit_dashboard` context in `views.py`; new PDCA-progress breakdown added to the KPI card; a floating shortcut button linking to `risiko_perencanaan_unit`; no new models — all data already exists in `RisikoUnit.status` field.

**Tech Stack:** Django 4.x, Bootstrap 5, Bootstrap Icons, vanilla JS (no new deps), existing `RisikoUnit` + `STATUS_CHOICES`.

**Spec:** `C:/Users/cubeb/Downloads/integrasi system arima.docx`

## Global Constraints

- No new pip dependencies — use only already-installed packages.
- No new models or migrations — `RisikoUnit.status` already has all required choices (`IDENTIFIKASI`, `PLAN`, `DO`, `EVALUASI`, `SELESAI`).
- Template changes only in `templates/akreditasi/dashboard.html`.
- View changes only in `akreditasi/views.py` (unit-scoped block, lines ~319–351).
- All tests in `akreditasi/tests_indikator_alur_integrasi.py` — keep 66/66 passing.
- Plans written in English.
- No wildcard `ALLOWED_HOSTS`.

## Review Focus

- `RisikoUnit` with no records → counts must be 0, not crash (`.count()` on empty QS is safe, but verify template renders 0 not `None`).
- Unit with child units → `unit_ids` already includes children; verify risiko breakdown also filters by `unit_ids`, not just `unit.id`.
- `status='SELESAI'` maps to "RTL / Terkendali" badge (green 🟢) — make sure the label wording matches spec exactly.
- Shortcut button must only appear on `unit_dashboard`, not on the global admin dashboard (guarded by `{% if unit_dashboard %}`).
- Navigate to Risk Register from komparasi-unit modal (existing Chart.js click handler) must still work after template changes.

---

## File Map

| File | Change |
|---|---|
| `akreditasi/views.py` | Add `risiko_plan`, `risiko_do`, `risiko_rtl` counts to unit-scoped context |
| `templates/akreditasi/dashboard.html` | (1) Expand Register Risiko Unit KPI card with 3-status breakdown; (2) Add shortcut button 🛡️ ERM |
| `akreditasi/tests_indikator_alur_integrasi.py` | Add `test_unit_dashboard_risiko_pdca_breakdown` |

---

## Task 1: Expose PDCA Status Counts in Unit Dashboard Context

**Files:**
- Modify: `akreditasi/views.py` lines ~318–350 (unit-scoped block)
- Test: `akreditasi/tests_indikator_alur_integrasi.py`

**Interfaces:**
- Consumes: `RisikoUnit.STATUS_CHOICES` — existing values `IDENTIFIKASI/PLAN/DO/EVALUASI/SELESAI/ACCEPTED`
- Produces: context keys `risiko_plan` (int), `risiko_do` (int), `risiko_rtl` (int) passed to template

- [x] **Step 1: Write failing test**

```python
# in akreditasi/tests_indikator_alur_integrasi.py
# append inside class IndikatorAlurIntegrasiTests

def test_unit_dashboard_risiko_pdca_breakdown(self):
    """Unit dashboard context must include risiko_plan, risiko_do, risiko_rtl counts."""
    from akreditasi.risiko_models import RisikoUnit
    from django.test import RequestFactory
    from django.contrib.auth.models import User
    from akreditasi.models import UserProfile

    user = User.objects.create_user(username='dashtest', password='x')
    up = UserProfile.objects.get_or_create(user=user)[0]
    up.unit_kerja = self.unit
    up.is_unit_scoped = True
    up.save()

    RisikoUnit.objects.create(
        unit=self.unit, tahun=2026, periode='TRIWULAN_1',
        kategori_risiko='OPERASIONAL', jenis_risiko='Test Plan',
        masalah='m', dampak=2, probabilitas=2,
        strategi_mitigasi='KURANGI', status='PLAN',
    )
    RisikoUnit.objects.create(
        unit=self.unit, tahun=2026, periode='TRIWULAN_1',
        kategori_risiko='OPERASIONAL', jenis_risiko='Test Do',
        masalah='m', dampak=2, probabilitas=2,
        strategi_mitigasi='KURANGI', status='DO',
    )
    RisikoUnit.objects.create(
        unit=self.unit, tahun=2026, periode='TRIWULAN_1',
        kategori_risiko='OPERASIONAL', jenis_risiko='Test RTL',
        masalah='m', dampak=2, probabilitas=2,
        strategi_mitigasi='KURANGI', status='SELESAI',
    )

    self.client.force_login(user)
    resp = self.client.get('/')
    self.assertEqual(resp.status_code, 200)
    self.assertEqual(resp.context['risiko_plan'], 1)
    self.assertEqual(resp.context['risiko_do'], 1)
    self.assertEqual(resp.context['risiko_rtl'], 1)
```

- [x] **Step 2: Run test — verify FAIL**

```bash
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django"
source .venv/Scripts/activate
python manage.py test akreditasi.tests_indikator_alur_integrasi.IndikatorAlurIntegrasiTests.test_unit_dashboard_risiko_pdca_breakdown -v2
```

Expected: `KeyError: 'risiko_plan'` or `AssertionError`.

- [x] **Step 3: Add counts to `views.py` unit-scoped block**

In `akreditasi/views.py`, inside the `if profile and profile.is_unit_scoped` block, **after** the `risiko_tinggi` line (~line 326), add:

```python
        risiko_plan = risiko_unit.filter(status='PLAN').count()
        risiko_do   = risiko_unit.filter(status='DO').count()
        risiko_rtl  = risiko_unit.filter(status__in=['SELESAI', 'ACCEPTED']).count()
```

Then add these three keys to the `context` dict (after `'risiko_tinggi': risiko_tinggi,`):

```python
            'risiko_plan': risiko_plan,
            'risiko_do':   risiko_do,
            'risiko_rtl':  risiko_rtl,
```

- [x] **Step 4: Run test — verify PASS**

```bash
python manage.py test akreditasi.tests_indikator_alur_integrasi -v2 2>&1 | grep -E "^Ran|^OK|FAIL"
```

Expected: all 11 tests PASS.

- [x] **Step 5: Commit**

```bash
git add akreditasi/views.py akreditasi/tests_indikator_alur_integrasi.py
git commit -m "feat(dashboard): expose PDCA status counts in unit dashboard context"
```

---

## Task 2: Expand Register Risiko Unit KPI Card with PDCA Breakdown

**Files:**
- Modify: `templates/akreditasi/dashboard.html` lines ~233–253 (Register Risiko Unit card)

**Interfaces:**
- Consumes: `risiko_plan`, `risiko_do`, `risiko_rtl` from Task 1 context
- Produces: visual 3-row breakdown inside KPI card (no new endpoints)

- [x] **Step 1: Locate the existing card in the template**

The card lives between `{% if unit_dashboard %}` and `<!-- BOX 4 (UNIT): EP TERISI -->`. Its current HTML:

```html
<div class="col-12 col-sm-6 col-xl-3">
    <div class="kpi-card kpi-evaluasi">
        <div>
            <div class="kpi-label">
                <span>Register Risiko Unit</span>
                <i class="bi bi-shield-exclamation text-warning fs-5"></i>
            </div>
            <div class="kpi-value text-warning">
                {{ total_risiko }}
            </div>
        </div>
        <div>
            <div class="d-flex justify-content-between kpi-sub mt-1.5">
                <span>Risiko Tinggi/Sangat Tinggi</span>
                <span class="fw-bold {% if risiko_tinggi > 0 %}text-danger{% else %}text-success{% endif %}">{{ risiko_tinggi }} Risiko</span>
            </div>
        </div>
    </div>
</div>
```

- [x] **Step 2: Replace card body with PDCA breakdown**

Replace the entire `<div class="kpi-card kpi-evaluasi">` inner content with:

```html
<div class="kpi-card kpi-evaluasi">
    <div>
        <div class="kpi-label">
            <span>Register Risiko Unit</span>
            <i class="bi bi-shield-exclamation text-warning fs-5"></i>
        </div>
        <div class="kpi-value text-warning">{{ total_risiko }}</div>
    </div>
    <div class="border-top pt-1 mt-1">
        <div class="d-flex justify-content-between kpi-sub mb-1">
            <span>🟡 Plan (Draft Mitigasi)</span>
            <span class="fw-bold text-warning">{{ risiko_plan }}</span>
        </div>
        <div class="d-flex justify-content-between kpi-sub mb-1">
            <span>🔵 Do (In Implementation)</span>
            <span class="fw-bold text-primary">{{ risiko_do }}</span>
        </div>
        <div class="d-flex justify-content-between kpi-sub">
            <span>🟢 RTL / Terkendali</span>
            <span class="fw-bold text-success">{{ risiko_rtl }}</span>
        </div>
    </div>
</div>
```

- [x] **Step 3: Smoke test visually — `manage.py check` + run server**

```bash
python manage.py check
python manage.py runserver 0.0.0.0:8001
```

Login as unit user, navigate to `/`. Verify card shows 3 rows.

- [x] **Step 4: Run full test suite**

```bash
python manage.py test akreditasi.tests_indikator_alur_integrasi akreditasi.tests_perencanaan_risiko -v2 2>&1 | grep -E "^Ran|^OK|FAIL"
```

Expected: 11 + 55 = 66 tests PASS.

- [x] **Step 5: Commit**

```bash
git add templates/akreditasi/dashboard.html
git commit -m "feat(dashboard): PDCA progress breakdown in Register Risiko Unit card"
```

---

## Task 3: Add ERM Shortcut Button on Unit Dashboard

**Files:**
- Modify: `templates/akreditasi/dashboard.html` — add button after KPI cards section, inside `{% if unit_dashboard %}` block

**Interfaces:**
- Consumes: `unit.id` from context (already present)
- Produces: clickable button → `risiko_perencanaan_unit` URL

- [x] **Step 1: Locate insertion point**

Find the closing `{% endif %}` of the `{% if unit_dashboard %}` KPI card block (after BOX 4 EP TERISI, before `{% else %}` for BOX 3 EVALUASI PDCA). The insertion goes immediately after BOX 4's closing `</div>` and before the `{% else %}`.

- [x] **Step 2: Insert shortcut button**

```html
<!-- ERM Shortcut: Risk Management cycle button (unit dashboard only) -->
<div class="col-12 mt-1 mb-2">
    <div class="d-flex gap-2 flex-wrap align-items-center">
        <a href="{% url 'akreditasi:risiko_perencanaan_unit' unit.id %}"
           class="btn btn-sm btn-outline-warning d-inline-flex align-items-center gap-1">
            <i class="bi bi-shield-check"></i>
            🛡️ Risk Management (ERM) — Lihat Siklus PDCA Unit
        </a>
        <a href="{% url 'akreditasi:risiko_monev_unit' unit.id %}"
           class="btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1">
            <i class="bi bi-arrow-repeat"></i>
            Monitoring &amp; Evaluasi
        </a>
        <a href="{% url 'akreditasi:indikator_dashboard' %}"
           class="btn btn-sm btn-outline-success d-inline-flex align-items-center gap-1">
            <i class="bi bi-graph-up"></i>
            Indikator Mutu
        </a>
    </div>
    <p class="text-muted mt-1 mb-0" style="font-size:0.72rem;">
        Data otomatis terhubung: Register Risiko Unit (ERM) ↔ Matriks PDCA EP Akreditasi ↔ Indikator Mutu
    </p>
</div>
```

Place this block between BOX 4 closing tag and `{% else %}`.

- [x] **Step 3: Verify URL names exist**

```bash
python manage.py shell -c "
from django.urls import reverse
print(reverse('akreditasi:risiko_perencanaan_unit', args=[1]))
print(reverse('akreditasi:risiko_monev_unit', args=[1]))
print(reverse('akreditasi:indikator_dashboard'))
"
```

Expected: `/risiko/perencanaan/1/`, `/risiko/monitoring-evaluasi/1/`, `/indikator-mutu/` (no error).

- [x] **Step 4: Run full suite**

```bash
python manage.py test akreditasi.tests_indikator_alur_integrasi akreditasi.tests_perencanaan_risiko 2>&1 | grep -E "^Ran|^OK|FAIL"
```

Expected: 66 PASS.

- [x] **Step 5: Commit + push**

```bash
git add templates/akreditasi/dashboard.html
git commit -m "feat(dashboard): ERM shortcut buttons linking Risk Register ↔ EP Akreditasi ↔ Indikator Mutu"
git push origin master
```

---

## Task 4: Deploy & Verify Production

- [x] **Step 1: Confirm Vercel deploy auto-triggered**

```bash
curl -sI https://sim-akreditasi-django.vercel.app/ | grep "HTTP/"
```

Expected: `HTTP/2 200`.

- [x] **Step 2: Verify no 500 errors on unit dashboard**

```bash
curl -s https://sim-akreditasi-django.vercel.app/ -o /dev/null -w "%{http_code}"
```

- [x] **Step 3: Update plan checkboxes to `[x]`**

```bash
sed -i 's/- \[ \]/- [x]/g' docs/superpowers/plans/2026-10-15-integrasi-system-arima.md
git add docs/
git commit -m "docs: mark integrasi-system-arima plan complete"
git push origin master
```
