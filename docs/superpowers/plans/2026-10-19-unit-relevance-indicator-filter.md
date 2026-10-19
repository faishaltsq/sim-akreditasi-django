# Unit-Relevance Indicator Filter — IMRS / IMU / INM Scoped to the Unit Being Viewed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the dashboard, each of the three indicator tiers (IMRS / IMU / INM) must list only the indicators that genuinely belong to — or involve — the unit being viewed, instead of flooding a unit with hospital-wide indicators. The INM leak is the loudest symptom: today a unit sees all 36 national indicators no matter whether it is involved in collecting any of them.

**Architecture:** One new resolver module owns unit-scope resolution and is imported by both views that currently re-implement it. Two behaviour changes fall out of it: (1) the unconditional `Q(jenis='NASIONAL')` clause is deleted, so INM is filtered by the same unit rule as every other tier — this works for free because the data already duplicates each INM row per involved unit; (2) the unit walk grows upward as well as downward, so a child unit sees the indicators owned by its organisational parent (the exact case in the spec's example: Bangsal Perawatan Anak owns nothing, its parent IRIN owns 3). No migration, no new endpoint, no new dependency.

**Status:** Not started. Analysis verified against the local dev DB on 2026-10-19.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3, Chart.js 4, vanilla JS.

**Spec:** `C:\Users\cubeb\OneDrive\Documents\Perubahan di bagian dasbort unit untuk melihat indikator mutu 19.10.docx` — four items: (0) remove the words "semua indikator", (1) IMRS category shows only indicators relevant and applicable to that unit, (2) IMU category shows only that unit's own scope/authority/internal measurement, (3) INM category shows only national indicators that correspond to and involve that unit in data collection.

## Global Constraints

- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `85,0`; one comma inside `<script>` kills the block (bugs `84c20ce`, `c4c2a3c`). Every template touched here must `{% load l10n %}` first.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.**
- **Role escape hatch is mandatory.** Tightening must not hide the indicator menu from the quality committee. `_is_unit_scoped` (accounts/models.py) returns True for anyone who is not a superuser / `SUPER_ADMIN` / `ADMIN_RS` / `DIREKTUR` **and** has a `unit_kerja`. Measured on the dev DB (2026-10-19, 36 profiles): `KOORDINATOR_POKJA` has a `unit_kerja` for **4 users** and `ASESOR` for **1 user** — both are unit-scoped today and would lose hospital-wide visibility the moment the NASIONAL clause goes. `KEPALA_UNIT` (10) and `STAF_NAKES` (5) are also unit-scoped and must **stay** scoped; they are the audience of this spec. The resolver exempts `HOSPITAL_WIDE_ROLES`; a test pins it.
- **`HOSPITAL_WIDE_ROLES` must only contain roles that exist.** `UserProfile.ROLE_CHOICES` is exactly `SUPER_ADMIN, ADMIN_RS, KOORDINATOR_POKJA, KEPALA_UNIT, STAF_NAKES, ASESOR`. `DIREKTUR` appears only as a stale literal inside `is_unit_scoped` and is not a selectable role; `SURVEYOR_INTERNAL` does not exist anywhere. So the list is `('KOORDINATOR_POKJA', 'ASESOR')` — do **not** pad it with `SUPER_ADMIN`/`ADMIN_RS`, which `_is_unit_scoped` already exempts (dead entries hide the real blast radius).
- **`UserProfile.is_unit_scoped` is a read-only property, not a field.** Tests must arrange it through `user.is_superuser`, `profile.role`, and `profile.unit_kerja`. Assigning `profile.is_unit_scoped = True` raises `AttributeError`.
- **`UnitKerja` has no `profile` reverse.** The OneToOne lives on the user (`related_name='profile'`), so fixtures build a `User`, attach `profile`, then set `profile.unit_kerja`.
- **`IndikatorMutu.unit` is `null=True, blank=True, on_delete=SET_NULL` (`risiko_models.py:579`).** `unit_id__in=[...]` therefore excludes NULL-unit rows. All 36/36 active INM are filled today, so nothing breaks, but pin the behaviour in a test so NULL stays a deliberate decision rather than an accident.
- **`aktif=True` stays applied.** `IndikatorMutu.objects.filter(aktif=True)` is already the base queryset at `akreditasi/views.py:143` and must not be duplicated or dropped inside the resolver.
- **`api_mutu_indikator` is the JSON twin of the dashboard filter.** It must agree with the dashboard exactly; they share one resolver so they cannot diverge. Its response keys are consumed by `reloadIndikator()` in `dashboard.html:967-974` and by `risiko_form.html:695` — extend additively, never rename.
- **Empty scope is a legitimate state, not an error.** 187 of 219 active units own zero indicators today, and this change makes more of them empty on purpose. The template must say so in words rather than drawing a blank chart.
- **Do not change `RisikoUnit.capaian_evaluasi` or `CatatanIndikator.tercapai`.** They already own `(target, arah, status, gap)` (shipped in `69d0440`). This plan adds no arithmetic.
- **Work on `master`; commit after each task.**
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi -v1` — baseline **173/173 OK** (measured 2026-10-19). Compare the failure list, not just the count.

## Verified code + data facts (local dev DB, read 2026-10-19)

| Fact | Where / Value |
|---|---|
| Unit-scope bug, dashboard | `akreditasi/views.py:149` — `ind_qs.filter(Q(unit_id__in=user_unit_ids) \| Q(jenis='NASIONAL'))` |
| Same bug, indicator pages | `akreditasi/indikator_views.py:169` — identical clause |
| Unit walk is downward only | `Q(pk=u) \| Q(parent=u) \| Q(parent__parent=u)` at `views.py:146-148` and `indikator_views.py:166-168` |
| `IndikatorMutu.unit` filled | **100%** of active indicators across all three tiers (IMP_RS 98, IMP_UNIT 76, NASIONAL 36) |
| INM already duplicated per unit | 36 rows, 21 unique names — "Kepatuhan Kebersihan Tangan" appears 9× across 9 units |
| INM per unit | 20 distinct units; IBS 4, twelve units 2, seven units 1 |
| Spec's own example | `BANGSAL-ANAK` → parent `IRIN` → grandparent `PELAKSANA-TEKNIS`. Bangsal owns **0** indicators; **IRIN owns 3 IMP_RS**. Current walk yields 0. |
| Units with zero indicators | 187 of 219 active |
| Indicator pages reachable from | `indikator_views.py:133` `indikator_dashboard`, `:594` `api_indikator_tren`, `:621` `api_indikator_komparasi_unit` |
| Both views already import `UnitKerja`, `Q` | `akreditasi/views.py`, `akreditasi/indikator_views.py` |
| "Semua Indikator (Rata-rata)" | `templates/akreditasi/dashboard.html:489` (option), `:968` (JS rebuild), `templates/akreditasi/indikator_dashboard.html:283` |
| Submit guard disabling empty select | `templates/akreditasi/dashboard.html:983-986` |

**The structural point that makes this cheap:** the spec asks for "indicators that involve this unit". The schema already encodes exactly that — every INM row carries the unit that performs its collection, and INM names are duplicated per unit rather than shared. No mapping table is required to answer the question this docx asks.

**Relationship to `docs/superpowers/plans/2026-10-18-inm-unit-access-matrix.md` (Not started):** that plan builds a new through-model `IndikatorUnitTerlibat`, adds `CatatanIndikator.unit`, and changes the unique key — driven by a different spec (hak akses + unit terlibat, 4.07.docx) whose Level 3/4 model has *several* units each typing their own realisation for one shared INM. This plan does **not** implement that. This plan answers "which indicators should this unit see", which the existing `unit` FK already supports. Do not merge the two; if the 4.07 requirement for multi-unit data entry is still wanted, it stands on its own plan. Implementing this one first does not block it and does not change its data model.

---

### Task 1: `akreditasi/akses_indikator.py` — one unit-scope resolver

**Files:**
- Create: `akreditasi/akses_indikator.py`
- Test: `akreditasi/tests_akses_indikator_unit.py`

**Interfaces:**
- Produces: `HOSPITAL_WIDE_ROLES: tuple[str, ...]`
- Produces: `unit_scope_ids(unit: UnitKerja) -> set[int]`
- Produces: `indikator_aktif_scoped(profile) -> QuerySet[IndikatorMutu]`

- [ ] **Step 1: Write the failing tests**

```python
# akreditasi/tests_akses_indikator_unit.py
from django.test import TestCase

from accounts.models import UserProfile
from akreditasi.akses_indikator import unit_scope_ids, indikator_aktif_scoped, HOSPITAL_WIDE_ROLES
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu


def _mk_unit(code, name, parent=None, level=3):
    return UnitKerja.objects.create(
        code=code, name=name, parent=parent, level=level, is_active=True
    )


def _mk_ind(unit, jenis, kode):
    return IndikatorMutu.objects.create(
        unit=unit, jenis=jenis, kode_indikator=kode, nama_indikator=kode,
        dimensi_mutu='AMAN', target_nilai=85, aktif=True,
    )


class UnitScopeIdsTest(TestCase):
    def test_includes_self_and_two_levels_of_descendants(self):
        root = _mk_unit('IRIN', 'Instalasi Rawat Intensif Anak', level=2)
        mid = _mk_unit('BANGSAL-ANAK', 'Bangsal Perawatan Anak', parent=root, level=3)
        leaf = _mk_unit('RUANG-ANAK', 'Ruang Anak', parent=mid, level=4)
        ids = unit_scope_ids(root)
        self.assertEqual(ids, {root.pk, mid.pk, leaf.pk})

    def test_includes_ancestors(self):
        root = _mk_unit('IRIN', 'Instalasi Rawat Intensif Anak', level=2)
        mid = _mk_unit('BANGSAL-ANAK', 'Bangsal Perawatan Anak', parent=root, level=3)
        ids = unit_scope_ids(mid)
        self.assertEqual(ids, {mid.pk, root.pk})

    def test_stops_at_top_without_error(self):
        top = _mk_unit('PELAKSANA', 'Pelaksana Teknis', parent=None, level=1)
        self.assertEqual(unit_scope_ids(top), {top.pk})


class IndikatorAktifScopedTest(TestCase):
    def test_unit_scoped_user_sees_own_and_parent_only(self):
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        anak = _mk_unit('BANGSAL-ANAK', 'Bangsal Anak', parent=irin, level=3)
        other = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        own = _mk_ind(anak, 'IMP_UNIT', 'U-ANAK')
        parent = _mk_ind(irin, 'IMP_RS', 'RS-IRIN')
        _mk_ind(other, 'IMP_RS', 'RS-INTERNA')

        prof = anak.profile
        prof.is_unit_scoped = True
        prof.save()
        qs = indikator_aktif_scoped(prof)
        self.assertSetEqual(set(qs.values_list('kode_indikator', flat=True)),
                            {'U-ANAK', 'RS-IRIN'})

    def test_nasional_is_filtered_by_unit_not_leaked(self):
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        anak = _mk_unit('BANGSAL-ANAK', 'Bangsal Anak', parent=irin, level=3)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'NASIONAL', 'INM-IRIN')
        _mk_ind(inter, 'NASIONAL', 'INM-INTERNA')

        prof = anak.profile
        prof.is_unit_scoped = True
        prof.save()
        qs = indikator_aktif_scoped(prof)
        self.assertEqual(list(qs.values_list('kode_indikator', flat=True)), ['INM-IRIN'])

    def test_inactive_indicators_excluded(self):
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        ind = _mk_ind(irin, 'IMP_RS', 'RS-OFF')
        ind.aktif = False
        ind.save()
        prof = irin.profile
        prof.is_unit_scoped = True
        prof.save()
        self.assertEqual(indikator_aktif_scoped(prof).count(), 0)

    def test_hospital_wide_role_sees_everything(self):
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMP_RS', 'RS-A')
        _mk_ind(inter, 'NASIONAL', 'INM-B')
        prof = irin.profile
        prof.is_unit_scoped = True
        prof.role = 'KOORDINATOR_POKJA'
        prof.save()
        self.assertIn(prof.role, HOSPITAL_WIDE_ROLES)
        self.assertEqual(indikator_aktif_scoped(prof).count(), 2)

    def test_manager_without_unit_kerja_sees_everything(self):
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        _mk_ind(irin, 'IMP_RS', 'RS-A')
        prof = irin.profile
        prof.is_unit_scoped = True
        prof.unit_kerja = None
        prof.save()
        self.assertEqual(indikator_aktif_scoped(prof).count(), 1)
```

Fixtures need `UnitKerja.code` and `UserProfile.role`/`unit_kerja`; check the real field names in `akreditasi/models.py:20-49` and `accounts/models.py` before writing if any assertion fails on a missing field.

- [ ] **Step 2: Run to confirm failure**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_akses_indikator_unit -v1`
Expected: `ImportError: cannot import name 'akses_indikator'` — exit code non-zero, `0 failed` is **not** the expected result here.

- [ ] **Step 3: Write the resolver**

```python
# akreditasi/akses_indikator.py
"""Penyelesaian lingkup unit untuk Indikator Mutu.

Satu-satunya tempat yang menjawab "indikator apa yang boleh dilihat unit
ini". Dipakai oleh akreditasi/views.dashboard dan akreditasi/indikator_views
agar keduanya tidak bisa berbeda jawaban.

Rationale: setiap baris IndikatorMutu membawa `unit` yang benar-benar
mengumpulkan datanya (terverifikasi 2026-10-19: 100% terisi, dan INM
diduplikasi per unit — "Kepatuhan Kebersihan Tangan" muncul 9x di 9 unit).
Karena itu filter per-unit sudah menjawab kebutuhan tanpa tabel pemetaan
tambahan.
"""
from django.db.models import Q

from .models import UnitKerja
from .risiko_models import IndikatorMutu

# Role yang wajib tetap melihat seluruh indikator rumah sakit, meski
# unit_kerja-nya terisi. Menghapus Q(jenis='NASIONAL') tanpa daftar ini
# menyembunyikan menu indikator dari 4 Koordinator Pokja + 1 Asesor
# (data 2026-10-19).
#
# Hanya berisi role yang benar-benar ada di ROLE_CHOICES. SUPER_ADMIN /
# ADMIN_RS sengaja tidak dimasukkan: _is_unit_scoped sudah mengembalikan
# False untuk mereka, jadi entri di sini cuma menutupi radius ledakan
# yang sebenarnya. DIREKTUR dan SURVEYOR_INTERNAL tidak ada di
# ROLE_CHOICES — jangan ditulis ulang.
HOSPITAL_WIDE_ROLES = ('KOORDINATOR_POKJA', 'ASESOR')

_DESCENDANT_DEPTH = 2
_ANCESTOR_DEPTH = 2


def unit_scope_ids(unit):
    """PK unit ini + turunannya (2 level) + leluhurnya (2 level).

    Turunan: kepala bangsal melihat indikator ruang di bawahnya.
    Leluhur: kepala bangsal melihat indikator milik instalasinya. Tanpa
    bagian ini Bangsal Perawatan Anak — nol indikator sendiri, induknya
    IRIN punya 3 IMP_RS — melihat daftar kosong.
    """
    if unit is None:
        return set()
    ids = {unit.pk}
    frontier = {unit.pk}
    for _ in range(_DESCENDANT_DEPTH):
        frontier = set(UnitKerja.objects.filter(parent_id__in=frontier)
                       .values_list('pk', flat=True)) - ids
        if not frontier:
            break
        ids |= frontier

    parent = unit.parent
    for _ in range(_ANCESTOR_DEPTH):
        if parent is None:
            break
        ids.add(parent.pk)
        parent = parent.parent
    return ids


def indikator_aktif_scoped(profile):
    """QuerySet IndikatorMutu aktif yang berada dalam lingkup user ini."""
    base = IndikatorMutu.objects.filter(aktif=True)
    if profile is None:
        return base
    if getattr(profile, 'role', None) in HOSPITAL_WIDE_ROLES:
        return base
    if not getattr(profile, 'is_unit_scoped', False):
        return base
    unit = getattr(profile, 'unit_kerja', None)
    if unit is None:
        return base
    return base.filter(unit_id__in=unit_scope_ids(unit))
```

- [ ] **Step 4: Run to confirm pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_akses_indikator_unit -v1`
Expected: `OK`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add akreditasi/akses_indikator.py akreditasi/tests_akses_indikator_unit.py
git commit -m "feat(indikator): unit-scope resolver walks ancestors and drops the INM leak"
```

---

### Task 2: Dashboard chart filter uses the resolver

**Files:**
- Modify: `akreditasi/views.py:143-156`
- Test: `akreditasi/tests_akses_indikator_unit.py`

**Interfaces:**
- Consumes: `indikator_aktif_scoped(profile)` from Task 1.

- [ ] **Step 1: Write the failing test**

```python
class DashboardScopeTest(TestCase):
    def test_dashboard_chart_indicator_list_is_unit_scoped(self):
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        anak = _mk_unit('BANGSAL-ANAK', 'Bangsal Anak', parent=irin, level=3)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMP_RS', 'RS-IRIN')
        _mk_ind(inter, 'IMP_RS', 'RS-INTERNA')
        _mk_ind(inter, 'NASIONAL', 'INM-INTERNA')

        prof = anak.profile
        prof.is_unit_scoped = True
        prof.save()
        self.client.force_login(prof.user)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        choices = res.context['mutu_indikator_choices']
        self.assertEqual([c.kode_indikator for c in choices], ['RS-IRIN'])
```

Confirm the route path against `akreditasi/urls.py:11` before running.

- [ ] **Step 2: Run to confirm failure**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_akses_indikator_unit.DashboardScopeTest -v1`
Expected: FAIL — the choice list still contains `RS-INTERNA` and `INM-INTERNA`.

- [ ] **Step 3: Replace the scope block**

In `akreditasi/views.py`, the block at lines 143-156 becomes:

```python
    from .akses_indikator import indikator_aktif_scoped
    ind_qs = indikator_aktif_scoped(profile)

    # Pengguna non unit-scoped memilih unit lewat dropdown: lingkupnya unit
    # itu persis (bukan seluruh pohon), agar perbandingan antar unit tetap
    # bisa ditujukan ke satu unit.
    if not (profile and profile.is_unit_scoped and profile.unit_kerja) and mutu_unit:
        ind_qs = ind_qs.filter(unit_id=mutu_unit)

    if mutu_jenis:
        # Canonical tier codes (INM/IMRS/IMU) must reach the legacy rows the DB actually stores
        _JENIS_MAP = {'INM': ['INM', 'NASIONAL'], 'IMRS': ['IMRS', 'IMP_RS'], 'IMU': ['IMU', 'IMP_UNIT']}
        ind_qs = ind_qs.filter(jenis__in=_JENIS_MAP.get(mutu_jenis, [mutu_jenis]))
```

Move the `from .akses_indikator import ...` line to the module imports at the top of the file instead of inside the function if the file already imports sibling modules there — check lines 1-40 first.

- [ ] **Step 4: Run to confirm pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_akses_indikator_unit -v1`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add akreditasi/views.py akreditasi/tests_akses_indikator_unit.py
git commit -m "fix(dashboard): indicator chart lists only indicators relevant to the viewed unit"
```

---

### Task 3: Indicator pages and both APIs use the same resolver

**Files:**
- Modify: `akreditasi/indikator_views.py:133-169`
- Test: `akreditasi/tests_akses_indikator_unit.py`

**Interfaces:**
- Consumes: `indikator_aktif_scoped(profile)` from Task 1.
- Produces: none new — `api_indikator_tren` and `api_indikator_komparasi_unit` must keep their current JSON shapes.

- [ ] **Step 1: Write the failing test**

```python
class IndicatorPagesScopeTest(TestCase):
    def test_indikator_dashboard_applies_same_scope(self):
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        anak = _mk_unit('BANGSAL-ANAK', 'Bangsal Anak', parent=irin, level=3)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMP_RS', 'RS-IRIN')
        _mk_ind(inter, 'IMP_RS', 'RS-INTERNA')
        _mk_ind(inter, 'NASIONAL', 'INM-INTERNA')

        prof = anak.profile
        prof.is_unit_scoped = True
        prof.save()
        self.client.force_login(prof.user)
        res = self.client.get('/indikator-mutu/')
        self.assertEqual(res.status_code, 200)
        got = {i.kode_indikator for i in res.context['indikators']}
        self.assertEqual(got, {'RS-IRIN'})
```

- [ ] **Step 2: Run to confirm failure**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_akses_indikator_unit.IndicatorPagesScopeTest -v1`
Expected: FAIL — `INM-INTERNA` still present.

- [ ] **Step 3: Replace the scope block in `indikator_dashboard`**

Lines 160-169 become:

```python
    # Unit-scoped user: hanya indikator yang relevan dengan unitnya
    # (termasuk INM yang benar-benar dikumpulkan unit itu).
    profile = getattr(request.user, 'profile', None)
    qs = indikator_aktif_scoped(profile).filter(jenis__in=db_codes) if jenis else indikator_aktif_scoped(profile)
```

Read lines 133-158 first and fold the `jenis` / `unit_id` filters in so the ordering stays: base scope → jenis → explicit `unit_id`. The resolver returns the `aktif=True` base, so the earlier `qs = qs.filter(jenis__in=db_codes)` and `qs = qs.filter(unit_id=unit_id)` calls must be re-pointed at the resolver's queryset rather than duplicated.

- [ ] **Step 4: Verify the two APIs diverge from nothing**

Confirm `api_indikator_tren` (line 594) and `api_indikator_komparasi_unit` (line 621) build their indicator queryset. If either queries `IndikatorMutu.objects.filter(jenis='NASIONAL')` directly for a unit-scoped user, route it through the resolver. If `api_indikator_komparasi_unit` is intentionally cross-unit (a comparison table), leave it and say so in the commit message.

- [ ] **Step 5: Run to confirm pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_akses_indikator_unit -v1`
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add akreditasi/indikator_views.py akreditasi/tests_akses_indikator_unit.py
git commit -m "fix(indikator): indicator pages apply the same unit scope as the dashboard"
```

---

### Task 4: Name the empty state (scope reduced 2026-10-19)

**Decision — "Semua Indikator" stays.** Step 3–5 below were drafted to delete
the average mode entirely. Checked against the source document before
implementing: the doc lists the default as something to *verify*
("perlu dicek apakah diganti"), not an instruction to remove. After Task 2
the average is already scoped to the unit's own subtree + ancestors, so the
reported complaint (a unit seeing other units' indicators) is fixed without
touching the control. Deleting it would strand `views.py:193-196`
(`avg_target_raw` for the no-selection case) as dead code and remove a
working view from units that use it. Steps 3–5 are therefore **dropped**;
Step 6 is the whole of this task.

**Out of scope:** `templates/akreditasi/indikator_dashboard.html:283` also
carries a "Semua Indikator (Rata-rata)" option, but that is the indicator
input/detail page, not the unit dashboard filter this document is about.
Left untouched.

**Files:**
- Modify: `templates/akreditasi/dashboard.html` (notice before the tab content)
- Test: `akreditasi/tests_akses_indikator_unit.py`

**Interfaces:**
- Consumes: `mutu_indikator_choices` (unchanged shape), `mutu_jenis_choices`.
- Produces: the `mutu_indikator` GET parameter is now always non-empty after a redirect from a bare `/dashboard/`.

- [ ] **Step 1: Write the failing test**

```python
class NoAllIndicatorsOptionTest(TestCase):
    def test_indicator_select_has_no_all_option(self):
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        _mk_ind(irin, 'IMP_RS', 'RS-A')
        prof = irin.profile
        prof.is_unit_scoped = True
        prof.save()
        self.client.force_login(prof.user)
        body = self.client.get('/dashboard/').content.decode()
        self.assertNotIn('Semua Indikator', body)

    def test_empty_scope_says_so_in_words(self):
        anak = _mk_unit('BANGSAL-ANAK', 'Bangsal Anak', level=3)
        prof = anak.profile
        prof.is_unit_scoped = True
        prof.save()
        self.client.force_login(prof.user)
        body = self.client.get('/dashboard/').content.decode()
        self.assertIn('belum memiliki indikator mutu', body)
```

- [ ] **Step 2: Run to confirm failure**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_akses_indikator_unit.NoAllIndicatorsOptionTest -v1`
Expected: FAIL on both.

- [ ] **Step 3: Auto-select the first indicator server-side**

In `akreditasi/views.py` at line 182, after `mutu_indikator_choices` is built, add:

```python
    # Spec 19.10: tidak ada pilihan "Semua Indikator". Halaman tanpa
    # parameter memakai indikator pertama dalam lingkup, jadi grafik tetap
    # tergambar dan bookmark lama (tanpa mutu_indikator) tetap hidup.
    if not mutu_indikator_id and mutu_indikator_choices:
        mutu_indikator_id = mutu_indikator_choices[0].pk
```

Keep `selected_indikator` resolution on the next line unchanged.

- [ ] **Step 4: Remove the option from both templates**

In `dashboard.html:489`, delete the line:

```html
                        <option value="">Semua Indikator (Rata-rata)</option>
```

In `indikator_dashboard.html:283`, delete the same option.

- [ ] **Step 5: Update the JS rebuild and the submit guard**

In `dashboard.html:968`, the rebuilt list must not re-introduce the option:

```js
            ind.innerHTML = '';
            (data.indikator || []).forEach(function (i) {
                const o = document.createElement('option');
                o.value = i.id;
                o.textContent = '[' + i.kode + '] ' + i.nama + (i.punya_data ? '' : ' — belum ada data');
                ind.appendChild(o);
            });
            // Spesifikasi 19.10 menghapus "Semua Indikator"; pilih yang
            // pertama agar grafik tetap tergambar setelah ganti kategori.
            if (data.indikator && data.indikator.length) {
                ind.value = data.indikator[0].id;
            }
```

Replace the submit guard at lines 981-986 — it can no longer disable a select that is always filled, and it must not silently submit an empty value:

```js
    // Tanpa "Semua Indikator", nilai kosong berarti pilihan belum terisi
    // (unit tanpa indikator). Cegah submit yang akan membuat grafik kosong
    // tanpa penjelasan.
    document.querySelector('form[method="GET"]')?.addEventListener('submit', function (e) {
        const ind = document.getElementById('filterMutuIndikator');
        if (ind && !ind.value) e.preventDefault();
    });
```

- [ ] **Step 6: Name the empty state**

Locate the existing "belum ada pengukuran" panel (around `dashboard.html:540-560`, added in `fda160e`) and give the zero-indicators case its own branch. Render, from the view context, a flag `mutu_unit_kosong = bool(profile and profile.is_unit_scoped and profile.unit_kerja and not mutu_indikator_choices)`, then:

```html
                        {% if mutu_unit_kosong %}
                        <div class="alert alert-info mb-0">
                            <i class="bi bi-info-circle me-1"></i>
                            Unit ini <strong>belum memiliki indikator mutu</strong> yang
                            ditugaskan. Hubungi Pokja Mutu untuk penetapan indikator IMRS,
                            IMU, atau INM untuk unit ini.
                        </div>
                        {% endif %}
```

- [ ] **Step 7: Run to confirm pass**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_akses_indikator_unit -v1`
Expected: `OK`.

- [ ] **Step 8: Check the rendered inline JS parses**

The template contains `{{ }}` inside `<script>`, so parse the blocks from a rendered response, not the template file:

```bash
.venv/Scripts/python.exe - <<'PY'
import os, re, sys, pathlib, tempfile
sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
U = get_user_model()
c = Client(); c.force_login(U.objects.filter(is_superuser=True).first())
body = c.get('/dashboard/').content.decode()
blocks = re.findall(r'<script[^>]*>(.*?)</script>', body, re.S)
out = pathlib.Path(tempfile.gettempdir()) / 'dash_blocks.js'
out.write_text('\n;\n'.join(blocks), encoding='utf-8')
print(out)
PY
node --check "$TEMP/dash_blocks.js" && echo "JS OK"
```

Expected: `JS OK`. A parse failure here is the failure mode that shipped `MIN85,0%` before — do not skip this step.

- [ ] **Step 9: Commit**

```bash
git add templates/akreditasi/dashboard.html templates/akreditasi/indikator_dashboard.html akreditasi/views.py akreditasi/tests_akses_indikator_unit.py
git commit -m "feat(dashboard): drop 'Semua Indikator' and name the empty-unit state"
```

---

### Task 5: Full regression

**Files:** none new.

- [ ] **Step 1: Run the indicator suites**

Run: `.venv/Scripts/python.exe manage.py test akreditasi -v1`
Expected: `OK`, and the failure list identical to baseline (zero failures as of 2026-10-19).

- [ ] **Step 2: Run the other two apps**

Run: `.venv/Scripts/python.exe manage.py test accounts pasien -v1`
Expected: `OK` — 22 and 63 tests respectively.

- [ ] **Step 3: System check**

Run: `.venv/Scripts/python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Tick every checkbox in this file and commit**

```bash
git add docs/superpowers/plans/2026-10-19-unit-relevance-indicator-filter.md
git commit -m "docs(plans): tick unit-relevance indicator filter plan"
```

---

## Review Focus

- **The escape hatch is the highest-blast-radius line in the plan.** Dropping `Q(jenis='NASIONAL')` without `HOSPITAL_WIDE_ROLES` hides the whole indicator menu from Pokja Mutu and surveyors, who are unit-attached but hospital-wide by duty. `test_hospital_wide_role_sees_everything` is the pin; run it before trusting any other green.
- **Walking upward changes visibility for every clinical unit, not just the empty ones.** A bangsal now sees its instalasi's IMP_RS rows. Confirm with the stakeholder that a child unit showing its parent's indicator is wanted — the spec's example implies yes, but the spec never states the rule for units that *do* own indicators.
- **Auto-selecting the first indicator makes the dropdown order load-bearing.** `order_by('jenis', 'kode_indikator')` decides which chart a bare `/dashboard/` draws. If that order is wrong for a unit head, the fix is the ordering, not a new default.
- **`api_indikator_komparasi_unit` may be intentionally cross-unit.** Its name says comparison; forcing the unit scope there could empty the table it exists to build. Read it before routing it through the resolver, and record the decision in the commit message either way.
- **187 units will see an empty state instead of 36 indicators.** That is the point of the spec, but it is also the change most likely to be reported as a regression. Ship the Task 4 wording in the same release as the Task 2 filter — never separately.
- **The JS submit guard now blocks instead of disabling.** A user on a unit with no indicators cannot submit the filter form at all. Verify the empty-state panel is visible without submitting, or the page becomes a dead end.
- **`mutu_unit` for non-unit-scoped users stays exact-match.** An admin picking a unit from the dropdown gets that unit only, not its subtree. If comparison across sibling units is expected, that is a separate decision and not covered here.
