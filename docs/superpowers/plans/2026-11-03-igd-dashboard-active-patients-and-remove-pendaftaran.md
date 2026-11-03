# IGD Dashboard Active Patients Inclusion and Layanan Unit Registration Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
1. Ensure active Emergency Department (IGD) patients who entered prior to today (e.g. overnight admissions still in `TRIAGE`, `ASESMEN`, or `DAFTAR`) automatically appear in the IGD daily service roster on the Integrated Control EMR dashboard (`/control/emr/?unit=54`) and the daily service page (`/control/layanan/?unit=54`), resolving the issue where recently registered emergency patients (such as `aimto` and `muningsih`) are absent ("2 pasien belum masuk").
2. Remove the redundant "Pendaftaran pasien" entry card from the `LAYANAN UNIT` box (`templates/akreditasi/kontrol/_layanan_unit.html`), keeping patient registration strictly in its dedicated hospital-wide admission module as stated in the template footnote.

**Architecture:**
1. **Query Union for Active IGD Visits:** Modify `_layanan_block(unit, on_date=None)` in `akreditasi/kontrol_data.py`. When displaying the current day (`on_date == timezone.localdate()`) for a unit encompassing IGD (`'IGD' in codes`), query `Q(tanggal_masuk__date=on_date) | Q(jenis_kunjungan='IGD', status__in=['TRIAGE', 'ASESMEN', 'DAFTAR'])`. For prior calendar dates, format multi-day stay entries with date prefixes (e.g., `dd/mm HH:MM`) so dwell times remain clear to clinicians.
2. **Template Sanitization:** Remove the `{% if registration_action %}...{% endif %}` block from `templates/akreditasi/kontrol/_layanan_unit.html`. The accompanying footnote (`Daftar harian mengikuti unit aktif dan tanggal layanan. Pendaftaran pasien dibuka melalui modul terpisah sesuai hak akses.`) remains as an explicit indicator that registration belongs to the separate admission module.
3. **Contract & Regression Tests:** Update `akreditasi/tests_kontrol_registration.py` and `akreditasi/tests_layanan_unit.py` to assert that:
   - Active IGD patients registered yesterday appear in today's IGD Layanan Unit roster with accurate status.
   - `data-service-action="pendaftaran"` is no longer rendered inside `_layanan_unit.html`.
   - The dedicated registration dashboard (`pasien:pendaftaran_dashboard`) remains intact and accessible to entitled roles.

**Tech Stack:** Django 5.x, PostgreSQL (Supabase) / SQLite, Python 3.14, Bootstrap 5.

---

## Global Constraints

- **Non-Destructive Data Policy:** Do not alter existing database records or timestamps; all changes are query-level and template-level.
- **Unit Isolation:** Outpatient clinics (Rajal) retain date-strict filtering (`tanggal_masuk__date=on_date`) to prevent finished clinic queues from leaking across days. Only emergency/active-care units with overnight stays incorporate active un-discharged statuses.
- **Staticfiles Hygiene:** If CSS or layout rules are touched, execute `collectstatic` and commit tracked artifacts in `staticfiles/` as required for Vercel deployments.
- **Zero RBAC Regression:** Removing the registration button from `_layanan_unit.html` must not alter user module permissions for `pendaftaran` or restrict access to `pasien:pendaftaran_dashboard`.

---

## Review Focus

1. **IGD Multi-Day Dwell Visibility:** Verify that an emergency patient registered at `2026-11-02 23:50` with status `TRIAGE` appears in the `2026-11-03` IGD Layanan Unit snapshot and `/control/layanan/` list.
2. **Discharged Patient Exclusion:** Verify that an IGD patient whose status is `PULANG`, `RUJUK`, or `RANAP` from yesterday does NOT leak into today's roster.
3. **Template Cleanliness:** Verify that `/control/emr/?unit=54` renders without the "Pendaftaran pasien" card, displaying only "Daftar layanan pasien hari ini" and "Bed & okupansi" (if applicable).
4. **Historical Browsing:** Ensure that browsing previous dates via `?tanggal=YYYY-MM-DD` continues to show historical admissions for that specific calendar date.

---

## File Structure

- Modify: `akreditasi/kontrol_data.py:306-370`
- Modify: `templates/akreditasi/kontrol/_layanan_unit.html:11-23`
- Modify: `akreditasi/tests_layanan_unit.py`
- Modify: `akreditasi/tests_kontrol_registration.py`

---

## Execution Tasks

### Task 1: Fix Query in `_layanan_block` to Include Overnight Active IGD Patients

**Files:**
- Modify: `akreditasi/kontrol_data.py`
- Test: `akreditasi/tests_layanan_unit.py`

- [ ] **Step 1: Write regression test for multi-day active IGD patients**
Add test case `test_overnight_active_igd_patient_appears_in_today_layanan` in `akreditasi/tests_layanan_unit.py`:
Create an IGD patient with `tanggal_masuk = timezone.now() - timedelta(days=1)` and `status = 'TRIAGE'`.
Assert that `_layanan_block(igd_unit, on_date=timezone.localdate())['items']` contains this patient.
Also assert that a discharged IGD patient from yesterday (`status = 'PULANG'`) is NOT included in today's block.

- [ ] **Step 2: Implement union query in `akreditasi/kontrol_data.py`**
In `_layanan_block`:
```python
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone

on_date = on_date or timezone.localdate()
codes = unit_codes(unit)
index = alias_index()
serves = bool(codes & service_codes())
owns_beds = unit_owns_beds(unit, codes)

is_today = on_date == timezone.localdate()
is_igd = 'IGD' in codes

if is_today and is_igd:
    visit_filter = Q(tanggal_masuk__date=on_date) | Q(
        jenis_kunjungan='IGD',
        status__in=['TRIAGE', 'ASESMEN', 'DAFTAR']
    )
else:
    visit_filter = Q(tanggal_masuk__date=on_date)

rows = list(
    KunjunganPasien.objects
    .filter(visit_filter)
    .select_related('pasien', 'bed__ruangan')
    .order_by('tanggal_masuk')
    .distinct()[:LAYANAN_LIMIT]
)
```
In item formatting, check if admission occurred on an earlier date:
```python
k_local = timezone.localtime(k.tanggal_masuk)
if k_local.date() < on_date:
    jam_str = k_local.strftime('%d/%m %H:%M')
else:
    jam_str = k_local.strftime('%H:%M')
```

- [ ] **Step 3: Run targeted test suite**
Run: `uv run python manage.py test akreditasi.tests_layanan_unit --keepdb`

---

### Task 2: Remove "Pendaftaran Pasien" Action Card from Layanan Unit Template

**Files:**
- Modify: `templates/akreditasi/kontrol/_layanan_unit.html`
- Modify: `akreditasi/tests_kontrol_registration.py`

- [ ] **Step 1: Remove the registration card from `templates/akreditasi/kontrol/_layanan_unit.html`**
Delete lines 11-22:
```html
    {% if registration_action %}
    <a class="layanan-entry layanan-entry-registration"
       data-service-action="pendaftaran"
       href="{{ registration_action.href }}">
        <span class="layanan-entry-icon"><i class="bi bi-person-plus" aria-hidden="true"></i></span>
        <span class="layanan-entry-text">
            <strong>{{ registration_action.label }}</strong>
            <small>{{ registration_action.description }}</small>
        </span>
        <i class="bi bi-arrow-right layanan-entry-go" aria-hidden="true"></i>
    </a>
    {% endif %}
```

- [ ] **Step 2: Update tests in `akreditasi/tests_kontrol_registration.py`**
Update assertions expecting `data-service-action="pendaftaran"` inside the rendered EMR dashboard to verify:
1. `_layanan_unit.html` does NOT render the pendaftaran card.
2. The route `pasien:pendaftaran_dashboard` remains accessible and authorized for entitled roles.

- [ ] **Step 3: Run registration tests**
Run: `uv run python manage.py test akreditasi.tests_kontrol_registration --keepdb`

---

### Task 3: Full End-to-End Verification & Production Asset Check

**Files:**
- Check: `git status`
- Run: `uv run python manage.py check`
- Run: `uv run python manage.py test akreditasi.tests_layanan_unit akreditasi.tests_kontrol_registration --keepdb`

- [ ] **Step 1: Verify all unit and integration tests pass**
- [ ] **Step 2: Run Django system check**
- [ ] **Step 3: Verify static assets and git diff cleanliness**
