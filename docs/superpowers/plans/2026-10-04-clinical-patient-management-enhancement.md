# Comprehensive Clinical Patient Management System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete end-to-end patient management workflows specified in the hospital operations manual across Pendaftaran (admission & routing with bed monitoring, wristband/SEP print), IGD (emergency triage, dwell-time counter, TTV, 4-way disposition), and Poli Rawat Jalan (specialist queue management, direct SOAP, diagnostic orders, internal consult, SKDP control letters).

**Architecture:** Extend Django `pasien` app models with clinical triage, queue state tracking, diagnostic orders, and specialized discharge records. Implement reactive UI elements (dwell-time counter, bed availability widget, queue calling states) with Bootstrap 5.3, vanilla JS, and atomic Django backend endpoints.

**Tech Stack:** Python 3.12, Django 5.x, PostgreSQL (Supabase) / SQLite, Bootstrap 5.3.3, Bootstrap Icons, ReportLab / printable HTML views.

**Spec:** `Downloads/Buku manajemen pasien pendaftaran-igd-poli-ranap.docx`

---

## Global Constraints

- Plans and technical specifications must be written in English.
- No third-party UI framework dependencies; use native HTML5, Bootstrap 5.3.3, and vanilla JS.
- All database state transitions (bed reservation, discharge, transfer) must execute inside `transaction.atomic()`.
- Sensitive medical records must not expose API keys or unredacted PII in frontend traces.
- All form submissions must include valid CSRF tokens.
- Layouts must adhere to ARIMA theme colors (`#0f172a`, `#0d9488`, `#2563eb`, `#dc2626`).

---

## Review Focus

1. **Concurrent Bed Admission Conflict**: Two users admitting different patients to the same bed simultaneously must be prevented via `transaction.atomic()` and atomic `select_for_update()`.
2. **Dwell-Time Calculation Boundary**: Patients admitted across midnight or in different server timezones must display correct elapsed hours/minutes without crashing or negative values.
3. **Queue Number Rollover**: Daily queue numbers for clinics (`POLI-JTG-001`, `IGD-001`) must correctly reset per day and per unit without duplicate collisions.
4. **Discharge Bed Release**: Discharging a patient via any disposition route (Sembuh, PAPS, Rujuk, Meninggal) must strictly release the occupied bed and mark it as `STERILISASI`.
5. **Partial Medical Form Data Loss**: Submitting quick TTV or diagnostic orders must not wipe previously entered CPPT or admission notes.

---

## File Structure

```
pasien/
├── models.py                     # Add OrderPenunjang, expand KunjunganPasien & DischargeRecord
├── views.py                      # New disposition handlers, queue endpoints, printable views
├── urls.py                       # URL routing for printables, orders, and queue updates
├── tests_management.py           # Unit and integration test suite
templates/
└── pasien/
    ├── pendaftaran_dashboard.html # Enhanced with real-time bed widget, NIK autocomplete, SEP/wristband modals
    ├── igd_dashboard.html         # Enhanced with dwell timer, TTV modal, 4-way disposition modals
    ├── rajal_dashboard.html       # Enhanced with queue caller, SOAP & Lab/Rad direct entry, SKDP modal
    ├── cetak_gelang.html          # Printable thermal wristband view (standard 25x280mm)
    ├── cetak_sep.html             # Printable BPJS SEP simulation letter
    ├── cetak_spri.html            # Printable SPRI (Surat Perintah Rawat Inap)
    └── cetak_skdp.html            # Printable SKDP (Surat Keterangan Dalam Perawatan)
```

---

## Task Decomposition

### Task 1: Database Model Enhancements & Migrations

**Files:**
- Modify: `pasien/models.py:114-237` (KunjunganPasien), `pasien/models.py:320-360` (DischargeRecord)
- Create: `pasien/models.py` (Add `OrderPenunjang` model)
- Test: `pasien/tests_management.py`

**Interfaces:**
- Consumes: Existing `KunjunganPasien`, `Bed`, `Pasien`, `User` models
- Produces:
  - `KunjunganPasien.nomor_antrean` (CharField)
  - `KunjunganPasien.flag_khusus` (CharField)
  - `KunjunganPasien.status_antrean` (CharField: MENUNGGU, DIPANGGIL, SEDANG_DILAYANI, SELESAI)
  - Vital signs fields: `ttv_sistole`, `ttv_diastole`, `ttv_nadi`, `ttv_rr`, `ttv_suhu`, `ttv_spo2`
  - Action fields: `icd9_tindakan`
  - Mortuary fields: `waktu_kematian`, `penyebab_kematian`
  - Referral fields: `sisrute_rs_tujuan`, `sisrute_alasan`, `konsul_ke_poli`, `konsul_catatan`
  - Model `OrderPenunjang`: FK to `KunjunganPasien`, `jenis` (LAB/RADIOLOGI), `nama_pemeriksaan`, `prioritas` (CITO/RUTIN), `status`
  - `DischargeRecord`: `paps_alasan`, `paps_nama_penolak`, `skdp_nomor`, `skdp_tanggal_kontrol`

- [ ] **Step 1: Write test for new model fields and OrderPenunjang**

```python
# pasien/tests_management.py
import pytest
from datetime import date
from django.utils import timezone
from django.contrib.auth.models import User
from pasien.models import Pasien, KunjunganPasien, OrderPenunjang, DischargeRecord, Bed, Ruangan

def test_model_fields_and_order_penunjang(db):
    user = User.objects.create_user(username="dr_test", password="password")
    pasien = Pasien.objects.create(
        no_rm="RM-99001",
        nama_lengkap="Budi Santoso",
        tanggal_lahir=date(1985, 5, 20),
        jenis_kelamin="L",
    )
    kunjungan = KunjunganPasien.objects.create(
        pasien=pasien,
        no_kunjungan="KUNJ-TEST-001",
        jenis_kunjungan="IGD",
        tanggal_masuk=timezone.now(),
        nomor_antrean="IGD-001",
        flag_khusus="AMBULANS",
        status_antrean="MENUNGGU",
        ttv_sistole=120,
        ttv_diastole=80,
        ttv_nadi=88,
        ttv_rr=20,
        ttv_suhu=36.8,
        ttv_spo2=99,
        icd9_tindakan="93.57 - Application of wound dressing",
    )
    assert kunjungan.nomor_antrean == "IGD-001"
    assert kunjungan.ttv_sistole == 120

    # Test OrderPenunjang
    order = OrderPenunjang.objects.create(
        kunjungan=kunjungan,
        jenis="LAB",
        nama_pemeriksaan="Darah Rutin, SGOT, SGPT, Ureum, Kreatinin",
        prioritas="CITO",
        dokter_pengirim="dr. Jaga IGD",
    )
    assert order.status == "ORDERED"
    assert order.kunjungan == kunjungan
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe" -m pytest pasien/tests_management.py -v`
Expected: FAIL with `cannot import name 'OrderPenunjang'` or attribute error.

- [ ] **Step 3: Update `pasien/models.py` with the required fields and `OrderPenunjang` model**

Add to `KunjunganPasien`:
- `nomor_antrean = models.CharField('No. Antrean', max_length=25, blank=True)`
- `flag_khusus = models.CharField('Flag Kondisi Khusus', max_length=50, blank=True, choices=[('NORMAL', 'Normal'), ('AMBULANS', 'Rujukan Ambulans'), ('KRITIS', 'Kondisi Kritis / Resusitasi')])`
- `status_antrean = models.CharField('Status Antrean', max_length=20, default='MENUNGGU', choices=[('MENUNGGU', 'Menunggu'), ('DIPANGGIL', 'Dipanggil'), ('SEDANG_DILAYANI', 'Sedang Dilayani'), ('SELESAI', 'Selesai')])`
- TTV fields: `ttv_sistole`, `ttv_diastole`, `ttv_nadi`, `ttv_rr`, `ttv_suhu`, `ttv_spo2`
- `icd9_tindakan = models.CharField('Tindakan Medis (ICD-9-CM)', max_length=300, blank=True)`
- SISRUTE fields: `sisrute_rs_tujuan = models.CharField('RS Tujuan Rujukan', max_length=200, blank=True)`, `sisrute_alasan = models.TextField('Alasan Rujukan Eksternal', blank=True)`
- Mortuary fields: `waktu_kematian = models.DateTimeField('Waktu Kematian', null=True, blank=True)`, `penyebab_kematian = models.TextField('Penyebab Kematian', blank=True)`
- Internal consult fields: `konsul_ke_poli = models.CharField('Konsul ke Poli', max_length=100, blank=True)`, `konsul_catatan = models.TextField('Catatan Konsultasi Internal', blank=True)`

Add `OrderPenunjang` class:
```python
class OrderPenunjang(models.Model):
    JENIS_CHOICES = [('LAB', 'Laboratorium'), ('RADIOLOGI', 'Radiologi')]
    PRIORITAS_CHOICES = [('CITO', 'CITO / Cepat'), ('RUTIN', 'Rutin')]
    STATUS_CHOICES = [('ORDERED', 'Terkirim'), ('PROSES', 'Dalam Pemeriksaan'), ('SELESAI', 'Selesai / Hasil Tersedia')]

    kunjungan = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='order_penunjang')
    jenis = models.CharField('Jenis Penunjang', max_length=15, choices=JENIS_CHOICES)
    nama_pemeriksaan = models.CharField('Nama Pemeriksaan / Tindakan', max_length=255)
    catatan_klinis = models.TextField('Catatan Klinis / Indikasi', blank=True)
    prioritas = models.CharField('Prioritas', max_length=10, choices=PRIORITAS_CHOICES, default='RUTIN')
    status = models.CharField('Status Order', max_length=15, choices=STATUS_CHOICES, default='ORDERED')
    dokter_pengirim = models.CharField('Dokter Pengirim', max_length=150, blank=True)
    hasil_pemeriksaan = models.TextField('Hasil Pemeriksaan', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Add to `DischargeRecord`:
- `paps_alasan = models.TextField('Alasan PAPS', blank=True)`
- `paps_nama_penolak = models.CharField('Nama Pasien/Keluarga Penolak', max_length=150, blank=True)`
- `skdp_nomor = models.CharField('Nomor SKDP', max_length=50, blank=True)`
- `skdp_tanggal_kontrol = models.DateField('Tanggal Kontrol SKDP', null=True, blank=True)`

- [ ] **Step 4: Generate and execute migration**

Run:
`python manage.py makemigrations pasien --name="patient_management_flow_fields"`
`python manage.py migrate pasien`
Expected: Migration `0004` applied successfully.

- [ ] **Step 5: Run tests and verify PASS**

Run: `"C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe" -m pytest pasien/tests_management.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pasien/models.py pasien/migrations/ pasien/tests_management.py
git commit -m "feat(pasien): add clinical queue, TTV, OrderPenunjang, and discharge fields"
```

---

### Task 2: Pendaftaran Dashboard Enhancements (Queue Numbers, Bed Real-Time, NIK Check, Printables)

**Files:**
- Modify: `pasien/views.py` (Add queue number generation helper, API for NIK duplicate check, printable views)
- Modify: `pasien/urls.py`
- Modify: `templates/pasien/pendaftaran_dashboard.html`
- Create: `templates/pasien/cetak_gelang.html`, `templates/pasien/cetak_sep.html`
- Test: `pasien/tests_management.py:test_pendaftaran_enhancements`

**Interfaces:**
- Consumes: `Pasien`, `KunjunganPasien`, `Bed`, `Ruangan`
- Produces:
  - `api_cek_nik(request)` -> JSON `{exists: bool, pasien: {...}}`
  - `cetak_gelang(request, pk)` -> HTML view optimized for 25x280mm thermal wristband print
  - `cetak_sep(request, pk)` -> HTML view simulating standard BPJS SEP form
  - Auto-generated queue codes: `IGD-XXX` for emergency, `JTG-XXX`, `PAR-XXX`, etc. for outpatient clinics
  - Live bed capacity status matrix embedded directly on the admission desk

- [ ] **Step 1: Write tests for NIK API and queue number generator**

```python
# In pasien/tests_management.py
def test_nik_api_and_queue_generation(client, db):
    p = Pasien.objects.create(
        no_rm="RM-12345", nik="3201012345670001", nama_lengkap="Siti Rahma",
        tanggal_lahir=date(1990, 1, 1), jenis_kelamin="P"
    )
    # Check duplicate NIK
    resp = client.get(f"/pasien/api/cek-nik/?nik=3201012345670001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is True
    assert data["pasien"]["no_rm"] == "RM-12345"

    # Check non-existent NIK
    resp = client.get(f"/pasien/api/cek-nik/?nik=9999999999999999")
    assert resp.json()["exists"] is False
```

- [ ] **Step 2: Implement view logic in `pasien/views.py`**

1. Helper `generate_nomor_antrean(jenis, poliklinik)`:
   - For IGD: Counts visits today with `jenis_kunjungan='IGD'`, returns `IGD-{count+1:03d}`
   - For RAJAL: Prefix based on clinic code (e.g., JTG, PAR, INT, PED), returns `{PREFIX}-{count+1:03d}`
2. View `api_cek_nik(request)`:
   - Searches `Pasien.objects.filter(nik=nik)` or `no_rm=q`. Returns details if matched.
3. Views `cetak_gelang(request, pk)` and `cetak_sep(request, pk)`:
   - Render clean, printable templates with barcode/QR code indicators.
4. Pass real-time `ruangan_bed_summary` to `pendaftaran_dashboard` context:
   - List of room classes (VIP, Kelas 1, Kelas 2, Kelas 3, ICU) with total beds, occupied beds, and available beds.

- [ ] **Step 3: Register URLs in `pasien/urls.py`**

- `path('api/cek-nik/', views.api_cek_nik, name='api_cek_nik')`
- `path('kunjungan/<int:pk>/cetak-gelang/', views.cetak_gelang, name='cetak_gelang')`
- `path('kunjungan/<int:pk>/cetak-sep/', views.cetak_sep, name='cetak_sep')`

- [ ] **Step 4: Create print templates and update `pendaftaran_dashboard.html`**

- `templates/pasien/cetak_gelang.html`: Standard horizontal patient ID bracelet with Name, No. RM, DOB, Gender, Barcode simulation.
- `templates/pasien/cetak_sep.html`: Standard Surat Eligibilitas Peserta (BPJS) format with No. Kartu, Diagnosa Awal, Poli Tujuan, and QR verification stamp.
- Update `pendaftaran_dashboard.html`:
  - Add NIK / No RM auto-lookup debounced AJAX input.
  - Add condition flagging selection (Ambulans, Kritis, Normal).
  - Add Bed Availability quick modal or mini summary cards.
  - Add quick action buttons: "Cetak Gelang" and "Cetak SEP".

- [ ] **Step 5: Run tests and verify PASS**

Run: `"C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe" -m pytest pasien/tests_management.py -k test_nik_api -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/
git commit -m "feat(pasien): pendaftaran queue generation, NIK duplicate check, bed widget, wristband & SEP print"
```

---

### Task 3: IGD Dashboard Enhancements (Dwell-Time, TTV/ICD-9, 4-Way Extended Dispositions)

**Files:**
- Modify: `pasien/views.py` (Update `igd_dashboard`, `kunjungan_disposisi`, and add `igd_ttv_update`)
- Modify: `pasien/urls.py`
- Modify: `templates/pasien/igd_dashboard.html`
- Create: `templates/pasien/cetak_spri.html`
- Test: `pasien/tests_management.py:test_igd_workflow`

**Interfaces:**
- Consumes: `KunjunganPasien`, `DischargeRecord`, `Bed`
- Produces:
  - Dwell-time calculation badge (Green < 2h, Yellow 2-4h, Red > 4h overcrowding alert)
  - Quick TTV & ICD-9 Action modal & endpoint
  - 4 Disposition routes:
    1. **Pulang**: Standard discharge (Sembuh) vs PAPS (Pulang Atas Permintaan Sendiri with refusal notes)
    2. **Rawat Inap**: Bed locking + SPRI generation + Admitting note
    3. **Rujuk Keluar**: SISRUTE hospital destination + clinical reason + transfer note
    4. **Meninggal Dunia**: Exact time of death + cause + notification flag for mortuary (Pemulasaraan Jenazah)

- [ ] **Step 1: Write test for IGD 4-way disposition & TTV updates**

```python
# In pasien/tests_management.py
def test_igd_four_way_disposition(client, db):
    user = User.objects.create_user(username="dr_igd", password="password")
    client.force_login(user)
    pasien = Pasien.objects.create(no_rm="RM-IGD-01", nama_lengkap="Pasien IGD", tanggal_lahir=date(1995, 3, 10), jenis_kelamin="L")
    k = KunjunganPasien.objects.create(pasien=pasien, no_kunjungan="KUNJ-IGD-01", jenis_kunjungan="IGD", tanggal_masuk=timezone.now(), status="TRIAGE")

    # Test PAPS Disposition
    resp = client.post(f"/pasien/kunjungan/{k.pk}/disposisi/", {
        "aksi": "PAPS",
        "paps_alasan": "Pasien menolak rawat inap karena urusan keluarga",
        "paps_nama_penolak": "Ayah Pasien",
        "resume_medis": "Pasien diedukasi risiko perburukan, tetap menolak rawat.",
    })
    k.refresh_from_db()
    assert k.status == "PULANG"
    assert k.discharge.kondisi_pulang == "APS"
    assert "urusan keluarga" in k.discharge.paps_alasan

    # Test Rujuk Keluar (SISRUTE)
    k2 = KunjunganPasien.objects.create(pasien=pasien, no_kunjungan="KUNJ-IGD-02", jenis_kunjungan="IGD", tanggal_masuk=timezone.now(), status="TRIAGE")
    resp = client.post(f"/pasien/kunjungan/{k2.pk}/disposisi/", {
        "aksi": "RUJUK_EKSTERNAL",
        "sisrute_rs_tujuan": "RSUP Dr. Sardjito",
        "sisrute_alasan": "Memerlukan intervensi cath lab segera (STEMI)",
        "resume_medis": "Pasien stabil saat ditransfer menggunakan ambulans advance.",
    })
    k2.refresh_from_db()
    assert k2.status == "RUJUK"
    assert k2.sisrute_rs_tujuan == "RSUP Dr. Sardjito"

    # Test Meninggal Dunia
    k3 = KunjunganPasien.objects.create(pasien=pasien, no_kunjungan="KUNJ-IGD-03", jenis_kunjungan="IGD", tanggal_masuk=timezone.now(), status="TRIAGE")
    waktu_mati = timezone.now().strftime('%Y-%m-%d %H:%M')
    resp = client.post(f"/pasien/kunjungan/{k3.pk}/disposisi/", {
        "aksi": "MENINGGAL",
        "waktu_kematian": waktu_mati,
        "penyebab_kematian": "Henti jantung irreversible pasca RJP 30 menit",
        "resume_medis": "DoA / dinyatakan meninggal di IGD",
    })
    k3.refresh_from_db()
    assert k3.status == "MENINGGAL"
    assert k3.discharge.kondisi_pulang == "MENINGGAL"
```

- [ ] **Step 2: Update `kunjungan_disposisi` in `pasien/views.py`**

Support:
- `aksi == 'PULANG'`: Standard discharge
- `aksi == 'PAPS'`: Save refusal notes, set `status='PULANG'`, condition `'APS'`
- `aksi == 'RANAP'`: Execute `admit_to_ranap(bed)`, generate SPRI number `SPRI-YYYYMMDD-XXXX`
- `aksi == 'RUJUK_EKSTERNAL'`: Set `status='RUJUK'`, save `sisrute_rs_tujuan`, `sisrute_alasan`
- `aksi == 'MENINGGAL'`: Set `status='MENINGGAL'`, save `waktu_kematian`, `penyebab_kematian`, release bed to sterilization

- [ ] **Step 3: Add `igd_ttv_update` view and URL**

Accepts: `ttv_sistole`, `ttv_diastole`, `ttv_nadi`, `ttv_rr`, `ttv_suhu`, `ttv_spo2`, `icd9_tindakan`. Updates `kunjungan` directly with instant feedback.

- [ ] **Step 4: Create `cetak_spri.html` and update `igd_dashboard.html`**

- Add client-side live Dwell-Time counter (`H:i` elapsed counter with badge color coding).
- Add TTV badge in table rows showing quick vitals (e.g. `120/80 mmHg | 88 bpm | 36.8°C | 99%`).
- Add comprehensive disposition modals:
  1. Modal Pulang Sembuh / Kontrol
  2. Modal Pulang PAPS (with signature / consent statement)
  3. Modal Rawat Inap (with bed picker and SPRI print link)
  4. Modal Rujuk Eksternal (SISRUTE form)
  5. Modal Pasien Meninggal Dunia (Mortuary protocol notification)

- [ ] **Step 5: Run tests and verify PASS**

Run: `"C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe" -m pytest pasien/tests_management.py -k test_igd -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/
git commit -m "feat(pasien): IGD dwell-time counter, TTV entry, 4-way disposition (Sembuh/PAPS/SISRUTE/Meninggal)"
```

---

### Task 4: Poli Rawat Jalan Enhancements (Queue Calling, Direct SOAP, Lab/Rad Orders, Internal Consult, SKDP)

**Files:**
- Modify: `pasien/views.py` (Update `rajal_dashboard`, add `rajal_antrean_panggil`, `order_penunjang_buat`)
- Modify: `pasien/urls.py`
- Modify: `templates/pasien/rajal_dashboard.html`
- Create: `templates/pasien/cetak_skdp.html`
- Test: `pasien/tests_management.py:test_rajal_workflow`

**Interfaces:**
- Consumes: `KunjunganPasien`, `OrderPenunjang`, `CPPT`, `ResepElektronik`
- Produces:
  - Queue calling transition endpoints: `MENUNGGU` -> `DIPANGGIL` -> `SEDANG_DILAYANI` -> `SELESAI`
  - Integrated direct SOAP entry that automatically appends to patient's CPPT records
  - Direct entry for Lab & Radiology diagnostic orders (`OrderPenunjang`)
  - Internal Consultation routing (transferring queue to another clinic specialty on the same date)
  - Printable SKDP (Surat Keterangan Dalam Perawatan) for outpatient control letters

- [ ] **Step 1: Write test for Outpatient queue transitions, orders, and internal consult**

```python
# In pasien/tests_management.py
def test_rajal_queue_and_orders(client, db):
    user = User.objects.create_user(username="dr_spesialis", password="password")
    client.force_login(user)
    pasien = Pasien.objects.create(no_rm="RM-RJ-01", nama_lengkap="Pasien Rajal", tanggal_lahir=date(1988, 7, 15), jenis_kelamin="P")
    k = KunjunganPasien.objects.create(
        pasien=pasien, no_kunjungan="KUNJ-RJ-01", jenis_kunjungan="RAJAL",
        poliklinik="Poli Jantung & Pembuluh Darah", tanggal_masuk=timezone.now(),
        nomor_antrean="JTG-001", status_antrean="MENUNGGU"
    )

    # 1. Test queue calling
    resp = client.post(f"/pasien/kunjungan/{k.pk}/antrean-status/", {"status_antrean": "DIPANGGIL"})
    k.refresh_from_db()
    assert k.status_antrean == "DIPANGGIL"

    # 2. Test Direct Lab Order
    resp = client.post(f"/pasien/kunjungan/{k.pk}/order-penunjang/", {
        "jenis": "LAB",
        "nama_pemeriksaan": "Profil Lipid (Kolesterol Total, HDL, LDL, Trigliserida)",
        "prioritas": "RUTIN",
        "catatan_klinis": "Evaluasi dislipidemia",
    })
    assert OrderPenunjang.objects.filter(kunjungan=k, jenis="LAB").exists()

    # 3. Test Internal Consultation to Poli Paru
    resp = client.post(f"/pasien/kunjungan/{k.pk}/disposisi/", {
        "aksi": "KONSUL_INTERNAL",
        "konsul_ke_poli": "Poli Paru & Respirasi",
        "konsul_catatan": "Mohon evaluasi batuk kronis 3 minggu dan gambaran rontgen toraks.",
    })
    k.refresh_from_db()
    assert k.poliklinik == "Poli Paru & Respirasi"
    assert k.konsul_ke_poli == "Poli Paru & Respirasi"
    assert k.status_antrean == "MENUNGGU"
```

- [ ] **Step 2: Implement Outpatient view endpoints in `pasien/views.py`**

1. `rajal_antrean_status(request, pk)`:
   - Updates `status_antrean` (`MENUNGGU`, `DIPANGGIL`, `SEDANG_DILAYANI`, `SELESAI`).
2. `order_penunjang_buat(request, pk)`:
   - Creates `OrderPenunjang` record. Automatically creates corresponding `BillingItem` ('LAB' or 'RADIOLOGI') with baseline price.
3. `rajal_soap_simpan(request, pk)`:
   - Saves S, O, A, P fields directly as a `CPPT` record with `profesi='DOKTER'` and `verifikasi_dpjp=True`.
4. Update `kunjungan_disposisi`:
   - Support `aksi == 'KONSUL_INTERNAL'`: routes visit to new target clinic, sets `status_antrean='MENUNGGU'`.
   - Support SKDP issuance when `aksi == 'PULANG'` with `jadwal_kontrol`.
5. `cetak_skdp(request, pk)`:
   - Printable view for Surat Keterangan Dalam Perawatan with doctor stamp and diagnostic summary.

- [ ] **Step 3: Register URLs in `pasien/urls.py`**

- `path('kunjungan/<int:pk>/antrean-status/', views.rajal_antrean_status, name='rajal_antrean_status')`
- `path('kunjungan/<int:pk>/order-penunjang/', views.order_penunjang_buat, name='order_penunjang_buat')`
- `path('kunjungan/<int:pk>/soap/', views.rajal_soap_simpan, name='rajal_soap_simpan')`
- `path('kunjungan/<int:pk>/cetak-skdp/', views.cetak_skdp, name='cetak_skdp')`

- [ ] **Step 4: Create `cetak_skdp.html` and enhance `rajal_dashboard.html`**

- Add Queue Action Caller buttons on each row: "Panggil Pasien", "Mulai Layani", "Selesai".
- Add tabs or modals for:
  - Direct SOAP entry (Subjective, Objective, Assessment, Plan)
  - Penunjang Order (Checklist Lab Hematologi, Kimia Darah, Urin, Rontgen, USG, CT-Scan)
  - Internal Consultation transfer modal
  - Selesai & SKDP print modal

- [ ] **Step 5: Run tests and verify PASS**

Run: `"C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe" -m pytest pasien/tests_management.py -k test_rajal -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/
git commit -m "feat(pasien): outpatient queue calling states, direct SOAP, Lab/Rad order, internal consult, SKDP"
```

---

### Task 5: End-to-End Verification & Production Build

**Files:**
- Test: `pasien/tests_management.py` (Full comprehensive test suite)
- Static assets: `manage.py collectstatic`

**Interfaces:**
- Validates the entire flow from Pendaftaran -> IGD / Rajal -> Disposisi -> Ranap / Pulang / SKDP.

- [ ] **Step 1: Run complete Django management check and test suite**

Run:
`"C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe" manage.py check`
`"C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe" -m pytest pasien/tests_management.py -v`
Expected: 0 issues, all tests PASS.

- [ ] **Step 2: Collect static assets**

Run: `"C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe" manage.py collectstatic --noinput`
Expected: All assets compiled and post-processed cleanly.

- [ ] **Step 3: Final Git Commit and Push to Master**

```bash
git add .
git commit -m "feat(pasien): complete clinical patient management workflow according to operational manual"
git push origin master
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-04-clinical-patient-management-enhancement.md`. Please review the plan. Does it capture what you want?
