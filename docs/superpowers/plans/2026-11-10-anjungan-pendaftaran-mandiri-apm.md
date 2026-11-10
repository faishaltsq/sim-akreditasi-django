# Modul Anjungan Pendaftaran Mandiri (APM) - ARima Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a touch-screen kiosk & mobile self-service admission module (APM) with dual patient onboarding (New vs Existing), automated patient validation, IGD fast-track, clinic & doctor schedule with real-time quotas, digital WhatsApp ticket generation, 80mm/58mm thermal slip printing, barcode check-in kiosk, T-60 self-service cancellation, BPJS 7 Task ID bridging, and a TV queue display board with Text-to-Speech voice call.

**Architecture:** A native Django full-stack vertical slice extending `pasien` app with dedicated kiosk views (`/pasien/apm/`), WhatsApp notification engine (`pasien/services/whatsapp.py`), BPJS 7 Task ID queue logger (`pasien/services/bpjs_antrean.py`), schedule & quota models (`JadwalDokterPoli`, `WhatsAppLog`, `AntreanBpjsTaskLog`), kiosk touch UI (`templates/pasien/apm/kiosk.html`), thermal receipt print view, and a real-time hospital waiting room display board (`templates/pasien/apm/display_antrean.html`).

**Tech Stack:** Django 5+, PostgreSQL / SQLite, Bootstrap 5.3.3, Vanilla JavaScript (Webcam, HTML5 QR scanner, Web Speech API TTS, thermal receipt print CSS), DeepSeek Vision / KTP Validator, BPJS V-Claim & Antrean Online v2.

**Spec:** `C:\Users\cubeb\Downloads\Modul Anjungan Pendaftaran Mandiri.docx` ("Modul Anjungan Pendaftaran Mandiri (APM) - Aplikasi ARima").

## Global Constraints
- Deliver all code and templates natively in Django without adding external npm or python packages.
- WhatsApp Gateway service must support live webhook/HTTP API (Fonnte/Wablas) with automatic simulated fallback logging to `WhatsAppLog`.
- WhatsApp ticket copy and formatting must strictly match the verbatim specification in the source document.
- Follow TDD (Red-Green-Refactor) using `.venv/Scripts/python manage.py test <target> --keepdb`.
- Kiosk UI must be optimized for 1920x1080 and 1366x768 touchscreen displays with high contrast and oversized buttons, and responsive down to mobile viewports (375px+).
- Cancellation policy must enforce the T-60 business rule: cancellations >= 60 minutes before estimated service release quota and mark visit `BATAL`; cancellations < 60 minutes lock quota and record `is_noshow = True`.

## Review Focus
1. **Existing vs New Patient Routing:** Verify existing patient lookup by NIK, No. BPJS, or No. RM does not create duplicate patient records.
2. **Quota Race Condition & Expiry:** Ensure doctor queue slots and quotas decrement atomically and recalculate available slots correctly.
3. **T-60 Cancellation Guard:** Ensure cancellation requests within 60 minutes of service time are rejected for quota release and recorded as No-Show.
4. **Barcode Check-in Validation:** Ensure check-in validates patient identity, marks `is_checkin = True`, and updates BPJS Task 3.
5. **IGD Fast-Track Priority:** Ensure emergency selections bypass clinic queues, trigger triage Red/Critical, and send instant notification alerts.

---

### Task 1: Database Models for APM, Doctor Quotas, WhatsApp Log & BPJS 7 Task ID

**Files:**
- Modify: `pasien/models.py`
- Create: `pasien/migrations/0019_apm_models_and_fields.py`
- Test: `pasien/tests_apm_models.py`

**Interfaces:**
- Consumes: `Pasien`, `KunjunganPasien`, `POLIKLINIK_CHOICES`, `RumahSakitProfile`
- Produces: `JadwalDokterPoli`, `WhatsAppLog`, `AntreanBpjsTaskLog`, and extended fields on `KunjunganPasien` (`kode_booking`, `token_batal`, `estimasi_pelayanan`, `is_apm`, `is_checkin`, `waktu_checkin`, `is_noshow`, `wa_notifikasi_sent`)

- [ ] **Step 1: Write the failing test**

```python
# pasien/tests_apm_models.py
from django.test import TestCase
from django.utils import timezone
from datetime import date, time
from pasien.models import Pasien, KunjunganPasien, JadwalDokterPoli, WhatsAppLog, AntreanBpjsTaskLog

class ApmModelsTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-TEST-APM',
            nama_lengkap='Budi APM',
            tanggal_lahir=date(1990, 5, 15),
            jenis_kelamin='L',
            no_hp='08123456789'
        )

    def test_kunjungan_apm_fields(self):
        k = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-APM-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP',
            is_apm=True,
            kode_booking='APM-20261110-001',
            token_batal='tok-test-12345',
            estimasi_pelayanan=time(10, 30)
        )
        self.assertTrue(k.is_apm)
        self.assertEqual(k.kode_booking, 'APM-20261110-001')
        self.assertEqual(k.token_batal, 'tok-test-12345')
        self.assertFalse(k.is_checkin)
        self.assertFalse(k.is_noshow)

    def test_jadwal_dokter_dan_sisa_kuota(self):
        j = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP',
            gelar='Spesialis Jantung & Pembuluh Darah',
            poliklinik='POLI_JANTUNG',
            hari_praktik='Senin - Jumat',
            jam_mulai=time(8, 0),
            jam_selesai=time(12, 0),
            kuota_maksimal=20,
            durasi_per_pasien_menit=15,
            status_ketersediaan='BUKA'
        )
        self.assertEqual(j.get_sisa_kuota(), 20)
        KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-APM-002',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP',
            is_apm=True
        )
        self.assertEqual(j.get_sisa_kuota(), 19)

    def test_whatsapp_log_creation(self):
        log = WhatsAppLog.objects.create(
            nomor_tujuan='08123456789',
            jenis_pesan='TIKET_APM',
            pesan='Bukti Pendaftaran APM',
            status='SIMULASI'
        )
        self.assertEqual(log.status, 'SIMULASI')

    def test_bpjs_7_task_log(self):
        k = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-APM-003',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now()
        )
        task = AntreanBpjsTaskLog.objects.create(
            kunjungan=k,
            task_id=3,
            nama_task='Akhir Waktu Tunggu Admisi / Check-In APM',
            status_kirim='SIMULATED'
        )
        self.assertEqual(task.task_id, 3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_models --keepdb`
Expected: FAIL (`ImportError: cannot import name 'JadwalDokterPoli'`)

- [ ] **Step 3: Write minimal implementation**

Add fields to `KunjunganPasien` in `pasien/models.py`:
- `kode_booking = models.CharField('Kode Booking Antrean', max_length=30, blank=True, db_index=True)`
- `token_batal = models.CharField('Token Pembatalan APM', max_length=64, blank=True, unique=True, null=True, db_index=True)`
- `estimasi_pelayanan = models.TimeField('Estimasi Waktu Pelayanan', null=True, blank=True)`
- `is_apm = models.BooleanField('Daftar via Mandiri / APM', default=False)`
- `is_checkin = models.BooleanField('Sudah Check-In di Kiosk', default=False)`
- `waktu_checkin = models.DateTimeField('Waktu Check-In Kiosk', null=True, blank=True)`
- `is_noshow = models.BooleanField('Tercatat No-Show', default=False)`
- `wa_notifikasi_sent = models.BooleanField('Notifikasi WA Terkirim', default=False)`

Add models to `pasien/models.py`:
- `JadwalDokterPoli`: schedule, quota, photo URL, calculation helpers.
- `WhatsAppLog`: phone, message type, payload, status.
- `AntreanBpjsTaskLog`: 7 Task ID tracking for BPJS Antrean.

Run: `.venv/Scripts/python manage.py makemigrations pasien`
Run: `.venv/Scripts/python manage.py migrate pasien`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_models --keepdb`
Expected: PASS (4/4 tests OK)

- [ ] **Step 5: Commit**

```bash
git add pasien/models.py pasien/migrations/0019* pasien/tests_apm_models.py
git commit -m "feat(apm): models for doctor schedules, whatsapp logs, and bpjs 7 task id"
```

---

### Task 2: Doctor Schedule Seeder & WhatsApp Gateway Engine with Exact Ticket Copy

**Files:**
- Create: `pasien/management/commands/seed_jadwal_dokter_apm.py`
- Create: `pasien/services/whatsapp.py`
- Test: `pasien/tests_apm_whatsapp.py`

**Interfaces:**
- Consumes: `KunjunganPasien`, `JadwalDokterPoli`, `RumahSakitProfile`
- Produces: `format_tiket_wa(kunjungan, base_url)`, `kirim_pesan_wa(nomor, pesan, jenis_pesan, kunjungan)`, `seed_jadwal_dokter_apm` command.

- [ ] **Step 1: Write the failing test**

```python
# pasien/tests_apm_whatsapp.py
from django.test import TestCase
from django.utils import timezone
from datetime import date, time
from pasien.models import Pasien, KunjunganPasien, WhatsAppLog
from pasien.services.whatsapp import format_tiket_wa, kirim_pesan_wa

class ApmWhatsAppTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-98230001',
            nama_lengkap='Tn. Ahmad',
            tanggal_lahir=date(1985, 3, 20),
            jenis_kelamin='L',
            no_hp='081299998888'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-20261110-0014',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            poliklinik='Poli Spesialis Jantung',
            dpjp='dr. Faisal, Sp.JP',
            nomor_antrean='B-014',
            estimasi_pelayanan=time(10, 30),
            token_batal='TRX-998231',
            is_apm=True
        )

    def test_verbatim_ticket_format(self):
        msg = format_tiket_wa(self.kunjungan, base_url='https://arima.rs')
        self.assertIn('BUKTI PENDAFTARAN MANDIRI (APM)', msg)
        self.assertIn('No. Rekam Medis: RM-98230001', msg)
        self.assertIn('Nama Pasien: Tn. Ahmad', msg)
        self.assertIn('Tujuan Poli: Poli Spesialis Jantung', msg)
        self.assertIn('Dokter DPJP: dr. Faisal, Sp.JP', msg)
        self.assertIn('No. Antrean Poli: B-014', msg)
        self.assertIn('Estimasi Waktu Pemeriksaan: 10:30 WIB', msg)
        self.assertIn('HIMBAUAN PENTING:', msg)
        self.assertIn('10:00 WIB', msg) # 30 mins before
        self.assertIn('09:30 WIB', msg) # 60 mins before
        self.assertIn('https://arima.rs/pasien/apm/batal/?token=TRX-998231', msg)

    def test_kirim_pesan_wa_simulated(self):
        res = kirim_pesan_wa(
            nomor='081299998888',
            pesan='Test WA Message',
            jenis_pesan='TIKET_APM',
            kunjungan=self.kunjungan
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'simulated')
        self.assertTrue(WhatsAppLog.objects.filter(nomor_tujuan='081299998888').exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_whatsapp --keepdb`
Expected: FAIL (`ModuleNotFoundError: No module named 'pasien.services.whatsapp'`)

- [ ] **Step 3: Write minimal implementation**

Create `pasien/services/whatsapp.py`:
- `format_tiket_wa`: formats ticket text verbatim as required by the hospital specification.
- `kirim_pesan_wa`: sends WhatsApp via HTTP API if environment tokens are provided, or creates simulated entry in `WhatsAppLog`.

Create `pasien/management/commands/seed_jadwal_dokter_apm.py`:
- Seeds 15+ specialist doctors with realistic quotas (20-30 slots), clinic assignments, operating hours, and photo avatars.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_whatsapp --keepdb`
Expected: PASS (2/2 tests OK)

Run: `.venv/Scripts/python manage.py seed_jadwal_dokter_apm`
Expected: 15 doctor schedules created/updated.

- [ ] **Step 5: Commit**

```bash
git add pasien/services/whatsapp.py pasien/management/commands/seed_jadwal_dokter_apm.py pasien/tests_apm_whatsapp.py
git commit -m "feat(apm): verbatim whatsapp ticket generator and doctor schedule seeder"
```

---

### Task 3: BPJS 7 Task ID Antrean Bridging & Fast-Track IGD Engine

**Files:**
- Create: `pasien/services/bpjs_antrean.py`
- Modify: `pasien/bpjs.py`
- Test: `pasien/tests_apm_bpjs_tasks.py`

**Interfaces:**
- Consumes: `KunjunganPasien`, `AntreanBpjsTaskLog`, `BPJS_ANTREAN_BASE`
- Produces: `update_task_id(kunjungan, task_id, waktu)`, `bpjs_antrean_7_tasks_summary(kunjungan)`

- [ ] **Step 1: Write the failing test**

```python
# pasien/tests_apm_bpjs_tasks.py
from django.test import TestCase
from django.utils import timezone
from datetime import date
from pasien.models import Pasien, KunjunganPasien, AntreanBpjsTaskLog
from pasien.services.bpjs_antrean import update_task_id, TASK_ID_NAMES

class ApmBpjsTaskTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-TASK-001',
            nama_lengkap='Pasien BPJS',
            tanggal_lahir=date(1992, 1, 1),
            jenis_kelamin='L',
            no_bpjs='0001234567890'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-BPJS-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            penjamin='BPJS'
        )

    def test_record_task_id_1_to_7(self):
        for tid in range(1, 8):
            res = update_task_id(self.kunjungan, tid)
            self.assertTrue(res['success'])
            self.assertEqual(res['task_id'], tid)
            self.assertIn(tid, TASK_ID_NAMES)

        logs = AntreanBpjsTaskLog.objects.filter(kunjungan=self.kunjungan)
        self.assertEqual(logs.count(), 7)

    def test_invalid_task_id_rejected(self):
        with self.assertRaises(ValueError):
            update_task_id(self.kunjungan, 8)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_bpjs_tasks --keepdb`
Expected: FAIL (`ModuleNotFoundError: No module named 'pasien.services.bpjs_antrean'`)

- [ ] **Step 3: Write minimal implementation**

Create `pasien/services/bpjs_antrean.py`:
- Map the 7 Task IDs:
  - 1: Mulai waktu tunggu admisi
  - 2: Akhir waktu tunggu admisi / mulai pelayanan admisi
  - 3: Akhir pelayanan admisi / mulai waktu tunggu poli (Check-in APM)
  - 4: Mulai pemeriksaan dokter
  - 5: Selesai pemeriksaan dokter / mulai waktu tunggu farmasi
  - 6: Mulai pelayanan farmasi
  - 7: Selesai pelayanan farmasi / serah terima obat
- Implement `update_task_id` with HMAC headers or simulated mock mode.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_bpjs_tasks --keepdb`
Expected: PASS (2/2 tests OK)

- [ ] **Step 5: Commit**

```bash
git add pasien/services/bpjs_antrean.py pasien/tests_apm_bpjs_tasks.py
git commit -m "feat(apm): bpjs antrean online 7 task id tracking engine"
```

---

### Task 4: Backend APM Endpoints (Search, Register, Check-in, T-60 Cancellation)

**Files:**
- Create: `pasien/apm_views.py`
- Modify: `pasien/urls.py`
- Test: `pasien/tests_apm_views.py`

**Interfaces:**
- Consumes: `Pasien`, `KunjunganPasien`, `JadwalDokterPoli`, `WhatsAppLog`
- Produces:
  - `GET /pasien/apm/api/cari-pasien/`
  - `GET /pasien/apm/api/jadwal-dokter/`
  - `POST /pasien/apm/api/daftar/`
  - `POST /pasien/apm/api/checkin/`
  - `GET /pasien/apm/batal/` & `POST /pasien/apm/batal/`

- [ ] **Step 1: Write the failing test**

```python
# pasien/tests_apm_views.py
from django.test import TestCase, Client
from django.utils import timezone
from datetime import date, time, timedelta
from pasien.models import Pasien, KunjunganPasien, JadwalDokterPoli
from django.urls import reverse

class ApmViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.pasien = Pasien.objects.create(
            no_rm='RM-LAMA-001',
            nama_lengkap='Pasien Lama',
            tanggal_lahir=date(1980, 1, 1),
            jenis_kelamin='L',
            nik='3273010101800001',
            no_bpjs='0001112223334',
            no_hp='081234567890'
        )
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP',
            poliklinik='POLI_JANTUNG',
            jam_mulai=time(8, 0),
            jam_selesai=time(12, 0),
            kuota_maksimal=10,
            status_ketersediaan='BUKA'
        )

    def test_api_cari_pasien_lama(self):
        # By NIK
        r1 = self.client.get(reverse('pasien:apm_api_cari_pasien'), {'q': '3273010101800001'})
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()['found'])
        self.assertEqual(r1.json()['pasien']['no_rm'], 'RM-LAMA-001')

        # By BPJS
        r2 = self.client.get(reverse('pasien:apm_api_cari_pasien'), {'q': '0001112223334'})
        self.assertTrue(r2.json()['found'])

    def test_api_daftar_pasien_lama_rajal(self):
        payload = {
            'tipe_pasien': 'LAMA',
            'no_rm': 'RM-LAMA-001',
            'no_wa': '081234567890',
            'jenis_layanan': 'RAJAL',
            'poliklinik': 'POLI_JANTUNG',
            'jadwal_id': self.jadwal.pk,
            'penjamin': 'BPJS'
        }
        res = self.client.post(reverse('pasien:apm_api_daftar'), payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['nomor_antrean'].startswith('JTG-') or 'B-' in data['nomor_antrean'])
        self.assertIn('token_batal', data)

    def test_api_daftar_igd_fast_track(self):
        payload = {
            'tipe_pasien': 'BARU',
            'nama_lengkap': 'Korban Kecelakaan',
            'jenis_kelamin': 'L',
            'tanggal_lahir': '1995-04-12',
            'no_wa': '085511223344',
            'jenis_layanan': 'IGD',
            'penjamin': 'UMUM'
        }
        res = self.client.post(reverse('pasien:apm_api_daftar'), payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['jenis_kunjungan'], 'IGD')
        self.assertTrue(data['nomor_antrean'].startswith('IGD-'))

    def test_api_checkin_kiosk(self):
        k = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-CHK-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            nomor_antrean='JTG-001',
            kode_booking='APM-CHK-001',
            is_apm=True
        )
        res = self.client.post(reverse('pasien:apm_api_checkin'), {'kode': 'APM-CHK-001'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        k.refresh_from_db()
        self.assertTrue(k.is_checkin)

    def test_cancellation_policy_t60(self):
        now = timezone.now()
        # Case A: >= 60 minutes before -> ALLOWED
        k1 = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-CAN-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=now,
            estimasi_pelayanan=(now + timedelta(hours=2)).time(),
            token_batal='tok-allowed',
            is_apm=True
        )
        res_a = self.client.post(reverse('pasien:apm_batal_mandiri'), {'token': 'tok-allowed'})
        self.assertEqual(res_a.status_code, 200)
        self.assertTrue(res_a.json()['success'])
        k1.refresh_from_db()
        self.assertEqual(k1.status, 'BATAL')

        # Case B: < 60 minutes before -> NO-SHOW LOCKED
        k2 = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-CAN-002',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=now,
            estimasi_pelayanan=(now + timedelta(minutes=30)).time(),
            token_batal='tok-locked',
            is_apm=True
        )
        res_b = self.client.post(reverse('pasien:apm_batal_mandiri'), {'token': 'tok-locked'})
        self.assertEqual(res_b.status_code, 200)
        self.assertFalse(res_b.json()['success']) # Rejected cancellation
        self.assertIn('No-Show', res_b.json()['message'])
        k2.refresh_from_db()
        self.assertTrue(k2.is_noshow)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_views --keepdb`
Expected: FAIL (`ImportError: cannot import name 'apm_views'`)

- [ ] **Step 3: Write minimal implementation**

Create `pasien/apm_views.py` implementing the endpoints with atomic transaction handling, quota verification, NIK parsing/checking, and WhatsApp triggering.
Register paths in `pasien/urls.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_views --keepdb`
Expected: PASS (5/5 tests OK)

- [ ] **Step 5: Commit**

```bash
git add pasien/apm_views.py pasien/urls.py pasien/tests_apm_views.py
git commit -m "feat(apm): endpoints for patient lookup, booking, check-in, and t-60 cancellation"
```

---

### Task 5: Kiosk Touchscreen Frontend, Receipt Printing & Waiting Room Display Board

**Files:**
- Create: `templates/pasien/apm/kiosk.html`
- Create: `templates/pasien/apm/struk_thermal.html`
- Create: `templates/pasien/apm/batal.html`
- Create: `templates/pasien/apm/display_antrean.html`
- Test: `pasien/tests_apm_ui.py`

**Features:**
- Kiosk UI:
  - Step 1: Welcome touch screen (Pasien Baru vs Pasien Lama vs Check-In Barcode).
  - Step 2: Patient identification (KTP OCR webcam modal or Barcode/NIK input).
  - Step 3: Fast-Track IGD button & Specialist Clinic Touch Grid with visual icons.
  - Step 4: Doctor DPJP card with professional photo, practicing hours, real-time quota badge.
  - Step 5: Insurance selection (BPJS, Umum, Asuransi).
  - Step 6: Confirmation, Digital Ticket summary with countdown timer auto-reset, and Thermal Receipt print button.
- Thermal Slip (`templates/pasien/apm/struk_thermal.html`):
  - POS 58mm/80mm layout with QR code, patient details, queue number, estimated time, and cancellation policy.
- Waiting Room Display Board (`templates/pasien/apm/display_antrean.html`):
  - TV monitor layout, current calling queue per clinic, and browser Text-to-Speech audio call synthesis.

- [ ] **Step 1: Write the failing test**

```python
# pasien/tests_apm_ui.py
from django.test import TestCase, Client
from django.urls import reverse
from pasien.models import Pasien, KunjunganPasien, JadwalDokterPoli
from django.utils import timezone
from datetime import date, time

class ApmUiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP',
            poliklinik='POLI_JANTUNG',
            jam_mulai=time(8, 0),
            jam_selesai=time(12, 0),
            kuota_maksimal=20,
            status_ketersediaan='BUKA'
        )

    def test_kiosk_page_renders_steps(self):
        res = self.client.get(reverse('pasien:apm_kiosk'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Anjungan Pendaftaran Mandiri')
        self.assertContains(res, 'Pasien Baru')
        self.assertContains(res, 'Pasien Lama')
        self.assertContains(res, 'Check-In Barcode')
        self.assertContains(res, 'IGD')

    def test_display_board_renders(self):
        res = self.client.get(reverse('pasien:antrean_display_board'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Papan Antrean Poliklinik')
        self.assertContains(res, 'speechSynthesis')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_ui --keepdb`
Expected: FAIL (Reverse for 'apm_kiosk' not found)

- [ ] **Step 3: Write minimal implementation**

Implement templates and views for:
- `apm_kiosk_view` (`templates/pasien/apm/kiosk.html`)
- `apm_cetak_struk_view` (`templates/pasien/apm/struk_thermal.html`)
- `apm_batal_mandiri_view` (`templates/pasien/apm/batal.html`)
- `antrean_display_board_view` (`templates/pasien/apm/display_antrean.html`)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python manage.py test pasien.tests_apm_ui --keepdb`
Expected: PASS (2/2 tests OK)

- [ ] **Step 5: Commit**

```bash
git add templates/pasien/apm/ pasien/apm_views.py pasien/urls.py pasien/tests_apm_ui.py
git commit -m "feat(apm): touchscreen kiosk ui, thermal receipt, and waiting room display board"
```

---

### Task 6: Sidebar Integration, Regression Testing & Deployment Verification

**Files:**
- Modify: `templates/includes/sidebar.html`
- Modify: `templates/pasien/pendaftaran_dashboard.html`
- Verify: Full test suite (`pasien.tests_*`, `akreditasi.tests_*`)
- Assets: `python manage.py collectstatic --noinput`

**Verification:**
- Add quick access button to APM Kiosk and Antrean Display from admission sidebar and dashboard.
- Run complete test suite and assert all tests pass.
- Run `collectstatic --noinput`.

- [ ] **Step 1: Update sidebar navigation**
Add APM Kiosk & Papan Antrean links under the Pasien / Pendaftaran section.

- [ ] **Step 2: Run full regression test suite**
Run: `.venv/Scripts/python manage.py test pasien.tests_apm_* pasien.tests_ktp_* pasien.tests_pendaftaran_* --keepdb`
Expected: PASS (100% OK)

- [ ] **Step 3: Run static assets compilation**
Run: `.venv/Scripts/python manage.py collectstatic --noinput`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add templates/includes/sidebar.html templates/pasien/pendaftaran_dashboard.html
git commit -m "feat(apm): sidebar navigation and admission dashboard integration"
```
