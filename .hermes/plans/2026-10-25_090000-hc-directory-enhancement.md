# Human Capital Directory Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Read `2026-10-25_090000-hc-staff-identity-roadmap.md` first for the source register, decisions X1–X10, and the measured environment facts. Task 1 depends on `2026-10-25_090000-staff-intake-v2.md` Task 4 and Task 7 having landed (`ProfilPribadiPegawai.foto_profil_versi` and `sdm:pegawai_avatar`). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Turn `sdm:pegawai_list` into the directory the source document describes — avatar, proper name display, contact chips, tenure, supervisor, dependent filters, live search, Excel/PDF export, and scoped bulk status change — without widening any caller's grant scope.

**Architecture:** `pegawai_list` stays one view but gains a small, explicit context builder and one shared queryset filter function so the HTML page, the Excel export, and the PDF export cannot disagree about what "the current filter" means. Avatars are fetched from the already-built `sdm:pegawai_avatar` route via `<img>` tags, never signed URLs inline, so a 25-row page costs 25 same-origin requests that the browser can cache. Live search is progressive enhancement over the existing GET form: with JavaScript off, the `Terapkan` button still works.

**Tech Stack:** Django 6.1.2, Django templates, Bootstrap 5.3.3, openpyxl 3.1.5, reportlab 5.0.1, vanilla JS in `static/js/`.

**Spec:** `C:/Users/cubeb/Downloads/input identitas karyawan.docx`, SHA-256 `60e0691b825244a07e93d0a39f8bc4220396a8ba0d21c3b323f55c00d7b4e803`, lines 51–70.

## Global constraints

Every task inherits the roadmap's Global constraints. In addition:

- Measured baseline: `Ran 291 tests … OK` for `python -m django test sdm`. This plan must not lower it.
- `PAGE_SIZE = 25` at `sdm/views.py:99`. Do not change it as a side effect; the export path must stream beyond one page and the test for that is Task 7.
- Run everything with `DJANGO_SETTINGS_MODULE=config.control_test_settings` and `.venv/Scripts/python.exe`.
- UI copy is Bahasa Indonesia and literal. Table headers, button labels, and empty states below are the exact strings to use.
- Every new read path goes through `visible_employees(user)` and `visible_units(user)`. No new query may use `Pegawai.objects.all()`.

## Review focus

1. A unit head whose grant covers a parent unit scrolling a page where every avatar request is denied — the page must degrade to initials, not to a wall of broken images.
2. A live-search keystroke stream hammering the server with a new full page render per character.
3. An export that silently returns only the 25 rows currently on screen.
4. A bulk status change applied to a row the operator can see but cannot manage.
5. A contact chip that reveals a personal phone number to a caller holding only `can_view_hc`.
6. The `Nomor` column rendering an em dash for every row, which is what the source complains about.

## File ownership

Modify existing:
- `sdm/views.py` (`pegawai_list`, plus two new export views)
- `templates/sdm/pegawai/list.html`
- `static/js/main.js` (live search) or a new `static/js/hc-directory.js`
- `sdm/tests/test_directory.py`
- `sdm/urls.py`

Create during implementation:
- `sdm/services/direktori.py` — `filter_directory_queryset`, `directory_rows`, `build_directory_export`
- `sdm/tests/test_directory_enhancement.py`
- `templates/sdm/pegawai/_avatar.html` (a small include used by both list and detail)

Do not create a second employee list view, a second filter implementation, or a new model. Every column in this plan is derived from data that already exists after the intake plan lands.

---

## Task 1: Avatar rendering with an initials fallback

**Files:**
- Create: `templates/sdm/pegawai/_avatar.html`
- Modify: `templates/sdm/pegawai/list.html:82-84`
- Modify: `templates/sdm/pegawai/detail.html` (header block)
- Modify: `sdm/views.py` (`pegawai_list` context, `pegawai_detail` context)
- Test: `sdm/tests/test_directory_enhancement.py` (create)

**Interfaces:**
- Consumes: `sdm:pegawai_avatar` (from the intake plan's Task 7), `ProfilPribadiPegawai.foto_profil_versi`.
- Produces: a `foto_url` attribute on each employee object in the list page context — `None` when no verified profile photo exists — and an `initials` attribute (max two characters, uppercase).

- [ ] **Step 1: Write the failing tests**

Create `sdm/tests/test_directory_enhancement.py`. The setUp copies `PegawaiDirectoryViewTests`' harness verbatim.

```python
"""Directory enhancement (avatar, columns, filters, export)."""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DokumenPegawai,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    ProfilPribadiPegawai,
    VersiDokumen,
)


class DirectoryEnhancementTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='EN-HC')
        self.child = UnitKerja.objects.create(
            name='Ruang Melati', code='EN-HC-RM', parent=self.root
        )
        self.other = UnitKerja.objects.create(name='Unit Rahasia', code='EN-OTHER')
        self.manager = self._user('en-manager')
        self.reader = self._user('en-reader', manage=False)
        self.with_photo = self._employee(
            'Pegawai Berfoto', 'EN-001', self.root, with_photo=True
        )
        self.without_photo = self._employee('Pegawai Biasa', 'EN-002', self.child)
        self.hidden = self._employee('Pegawai Rahasia', 'EN-900', self.other)

    def _user(self, username, *, manage=True):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        # Role permission is global per role; keep it enabled for ADMIN_RS and
        # vary authority with the per-user HcGrant below. Setting this to
        # ``manage`` would revoke the manager when the reader fixture is made.
        config.can_manage_hc_employees = True
        config.can_export_hc = True
        config.save(update_fields=[
            'can_view_hc', 'can_manage_hc_employees', 'can_export_hc', 'updated_at',
        ])
        # include_descendants is required: ``self.child`` is a descendant of
        # ``self.root`` and ``HcGrant.include_descendants`` defaults to False,
        # so without it ``self.without_photo`` (placed in the child unit) would
        # be invisible and every row lookup in this class would KeyError.
        HcGrant.objects.create(
            user=user, capability='can_view_hc', unit_kerja=self.root,
            include_descendants=True,
        )
        if manage:
            HcGrant.objects.create(
                user=user, capability='can_manage_hc_employees',
                unit_kerja=self.root, include_descendants=True,
            )
            HcGrant.objects.create(
                user=user, capability='can_export_hc',
                unit_kerja=self.root, include_descendants=True,
            )
        return user

    def _employee(self, name, number, unit, *, with_photo=False):
        employee = Pegawai.objects.create(
            nama_lengkap=name, nomor_pegawai=number,
            kategori='NON_PPA', profesi='Administrasi', status='AKTIF',
        )
        PenempatanPegawai.objects.create(
            pegawai=employee, unit_kerja=unit,
            tanggal_mulai=self.today - timedelta(days=400), alokasi_fte=1.00,
        )
        profile = ProfilPribadiPegawai.objects.create(
            employee=employee, nama_depan=name.split()[0],
            nama_belakang=' '.join(name.split()[1:]),
        )
        if with_photo:
            document = DokumenPegawai.objects.create(
                employee=employee, document_type='IDENTITY', jenis_berkas='FOTO',
                title='Pas Foto', sensitivity='personnel',
            )
            version = VersiDokumen.objects.create(
                document=document, version_number=1, original_filename='foto.jpg',
                storage_key=f'personnel/{employee.pk}/{uuid.uuid4().hex}.jpg',
                sha256='a' * 64, size_bytes=10, content_type='image/jpeg',
                status='VERIFIED', valid_until=self.today + timedelta(days=365),
            )
            profile.foto_profil_versi = version
            profile.save(update_fields=['foto_profil_versi'])
        return employee

    def test_rows_carry_photo_url_and_initials(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_list'))
        rows = {row.employee.pk: row for row in response.context['rows']}
        self.assertIsNotNone(rows[self.with_photo.pk].foto_url)
        self.assertIsNone(rows[self.without_photo.pk].foto_url)
        self.assertEqual(rows[self.without_photo.pk].initials, 'PB')

    def test_avatar_image_is_not_requested_for_employees_without_a_photo(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_list'))
        content = response.content.decode()
        self.assertIn(
            reverse('sdm:pegawai_avatar', kwargs={'employee_id': self.with_photo.pk}),
            content,
        )
        self.assertNotIn(
            reverse('sdm:pegawai_avatar', kwargs={'employee_id': self.without_photo.pk}),
            content,
        )

    def test_foreign_employee_never_appears(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_list'))
        ids = {row.employee.pk for row in response.context['rows']}
        self.assertIn(self.with_photo.pk, ids)
        self.assertNotIn(self.hidden.pk, ids)
```

- [ ] **Step 2: Run them to confirm they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement --verbosity 2
```

Expected: `KeyError: 'rows'` — the current view passes `page_obj`, not `rows`. That is the RED signal.

- [ ] **Step 3: Add the shared row builder**

Create `sdm/services/direktori.py`:

```python
"""Directory row projection shared by the HTML page and both exports."""

from django.db.models import Q
from django.utils import timezone

from sdm.models import DokumenPegawai, PenempatanPegawai, VersiDokumen


class DirectoryRow:
    """One rendered directory line. Not a model; built per request."""

    __slots__ = (
        'employee', 'placements', 'foto_url', 'initials', 'contact',
        'tenure_days', 'supervisor', 'nomor',
    )

    def __init__(self, employee):
        self.employee = employee
        self.placements = []
        self.foto_url = None
        self.initials = _initials(employee)
        self.contact = {'telepon': '', 'email': '', 'whatsapp': ''}
        self.tenure_days = None
        self.supervisor = None
        self.nomor = employee.nomor_pegawai or ''


def _initials(employee):
    profile = getattr(employee, 'profil_pribadi', None)
    first = (getattr(profile, 'nama_depan', '') or '').strip()
    last = (getattr(profile, 'nama_belakang', '') or '').strip()
    if not first and not last:
        parts = (employee.nama_lengkap or '').split()
        first = parts[0] if parts else ''
        last = parts[-1] if len(parts) > 1 else ''
    letters = f'{first[:1]}{last[:1]}'.strip().upper()
    return letters or '?'


def build_directory_rows(employees, *, user, today=None):
    """Attach placements, avatar URL, contact and tenure to each employee."""
    today = today or timezone.localdate()
    employee_ids = [employee.pk for employee in employees]
    rows = {employee.pk: DirectoryRow(employee) for employee in employees}

    placements = (
        PenempatanPegawai.objects.filter(
            pegawai_id__in=employee_ids, tanggal_mulai__lte=today,
        )
        .filter(Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=today))
        .select_related('unit_kerja', 'unit_induk', 'atasan_langsung')
        .order_by('unit_kerja__level', 'unit_kerja__code')
    )
    for placement in placements:
        row = rows.get(placement.pegawai_id)
        if row is None:
            continue
        row.placements.append(placement)
        if row.supervisor is None and placement.atasan_langsung_id:
            row.supervisor = placement.atasan_langsung

    photo_versions = (
        VersiDokumen.objects.filter(
            profil_foto_utama__employee_id__in=employee_ids,
            status='VERIFIED',
            document__sensitivity='personnel',
        )
        .select_related('document')
        .values('pk', 'document__employee_id')
    )
    from django.urls import reverse

    for entry in photo_versions:
        row = rows.get(entry['document__employee_id'])
        if row is not None and row.foto_url is None:
            row.foto_url = reverse(
                'sdm:pegawai_avatar',
                kwargs={'employee_id': entry['document__employee_id']},
            )

    can_see_contact = _can_see_contact(user)
    for row in rows.values():
        profile = getattr(row.employee, 'profil_pribadi', None)
        if (
            row.employee.akun_id == user.pk
            or (can_see_contact and _manages(user, row.employee))
        ):
            telepon = (getattr(profile, 'telepon', '') or '').strip()
            row.contact = {
                'telepon': telepon,
                'whatsapp': _to_wa_number(telepon),
                'email': (getattr(profile, 'email_terverifikasi', '') or '').strip(),
            }
        tmt = (
            row.employee.riwayat_kepegawaian
            .order_by('-tanggal_tmt')
            .values_list('tanggal_tmt', flat=True)
            .first()
        )
        if tmt:
            row.tenure_days = (today - tmt).days
    return list(rows.values())


def _to_wa_number(telepon):
    digits = ''.join(ch for ch in (telepon or '') if ch.isdigit())
    if not digits:
        return ''
    if digits.startswith('0'):
        return '62' + digits[1:]
    if digits.startswith('62'):
        return digits
    return '62' + digits


def _manages(user, employee):
    """True when the caller holds a management grant covering this employee."""
    from django.core.exceptions import PermissionDenied

    from sdm.akses import require_hc_capability

    try:
        require_hc_capability(user, 'can_manage_hc_employees', employee=employee)
    except PermissionDenied:
        return False
    return True


def _can_see_contact(user):
    """Cheap pre-check: does the caller hold any management grant at all?

    Per-employee authority is still decided by ``_manages`` — a caller with a
    grant on one child unit must not see contact details for a parent-scoped
    employee they can merely view.
    """
    from django.core.exceptions import PermissionDenied

    from sdm.akses import require_hc_capability

    try:
        require_hc_capability(user, 'can_manage_hc_employees')
    except PermissionDenied:
        return False
    return True
```

- [ ] **Step 4: Build the row list in the view**

In `sdm/views.py`, replace the block from `page_obj = Paginator(queryset, PAGE_SIZE)...` through `page_obj.object_list = page_employees` in `pegawai_list` with:

```python
    page_obj = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get('page'))
    rows = build_directory_rows(
        list(page_obj.object_list.select_related('profil_pribadi')), user=request.user
    )
    rows.sort(key=lambda row: (row.employee.nama_lengkap, str(row.employee.pk)))
```

and add `'rows': rows,` to the render context, keeping `page_obj` for the paginator controls. Import:

```python
from sdm.services.direktori import build_directory_rows
```

Note the double sort: the queryset is already ordered by `nama_lengkap, pk`, and the Python sort is stable over it, so pagination order and display order agree.

- [ ] **Step 5: Create the avatar include**

Create `templates/sdm/pegawai/_avatar.html`:

```django
{% comment %}
Renders a directory avatar. Expects `row` (a DirectoryRow).
Falls back to initials when no verified profile photo exists, so a page
never shows a broken image for an employee without one.
{% endcomment %}
{% if row.foto_url %}
<object data="{{ row.foto_url }}" type="image/jpeg" width="36" height="36"
        class="rounded-circle border object-fit-cover flex-shrink-0"
        style="width:36px;height:36px;object-fit:cover;overflow:hidden;" aria-hidden="true">
    <span class="rounded-circle border bg-light d-inline-flex align-items-center justify-content-center"
          style="width:36px;height:36px;">
        <small class="fw-semibold text-muted">{{ row.initials }}</small>
    </span>
</object>
{% else %}
<span class="rounded-circle border bg-light d-inline-flex align-items-center justify-content-center flex-shrink-0"
      style="width:36px;height:36px;" aria-hidden="true">
    <small class="fw-semibold text-muted">{{ row.initials }}</small>
</span>
{% endif %}
```

`aria-hidden="true"` is deliberate: the name is already adjacent in the same row, so the avatar must not be announced twice. The `<object>` fallback renders the initials when the authenticated image request returns 404/403 or the object cannot be decoded; this is what keeps a grant change or storage outage from producing broken-image icons.

- [ ] **Step 6: Render the avatar in the list**

In `templates/sdm/pegawai/list.html`, replace the employee-name cell:

```django
                        <td><a class="fw-semibold text-decoration-none" href="{% url 'sdm:pegawai_detail' employee.pk %}">{{ employee.nama_lengkap }}</a></td>
```

and change the row loop from `{% for employee in page_obj %}` to `{% for row in rows %}`, using `row.employee` everywhere the old template used `employee`. The employee cell becomes:

```django
                        <td>
                            <div class="d-flex align-items-center gap-2">
                                {% include "sdm/pegawai/_avatar.html" with row=row %}
                                <a class="fw-semibold text-decoration-none" href="{% url 'sdm:pegawai_detail' row.employee.pk %}">{{ row.employee.nama_lengkap }}</a>
                            </div>
                        </td>
```

- [ ] **Step 7: Render the avatar in the detail header**

In `templates/sdm/pegawai/detail.html`, wrap the `<h1>` block so the avatar sits to its left:

```django
            <div class="d-flex align-items-center gap-3">
                {% include "sdm/pegawai/_avatar.html" with row=row %}
                <div>
                    <h1 class="page-title h4 mt-2 mb-1">{{ employee.nama_lengkap }}</h1>
                    <p class="page-subtitle text-muted mb-0">{{ employee.get_kategori_display }} · {{ employee.profesi|default:"Profesi belum dicatat" }}</p>
                </div>
            </div>
```

and add `'row': build_directory_rows([employee], user=request.user)[0],` to the `pegawai_detail` render context.

- [ ] **Step 8: Run the tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement sdm.tests.test_directory --verbosity 2
```

Expected: `0 failed`. `test_directory`'s existing pagination test asserts on `page_obj`; it must still pass because `page_obj` remains in the context.

- [ ] **Step 9: Commit**

```bash
git add sdm/services/direktori.py sdm/views.py templates/sdm/pegawai/_avatar.html templates/sdm/pegawai/list.html templates/sdm/pegawai/detail.html sdm/tests/test_directory_enhancement.py
git commit -m "feat(hc): directory avatars with initials fallback"
```

---

## Task 2: Name display, Nomor column, and the FTE tooltip

Fixes the source's three table complaints (lines 56–59). Implements decisions X6 and X9.

**Files:**
- Modify: `sdm/models/pegawai.py` (`Pegawai.nama_tampil`)
- Modify: `templates/sdm/pegawai/list.html`
- Test: `sdm/tests/test_directory_enhancement.py` (add two methods)

**Interfaces:**
- Consumes: `ProfilPribadiPegawai.gelar_depan`, `gelar_belakang`, `nama_depan`, `nama_belakang`.
- Produces: `Pegawai.nama_tampil` — a property returning the composed display name, falling back to `nama_lengkap`.

- [ ] **Step 1: Write the failing tests**

```python
    def test_nama_tampil_composes_titles_without_mutating_stored_name(self):
        profile = self.without_photo.profil_pribadi
        profile.gelar_depan = 'dr.'
        profile.gelar_belakang = 'Sp.PD'
        profile.save(update_fields=['gelar_depan', 'gelar_belakang'])
        self.without_photo.refresh_from_db()
        self.assertEqual(self.without_photo.nama_tampil, 'dr. Pegawai Biasa, Sp.PD')
        self.assertEqual(self.without_photo.nama_lengkap, 'Pegawai Biasa')

    def test_nomor_column_is_hidden_when_every_row_is_blank(self):
        Pegawai.objects.filter(pk__in=[self.with_photo.pk, self.without_photo.pk]).update(
            nomor_pegawai=''
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_list'))
        self.assertFalse(response.context['show_nomor_column'])
        self.assertNotContains(response, '<th scope="col">Nomor</th>')
```

- [ ] **Step 2: Run them to confirm they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement --verbosity 2
```

Expected: `AttributeError: 'Pegawai' object has no attribute 'nama_tampil'`, and `KeyError: 'show_nomor_column'`.

- [ ] **Step 3: Add the display-name property**

In `sdm/models/pegawai.py`, inside `class Pegawai`, after `__str__`:

```python
    @property
    def nama_tampil(self):
        """Display name with titles, for print and directory use.

        Never writes back to ``nama_lengkap``: existing rows may contain names
        that a title-aware rewrite would corrupt, and a mononym has no last name
        to append a suffix to.
        """
        profile = getattr(self, 'profil_pribadi', None)
        if profile is None:
            return self.nama_lengkap
        base = ' '.join(
            part for part in (profile.nama_depan, profile.nama_belakang) if part
        ).strip()
        if not base:
            return self.nama_lengkap
        depan = (profile.gelar_depan or '').strip()
        belakang = (profile.gelar_belakang or '').strip()
        composed = f'{depan} {base}'.strip()
        if belakang:
            composed = f'{composed}, {belakang}'
        return composed
```

- [ ] **Step 4: Render the composed name and the conditional Nomor column**

In `sdm/views.py`, in `pegawai_list`, after `rows` is built, add:

```python
    show_nomor_column = any(row.nomor for row in rows)
```

and add `'show_nomor_column': show_nomor_column,` to the context.

In `templates/sdm/pegawai/list.html`, change the name anchor to use the composed name:

```django
                                <a class="fw-semibold text-decoration-none" href="{% url 'sdm:pegawai_detail' row.employee.pk %}">{{ row.employee.nama_tampil }}</a>
```

Wrap the Nomor header and cell in the flag:

```django
                        {% if show_nomor_column %}<th scope="col">Nomor</th>{% endif %}
```

```django
                        {% if show_nomor_column %}<td class="font-monospace small">{{ row.nomor|default:"—" }}</td>{% endif %}
```

and update the two `colspan` values in that table (the empty-state `colspan="7"` becomes `{% if show_nomor_column %}7{% else %}6{% endif %}`).

- [ ] **Step 5: Add the FTE tooltip**

Replace the placement badge line:

```django
                            <span class="badge bg-light text-dark border">{{ placement.unit_kerja.code }} · {{ placement.alokasi_fte }} FTE</span>
```

with:

```django
                            <span class="badge bg-light text-dark border"
                                  data-bs-toggle="tooltip" data-bs-placement="top"
                                  title="FTE (Full-Time Equivalent): 1,00 berarti satu beban kerja penuh. Nilai 0,50 berarti setengah beban kerja penuh.">{{ placement.unit_kerja.code }} · {{ placement.alokasi_fte }} FTE</span>
```

Add `tabindex="0"` to the badge. Its native `title` remains usable before
Task 4 lands; Task 4 enhances it with Bootstrap from
`static/js/hc-directory.js`. Do not add inline JavaScript here — `base.html`
enforces a strict CSP, and Task 4 owns the single external script block.

- [ ] **Step 6: Run the tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement sdm.tests.test_directory --verbosity 2
```

Expected: `0 failed`.

- [ ] **Step 7: Commit**

```bash
git add sdm/models/pegawai.py sdm/views.py templates/sdm/pegawai/list.html sdm/tests/test_directory_enhancement.py
git commit -m "feat(hc): composed display name, conditional number column and FTE tooltip"
```

---

## Task 3: Contact chips, tenure, and supervisor columns

Implements the source's "Penambahan Kolom" block (lines 60–64) and decision X7.

**Files:**
- Modify: `templates/sdm/pegawai/list.html`
- Modify: `sdm/views.py` (pass a `columns` dict)
- Test: `sdm/tests/test_directory_enhancement.py` (add four methods)

**Interfaces:**
- Consumes: `DirectoryRow.contact`, `.tenure_days`, `.supervisor` from Task 1.
- Produces: context key `columns` — a dict with `kontak`, `masa_kerja`, `atasan` booleans, each false when no row on the page has that data, so the table never grows an all-empty column.

- [ ] **Step 1: Write the failing tests**

```python
    def test_contact_chip_is_hidden_from_a_view_only_grant(self):
        profile = self.with_photo.profil_pribadi
        profile.telepon = '081234567890'
        profile.save(update_fields=['telepon'])
        self.client.force_login(self.reader)
        response = self.client.get(reverse('sdm:pegawai_list'))
        self.assertNotContains(response, '081234567890')
        self.assertNotContains(response, 'wa.me/6281234567890')

    def test_employee_can_see_contact_on_their_own_row(self):
        self.without_photo.akun = self.reader
        self.without_photo.save(update_fields=['akun'])
        profile = self.without_photo.profil_pribadi
        profile.telepon = '081255500011'
        profile.save(update_fields=['telepon'])
        self.client.force_login(self.reader)
        response = self.client.get(reverse('sdm:pegawai_list'))
        self.assertContains(response, 'wa.me/6281255500011')

    def test_contact_chip_is_shown_to_a_manager(self):
        profile = self.with_photo.profil_pribadi
        profile.telepon = '081234567890'
        profile.save(update_fields=['telepon'])
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_list'))
        self.assertContains(response, 'wa.me/6281234567890')

    def test_tenure_and_supervisor_render(self):
        from sdm.models import RiwayatKepegawaian
        RiwayatKepegawaian.objects.create(
            pegawai=self.without_photo, kategori_pegawai='TETAP',
            tanggal_tmt=self.today - timedelta(days=800),
        )
        PenempatanPegawai.objects.filter(pegawai=self.without_photo).update(
            atasan_langsung=self.with_photo
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_list'))
        rows = {row.employee.pk: row for row in response.context['rows']}
        self.assertEqual(rows[self.without_photo.pk].tenure_days, 800)
        self.assertEqual(rows[self.without_photo.pk].supervisor, self.with_photo)
        self.assertContains(response, 'Pegawai Berfoto')
```

- [ ] **Step 2: Run them to confirm they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement --verbosity 2
```

Expected: the contact tests fail because no template renders `wa.me`; the tenure test fails with `AssertionError: None != 800` only if the supervisor lookup works — if it raises `AttributeError: 'PenempatanPegawai' object has no attribute 'atasan_langsung'`, the intake plan's Task 5 has not landed and this task is BLOCKED until it does.

- [ ] **Step 3: Compute the column flags**

In `sdm/views.py`, in `pegawai_list`, after `show_nomor_column`:

```python
    columns = {
        'kontak': any(
            row.contact['telepon'] or row.contact['email'] for row in rows
        ),
        'masa_kerja': any(row.tenure_days is not None for row in rows),
        'atasan': any(row.supervisor is not None for row in rows),
    }
```

and add `'columns': columns,` to the context.

- [ ] **Step 4: Render the three columns**

In `templates/sdm/pegawai/list.html`, add these headers after the existing Profesi/Jabatan header:

```django
                        {% if columns.kontak %}<th scope="col">Kontak</th>{% endif %}
                        {% if columns.masa_kerja %}<th scope="col">Masa Kerja</th>{% endif %}
                        {% if columns.atasan %}<th scope="col">Atasan Langsung</th>{% endif %}
```

and these cells after the Profesi/Jabatan cell:

```django
                        {% if columns.kontak %}
                        <td class="text-nowrap">
                            {% if row.contact.whatsapp %}
                            <a class="btn btn-sm btn-outline-success py-0 px-1" href="https://wa.me/{{ row.contact.whatsapp }}" target="_blank" rel="noopener noreferrer" aria-label="WhatsApp {{ row.employee.nama_tampil }}" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>
                            {% endif %}
                            {% if row.contact.telepon %}
                            <a class="btn btn-sm btn-outline-secondary py-0 px-1" href="tel:{{ row.contact.telepon }}" aria-label="Telepon {{ row.employee.nama_tampil }}" title="Telepon"><i class="bi bi-telephone"></i></a>
                            {% endif %}
                            {% if row.contact.email %}
                            <a class="btn btn-sm btn-outline-secondary py-0 px-1" href="mailto:{{ row.contact.email }}" aria-label="Email {{ row.employee.nama_tampil }}" title="Email"><i class="bi bi-envelope"></i></a>
                            {% endif %}
                            {% if not row.contact.whatsapp and not row.contact.telepon and not row.contact.email %}<span class="text-muted">—</span>{% endif %}
                        </td>
                        {% endif %}
                        {% if columns.masa_kerja %}
                        <td class="text-nowrap small">{% if row.tenure_days is not None %}{{ row.tenure_days }} hari{% else %}<span class="text-muted">Belum dapat dihitung</span>{% endif %}</td>
                        {% endif %}
                        {% if columns.atasan %}
                        <td class="small">{% if row.supervisor %}{{ row.supervisor.nama_tampil }}{% else %}<span class="text-muted">—</span>{% endif %}</td>
                        {% endif %}
```

`rel="noopener noreferrer"` is required on the `wa.me` link: it opens a third-party page in a new tab.

- [ ] **Step 5: Run the tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement --verbosity 2
```

Expected: `0 failed`.

- [ ] **Step 6: Commit**

```bash
git add sdm/views.py templates/sdm/pegawai/list.html sdm/tests/test_directory_enhancement.py
git commit -m "feat(hc): directory contact chips, tenure and supervisor columns"
```

---

## Task 4: One filter function, dependent dropdowns, and live search

Implements the source's filter block (lines 65–67).

**Files:**
- Create: `sdm/services/direktori.py` addition — `filter_directory_queryset`
- Modify: `sdm/views.py` (`pegawai_list` filter section)
- Modify: `templates/sdm/pegawai/list.html` (filter form)
- Create: `static/js/hc-directory.js`
- Modify: `config/settings.py` only if `STATICFILES_DIRS` needs nothing — it already includes `BASE_DIR / 'static'`, so no change.
- Test: `sdm/tests/test_directory_enhancement.py` (add five methods)

**Interfaces:**
- Consumes: `visible_employees(user, unit=None)`, `visible_units(user)`.
- Produces: `filter_directory_queryset(user, params, *, capability='can_view_hc') -> tuple[QuerySet, dict]` where `params` is a `QueryDict` and the returned dict holds the normalised `q`, `unit`, `status`, `kategori`, `profesi` values actually applied. The list uses the default view scope; both exports pass `capability='can_export_hc'` so an export grant narrower than a view grant cannot leak the broader set.

- [ ] **Step 1: Write the failing tests**

```python
    def test_profession_options_follow_the_selected_unit(self):
        self.without_photo.profesi = 'Radiografer'
        self.without_photo.save(update_fields=['profesi'])
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:pegawai_list'), {'unit': str(self.child.pk)}
        )
        options = list(response.context['profession_options'])
        self.assertIn('Radiografer', options)
        self.assertNotIn('Administrasi', options)

    def test_search_matches_nomor_and_email(self):
        profile = self.with_photo.profil_pribadi
        profile.email_terverifikasi = 'cari.saya@example.com'
        profile.save(update_fields=['email_terverifikasi'])
        self.client.force_login(self.manager)
        by_nomor = self.client.get(reverse('sdm:pegawai_list'), {'q': 'EN-001'})
        self.assertEqual(len(by_nomor.context['rows']), 1)
        by_email = self.client.get(reverse('sdm:pegawai_list'), {'q': 'cari.saya'})
        self.assertEqual(len(by_email.context['rows']), 1)

    def test_search_does_not_disclose_other_employee_contact_to_viewer(self):
        profile = self.with_photo.profil_pribadi
        profile.email_terverifikasi = 'private-contact@example.com'
        profile.save(update_fields=['email_terverifikasi'])
        self.client.force_login(self.reader)
        response = self.client.get(
            reverse('sdm:pegawai_list'), {'q': 'private-contact'}
        )
        self.assertEqual(response.context['rows'], [])

    def test_search_allows_employee_to_find_their_own_contact(self):
        self.without_photo.akun = self.reader
        self.without_photo.save(update_fields=['akun'])
        profile = self.without_photo.profil_pribadi
        profile.email_terverifikasi = 'self-contact@example.com'
        profile.save(update_fields=['email_terverifikasi'])
        self.client.force_login(self.reader)
        response = self.client.get(
            reverse('sdm:pegawai_list'), {'q': 'self-contact'}
        )
        self.assertEqual(
            [row.employee.pk for row in response.context['rows']],
            [self.without_photo.pk],
        )

    def test_live_search_endpoint_respects_scope(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:pegawai_list'), {'q': 'Rahasia', 'format': 'rows'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['rows'], [])
```

- [ ] **Step 2: Run them to confirm they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement --verbosity 2
```

Expected: `KeyError: 'profession_options'` and `AssertionError` on the email search (the current filter searches only name, number, profession, and position).

- [ ] **Step 3: Extract the filter function**

Append to `sdm/services/direktori.py`:

```python
def filter_directory_queryset(user, params, *, capability='can_view_hc'):
    """Apply the directory filters once, for the page and both exports.

    Returns ``(queryset, applied)``. ``applied`` holds the normalised values
    so a template and an export cannot disagree about what was requested.
    """
    from django.db.models import Q

    from sdm.akses import visible_employees

    search_q = (params.get('q') or '').strip()[:100]
    unit_raw = (params.get('unit') or '').strip()
    status_raw = (params.get('status') or '').strip()
    kategori_raw = (params.get('kategori') or '').strip()
    profesi_raw = (params.get('profesi') or '').strip()[:120]

    queryset = visible_employees(
        user, capability=capability
    ).select_related('akun', 'profil_pribadi')

    if search_q:
        manageable_ids = visible_employees(
            user, capability='can_manage_hc_employees'
        ).values('pk')
        public_match = (
            Q(nama_lengkap__icontains=search_q)
            | Q(nomor_pegawai__icontains=search_q)
            | Q(profesi__icontains=search_q)
            | Q(jabatan__icontains=search_q)
        )
        contact_match = (
            Q(profil_pribadi__email_terverifikasi__icontains=search_q)
            | Q(profil_pribadi__telepon__icontains=search_q)
        ) & (Q(pk__in=manageable_ids) | Q(akun_id=user.pk))
        queryset = queryset.filter(public_match | contact_match)

    applied = {'q': search_q, 'unit': '', 'status': '', 'kategori': '', 'profesi': ''}

    if unit_raw:
        if not unit_raw.isdigit():
            queryset = queryset.none()
        else:
            scoped = visible_employees(
                user, unit=int(unit_raw), capability=capability
            )
            queryset = queryset.filter(pk__in=scoped.values('pk'))
            applied['unit'] = unit_raw

    if status_raw in ('AKTIF', 'NONAKTIF'):
        queryset = queryset.filter(status=status_raw)
        applied['status'] = status_raw

    if kategori_raw in ('PPA', 'NON_PPA'):
        queryset = queryset.filter(kategori=kategori_raw)
        applied['kategori'] = kategori_raw

    if profesi_raw:
        queryset = queryset.filter(profesi__iexact=profesi_raw)
        applied['profesi'] = profesi_raw

    return queryset.order_by('nama_lengkap', 'pk'), applied


def profession_options(user, unit_raw=''):
    """Distinct profession texts inside the caller's scope, optionally one unit."""
    from sdm.akses import visible_employees

    if unit_raw and unit_raw.isdigit():
        base = visible_employees(user, unit=int(unit_raw))
    else:
        base = visible_employees(user)
    return list(
        base.exclude(profesi='')
        .values_list('profesi', flat=True)
        .distinct()
        .order_by('profesi')
    )
```

- [ ] **Step 4: Use it in the view**

In `sdm/views.py`, replace the whole filter section of `pegawai_list` — from `search_q = request.GET.get('q', '')` through `profession_filter = request.GET.get('profesi', '')[:120]` and its `if` block — with:

```python
    queryset, applied = filter_directory_queryset(request.user, request.GET)
```

Then replace the corresponding entries in the render context with the `applied`
values (shown here as the dict body, without the surrounding
`context = {...}`):

```python
{
    'search_q': applied['q'],
    'selected_unit': applied['unit'],
    'selected_status': applied['status'],
    'selected_category': applied['kategori'],
    'profession_filter': applied['profesi'],
    'profession_options': profession_options(request.user, applied['unit']),
}
```

and import:

```python
from sdm.services.direktori import (
    build_directory_rows,
    filter_directory_queryset,
    profession_options,
)
```

- [ ] **Step 5: Replace the free-text profession filter with a dependent dropdown**

In `templates/sdm/pegawai/list.html`, replace the profesi input block:

```django
            <div class="col-6 col-md-2">
                <label class="form-label small fw-semibold" for="filter-profesi">Profesi</label>
                <input id="filter-profesi" class="form-control form-control-sm" name="profesi" value="{{ profession_filter }}" maxlength="120">
            </div>
```

with:

```django
            <div class="col-6 col-md-2">
                <label class="form-label small fw-semibold" for="filter-profesi">Profesi</label>
                <select id="filter-profesi" class="form-select form-select-sm" name="profesi">
                    <option value="">Semua profesi</option>
                    {% for option in profession_options %}
                    <option value="{{ option }}" {% if profession_filter == option %}selected{% endif %}>{{ option }}</option>
                    {% endfor %}
                </select>
            </div>
```

Add `data-hc-directory` to the form and `data-hc-unit` / `data-hc-profesi` markers to the two selects so the script finds them without brittle IDs:

```django
    <form method="get" class="card border shadow-sm mb-3" role="search" aria-label="Filter pegawai" data-hc-directory>
```

and on the unit select: `data-hc-unit`, on the profesi select: `data-hc-profesi`.

- [ ] **Step 6: Add progressive live search**

Create `static/js/hc-directory.js`:

```javascript
/**
 * Directory live search.
 *
 * Progressive enhancement only: with this file absent or blocked, the
 * "Terapkan" button submits the same GET form and produces the same page.
 */
(function () {
    'use strict';

    var form = document.querySelector('[data-hc-directory]');
    if (!form) return;

    var searchInput = form.querySelector('#filter-q');
    var unitSelect = form.querySelector('[data-hc-unit]');
    var professionSelect = form.querySelector('[data-hc-profesi]');
    if (!searchInput) return;

    var timer = null;
    var DEBOUNCE_MS = 400;

    function submitSoon() {
        window.clearTimeout(timer);
        timer = window.setTimeout(function () {
            form.requestSubmit
                ? form.requestSubmit()
                : form.submit();
        }, DEBOUNCE_MS);
    }

    searchInput.addEventListener('input', submitSoon);

    // A unit change refreshes the profession options server-side, so it must
    // submit immediately rather than wait for the debounce.
    if (unitSelect) {
        unitSelect.addEventListener('change', function () {
            if (professionSelect) professionSelect.value = '';
            form.requestSubmit ? form.requestSubmit() : form.submit();
        });
    }
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (node) {
        if (window.bootstrap && window.bootstrap.Tooltip) {
            new window.bootstrap.Tooltip(node);
        }
    });
})();
```

Load it from the list template without an inline script, so the page remains compatible with a strict CSP:

```django
{% block extra_js %}
<script src="{% static 'js/hc-directory.js' %}" defer></script>
{% endblock %}
```

and add `{% load static %}` at the top of `list.html` if it is not already there.

- [ ] **Step 7: Run the tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement sdm.tests.test_directory --verbosity 2
```

Expected: `0 failed`. `test_directory_search_and_pagination_stay_inside_grant_scope` and `test_directory_unit_filter_fails_closed_for_foreign_unit` must both stay green — they are the regression gate for this refactor.

- [ ] **Step 8: Collect static**

Run:

```bash
.venv/Scripts/python.exe manage.py collectstatic --no-input
```

Expected: `1 static file copied` (or similar) and `staticfiles/staticfiles.json` updated. The repository tracks `staticfiles/` deliberately for the Vercel build; commit the new hashed artifact together with the source file.

- [ ] **Step 9: Commit**

```bash
git add sdm/services/direktori.py sdm/views.py templates/sdm/pegawai/list.html static/js/hc-directory.js staticfiles/ sdm/tests/test_directory_enhancement.py
git commit -m "feat(hc): single directory filter, dependent profession dropdown and live search"
```

---

## Task 5: Excel and PDF export of the current filter

Implements the source's "Tombol Ekspor" (line 69).

**Files:**
- Modify: `sdm/services/direktori.py` (add `build_directory_xlsx`, `build_directory_pdf`)
- Modify: `sdm/views.py` (two export views)
- Modify: `sdm/urls.py`
- Modify: `templates/sdm/pegawai/list.html`
- Test: `sdm/tests/test_directory_enhancement.py` (add six methods)

**Interfaces:**
- Consumes: `filter_directory_queryset`, `build_directory_rows`.
- Produces routes `sdm:pegawai_export` at `pegawai/ekspor/` and `sdm:pegawai_export_pdf` at `pegawai/ekspor/pdf/`, both accepting the same query string as the list page.

- [ ] **Step 1: Write the failing tests**

```python
    def test_excel_export_contains_every_scoped_row_not_just_one_page(self):
        import openpyxl
        from io import BytesIO
        for index in range(30):
            self._employee(f'Pegawai Massal {index:02d}', f'EN-M{index:03d}', self.root)
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_export'))
        self.assertEqual(response.status_code, 200)
        workbook = openpyxl.load_workbook(BytesIO(response.content))
        sheet = workbook.active
        names = [row[0] for row in sheet.iter_rows(min_row=2, values_only=True)]
        self.assertEqual(len(names), 32)

    def test_excel_export_excludes_foreign_employees(self):
        import openpyxl
        from io import BytesIO
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_export'))
        workbook = openpyxl.load_workbook(BytesIO(response.content))
        sheet = workbook.active
        names = [row[0] for row in sheet.iter_rows(min_row=2, values_only=True)]
        self.assertNotIn('Pegawai Rahasia', names)

    def test_export_requires_export_capability(self):
        self.client.force_login(self.reader)
        response = self.client.get(reverse('sdm:pegawai_export'))
        self.assertEqual(response.status_code, 403)

    def test_export_uses_export_scope_not_broader_view_scope(self):
        import openpyxl
        from io import BytesIO
        HcGrant.objects.filter(
            user=self.manager, capability='can_export_hc'
        ).delete()
        HcGrant.objects.create(
            user=self.manager, capability='can_export_hc', unit_kerja=self.child
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_export'))
        workbook = openpyxl.load_workbook(BytesIO(response.content))
        names = [row[0] for row in workbook.active.iter_rows(
            min_row=2, values_only=True
        )]
        self.assertIn('Pegawai Biasa', names)
        self.assertNotIn('Pegawai Berfoto', names)
        self.assertNotIn('Pegawai Rahasia', names)

    def test_export_escapes_formula_injection(self):
        import openpyxl
        from io import BytesIO
        Pegawai.objects.filter(pk=self.with_photo.pk).update(
            nama_lengkap='=HYPERLINK("http://evil.example","klik")'
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_export'))
        workbook = openpyxl.load_workbook(BytesIO(response.content))
        values = [row[0] for row in workbook.active.iter_rows(min_row=2, values_only=True)]
        self.assertFalse(any(str(v).startswith('=') for v in values))

    def test_pdf_export_escapes_reportlab_markup(self):
        Pegawai.objects.filter(pk=self.with_photo.pk).update(
            nama_lengkap='R&D <Ops>'
        )
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:pegawai_export_pdf'), {'q': 'R&D'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
```

- [ ] **Step 2: Run them to confirm they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement --verbosity 2
```

Expected: `NoReverseMatch: 'pegawai_export'`.

- [ ] **Step 3: Build both payloads**

Append to `sdm/services/direktori.py`:

```python
def _escape(value):
    """Neutralise spreadsheet formula injection in an exported cell."""
    text = '' if value is None else str(value)
    if text[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + text
    return text


def build_directory_xlsx(rows, *, applied):
    from io import BytesIO

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Direktori Pegawai'
    sheet.append([
        'Nama', 'Nomor', 'Profesi', 'Jabatan', 'Unit', 'Sub-Unit', 'FTE',
        'Atasan Langsung', 'Masa Kerja (hari)', 'Status', 'Kategori',
    ])
    for row in rows:
        primary = row.placements[0] if row.placements else None
        sheet.append([
            _escape(row.employee.nama_tampil),
            _escape(row.nomor),
            _escape(row.employee.profesi),
            _escape(row.employee.jabatan),
            _escape(primary.unit_kerja.code if primary else ''),
            _escape(
                primary.unit_kerja.name
                if primary and primary.unit_induk_id else ''
            ),
            float(primary.alokasi_fte) if primary else None,
            _escape(row.supervisor.nama_tampil if row.supervisor else ''),
            row.tenure_days,
            _escape(row.employee.get_status_display()),
            _escape(row.employee.get_kategori_display()),
        ])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_directory_pdf(rows, *, applied, generated_at=None):
    from io import BytesIO
    from xml.sax.saxutils import escape as xml_escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    generated_at = generated_at or timezone.now()
    styles = getSampleStyleSheet()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    filters = ', '.join(
        f'{key}={value}' for key, value in applied.items() if value
    ) or 'tanpa filter'
    pdf_text = lambda value: xml_escape('' if value is None else str(value))
    story = [
        Paragraph('Direktori Pegawai — Arima Human Capital', styles['Title']),
        Paragraph(
            f'Digenerate: {generated_at:%d %B %Y %H:%M} WIB · '
            f'{pdf_text(filters)} · {len(rows)} pegawai',
            styles['Normal'],
        ),
        Spacer(1, 6 * mm),
    ]
    data = [['Nama', 'Nomor', 'Profesi', 'Unit', 'FTE', 'Atasan', 'Status']]
    for row in rows:
        primary = row.placements[0] if row.placements else None
        data.append([
            Paragraph(pdf_text(row.employee.nama_tampil), styles['BodyText']),
            Paragraph(pdf_text(row.nomor or '—'), styles['BodyText']),
            Paragraph(pdf_text(row.employee.profesi or '—'), styles['BodyText']),
            Paragraph(
                pdf_text(primary.unit_kerja.code if primary else '—'),
                styles['BodyText'],
            ),
            f'{primary.alokasi_fte}' if primary else '—',
            Paragraph(
                pdf_text(row.supervisor.nama_tampil if row.supervisor else '—'),
                styles['BodyText'],
            ),
            Paragraph(
                pdf_text(row.employee.get_status_display()), styles['BodyText']
            ),
        ])
    table = Table(data, repeatRows=1, colWidths=[
        52 * mm, 26 * mm, 34 * mm, 24 * mm, 14 * mm, 46 * mm, 22 * mm,
    ])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
    ]))
    story.append(table)
    document.build(story)
    return buffer.getvalue()
```

- [ ] **Step 4: Add the two views**

In `sdm/views.py`, after `pegawai_list`:

```python
@login_required
def pegawai_export(request):
    require_hc_capability(request.user, 'can_export_hc')
    queryset, applied = filter_directory_queryset(
        request.user, request.GET, capability='can_export_hc'
    )
    rows = build_directory_rows(list(queryset), user=request.user)
    payload = build_directory_xlsx(rows, applied=applied)
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='hc_directory_exported',
        target_tipe='directory',
        target_id='pegawai',
        status_sesudah='EXPORTED',
        alasan='directory xlsx export',
    )
    response = HttpResponse(
        payload,
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
    )
    response['Content-Disposition'] = (
        f'attachment; filename="direktori-pegawai-{timezone.localdate():%Y%m%d}.xlsx"'
    )
    return response


@login_required
def pegawai_export_pdf(request):
    require_hc_capability(request.user, 'can_export_hc')
    queryset, applied = filter_directory_queryset(
        request.user, request.GET, capability='can_export_hc'
    )
    rows = build_directory_rows(list(queryset), user=request.user)
    payload = build_directory_pdf(rows, applied=applied)
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='hc_directory_exported',
        target_tipe='directory',
        target_id='pegawai',
        status_sesudah='EXPORTED',
        alasan='directory pdf export',
    )
    response = HttpResponse(payload, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="direktori-pegawai-{timezone.localdate():%Y%m%d}.pdf"'
    )
    return response
```

Import `build_directory_xlsx` and `build_directory_pdf` from `sdm.services.direktori`.

- [ ] **Step 5: Register the routes**

In `sdm/urls.py`, before the `pegawai/<uuid:employee_id>/` pattern:

```python
    path('pegawai/ekspor/', views.pegawai_export, name='pegawai_export'),
    path('pegawai/ekspor/pdf/', views.pegawai_export_pdf, name='pegawai_export_pdf'),
```

- [ ] **Step 6: Add the export buttons**

In `templates/sdm/pegawai/list.html`, in the `page-header-box` actions area, add a permission-gated group. The context needs the flag, so add `'can_export': visible_units(request.user, capability='can_export_hc').exists(),` to the `pegawai_list` context. Do not derive this from `granted_capabilities`: that navigation helper intentionally excludes global (`unit_kerja=NULL`) grants, while `require_hc_capability` and `visible_units` treat them as all-unit scope. Then:

```django
        {% if can_export %}
        <div class="d-flex gap-2">
            <a class="btn btn-outline-secondary btn-sm" href="{% url 'sdm:pegawai_export' %}?{{ pagination_query }}">
                <i class="bi bi-file-earmark-excel me-1"></i>Ekspor Excel
            </a>
            <a class="btn btn-outline-secondary btn-sm" href="{% url 'sdm:pegawai_export_pdf' %}?{{ pagination_query }}">
                <i class="bi bi-file-earmark-pdf me-1"></i>Ekspor PDF
            </a>
        </div>
        {% endif %}
```

`pagination_query` already carries the current filter without `page`, so the export matches what the operator is looking at.

- [ ] **Step 7: Run the tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement sdm.tests.test_directory sdm.tests.test_ekspor --verbosity 2
```

Expected: `0 failed`. `test_ekspor` covers the pre-existing compliance exports; this task adds a different export and must not change those.

- [ ] **Step 8: Commit**

```bash
git add sdm/services/direktori.py sdm/views.py sdm/urls.py templates/sdm/pegawai/list.html sdm/tests/test_directory_enhancement.py
git commit -m "feat(hc): filtered directory export to Excel and PDF"
```

---

## Task 6: Scoped bulk status change

Implements the source's "Aksi Massal" (line 70) under decision X8.

**Files:**
- Modify: `sdm/views.py` (add `pegawai_bulk_status`)
- Modify: `sdm/urls.py`
- Modify: `templates/sdm/pegawai/list.html` (checkbox column + bulk bar)
- Test: `sdm/tests/test_directory_enhancement.py` (add four methods)

**Interfaces:**
- Consumes: `visible_employees`, `require_hc_capability`, `PeristiwaSDM`.
- Produces route `sdm:pegawai_bulk_status` at `pegawai/aksi-massal/`, POST only, fields `employee_ids` (repeated) and `status` (`AKTIF`/`NONAKTIF`).

- [ ] **Step 1: Write the failing tests**

```python
    def test_bulk_status_updates_only_scoped_rows(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('sdm:pegawai_bulk_status'), {
            'employee_ids': [str(self.with_photo.pk), str(self.without_photo.pk),
                             str(self.hidden.pk)],
            'status': 'NONAKTIF',
        })
        self.assertEqual(response.status_code, 302)
        self.with_photo.refresh_from_db()
        self.without_photo.refresh_from_db()
        self.hidden.refresh_from_db()
        self.assertEqual(self.with_photo.status, 'NONAKTIF')
        self.assertEqual(self.without_photo.status, 'NONAKTIF')
        self.assertEqual(self.hidden.status, 'AKTIF')

    def test_bulk_status_requires_a_manage_grant(self):
        self.client.force_login(self.reader)
        response = self.client.post(reverse('sdm:pegawai_bulk_status'), {
            'employee_ids': [str(self.with_photo.pk)], 'status': 'NONAKTIF',
        })
        self.assertEqual(response.status_code, 403)
        self.with_photo.refresh_from_db()
        self.assertEqual(self.with_photo.status, 'AKTIF')

    def test_bulk_status_is_post_only(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_bulk_status'))
        self.assertEqual(response.status_code, 405)

    def test_bulk_status_writes_one_audit_row_per_employee(self):
        from sdm.models import PeristiwaSDM
        self.client.force_login(self.manager)
        self.client.post(reverse('sdm:pegawai_bulk_status'), {
            'employee_ids': [str(self.with_photo.pk), str(self.without_photo.pk)],
            'status': 'NONAKTIF',
        })
        self.assertEqual(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='employee_updated', actor=self.manager
            ).count(),
            2,
        )
```

- [ ] **Step 2: Run them to confirm they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement --verbosity 2
```

Expected: `NoReverseMatch: 'pegawai_bulk_status'`.

- [ ] **Step 3: Implement the view**

In `sdm/views.py`:

```python
@login_required
@require_POST
def pegawai_bulk_status(request):
    require_hc_capability(request.user, 'can_manage_hc_employees')
    raw_ids = request.POST.getlist('employee_ids')
    new_status = (request.POST.get('status') or '').strip()
    if new_status not in ('AKTIF', 'NONAKTIF'):
        messages.error(request, 'Status yang diminta tidak valid.')
        return redirect('sdm:pegawai_list')
    if not raw_ids:
        messages.warning(request, 'Tidak ada pegawai yang dipilih.')
        return redirect('sdm:pegawai_list')

    try:
        ids = [uuid.UUID(value) for value in raw_ids[:200]]
    except (TypeError, ValueError):
        messages.error(request, 'Daftar pegawai tidak valid.')
        return redirect('sdm:pegawai_list')

    updated = skipped = 0
    with transaction.atomic():
        scoped_employees = visible_employees(request.user).select_for_update()
        for employee in scoped_employees.filter(pk__in=ids):
            try:
                require_hc_capability(
                    request.user, 'can_manage_hc_employees', employee=employee
                )
            except PermissionDenied:
                skipped += 1
                continue
            if employee.status == new_status:
                continue
            old_status = employee.status
            employee.status = new_status
            employee.save(update_fields=['status', 'updated_at'])
            PeristiwaSDM.objects.create(
                actor=request.user,
                jenis_peristiwa='employee_updated',
                target_tipe='employee',
                target_id=str(employee.pk),
                status_sebelum=old_status,
                status_sesudah=new_status,
                alasan='Perubahan status massal dari direktori.',
            )
            updated += 1

    messages.success(
        request,
        f'{updated} pegawai diperbarui'
        + (f', {skipped} dilewati karena di luar lingkup.' if skipped else '.'),
    )
    return redirect('sdm:pegawai_list')
```

Add `import uuid` to `sdm/views.py`.

- [ ] **Step 4: Register the route**

In `sdm/urls.py`, before the `pegawai/<uuid:employee_id>/` pattern:

```python
    path('pegawai/aksi-massal/', views.pegawai_bulk_status, name='pegawai_bulk_status'),
```

- [ ] **Step 5: Add the checkbox column and bulk bar**

In `templates/sdm/pegawai/list.html`, add a header cell as the first column, gated on `can_create` (the existing manage proxy):

```django
                        {% if can_create %}<th scope="col" class="text-center"><span class="visually-hidden">Pilih</span></th>{% endif %}
```

and a matching first cell per row:

```django
                        {% if can_create %}<td class="text-center"><input class="form-check-input" type="checkbox" name="employee_ids" value="{{ row.employee.pk }}" form="bulk-status-form" aria-label="Pilih {{ row.employee.nama_tampil }}"></td>{% endif %}
```

Wrap the table in a form so the checkboxes submit, and add the bar above the table:

```django
    {% if can_create %}
    <form method="post" action="{% url 'sdm:pegawai_bulk_status' %}" id="bulk-status-form" class="card border shadow-sm mb-3">
        {% csrf_token %}
        <div class="card-body d-flex flex-wrap align-items-center gap-2">
            <span class="small text-muted me-2">Aksi massal untuk pegawai terpilih:</span>
            <select name="status" class="form-select form-select-sm w-auto" aria-label="Status tujuan">
                <option value="AKTIF">Aktifkan</option>
                <option value="NONAKTIF">Nonaktifkan</option>
            </select>
            <button class="btn btn-outline-primary btn-sm" type="submit">Terapkan</button>
        </div>
    </form>
    {% endif %}
```

Using `form="bulk-status-form"` on each checkbox keeps the checkboxes outside the form element while still submitting with it, so the table markup is not restructured.

- [ ] **Step 6: Run the tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement sdm.tests.test_directory --verbosity 2
```

Expected: `0 failed`. `test_view_only_grant_cannot_edit_employee` must stay green — it asserts the same capability this view requires.

- [ ] **Step 7: Commit**

```bash
git add sdm/views.py sdm/urls.py templates/sdm/pegawai/list.html sdm/tests/test_directory_enhancement.py
git commit -m "feat(hc): scoped bulk status change from the directory"
```

---

## Task 7: Full gate and responsive verification

**Files:**
- Modify: none
- Test: none new

**Interfaces:**
- Consumes: everything above.
- Produces: recorded evidence appended to `docs/qa/staff-intake-v2-verification.md`.

- [ ] **Step 1: Run the focused gate**

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_directory_enhancement sdm.tests.test_directory sdm.tests.test_ekspor sdm.tests.test_akses --verbosity 1
```

Expected: `0 failed`, exit code 0.

- [ ] **Step 2: Run the whole app suite**

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm --verbosity 1
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Expected: at least the 291 baseline, `0 failed`; `No changes detected` (this plan adds no model field beyond `nama_tampil`, which is a property); whitespace clean.

- [ ] **Step 3: Verify the responsive behaviour**

Measure the rendered list page at 1440×900, 768×1024, and 360×800. The requirement is: no horizontal page scroll at any width, the avatar column never collapses the name to an unreadable width, and the table scrolls inside its own `.table-responsive` wrapper rather than the page. Record the measured `document.documentElement.scrollWidth` against `clientWidth` for each viewport.

- [ ] **Step 4: Verify the degraded path**

Load the list page with `static/js/hc-directory.js` blocked. The `Terapkan` button must still submit and produce the same filtered page. Record the result.

- [ ] **Step 5: Append the evidence**

Add a section to `docs/qa/staff-intake-v2-verification.md` titled `## Directory enhancement` with the commands, outputs, viewport measurements, and the degraded-path result.

- [ ] **Step 6: Commit**

```bash
git add docs/qa/staff-intake-v2-verification.md
git commit -m "docs(hc): record directory enhancement verification"
```

---

## Definition of done

A manager opening `Human Capital → Direktori` sees a photo or initials per row, the composed name with titles, a Nomor column that appears only when numbers exist, an FTE badge that explains itself, contact chips for WhatsApp/phone/email, a tenure figure in days, and the direct supervisor — all inside their grant scope. Changing the unit filter narrows the profession dropdown. Typing in the search box refreshes the list after a 400 ms pause and still works with JavaScript disabled. Both export buttons download the full filtered set, not the visible page, with formula injection neutralised. Selecting rows and choosing a status updates exactly the rows the operator may manage, writes one audit row per change, and reports how many were skipped for being out of scope.
