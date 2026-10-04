# Clinical Workflow Dashboards: Pendaftaran, IGD, and Poli Rawat Jalan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build dedicated operational dashboards for Patient Registration (Pendaftaran), Emergency Department (IGD), and Outpatient Clinics (Poli Rawat Jalan) with seamless patient routing and one-click disposition workflows (Discharge vs. Inpatient Admission / Transfer to RANAP with bed assignment).

**Architecture:**
- **Pendaftaran Dashboard (`/pasien/pendaftaran/`)**: Front-office desk for quick patient search, registration, and immediate routing into IGD (with triage selection) or Poli Rawat Jalan (with clinic/specialty selection: Jantung, Paru, Penyakit Dalam, Anak, Bedah, Obgyn, Mata, Saraf).
- **IGD Dashboard (`/pasien/igd/`)**: Real-time triage board (Merah, Kuning, Hijau, Hitam) for emergency department staff. Each patient card/row provides quick disposition actions: (1) **Pulang (Discharge)** with modal resume and billing clearance, or (2) **Rawat Inap (Transfer to RANAP)** with interactive bed selection from available rooms.
- **Poli Rawat Jalan Dashboard (`/pasien/rajal/`)**: Clinic queue dashboard filterable by specialty (Poli Jantung, Paru, etc.). Each patient row provides quick disposition actions: (1) **Pulang (Selesai Pelayanan / Kontrol)**, or (2) **Rujuk Rawat Inap (SPRI / Admisi Ranap)** with bed selector.
- **Backend Disposition Endpoints**: Reusable view actions `kunjungan_disposisi_ranap` and `kunjungan_disposisi_pulang` ensuring transactional bed allocation, status transitions (`DAFTAR` -> `TRIAGE` / `ASESMEN` -> `RANAP` / `PULANG`), and audit logging.

**Tech Stack:** Django 5.2, PostgreSQL (Supabase) / SQLite, Bootstrap 5.3 + Bootstrap Icons, Vanilla JS modals.

---

## Global Constraints

- Must maintain strict data integrity with existing `KunjunganPasien`, `Bed`, `Ruangan`, `DischargeRecord`, and `BillingItem` models.
- When transferring to Inpatient (`RANAP`), an available `Bed` (`status='TERSEDIA'`) must be atomically locked and transitioned to `status='TERISI'`, linking `kunjungan.bed` and updating `kunjungan.jenis_kunjungan = 'RANAP'`.
- When discharging a patient (`PULANG`), if the patient occupied a bed, the bed status must change to `STERILISASI`.
- Sidebar navigation must cleanly surface these 3 operational dashboards under the SIMRS / Pasien navigation section.
- Responsive design: Dashboards must look pristine on desktop and clinic tablets.

---

### Task 1: Add Poliklinik Constants and Disposition Helper Methods to `pasien/models.py`

**Files:**
- Modify: `pasien/models.py`
- Test: `tests/test_pasien_workflow.py`

**Interfaces:**
- Produces: `POLIKLINIK_CHOICES` tuple list in `KunjunganPasien` (Poli Jantung, Paru, Penyakit Dalam, Anak, Bedah Umum, Kebidanan & Kandungan, Mata, Saraf, Gigi & Mulut, THT).
- Produces: Helper methods on `KunjunganPasien`:
  - `admit_to_ranap(bed, dpjp=None, catatan='')`: Validates bed availability, assigns bed, sets `jenis_kunjungan='RANAP'`, `status='RANAP'`.
  - `discharge_patient(kondisi, resume, user, tanggal=None)`: Creates or updates `DischargeRecord`, sets `status='PULANG'`, releases bed to `STERILISASI`.

- [ ] **Step 1: Write the failing unit test**

```python
# tests/test_pasien_workflow.py
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from pasien.models import Pasien, Ruangan, Bed, KunjunganPasien, DischargeRecord

class PasienWorkflowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('dokter1', 'doc@rs.com', 'pass123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-TEST-001',
            nama_lengkap='Budi Santoso',
            tanggal_lahir='1985-05-15',
            jenis_kelamin='L'
        )
        self.ruangan = Ruangan.objects.create(kode='R-VIP-01', nama='VIP Anggrek', kelas='VIP', jenis='RANAP', kapasitas=1)
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='B1', status='TERSEDIA')

    def test_igd_to_ranap_transfer(self):
        kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-IGD-001',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            triage='KUNING',
            status='TRIAGE'
        )
        kunjungan.admit_to_ranap(bed=self.bed, dpjp='dr. Hartono, Sp.JP')
        kunjungan.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(kunjungan.jenis_kunjungan, 'RANAP')
        self.assertEqual(kunjungan.status, 'RANAP')
        self.assertEqual(kunjungan.bed, self.bed)
        self.assertEqual(self.bed.status, 'TERISI')

    def test_rajal_discharge(self):
        kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-RAJAL-001',
            jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(),
            status='DAFTAR'
        )
        kunjungan.discharge_patient(kondisi='MEMBAIK', resume='Observasi stabil, kontrol 1 minggu lagi', user=self.user)
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'PULANG')
        self.assertTrue(DischargeRecord.objects.filter(kunjungan=kunjungan).exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py test tests.test_pasien_workflow`
Expected: `AttributeError: 'KunjunganPasien' object has no attribute 'admit_to_ranap'`

- [ ] **Step 3: Update `pasien/models.py` with constants and helper methods**

In `pasien/models.py`, define `POLIKLINIK_CHOICES`:

```python
POLIKLINIK_CHOICES = [
    ('POLI_JANTUNG', 'Poli Jantung & Pembuluh Darah'),
    ('POLI_PARU', 'Poli Paru & Respirasi'),
    ('POLI_PENYAKIT_DALAM', 'Poli Penyakit Dalam (Interna)'),
    ('POLI_ANAK', 'Poli Anak (Pediatri)'),
    ('POLI_BEDAH', 'Poli Bedah Umum'),
    ('POLI_OBGYN', 'Poli Kebidanan & Kandungan (Obgyn)'),
    ('POLI_MATA', 'Poli Mata'),
    ('POLI_SARAF', 'Poli Saraf (Neurologi)'),
    ('POLI_GIGI', 'Poli Gigi & Mulut'),
    ('POLI_THT', 'Poli THT-KL'),
    ('POLI_UMUM', 'Poli Umum'),
]
```

Add methods inside `KunjunganPasien`:

```python
    def admit_to_ranap(self, bed, dpjp=None, catatan=''):
        """Transfer/admit patient to Inpatient (RANAP) and lock the bed."""
        from django.db import transaction
        with transaction.atomic():
            if bed.status != 'TERSEDIA':
                raise ValueError(f"Bed {bed} sedang berstatus {bed.get_status_display()}, tidak dapat ditempati.")
            self.jenis_kunjungan = 'RANAP'
            self.status = 'RANAP'
            self.bed = bed
            if dpjp:
                self.dpjp = dpjp
            if catatan:
                self.catatan_admisi = f"{self.catatan_admisi}\n[Transfer Ranap] {catatan}".strip()
            self.save()
            bed.status = 'TERISI'
            bed.save()

    def discharge_patient(self, kondisi='MEMBAIK', resume='', user=None, tanggal=None, edukasi='', obat='', kontrol=None):
        """Discharge patient, release bed to sterilisation, and create DischargeRecord."""
        from django.utils import timezone
        from django.db import transaction
        with transaction.atomic():
            tgl = tanggal or timezone.now()
            self.status = 'PULANG'
            self.tanggal_keluar = tgl
            old_bed = self.bed
            self.bed = None
            self.save()
            if old_bed:
                old_bed.status = 'STERILISASI'
                old_bed.save()
            from .models import DischargeRecord
            total = sum(b.subtotal for b in self.billing.all())
            DischargeRecord.objects.update_or_create(
                kunjungan=self,
                defaults={
                    'tanggal_discharge': tgl,
                    'kondisi_pulang': kondisi,
                    'resume_medis': resume or 'Discharge pelayanan selesai.',
                    'edukasi_pulang': edukasi,
                    'obat_pulang': obat,
                    'jadwal_kontrol': kontrol,
                    'total_tagihan': total,
                    'status_clearance': 'CLEARANCE',
                    'dibuat_oleh': user,
                }
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py test tests.test_pasien_workflow`
Expected: `Ran 2 tests ... OK`

- [ ] **Step 5: Commit Task 1**

```bash
git add pasien/models.py tests/test_pasien_workflow.py
git commit -m "feat(pasien): add POLIKLINIK_CHOICES and admission/discharge helper methods"
```

---

### Task 2: Implement Registration Dashboard (`/pasien/pendaftaran/`) and Routing Views

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Create: `templates/pasien/pendaftaran_dashboard.html`

**Interfaces:**
- View: `pasien:pendaftaran_dashboard` (`/pasien/pendaftaran/`)
  - Summary KPI cards: Total Terdaftar Hari Ini, Pasien Baru, Menunggu Routing, Dikirim ke IGD, Dikirim ke Rajal.
  - Search / Quick Register Patient (NIK, No RM, Nama, Tgl Lahir, BPJS).
  - Fast Routing Form: Direct routing to IGD (with triage level selection) OR Poli Rawat Jalan (with clinic dropdown).
  - Live table of today's registrations with quick route buttons and status badges.
- View: `pasien:pendaftaran_route` (`POST /pasien/pendaftaran/<kunjungan_id>/route/`)
  - Handles routing form submissions: switches visit to IGD (status `TRIAGE`) or Rajal (status `DAFTAR`, assigns `poliklinik`).

- [ ] **Step 1: Write integration tests for registration dashboard and routing**

```python
# In tests/test_pasien_views.py
def test_pendaftaran_dashboard_loads(self):
    response = self.client.get('/pasien/pendaftaran/')
    self.assertEqual(response.status_code, 200)

def test_route_to_igd(self):
    k = KunjunganPasien.objects.create(pasien=self.pasien, no_kunjungan='KUNJ-TEST-REG', jenis_kunjungan='RAJAL', status='DAFTAR', tanggal_masuk=timezone.now())
    response = self.client.post(f'/pasien/pendaftaran/{k.pk}/route/', {'tujuan': 'IGD', 'triage': 'MERAH', 'dpjp': 'dr. Jaga IGD'})
    k.refresh_from_db()
    self.assertEqual(k.jenis_kunjungan, 'IGD')
    self.assertEqual(k.triage, 'MERAH')
    self.assertEqual(k.status, 'TRIAGE')

def test_route_to_rajal(self):
    k = KunjunganPasien.objects.create(pasien=self.pasien, no_kunjungan='KUNJ-TEST-REG2', jenis_kunjungan='RAJAL', status='DAFTAR', tanggal_masuk=timezone.now())
    response = self.client.post(f'/pasien/pendaftaran/{k.pk}/route/', {'tujuan': 'RAJAL', 'poliklinik': 'POLI_JANTUNG', 'dpjp': 'dr. Bambang, Sp.JP'})
    k.refresh_from_db()
    self.assertEqual(k.jenis_kunjungan, 'RAJAL')
    self.assertEqual(k.poliklinik, 'Poli Jantung & Pembuluh Darah')
```

- [ ] **Step 2: Add views `pendaftaran_dashboard` and `pendaftaran_route` in `pasien/views.py`**

```python
@login_required
def pendaftaran_dashboard(request):
    """Dedicated Front-Office Registration Desk."""
    today = timezone.localdate()
    kunjungan_hari_ini = KunjunganPasien.objects.filter(
        tanggal_masuk__date=today
    ).select_related('pasien', 'bed', 'created_by').order_by('-tanggal_masuk')

    # Metrics
    total_hari_ini = kunjungan_hari_ini.count()
    ke_igd = kunjungan_hari_ini.filter(jenis_kunjungan='IGD').count()
    ke_rajal = kunjungan_hari_ini.filter(jenis_kunjungan='RAJAL').count()
    ke_ranap = kunjungan_hari_ini.filter(jenis_kunjungan='RANAP').count()

    from .models import POLIKLINIK_CHOICES
    ctx = {
        'kunjungan_list': kunjungan_hari_ini[:50],
        'total_hari_ini': total_hari_ini,
        'ke_igd': ke_igd,
        'ke_rajal': ke_rajal,
        'ke_ranap': ke_ranap,
        'poliklinik_choices': POLIKLINIK_CHOICES,
        'triage_choices': KunjunganPasien.TRIAGE_CHOICES,
        'penjamin_choices': KunjunganPasien.TIPE_PENJAMIN,
        'pasien_recent': Pasien.objects.order_by('-created_at')[:10],
    }
    return render(request, 'pasien/pendaftaran_dashboard.html', ctx)


@login_required
def pendaftaran_route(request, pk):
    """Route a registered patient to IGD or Poli Rawat Jalan."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    if request.method == 'POST':
        tujuan = request.POST.get('tujuan')
        dpjp = request.POST.get('dpjp', '')
        if tujuan == 'IGD':
            k.jenis_kunjungan = 'IGD'
            k.triage = request.POST.get('triage', 'HIJAU')
            k.status = 'TRIAGE'
            if dpjp:
                k.dpjp = dpjp
            k.save()
            messages.success(request, f'Pasien {k.pasien.nama_lengkap} diarahkan ke IGD ({k.get_triage_display()}).')
            return redirect('pasien:igd_dashboard')
        elif tujuan == 'RAJAL':
            k.jenis_kunjungan = 'RAJAL'
            poli_key = request.POST.get('poliklinik', '')
            from .models import POLIKLINIK_CHOICES
            poli_dict = dict(POLIKLINIK_CHOICES)
            k.poliklinik = poli_dict.get(poli_key, poli_key)
            k.status = 'DAFTAR'
            if dpjp:
                k.dpjp = dpjp
            k.save()
            messages.success(request, f'Pasien {k.pasien.nama_lengkap} diarahkan ke {k.poliklinik}.')
            return redirect('pasien:rajal_dashboard')
    return redirect('pasien:pendaftaran_dashboard')
```

- [ ] **Step 3: Register URLs in `pasien/urls.py`**

```python
path('pendaftaran/', views.pendaftaran_dashboard, name='pendaftaran_dashboard'),
path('pendaftaran/<int:pk>/route/', views.pendaftaran_route, name='pendaftaran_route'),
```

- [ ] **Step 4: Create template `templates/pasien/pendaftaran_dashboard.html`**

Design full-featured registration dashboard:
- 4 Metric cards (Total Registrasi, Antrean IGD, Antrean Poli Spesialis, Rawat Inap).
- "Registrasi Kunjungan Baru" card with tabs: (A) Pasien Baru + Langsung Kunjungan, (B) Pasien Terdaftar.
- Radio buttons for Destination: **"1. IGD (Gawat Darurat)"** vs. **"2. Poli Rawat Jalan (Spesialis)"**.
- Dynamic toggle: selecting IGD shows Triage color picker (Merah/Kuning/Hijau/Hitam); selecting Rajal shows Poliklinik dropdown (Jantung, Paru, Penyakit Dalam, dll).
- Table of today's registrants with direct action modals to change route or view medical record.

- [ ] **Step 5: Run tests & verify**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py test tests.test_pasien_views`
Expected: `OK`

- [ ] **Step 6: Commit Task 2**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/pendaftaran_dashboard.html
git commit -m "feat(pendaftaran): add dedicated registration desk dashboard and clinical routing"
```

---

### Task 3: Implement Dedicated IGD Dashboard (`/pasien/igd/`) with Discharge vs. Ranap Actions

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Create: `templates/pasien/igd_dashboard.html`

**Interfaces:**
- View: `pasien:igd_dashboard` (`/pasien/igd/`)
  - Active emergency patients view (Status: `TRIAGE`, `ASESMEN`, `DAFTAR` where `jenis_kunjungan='IGD'`).
  - Triage breakdown tabs: Merah (P1 Resusitasi), Kuning (P2 Urgent), Hijau (P3 Non-Urgent), Hitam (P4).
  - Quick actions per patient:
    - **Pilihan 1: Pulang (Discharge / APS)** -> Modal inputting Kondisi Pulang, Resume Medis, Resep Pulang -> invokes `discharge_patient()`.
    - **Pilihan 2: Rawat Inap (Admisi RANAP)** -> Modal showing available beds grouped by Ruangan/Kelas -> invokes `admit_to_ranap()`.
- View: `pasien:kunjungan_disposisi` (`POST /pasien/kunjungan/<pk>/disposisi/`)
  - Unified disposition handler for both IGD and Rajal.

- [ ] **Step 1: Write integration tests for IGD dashboard and dispositions**

```python
# In tests/test_pasien_views.py
def test_igd_dashboard_loads(self):
    response = self.client.get('/pasien/igd/')
    self.assertEqual(response.status_code, 200)

def test_igd_disposisi_pulang(self):
    k = KunjunganPasien.objects.create(pasien=self.pasien, no_kunjungan='KUNJ-IGD-DISP-1', jenis_kunjungan='IGD', status='TRIAGE', tanggal_masuk=timezone.now())
    response = self.client.post(f'/pasien/kunjungan/{k.pk}/disposisi/', {
        'aksi': 'PULANG',
        'kondisi_pulang': 'MEMBAIK',
        'resume_medis': 'Keluhan mereda, obat oral diberikan'
    })
    k.refresh_from_db()
    self.assertEqual(k.status, 'PULANG')

def test_igd_disposisi_ranap(self):
    k = KunjunganPasien.objects.create(pasien=self.pasien, no_kunjungan='KUNJ-IGD-DISP-2', jenis_kunjungan='IGD', status='TRIAGE', tanggal_masuk=timezone.now())
    response = self.client.post(f'/pasien/kunjungan/{k.pk}/disposisi/', {
        'aksi': 'RANAP',
        'bed_id': self.bed.pk,
        'dpjp': 'dr. Sutomo, Sp.B'
    })
    k.refresh_from_db()
    self.bed.refresh_from_db()
    self.assertEqual(k.jenis_kunjungan, 'RANAP')
    self.assertEqual(k.status, 'RANAP')
    self.assertEqual(self.bed.status, 'TERISI')
```

- [ ] **Step 2: Add `igd_dashboard` and `kunjungan_disposisi` in `pasien/views.py`**

```python
@login_required
def igd_dashboard(request):
    """Dedicated Emergency Department (IGD) Clinical Dashboard."""
    triage_filter = request.GET.get('triage', '')
    active_igd = KunjunganPasien.objects.filter(
        jenis_kunjungan='IGD',
        status__in=['TRIAGE', 'ASESMEN', 'DAFTAR']
    ).select_related('pasien', 'created_by').order_by('triage', '-tanggal_masuk')

    if triage_filter:
        active_igd = active_igd.filter(triage=triage_filter)

    # Available beds for admission modal
    available_beds = Bed.objects.filter(status='TERSEDIA').select_related('ruangan').order_by('ruangan__kelas', 'ruangan__kode', 'kode_bed')

    ctx = {
        'pasien_igd_list': active_igd,
        'triage_filter': triage_filter,
        'count_merah': KunjunganPasien.objects.filter(jenis_kunjungan='IGD', status__in=['TRIAGE', 'ASESMEN', 'DAFTAR'], triage='MERAH').count(),
        'count_kuning': KunjunganPasien.objects.filter(jenis_kunjungan='IGD', status__in=['TRIAGE', 'ASESMEN', 'DAFTAR'], triage='KUNING').count(),
        'count_hijau': KunjunganPasien.objects.filter(jenis_kunjungan='IGD', status__in=['TRIAGE', 'ASESMEN', 'DAFTAR'], triage='HIJAU').count(),
        'count_hitam': KunjunganPasien.objects.filter(jenis_kunjungan='IGD', status__in=['TRIAGE', 'ASESMEN', 'DAFTAR'], triage='HITAM').count(),
        'available_beds': available_beds,
        'kondisi_pulang_choices': DischargeRecord.KONDISI_CHOICES if hasattr(DischargeRecord, 'KONDISI_CHOICES') else [
            ('MEMBAIK', 'Sembuh / Membaik'),
            ('BELUM_SEMBUH', 'Belum Sembuh (Rawat Jalan)'),
            ('APS', 'Atas Permintaan Sendiri (APS)'),
            ('RUJUK', 'Dirujuk ke RS Lain'),
            ('MENINGGAL', 'Meninggal Dunia'),
        ],
    }
    return render(request, 'pasien/igd_dashboard.html', ctx)


@login_required
def kunjungan_disposisi(request, pk):
    """Process clinical disposition: Pulang (Discharge) or Rawat Inap (Ranap Admission)."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    redirect_target = request.POST.get('next') or ('pasien:igd_dashboard' if k.jenis_kunjungan == 'IGD' else 'pasien:rajal_dashboard')

    if request.method == 'POST':
        aksi = request.POST.get('aksi')
        try:
            if aksi == 'PULANG':
                kondisi = request.POST.get('kondisi_pulang', 'MEMBAIK')
                resume = request.POST.get('resume_medis', 'Pelayanan selesai.')
                edukasi = request.POST.get('edukasi_pulang', '')
                obat = request.POST.get('obat_pulang', '')
                k.discharge_patient(kondisi=kondisi, resume=resume, user=request.user, edukasi=edukasi, obat=obat)
                messages.success(request, f'Pasien {k.pasien.nama_lengkap} berhasil dipulangkan.')

            elif aksi == 'RANAP':
                bed_id = request.POST.get('bed_id')
                if not bed_id:
                    raise ValueError('Silakan pilih Bed rawat inap.')
                bed_obj = get_object_or_404(Bed, pk=bed_id)
                dpjp = request.POST.get('dpjp', k.dpjp)
                catatan = request.POST.get('catatan_admisi', '')
                k.admit_to_ranap(bed=bed_obj, dpjp=dpjp, catatan=catatan)
                messages.success(request, f'Pasien {k.pasien.nama_lengkap} berhasil masuk Rawat Inap di {bed_obj}.')
            else:
                messages.error(request, 'Aksi disposisi tidak dikenali.')
        except Exception as e:
            messages.error(request, f'Gagal memproses disposisi: {e}')

    return redirect(redirect_target)
```

- [ ] **Step 3: Register URLs in `pasien/urls.py`**

```python
path('igd/', views.igd_dashboard, name='igd_dashboard'),
path('kunjungan/<int:pk>/disposisi/', views.kunjungan_disposisi, name='kunjungan_disposisi'),
```

- [ ] **Step 4: Create template `templates/pasien/igd_dashboard.html`**

Design IGD dashboard with:
- Top triage badges (Merah, Kuning, Hijau, Hitam) with counts.
- Triage priority cards with patient NIK, RM, Keluhan, DPJP, Durasi IGD.
- Two distinct disposition buttons on every patient card:
  - Button 1: `<button class="btn btn-outline-success" data-bs-toggle="modal" data-bs-target="#modalPulang{{ k.pk }}"><i class="bi bi-box-arrow-right me-1"></i>Pulang</button>`
  - Button 2: `<button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#modalRanap{{ k.pk }}"><i class="bi bi-hospital me-1"></i>Rawat Inap</button>`
- Modal Pulang: Form input for Kondisi Pulang, Resume Medis, Resep / Obat Pulang.
- Modal Rawat Inap: Dropdown of available beds grouped by Ruangan + Kelas, DPJP selector, transfer note.

- [ ] **Step 5: Run tests & verify**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py test tests.test_pasien_views`
Expected: `OK`

- [ ] **Step 6: Commit Task 3**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/igd_dashboard.html
git commit -m "feat(igd): add dedicated IGD emergency dashboard with Pulang and Ranap disposition"
```

---

### Task 4: Implement Dedicated Poli Rawat Jalan Dashboard (`/pasien/rajal/`) with Clinic Filters & Disposition

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Create: `templates/pasien/rajal_dashboard.html`

**Interfaces:**
- View: `pasien:rajal_dashboard` (`/pasien/rajal/`)
  - Filterable by Clinic/Specialty: Jantung, Paru, Penyakit Dalam, Anak, Bedah, Obgyn, Mata, Saraf, dll.
  - Active outpatient visits queue (`jenis_kunjungan='RAJAL'`, `status__in=['DAFTAR', 'ASESMEN']`).
  - Two direct clinical disposition actions per patient:
    - **Pilihan 1: Pulang (Selesai Pelayanan / Kontrol)** -> Modal for discharge, resume, control date -> uses `kunjungan_disposisi`.
    - **Pilihan 2: Rawat Inap (SPRI / Admisi)** -> Modal for bed selection -> uses `kunjungan_disposisi`.

- [ ] **Step 1: Write integration tests for Rajal dashboard**

```python
# In tests/test_pasien_views.py
def test_rajal_dashboard_loads_with_poli_filter(self):
    response = self.client.get('/pasien/rajal/?poli=Poli+Jantung')
    self.assertEqual(response.status_code, 200)

def test_rajal_disposisi_ranap(self):
    k = KunjunganPasien.objects.create(
        pasien=self.pasien, no_kunjungan='KUNJ-RAJAL-DISP', jenis_kunjungan='RAJAL',
        poliklinik='Poli Jantung & Pembuluh Darah', status='DAFTAR', tanggal_masuk=timezone.now()
    )
    response = self.client.post(f'/pasien/kunjungan/{k.pk}/disposisi/', {
        'aksi': 'RANAP',
        'bed_id': self.bed.pk,
        'dpjp': 'dr. Bambang, Sp.JP'
    })
    k.refresh_from_db()
    self.bed.refresh_from_db()
    self.assertEqual(k.jenis_kunjungan, 'RANAP')
    self.assertEqual(k.status, 'RANAP')
    self.assertEqual(self.bed.status, 'TERISI')
```

- [ ] **Step 2: Add `rajal_dashboard` view in `pasien/views.py`**

```python
@login_required
def rajal_dashboard(request):
    """Dedicated Outpatient Clinics (Poli Rawat Jalan) Dashboard."""
    from .models import POLIKLINIK_CHOICES
    poli_filter = request.GET.get('poli', '')
    active_rajal = KunjunganPasien.objects.filter(
        jenis_kunjungan='RAJAL',
        status__in=['DAFTAR', 'ASESMEN']
    ).select_related('pasien', 'created_by').order_by('poliklinik', '-tanggal_masuk')

    if poli_filter:
        active_rajal = active_rajal.filter(poliklinik__icontains=poli_filter)

    available_beds = Bed.objects.filter(status='TERSEDIA').select_related('ruangan').order_by('ruangan__kelas', 'ruangan__kode', 'kode_bed')

    # Clinic queue counts
    poli_counts = {}
    for code, label in POLIKLINIK_CHOICES:
        cnt = KunjunganPasien.objects.filter(jenis_kunjungan='RAJAL', status__in=['DAFTAR', 'ASESMEN'], poliklinik__icontains=label[:10]).count()
        poli_counts[code] = {'label': label, 'count': cnt}

    ctx = {
        'pasien_rajal_list': active_rajal,
        'poli_filter': poli_filter,
        'poliklinik_choices': POLIKLINIK_CHOICES,
        'poli_counts': poli_counts,
        'available_beds': available_beds,
        'kondisi_pulang_choices': [
            ('MEMBAIK', 'Pelayanan Selesai / Sembuh'),
            ('KONTROL', 'Perlu Kontrol Kembali'),
            ('RUJUK', 'Rujuk Eksternal'),
        ],
    }
    return render(request, 'pasien/rajal_dashboard.html', ctx)
```

- [ ] **Step 3: Register URL in `pasien/urls.py`**

```python
path('rajal/', views.rajal_dashboard, name='rajal_dashboard'),
```

- [ ] **Step 4: Create template `templates/pasien/rajal_dashboard.html`**

Design Rajal dashboard with:
- Horizontal pill navigation / clinic filter bar showing: Semua Poli, Poli Jantung, Poli Paru, Poli Penyakit Dalam, Poli Anak, Poli Bedah, dll with active patient counter badges.
- Clean table/card grid showing: No. Antrean/RM, Nama Pasien, Penjamin, Diagnosa Awal/Keluhan, DPJP Spesialis.
- Direct disposition buttons on each row:
  - `<button class="btn btn-outline-success btn-sm" data-bs-toggle="modal" data-bs-target="#modalPulangRajal{{ k.pk }}"><i class="bi bi-check-circle me-1"></i>Pulang / Selesai</button>`
  - `<button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#modalRanapRajal{{ k.pk }}"><i class="bi bi-hospital me-1"></i>Rawat Inap</button>`
- Modal Pulang (Discharge & Kontrol): Jadwal Kontrol, Edukasi Pasien, Resep Obat.
- Modal Rawat Inap (SPRI / Admisi): Pilihan Kamar & Bed, Dokter Penanggung Jawab Rawat Inap, Catatan Admisi.

- [ ] **Step 5: Run tests & verify**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py test tests.test_pasien_views`
Expected: `OK`

- [ ] **Step 6: Commit Task 4**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/rajal_dashboard.html
git commit -m "feat(rajal): add dedicated Outpatient clinic dashboard with clinic filters and disposition"
```

---

### Task 5: Sidebar Navigation Integration, Static Build, and End-to-End Verification

**Files:**
- Modify: `templates/includes/sidebar.html`

**Interfaces:**
- Updates sidebar under `Pelayanan Pasien (SIMRS)` section to cleanly display:
  - `bi-person-badge` **Pendaftaran & Admisi** (`pasien:pendaftaran_dashboard`)
  - `bi-heart-pulse` **Gawat Darurat (IGD)** (`pasien:igd_dashboard`)
  - `bi-hospital` **Poli Rawat Jalan** (`pasien:rajal_dashboard`)
  - `bi-door-open` **Rawat Inap & Bed** (`pasien:bed_management`)
  - `bi-capsule` **Farmasi & E-Prescribing** (`pasien:farmasi_antrean`)

- [ ] **Step 1: Update `templates/includes/sidebar.html`**

Update the SIMRS links to point to the dedicated dashboards while maintaining active class state.

- [ ] **Step 2: Run `manage.py check`**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py check`
Expected: `0 issues`

- [ ] **Step 3: Run comprehensive test suite**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py test tests.test_pasien_workflow tests.test_pasien_views`
Expected: All tests pass.

- [ ] **Step 4: Collect static assets**

Run: `/c/Users/cubeb/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe manage.py collectstatic --no-input`

- [ ] **Step 5: Commit & push to master**

Run:
```bash
git add templates/includes/sidebar.html staticfiles/
git commit -m "feat(navigation): integrate Pendaftaran, IGD, and Rajal dashboards into sidebar"
git push origin master
```

- [ ] **Step 6: Verify deployment on Vercel**

Run: `curl -s -o /dev/null -w "%{http_code}" https://sim-akreditasi-django.vercel.app/pasien/pendaftaran/`
Expected: `HTTP 200` or `HTTP 302` (authenticated redirect).

---

## Plan Self-Review Checklist

1. **Spec Coverage:**
   - [x] Dedicated Pendaftaran dashboard with 2 clear choices after registration: (1) ke IGD, (2) ke Poli Rawat Jalan (spesialis jantung, paru, dll).
   - [x] Dedicated IGD dashboard with 2 clinical choices: (1) Pulang (discharge), (2) Rawat Inap.
   - [x] Dedicated Poli Rawat Jalan dashboard with 2 clinical choices: (1) Pulang, (2) Rawat Inap.
2. **Atomic Bed Locking:**
   - [x] `admit_to_ranap()` uses `transaction.atomic()` to guarantee bed status transitions from `TERSEDIA` to `TERISI`.
   - [x] `discharge_patient()` automatically sets bed status to `STERILISASI`.
3. **Template & UX:**
   - [x] Distinct modal dialogs with clear validation, condition selection, and bed pickers.
