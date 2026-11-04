# Dasbor Pendaftaran Integrasi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate NIK/DPJP bridging (BPJS V-Claim + SatuSehat simulation), staff shift & logbook, and quick RME/queue actions into the existing `pasien:pendaftaran_dashboard` registration desk.

**Architecture:** One dashboard, no new sidebar menu. Additive only: two new admission models (`JadwalDinusAdmission`, `LogbookHarianAdmission`), one small bridging service module, four new POST views + one JSON GET view, and template edits to `templates/pasien/pendaftaran_dashboard.html` (Tab 8 pane, NIK auto-fill JS, data-poli DPJP filter, table action buttons). Reuses existing `KunjunganPasien` TTV/antrean fields — no duplicate tables.

**Tech Stack:** Django 5.x, Bootstrap 5 (tabs/modals already in template), Django `TestCase` + test client, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-04-dasbor-pendaftaran-bridging-logbook-rme-design.md`

## Global Constraints

- Repo URL convention is `pasien:api_*` / `pasien:pendaftaran_*` (see `pasien/urls.py`) — the spec's `/api/v1/cek-nik/` path is implemented as `api/bridging/peserta/` to match the live catalogue.
- DPJP filtering is **client-side** via `data-poli` attributes; no `/filter-dpjp/` endpoint is created (static 24-option list — YAGNI).
- All new bridging responses are explicitly **simulasi** (no real BPJS/SatuSehat server), matching existing `api_cek_bpjs`.
- Copy/labels are Bahasa Indonesia; verbose names match existing `pasien/models.py` style.
- Do not modify existing endpoints `api_cek_nik`, `api_cek_bpjs`, or the two-box form flow (`tests_revisi_pendaftaran_dua_kotak.py`, `tests_revisi_pendaftaran_formulir.py` must stay green).
- Windows: run tests with `$env:PYTHONIOENCODING="utf-8"; python manage.py test ...` (seed migrations print unicode).

## Review Focus

- NIK that is 16 digits but unknown locally — auto-fill must show simulated V-Claim data, never a blank/500 page.
- NIK shorter than 16 digits or non-numeric — no fetch, no crash, feedback cleared.
- Poliklinik with no mapped DPJP (e.g. after map drift) — dropdown must not end up with zero selectable options (fallback: show all).
- Queue call on an already `BATAL` visit — button hidden; POST must not resurrect cancelled visits.
- Logbook/jadwal POST with empty `kegiatan` / invalid `shift` — rejected with error message, no row created.

---

### Task 1: DPJP → Poliklinik mapping constant

**Files:**
- Modify: `pasien/models.py` (append after `DPJP_CHOICES`, ends line 252)
- Test: `pasien/tests_pendaftaran_integrasi.py` (create)

**Interfaces:**
- Consumes: `POLIKLINIK_CHOICES` (models.py:207), `DPJP_CHOICES` (models.py:227)
- Produces: `DPJP_POLI_MAP: dict[str, tuple[str, ...]]` — poli code → DPJP values; used by Task 7 view context and template `data-poli`.

- [ ] **Step 1: Write the failing test**

Create `pasien/tests_pendaftaran_integrasi.py`:

```python
from django.test import TestCase
from pasien.models import DPJP_CHOICES, DPJP_POLI_MAP, POLIKLINIK_CHOICES


class DPJPPoliMapTest(TestCase):
    def test_every_dpjp_mapped_to_at_least_one_poli(self):
        mapped = {dpjp for dpjps in DPJP_POLI_MAP.values() for dpjp in dpjps}
        for val, _label in DPJP_CHOICES:
            self.assertIn(val, mapped, f'{val} tidak ter-map ke poliklinik manapun')

    def test_map_contains_only_known_dpjp_and_poli(self):
        dpjp_vals = {val for val, _ in DPJP_CHOICES}
        poli_vals = {val for val, _ in POLIKLINIK_CHOICES}
        for poli, dpjps in DPJP_POLI_MAP.items():
            self.assertIn(poli, poli_vals)
            for dpjp in dpjps:
                self.assertIn(dpjp, dpjp_vals)

    def test_every_poli_has_at_least_one_dpjp(self):
        for poli, _label in POLIKLINIK_CHOICES:
            self.assertIn(poli, DPJP_POLI_MAP, f'{poli} tidak punya DPJP')
            self.assertTrue(DPJP_POLI_MAP[poli])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi -v 2`
Expected: FAIL — `ImportError: cannot import name 'DPJP_POLI_MAP'`

- [ ] **Step 3: Write minimal implementation**

Append to `pasien/models.py` after line 252 (after `DPJP_CHOICES` closing `]`):

```python
# Pemetaan DPJP → Poliklinik tujuan (untuk filter dropdown dinamis dasbor pendaftaran).
# Kunci = POLIKLINIK_CHOICES code; nilai = DPJP_CHOICES value.
DPJP_POLI_MAP = {
    'POLI_JANTUNG':        ('dr. Faisal, Sp.JP', 'dr. Bambang, Sp.JP, FIHA'),
    'POLI_PARU':           ('dr. Indah, Sp.P', 'dr. Gunawan, Sp.P, FAPSR'),
    'POLI_PENYAKIT_DALAM': ('dr. Budi Santoso, Sp.PD', 'dr. Siti Rahma, Sp.PD-KGEH'),
    'POLI_BEDAH':          ('dr. Hendra, Sp.B', 'dr. Ahmad, Sp.B, FICS'),
    'POLI_ANAK':           ('dr. Nurul, Sp.A', 'dr. Maya, Sp.A, M.Biomed'),
    'POLI_OBGYN':          ('dr. Rina, Sp.OG', 'dr. Dewi, Sp.OG(K)'),
    'POLI_MATA':           ('dr. Farida, Sp.M',),
    'POLI_SARAF':          ('dr. Eko, Sp.S',),
    'POLI_THT':            ('dr. Haryanto, Sp.THT-KL',),
    'POLI_GIGI':           ('drg. Amanda, Sp.KG', 'drg. Rizki'),
    'POLI_ORTHO':          ('dr. Kevin, Sp.OT',),
    'POLI_KULIT':          ('dr. Citra, Sp.DV',),
    'POLI_JIWA':           ('dr. Hadi, Sp.KJ',),
    'REHAB_MEDIK':         ('dr. Lina, Sp.KFR',),
    'POLI_ENDOKRIN':       ('dr. Siti Rahma, Sp.PD-KGEH',),
    'POLI_BSARAF':         ('dr. Hendra, Sp.B',),
    'POLI_UMUM':           ('dr. Pratama', 'dr. Intan', 'dr. Jaga IGD'),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi -v 2`
Expected: PASS, 3 tests, 0 failed

- [ ] **Step 5: Commit**

```bash
git add pasien/models.py pasien/tests_pendaftaran_integrasi.py
git commit -m "feat(pasien): add DPJP to poliklinik mapping constant"
```

---

### Task 2: Admission shift & logbook models + migration

**Files:**
- Modify: `pasien/models.py` (append at end of file)
- Create: migration via `makemigrations` (expected `pasien/migrations/0015_*.py`)
- Test: `pasien/tests_pendaftaran_integrasi.py` (extend)

**Interfaces:**
- Consumes: `User` (models.py:6 — file imports `User` directly, no `settings` import exists; match file idiom), `timezone` (add `from django.utils import timezone` to models.py imports in this task)
- Produces: `JadwalDinusAdmission` (fields: `petugas`, `tanggal`, `shift`, `status_kehadiran`, `catatan`, `created_at`; `SHIFT_CHOICES`), `LogbookHarianAdmission` (fields: `petugas`, `tanggal`, `jam_aktivitas`, `kegiatan`, `kendala`, `created_at`)

- [ ] **Step 1: Write the failing test**

Append to `pasien/tests_pendaftaran_integrasi.py`:

```python
from django.contrib.auth.models import User
from django.utils import timezone
from pasien.models import JadwalDinusAdmission, LogbookHarianAdmission


class AdmissionShiftLogbookModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas_loket', password='password123')

    def test_create_jadwal_dinus_defaults(self):
        j = JadwalDinusAdmission.objects.create(petugas=self.user, tanggal='2026-11-04', shift='PAGI')
        self.assertEqual(j.status_kehadiran, 'HADIR')
        self.assertEqual(str(j), f'{self.user.username} — 2026-11-04 Pagi (07:00 - 14:00)')

    def test_create_logbook_defaults(self):
        log = LogbookHarianAdmission.objects.create(
            petugas=self.user, kegiatan='Verifikasi berkas 12 pasien BPJS')
        self.assertEqual(log.tanggal, timezone.localdate())
        self.assertIsNotNone(log.jam_aktivitas)
        self.assertIn('Verifikasi berkas', str(log))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.AdmissionShiftLogbookModelTest -v 2`
Expected: FAIL — `ImportError: cannot import name 'JadwalDinusAdmission'`

- [ ] **Step 3: Write minimal implementation**

First, add the timezone import at the top of `pasien/models.py` (after line 5 `from django.db import models`):

```python
from django.utils import timezone
```

Then append to end of `pasien/models.py`:

```python
# ── 10. Jadwal Dinus & Logbook Staf Pendaftaran/Admisi ───────────────────────

class JadwalDinusAdmission(models.Model):
    """Pencatatan shift dinas petugas loket pendaftaran & admisi."""
    SHIFT_CHOICES = [
        ('PAGI', 'Pagi (07:00 - 14:00)'),
        ('SIANG', 'Siang (14:00 - 21:00)'),
        ('MALAM', 'Malam (21:00 - 07:00)'),
    ]
    STATUS_KEHADIRAN_CHOICES = [
        ('HADIR', 'Hadir'),
        ('IZIN', 'Izin'),
        ('SAKIT', 'Sakit'),
        ('ALPHA', 'Alpha'),
    ]
    petugas = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jadwal_admission')
    tanggal = models.DateField('Tanggal Dinus')
    shift = models.CharField('Shift Kerja', max_length=10, choices=SHIFT_CHOICES)
    status_kehadiran = models.CharField('Status Kehadiran', max_length=12, choices=STATUS_KEHADIRAN_CHOICES, default='HADIR')
    catatan = models.CharField('Catatan', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Jadwal Dinus Pendaftaran'
        verbose_name_plural = 'Jadwal Dinus Pendaftaran'
        ordering = ['-tanggal', 'shift']

    def __str__(self):
        return f'{self.petugas.username} — {self.tanggal:%Y-%m-%d} {self.get_shift_display()}'


class LogbookHarianAdmission(models.Model):
    """Logbook akuntabilitas kinerja harian dan kendala staf loket pendaftaran."""
    petugas = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logbook_admission')
    tanggal = models.DateField('Tanggal Catatan', default=timezone.localdate)
    jam_aktivitas = models.TimeField('Jam Aktivitas', auto_now_add=True)
    kegiatan = models.TextField('Uraian Kegiatan Pelayanan')
    kendala = models.TextField('Kendala Operasional', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Logbook Harian Pendaftaran'
        verbose_name_plural = 'Logbook Harian Pendaftaran'
        ordering = ['-tanggal', '-jam_aktivitas']

    def __str__(self):
        return f'{self.petugas.username} {self.tanggal:%Y-%m-%d}: {self.kegiatan[:60]}'
```

Then generate the migration:

```bash
python manage.py makemigrations pasien
```

Expected new file `pasien/migrations/0015_*.py` with two `CreateModel` operations. If `makemigrations` prompts (it will not — no ambiguous names), accept defaults.

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.AdmissionShiftLogbookModelTest -v 2`
Expected: PASS, 2 tests, 0 failed

- [ ] **Step 5: Commit**

```bash
git add pasien/models.py pasien/migrations/0015_*.py
git commit -m "feat(pasien): add admission shift & logbook models"
```

---

### Task 3: Bridging service + `api_bridging_peserta` endpoint

**Files:**
- Create: `pasien/bridging_services.py`
- Modify: `pasien/views.py` (append view after `api_cek_bpjs`, ends line 1816)
- Modify: `pasien/urls.py` (add after line 53 `path('api/cek-nik/', ...)`)
- Test: `pasien/tests_pendaftaran_integrasi.py` (extend)

**Interfaces:**
- Consumes: `Pasien` (models.py), `JsonResponse` (already imported views.py:8)
- Produces:
  - `BPJSVClaimService.cek_peserta_by_nik(nik: str) -> dict` with keys `noKartu`, `nik`, `nama`, `tglLahir` (ISO `YYYY-MM-DD`), `sex` (`'L'`/`'P'`), `hakKelas`, `statusPeserta`; raises `ValueError` if not 16 digits numeric.
  - `SatuSehatService.get_patient_by_nik(nik: str) -> dict` FHIR-shaped: `resourceType='Patient'`, `id`, `name` (list with `text`), `gender`, `birthDate`, `identifier` (list with `system='https://fhir.kemkes.go.id/id/nik'`, `value`); raises `ValueError` on bad NIK.
  - URL name `pasien:api_bridging_peserta` at path `api/bridging/peserta/`.

- [ ] **Step 1: Write the failing test**

Append to `pasien/tests_pendaftaran_integrasi.py`:

```python
from datetime import date
from django.urls import reverse
from pasien.bridging_services import BPJSVClaimService, SatuSehatService
from pasien.models import Pasien


class BridgingServiceTest(TestCase):
    def test_vclaim_valid_nik_returns_simulated_payload(self):
        p = BPJSVClaimService.cek_peserta_by_nik('3201234567890001')
        self.assertEqual(p['nik'], '3201234567890001')
        self.assertIn(p['sex'], ('L', 'P'))
        self.assertEqual(p['statusPeserta'], 'AKTIF')
        date.fromisoformat(p['tglLahir'])  # raises if not ISO
        self.assertTrue(p['noKartu'])

    def test_vclaim_invalid_nik_raises(self):
        with self.assertRaises(ValueError):
            BPJSVClaimService.cek_peserta_by_nik('12345')
        with self.assertRaises(ValueError):
            BPJSVClaimService.cek_peserta_by_nik('32012345678900AB')

    def test_satusehat_patient_shape(self):
        p = SatuSehatService.get_patient_by_nik('3201234567890001')
        self.assertEqual(p['resourceType'], 'Patient')
        self.assertIn(p['gender'], ('male', 'female'))
        self.assertEqual(p['identifier'][0]['system'], 'https://fhir.kemkes.go.id/id/nik')
        self.assertEqual(p['identifier'][0]['value'], '3201234567890001')


class ApiBridgingPesertaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas_bridging', password='password123')
        self.client.login(username='petugas_bridging', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-BRIDGE-001', nik='3201000000000009', nama_lengkap='Siti Nurhaliza',
            tanggal_lahir='1988-02-02', jenis_kelamin='P', no_bpjs='0001234567890')

    def test_local_pasien_wins(self):
        res = self.client.get(reverse('pasien:api_bridging_peserta') + '?nik=3201000000000009')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['source'], 'LOKAL')
        self.assertEqual(data['peserta']['nama'], 'Siti Nurhaliza')
        self.assertEqual(data['peserta']['sex'], 'P')

    def test_unknown_nik_falls_back_to_vclaim_simulation(self):
        res = self.client.get(reverse('pasien:api_bridging_peserta') + '?nik=3209998887770001')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['source'], 'BPJS_VCLAIM')
        self.assertIn('tglLahir', data['peserta'])

    def test_missing_nik_returns_400(self):
        res = self.client.get(reverse('pasien:api_bridging_peserta'))
        self.assertEqual(res.status_code, 400)

    def test_short_nik_returns_400(self):
        res = self.client.get(reverse('pasien:api_bridging_peserta') + '?nik=123')
        self.assertEqual(res.status_code, 400)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.BridgingServiceTest pasien.tests_pendaftaran_integrasi.ApiBridgingPesertaTest -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'pasien.bridging_services'`

- [ ] **Step 3: Write minimal implementation**

Create `pasien/bridging_services.py`:

```python
"""Bridging kepesertaan — V-Claim BPJS & SatuSehat (SIMULASI).

Belum terhubung server BPJS/Kemenkes produksi. Payload mengikuti format
V-Claim 2.x dan FHIR Patient agar kontrak konsumsi UI tidak berubah saat
integrasi nyata dipasang.
"""
from datetime import date


def _valid_nik(nik):
    nik = (nik or '').strip()
    if not (nik.isdigit() and len(nik) == 16):
        raise ValueError('NIK harus 16 digit numerik.')
    return nik


class BPJSVClaimService:
    """Simulasi layanan BPJS V-Claim: cek kepesertaan by NIK."""

    @staticmethod
    def cek_peserta_by_nik(nik):
        nik = _valid_nik(nik)
        # Derivasi deterministik dari digit NIK agar simulasi stabil per-NIK.
        tahun = 1950 + (int(nik[6:8]) % 60)
        bulan = 1 + (int(nik[8:10]) % 12)
        hari = 1 + (int(nik[10:12]) % 28)
        sex = 'P' if int(nik[6]) >= 5 else 'L'  # konvensi NIK: +40 pada digit ke-7 untuk perempuan
        return {
            'noKartu': '000' + nik[:10],
            'nik': nik,
            'nama': '',  # nama hanya tersedia dari data lokal atau response server asli
            'tglLahir': date(tahun, bulan, hari).isoformat(),
            'sex': sex,
            'hakKelas': '3',
            'statusPeserta': 'AKTIF',
        }


class SatuSehatService:
    """Simulasi SatuSehat Kemenkes: Patient resource by NIK."""

    @staticmethod
    def get_patient_by_nik(nik):
        nik = _valid_nik(nik)
        return {
            'resourceType': 'Patient',
            'id': nik,
            'identifier': [{
                'system': 'https://fhir.kemkes.go.id/id/nik',
                'value': nik,
            }],
            'gender': 'female' if int(nik[6]) >= 5 else 'male',
            'birthDate': BPJSVClaimService.cek_peserta_by_nik(nik)['tglLahir'],
            'name': [{'text': ''}],
        }
```

Append to `pasien/views.py` after line 1816 (end of `api_cek_bpjs`):

```python
@login_required
def api_bridging_peserta(request):
    """Auto-fill identitas pasien by NIK: data lokal dulu, fallback simulasi V-Claim BPJS."""
    nik = request.GET.get('nik', '').strip()
    if not nik:
        return JsonResponse({'status': 'error', 'message': 'Parameter nik wajib.'}, status=400)

    p = Pasien.objects.filter(nik=nik).first()
    if p:
        return JsonResponse({
            'status': 'success',
            'source': 'LOKAL',
            'peserta': {
                'nama': p.nama_lengkap,
                'tglLahir': p.tanggal_lahir.isoformat() if p.tanggal_lahir else '',
                'sex': p.jenis_kelamin,
                'noKartu': p.no_bpjs or '',
                'hakKelas': '',
                'statusPeserta': '',
            },
        })

    try:
        peserta = BPJSVClaimService.cek_peserta_by_nik(nik)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'success', 'source': 'BPJS_VCLAIM', 'peserta': peserta})
```

In `pasien/views.py` add to the imports from `.models` (line 16-21 block) — no model import needed here. Add service import after line 23 (`from .satusehat import ...`):

```python
from .bridging_services import BPJSVClaimService, SatuSehatService
```

In `pasien/urls.py` add after line 53:

```python
    path('api/bridging/peserta/', views.api_bridging_peserta, name='api_bridging_peserta'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.BridgingServiceTest pasien.tests_pendaftaran_integrasi.ApiBridgingPesertaTest -v 2`
Expected: PASS, 7 tests, 0 failed

- [ ] **Step 5: Commit**

```bash
git add pasien/bridging_services.py pasien/views.py pasien/urls.py
git commit -m "feat(pasien): add BPJS V-Claim & SatuSehat bridging service with peserta API"
```

---

### Task 4: Quick TTV (RME awal) & queue-call views

**Files:**
- Modify: `pasien/views.py` (append after `pendaftaran_route`, ends ~line 975)
- Modify: `pasien/urls.py` (add after line 32)
- Test: `pasien/tests_pendaftaran_integrasi.py` (extend)

**Interfaces:**
- Consumes: `KunjunganPasien` TTV fields (`ttv_sistole`, `ttv_diastole`, `ttv_nadi`, `ttv_rr`, `ttv_suhu`, `ttv_spo2`), `status_antrean` + `STATUS_ANTREAN_CHOICES`, `require_POST` (imported views.py:9), `messages` (views.py:5)
- Produces: URL names `pasien:pendaftaran_ttv_simpan` (`pendaftaran/kunjungan/<pk>/ttv/`), `pasien:pendaftaran_antrean_status` (`pendaftaran/kunjungan/<pk>/antrean/`). Both `POST`-only, redirect to `pasien:pendaftaran_dashboard`.

- [ ] **Step 1: Write the failing test**

Append to `pasien/tests_pendaftaran_integrasi.py`:

```python
from pasien.models import KunjunganPasien, Pasien


class PendaftaranTtvAntreanTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='loket_ttv', password='password123')
        self.client.login(username='loket_ttv', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-TTV-001', nik='3201000000000011', nama_lengkap='Budi Harjanto',
            tanggal_lahir='1980-01-01', jenis_kelamin='L')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='RAJAL', no_kunjungan='RAJAL-TTV-001',
            poliklinik='POLI_JANTUNG', dpjp='dr. Faisal, Sp.JP', penjamin='BPJS')

    def test_ttv_saved_and_redirects_to_dashboard(self):
        res = self.client.post(reverse('pasien:pendaftaran_ttv_simpan', args=[self.kunjungan.pk]), {
            'ttv_sistole': '120', 'ttv_diastole': '80', 'ttv_nadi': '78',
            'ttv_rr': '18', 'ttv_suhu': '36.5', 'ttv_spo2': '98',
            'catatan_admisi': 'Keluhan nyeri dada sejak pagi',
        })
        self.assertRedirects(res, reverse('pasien:pendaftaran_dashboard'))
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.ttv_sistole, 120)
        self.assertEqual(self.kunjungan.ttv_diastole, 80)
        self.assertEqual(self.kunjungan.ttv_nadi, 78)
        self.assertEqual(self.kunjungan.ttv_rr, 18)
        self.assertEqual(float(self.kunjungan.ttv_suhu), 36.5)
        self.assertEqual(self.kunjungan.ttv_spo2, 98)
        self.assertEqual(self.kunjungan.catatan_admisi, 'Keluhan nyeri dada sejak pagi')

    def test_ttv_empty_values_become_null_not_error(self):
        res = self.client.post(reverse('pasien:pendaftaran_ttv_simpan', args=[self.kunjungan.pk]), {
            'ttv_sistole': '', 'ttv_diastole': '', 'ttv_nadi': '',
            'ttv_rr': '', 'ttv_suhu': '', 'ttv_spo2': '',
        })
        self.assertEqual(res.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertIsNone(self.kunjungan.ttv_sistole)

    def test_antrean_panggil_updates_status(self):
        res = self.client.post(reverse('pasien:pendaftaran_antrean_status', args=[self.kunjungan.pk]),
                               {'status_antrean': 'DIPANGGIL'})
        self.assertRedirects(res, reverse('pasien:pendaftaran_dashboard'))
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status_antrean, 'DIPANGGIL')

    def test_antrean_selesai_updates_status(self):
        res = self.client.post(reverse('pasien:pendaftaran_antrean_status', args=[self.kunjungan.pk]),
                               {'status_antrean': 'SELESAI'})
        self.assertEqual(res.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status_antrean, 'SELESAI')

    def test_antrean_invalid_status_ignored(self):
        res = self.client.post(reverse('pasien:pendaftaran_antrean_status', args=[self.kunjungan.pk]),
                               {'status_antrean': 'HANCUR'})
        self.assertEqual(res.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status_antrean, 'MENUNGGU')

    def test_ttv_get_not_allowed(self):
        res = self.client.get(reverse('pasien:pendaftaran_ttv_simpan', args=[self.kunjungan.pk]))
        self.assertEqual(res.status_code, 405)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranTtvAntreanTest -v 2`
Expected: FAIL — `NoReverseMatch` for `pasien:pendaftaran_ttv_simpan`

- [ ] **Step 3: Write minimal implementation**

Append to `pasien/views.py` after `pendaftaran_route`:

```python
@login_required
@require_POST
def pendaftaran_ttv_simpan(request, pk):
    """Simpan TTV awal (RME ringkas) dari loket pendaftaran & admisi."""
    k = get_object_or_404(KunjunganPasien, pk=pk)

    def _int(name):
        val = request.POST.get(name, '').strip()
        return int(val) if val else None

    k.ttv_sistole = _int('ttv_sistole')
    k.ttv_diastole = _int('ttv_diastole')
    k.ttv_nadi = _int('ttv_nadi')
    k.ttv_rr = _int('ttv_rr')
    k.ttv_spo2 = _int('ttv_spo2')
    suhu = request.POST.get('ttv_suhu', '').strip()
    k.ttv_suhu = float(suhu) if suhu else None
    catatan = request.POST.get('catatan_admisi', '').strip()
    if catatan:
        k.catatan_admisi = catatan
    k.save()
    messages.success(request, f'TTV {k.pasien.nama_lengkap} berhasil disimpan.')
    return redirect('pasien:pendaftaran_dashboard')


@login_required
@require_POST
def pendaftaran_antrean_status(request, pk):
    """Panggil / layani / selesaikan antrean loket pendaftaran."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    st = request.POST.get('status_antrean', '')
    allowed = ['DIPANGGIL', 'SEDANG_DILAYANI', 'SELESAI']
    if st in allowed and k.status != 'BATAL':
        k.status_antrean = st
        k.save(update_fields=['status_antrean'])
        messages.info(request, f'Antrean {k.nomor_antrean or k.no_kunjungan} ({k.pasien.nama_lengkap}) → {k.get_status_antrean_display()}.')
    return redirect('pasien:pendaftaran_dashboard')
```

In `pasien/urls.py` add after line 32 (`pendaftaran/<int:pk>/route/`):

```python
    path('pendaftaran/kunjungan/<int:pk>/ttv/', views.pendaftaran_ttv_simpan, name='pendaftaran_ttv_simpan'),
    path('pendaftaran/kunjungan/<int:pk>/antrean/', views.pendaftaran_antrean_status, name='pendaftaran_antrean_status'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranTtvAntreanTest -v 2`
Expected: PASS, 6 tests, 0 failed

- [ ] **Step 5: Commit**

```bash
git add pasien/views.py pasien/urls.py
git commit -m "feat(pasien): add quick TTV & queue-call actions from registration desk"
```

---

### Task 5: Logbook & shift-dinus POST views + dashboard context

**Files:**
- Modify: `pasien/views.py` (append views; extend `pendaftaran_dashboard` ctx lines 855-881)
- Modify: `pasien/urls.py` (add after the Task 4 lines)
- Test: `pasien/tests_pendaftaran_integrasi.py` (extend)

**Interfaces:**
- Consumes: `JadwalDinusAdmission`, `LogbookHarianAdmission` (Task 2), `DPJP_POLI_MAP` (Task 1), `POLIKLINIK_CHOICES`, `DPJP_CHOICES` (already imported views.py:19)
- Produces: URL names `pasien:pendaftaran_logbook_simpan` (`pendaftaran/logbook/simpan/`), `pasien:pendaftaran_jadwal_simpan` (`pendaftaran/jadwal/simpan/`). Dashboard ctx gains `jadwal_hari_ini`, `logbook_hari_ini`, `shift_choices`, `dpjp_choices_poli` (list of `(val, label, poli_string)`).

- [ ] **Step 1: Write the failing test**

Append to `pasien/tests_pendaftaran_integrasi.py`:

```python
from pasien.models import JadwalDinusAdmission, LogbookHarianAdmission


class PendaftaranLogbookJadwalTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='loket_log', password='password123')
        self.client.login(username='loket_log', password='password123')

    def test_logbook_valid_post_creates_row(self):
        res = self.client.post(reverse('pasien:pendaftaran_logbook_simpan'), {
            'kegiatan': 'Verifikasi 8 berkas BPJS pagi ini',
            'kendala': 'Server V-Claim lambat',
        })
        self.assertRedirects(res, reverse('pasien:pendaftaran_dashboard'))
        log = LogbookHarianAdmission.objects.get(petugas=self.user)
        self.assertEqual(log.kegiatan, 'Verifikasi 8 berkas BPJS pagi ini')
        self.assertEqual(log.kendala, 'Server V-Claim lambat')

    def test_logbook_empty_kegiatan_rejected(self):
        res = self.client.post(reverse('pasien:pendaftaran_logbook_simpan'), {
            'kegiatan': '   ', 'kendala': '',
        })
        self.assertRedirects(res, reverse('pasien:pendaftaran_dashboard'))
        self.assertFalse(LogbookHarianAdmission.objects.filter(petugas=self.user).exists())

    def test_jadwal_valid_post_creates_row(self):
        res = self.client.post(reverse('pasien:pendaftaran_jadwal_simpan'), {
            'tanggal': '2026-11-04', 'shift': 'MALAM',
            'status_kehadiran': 'HADIR', 'catatan': 'Jaga loket',
        })
        self.assertRedirects(res, reverse('pasien:pendaftaran_dashboard'))
        j = JadwalDinusAdmission.objects.get(petugas=self.user)
        self.assertEqual(j.shift, 'MALAM')

    def test_jadwal_invalid_shift_rejected(self):
        res = self.client.post(reverse('pasien:pendaftaran_jadwal_simpan'), {
            'tanggal': '2026-11-04', 'shift': 'FOGGING',
        })
        self.assertRedirects(res, reverse('pasien:pendaftaran_dashboard'))
        self.assertFalse(JadwalDinusAdmission.objects.filter(petugas=self.user).exists())

    def test_dashboard_context_has_shift_logbook_and_dpjp_poli(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('jadwal_hari_ini', res.context)
        self.assertIn('logbook_hari_ini', res.context)
        self.assertEqual(len(res.context['shift_choices']), 3)
        # setiap dpjp punya string data-poli (boleh kosong hanya bila belum ter-map)
        mapped = {dpjp for dpjps in DPJP_POLI_MAP.values() for dpjp in dpjps}
        for val, _label, polis in res.context['dpjp_choices_poli']:
            if val in mapped:
                self.assertTrue(polis, f'{val} kehilangan data-poli')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranLogbookJadwalTest -v 2`
Expected: FAIL — `NoReverseMatch` for `pasien:pendaftaran_logbook_simpan`

- [ ] **Step 3: Write minimal implementation**

Append to `pasien/views.py` after `pendaftaran_antrean_status`:

```python
@login_required
@require_POST
def pendaftaran_logbook_simpan(request):
    """Catat kegiatan & kendala harian staf pendaftaran (akuntabilitas loket)."""
    kegiatan = request.POST.get('kegiatan', '').strip()
    if not kegiatan:
        messages.error(request, 'Uraian kegiatan wajib diisi.')
        return redirect('pasien:pendaftaran_dashboard')
    LogbookHarianAdmission.objects.create(
        petugas=request.user,
        kegiatan=kegiatan,
        kendala=request.POST.get('kendala', '').strip(),
    )
    messages.success(request, 'Logbook harian tersimpan.')
    return redirect('pasien:pendaftaran_dashboard')


@login_required
@require_POST
def pendaftaran_jadwal_simpan(request):
    """Catat shift dinas staf pendaftaran."""
    shift = request.POST.get('shift', '')
    if shift not in dict(JadwalDinusAdmission.SHIFT_CHOICES):
        messages.error(request, 'Shift tidak valid.')
        return redirect('pasien:pendaftaran_dashboard')
    JadwalDinusAdmission.objects.create(
        petugas=request.user,
        tanggal=request.POST.get('tanggal') or timezone.localdate(),
        shift=shift,
        status_kehadiran=request.POST.get('status_kehadiran', 'HADIR'),
        catatan=request.POST.get('catatan', '').strip(),
    )
    messages.success(request, 'Jadwal dinas tersimpan.')
    return redirect('pasien:pendaftaran_dashboard')
```

Extend the imports in `pasien/views.py` line 16-21 model import block — add `JadwalDinusAdmission, LogbookHarianAdmission, DPJP_POLI_MAP`:

```python
from .models import (
    Pasien, KunjunganPasien, Bed, Ruangan, CPPT, AsesmenRisikoKlinis,
    BillingItem, DischargeRecord, ResepElektronik, ResepDetail,
    OrderPenunjang, POLIKLINIK_CHOICES, DPJP_CHOICES, BookingKamar,
    GeneralConsentRawatInap, generate_no_rm, generate_no_kunjungan,
    JadwalDinusAdmission, LogbookHarianAdmission, DPJP_POLI_MAP
)
```

In `pendaftaran_dashboard` (views.py:855-881), add to the `ctx` dict after the `'dpjp_choices': DPJP_CHOICES,` line:

```python
        'shift_choices':         JadwalDinusAdmission.SHIFT_CHOICES,
        'jadwal_hari_ini':       JadwalDinusAdmission.objects.filter(tanggal=today).select_related('petugas'),
        'logbook_hari_ini':      LogbookHarianAdmission.objects.filter(tanggal=today).select_related('petugas')[:50],
        'dpjp_choices_poli':     [
            (val, label, ' '.join(p for p, dps in DPJP_POLI_MAP.items() if val in dps))
            for val, label in DPJP_CHOICES
        ],
```

In `pasien/urls.py` add after the Task 4 lines:

```python
    path('pendaftaran/logbook/simpan/', views.pendaftaran_logbook_simpan, name='pendaftaran_logbook_simpan'),
    path('pendaftaran/jadwal/simpan/', views.pendaftaran_jadwal_simpan, name='pendaftaran_jadwal_simpan'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranLogbookJadwalTest -v 2`
Expected: PASS, 5 tests, 0 failed

- [ ] **Step 5: Commit**

```bash
git add pasien/views.py pasien/urls.py
git commit -m "feat(pasien): add logbook & shift-dinus entry views with dashboard context"
```

---

### Task 6: Template — Tab 8 pane (Shift & Logbook)

**Files:**
- Modify: `templates/pasien/pendaftaran_dashboard.html` (nav after line 141; pane before line 837)
- Test: `pasien/tests_pendaftaran_integrasi.py` (extend)

**Interfaces:**
- Consumes: ctx `jadwal_hari_ini`, `logbook_hari_ini`, `shift_choices` (Task 5); URL names `pasien:pendaftaran_jadwal_simpan`, `pasien:pendaftaran_logbook_simpan`
- Produces: rendered pane `#pane-shift` with two tables and two POST forms; test asserts strings.

- [ ] **Step 1: Write the failing test**

Append to `pasien/tests_pendaftaran_integrasi.py`:

```python
class PendaftaranDashboardTabTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='loket_tab', password='password123')
        self.client.login(username='loket_tab', password='password123')

    def test_tab_shift_logbook_rendered(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="tab-shift"')
        self.assertContains(res, 'id="pane-shift"')
        self.assertContains(res, 'Shift &amp; Logbook Staf')
        self.assertContains(res, reverse('pasien:pendaftaran_logbook_simpan'))
        self.assertContains(res, reverse('pasien:pendaftaran_jadwal_simpan'))
        self.assertContains(res, 'Belum ada jadwal dinas')

    def test_tab_shift_logbook_lists_rows(self):
        JadwalDinusAdmission.objects.create(petugas=self.user, tanggal=timezone.localdate(), shift='PAGI')
        LogbookHarianAdmission.objects.create(petugas=self.user, kegiatan='Scan ulang berkas BPJS')
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(res, 'loket_tab')
        self.assertContains(res, 'Scan ulang berkas BPJS')
        self.assertContains(res, 'Pagi (07:00 - 14:00)')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranDashboardTabTest -v 2`
Expected: FAIL — `assertContains` cannot find `id="tab-shift"`

- [ ] **Step 3: Write minimal implementation**

In `templates/pasien/pendaftaran_dashboard.html`, add the nav button after line 141 (the `</li>` closing the tab-utility item, before `</ul>` at line 142):

```html
                <li class="nav-item" role="presentation">
                    <button class="nav-link text-nowrap" id="tab-shift" data-bs-toggle="tab" data-bs-target="#pane-shift" type="button" role="tab">
                        <i class="bi bi-clipboard-check me-1 text-success"></i> 8. Shift &amp; Logbook Staf
                    </button>
                </li>
```

Add the pane immediately before line 837 (the `</div>` that closes `.tab-content`, anchored by `<!-- TABEL KUNJUNGAN HARI INI -->`):

```html
            <!-- TAB 8: SHIFT & LOGBOOK STAF PENDAFTARAN -->
            <div class="tab-pane fade p-4" id="pane-shift" role="tabpanel">
                <h6 class="fw-bold mb-3 text-dark">Shift &amp; Logbook Staf Loket Pendaftaran</h6>
                <div class="row g-3">
                    <div class="col-lg-6">
                        <div class="card border h-100">
                            <div class="card-header bg-white d-flex justify-content-between align-items-center py-2">
                                <span class="fw-bold small"><i class="bi bi-person-badge me-1 text-primary"></i> Jadwal Dinus Hari Ini</span>
                                <button class="btn btn-sm btn-outline-primary" data-bs-toggle="modal" data-bs-target="#modalJadwal">
                                    <i class="bi bi-plus-lg"></i> Tambah
                                </button>
                            </div>
                            <div class="card-body p-0">
                                {% if jadwal_hari_ini %}
                                <div class="table-responsive">
                                    <table class="table table-sm table-hover align-middle mb-0 small">
                                        <thead class="table-light text-muted">
                                            <tr><th class="ps-3">Petugas</th><th>Shift</th><th>Kehadiran</th><th>Catatan</th></tr>
                                        </thead>
                                        <tbody>
                                            {% for j in jadwal_hari_ini %}
                                            <tr>
                                                <td class="ps-3 fw-semibold">{{ j.petugas.get_full_name|default:j.petugas.username }}</td>
                                                <td>{{ j.get_shift_display }}</td>
                                                <td><span class="badge {% if j.status_kehadiran == 'HADIR' %}bg-success-subtle text-success{% else %}bg-warning-subtle text-dark{% endif %}">{{ j.get_status_kehadiran_display }}</span></td>
                                                <td><small class="text-muted">{{ j.catatan|default:"-" }}</small></td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                {% else %}
                                <div class="text-center py-4">
                                    <i class="bi bi-calendar-x text-muted fs-3"></i>
                                    <p class="text-muted small mt-2 mb-0">Belum ada jadwal dinas untuk hari ini.</p>
                                </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card border h-100">
                            <div class="card-header bg-white d-flex justify-content-between align-items-center py-2">
                                <span class="fw-bold small"><i class="bi bi-journal-text me-1 text-success"></i> Logbook Harian Staf</span>
                                <button class="btn btn-sm btn-outline-success" data-bs-toggle="modal" data-bs-target="#modalLogbook">
                                    <i class="bi bi-plus-lg"></i> Tambah
                                </button>
                            </div>
                            <div class="card-body p-0">
                                {% if logbook_hari_ini %}
                                <div class="table-responsive">
                                    <table class="table table-sm table-hover align-middle mb-0 small">
                                        <thead class="table-light text-muted">
                                            <tr><th class="ps-3">Jam</th><th>Petugas</th><th>Kegiatan &amp; Kendala</th></tr>
                                        </thead>
                                        <tbody>
                                            {% for log in logbook_hari_ini %}
                                            <tr>
                                                <td class="ps-3 font-monospace">{{ log.jam_aktivitas|date:"H:i" }}</td>
                                                <td class="text-nowrap">{{ log.petugas.get_full_name|default:log.petugas.username }}</td>
                                                <td>
                                                    {{ log.kegiatan }}
                                                    {% if log.kendala %}<div class="small text-danger"><i class="bi bi-exclamation-triangle me-1"></i>{{ log.kendala }}</div>{% endif %}
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                {% else %}
                                <div class="text-center py-4">
                                    <i class="bi bi-journal-x text-muted fs-3"></i>
                                    <p class="text-muted small mt-2 mb-0">Belum ada catatan logbook hari ini.</p>
                                </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

```

Add the two modals immediately after the new pane (still before `<!-- TABEL KUNJUNGAN HARI INI -->`):

```html
            <!-- MODAL TAMBAH JADWAL DINIS -->
            <div class="modal fade" id="modalJadwal" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <form method="POST" action="{% url 'pasien:pendaftaran_jadwal_simpan' %}">
                            {% csrf_token %}
                            <div class="modal-header">
                                <h6 class="modal-title fw-bold">Tambah Jadwal Dinus</h6>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="mb-3">
                                    <label class="form-label small fw-semibold">Tanggal</label>
                                    <input type="date" name="tanggal" class="form-control form-control-sm" value="{{ today_iso|default:'' }}">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small fw-semibold">Shift Kerja</label>
                                    <select name="shift" class="form-select form-select-sm" required>
                                        {% for code, label in shift_choices %}
                                        <option value="{{ code }}">{{ label }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small fw-semibold">Status Kehadiran</label>
                                    <select name="status_kehadiran" class="form-select form-select-sm">
                                        <option value="HADIR">Hadir</option>
                                        <option value="IZIN">Izin</option>
                                        <option value="SAKIT">Sakit</option>
                                        <option value="ALPHA">Alpha</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small fw-semibold">Catatan</label>
                                    <input type="text" name="catatan" class="form-control form-control-sm" placeholder="Opsional...">
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Batal</button>
                                <button type="submit" class="btn btn-primary btn-sm">Simpan Jadwal</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <!-- MODAL TAMBAH LOGBOOK -->
            <div class="modal fade" id="modalLogbook" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <form method="POST" action="{% url 'pasien:pendaftaran_logbook_simpan' %}">
                            {% csrf_token %}
                            <div class="modal-header">
                                <h6 class="modal-title fw-bold">Tambah Logbook Harian</h6>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="mb-3">
                                    <label class="form-label small fw-semibold">Uraian Kegiatan <span class="text-danger">*</span></label>
                                    <textarea name="kegiatan" class="form-control form-control-sm" rows="3" required placeholder="Contoh: verifikasi berkas 10 pasien BPJS..."></textarea>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label small fw-semibold">Kendala Operasional</label>
                                    <textarea name="kendala" class="form-control form-control-sm" rows="2" placeholder="Opsional..."></textarea>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Batal</button>
                                <button type="submit" class="btn btn-success btn-sm">Simpan Logbook</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

```

Note: the Jadwal modal date input uses `{{ today_iso|default:'' }}`. Add `today_iso` to the dashboard ctx in this task (views.py `pendaftaran_dashboard`): `'today_iso': today.isoformat(),` — one line, keeps the modal prefilled with today.

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranDashboardTabTest -v 2`
Expected: PASS, 2 tests, 0 failed

- [ ] **Step 5: Commit**

```bash
git add templates/pasien/pendaftaran_dashboard.html pasien/views.py
git commit -m "feat(ui): add shift & logbook tab to registration dashboard"
```

---

### Task 7: Template — NIK auto-fill + data-poli DPJP filter

**Files:**
- Modify: `templates/pasien/pendaftaran_dashboard.html` (ids on Kotak 2 inputs; option loops lines 267-269 & 539-541; `syncDpjpLama`/`syncDpjpBaru` lines 1431-1454; new JS)
- Test: `pasien/tests_pendaftaran_integrasi.py` (extend)

**Interfaces:**
- Consumes: URL `pasien:api_bridging_peserta` (Task 3), ctx `dpjp_choices_poli` (Task 5)
- Produces: Kotak 2 input ids `namaLengkapBaru`, `tglLahirBaru`, `bpjsBaruInput`; DPJP `<option data-poli="...">`; rewritten `syncDpjpLama()`/`syncDpjpBaru()`; new `cekNikBridging()` fetch.

- [ ] **Step 1: Write the failing test**

Append to `pasien/tests_pendaftaran_integrasi.py`:

```python
class PendaftaranBridgingUiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='loket_ui', password='password123')
        self.client.login(username='loket_ui', password='password123')

    def test_kotak_baru_inputs_have_autofill_ids(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(res, 'id="namaLengkapBaru"')
        self.assertContains(res, 'id="tglLahirBaru"')
        self.assertContains(res, 'id="bpjsBaruInput"')

    def test_dpjp_options_carry_data_poli(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(res, 'data-poli="POLI_MATA"')  # dr. Farida, Sp.M hanya di Poli Mata
        self.assertContains(res, 'data-poli="POLI_ANAK"')

    def test_nik_bridging_js_present(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(res, 'cekNikBridging')
        self.assertContains(res, reverse('pasien:api_bridging_peserta'))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranBridgingUiTest -v 2`
Expected: FAIL — `assertContains` cannot find `id="namaLengkapBaru"`

- [ ] **Step 3: Write minimal implementation**

Edit 1 — Kotak 2 Nama Lengkap input (line 340):

```html
                                                <input type="text" name="nama_lengkap" id="namaLengkapBaru" class="form-control form-control-sm" required placeholder="Nama lengkap pasien tanpa singkatan...">
```

Edit 2 — Kotak 2 Tanggal Lahir input (line 356):

```html
                                                <input type="date" name="tanggal_lahir" id="tglLahirBaru" class="form-control form-control-sm" required>
```

Edit 3 — Kotak 2 No. BPJS input (line 452):

```html
                                                <input type="text" name="no_bpjs" id="bpjsBaruInput" class="form-control form-control-sm font-monospace" placeholder="13 digit nomor kartu BPJS...">
```

Edit 4 — DPJP option loop for `dpjpSelectLama` (lines 267-269):

```html
                                                        {% for val, label, polis in dpjp_choices_poli %}
                                                        <option value="{{ val }}" data-poli="{{ polis }}">{{ label }}</option>
                                                        {% endfor %}
```

Edit 5 — DPJP option loop for `dpjpSelectBaru` (lines 539-541): identical replacement as Edit 4.

Edit 6 — replace the whole block lines 1431-1454 (`// 4. SYNC DPJP PASIEN LAMA & BARU` through the end of `syncDpjpBaru`) with:

```js
    // 4. FILTER DPJP BERDASARKAN POLIKLINIK (data-poli)
    function filterDpjpByPoli(selectId, poliVal) {
        const dpjpSelect = document.getElementById(selectId);
        if (!dpjpSelect) return;
        let matched = false;
        for (let opt of dpjpSelect.options) {
            if (!opt.value) continue;
            const polis = (opt.getAttribute('data-poli') || '').split(' ');
            const show = !poliVal || polis.indexOf(poliVal) !== -1;
            opt.hidden = !show;
            opt.disabled = !show;
            if (show && poliVal && !matched) {
                opt.selected = true;
                matched = true;
            }
        }
        if (poliVal && !matched) dpjpSelect.value = '';
    }

    function syncDpjpLama() {
        filterDpjpByPoli('dpjpSelectLama', document.getElementById('poliSelectLama').value);
    }

    function syncDpjpBaru() {
        filterDpjpByPoli('dpjpSelectBaru', document.getElementById('poliSelectBaru').value);
    }
```

Edit 7 — append the NIK bridging auto-fill JS just before the closing `</script>` of the page (after `togglePenjaminBaru`'s closing brace at line 1472, before `</script>` line 1474):

```js
    // 7. BRIDGING NIK → AUTO-FILL IDENTITAS (V-Claim BPJS simulasi)
    (function() {
        const nikInput = document.getElementById('nikBaruInput');
        const nikFeedback = document.getElementById('nikBaruFeedback');
        if (!nikInput) return;

        function setFeedback(html) {
            if (nikFeedback) nikFeedback.innerHTML = html;
        }

        window.cekNikBridging = function(nik) {
            if (!/^\d{16}$/.test(nik)) {
                setFeedback('');
                return;
            }
            setFeedback('<span class="text-muted"><span class="spinner-border spinner-border-sm me-1"></span>Cek kepesertaan BPJS...</span>');
            fetch('{% url "pasien:api_bridging_peserta" %}?nik=' + encodeURIComponent(nik), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.status !== 'success') {
                        setFeedback('<span class="text-danger small">' + (data.message || 'NIK tidak dapat diverifikasi.') + '</span>');
                        return;
                    }
                    const s = data.peserta;
                    const badge = data.source === 'LOKAL'
                        ? '<span class="badge bg-success-subtle text-success border">Data lokal (pasien terdaftar)</span>'
                        : '<span class="badge bg-info-subtle text-info border">Terverifikasi V-Claim BPJS (simulasi)</span>';
                    setFeedback(badge);
                    if (s.nama) {
                        const nama = document.getElementById('namaLengkapBaru');
                        if (nama && !nama.value) nama.value = s.nama;
                    }
                    if (s.tglLahir) {
                        const tgl = document.getElementById('tglLahirBaru');
                        if (tgl && !tgl.value) tgl.value = s.tglLahir;
                    }
                    if (s.sex === 'L') {
                        const jkL = document.getElementById('jkL');
                        if (jkL) jkL.checked = true;
                    } else if (s.sex === 'P') {
                        const jkP = document.getElementById('jkP');
                        if (jkP) jkP.checked = true;
                    }
                    if (s.noKartu) {
                        const bpjs = document.getElementById('bpjsBaruInput');
                        if (bpjs && !bpjs.value) bpjs.value = s.noKartu;
                        const penjamin = document.getElementById('penjaminBaru');
                        if (penjamin && !penjamin.value) penjamin.value = 'BPJS';
                        if (typeof togglePenjaminBaru === 'function') togglePenjaminBaru();
                    }
                })
                .catch(function() {
                    setFeedback('<span class="text-warning small">Layanan bridging tidak merespons. Isi data manual.</span>');
                });
        };

        nikInput.addEventListener('input', function() {
            if (nikInput.value.length === 16) window.cekNikBridging(nikInput.value);
        });
    })();
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranBridgingUiTest -v 2`
Expected: PASS, 3 tests, 0 failed

- [ ] **Step 5: Commit**

```bash
git add templates/pasien/pendaftaran_dashboard.html
git commit -m "feat(ui): NIK auto-fill bridging & data-poli DPJP filter on registration dashboard"
```

---

### Task 8: Template — RME awal modal & queue-call buttons in today's table

**Files:**
- Modify: `templates/pasien/pendaftaran_dashboard.html` (action cell ~line 920-948; modals after `<!-- MODAL ROUTING ULANG -->` block)
- Test: `pasien/tests_pendaftaran_integrasi.py` (extend)

**Interfaces:**
- Consumes: URL names `pasien:pendaftaran_ttv_simpan`, `pasien:pendaftaran_antrean_status` (Task 4)
- Produces: per-row `#modalRme{{ k.pk }}` TTV form, `[RME Awal]` trigger button (badge when TTV exists), queue-call POST form (hidden `status_antrean`), antrean status badge in Status cell.

- [ ] **Step 1: Write the failing test**

Append to `pasien/tests_pendaftaran_integrasi.py`:

```python
class PendaftaranRmeAntreanUiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='loket_rme', password='password123')
        self.client.login(username='loket_rme', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-RME-001', nik='3201000000000021', nama_lengkap='Rina Wulandari',
            tanggal_lahir='1992-07-07', jenis_kelamin='P')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='RAJAL', no_kunjungan='RAJAL-RME-001',
            poliklinik='POLI_ANAK', dpjp='dr. Nurul, Sp.A', penjamin='BPJS',
            nomor_antrean='A-001', status_antrean='MENUNGGU')

    def test_rme_and_antrean_controls_rendered(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(res, 'modalRme%d' % self.kunjungan.pk)
        self.assertContains(res, reverse('pasien:pendaftaran_ttv_simpan', args=[self.kunjungan.pk]))
        self.assertContains(res, reverse('pasien:pendaftaran_antrean_status', args=[self.kunjungan.pk]))
        self.assertContains(res, 'RME Awal')
        self.assertContains(res, 'Panggil')

    def test_ttv_badge_shown_when_ttv_exists(self):
        self.kunjungan.ttv_sistole = 110
        self.kunjungan.save()
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(res, '</i> ✓')  # tombol RME bertanda ✓ saat TTV sudah terisi

    def test_cancelled_visit_has_no_call_button(self):
        self.kunjungan.status = 'BATAL'
        self.kunjungan.save()
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        content = res.content.decode()
        self.assertNotIn(reverse('pasien:pendaftaran_antrean_status', args=[self.kunjungan.pk]), content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranRmeAntreanUiTest -v 2`
Expected: FAIL — `assertContains` cannot find `modalRme1`

- [ ] **Step 3: Write minimal implementation**

Edit 1 — in the Status cell (line 915-919), append the antrean badge after the status badge `</span>`:

```html
                                {% if k.status != 'BATAL' %}
                                <br><span class="badge {% if k.status_antrean == 'MENUNGGU' %}bg-warning-subtle text-dark border{% elif k.status_antrean == 'DIPANGGIL' %}bg-info-subtle text-info border{% elif k.status_antrean == 'SELESAI' %}bg-success-subtle text-success border{% else %}bg-secondary-subtle border{% endif %}" style="font-size:.68rem;">
                                    <i class="bi bi-person-arms-up me-1"></i>{{ k.get_status_antrean_display }}
                                </span>
                                {% endif %}
```

Edit 2 — in the Aksi cell, insert the RME + queue buttons before the routing button (line 937):

```html
                                    {% if k.status != 'BATAL' %}
                                    <button class="btn btn-outline-success" data-bs-toggle="modal" data-bs-target="#modalRme{{ k.pk }}" title="Input RME Awal (TTV)">
                                        <i class="bi bi-clipboard2-pulse"></i>{% if k.ttv_sistole %} ✓{% endif %}
                                    </button>
                                    {% if k.status_antrean != 'DIPANGGIL' and k.status_antrean != 'SELESAI' %}
                                    <form method="POST" action="{% url 'pasien:pendaftaran_antrean_status' k.pk %}" class="d-inline">
                                        {% csrf_token %}
                                        <input type="hidden" name="status_antrean" value="DIPANGGIL">
                                        <button type="submit" class="btn btn-outline-info" title="Panggil Antrean Loket">
                                            <i class="bi bi-megaphone"></i>
                                        </button>
                                    </form>
                                    {% endif %}
                                    {% endif %}
```

Note: the existing routing button and Batal form remain unchanged below these.

Edit 3 — add the RME modal immediately after the existing `<!-- MODAL ROUTING ULANG -->` modal's closing tags (after line 1007 `</div>` which closes `#modalRoute{{ k.pk }}`, still inside the `{% for %}` loop):

```html
                        <!-- MODAL RME AWAL (TTV) -->
                        <div class="modal fade" id="modalRme{{ k.pk }}" tabindex="-1">
                            <div class="modal-dialog modal-dialog-centered">
                                <div class="modal-content">
                                    <form method="POST" action="{% url 'pasien:pendaftaran_ttv_simpan' k.pk %}">
                                        {% csrf_token %}
                                        <div class="modal-header">
                                            <h6 class="modal-title fw-bold">RME Awal (TTV) — {{ k.pasien.nama_lengkap }}</h6>
                                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                        </div>
                                        <div class="modal-body">
                                            <p class="small text-muted mb-3">Input tanda-tanda vital awal di loket sebelum pasien dipanggil ke poliklinik.</p>
                                            <div class="row g-2 mb-2">
                                                <div class="col-6">
                                                    <label class="form-label small fw-semibold">Sistole (mmHg)</label>
                                                    <input type="number" name="ttv_sistole" class="form-control form-control-sm" value="{{ k.ttv_sistole|default:'' }}" min="50" max="300">
                                                </div>
                                                <div class="col-6">
                                                    <label class="form-label small fw-semibold">Diastole (mmHg)</label>
                                                    <input type="number" name="ttv_diastole" class="form-control form-control-sm" value="{{ k.ttv_diastole|default:'' }}" min="30" max="200">
                                                </div>
                                            </div>
                                            <div class="row g-2 mb-2">
                                                <div class="col-4">
                                                    <label class="form-label small fw-semibold">Nadi (bpm)</label>
                                                    <input type="number" name="ttv_nadi" class="form-control form-control-sm" value="{{ k.ttv_nadi|default:'' }}" min="30" max="250">
                                                </div>
                                                <div class="col-4">
                                                    <label class="form-label small fw-semibold">RR (x/menit)</label>
                                                    <input type="number" name="ttv_rr" class="form-control form-control-sm" value="{{ k.ttv_rr|default:'' }}" min="5" max="60">
                                                </div>
                                                <div class="col-4">
                                                    <label class="form-label small fw-semibold">SpO2 (%)</label>
                                                    <input type="number" name="ttv_spo2" class="form-control form-control-sm" value="{{ k.ttv_spo2|default:'' }}" min="50" max="100">
                                                </div>
                                            </div>
                                            <div class="mb-2">
                                                <label class="form-label small fw-semibold">Suhu (°C)</label>
                                                <input type="number" step="0.1" name="ttv_suhu" class="form-control form-control-sm" value="{{ k.ttv_suhu|default:'' }}" min="34" max="43">
                                            </div>
                                            <div class="mb-2">
                                                <label class="form-label small fw-semibold">Catatan Admisi</label>
                                                <textarea name="catatan_admisi" class="form-control form-control-sm" rows="2" placeholder="Keluhan utama / catatan loket...">{{ k.catatan_admisi }}</textarea>
                                            </div>
                                        </div>
                                        <div class="modal-footer">
                                            <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Batal</button>
                                            <button type="submit" class="btn btn-success btn-sm">Simpan TTV</button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        </div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien.tests_pendaftaran_integrasi.PendaftaranRmeAntreanUiTest -v 2`
Expected: PASS, 3 tests, 0 failed

- [ ] **Step 5: Commit**

```bash
git add templates/pasien/pendaftaran_dashboard.html
git commit -m "feat(ui): add RME awal modal & queue-call buttons to today's visit table"
```

---

### Task 9: Full regression — pasien app suite

**Files:**
- No file changes expected. Fix only failures caused by this plan's tasks.

**Interfaces:**
- Consumes: everything above
- Produces: green `python manage.py test pasien`

- [ ] **Step 1: Run the whole pasien app suite**

Run: `$env:PYTHONIOENCODING="utf-8"; python manage.py test pasien -v 1`
Expected: 0 failed. This covers the pre-existing revision suites (`tests_revisi_pendaftaran_dua_kotak.py`, `tests_revisi_pendaftaran_formulir.py`) that must stay green per Global Constraints.

- [ ] **Step 2: If anything fails**

Fix in the owning task's files only; re-run the failing module, then re-run the full suite. Do not weaken pre-existing assertions.

- [ ] **Step 3: Commit any fix**

```bash
git add -A
git commit -m "fix(pasien): regression fixes from registration dashboard integration"
```
