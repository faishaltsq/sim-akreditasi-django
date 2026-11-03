# Pendaftaran & Admission Desk — Hospital-Wide Daily Services Implementation Plan

> **For agentic workers:** Use `executing-plans` for native execution or `subagent-driven-development` for task-by-task implementation and review. Track progress with the checkboxes below. This document is a plan, not approval to implement, commit, push, or deploy during the planning turn.

**Goal:** Make the Integrated Control EMR portal usable from the *Pendaftaran & Admission* desk (`UnitKerja` id 97, code `PENDAFTARAN-ADMISSION`) without pretending it is a clinical service unit: show today's hospital-wide patient flow, expose the registration shortcut that entitlement already allows, link the KPI to the real daily list, add per-row detail/SEP actions, and add an honest staff-on-duty panel sourced from real HR placement/shift data.

**Architecture:** Admission desks are not clinical units and must never be "mapped" to poliklinik or bangsal codes. Add one pure predicate, `is_admission_desk(unit)`, in `akreditasi/layanan_unit.py`; when it is true, `_layanan_block` and `_emr_block` read the whole hospital's visits for the selected date instead of resolving a unit code. Reuse the existing `snapshot`/`_common_context` plumbing, the existing `registration_action` builder (already computed but currently unrendered), the existing `pasien:` destinations (`pendaftaran_dashboard`, `kunjungan_detail`, `bpjs_buat_sep`), and the existing HR models (`sdm.PenempatanPegawai`, `sdm.PenugasanShift`, `accounts.NakesCredential`). No new model, no migration, no new route.

**Tech stack:** Django 6.x, server-rendered templates, Bootstrap 5.3.3, Bootstrap Icons, existing `static/css/kontrol-workspace.css`, SQLite test settings at `config/control_test_settings.py`.

**Specification:** `C:\Users\cubeb\Downloads\perbaikan didasbor pendaftaran.docx` (author Basirun Alummah, 2026-11-03), a consultant gap analysis of the STARKES EMR portal screenshot plus proposed Django/HTML samples. This plan implements the *intent* of that document against the real schema; the document's code samples are corrected in the "Document corrections" section below.

## Current context and assumptions

- **Progress at 2026-11-03 (post-planning):** Task 2 is applied in the working tree — `ADMISSION_DESK_CODES` + `is_admission_desk()` in `akreditasi/layanan_unit.py` and `AdmissionDeskTest` (4 tests) in `akreditasi/tests_layanan_unit.py`; class runs `OK`. Tasks 1, 3-9 are not started. Nothing is committed.
- Workspace `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django`, branch `master`, HEAD `7f220e4`, working tree clean at planning time.
- The screenshot in the document is `templates/akreditasi/kontrol/emr.html` rendered for `unit=97`. Evidence from the live SQLite database:
  - `akreditasi_unitkerja` id 97 = `PENDAFTARAN-ADMISSION`, name `Unit Pendaftaran & Admission`, `tipe_unit='RUANGAN'`, `parent_id=96` (`REKAM-MEDIS`, `INSTALASI`); sibling id 113 = `ADMISI` (`Unit Pendaftaran & Admisi Pasien`).
  - Unit 97 has zero `accounts_userprofile` rows and no child units. Nobody is unit-scoped to it; it is reached by broad roles selecting it from the unit switcher.
  - `pasien_kunjunganpasien` has 7 rows; all are synthetic/test (e.g. `IGD-TEST-…`, `REG-2026-0001`). `pasien_pasien` has 10 rows.
  - `sdm_pegawai` has 9 rows, `sdm_penempatanpegawai` 9 rows — **none** placed in unit 96/97/113. `sdm_shiftdinas`, `sdm_penugasanshift`, `sdm_periwatapresensi` are all **0 rows**. The staff panel therefore ships with an empty state, not fabricated names.
- Why the screenshot is empty (verified in code, not inferred):
  - `akreditasi/kontrol_data.py:326` sets `serves = bool(codes & service_codes())`; `service_codes()` (`akreditasi/layanan_unit.py:220-228`) only contains `POLI_UNIT_CODE` and `RUANGAN_UNIT_CODE` targets, so an admission desk is never "mapped" → the warning at `templates/akreditasi/kontrol/_layanan_unit.html:12-15`.
  - `akreditasi/kontrol_navigation.py:72-94` builds EMR actions only when `unit.code` equals a `POLI_UNIT_CODE` target, is `IGD`, or `layanan.owns_beds` with `ranap`; admission desks match none → `templates/akreditasi/kontrol/_module_actions.html:15` prints "Tidak ada pintasan operasional".
  - `registration_action(...)` exists in `akreditasi/kontrol_navigation.py:21-38` and is injected at `akreditasi/kontrol_views.py:131-133`, but **no template renders it**; commit `03390f8` deliberately removed the card from `_layanan_unit.html` while keeping the builder and its tests.
- Consultant's core recommendation — "map unit=97 to poliklinik and inpatient units" — is **rejected**. Mapping an admission desk into `POLI_UNIT_CODE`/`RUANGAN_UNIT_CODE` would (a) make every poli's patients look like that desk's own clinical service, (b) corrupt `service_codes()`-derived unit lists and `_emr_block` gaps for real clinical units, and (c) require editing a hand-maintained constant for a semantic that is "hospital-wide", not "this unit". A separate, explicit predicate is cheaper and reversible.
- Registration dashboard already exists and is rich: `pasien/views.py:835-882` + `templates/pasien/pendaftaran_dashboard.html` (7 tabs: patient new/old, rajal, IGD fast-track, ranap/SPRI, bed matrix, reports, utility). Utility tab already contains the BPJS V-Claim check (`api_cek_bpjs`, simulated when credentials absent; live client at `pasien/bpjs.py`). No new registration form is needed.
- The daily list page `akreditasi:kontrol_layanan` (`akreditasi/kontrol_views.py:318-366`, `templates/akreditasi/kontrol/layanan.html`) already renders time, RM, patient, age/sex, poli/room, DPJP, status badge, and penjamin — i.e. the document's "live patient queue" table already exists for clinical units. It is unreachable for admission desks because `mapped=False`.
- `_layanan_unit.html` is shared by EMR, risk, and document portals; any scope note added there must stay true on all three.
- Prior plans to reconcile: `docs/superpowers/plans/2026-11-03-igd-dashboard-active-patients-and-remove-pendaftaran.md` (executed in `03390f8`) removed the registration card from the Layanan block and added overnight-IGD inclusion. This plan **does not restore that card**; it renders the action in the `Akses modul` toolbar, which is a different surface and does not contradict that decision. `.hermes/plans/2026-10-24_185444-control-readability-emr-registration.md` supplies the typography/registration context; its CSS work is already in the tree.
- The installed interpreter is `.venv/Scripts/python.exe`. Tests must run under `config.control_test_settings` (in-memory SQLite, migrations disabled, local cache).

## Document corrections (claims in the doc vs. this repository)

| Document says | Reality in this repo | Plan uses |
|---|---|---|
| `class KunjunganPasien` with `no_registrasi`, `jenis_kunjungan RJ/RI/IGD`, `no_sep`, `tanggal_kunjungan` | `pasien.KunjunganPasien` already exists (`pasien/models.py:255`) with `no_kunjungan`, `jenis_kunjungan IGD/RAJAL/RANAP`, `tanggal_masuk`, `penjamin`, `status`, `unit_kerja`, `bed`, `status_antrean`, `nomor_antrean`; no `no_sep` column — SEP number lives in the BPJS response/print flow | existing model, no migration |
| `PatientVisit`, `AdmissionRecord`, `ClinicalUnit`, `StaffAssignment`, `EmployeeShift` | Do not exist | `pasien.KunjunganPasien`, `akreditasi.UnitKerja`, `sdm.PenugasanShift`, `sdm.PenempatanPegawai` |
| `Patient.medical_record_number`, `full_name`, `insurance_type` | Real fields are `no_rm`, `nama_lengkap`, `KunjunganPasien.penjamin` | real fields |
| New `dashboard_admission_view` + `urls.py` entries | `akreditasi:kontrol_emr`, `akreditasi:kontrol_layanan`, `pasien:pendaftaran_dashboard` already exist | existing routes |
| "Map unit 97 to poliklinik/bangsal" | Semantically wrong (see above) | `is_admission_desk()` hospital-wide mode |
| "Staf Pendaftaran Bertugas" from `StaffAssignment.is_active_shift` | No such field/table; 0 shift rows exist | `PenempatanPegawai` + optional `PenugasanShift` today, with empty state |
| "Real-time" | Snapshot cache is 60s (`SNAPSHOT_CACHE_VERSION`), page is request-rendered | same cache; copy must not promise streaming |
| Four quick actions: `+ Pasien Baru`, `+ RJ`, `+ RI`, `Cek Kepesertaan BPJS/SEP` | All four already live as tabs/utility inside `pasien:pendaftaran_dashboard` (`pasien/views.py:835-882`); portal toolbar has no room for four CTAs and `_module_actions` is a single-column list | one `Pendaftaran pasien` shortcut; the doc's other three are one click deeper in that dashboard |
| "Kunjungan aktif / Tanpa CPPT / Tanpa asesmen" all clickable | Only `active_total` has a destination list (`akreditasi:kontrol_layanan`); CPPT/assessment gap filters do not exist | link `Kunjungan aktif` only (Task 6) |

## Global constraints

1. No new Django model, no migration, no new URL route. Read-only queries; the only writes are the existing SEP POST endpoint.
2. Do not touch `POLI_UNIT_CODE`, `RUANGAN_UNIT_CODE`, `service_codes()`, or any unit-scoping authorization. Registration desks bypass unit resolution for *display* only; `_resolve_unit` and `UserProfile` scoping stay untouched.
3. Preserve current behavior for every clinical unit and for genuinely unmapped administrative units (`KOMITE-MUTU`, `DIREKSI`): same warning text, same empty actions, same zero/null semantics.
4. Registration remains entitlement-gated by `UserProfile.get_allowed_patient_modules()` containing `pendaftaran`. Do not widen RBAC.
5. Never render patient identifiers to users who could not already reach `pasien:pendaftaran_dashboard`; hospital-wide lists inherit the existing portal login + unit-scope rules only.
6. Do not add polling, websockets, AJAX refresh, or a "live" indicator. The 60-second snapshot cache is the contract.
7. `templates/akreditasi/kontrol/layanan.html` SEP action must be a `POST` form with `{% csrf_token %}` — `bpjs_buat_sep_view` performs an external write on GET.
8. Do not fabricate staff names, credentials, or BPJS status. Empty data renders an explicit empty state.
9. Static assets: this plan changes no CSS, so no `collectstatic` is required. If a task adds CSS, update `staticfiles/` in the same task.
10. Commit checkpoints apply only when execution authorization includes commits.

## Review focus

1. **Admission desk sees hospital-wide flow.** `unit=97` (`PENDAFTARAN-ADMISSION`) and `unit=113` (`ADMISI`) both render `mapped=True`, `scope='hospital'`, and today's list without any unit filter; a patient registered in `POLI-PD` appears.
2. **Clinical units unchanged.** `POLI-JANTUNG` must still show only its own poliklinik's visits, and `POLI-UMUM` (mapped to `None`) must still be unmapped.
3. **Parent installation.** `unit=96` (`REKAM-MEDIS`) also counts as an admission desk because a descendant is one; a committee unit with no desk descendant must not.
4. **Entitlement boundary.** A user without `pendaftaran` on an admission desk gets no registration shortcut and still receives HTTP 403 from the destination; `Tidak ada pintasan operasional` must still appear for `DIREKSI`.
5. **No duplicate registration entry.** The Layanan Unit block must not regain `data-service-action="pendaftaran"` (test at `akreditasi/tests_kontrol_registration.py:86` and `:96` guards this).
6. **SEP safety.** The SEP control is a POST form; a GET to the row action must not create a SEP.
7. **Honest staff panel.** With zero placements/shifts it says so; with one placement it shows name, role/profession, unit, and credential state derived from `NakesCredential` (or "Belum ada kredensial").

## File inventory

Modify:
- `akreditasi/layanan_unit.py` — `ADMISSION_DESK_CODES`, `is_admission_desk()`.
- `akreditasi/kontrol_data.py` — `_layanan_block` hospital-wide branch; `_emr_block` hospital-wide branch; new `_staff_block`; wire into `build_unit_snapshot`.
- `akreditasi/kontrol_navigation.py` — admission-desk registration shortcut inside `module_actions('emr', ...)`.
- `akreditasi/kontrol_views.py` — pass `layanan` to `module_actions` (already) and expose `staff` unchanged via snapshot; no structural change beyond what `build_unit_snapshot` returns.
- `templates/akreditasi/kontrol/_module_actions.html` — render `data-module-action` attributes; keep empty state.
- `templates/akreditasi/kontrol/_layanan_unit.html` — hospital-wide scope note branch.
- `templates/akreditasi/kontrol/emr.html` — clickable KPI link + staff panel include.
- `templates/akreditasi/kontrol/layanan.html` — actions column (Detail, SEP POST).
- `akreditasi/tests_layanan_unit.py` — desk resolver tests; adjust the ADMISI expectation.
- `akreditasi/tests_kontrol_registration.py` — replace the ADMISI "unmapped" assertion.
- `akreditasi/tests_kontrol_workspace.py` — keep DIREKSI empty-state test; add admission-desk action test.

Create:
- `akreditasi/tests_kontrol_admission_desk.py` — end-to-end matrix for desk mode, KPI link, staff panel, SEP action.

No generated static assets expected.

## Tasks

### Task 1: Baseline

- [x] Run the focused gate and record the actual count:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_layanan_unit akreditasi.tests_kontrol_registration akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_navigation --verbosity 1
```

Expected `OK`. Record the number of tests; it is the baseline for the final gate. A pre-existing failure is reported, not "fixed while here".

### Task 2: Add the admission-desk predicate

**Files:** `akreditasi/layanan_unit.py`, `akreditasi/tests_layanan_unit.py`.

**Interface:** `is_admission_desk(unit, codes=None) -> bool` — pure, no query when `codes` is supplied; uses `unit_codes(unit)` otherwise.

- [x] Append this test class to `akreditasi/tests_layanan_unit.py`:

```python
class AdmissionDeskTest(TestCase):
    def test_admission_codes_are_desks(self):
        from akreditasi.layanan_unit import is_admission_desk

        for code, name in (
            ('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission'),
            ('ADMISI', 'Unit Pendaftaran & Admisi Pasien'),
        ):
            with self.subTest(code=code):
                self.assertTrue(is_admission_desk(_unit(code, name, 4)))

    def test_parent_installation_of_a_desk_is_a_desk(self):
        from akreditasi.layanan_unit import is_admission_desk

        parent = _unit('REKAM-MEDIS', 'Instalasi Rekam Medis & Pendaftaran', 3)
        _unit('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission', 4, parent)
        self.assertTrue(is_admission_desk(parent))

    def test_clinical_and_committee_units_are_not_desks(self):
        from akreditasi.layanan_unit import is_admission_desk

        for code, name, level in (
            ('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4),
            ('KOMITE-MUTU', 'Komite Mutu PMKP & Keselamatan Pasien', 2),
            ('DIREKSI', 'Direksi', 1),
        ):
            with self.subTest(code=code):
                self.assertFalse(is_admission_desk(_unit(code, name, level)))

    def test_none_is_not_a_desk(self):
        from akreditasi.layanan_unit import is_admission_desk

        self.assertFalse(is_admission_desk(None))
```

- [x] RED: `... test akreditasi.tests_layanan_unit.AdmissionDeskTest --verbosity 2`. Expected `ImportError: cannot import name 'is_admission_desk'`.
- [x] In `akreditasi/layanan_unit.py`, after `EXTRA_ALIASES` (line 65), add:

```python
# Unit administratif yang mengelola alur pendaftaran seluruh rumah sakit.
# Unit seperti ini TIDAK dipetakan ke poliklinik/bangsal: pasiennya bukan
# "milik" unit, sehingga blok layanan dan KPI EMR harus dibaca RS-wide.
# Tambahkan kode di sini bila ada loket pendaftaran baru; bila suatu saat
# jumlahnya bertambah, ganti dengan flag DB di UnitKerja.
ADMISSION_DESK_CODES = frozenset({'PENDAFTARAN-ADMISSION', 'ADMISI'})
```

and after `unit_codes()` (line 197):

```python
def is_admission_desk(unit, codes=None):
    """True bila unit (atau turunannya) adalah loket pendaftaran/admisi."""
    if unit is None:
        return False
    codes = unit_codes(unit) if codes is None else codes
    return bool(codes & ADMISSION_DESK_CODES)
```

- [x] GREEN: rerun the class; expect `OK`.

### Task 3: Hospital-wide service block and EMR block

**Files:** `akreditasi/kontrol_data.py`, `akreditasi/tests_layanan_unit.py`.

- [x] Add tests to `AdmissionDeskTest`:

```python
    def _visit(self, no, poli, status='DAFTAR', jenis='RAJAL'):
        return KunjunganPasien.objects.create(
            pasien=_pasien('RM-' + no), no_kunjungan=no,
            jenis_kunjungan=jenis, tanggal_masuk=timezone.now(),
            poliklinik=poli, status=status)

    def test_desk_block_is_hospital_wide(self):
        from akreditasi.kontrol_data import _layanan_block

        _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3)
        desk = _unit('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission', 4)
        self._visit('K-1', 'Poli Penyakit Dalam')
        block = _layanan_block(desk)
        self.assertTrue(block['mapped'])
        self.assertEqual(block['scope'], 'hospital')
        self.assertEqual(block['total'], 1)

    def test_clinical_block_stays_unit_scoped(self):
        from akreditasi.kontrol_data import _layanan_block

        poli = _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3)
        _unit('POLI-ANAK', 'Poliklinik Anak', 3)
        self._visit('K-2', 'Poli Penyakit Dalam')
        self._visit('K-3', 'Poli Anak')
        block = _layanan_block(poli)
        self.assertTrue(block['mapped'])
        self.assertEqual(block['scope'], 'unit')
        self.assertEqual(block['total'], 1)
```

- [x] RED: both fail (`scope` key missing, desk `mapped=False`).
- [x] In `_layanan_block` (line 307), replace the resolution preamble:

```python
    codes = unit_codes(unit)
    index = alias_index()
    hospital_wide = is_admission_desk(unit, codes)
    serves = hospital_wide or bool(codes & service_codes())
    owns_beds = unit_owns_beds(unit, codes)
```

and the row filter so a desk skips per-row code matching:

```python
    for k in rows:
        if hospital_wide:
            pass  # setiap kunjungan RS pada tanggal itu, tanpa filter unit
        elif k.jenis_kunjungan == 'IGD':
            ...
```

Add `'scope': 'hospital' if hospital_wide else 'unit'` to the returned dict, and import `is_admission_desk` in the existing `from .layanan_unit import (...)` list at line 319-321.

Keep `truncated`, `by_status`, `owns_beds`, and item shape identical so the templates and existing tests stay green.

- [x] In `_emr_block` (line 191), mirror the same branch:

```python
    from .layanan_unit import is_admission_desk, resolve_visit_ids
    ...
    if is_admission_desk(unit):
        visits = KunjunganPasien.objects.filter(status__in=ACTIVE_VISIT_STATUSES)
    else:
        matching = resolve_visit_ids(active, unit)
        visits = (...)
```

- [x] Adjust the now-wrong test in `akreditasi/tests_kontrol_registration.py:92-98`. Replace the body of `test_unmapped_admission_still_has_registration` with:

```python
    def test_admission_desk_reads_hospital_wide_instead_of_unmapped(self):
        unit = self.login(code='ADMISI')
        response = self.emr(unit)
        layanan = response.context['snapshot']['layanan']
        self.assertTrue(layanan['mapped'])
        self.assertEqual(layanan['scope'], 'hospital')
        self.assertNotContains(response, 'data-service-action="pendaftaran"')
        self.assertNotContains(
            response,
            'belum memiliki pemetaan layanan klinis untuk daftar kunjungan harian')
```

Also rename the method in the same edit (do not add a second copy). `akreditasi/tests_layanan_unit.py::test_unmapped_unit_explains_itself` uses `KOMITE-MUTU` and must remain untouched.

- [x] GREEN: `... test akreditasi.tests_layanan_unit akreditasi.tests_kontrol_registration --verbosity 1`.

### Task 4: Scope copy for the shared Layanan block

**Files:** `templates/akreditasi/kontrol/_layanan_unit.html`, `akreditasi/tests_layanan_unit.py`.

- [x] Add a test to `AdmissionDeskTest`:

```python
    def test_desk_copy_states_hospital_scope(self):
        from django.urls import reverse
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache

        desk = _unit('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission', 4)
        user = get_user_model().objects.create_user('desk-copy', 'd@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=desk)
        self.client.force_login(user)
        cache.clear()
        body = self.client.get(
            reverse('akreditasi:kontrol_emr'), {'unit': desk.pk}).content.decode()
        self.assertIn('Seluruh rumah sakit', body)
        self.assertNotIn('belum memiliki pemetaan layanan klinis', body)
```

- [x] In `_layanan_unit.html`, inside the mapped branch, before the daily-service anchor, insert:

```django
    {% if snapshot.layanan.scope == 'hospital' %}
    <p class="kontrol-caption layanan-scope-note">
        Menampilkan seluruh kunjungan rumah sakit pada tanggal layanan, bukan hanya layanan klinis unit ini.
    </p>
    {% endif %}
```

Then replace the existing sentence at line 29 (`Daftar harian mengikuti unit aktif dan tanggal layanan.`) with:

```django
    <p class="kontrol-caption layanan-scope-note">
        {% if snapshot.layanan.scope == 'hospital' %}Daftar harian mengikuti tanggal layanan untuk seluruh rumah sakit.
        {% else %}Daftar harian mengikuti unit aktif dan tanggal layanan.{% endif %}
    </p>
```

Do not add both notes at once: the inserted paragraph explains *why* the scope is hospital-wide, the existing paragraph states the filter. If the two read as duplicates during implementation, keep only the conditional replacement (it is the one that must be true) and record the decision. Do not change the unmapped warning.

- [x] GREEN.

### Task 5: Registration and BPJS shortcuts in `Akses modul`

**Files:** `akreditasi/kontrol_navigation.py`, `templates/akreditasi/kontrol/_module_actions.html`, `akreditasi/tests_kontrol_workspace.py`.

**Interface:** `module_actions('emr', ...)` gains one dict `{'key': 'pendaftaran', 'label': 'Pendaftaran pasien', 'href': reverse('pasien:pendaftaran_dashboard'), 'scope': 'Seluruh rumah sakit', 'description': ...}` when `pendaftaran` is in `allowed_patient_modules`. No query string, no unit parameter.

- [x] Add tests to `ControlWorkspaceScopeTest` (the class owning `_login`, line 192):

```python
    def test_admission_desk_gets_registration_shortcut(self):
        unit = self._unit('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission', level=4)
        self._login(unit, role='STAF')
        res = self._get('akreditasi:kontrol_emr', unit)
        keys = [a['key'] for a in res.context['module_actions']]
        self.assertIn('pendaftaran', keys)
        self.assertContains(res, 'data-module-action="pendaftaran"')
        self.assertNotContains(res, 'Tidak ada pintasan operasional')

    def test_registration_shortcut_is_entitlement_gated(self):
        unit = self._unit('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission', level=4)
        self._login(unit, role='ASESOR')
        res = self._get('akreditasi:kontrol_emr', unit)
        self.assertNotIn('pendaftaran',
                         [a['key'] for a in res.context['module_actions']])
```

(`ASESOR` has no `pendaftaran` entitlement; confirm against `accounts/models.py::get_allowed_patient_modules` before writing the assertion — if it does, use `DIREKSI`/`KOMITE-MUTU` instead.)

- [x] RED.
- [x] In `kontrol_navigation.py::module_actions`, inside the `if portal == 'emr':` branch before the `rajal` loop:

```python
        if 'pendaftaran' in allowed:
            actions.append(_action(
                'pendaftaran', 'Pendaftaran pasien',
                'pasien:pendaftaran_dashboard',
                scope='Seluruh rumah sakit'))
```

Do **not** call `registration_action` twice or add a second source of truth; leave `registration_action` and its tests untouched (it stays available for the read-only context contract).

- [x] In `_module_actions.html`, add `data-module-action="{{ action.key }}"` to the anchor. Keep the empty-state paragraph exactly as-is so `tests_kontrol_workspace.py:228` stays valid.
- [x] GREEN: `... test akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_registration akreditasi.tests_kontrol_navigation`.

### Task 6: Clickable EMR KPI

**Files:** `templates/akreditasi/kontrol/emr.html`, `akreditasi/tests_kontrol_admission_desk.py` (new).

- [x] Create `akreditasi/tests_kontrol_admission_desk.py` with a shared fixture and one test:

```python
"""Kontrak dasbor EMR untuk loket Pendaftaran & Admission."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien


class AdmissionDeskDashboardTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.unit, _ = UnitKerja.objects.get_or_create(
            code='ADMISI',
            defaults={'name': 'Unit Pendaftaran & Admisi Pasien', 'level': 4})
        user = get_user_model().objects.create_user('desk-dash')
        UserProfile.objects.create(user=user, role='STAF', unit_kerja=self.unit)
        self.client.force_login(user)
        cache.clear()

    def test_active_visits_kpi_links_to_daily_list(self):
        res = self.client.get(reverse('akreditasi:kontrol_emr'),
                              {'unit': self.unit.pk})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'data-kpi-link="layanan"')
        self.assertContains(res, reverse('akreditasi:kontrol_layanan'))
```

- [x] RED.
- [x] In `emr.html`, replace the "Kunjungan aktif" KPI body (lines 11-15) with:

```django
    <div class="kpi">
        <span class="kpi-label">Kunjungan aktif</span>
        {% if snapshot.emr.active_total %}
        <a class="kpi-value" data-kpi-link="layanan"
           href="{% url 'akreditasi:kontrol_layanan' %}?unit={{ unit.id }}">{{ snapshot.emr.active_total }}</a>
        {% else %}
        <strong class="kpi-value">{{ snapshot.emr.active_total }}</strong>
        {% endif %}
        <span class="kpi-foot">status terdaftar sampai rawat inap pada unit aktif</span>
    </div>
```

Only the KPI value becomes a link; do not wrap the card, and do not add links for the two gap KPIs (they would need a gap filter that does not exist).

- [x] GREEN.

### Task 7: Row actions on the daily list

**Files:** `templates/akreditasi/kontrol/layanan.html`, `akreditasi/tests_kontrol_admission_desk.py`.

- [x] Add a test:

```python
    def test_sep_action_is_post_only_for_bpjs_rows(self):
        pasien = Pasien.objects.create(
            no_rm='RM-SEP', nama_lengkap='Pasien SEP',
            tanggal_lahir='1990-01-01', jenis_kelamin='L')
        k = KunjunganPasien.objects.create(
            pasien=pasien, no_kunjungan='SEP-1', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            poliklinik='Poli Penyakit Dalam', penjamin='BPJS', status='DAFTAR')
        res = self.client.get(reverse('akreditasi:kontrol_layanan'),
                              {'unit': self.unit.pk})
        body = res.content.decode()
        sep_url = reverse('pasien:bpjs_buat_sep', args=[k.pk])
        self.assertIn(f'action="{sep_url}"', body)
        self.assertIn('method="post"', body.lower())
```

Add `from django.utils import timezone` to the new test module's imports. Note that `Poli Penyakit Dalam` will not resolve to a unit for an admission desk (verification `KunjunganPasien` field set — do not invent fields such as `tgl_kunjungan`).

- [x] RED.
- [x] In `layanan.html`, add `<th>Aksi</th>` to the header row and a matching `<td>` per row:

```django
                    <td class="text-nowrap">
                        <a class="kontrol-ghost" href="{% url 'pasien:kunjungan_detail' i.pk %}">Detail</a>
                        {% if i.penjamin == 'BPJS Kesehatan' %}
                        <form method="post" action="{% url 'pasien:bpjs_buat_sep' i.pk %}" class="d-inline">
                            {% csrf_token %}
                            <button type="submit" class="kontrol-ghost">SEP</button>
                        </form>
                        {% endif %}
                    </td>
```

`i.penjamin` is already the display label (`'BPJS Kesehatan'` via `get_penjamin_display()` at `kontrol_data.py:378`). If a stricter check is preferred, expose `penjamin_code` from `_layanan_block` and compare to `'BPJS'`; do not string-compare a translated label twice.

- [x] GREEN.

### Task 8: Staff-on-duty panel

**Files:** `akreditasi/kontrol_data.py`, `templates/akreditasi/kontrol/_staff_unit.html` (new), `templates/akreditasi/kontrol/emr.html`, `akreditasi/tests_kontrol_admission_desk.py`.

**Interface:** `snapshot['staff'] = {'items': [...], 'total': int, 'scope': 'unit'|'subtree'}`; each item `{'nama', 'profesi', 'unit', 'shift', 'hadir', 'kredensial'}`.

- [x] Add a probe-driven test:

```python
    def test_staff_panel_lists_placed_employees_and_empty_state(self):
        from sdm.models import Pegawai, PenempatanPegawai
        from datetime import date

        pegawai = Pegawai.objects.create(nama_lengkap='Petugas Uji', kategori='NON_PPA')
        PenempatanPegawai.objects.create(
            pegawai=pegawai, unit_kerja=self.unit, tanggal_mulai=date(2025, 1, 1),
            alokasi_fte=1)
        body = self.client.get(reverse('akreditasi:kontrol_emr'),
                              {'unit': self.unit.pk}).content.decode()
        self.assertIn('Petugas Uji', body)

    def test_staff_panel_empty_state_without_placement(self):
        body = self.client.get(reverse('akreditasi:kontrol_emr'),
                              {'unit': self.unit.pk}).content.decode()
        self.assertIn('Belum ada petugas yang ditempatkan', body)
```

Check the real required fields of `Pegawai`/`PenempatanPegawai` (`sdm/models/*.py`) before writing the fixtures; use only fields the models actually declare (no `status_kepegawaian` — it does not exist).

- [x] RED.
- [x] Add `_staff_block(unit)` to `kontrol_data.py`:

```python
def _staff_block(unit):
    """Petugas yang ditempatkan di unit ini; shift hari ini bila sudah dijadwalkan."""
    from django.utils import timezone
    from sdm.models import PenempatanPegawai, PenugasanShift

    if unit is None:
        return {'items': [], 'total': 0, 'scope': 'unit'}

    today = timezone.localdate()
    placements = (PenempatanPegawai.objects
                  .filter(unit_kerja=unit,
                          tanggal_mulai__lte=today)
                  .filter(Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=today))
                  .select_related('pegawai__akun__profile'))
    shifts = {
        a.employee_id: a.shift
        for a in PenugasanShift.objects
        .filter(tanggal=today, is_active=True, shift__unit_kerja=unit)
        .select_related('shift')
    }
    items = []
    for p in placements:
        pegawai = p.pegawai
        profile = getattr(pegawai.akun, 'profile', None) if pegawai.akun_id else None
        kredensial = 'Belum ada kredensial'
        if profile is not None:
            from accounts.models import NakesCredential
            kredensial = ('Valid' if NakesCredential.objects.filter(
                user_profile=profile, status='VERIFIED').filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=today)).exists()
                else 'Belum valid')
        shift = shifts.get(pegawai.pk)
        items.append({
            'nama': pegawai.nama_lengkap,
            'profesi': pegawai.get_kategori_display(),
            'unit': unit.name,
            'shift': shift.nama if shift else 'Belum ada jadwal shift',
            'hadir': None,
            'kredensial': kredensial,
        })
    return {'items': items, 'total': len(items), 'scope': 'unit'}
```

Notes for the implementer: `PenugasanShift.employee` is a `Pegawai` FK; attendance (`PeristiwaPresensi`) has no rows in this database, so `hadir` stays `None` and the template prints `—` rather than inventing a status. Do not add a query per row for credentials beyond this loop in the first version; if the panel grows, aggregate `NakesCredential` in one query keyed by `user_profile_id`.

- [x] Wire `'staff': _staff_block(unit)` into `build_unit_snapshot` (line 396) next to `'layanan'`.
- [x] Create `templates/akreditasi/kontrol/_staff_unit.html`:

```django
<section class="kontrol-panel" aria-label="Petugas unit">
    <header class="panel-head">
        <h2><i class="bi bi-person-badge"></i> Petugas unit</h2>
        <span class="panel-hint">penempatan aktif</span>
    </header>
    {% if snapshot.staff.total %}
    <ul class="list-group list-group-flush">
        {% for s in snapshot.staff.items %}
        <li class="list-group-item">
            <strong>{{ s.nama }}</strong>
            <div class="kontrol-caption">{{ s.profesi }} · {{ s.shift }} · Kredensial: {{ s.kredensial }}</div>
        </li>
        {% endfor %}
    </ul>
    {% else %}
    <p class="kontrol-empty-inline"><i class="bi bi-inbox"></i> Belum ada petugas yang ditempatkan di unit ini.</p>
    {% endif %}
</section>
```

- [x] Include it in `emr.html` immediately after the `kontrol-grid-2` block (before `_ai_panel.html`). Do not add it to risk/document portals.
- [x] GREEN.

### Task 9: Full gate

- [x] Run the focused gate plus the new module:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_layanan_unit akreditasi.tests_kontrol_registration akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_navigation akreditasi.tests_kontrol_admission_desk akreditasi.tests_kontrol_snapshot akreditasi.tests_kontrol_render akreditasi.tests_kontrol_dasbor --verbosity 1
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django check
```

Expected `OK`, exit code 0, no system-check errors. Compare the test count to the Task 1 baseline; every new test must be accounted for.

- [x] `git status --short` — only the files in the inventory, plus the new test file. No `staticfiles/` churn.

## Risks and open questions

1. **Desk-code constant.** `ADMISSION_DESK_CODES` is a literal set of two codes. If the hospital renames a unit, the desk silently reverts to "unmapped". Mitigation: the constant carries an upgrade note; a follow-up may add `UnitKerja.owns_hospital_visits` (needs a migration) when a third desk appears.
2. **Parent installation.** Treating `REKAM-MEDIS` (96) as a desk because a child is one is a deliberate convenience for the instalasi head. If the product should not do ancestor inheritance, pass `codes={unit.code}` instead of `unit_codes(unit)` in `is_admission_desk` — one-line change, one test update.
3. **Hospital-wide patient visibility.** Any user who can open the EMR portal for an admission desk now sees the whole hospital's daily patient list. This matches the desk's job and the existing `pasien:pendaftaran_dashboard` visibility, but it is a *widening* for committee accounts that select `ADMISI` manually. Confirm with the owner before shipping if that is not intended.
4. **Staff panel is data-empty today.** 0 placements for units 96/97/113 and 0 shift rows. The feature is correct but will show the empty state until HR places staff and publishes a roster. This is a data task, not part of this plan.
5. **SEP via POST.** `pasien:bpjs_buat_sep` calls the external BPJS client. In simulation mode it returns a simulated success; in live mode it creates a real SEP. The row action must never be reachable by GET.
6. **"Real-time" phrasing.** The doc asks for real-time; the snapshot cache is 60 seconds. Copy says "tanggal layanan", never "real-time".

## Explicitly NOT in this plan — do not implement, do not fix while here

- Mapping `PENDAFTARAN-ADMISSION`/`ADMISI` into `POLI_UNIT_CODE` or `RUANGAN_UNIT_CODE`.
- Creating the document's `KunjunganPasien`, `StaffAssignment`, `ClinicalUnit`, or `PatientVisit` models; any migration.
- A new admission dashboard route, controller, or template.
- BPJS/SatuSehat live-status widgets or polling on the dashboard; `pasien:integrasi_status` stays as-is.
- NIK/BPJS real-time validation gates inside the registration form.
- Restoring the registration card inside `Layanan Unit` (removed intentionally in `03390f8`).
- Changing `service_codes()`, `unit_codes()`, `_resolve_unit()`, `UserProfile.get_allowed_patient_modules()`, or any RBAC.
- Reworking the typography/CSS of the control workspace.

## Acceptance checklist

- [x] `unit=97` and `unit=113` render today's hospital-wide visits with `scope='hospital'` and no "belum memiliki pemetaan" warning.
- [x] `unit=96` also reads hospital-wide; `POLI-*`, `IGD`, `KOMITE-MUTU`, `DIREKSI` behavior is unchanged.
- [x] An entitled admission-desk user sees a `Pendaftaran pasien` entry in `Akses modul`; a non-entitled user does not, and still gets `Tidak ada pintasan operasional`.
- [x] The "Kunjungan aktif" KPI links to `akreditasi:kontrol_layanan` for the selected unit.
- [x] The daily list exposes `Detail` for every row and a `POST`-only `SEP` button for BPJS rows.
- [x] The staff panel lists placed employees or prints the explicit empty state; no invented names or credentials.
- [x] No model, migration, route, CSS, or static-asset change; focused suite green; system check clean.
## Execution record — 2026-11-03

Executed in three parallel lanes after Task 2 was already in the tree.

**Files changed:** `akreditasi/layanan_unit.py` (constant + predicate), `akreditasi/kontrol_data.py` (`_layanan_block` hospital-wide, `_emr_block` hospital-wide, new `_staff_block`, `penjamin_code` on row items, `SNAPSHOT_CACHE_VERSION` v2→v3), `akreditasi/kontrol_navigation.py` (desk-gated registration action), `_module_actions.html`, `_layanan_unit.html`, `emr.html`, `layanan.html`, `_staff_unit.html` (new), `tests_layanan_unit.py`, `tests_kontrol_registration.py`, `tests_kontrol_workspace.py`, `tests_kontrol_admission_desk.py` (new).

**Gate:** `layanan_unit + kontrol_registration + kontrol_workspace + kontrol_navigation + kontrol_admission_desk + kontrol_snapshot + kontrol_render + kontrol_dasbor` → **118 tests, OK**, `django check` clean.

**Pre-existing red, diagnosed and fixed on request.** `tests_kontrol_registration.RegistrationEntryTest.test_emr_defaults_to_clinical_service_unit_when_no_unit_specified` failed at baseline (`'KOMITE-MUTU' != 'IGD'`), not because of the product but because the test created only a `KOMITE-MUTU` unit and then expected the EMR default to land on `IGD` — and the in-memory test database (migrations disabled) holds no seed units. Product logic was already correct: `service_codes()` does contain `IGD` (via `RUANGAN_UNIT_CODE`), so `_resolve_unit`'s clinical-first default picks `IGD` whenever an `IGD` unit exists. Fix = the missing fixture: the test now `get_or_create`s the `IGD` unit before opening the EMR without `?unit=`. `kontrol_views.py` unchanged.

**Corrections to this plan discovered during execution:**

1. **Entitlement comes from unit ancestry, not role.** `accounts.models.UserProfile.get_allowed_patient_modules` derives modules from the unit's `all_codes`, so a user placed in `PENDAFTARAN-ADMISSION` gets `pendaftaran` for *any* role (including `ASESOR`). The negative test therefore uses `DIREKSI`, not the plan's `ASESOR` guess. A `role='ASESOR'` user with **no** `unit_kerja` also lacks the entitlement, but that tests the wrong thing.
2. **`penjamin_code` was added** to `_layanan_block` row dicts (raw `k.penjamin`) so `layanan.html` can gate the SEP button on `'BPJS'` instead of comparing a translated label.
3. **`SNAPSHOT_CACHE_VERSION` bumped to `v3`** — the snapshot gained `layanan.scope` and `staff`; without the bump a 60s-old cached dict would render the new templates with missing keys.
4. **Task 4 note resolved toward the conditional replacement only.** One paragraph, not two: `Daftar harian mencakup seluruh rumah sakit pada tanggal layanan…` for `scope='hospital'`, the old sentence otherwise.
5. **Tests were not duplicated.** `test_admission_desk_gets_registration_shortcut` / `test_registration_shortcut_is_entitlement_gated` live only in `tests_kontrol_workspace.py`. `tests_kontrol_admission_desk.py` keeps the end-to-end tests that have no other home (KPI link both states, SEP POST/non-BPJS, staff panel both states, hospital-scope copy).
6. **Non-blocking plan item deferred:** the `NakesCredential` query in `_staff_block` runs per placed employee. Fine for a loket (single-digit headcount); aggregate by `user_profile_id` if the panel is ever reused for a ward with dozens of staff.
