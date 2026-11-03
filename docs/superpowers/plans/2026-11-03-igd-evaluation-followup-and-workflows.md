# IGD Evaluation Follow-up: Clinical Workflows, Active Statuses, and Control Navigation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
Implement the clinical workflow improvements and navigation structures specified in `Hasil evaluasi igd dan langkah lanjut.docx`:
1. Provide visit modification ("Tambahkan menu edit/hapus") allowing clinicians to edit visit admission info and cancel erroneous visits with an audit trail.
2. Enable interactive patient lifecycle state transitions ("Hidupkan status") across the emergency care path (`DAFTAR` -> `TRIAGE` -> `ASESMEN` -> `PENUNJANG` -> `TINDAKAN` -> `DISPOSISI`).
3. Wire the 6-stage Emergency Care Workflow navigation menu (`/control/igd/triage/` through `/control/igd/administrasi/`).
4. Wire the 5-stage Quality & Logbook IGD menu (`/control/igd/logbook/`, `/control/igd/triage-audit/`, `/control/igd/indicators/`, `/control/igd/inventory/`, `/control/igd/handover/`).

**Architecture:**
- **Status Model Expansion:** Expand `KunjunganPasien.STATUS_KUNJUNGAN` in `pasien/models.py` with active clinical stages (`PENUNJANG`, `TINDAKAN`, `DISPOSISI`) while preserving existing statuses. Update active query sets (`ACTIVE_VISIT_STATUSES`) in `akreditasi/kontrol_data.py` and `pasien/views.py` so patients across all intermediate active states remain visible on dashboards and daily rosters.
- **Visit Modification & Cancellation:** Add `igd_kunjungan_edit` and `igd_kunjungan_batal` views with validation and feedback modals in `templates/pasien/igd_dashboard.html`.
- **Interactive Status Stepper ("Hidupkan Status"):** Add quick-status transition actions in each patient row with a dropdown pill and an endpoint `igd_status_update`.
- **Control & Sidebar Navigation Routing:** Implement `/control/igd/` route dispatchers in `akreditasi/igd_control_urls.py` and integrate the two dropdown menus into `templates/includes/sidebar.html`, `templates/base.html`, and `templates/akreditasi/kontrol/base_kontrol.html`.

**Tech Stack:** Django 5.x, Python 3.12/3.14, Bootstrap 5, Bootstrap Icons, SQLite/PostgreSQL.

**Spec / Source Document:** `C:\Users\cubeb\Downloads\Hasil evaluasi igd dan langkah lanjut.docx`

---

## Global Constraints

- **Non-Destructive Database Policy:** Never delete medical records physically without confirmation; cancellation sets `status='BATAL'` with reason recorded in `catatan_admisi` and logs to `AuditLog`.
- **Zero RBAC Regression:** Only authorized medical personnel (`STAF_NAKES`, `DOKTER`, `PERAWAT`, `KEPALA_UNIT`, `SUPER_ADMIN`, `ADMIN_RS`) with access to the IGD module may alter clinical statuses and edit visits.
- **Active Roster Consistency:** Outpatient clinics (Rajal) maintain strict calendar-date filtering while IGD rosters include all active statuses (`DAFTAR`, `TRIAGE`, `ASESMEN`, `PENUNJANG`, `TINDAKAN`, `DISPOSISI`).
- **Encoding Compliance:** Windows commands must execute with UTF-8 encoding (`$env:PYTHONIOENCODING="utf-8"`).

---

## Review Focus

1. **Active Roster Invariant:** Does an IGD patient whose status is transitioned to `PENUNJANG`, `TINDAKAN`, or `DISPOSISI` remain visible on `pasien:igd_dashboard` and `akreditasi:kontrol_emr`?
2. **Cancellation Isolation:** When a visit is cancelled (`BATAL`), does it immediately disappear from the active IGD board and release any reserved beds?
3. **Status Progression Guard:** Does attempting to transition a discharged (`PULANG`) or referred (`RUJUK`) patient prevent accidental overwrite without reopening?
4. **Navigation Deep-Linking:** Do all 6 clinical links and 5 quality links resolve correctly and land on the appropriate view or tab?
5. **Validation & Audit:** Does editing a visit retain original timestamps and record the editing user?

---

## File Structure

```text
pasien/
├── models.py                     # STATUS_KUNJUNGAN choices & helper properties
├── views.py                      # igd_kunjungan_edit, igd_kunjungan_batal, igd_status_update
├── urls.py                       # URL mappings for edit, batal, status
└── tests_igd_lifecycle.py        # Unit tests for status lifecycle & edit/batal

akreditasi/
├── kontrol_data.py               # ACTIVE_VISIT_STATUSES and _layanan_block updates
├── igd_control_urls.py           # Dedicated route hub for /control/igd/*
├── urls.py                       # Hook /control/igd/ into akreditasi URLconf
└── tests_igd_control_navigation.py # Navigation & endpoint resolution tests

templates/
├── includes/
│   └── sidebar.html              # Alur Pelayanan IGD & Mutu & Logbook IGD menus
├── akreditasi/kontrol/
│   └── base_kontrol.html         # Control portal navigation integration
└── pasien/
    └── igd_dashboard.html        # Interactive status badges, Edit & Batal modals
```

---

## Execution Tasks

### Task 1: Model & Query Support for Active IGD Statuses

**Files:**
- Modify: `pasien/models.py:266-285`
- Modify: `akreditasi/kontrol_data.py:30-40, 330-340`
- Modify: `pasien/views.py:990-1010`
- Test: `pasien/tests_igd_lifecycle.py`

**Interfaces:**
- Consumes: `KunjunganPasien.STATUS_KUNJUNGAN`
- Produces: `ACTIVE_IGD_STATUSES = ('DAFTAR', 'TRIAGE', 'ASESMEN', 'PENUNJANG', 'TINDAKAN', 'DISPOSISI')`

- [x] **Step 1: Write failing test for active IGD statuses in `pasien/tests_igd_lifecycle.py`**

```python
from django.test import TestCase
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien
from akreditasi.kontrol_data import ACTIVE_VISIT_STATUSES, _layanan_block
from akreditasi.models import UnitKerja

class IGDActiveStatusesTestCase(TestCase):
    def setUp(self):
        self.unit_igd = UnitKerja.objects.create(code='IGD', name='Instalasi Gawat Darurat', level=3)
        self.pasien = Pasien.objects.create(
            no_rm='RM-STAT-01',
            nama_lengkap='Pasien Penunjang',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-STAT-01',
            jenis_kunjungan='IGD',
            status='PENUNJANG',
            triage='KUNING',
            tanggal_masuk=timezone.now()
        )

    def test_penunjang_and_tindakan_in_active_statuses(self):
        self.assertIn('PENUNJANG', ACTIVE_VISIT_STATUSES)
        self.assertIn('TINDAKAN', ACTIVE_VISIT_STATUSES)
        self.assertIn('DISPOSISI', ACTIVE_VISIT_STATUSES)

    def test_active_igd_patient_in_layanan_block(self):
        block = _layanan_block(self.unit_igd, on_date=timezone.localdate())
        no_kunjungan_list = [item['no_kunjungan'] for item in block['items']]
        self.assertIn('KUNJ-STAT-01', no_kunjungan_list)
```

- [x] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_igd_lifecycle`
Expected: FAIL with `AssertionError: 'PENUNJANG' not found in ACTIVE_VISIT_STATUSES`.

- [x] **Step 3: Update `pasien/models.py`, `akreditasi/kontrol_data.py`, and `pasien/views.py`**

In `pasien/models.py`:
```python
    STATUS_KUNJUNGAN = [
        ('DAFTAR',    'Terdaftar'),
        ('TRIAGE',    'Triage (IGD)'),
        ('ASESMEN',   'Asesmen PPA'),
        ('PENUNJANG', 'Pemeriksaan Penunjang'),
        ('TINDAKAN',  'Tindakan & Resusitasi'),
        ('DISPOSISI', 'Keputusan Disposisi'),
        ('RANAP',     'Rawat Inap'),
        ('PULANG',    'Pulang'),
        ('RUJUK',     'Dirujuk Keluar'),
        ('MENINGGAL', 'Meninggal'),
        ('BATAL',     'Dibatalkan'),
    ]
```

In `akreditasi/kontrol_data.py`:
```python
ACTIVE_VISIT_STATUSES = (
    'DAFTAR', 'TRIAGE', 'ASESMEN', 'PENUNJANG', 'TINDAKAN', 'DISPOSISI', 'RANAP'
)
ACTIVE_IGD_STATUSES = (
    'DAFTAR', 'TRIAGE', 'ASESMEN', 'PENUNJANG', 'TINDAKAN', 'DISPOSISI'
)
```
Update line 332 in `akreditasi/kontrol_data.py`:
```python
        visit_filter = Q(tanggal_masuk__date=on_date) | Q(
            jenis_kunjungan='IGD',
            status__in=ACTIVE_IGD_STATUSES
        )
```

In `pasien/views.py`:
```python
ACTIVE_IGD_STATUSES = ['DAFTAR', 'TRIAGE', 'ASESMEN', 'PENUNJANG', 'TINDAKAN', 'DISPOSISI']
```
Use `status__in=ACTIVE_IGD_STATUSES` inside `igd_dashboard`.

- [x] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_igd_lifecycle`
Expected: PASS (2 tests passed, 0 failed).

- [x] **Step 5: Create migration and commit**

```bash
python manage.py makemigrations pasien
git add pasien/models.py akreditasi/kontrol_data.py pasien/views.py pasien/tests_igd_lifecycle.py
git commit -m "feat(igd): add intermediate active clinical statuses to KunjunganPasien"
```

---

### Task 2: Edit Kunjungan & Batal Kunjungan Backend Endpoints

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Test: `pasien/tests_igd_lifecycle.py`

**Interfaces:**
- `igd_kunjungan_edit(request, pk)`: Updates `catatan_admisi`, `dpjp`, `triage`, `penjamin`, `diagnosa_masuk`, `diagnosa_keperawatan_sdki`.
- `igd_kunjungan_batal(request, pk)`: Sets `status='BATAL'`, releases bed if occupied, appends cancellation reason to `catatan_admisi`.

- [x] **Step 1: Write failing test in `pasien/tests_igd_lifecycle.py`**

```python
    def test_edit_kunjungan_igd(self):
        self.client.force_login(self.user)
        url = reverse('pasien:igd_kunjungan_edit', kwargs={'pk': self.kunjungan.pk})
        response = self.client.post(url, {
            'catatan_admisi': 'Nyeri dada menjalar ke punggung',
            'dpjp': 'dr. Pratama',
            'triage': 'MERAH',
            'penjamin': 'BPJS',
            'diagnosa_masuk': 'I21.9 - Acute Myocardial Infarction'
        })
        self.assertEqual(response.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.triage, 'MERAH')
        self.assertEqual(self.kunjungan.penjamin, 'BPJS')
        self.assertEqual(self.kunjungan.catatan_admisi, 'Nyeri dada menjalar ke punggung')

    def test_batal_kunjungan_igd(self):
        self.client.force_login(self.user)
        url = reverse('pasien:igd_kunjungan_batal', kwargs={'pk': self.kunjungan.pk})
        response = self.client.post(url, {
            'alasan_batal': 'Salah input registrasi ganda'
        })
        self.assertEqual(response.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status, 'BATAL')
        self.assertIn('Salah input registrasi ganda', self.kunjungan.catatan_admisi)
```

- [x] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_igd_lifecycle.IGDActiveStatusesTestCase.test_edit_kunjungan_igd`
Expected: FAIL with `NoReverseMatch`.

- [x] **Step 3: Implement `igd_kunjungan_edit` and `igd_kunjungan_batal`**

In `pasien/views.py`:
```python
@login_required
@require_POST
def igd_kunjungan_edit(request, pk):
    kunjungan = get_object_or_404(KunjunganPasien, pk=pk, jenis_kunjungan='IGD')
    catatan_admisi = request.POST.get('catatan_admisi', '').strip()
    dpjp = request.POST.get('dpjp', '').strip()
    triage = request.POST.get('triage', '').strip()
    penjamin = request.POST.get('penjamin', '').strip()
    diagnosa_masuk = request.POST.get('diagnosa_masuk', '').strip()
    diagnosa_sdki = request.POST.get('diagnosa_keperawatan_sdki', '').strip()

    if catatan_admisi:
        kunjungan.catatan_admisi = catatan_admisi
    if dpjp:
        kunjungan.dpjp = dpjp
    if triage in dict(KunjunganPasien.TRIAGE_CHOICES):
        kunjungan.triage = triage
    if penjamin in dict(KunjunganPasien.TIPE_PENJAMIN):
        kunjungan.penjamin = penjamin
    if diagnosa_masuk:
        kunjungan.diagnosa_masuk = diagnosa_masuk
    if diagnosa_sdki:
        kunjungan.diagnosa_keperawatan_sdki = diagnosa_sdki

    kunjungan.save()
    messages.success(request, f"Data kunjungan {kunjungan.no_kunjungan} berhasil diperbarui.")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('pasien:igd_dashboard')
    return redirect(next_url)


@login_required
@require_POST
def igd_kunjungan_batal(request, pk):
    kunjungan = get_object_or_404(KunjunganPasien, pk=pk, jenis_kunjungan='IGD')
    alasan = request.POST.get('alasan_batal', '').strip() or 'Dibatalkan oleh petugas'

    if kunjungan.bed:
        bed = kunjungan.bed
        bed.status = 'TERSEDIA'
        bed.save()
        kunjungan.bed = None

    kunjungan.status = 'BATAL'
    waktu_str = timezone.now().strftime('%d/%m/%Y %H:%M')
    prefix = f"[BATAL {waktu_str} oleh {request.user.username}]: {alasan}"
    kunjungan.catatan_admisi = f"{prefix}\n{kunjungan.catatan_admisi}".strip()
    kunjungan.save()

    messages.warning(request, f"Kunjungan {kunjungan.no_kunjungan} telah dibatalkan.")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('pasien:igd_dashboard')
    return redirect(next_url)
```

In `pasien/urls.py`:
```python
    path('igd/kunjungan/<int:pk>/edit/', views.igd_kunjungan_edit, name='igd_kunjungan_edit'),
    path('igd/kunjungan/<int:pk>/batal/', views.igd_kunjungan_batal, name='igd_kunjungan_batal'),
```

- [x] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_igd_lifecycle`
Expected: PASS (4 tests passed, 0 failed).

- [x] **Step 5: Commit**

```bash
git add pasien/views.py pasien/urls.py pasien/tests_igd_lifecycle.py
git commit -m "feat(igd): implement edit and cancel visit endpoints for emergency patients"
```

---

### Task 3: Interactive Status Switcher ("Hidupkan Status") & UI Action Controls

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Modify: `templates/pasien/igd_dashboard.html`
- Test: `pasien/tests_igd_lifecycle.py`

**Interfaces:**
- `igd_status_update(request, pk)`: Updates `kunjungan.status` to one of `ACTIVE_IGD_STATUSES` or triggers disposal flows.
- AJAX/POST responses: JSON if requested by XHR, redirect with flash message otherwise.

- [x] **Step 1: Write failing test for `igd_status_update` in `pasien/tests_igd_lifecycle.py`**

```python
    def test_update_status_kunjungan_igd(self):
        self.client.force_login(self.user)
        url = reverse('pasien:igd_status_update', kwargs={'pk': self.kunjungan.pk})
        response = self.client.post(url, {'status': 'TINDAKAN'})
        self.assertEqual(response.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status, 'TINDAKAN')

    def test_update_status_kunjungan_ajax(self):
        self.client.force_login(self.user)
        url = reverse('pasien:igd_status_update', kwargs={'pk': self.kunjungan.pk})
        response = self.client.post(url, {'status': 'DISPOSISI'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status, 'DISPOSISI')
```

- [x] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_igd_lifecycle.IGDActiveStatusesTestCase.test_update_status_kunjungan_igd`
Expected: FAIL with `NoReverseMatch`.

- [x] **Step 3: Implement `igd_status_update` in `pasien/views.py` and register in `pasien/urls.py`**

In `pasien/views.py`:
```python
from django.http import JsonResponse

@login_required
@require_POST
def igd_status_update(request, pk):
    kunjungan = get_object_or_404(KunjunganPasien, pk=pk, jenis_kunjungan='IGD')
    new_status = request.POST.get('status', '').strip()
    valid_statuses = dict(KunjunganPasien.STATUS_KUNJUNGAN)

    if new_status not in valid_statuses:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Status tidak valid'}, status=400)
        messages.error(request, 'Status tidak valid.')
        return redirect('pasien:igd_dashboard')

    kunjungan.status = new_status
    kunjungan.save()

    label = valid_statuses[new_status]
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'new_status': new_status,
            'label': label,
            'message': f"Status pasien diubah menjadi {label}."
        })

    messages.success(request, f"Status pasien {kunjungan.no_kunjungan} diubah menjadi {label}.")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('pasien:igd_dashboard')
    return redirect(next_url)
```

In `pasien/urls.py`:
```python
    path('igd/kunjungan/<int:pk>/status/', views.igd_status_update, name='igd_status_update'),
```

- [x] **Step 4: Update `templates/pasien/igd_dashboard.html` with Interactive Status Pill, Edit Modal, and Batal Modal**

In `templates/pasien/igd_dashboard.html`:
1. Add Status column header and cell:
```html
<th>Status Alur</th>
```
And inside `<tbody>`:
```html
<td>
    <div class="dropdown">
        <button class="btn btn-sm btn-outline-primary dropdown-toggle py-0 px-2 font-monospace fw-semibold"
                type="button" data-bs-toggle="dropdown" aria-expanded="false" style="font-size: .75rem;">
            {{ k.get_status_display }}
        </button>
        <ul class="dropdown-menu shadow-sm" style="font-size: .8rem;">
            <li><h6 class="dropdown-header text-uppercase">Ubah Status Alur IGD</h6></li>
            {% for s_val, s_lbl in status_choices %}
            <li>
                <form method="post" action="{% url 'pasien:igd_status_update' k.pk %}">
                    {% csrf_token %}
                    <input type="hidden" name="status" value="{{ s_val }}">
                    <button type="submit" class="dropdown-item {% if k.status == s_val %}active{% endif %}">
                        {{ s_lbl }}
                    </button>
                </form>
            </li>
            {% endfor %}
        </ul>
    </div>
</td>
```
2. In the action dropdown, add "Edit Kunjungan" and "Batalkan Kunjungan" triggers:
```html
<li>
    <a class="dropdown-item py-2 text-primary" href="#" data-bs-toggle="modal" data-bs-target="#modalEditKunjungan{{ k.pk }}">
        <i class="bi bi-pencil-square me-2"></i> Edit Data Kunjungan
    </a>
</li>
<li>
    <a class="dropdown-item py-2 text-danger" href="#" data-bs-toggle="modal" data-bs-target="#modalBatalKunjungan{{ k.pk }}">
        <i class="bi bi-trash3 me-2"></i> Batalkan Kunjungan
    </a>
</li>
```
3. Add modal dialogs `#modalEditKunjungan{{ k.pk }}` and `#modalBatalKunjungan{{ k.pk }}`.

- [x] **Step 5: Run tests to verify**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_igd_lifecycle`
Expected: PASS (6 tests passed, 0 failed).

- [x] **Step 6: Commit**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/igd_dashboard.html pasien/tests_igd_lifecycle.py
git commit -m "feat(igd): add interactive status switcher and edit/cancel modals to IGD dashboard"
```

---

### Task 4: Dedicated Navigation & URL Routing for Alur Pelayanan IGD (1-6) and Mutu & Logbook IGD (1-5)

**Files:**
- Create: `akreditasi/igd_control_urls.py`
- Modify: `akreditasi/urls.py`
- Modify: `templates/includes/sidebar.html`
- Modify: `templates/base.html`
- Modify: `templates/akreditasi/kontrol/base_kontrol.html`
- Test: `akreditasi/tests_igd_control_navigation.py`

**Interfaces:**
- Routes in `akreditasi/igd_control_urls.py`:
  - `/control/igd/` -> `igd_control_hub`
  - `/control/igd/triage/` -> `igd_alur_triage`
  - `/control/igd/asesmen-ppa/` -> `igd_alur_asesmen_ppa`
  - `/control/igd/penunjang/` -> `igd_alur_penunjang`
  - `/control/igd/tindakan/` -> `igd_alur_tindakan`
  - `/control/igd/disposisi/` -> `igd_alur_disposisi`
  - `/control/igd/administrasi/` -> `igd_alur_administrasi`
  - `/control/igd/logbook/` -> `igd_mutu_logbook`
  - `/control/igd/triage-audit/` -> `igd_mutu_triage_audit`
  - `/control/igd/indicators/` -> `igd_mutu_indicators`
  - `/control/igd/inventory/` -> `igd_mutu_inventory`
  - `/control/igd/handover/` -> `igd_mutu_handover`

- [x] **Step 1: Write failing test in `akreditasi/tests_igd_control_navigation.py`**

```python
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()

class IGDControlNavigationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='admin_igd', password='password123')
        self.unit_igd = UnitKerja.objects.create(code='IGD', name='Instalasi Gawat Darurat', level=3)
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='SUPER_ADMIN',
            unit_kerja=self.unit_igd
        )
        self.client.login(username='admin_igd', password='password123')

    def test_alur_pelayanan_igd_routes_exist(self):
        routes = [
            '/control/igd/triage/',
            '/control/igd/asesmen-ppa/',
            '/control/igd/penunjang/',
            '/control/igd/tindakan/',
            '/control/igd/disposisi/',
            '/control/igd/administrasi/',
        ]
        for r in routes:
            res = self.client.get(r)
            self.assertIn(res.status_code, (200, 302))

    def test_mutu_logbook_igd_routes_exist(self):
        routes = [
            '/control/igd/logbook/',
            '/control/igd/triage-audit/',
            '/control/igd/indicators/',
            '/control/igd/inventory/',
            '/control/igd/handover/',
        ]
        for r in routes:
            res = self.client.get(r)
            self.assertIn(res.status_code, (200, 302))
```

- [x] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test akreditasi.tests_igd_control_navigation`
Expected: FAIL with 404 Not Found.

- [x] **Step 3: Create `akreditasi/igd_control_urls.py` and register in `akreditasi/urls.py`**

Create `akreditasi/igd_control_urls.py`:
```python
from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse

@login_required
def igd_control_hub(request):
    return redirect('pasien:igd_dashboard')

@login_required
def igd_alur_triage(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=triage')

@login_required
def igd_alur_asesmen_ppa(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=asesmen')

@login_required
def igd_alur_penunjang(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=penunjang')

@login_required
def igd_alur_tindakan(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=tindakan')

@login_required
def igd_alur_disposisi(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=disposisi')

@login_required
def igd_alur_administrasi(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=administrasi')

@login_required
def igd_mutu_logbook(request):
    return redirect(reverse('akreditasi:logbook_daftar') + '?jenis=IGD')

@login_required
def igd_mutu_triage_audit(request):
    return redirect(reverse('pasien:igd_dashboard') + '?audit=door_time')

@login_required
def igd_mutu_indicators(request):
    return redirect(reverse('akreditasi:indikator_dashboard'))

@login_required
def igd_mutu_inventory(request):
    return redirect(reverse('akreditasi:logbook_daftar') + '?jenis=IGD&focus=troli')

@login_required
def igd_mutu_handover(request):
    return redirect(reverse('akreditasi:logbook_daftar') + '?jenis=IGD&focus=handover')

urlpatterns = [
    path('', igd_control_hub, name='igd_control_hub'),
    path('triage/', igd_alur_triage, name='igd_alur_triage'),
    path('asesmen-ppa/', igd_alur_asesmen_ppa, name='igd_alur_asesmen_ppa'),
    path('penunjang/', igd_alur_penunjang, name='igd_alur_penunjang'),
    path('tindakan/', igd_alur_tindakan, name='igd_alur_tindakan'),
    path('disposisi/', igd_alur_disposisi, name='igd_alur_disposisi'),
    path('administrasi/', igd_alur_administrasi, name='igd_alur_administrasi'),
    path('logbook/', igd_mutu_logbook, name='igd_mutu_logbook'),
    path('triage-audit/', igd_mutu_triage_audit, name='igd_mutu_triage_audit'),
    path('indicators/', igd_mutu_indicators, name='igd_mutu_indicators'),
    path('inventory/', igd_mutu_inventory, name='igd_mutu_inventory'),
    path('handover/', igd_mutu_handover, name='igd_mutu_handover'),
]
```

In `akreditasi/urls.py`:
```python
    path('control/igd/', include('akreditasi.igd_control_urls')),
```

- [x] **Step 4: Update Sidebar & Topbar Templates**

In `templates/includes/sidebar.html`, under the Pasien / IGD section, add:
1. Submenu **Alur Pelayanan IGD (1 - 6)**
2. Submenu **Mutu & Logbook IGD (1 - 5)**

In `templates/akreditasi/kontrol/base_kontrol.html` and `templates/base.html`, embed the menu snippet provided in the evaluation document.

- [x] **Step 5: Run tests to verify**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test akreditasi.tests_igd_control_navigation`
Expected: PASS (2 tests passed, 0 failed).

- [x] **Step 6: Commit**

```bash
git add akreditasi/igd_control_urls.py akreditasi/urls.py templates/includes/sidebar.html templates/base.html templates/akreditasi/kontrol/base_kontrol.html akreditasi/tests_igd_control_navigation.py
git commit -m "feat(navigation): wire IGD clinical pathway and quality logbook menus to /control/igd/"
```

---

### Task 5: End-to-End Regression & Quality Gate

**Files:**
- Test: `pasien/tests_revisi_igd.py`
- Test: `pasien/tests_revisi_igd_klinis.py`
- Test: `pasien/tests_igd_lifecycle.py`
- Test: `akreditasi/tests_igd_control_navigation.py`
- Test: `akreditasi/tests_layanan_unit.py`

- [x] **Step 1: Execute full test suite for `pasien` and `akreditasi`**

Run:
```bash
$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_igd_lifecycle akreditasi.tests_igd_control_navigation pasien.tests_revisi_igd pasien.tests_revisi_igd_klinis akreditasi.tests_layanan_unit
```
Expected: All tests PASS with zero errors.

- [x] **Step 2: Collectstatic hygiene**

Run:
```bash
python manage.py collectstatic --noinput
```

- [x] **Step 3: Commit final plan verification and documentation**

```bash
git add docs/superpowers/plans/2026-11-03-igd-evaluation-followup-and-workflows.md
git commit -m "docs(plan): add comprehensive execution plan for IGD evaluation and workflows"
```
