# Unit-Scoped Patient Management & Clinical RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement department/unit-scoped access control and navigation filtering for the Patient Management (SIMRS) module, hiding non-relevant submenus (Pendaftaran, IGD, Poli Rawat Jalan) for Laboratory staff, introducing a dedicated Laboratory worklist & critical result tracking page, and automatically adapting available menus across all hospital units according to their clinical functions.

**Architecture:** Extend `UserProfile` in `accounts` with a property and permission evaluation engine for patient submodules (`can_access_pendaftaran`, `can_access_igd`, `can_access_rajal`, `can_access_ranap`, `can_access_farmasi`, `can_access_laboratorium`). Add a template context processor / helper tag to dynamically prune `sidebar.html` submenus under "Manajemen Pasien" based on the user's assigned `unit_kerja` and `profesi`. Implement the missing Laboratory & Diagnostic Order worklist view (`pasien/laboratorium/`) with critical value flag management, and apply unit-scoped decorators/guards in `pasien/views.py`.

**Tech Stack:** Django 5.x, Python 3.12, Bootstrap 5.3.3, SQLite / PostgreSQL, Django Test Framework.

**Spec:** Clinical RBAC & Unit Scoping Matrix based on Indonesian Ministry of Health SIMRS standards (Permenkes 24/2022 on Electronic Medical Records & STARKES KMK 1128/2022 standards for AP/PAP/SKP).

## Global Constraints
- Plans must always be written in English.
- DeepSeek API key or secrets must never be exposed to frontend/JS/browser.
- Patient medical records and identifiers must be sanitized in audit logs and views.
- Views must not throw HTTP 500 when queries hit unpopulated or missing relational fields; always guard with `try/except` and fallback defaults.
- Only one `+` symbol per menu sublevel in navigation templates.
- Preserve backward compatibility for `SUPER_ADMIN`, `ADMIN_RS`, and `DIREKTUR` (unrestricted global view).

## Review Focus
- A Laboratory staff user (`LAB-BDRS` or `ANALIS_LAB`) sees ONLY Laboratory Worklist, Master Pasien (lookup), and Riwayat Kunjungan — IGD, Rajal, Pendaftaran, and Bed Management must be hidden.
- Direct URL access to `/pasien/igd/`, `/pasien/pendaftaran/`, or `/pasien/rajal/` by a unit-scoped user without permission must return HTTP 403 Forbidden, not HTTP 200 or 500.
- Super Admin and Hospital Directors retain full unrestricted visibility across all 8+ submenus.
- Pharmacy staff (`FARM`, `DEPO-RAJAL`, `APOTEKER`) sees Farmasi & Dispensing, Master Pasien, and Riwayat Kunjungan.
- Emergency room staff (`IGD`, `DOKTER_UMUM`, `PERAWAT`) sees IGD Dashboard, Triage, Pendaftaran, Bed Reservation, and Riwayat Kunjungan.

---

### Task 1: Clinical Unit Access Resolver in `accounts/models.py`

**Files:**
- Modify: `accounts/models.py:170-220`
- Test: `accounts/tests_unit_rbac.py`

**Interfaces:**
- Consumes: `UserProfile.unit_kerja`, `UserProfile.role`, `UserProfile.profesi`, `UserProfile.is_unit_scoped`
- Produces: `UserProfile.get_allowed_patient_modules() -> set[str]` with keys: `'pendaftaran'`, `'igd'`, `'rajal'`, `'ranap'`, `'farmasi'`, `'laboratorium'`, `'master_pasien'`, `'riwayat'`

- [ ] **Step 1: Write failing test for unit-scoped module resolution**

```python
# accounts/tests_unit_rbac.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja

User = get_user_model()

class UnitPatientModuleRBACTest(TestCase):
    def setUp(self):
        self.unit_lab = UnitKerja.objects.create(code='LAB-BDRS', name='Instalasi Laboratorium', level=3)
        self.unit_farm = UnitKerja.objects.create(code='FARM', name='Instalasi Farmasi', level=3)
        self.unit_igd = UnitKerja.objects.create(code='IGD', name='Instalasi Gawat Darurat', level=3)

    def test_lab_user_allowed_modules(self):
        user = User.objects.create_user('analis1', 'analis@rs.id', 'pass123')
        profile = user.profile
        profile.role = 'STAF_NAKES'
        profile.profesi = 'ANALIS_LAB'
        profile.unit_kerja = self.unit_lab
        profile.save()

        allowed = profile.get_allowed_patient_modules()
        self.assertIn('laboratorium', allowed)
        self.assertIn('master_pasien', allowed)
        self.assertIn('riwayat', allowed)
        self.assertNotIn('igd', allowed)
        self.assertNotIn('rajal', allowed)
        self.assertNotIn('pendaftaran', allowed)
        self.assertNotIn('ranap', allowed)

    def test_superuser_allowed_all_modules(self):
        admin = User.objects.create_superuser('superadmin', 'admin@rs.id', 'pass123')
        allowed = admin.profile.get_allowed_patient_modules()
        for mod in ['pendaftaran', 'igd', 'rajal', 'ranap', 'farmasi', 'laboratorium', 'master_pasien', 'riwayat']:
            self.assertIn(mod, allowed)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test accounts.tests_unit_rbac -v2`
Expected: FAIL with `AttributeError: 'UserProfile' object has no attribute 'get_allowed_patient_modules'`

- [ ] **Step 3: Implement `get_allowed_patient_modules` in `UserProfile`**

```python
# accounts/models.py
def get_allowed_patient_modules(self) -> set:
    """
    Return set of allowed patient submodules for this user based on their role,
    assigned unit kerja, and clinical profession.
    """
    if self.user.is_superuser or self.role in ['SUPER_ADMIN', 'ADMIN_RS', 'DIREKTUR']:
        return {'pendaftaran', 'igd', 'rajal', 'ranap', 'farmasi', 'laboratorium', 'master_pasien', 'riwayat'}

    if not self.unit_kerja:
        # Default fallback for users without explicit unit
        return {'master_pasien', 'riwayat'}

    code = (self.unit_kerja.code or '').upper()
    parent_code = (self.unit_kerja.parent.code or '').upper() if self.unit_kerja.parent else ''
    all_codes = {code, parent_code}

    allowed = {'master_pasien', 'riwayat'}

    # 1. Laboratorium & Bank Darah
    if any('LAB' in c for c in all_codes) or self.profesi == 'ANALIS_LAB':
        allowed.add('laboratorium')
        return allowed

    # 2. Farmasi
    if any('FARM' in c or 'APOTEK' in c or 'DEPO' in c for c in all_codes) or self.profesi == 'APOTEKER':
        allowed.add('farmasi')
        return allowed

    # 3. IGD
    if any('IGD' in c for c in all_codes):
        allowed.update({'igd', 'pendaftaran', 'ranap'})
        return allowed

    # 4. Rawat Jalan (IRJ, Poliklinik)
    if any('IRJ' in c or 'POLI' in c for c in all_codes):
        allowed.update({'rajal', 'ranap'})
        return allowed

    # 5. Rawat Inap & ICU/HCU/VK
    if any('IRIN' in c or 'BANGSAL' in c or 'INTENSIF' in c or 'RUANG' in c for c in all_codes):
        allowed.update({'ranap'})
        return allowed

    # 6. Rekam Medis / Pendaftaran / Admisi
    if any('ADMISI' in c or 'PENDAFTARAN' in c or 'REKAM-MEDIS' in c for c in all_codes):
        allowed.update({'pendaftaran', 'master_pasien', 'riwayat', 'ranap'})
        return allowed

    return allowed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test accounts.tests_unit_rbac -v2`
Expected: PASS (2/2 tests OK)

- [ ] **Step 5: Commit**

```bash
git add accounts/models.py accounts/tests_unit_rbac.py
git commit -m "feat(rbac): implement get_allowed_patient_modules on UserProfile based on clinical unit"
```

---

### Task 2: Dedicated Laboratory & Diagnostic Worklist Module (`pasien/laboratorium/`)

**Files:**
- Create: `templates/pasien/laboratorium_dashboard.html`
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Test: `pasien/tests_laboratorium.py`

**Interfaces:**
- Consumes: `OrderPenunjang` where `jenis_pemeriksaan='LAB'`
- Produces: HTTP 200 view with laboratory order queue, critical value flag toggle, result verification action

- [ ] **Step 1: Write failing test for Laboratory dashboard view**

```python
# pasien/tests_laboratorium.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from akreditasi.models import UnitKerja
from pasien.models import Pasien, KunjunganPasien, OrderPenunjang

User = get_user_model()

class LaboratoriumViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.unit_lab = UnitKerja.objects.create(code='LAB-BDRS', name='Laboratorium', level=3)
        self.lab_user = User.objects.create_user('analis_test', 'analis@rs.id', 'pass123')
        self.lab_user.profile.role = 'STAF_NAKES'
        self.lab_user.profile.profesi = 'ANALIS_LAB'
        self.lab_user.profile.unit_kerja = self.unit_lab
        self.lab_user.profile.save()

        self.pasien = Pasien.objects.create(no_rm='RM-LAB-01', nama='Pasien Test Lab', jenis_kelamin='L')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, tipe_kunjungan='IGD', unit_tujuan=self.unit_lab, status='ASESMEN'
        )
        self.order = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan, jenis_pemeriksaan='LAB', nama_pemeriksaan='Darah Lengkap',
            catatan_klinis='Cek leukosit dan hemoglobin', is_critical_value=True
        )

    def test_laboratorium_dashboard_accessible_by_lab_staff(self):
        self.client.force_login(self.lab_user)
        resp = self.client.get(reverse('pasien:laboratorium_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Darah Lengkap')
        self.assertContains(resp, 'RM-LAB-01')

    def test_update_order_lab_status(self):
        self.client.force_login(self.lab_user)
        resp = self.client.post(
            reverse('pasien:order_penunjang_update', args=[self.order.pk]),
            {'status_order': 'SELESAI', 'hasil_teks': 'Hb 13.5 g/dL, Leukosit 8.200 /uL', 'is_critical_value': '0'}
        )
        self.assertEqual(resp.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status_order, 'SELESAI')
        self.assertFalse(self.order.is_critical_value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_laboratorium -v2`
Expected: FAIL with `NoReverseMatch: Reverse for 'laboratorium_dashboard' not found`

- [ ] **Step 3: Implement view, URLs, and template**

Add route in `pasien/urls.py`:
```python
path('laboratorium/', views.laboratorium_dashboard, name='laboratorium_dashboard'),
path('order-penunjang/<int:pk>/update/', views.order_penunjang_update, name='order_penunjang_update'),
```

Add views in `pasien/views.py`:
```python
@login_required
def laboratorium_dashboard(request):
    """Dashboard khusus Instalasi Laboratorium & Bank Darah."""
    orders = OrderPenunjang.objects.filter(
        jenis_pemeriksaan='LAB'
    ).select_related('kunjungan__pasien').order_by('-created_at')[:50]
    
    critical_orders = OrderPenunjang.objects.filter(
        jenis_pemeriksaan='LAB', is_critical_value=True
    ).exclude(status_order='SELESAI')

    return render(request, 'pasien/laboratorium_dashboard.html', {
        'orders': orders,
        'critical_orders': critical_orders,
        'total_pending': orders.filter(status_order='ORDER').count(),
        'total_proses': orders.filter(status_order='PROSES').count(),
        'total_selesai': orders.filter(status_order='SELESAI').count(),
    })

@login_required
def order_penunjang_update(request, pk):
    """Update status, hasil, dan flag critical value order penunjang."""
    order = get_object_or_404(OrderPenunjang, pk=pk)
    if request.method == 'POST':
        order.status_order = request.POST.get('status_order', order.status_order)
        order.hasil_teks = request.POST.get('hasil_teks', order.hasil_teks)
        order.is_critical_value = request.POST.get('is_critical_value') == '1'
        order.critical_value_catatan = request.POST.get('critical_value_catatan', '')
        order.save()
        messages.success(request, f'Order #{order.pk} berhasil diperbarui.')
    return redirect(request.META.get('HTTP_REFERER', 'pasien:laboratorium_dashboard'))
```

Create `templates/pasien/laboratorium_dashboard.html` with worklist table, critical value alert banner, and update modal.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_laboratorium -v2`
Expected: PASS (2/2 tests OK)

- [ ] **Step 5: Commit**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/laboratorium_dashboard.html pasien/tests_laboratorium.py
git commit -m "feat(lab): add dedicated laboratory worklist dashboard and result update action"
```

---

### Task 3: Sidebar Navigation Filtering by Unit Scoping

**Files:**
- Modify: `templates/includes/sidebar.html:286-347`
- Test: `accounts/tests_sidebar_visibility.py`

**Interfaces:**
- Consumes: `request.user.profile.get_allowed_patient_modules()`
- Produces: HTML rendering of only the allowed submenus under "Manajemen Pasien"

- [ ] **Step 1: Write failing test for sidebar template rendering**

```python
# accounts/tests_sidebar_visibility.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from akreditasi.models import UnitKerja

User = get_user_model()

class SidebarPatientVisibilityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.unit_lab = UnitKerja.objects.create(code='LAB-BDRS', name='Laboratorium', level=3)
        self.user_lab = User.objects.create_user('analis_vis', 'analis@rs.id', 'pass123')
        self.user_lab.profile.role = 'STAF_NAKES'
        self.user_lab.profile.profesi = 'ANALIS_LAB'
        self.user_lab.profile.unit_kerja = self.unit_lab
        self.user_lab.profile.save()

    def test_lab_sidebar_hides_pendaftaran_igd_rajal_and_shows_lab(self):
        self.client.force_login(self.user_lab)
        resp = self.client.get(reverse('akreditasi:dashboard'))
        self.assertEqual(resp.status_code, 200)
        # Must show Laboratorium
        self.assertContains(resp, 'Laboratorium & LIS')
        # Must NOT show irrelevant clinical dashboards
        self.assertNotContains(resp, 'Pendaftaran & Admisi')
        self.assertNotContains(resp, 'Gawat Darurat (IGD)')
        self.assertNotContains(resp, 'Poli Rawat Jalan')
        self.assertNotContains(resp, 'Rawat Inap & Bed')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test accounts.tests_sidebar_visibility -v2`
Expected: FAIL because sidebar currently renders all 8 menus hardcoded.

- [ ] **Step 3: Modify `templates/includes/sidebar.html`**

Update the "Manajemen Pasien" section:
```html
{% with allowed_mods=request.user.profile.get_allowed_patient_modules %}
    <!-- MANAJEMEN PASIEN (SIMRS) — disaring berdasarkan unit kerja & hak akses -->
    <div class="nav-section mt-2" style="border-top:1px solid #e2e8f0; padding-top:10px; margin-top:8px;">
        <i class="bi bi-people-fill me-1" style="font-size:0.6rem;"></i> Manajemen Pasien
    </div>
    
    {% if 'pendaftaran' in allowed_mods %}
    <a href="{% url 'pasien:pendaftaran_dashboard' %}" class="nav-link {% if request.resolver_match.url_name == 'pendaftaran_dashboard' %}active{% endif %}">
        <span class="nav-icon"><i class="bi bi-person-badge"></i></span>
        <span class="nav-text">
            <span class="nav-title">Pendaftaran &amp; Admisi</span>
            <span class="nav-desc">Loket &amp; Routing Pasien</span>
        </span>
    </a>
    {% endif %}

    {% if 'igd' in allowed_mods %}
    <a href="{% url 'pasien:igd_dashboard' %}" class="nav-link {% if request.resolver_match.url_name == 'igd_dashboard' %}active{% endif %}">
        <span class="nav-icon"><i class="bi bi-heart-pulse-fill text-danger"></i></span>
        <span class="nav-text">
            <span class="nav-title">Gawat Darurat (IGD)</span>
            <span class="nav-desc">Triage &amp; Disposisi</span>
        </span>
    </a>
    {% endif %}

    {% if 'rajal' in allowed_mods %}
    <a href="{% url 'pasien:rajal_dashboard' %}" class="nav-link {% if request.resolver_match.url_name == 'rajal_dashboard' %}active{% endif %}">
        <span class="nav-icon"><i class="bi bi-hospital-fill text-primary"></i></span>
        <span class="nav-text">
            <span class="nav-title">Poli Rawat Jalan</span>
            <span class="nav-desc">Antrean Spesialis</span>
        </span>
    </a>
    {% endif %}

    {% if 'ranap' in allowed_mods %}
    <a href="{% url 'pasien:bed_management' %}" class="nav-link {% if request.resolver_match.url_name == 'bed_management' %}active{% endif %}">
        <span class="nav-icon"><i class="bi bi-grid-3x3-gap-fill text-success"></i></span>
        <span class="nav-text">
            <span class="nav-title">Rawat Inap &amp; Bed</span>
            <span class="nav-desc">Ketersediaan &amp; BOR</span>
        </span>
    </a>
    {% endif %}

    {% if 'laboratorium' in allowed_mods %}
    <a href="{% url 'pasien:laboratorium_dashboard' %}" class="nav-link {% if request.resolver_match.url_name == 'laboratorium_dashboard' %}active{% endif %}">
        <span class="nav-icon"><i class="bi bi-moisture text-warning"></i></span>
        <span class="nav-text">
            <span class="nav-title">Laboratorium &amp; LIS</span>
            <span class="nav-desc">Order Penunjang &amp; Nilai Kritis</span>
        </span>
    </a>
    {% endif %}

    {% if 'farmasi' in allowed_mods %}
    <a href="{% url 'pasien:farmasi_antrean' %}" class="nav-link {% if request.resolver_match.url_name == 'farmasi_antrean' %}active{% endif %}">
        <span class="nav-icon"><i class="bi bi-capsule"></i></span>
        <span class="nav-text">
            <span class="nav-title">Farmasi &amp; Dispensing</span>
            <span class="nav-desc">Antrean Resep Elektronik</span>
        </span>
    </a>
    {% endif %}

    {% if 'master_pasien' in allowed_mods %}
    <a href="{% url 'pasien:pasien_daftar' %}" class="nav-link {% if request.resolver_match.url_name == 'pasien_daftar' or request.resolver_match.url_name == 'pasien_baru' %}active{% endif %}">
        <span class="nav-icon"><i class="bi bi-person-lines-fill"></i></span>
        <span class="nav-text">
            <span class="nav-title">Master Pasien</span>
            <span class="nav-desc">Database Rekam Medis</span>
        </span>
    </a>
    {% endif %}

    {% if 'riwayat' in allowed_mods %}
    <a href="{% url 'pasien:kunjungan_daftar' %}" class="nav-link {% if request.resolver_match.url_name == 'kunjungan_daftar' or request.resolver_match.url_name == 'kunjungan_baru' %}active{% endif %}">
        <span class="nav-icon"><i class="bi bi-clipboard2-pulse"></i></span>
        <span class="nav-text">
            <span class="nav-title">Riwayat Kunjungan</span>
            <span class="nav-desc">Semua Pelayanan</span>
        </span>
    </a>
    {% endif %}
{% endwith %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test accounts.tests_sidebar_visibility -v2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/includes/sidebar.html accounts/tests_sidebar_visibility.py
git commit -m "feat(ui): adapt sidebar patient menus dynamically to user assigned clinical unit"
```

---

### Task 4: View-Level RBAC Enforcement Decorator for Patient Routes

**Files:**
- Create: `pasien/decorators.py`
- Modify: `pasien/views.py`
- Test: `pasien/tests_route_rbac.py`

**Interfaces:**
- Consumes: `@require_patient_module('igd')`, `@require_patient_module('rajal')`, etc.
- Produces: HTTP 403 response or redirect to dashboard if unauthorized

- [ ] **Step 1: Write failing test for direct URL protection**

```python
# pasien/tests_route_rbac.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from akreditasi.models import UnitKerja

User = get_user_model()

class PatientRouteRBACTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.unit_lab = UnitKerja.objects.create(code='LAB-BDRS', name='Laboratorium', level=3)
        self.user_lab = User.objects.create_user('analis_sec', 'analis@rs.id', 'pass123')
        self.user_lab.profile.role = 'STAF_NAKES'
        self.user_lab.profile.profesi = 'ANALIS_LAB'
        self.user_lab.profile.unit_kerja = self.unit_lab
        self.user_lab.profile.save()

    def test_lab_user_blocked_from_igd_and_rajal_views(self):
        self.client.force_login(self.user_lab)
        resp_igd = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(resp_igd.status_code, 403)

        resp_rajal = self.client.get(reverse('pasien:rajal_dashboard'))
        self.assertEqual(resp_rajal.status_code, 403)

        resp_pendaftaran = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(resp_pendaftaran.status_code, 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_route_rbac -v2`
Expected: FAIL (status 200 != 403)

- [ ] **Step 3: Implement `@require_patient_module` decorator and apply to views**

Create `pasien/decorators.py`:
```python
from functools import wraps
from django.core.exceptions import PermissionDenied

def require_patient_module(module_name):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.conf import settings
                from django.shortcuts import redirect
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
            
            allowed = request.user.profile.get_allowed_patient_modules()
            if module_name not in allowed:
                raise PermissionDenied(f"Akses ditolak: Unit kerja Anda tidak memiliki wewenang untuk modul {module_name}.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
```

Decorate views in `pasien/views.py`:
- `@require_patient_module('igd')` on `igd_dashboard`
- `@require_patient_module('rajal')` on `rajal_dashboard`
- `@require_patient_module('pendaftaran')` on `pendaftaran_dashboard`
- `@require_patient_module('ranap')` on `bed_management`
- `@require_patient_module('farmasi')` on `farmasi_antrean`
- `@require_patient_module('laboratorium')` on `laboratorium_dashboard`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_route_rbac -v2`
Expected: PASS (1/1 test OK)

- [ ] **Step 5: Commit**

```bash
git add pasien/decorators.py pasien/views.py pasien/tests_route_rbac.py
git commit -m "feat(security): enforce require_patient_module decorator on patient dashboard routes"
```

---

### Task 5: Full Regression Testing & Remote Deployment

**Files:**
- Test: all suites in `pasien` and `accounts`

- [ ] **Step 1: Run complete test suite**

Run: `.venv/Scripts/python.exe manage.py test pasien accounts akreditasi.tests_ai -v2`
Expected: All 30+ tests PASS

- [ ] **Step 2: Push changes to GitHub master**

```bash
git push origin master
```
Verify Vercel builds successfully.
