# Clinical Patient Management Revision 01 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the new workflow enhancements specified in `revisi 01 Buku manajemen pasien pendaftaran-igd-poli-ranap.docx`, specifically: Room/Bed Reservation (Booking Kamar) with automated expiration & bed locking, General Consent for Inpatient (Persetujuan Rawat Inap) with legal STARKES compliance & A4 printout, advanced Emergency (IGD) TTV (GCS + Pain Scale) & Critical Value Alerts, and Outpatient Specialty (Poli) Drug Interaction checks with direct billing.

**Architecture:** Django 5+ backend with models in `pasien/models.py`, view controllers in `pasien/views.py`, URL routing in `pasien/urls.py`, and responsive Bootstrap 5.3.3 templates under `templates/pasien/`. Real-time bed reservation updates bed status to `DIBOOKING`, transitioning to `TERISI` upon admission or releasing to `TERSEDIA` upon cancellation/timeout. General Consent records patient/guardian identity, treatment permissions, privacy disclosure, and billing responsibility with a printable A4 accreditation document.

**Tech Stack:** Django 5.x, Python 3.11+, PostgreSQL (Supabase) / SQLite (local dev), Bootstrap 5.3.3, Bootstrap Icons, HTML5 Print CSS.

**Spec:** `Downloads/revisi 01 Buku manajemen pasien pendaftaran-igd-poli-ranap.docx`

---

## Global Constraints

- **Language for Documentation & Plan**: English for all plans in `docs/superpowers/plans/`; Bahasa Indonesia for user-facing UI copy and print deliverables.
- **AI Security**: DeepSeek API key must never be exposed to frontend/JS/browser; only invoked via Django backend.
- **Data Protection**: Patient data must be sanitized in any external API integration.
- **UI Spacing & Styling**: No touching buttons or unspaced text elements; enforce `gap-*` or Bootstrap margin utilities. Single `+` per menu sublevel.
- **Deployment Compatibility**: WhiteNoise static files, standard Django migrations applicable on Railway and local dev.
- **Accreditation Alignment**: Comply with Kemenkes STARKES HPK (Hak Pasien & Keluarga) and ARK (Akses & Rekinseptualisasi Pasien).

## Review Focus

- Bed status transition conflict: Attempting to book a bed already marked `TERISI` or `DIBOOKING` must be rejected with an informative error message.
- Expired booking cleanup: Bookings past their expiration time (`batas_waktu`) should not block admissions or persist indefinitely.
- Inpatient General Consent validation: Submission requires penanggung jawab name, NIK, relation to patient, and explicit confirmation flags before allowing transfer/admission.
- TTV range enforcement: GCS score (3-15) and numeric Pain Scale (0-10) must be validated before persisting to database.
- Critical Value Alert visibility: Laboratory orders marked as critical value must trigger prominent UI alert banners on both IGD and Poli dashboards.

---

### Task 1: Bed Reservation & Room Booking System (`BookingKamar` Model & Bed Status `DIBOOKING`)

**Files:**
- Modify: `pasien/models.py` (extend `Bed.STATUS` with `DIBOOKING`; create `BookingKamar` model)
- Create: `pasien/migrations/0005_bed_booking_and_general_consent.py` (via `makemigrations`)
- Modify: `pasien/views.py` (add `booking_kamar_buat`, `booking_kamar_batal`, `booking_kamar_checkin`, `api_bed_tersedia`)
- Modify: `pasien/urls.py` (register booking endpoints)
- Create: `templates/pasien/booking_kamar_modal.html` (reusable booking modal & bed picker)
- Test: `pasien/tests_booking.py`

**Interfaces:**
- Consumes: `Bed`, `Pasien`, `KunjunganPasien`
- Produces: `BookingKamar(pasien, bed, kunjungan, nomor_booking, waktu_booking, batas_waktu, status, catatan, petugas)`

- [ ] **Step 1: Write the failing test**

Create `pasien/tests_booking.py`:
```python
from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from pasien.models import Pasien, Ruangan, Bed, KunjunganPasien, BookingKamar

class BookingKamarTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('petugas_admisi', 'admisi@rs.com', 'pass123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-BK-001',
            nama_lengkap='Siti Rahma',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='P'
        )
        self.ruangan = Ruangan.objects.create(kode='R-MAWAR-01', nama='Mawar 1', kelas='1', jenis='RANAP', kapasitas=2)
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='B1', status='TERSEDIA')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-IGD-BK01',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            status='RAWAT'
        )

    def test_create_bed_booking_locks_bed(self):
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=self.kunjungan,
            bed=self.bed,
            nomor_booking='BK-20261004-001',
            batas_waktu=timezone.now() + timedelta(hours=2),
            catatan='Rencana transfer dari IGD',
            petugas=self.user
        )
        self.bed.refresh_from_db()
        self.assertEqual(booking.status, 'BOOKED')
        self.assertEqual(self.bed.status, 'DIBOOKING')

    def test_cancel_bed_booking_releases_bed(self):
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=self.kunjungan,
            bed=self.bed,
            nomor_booking='BK-20261004-002',
            batas_waktu=timezone.now() + timedelta(hours=2),
            petugas=self.user
        )
        booking.batalkan(alasan='Pasien memilih rawat jalan')
        booking.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(booking.status, 'BATAL')
        self.assertEqual(self.bed.status, 'TERSEDIA')

    def test_checkin_bed_booking_occupies_bed(self):
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=self.kunjungan,
            bed=self.bed,
            nomor_booking='BK-20261004-003',
            batas_waktu=timezone.now() + timedelta(hours=2),
            petugas=self.user
        )
        booking.checkin()
        booking.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(booking.status, 'CHECKIN')
        self.assertEqual(self.bed.status, 'TERISI')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_booking`
Expected: FAIL with `ImportError: cannot import name 'BookingKamar' from 'pasien.models'`

- [ ] **Step 3: Implement minimal code**

In `pasien/models.py`:
Update `Bed.STATUS`:
```python
    STATUS = [
        ('TERSEDIA', 'Tersedia'),
        ('DIBOOKING', 'Dibooking / Dipesan'),
        ('TERISI',   'Terisi'),
        ('STERILISASI', 'Proses Sterilisasi'),
        ('TIDAK_AKTIF', 'Tidak Aktif'),
    ]
```

Add `BookingKamar` model:
```python
class BookingKamar(models.Model):
    STATUS_BOOKING = [
        ('BOOKED',  'Dipesan (Menunggu Check-in)'),
        ('CHECKIN', 'Sudah Masuk Kamar'),
        ('BATAL',   'Dibatalkan'),
        ('EXPIRED', 'Kedaluwarsa'),
    ]

    nomor_booking = models.CharField('Nomor Booking', max_length=30, unique=True)
    pasien        = models.ForeignKey(Pasien, on_delete=models.CASCADE, related_name='room_bookings')
    kunjungan     = models.ForeignKey('KunjunganPasien', on_delete=models.SET_NULL, null=True, blank=True, related_name='room_bookings')
    bed           = models.ForeignKey(Bed, on_delete=models.CASCADE, related_name='bookings')
    waktu_booking = models.DateTimeField('Waktu Pesan', auto_now_add=True)
    batas_waktu   = models.DateTimeField('Batas Waktu Tunggu')
    status        = models.CharField('Status Booking', max_length=15, choices=STATUS_BOOKING, default='BOOKED')
    catatan       = models.TextField('Catatan / Indikasi', blank=True)
    alasan_batal  = models.TextField('Alasan Pembatalan', blank=True)
    petugas       = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Pemesanan Kamar (Booking Bed)'
        verbose_name_plural = 'Pemesanan Kamar (Booking Bed)'
        ordering = ['-waktu_booking']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.status == 'BOOKED':
            self.bed.status = 'DIBOOKING'
            self.bed.save(update_fields=['status'])

    def batalkan(self, alasan=''):
        self.status = 'BATAL'
        self.alasan_batal = alasan
        self.save(update_fields=['status', 'alasan_batal'])
        if self.bed.status == 'DIBOOKING':
            self.bed.status = 'TERSEDIA'
            self.bed.save(update_fields=['status'])

    def checkin(self):
        self.status = 'CHECKIN'
        self.save(update_fields=['status'])
        self.bed.status = 'TERISI'
        self.bed.save(update_fields=['status'])
        if self.kunjungan:
            self.kunjungan.bed = self.bed
            self.kunjungan.jenis_kunjungan = 'RANAP'
            self.kunjungan.status = 'RANAP'
            self.kunjungan.save(update_fields=['bed', 'jenis_kunjungan', 'status'])
```

Run migration command:
`.venv/Scripts/python.exe manage.py makemigrations pasien --name=bed_booking_and_general_consent`
`.venv/Scripts/python.exe manage.py migrate pasien`

Implement view controllers in `pasien/views.py`:
- `booking_kamar_buat`: handles form submission from IGD or Poli, validates bed availability, generates `BK-YYYYMMDD-XXX` code, sets 2-4 hours expiration, and locks bed.
- `booking_kamar_batal`: releases bed back to `TERSEDIA`.
- `booking_kamar_checkin`: finalizes admission, updates `KunjunganPasien` to `RANAP` with `bed`, marks bed `TERISI`.
- `api_bed_tersedia`: JSON endpoint returning available beds filtered by `ruangan__kelas`.

Register in `pasien/urls.py`:
- `path('booking-kamar/buat/<int:kunjungan_id>/', views.booking_kamar_buat, name='booking_kamar_buat')`
- `path('booking-kamar/batal/<int:booking_id>/', views.booking_kamar_batal, name='booking_kamar_batal')`
- `path('booking-kamar/checkin/<int:booking_id>/', views.booking_kamar_checkin, name='booking_kamar_checkin')`
- `path('api/bed-tersedia/', views.api_bed_tersedia, name='api_bed_tersedia')`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_booking`
Expected: PASS with 3 tests OK.

- [ ] **Step 5: Commit**

```bash
git add pasien/models.py pasien/views.py pasien/urls.py pasien/tests_booking.py pasien/migrations/*
git commit -m "feat(pasien): add room booking (pesan kamar) model, bed status DIBOOKING, and controllers"
```

---

### Task 2: Inpatient General Consent (`GeneralConsentRawatInap` Model & Accreditation Print Template)

**Files:**
- Modify: `pasien/models.py` (add `GeneralConsentRawatInap` model with legal guardian & STARKES HPK clauses)
- Create: `pasien/migrations/0006_general_consent_rawat_inap.py` (via `makemigrations`)
- Modify: `pasien/views.py` (add `general_consent_form`, `general_consent_simpan`, `cetak_general_consent`)
- Modify: `pasien/urls.py` (register consent endpoints)
- Create: `templates/pasien/general_consent_modal.html` (interactive digital consent modal)
- Create: `templates/pasien/cetak_general_consent.html` (standard A4 STARKES accreditation printable document)
- Test: `pasien/tests_consent.py`

**Interfaces:**
- Consumes: `KunjunganPasien`, `Pasien`
- Produces: `GeneralConsentRawatInap(kunjungan, nama_penanggung_jawab, nik_pj, hubungan, telepon_pj, alamat_pj, setuju_perawatan_umum, setuju_pelepasan_informasi, setuju_tata_tertib, jaminan_biaya, tanda_tangan_nama, waktu_persetujuan)`

- [ ] **Step 1: Write the failing test**

Create `pasien/tests_consent.py`:
```python
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth.models import User
from pasien.models import Pasien, KunjunganPasien, GeneralConsentRawatInap

class GeneralConsentTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('nakes1', 'nakes@rs.com', 'pass123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-GC-001',
            nama_lengkap='Ahmad Fauzi',
            tanggal_lahir='1980-04-12',
            jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-RANAP-GC01',
            jenis_kunjungan='RANAP',
            tanggal_masuk=timezone.now(),
            status='RANAP'
        )

    def test_create_general_consent(self):
        consent = GeneralConsentRawatInap.objects.create(
            kunjungan=self.kunjungan,
            nama_pj='Nurul Hidayah',
            nik_pj='3301019902880001',
            hubungan='ISTRI',
            telepon_pj='081234567890',
            alamat_pj='Jl. Merdeka No. 45 Semarang',
            setuju_perawatan_umum=True,
            setuju_pelepasan_informasi=True,
            setuju_tata_tertib=True,
            jaminan_biaya='BPJS',
            petugas_saksi=self.user
        )
        self.assertTrue(consent.is_lengkap)
        self.assertEqual(consent.kunjungan.pasien.nama_lengkap, 'Ahmad Fauzi')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_consent`
Expected: FAIL with `ImportError: cannot import name 'GeneralConsentRawatInap' from 'pasien.models'`

- [ ] **Step 3: Implement minimal code**

In `pasien/models.py`:
```python
class GeneralConsentRawatInap(models.Model):
    HUBUNGAN_CHOICES = [
        ('DIRI_SENDIRI', 'Diri Sendiri (Pasien)'),
        ('SUAMI_ISTRI',  'Suami / Istri'),
        ('ORANG_TUA',    'Orang Tua / Ayah / Ibu'),
        ('ANAK',         'Anak Kandung'),
        ('SAUDARA',      'Saudara Kandung'),
        ('WALI',         'Wali / Penanggung Jawab Lainnya'),
    ]

    JAMINAN_CHOICES = [
        ('BPJS',     'BPJS Kesehatan / KIS'),
        ('UMUM',     'Biaya Pribadi (Umum / Tunai)'),
        ('ASURANSI', 'Asuransi Swasta / Perusahaan'),
    ]

    kunjungan                  = models.OneToOneField('KunjunganPasien', on_delete=models.CASCADE, related_name='general_consent')
    nama_pj                    = models.CharField('Nama Penanggung Jawab / Wali', max_length=150)
    nik_pj                     = models.CharField('NIK Penanggung Jawab', max_length=20)
    hubungan                   = models.CharField('Hubungan dengan Pasien', max_length=20, choices=HUBUNGAN_CHOICES)
    telepon_pj                 = models.CharField('Nomor Telepon / WhatsApp', max_length=25)
    alamat_pj                  = models.TextField('Alamat Lengkap')

    # STARKES HPK Consent Checkboxes
    setuju_perawatan_umum      = models.BooleanField('Persetujuan Tindakan & Perawatan Medis Umum', default=True)
    setuju_pelepasan_informasi = models.BooleanField('Persetujuan Pelepasan Informasi Medis & Privasi', default=True)
    setuju_tata_tertib         = models.BooleanField('Persetujuan Tata Tertib Rawat Inap & Jam Besuk', default=True)
    nama_anggota_akses_info    = models.TextField('Nama Anggota Keluarga yang Diberi Akses Informasi', blank=True, help_text='Daftar nama keluarga yang diperbolehkan menerima informasi perkembangan medis pasien.')

    # Billing & Financial Responsibility
    jaminan_biaya              = models.CharField('Penjamin / Penanggung Biaya', max_length=15, choices=JAMINAN_CHOICES, default='BPJS')
    pernyataan_selisih_biaya   = models.BooleanField('Setuju Ketentuan Selisih Biaya (Bila Naik Kelas)', default=True)

    waktu_persetujuan          = models.DateTimeField('Waktu Persetujuan', auto_now_add=True)
    petugas_saksi              = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'General Consent Rawat Inap'
        verbose_name_plural = 'General Consent Rawat Inap'

    @property
    def is_lengkap(self):
        return bool(self.nama_pj and self.nik_pj and self.setuju_perawatan_umum and self.setuju_pelepasan_informasi)
```

In `pasien/views.py`:
- `general_consent_simpan(request, kunjungan_id)`: processes form, saves or updates `GeneralConsentRawatInap`, sets success message.
- `cetak_general_consent(request, kunjungan_id)`: renders clean A4 formatted template `templates/pasien/cetak_general_consent.html` complete with hospital header, patient demographic box, HPK rights clauses, declaration statements, and signature blocks.

In `templates/pasien/cetak_general_consent.html`:
Implement standardized hospital letterhead with logo, accreditation statement (STARKES Standar HPK 1.1), full patient details, identity of guarantor, the 5 core clauses (Persetujuan Tindakan Umum, Akses & Privasi Informasi, Tata Tertib Kamar & Penunggu, Jaminan Biaya & Biaya Selisih, Pembatalan Persetujuan), and two-column signature box (Pemberi Persetujuan vs Petugas Admisi Saksi).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_consent`
Expected: PASS with 1 test OK.

- [ ] **Step 5: Commit**

```bash
git add pasien/models.py pasien/views.py pasien/urls.py templates/pasien/cetak_general_consent.html pasien/tests_consent.py pasien/migrations/*
git commit -m "feat(pasien): add General Consent for Inpatient model, controller, and STARKES A4 print view"
```

---

### Task 3: Comprehensive IGD Dashboard Enhancements (GCS, Pain Scale, Lab Critical Value Alerts, Direct Booking & General Consent Modal)

**Files:**
- Modify: `pasien/models.py` (add `ttv_gcs`, `ttv_skala_nyeri`, `triage_alasan` to `KunjunganPasien`; add `is_critical_value`, `critical_value_catatan` to `OrderPenunjang`)
- Modify: `pasien/views.py` (`igd_ttv_update`, `order_penunjang_buat`, `igd_dashboard` context)
- Modify: `templates/pasien/igd_dashboard.html` (integrate GCS input, 0-10 pain scale face-icon selector, critical value notification bar, quick button for "Booking Kamar" and "General Consent")
- Test: `pasien/tests_igd_advanced.py`

**Interfaces:**
- Consumes: `KunjunganPasien`, `OrderPenunjang`, `BookingKamar`, `GeneralConsentRawatInap`
- Produces: Updated TTV with neurological GCS (3-15) and pain scale (0-10); critical value badges on active laboratory orders.

- [ ] **Step 1: Write the failing test**

Create `pasien/tests_igd_advanced.py`:
```python
from django.test import TestCase, Client
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, OrderPenunjang

class IgdAdvancedTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-IGD-ADV01',
            nama_lengkap='Joko Widodo',
            tanggal_lahir='1975-08-17',
            jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-IGD-ADV01',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            triage='MERAH',
            status='TRIAGE'
        )

    def test_gcs_and_pain_scale_saving(self):
        self.kunjungan.ttv_gcs = 'E4V5M6 (15)'
        self.kunjungan.ttv_skala_nyeri = 7
        self.kunjungan.save()
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.ttv_gcs, 'E4V5M6 (15)')
        self.assertEqual(self.kunjungan.ttv_skala_nyeri, 7)

    def test_critical_value_alert_flag(self):
        order = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan,
            jenis='LAB',
            prioritas='CITO',
            nama_pemeriksaan='Kalium Darah',
            is_critical_value=True,
            critical_value_catatan='K = 2.1 mEq/L (Severe Hypokalemia)'
        )
        self.assertTrue(order.is_critical_value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_igd_advanced`
Expected: FAIL with `AttributeError: 'KunjunganPasien' object has no attribute 'ttv_gcs'`

- [ ] **Step 3: Implement minimal code**

In `pasien/models.py`:
Add to `KunjunganPasien`:
```python
    ttv_gcs         = models.CharField('Glasgow Coma Scale (GCS)', max_length=30, blank=True, help_text='Contoh: E4V5M6 (15) atau Somnolen')
    ttv_skala_nyeri = models.IntegerField('Skala Nyeri (NRS 0-10)', null=True, blank=True, help_text='0 (Tidak Nyeri) s.d 10 (Sangat Hebat)')
```
Add to `OrderPenunjang`:
```python
    is_critical_value       = models.BooleanField('Critical Value Alert', default=False)
    critical_value_catatan  = models.CharField('Catatan Nilai Kritis', max_length=200, blank=True)
```

In `pasien/views.py`:
Update `igd_ttv_update` to parse and save `ttv_gcs` and `ttv_skala_nyeri`.
In `igd_dashboard`, query pending critical orders and inject into context `critical_orders = OrderPenunjang.objects.filter(kunjungan__status='RAWAT', is_critical_value=True, jenis='LAB')`.

In `templates/pasien/igd_dashboard.html`:
- Add Critical Value Alert banner at top if `critical_orders` exist: red flashing alert box displaying patient RM, test name, and critical value.
- Add GCS and Pain Scale (0-10 visual badge with color gradient) into the TTV modal `#modalTTV{{ k.pk }}`.
- Add quick action button in table dropdown:
  - `<a href="#" class="dropdown-item text-primary" data-bs-toggle="modal" data-bs-target="#modalBooking{{ k.pk }}"><i class="bi bi-calendar-plus me-1"></i> Pesan / Booking Kamar</a>`
  - `<a href="#" class="dropdown-item text-success" data-bs-toggle="modal" data-bs-target="#modalConsent{{ k.pk }}"><i class="bi bi-file-earmark-check me-1"></i> Form General Consent Ranap</a>`
  - `<a href="{% url 'pasien:cetak_general_consent' k.pk %}" class="dropdown-item text-secondary" target="_blank"><i class="bi bi-printer me-1"></i> Cetak General Consent A4</a>`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_igd_advanced`
Expected: PASS with 2 tests OK.

- [ ] **Step 5: Commit**

```bash
git add pasien/models.py pasien/views.py templates/pasien/igd_dashboard.html pasien/tests_igd_advanced.py
git commit -m "feat(igd): integrate GCS, pain scale, lab critical value alert, and booking/consent links"
```

---

### Task 4: Comprehensive Outpatient Specialty (Poli) Enhancements (Specialty Assessment, E-Prescribing Drug Alerts, & Direct Room Booking)

**Files:**
- Modify: `pasien/models.py` (add `resep_catatan_interaksi` to `ResepElektronik` or `KunjunganPasien`)
- Modify: `pasien/views.py` (`rajal_dashboard`, `rajal_soap_simpan`)
- Modify: `templates/pasien/rajal_dashboard.html` (integrate Booking Kamar modal, General Consent modal & print links, specialty assessment fields)
- Test: `pasien/tests_rajal_advanced.py`

**Interfaces:**
- Consumes: `KunjunganPasien`, `BookingKamar`, `GeneralConsentRawatInap`, `ResepElektronik`
- Produces: Integrated specialty consultation workflow with room booking directly from Outpatient Clinic before inpatient transfer.

- [ ] **Step 1: Write the failing test**

Create `pasien/tests_rajal_advanced.py`:
```python
from django.test import TestCase
from django.utils import timezone
from pasien.models import Pasien, Ruangan, Bed, KunjunganPasien, BookingKamar

class RajalAdvancedTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-RAJAL-ADV01',
            nama_lengkap='Bambang Pamungkas',
            tanggal_lahir='1982-06-10',
            jenis_kelamin='L'
        )
        self.ruangan = Ruangan.objects.create(kode='R-VIP-02', nama='VIP Melati', kelas='VIP', jenis='RANAP', kapasitas=1)
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='B1', status='TERSEDIA')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-RAJAL-ADV01',
            jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(),
            status='DAFTAR'
        )

    def test_poli_spri_with_bed_booking(self):
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=self.kunjungan,
            bed=self.bed,
            nomor_booking='BK-POLI-001',
            batas_waktu=timezone.now() + timezone.timedelta(hours=4),
            catatan='Indikasi Angiografi Koroner terencana'
        )
        self.assertEqual(booking.bed.status, 'DIBOOKING')
        self.assertEqual(booking.kunjungan.poliklinik, 'Poli Jantung & Pembuluh Darah')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_rajal_advanced`
Expected: Passes once Task 1 is completed.

- [ ] **Step 3: Implement minimal code**

In `templates/pasien/rajal_dashboard.html`:
- Add dropdown options in the action button column:
  - `<a class="dropdown-item text-primary" href="#" data-bs-toggle="modal" data-bs-target="#modalBookingR{{ k.pk }}"><i class="bi bi-calendar-plus me-1"></i> Pesan / Booking Kamar (SPRI)</a>`
  - `<a class="dropdown-item text-success" href="#" data-bs-toggle="modal" data-bs-target="#modalConsentR{{ k.pk }}"><i class="bi bi-file-earmark-check me-1"></i> Form General Consent Ranap</a>`
  - `<a class="dropdown-item text-secondary" href="{% url 'pasien:cetak_general_consent' k.pk %}" target="_blank"><i class="bi bi-printer me-1"></i> Cetak General Consent A4</a>`
- Include modal markup `#modalBookingR{{ k.pk }}` and `#modalConsentR{{ k.pk }}` for seamless entry without navigating away from the clinic queue.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_rajal_advanced`
Expected: PASS with 1 test OK.

- [ ] **Step 5: Commit**

```bash
git add templates/pasien/rajal_dashboard.html pasien/tests_rajal_advanced.py
git commit -m "feat(rajal): add room booking and general consent workflows to outpatient dashboard"
```

---

### Task 5: End-to-End Test Suite, Verification, & Remote Deployment

**Files:**
- Modify: `pasien/tests_workflow.py` (full lifecycle test from Pendaftaran -> IGD/Poli -> Booking Bed -> General Consent -> Ranap Admission -> Discharge)
- Verify: `manage.py check` & `manage.py test`
- Deploy: Commit and push to `master` (triggers Railway build & Supabase migrations)

- [ ] **Step 1: Write end-to-end integration test**

Update `pasien/tests_workflow.py`:
```python
    def test_complete_booking_and_consent_inpatient_flow(self):
        # 1. Patient registers at IGD
        kunj = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-E2E-001',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            triage='KUNING',
            status='RAWAT'
        )
        # 2. Doctor books a bed
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=kunj,
            bed=self.bed,
            nomor_booking='BK-E2E-001',
            batas_waktu=timezone.now() + timezone.timedelta(hours=2),
            catatan='Rencana rawat observasi 24 jam',
            petugas=self.user
        )
        self.assertEqual(self.bed.status, 'DIBOOKING')

        # 3. Family signs General Consent
        consent = GeneralConsentRawatInap.objects.create(
            kunjungan=kunj,
            nama_pj='Wahyudi',
            nik_pj='3301021234560002',
            hubungan='SUAMI_ISTRI',
            telepon_pj='081987654321',
            alamat_pj='Semarang',
            setuju_perawatan_umum=True,
            setuju_pelepasan_informasi=True,
            setuju_tata_tertib=True,
            jaminan_biaya='BPJS',
            petugas_saksi=self.user
        )
        self.assertTrue(consent.is_lengkap)

        # 4. Check-in to inpatient room
        booking.checkin()
        kunj.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(kunj.jenis_kunjungan, 'RANAP')
        self.assertEqual(self.bed.status, 'TERISI')
```

- [ ] **Step 2: Run all tests**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: All tests pass with 0 errors.

- [ ] **Step 3: Run Django system check & static collection**

Run: `.venv/Scripts/python.exe manage.py check`
Run: `.venv/Scripts/python.exe manage.py collectstatic --noinput`

- [ ] **Step 4: Push to origin master**

Run: `git push origin master`
Verify Railway auto-deployment completes successfully.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-04-clinical-patient-management-revisi-01.md`. Please review the plan. Which execution approach would you prefer?

- **Subagent-driven** - A fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** - I implement every task myself in this session, the way this harness runs work, then one fresh reviewer on the most capable model checks the whole branch. Cheapest and fastest; no independent review until the end. Runs well with a mid-tier session model, since the plan carries the design.

For this plan I recommend **Native**, because the tasks build on the existing Django models, templates, and views in a tightly coupled sequential flow where direct context reuse is fast, safe, and avoids context reloading overhead. Does the plan capture what you want, and which approach should we use?
