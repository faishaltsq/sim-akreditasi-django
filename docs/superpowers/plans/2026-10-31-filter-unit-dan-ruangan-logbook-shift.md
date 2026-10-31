# Filter Unit Kerja dan Ruangan Logbook Shift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter the Unit Kerja and Ruangan dropdowns in the Shift Logbook creation form so that ward/unit heads and staff only see their own unit and its subordinate units (never ancestor directorates/installations), pre-fill the user's assigned unit automatically, and dynamically filter rooms by selected unit.

**Architecture:** 
1. Replace bidirectional `unit_scope_ids` in `akreditasi/logbook.py::_unit_pilihan` with descendant-only `unit_subtree_ids` from `akreditasi/indikator_views.py`, strictly excluding 2-level ancestor climbing for operational shift logbooks while retaining full hospital access for `SUPER_ADMIN`, `ADMIN_RS`, and `ROLE_LINGKUP_RS`.
2. Backfill `ruangan.unit_kerja` in `pasien.models.Ruangan` via data migration using canonical mapping `RUANGAN_UNIT_CODE` in `akreditasi/layanan_unit.py`.
3. Provide `default_unit_id` and room-to-unit mapping in `logbook_buat` context, render `selected` on the unit option, and add lightweight vanilla JavaScript in `logbook_form.html` for instant dependent filtering of the Ruangan dropdown on change and page load.
4. Enforce server-side cross-unit validation on POST so submitted `ruangan` must belong to the submitted `unit`.

**Tech Stack:** Django 5.x / 6.x, PostgreSQL / SQLite, Python 3.14, Vanilla JavaScript (ES6), Bootstrap 5.

**Spec:** `C:\Users\cubeb\Downloads\Difilter unitnya.docx`

---

## Global Constraints

- **Scope direction:** Shift logbooks are operational records for a unit shift; unit-scoped users (`KEPALA_UNIT`, `STAF_NAKES`) must NEVER create logbooks for parent installations (`IRIN`) or top-level directorates (`PELAKSANA-TEKNIS`).
- **Admin override:** `SUPER_ADMIN` and `ADMIN_RS` (and hospital-wide roles `KOORDINATOR_POKJA`, `ASESOR`) retain visibility of all active units.
- **Pre-fill behavior:** If user has an assigned `unit_kerja`, the Unit Kerja dropdown must default to that unit (`selected`).
- **Zero extra dependencies:** Dependent dropdown filtering must use native DOM events and dataset attributes (`data-unit`), without adding external libraries.
- **Data integrity:** Server-side validation must reject any mismatch between submitted `unit` and `ruangan`.

---

## Review Focus

1. **Ancestor leakage:** User assigned to `Bangsal Dewasa Non-Bedah` (level 3) must see `Bangsal Dewasa Non-Bedah` and its sub-rooms (`Ruang Perawatan Pria`, `Ruang Perawatan Wanita`), but must NOT see `IRIN` (level 2) or `Unsur Pelaksana Teknis` (level 1).
2. **Hospital-wide role preservation:** `ADMIN_RS` and `SUPER_ADMIN` must continue to see all 100+ hospital units.
3. **Empty unit assignment:** A user without an assigned unit must not trigger a crash (`NoneType` error) and should see an empty unit list or be cleanly blocked with a polite validation notice.
4. **Room isolation:** When `Bangsal Dewasa Non-Bedah` is selected, the room dropdown must only display `R-K1`, `R-K2`, `R-K3` (or unit-level option), never `IGD-01`, `VIP-A`, or `OK-01`.
5. **Tamper protection:** An attacker submitting a valid unit ID with an unrelated room ID from another unit via forged POST must have the room rejected or reset to null.

---

## File Structure

- Create: `pasien/migrations/0012_backfill_ruangan_unit_kerja.py`
- Modify: `pasien/management/commands/seed_pasien_data.py:15-42`
- Modify: `akreditasi/logbook.py:132-145, 265-315`
- Modify: `templates/akreditasi/logbook_form.html:38-66`
- Create: `akreditasi/tests/test_logbook_unit_filter.py`

---

### Task 1: Backfill `Ruangan.unit_kerja` in Database and Seeder

**Files:**
- Create: `pasien/migrations/0012_backfill_ruangan_unit_kerja.py`
- Modify: `pasien/management/commands/seed_pasien_data.py:15-42`
- Test: `akreditasi/tests/test_logbook_unit_filter.py`

**Interfaces:**
- Consumes: `akreditasi.layanan_unit.RUANGAN_UNIT_CODE`, `pasien.models.Ruangan`, `akreditasi.models.UnitKerja`
- Produces: Persistent `unit_kerja_id` FK on all `Ruangan` records.

- [ ] **Step 1: Write the failing test for Ruangan FK linkage**

Create `akreditasi/tests/test_logbook_unit_filter.py`:

```python
from django.test import TestCase
from pasien.models import Ruangan
from akreditasi.models import UnitKerja
from akreditasi.layanan_unit import RUANGAN_UNIT_CODE


class RuanganUnitKerjaLinkageTest(TestCase):
    def test_ruangan_linked_to_unit_kerja(self):
        """Every seeded Ruangan in RUANGAN_UNIT_CODE must have unit_kerja populated."""
        for kode, unit_code in RUANGAN_UNIT_CODE.items():
            unit = UnitKerja.objects.filter(code=unit_code).first()
            if not unit:
                continue
            r, _ = Ruangan.objects.get_or_create(
                kode=kode,
                defaults={'nama': kode, 'kelas': '1', 'jenis': 'RANAP'}
            )
            # Must be populated by migration or post-save logic
            self.assertIsNotNone(r.unit_kerja, f"Ruangan {kode} unit_kerja must not be None")
            self.assertEqual(r.unit_kerja.code, unit_code)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter.RuanganUnitKerjaLinkageTest --keepdb -v 1`
Expected: FAIL (`AssertionError: None is not None`)

- [ ] **Step 3: Create data migration to backfill `Ruangan.unit_kerja`**

Write `pasien/migrations/0012_backfill_ruangan_unit_kerja.py`:

```python
from django.db import migrations


def link_ruangan_to_unit_kerja(apps, schema_editor):
    Ruangan = apps.get_model('pasien', 'Ruangan')
    UnitKerja = apps.get_model('akreditasi', 'UnitKerja')

    RUANGAN_UNIT_CODE = {
        'R-K1': 'BANGSAL-DEWASA',
        'R-K2': 'BANGSAL-DEWASA',
        'R-K3': 'BANGSAL-DEWASA',
        'VIP-A': 'BANGSAL-VIP',
        'ICU-01': 'ICU',
        'IGD-01': 'IGD',
        'IGD-02': 'IGD',
        'OK-01': 'IBS',
    }

    unit_cache = {
        u.code: u for u in UnitKerja.objects.filter(code__in=list(RUANGAN_UNIT_CODE.values()))
    }

    for kode, unit_code in RUANGAN_UNIT_CODE.items():
        unit = unit_cache.get(unit_code)
        if unit:
            Ruangan.objects.filter(kode=kode).update(unit_kerja=unit)


def unlink_ruangan(apps, schema_editor):
    Ruangan = apps.get_model('pasien', 'Ruangan')
    Ruangan.objects.all().update(unit_kerja=None)


class Migration(migrations.Migration):
    dependencies = [
        ('pasien', '0011_kunjunganpasien_unit_kerja_ruangan_unit_kerja'),
        ('akreditasi', '0065_seed_master_katalog_rkk'),
    ]

    operations = [
        migrations.RunPython(link_ruangan_to_unit_kerja, unlink_ruangan),
    ]
```

- [ ] **Step 4: Update `seed_pasien_data.py` to set `unit_kerja` when creating rooms**

Patch `pasien/management/commands/seed_pasien_data.py`:

```python
        from akreditasi.layanan_unit import RUANGAN_UNIT_CODE
        from akreditasi.models import UnitKerja

        unit_cache = {
            u.code: u for u in UnitKerja.objects.filter(code__in=list(RUANGAN_UNIT_CODE.values()))
        }

        total_beds = 0
        for kode, nama, kelas, jenis, kap in ruangan_data:
            target_unit = unit_cache.get(RUANGAN_UNIT_CODE.get(kode))
            r, created = Ruangan.objects.get_or_create(
                kode=kode,
                defaults={
                    'nama': nama, 'kelas': kelas, 'jenis': jenis, 'kapasitas': kap,
                    'unit_kerja': target_unit,
                }
            )
            if not created and r.unit_kerja != target_unit and target_unit:
                r.unit_kerja = target_unit
                r.save(update_fields=['unit_kerja'])
```

- [ ] **Step 5: Apply migration and verify test passes**

Run:
```bash
.venv/Scripts/python manage.py migrate pasien
.venv/Scripts/python manage.py seed_pasien_data
.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter.RuanganUnitKerjaLinkageTest --keepdb -v 1
```
Expected: PASS

- [ ] **Step 6: Commit Task 1**

```bash
git add pasien/migrations/0012_backfill_ruangan_unit_kerja.py pasien/management/commands/seed_pasien_data.py akreditasi/tests/test_logbook_unit_filter.py
git commit -m "feat(pasien): backfill Ruangan unit_kerja foreign key from RUANGAN_UNIT_CODE"
```

---

### Task 2: Backend Unit Subtree Scoping & Context Pre-fill in `akreditasi/logbook.py`

**Files:**
- Modify: `akreditasi/logbook.py:132-145, 265-315`
- Test: `akreditasi/tests/test_logbook_unit_filter.py`

**Interfaces:**
- Consumes: `akreditasi.indikator_views.unit_subtree_ids`, `akreditasi.logbook._profil`, `request.user`
- Produces: `_unit_pilihan(user)` returning only user's unit + descendants (no ancestors); `logbook_buat` context containing `default_unit_id` and unit-filtered `ruangan_pilihan`.

- [ ] **Step 1: Write failing tests for `_unit_pilihan` ancestor exclusion and pre-selection**

Add to `akreditasi/tests/test_logbook_unit_filter.py`:

```python
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.logbook import _unit_pilihan


class UnitPilihanScopingTest(TestCase):
    def setUp(self):
        self.pelaksana = UnitKerja.objects.create(code='DIR-OPS', name='Direktorat Ops', level=1)
        self.irin = UnitKerja.objects.create(code='IRIN-TEST', name='Instalasi Rawat Inap', level=2, parent=self.pelaksana)
        self.bangsal = UnitKerja.objects.create(code='BANGSAL-D', name='Bangsal Dewasa', level=3, parent=self.irin)
        self.ruang_pria = UnitKerja.objects.create(code='R-PRIA', name='Ruang Pria', level=4, parent=self.bangsal)

        self.user_bangsal = User.objects.create_user('ka.bangsal', password='x')
        UserProfile.objects.update_or_create(user=self.user_bangsal, defaults={'role': 'KEPALA_UNIT', 'unit_kerja': self.bangsal})

        self.user_admin = User.objects.create_user('admin.test', password='x')
        UserProfile.objects.update_or_create(user=self.user_admin, defaults={'role': 'ADMIN_RS'})

    def test_unit_scoped_user_only_sees_subtree_no_ancestors(self):
        """User at Bangsal must see Bangsal and Ruang Pria, but NOT IRIN or Pelaksana Teknis."""
        units = _unit_pilihan(self.user_bangsal)
        unit_pks = set(units.values_list('pk', flat=True))

        self.assertIn(self.bangsal.pk, unit_pks)
        self.assertIn(self.ruang_pria.pk, unit_pks)
        self.assertNotIn(self.irin.pk, unit_pks, "Ancestor IRIN must not appear in unit_pilihan")
        self.assertNotIn(self.pelaksana.pk, unit_pks, "Ancestor Direktorat must not appear in unit_pilihan")

    def test_admin_sees_all_units(self):
        """Admin RS must see all active units including top level."""
        units = _unit_pilihan(self.user_admin)
        unit_pks = set(units.values_list('pk', flat=True))
        self.assertIn(self.pelaksana.pk, unit_pks)
        self.assertIn(self.irin.pk, unit_pks)
        self.assertIn(self.bangsal.pk, unit_pks)

    def test_logbook_buat_context_prefills_default_unit(self):
        """GET /logbook/buat/ passes default_unit_id equal to user's assigned unit."""
        self.client.force_login(self.user_bangsal)
        r = self.client.get(reverse('akreditasi:logbook_buat'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['default_unit_id'], self.bangsal.pk)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter.UnitPilihanScopingTest --keepdb -v 1`
Expected: FAIL (`AssertionError: Ancestor IRIN must not appear in unit_pilihan`)

- [ ] **Step 3: Modify `_unit_pilihan` and `logbook_buat` in `akreditasi/logbook.py`**

In `akreditasi/logbook.py`:
1. Import `unit_subtree_ids` from `akreditasi.indikator_views`:
```python
from .indikator_views import unit_subtree_ids
```
2. Refactor `_unit_pilihan`:
```python
def _unit_pilihan(user):
    """Unit kerja yang boleh dipilih saat membuat logbook.

    Untuk user tingkat unit (KEPALA_UNIT, STAF_NAKES), hanya menampilkan unit
    miliknya dan turunan ke bawah (subtree descendants), TIDAK menampilkan
    leluhur (ancestors seperti IRIN atau Pelaksana Teknis).
    Admin RS, Super Admin, dan role lingkup RS tetap melihat seluruh unit aktif.
    """
    qs = UnitKerja.objects.filter(is_active=True).order_by('level', 'name')
    if user.is_superuser:
        return qs
    p = _profil(user)
    if p is None:
        return qs.none()
    if p.role in ROLE_LINGKUP_RS:
        return qs
    if p.unit_kerja:
        allowed_ids = unit_subtree_ids(p.unit_kerja)
        return qs.filter(pk__in=allowed_ids)
    return qs.none()
```
3. Update `logbook_buat` view to determine `default_unit_id` and scope `ruangan_pilihan`:
```python
    unit_choices = _unit_pilihan(request.user)
    default_unit_id = None
    if p and p.unit_kerja and unit_choices.filter(pk=p.unit_kerja_id).exists():
        default_unit_id = p.unit_kerja_id
    elif unit_choices.exists():
        default_unit_id = unit_choices.first().pk

    # Filter ruangan pilihan to only rooms belonging to allowable units
    if request.user.is_superuser or (p and p.role in ROLE_LINGKUP_RS):
        ruangan_qs = Ruangan.objects.all().order_by('kode')
    elif p and p.unit_kerja:
        allowed_unit_ids = unit_subtree_ids(p.unit_kerja)
        ruangan_qs = Ruangan.objects.filter(unit_kerja_id__in=allowed_unit_ids).order_by('kode')
    else:
        ruangan_qs = Ruangan.objects.none()

    return render(request, 'akreditasi/logbook_form.html', {
        'jenis_pilihan': JENIS_CHOICES,
        'shift_pilihan': SHIFT_CHOICES,
        'unit_pilihan': unit_choices,
        'default_unit_id': default_unit_id,
        'ruangan_pilihan': ruangan_qs,
        'hari_ini': timezone.localdate(),
        'tanggal_awal': (timezone.localdate() - timedelta(days=1)).isoformat(),
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter.UnitPilihanScopingTest --keepdb -v 1`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add akreditasi/logbook.py akreditasi/tests/test_logbook_unit_filter.py
git commit -m "fix(logbook): scope unit_pilihan to unit subtree without ancestors and supply default_unit_id"
```

---

### Task 3: Template Pre-Selection & Dynamic Dependent Ruangan Filter

**Files:**
- Modify: `templates/akreditasi/logbook_form.html:38-67`
- Test: `akreditasi/tests/test_logbook_unit_filter.py`

**Interfaces:**
- Consumes: `unit_pilihan`, `default_unit_id`, `ruangan_pilihan` with `r.unit_kerja_id`
- Produces: HTML `<select id="id_unit">` with `selected` attribute on `default_unit_id`, `<select id="id_ruangan">` with `data-unit` attribute, and client-side JavaScript syncing room options when unit changes.

- [ ] **Step 1: Write template context & rendered output test**

Add to `akreditasi/tests/test_logbook_unit_filter.py`:

```python
class LogbookFormTemplateRenderTest(TestCase):
    def setUp(self):
        self.bangsal = UnitKerja.objects.create(code='BANGSAL-D', name='Bangsal Dewasa', level=3)
        self.r1 = Ruangan.objects.create(kode='R-K1', nama='Bangsal Mawar', kelas='1', jenis='RANAP', unit_kerja=self.bangsal)
        self.user = User.objects.create_user('ka.bangsal', password='x')
        UserProfile.objects.update_or_create(user=self.user, defaults={'role': 'KEPALA_UNIT', 'unit_kerja': self.bangsal})

    def test_rendered_form_has_preselected_unit_and_data_unit_attributes(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('akreditasi:logbook_buat'))
        self.assertEqual(r.status_code, 200)
        content = r.content.decode('utf-8')
        # Check pre-selected unit
        self.assertIn(f'value="{self.bangsal.pk}" selected', content)
        # Check data-unit on room option
        self.assertIn(f'data-unit="{self.bangsal.pk}"', content)
        # Check presence of client-side sync script
        self.assertIn('filterRuanganByUnit', content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter.LogbookFormTemplateRenderTest --keepdb -v 1`
Expected: FAIL

- [ ] **Step 3: Update `templates/akreditasi/logbook_form.html`**

Update lines 38-66 in `templates/akreditasi/logbook_form.html`:

```html
                        <div class="col-12 col-md-6">
                            <label class="form-label small mb-1" for="id_unit">Unit Kerja</label>
                            <select name="unit" id="id_unit" class="form-select form-select-sm" required>
                                {% for u in unit_pilihan %}
                                <option value="{{ u.pk }}" {% if u.pk == default_unit_id %}selected{% endif %}>{{ u.name }}</option>
                                {% empty %}
                                <option value="">— tidak ada unit dalam lingkup Anda —</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col-12">
                            <label class="form-label small mb-1" for="id_ruangan">Ruangan <span class="text-muted">(opsional, untuk logbook per bangsal)</span></label>
                            <select name="ruangan" id="id_ruangan" class="form-select form-select-sm">
                                <option value="" data-unit="">— tingkat unit (semua ruangan) —</option>
                                {% for r in ruangan_pilihan %}
                                <option value="{{ r.pk }}" data-unit="{{ r.unit_kerja_id|default:'' }}" {% if forloop.first and not forloop.last and not default_unit_id %}selected{% endif %}>{{ r }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
                </div>
                <div class="card-footer bg-transparent d-flex justify-content-between">
                    <a href="{% url 'akreditasi:logbook_daftar' %}" class="btn btn-sm btn-outline-secondary">Batal</a>
                    <button class="btn btn-sm btn-primary"><i class="bi bi-journal-plus me-1"></i> Buat Logbook</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function () {
    const unitSelect = document.getElementById('id_unit');
    const ruanganSelect = document.getElementById('id_ruangan');
    if (!unitSelect || !ruanganSelect) return;

    // Cache all initial options
    const allOptions = Array.from(ruanganSelect.querySelectorAll('option'));

    function filterRuanganByUnit() {
        const selectedUnit = unitSelect.value;
        const currentRuangan = ruanganSelect.value;
        let isCurrentStillValid = false;

        // Clear select
        ruanganSelect.innerHTML = '';

        allOptions.forEach(opt => {
            const optUnit = opt.getAttribute('data-unit');
            // Keep default option (data-unit empty) or matching unit
            if (!optUnit || optUnit === selectedUnit) {
                ruanganSelect.appendChild(opt);
                if (opt.value === currentRuangan && currentRuangan !== '') {
                    isCurrentStillValid = true;
                }
            }
        });

        if (isCurrentStillValid) {
            ruanganSelect.value = currentRuangan;
        } else {
            ruanganSelect.value = '';
        }
    }

    unitSelect.addEventListener('change', filterRuanganByUnit);
    // Initial run on page load
    filterRuanganByUnit();
});
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter.LogbookFormTemplateRenderTest --keepdb -v 1`
Expected: PASS

- [ ] **Step 5: Commit Task 3**

```bash
git add templates/akreditasi/logbook_form.html akreditasi/tests/test_logbook_unit_filter.py
git commit -m "feat(logbook): pre-select unit and add dynamic room dependent dropdown filtering"
```

---

### Task 4: Server-Side POST Validation for Unit-Ruangan Consistency

**Files:**
- Modify: `akreditasi/logbook.py:273-304`
- Test: `akreditasi/tests/test_logbook_unit_filter.py`

**Interfaces:**
- Consumes: `request.POST.get('unit')`, `request.POST.get('ruangan')`, `_unit_pilihan`
- Produces: Sanitized creation where `ruangan` is strictly validated to belong to `unit` (or within `unit_subtree_ids(unit)`).

- [ ] **Step 1: Write failing test for cross-unit room tampering**

Add to `akreditasi/tests/test_logbook_unit_filter.py`:

```python
class LogbookPostValidationTest(TestCase):
    def setUp(self):
        self.bangsal = UnitKerja.objects.create(code='BANGSAL-D', name='Bangsal Dewasa', level=3)
        self.igd = UnitKerja.objects.create(code='IGD', name='IGD', level=2)

        self.r_bangsal = Ruangan.objects.create(kode='R-K1', nama='Bangsal Mawar', kelas='1', jenis='RANAP', unit_kerja=self.bangsal)
        self.r_igd = Ruangan.objects.create(kode='IGD-01', nama='Triase IGD', kelas='IGD', jenis='IGD', unit_kerja=self.igd)

        self.user = User.objects.create_user('ka.bangsal', password='x')
        UserProfile.objects.update_or_create(user=self.user, defaults={'role': 'KEPALA_UNIT', 'unit_kerja': self.bangsal})

    def test_forged_room_from_different_unit_is_sanitized_or_rejected(self):
        """If user submits Bangsal Dewasa unit but injects IGD ruangan, room must not be linked."""
        self.client.force_login(self.user)
        r = self.client.post(reverse('akreditasi:logbook_buat'), {
            'jenis': 'RANAP',
            'shift': 'PAGI',
            'unit': self.bangsal.pk,
            'ruangan': self.r_igd.pk,  # Tampered room
            'tanggal': '2026-10-31',
        })
        self.assertEqual(r.status_code, 302)
        from akreditasi.logbook_models import LogbookHarian
        lb = LogbookHarian.objects.get(unit=self.bangsal, shift='PAGI')
        # Room must be sanitized to None because r_igd does not belong to self.bangsal
        self.assertIsNone(lb.ruangan, "Mismatched ruangan must be sanitized to None")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter.LogbookPostValidationTest --keepdb -v 1`
Expected: FAIL (`AssertionError: <Ruangan: [IGD-01] Triase IGD (IGD)> is not None`)

- [ ] **Step 3: Modify `logbook_buat` in `akreditasi/logbook.py` to validate room-to-unit assignment**

In `akreditasi/logbook.py:logbook_buat`:

```python
        unit = get_object_or_404(_unit_pilihan(request.user), pk=unit_id)
        ruangan = None
        if ruangan_id:
            candidate_room = Ruangan.objects.filter(pk=ruangan_id).first()
            if candidate_room:
                # Room must either have unit_kerja == unit, or be within unit subtree
                valid_unit_ids = unit_subtree_ids(unit)
                if candidate_room.unit_kerja_id in valid_unit_ids:
                    ruangan = candidate_room
                else:
                    # Mismatched room: ignore to prevent corrupted unit-room relationship
                    ruangan = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter.LogbookPostValidationTest --keepdb -v 1`
Expected: PASS

- [ ] **Step 5: Commit Task 4**

```bash
git add akreditasi/logbook.py akreditasi/tests/test_logbook_unit_filter.py
git commit -m "fix(logbook): sanitize mismatched ruangan when creating logbook shift"
```

---

### Task 5: Full Regression Testing & Production Deployment Verification

**Files:**
- Modify: `akreditasi/tests/test_logbook_unit_filter.py`
- Test: Full test suite for `akreditasi.tests_logbook_views` and `akreditasi.tests.test_logbook_unit_filter`

- [ ] **Step 1: Run comprehensive unit filter test suite**

Run:
```bash
.venv/Scripts/python manage.py test akreditasi.tests.test_logbook_unit_filter --keepdb -v 1
```
Expected: All tests pass (0 failed).

- [ ] **Step 2: Run existing logbook view test suite for regression**

Run:
```bash
.venv/Scripts/python manage.py test akreditasi.tests_logbook_views --keepdb -v 1
```
Expected: Ran 28 tests in ~90s, OK.

- [ ] **Step 3: Perform static code checks and git status audit**

Run:
```bash
git status -s
git diff --check
```
Expected: Clean working tree, no syntax errors, no orphaned files.

- [ ] **Step 4: Push to GitHub master**

```bash
git push origin master
```

- [ ] **Step 5: Deploy to Vercel production and verify live deployment**

Run:
```bash
vercel --prod --yes
```
Verify live:
- Run browser test against `https://arima.web.id/logbook/buat/` with `ka.ranap` or audit DOM output using curl/CDP.
- Verify Unit Kerja options only include Bangsal and descendants, with Bangsal Dewasa Non-Bedah selected by default.
