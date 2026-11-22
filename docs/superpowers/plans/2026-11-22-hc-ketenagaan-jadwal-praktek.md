# Human Capital: Pola Ketenagaan Komprehensif & Jadwal Praktek Dokter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the ARIMA Human Capital module (`sdm` app) with a comprehensive staffing-pattern engine covering all four workforce families (Medis, Keperawatan & Kebidanan, Nakes Lain, Non-Medis), seed 25 fictional medical staff, and build a full Doctor Practice Schedule sub-module inside HC that bridges to the existing APM `JadwalDokterPoli` in the `pasien` app — including leave/substitute management, on-time compliance, quota control, and Risk Register escalation.

**Architecture:**
The `sdm` Django app already has rich models for employees (`Pegawai`, `MasterProfesiPegawai`), placement (`PenempatanPegawai`), formation planning (`RencanaFormasi`, `BebanKerja`, `JamKerjaEfektif`, `StandarKetenagaan`), credentials (`PengajuanKredensial`, `PenugasanKlinis`), documents (`DokumenPegawai`, `AturanDokumen`), and training (`ProgramDiklat`). The APM patient-facing schedule lives in `pasien.JadwalDokterPoli` with plain-text doctor names and no FK to `Pegawai`. This plan adds three vertical slices: (1) a comprehensive staffing-pattern dashboard with gap analysis across all rumpun, (2) a structured doctor-schedule sub-module under `/human-capital/jadwal-praktek/` with rutin/harian separation, leave management, and substitute assignment, and (3) a sync bridge so APM always reflects the HC-authoritative schedule.

**Tech Stack:** Django 4.2+, Python 3.11, Supabase Postgres, Tailwind CSS (via existing template system), ReportLab (existing PDF generation)

**Spec:** Source documents:
- `Modul Pola Ketenagaan Komprehensif.docx` — 4-rumpun staffing model
- `Master_Staf_Medis_ARIMA.xlsx` — 25 fictional doctors (seed data)
- `Modul_Jadwal_Praktek_Dokter_ARIMA.docx` — schedule module spec
- `jadwal praktek dokter.pdf` — consolidated requirements

## Existing Codebase Findings

### What Already Exists (no need to rebuild)
1. **`MasterProfesiPegawai`** (`sdm/models/pegawai.py:184`) — already has `KELUARGA_CHOICES` with MEDIS, KEPERAWATAN_KEBIDANAN, NAKES_LAIN, NON_KLINIS. Maps directly to the 4 rumpun in the spec.
2. **`Pegawai`** — has `kategori` (PPA/NON_PPA), `profesi`, `profesi_master` FK, `jenjang_master` FK, `status`.
3. **`PenempatanPegawai`** — placement with unit_kerja FK, alokasi_fte, date range.
4. **`RencanaFormasi` + `AktivitasBebanKerja` + `HasilFormasi`** — activity-based FTE planning with immutable approved results.
5. **`BebanKerja`** — WISN/activity-based workload snapshots.
6. **`JamKerjaEfektif`** — approved productive minutes per year.
7. **`StandarKetenagaan`** — reviewed regulatory ratios.
8. **`AturanDokumen`** — document compliance rules per kategori/profesi.
9. **`ProgramDiklat` + `PesertaDiklat` + `SertifikatDiklat`** — training tracking.
10. **`PenugasanKlinis`** — SPK with nomor_spk, berlaku_mulai/sampai, is_active.
11. **`JadwalDokterPoli`** (`pasien/models.py:1575`) — APM schedule with text-based nama_dokter, hari_praktik, kuota, status. No FK to Pegawai.

### What Needs to Be Built
1. **Pola Ketenagaan Dashboard** — gap-analysis heatmap aggregating existing formasi data across all 4 rumpun, with risk escalation triggers.
2. **Jadwal Praktek Models** — `JadwalPraktekRutin`, `JadwalPraktekHarian`, `PengajuanIzinDokter`, `TindakLanjutPasienJadwal`, `LogAuditJadwal` in the `sdm` app.
3. **Jadwal Praktek Views/Templates** — full CRUD under `/human-capital/jadwal-praktek/`.
4. **APM Bridge** — optional FK from `JadwalDokterPoli.pegawai` → `Pegawai`, sync service.
5. **Seed Data** — management command to load 25 doctors from the Excel spec.

### Changes to Existing Models
- `JadwalDokterPoli`: add nullable FK `pegawai` → `sdm.Pegawai` (backward-compatible).
- `Pegawai`: no schema changes needed.
- Navigation (`sdm/navigation.py`): add "Jadwal Praktek" menu item under HC sidebar.

## Global Constraints

- All new models go in `sdm/models/` as separate files, registered in `sdm/models/__init__.py`.
- All new URLs go in `sdm/urls.py` under `app_name = 'sdm'`.
- Templates follow existing pattern: `templates/sdm/` with Tailwind classes.
- Tests use `--keepdb` for speed; each test file seeds its own data.
- Migrations are additive only — no destructive changes to existing tables.
- All Indonesian UI copy; English code identifiers.
- STARKES 2024 compliance: KPS, TKRS, HPK, AK-P/PAP chapter alignment.
- Existing `calculate_formasi()` logic is not modified; new gap-analysis reads its outputs.

## Review Focus

1. **Credential validation on schedule publish** — a doctor with expired SPK/SIP must not have an active schedule; the spec demands this but no existing code enforces it across JadwalDokterPoli.
2. **Conflict detection across poli** — a doctor scheduled in two poliklinik at overlapping times must be caught; neither the spec nor existing code handles this.
3. **Quota split JKN/non-JKN** — the spec requires separate quotas but `JadwalDokterPoli.kuota_maksimal` is a single integer; the bridge must reconcile this.
4. **Leave cascade to APM** — when a doctor is marked on leave in HC, the APM kiosk must reflect LIBUR status immediately; the sync must be atomic.
5. **Risk Register FK** — the spec references escalation to Risk Register; the `akreditasi` app's risk model must be verified before creating FKs.

---

## Task Overview

| # | Task | New Files | Modified Files |
|---|------|-----------|----------------|
| 1 | Seed Master Profesi & 25 Staf Medis | `sdm/management/commands/seed_staf_medis.py` | `sdm/models/__init__.py` |
| 2 | Jadwal Praktek Models (Rutin, Harian, Izin, Tindak Lanjut, Audit Log) | `sdm/models/jadwal_praktek.py` | `sdm/models/__init__.py` |
| 3 | APM Bridge — JadwalDokterPoli FK to Pegawai | `pasien/migrations/0XXX_*.py` | `pasien/models.py` |
| 4 | Jadwal Praktek Services (conflict check, credential validation, quota, sync) | `sdm/services/jadwal_praktek.py` | — |
| 5 | Pola Ketenagaan Gap Analysis Service | `sdm/services/pola_ketenagaan.py` | — |
| 6 | Jadwal Praktek Views & URLs | `sdm/jadwal_views.py` | `sdm/urls.py`, `sdm/navigation.py` |
| 7 | Pola Ketenagaan Dashboard Enhancement | — | `sdm/views.py`, `sdm/services/` |
| 8 | Templates — Jadwal Praktek (list, detail, form, matrix) | `templates/sdm/jadwal_praktek/*.html` | — |
| 9 | Templates — Pola Ketenagaan Dashboard Cards & Gap Table | — | `templates/sdm/dashboard.html` |
| 10 | Tests — Models & Services | `sdm/tests/test_jadwal_praktek.py`, `sdm/tests/test_pola_ketenagaan.py` | — |

---

### Task 1: Seed Master Profesi & 25 Staf Medis

**Files:**
- Create: `sdm/management/commands/seed_staf_medis.py`
- Modify: (none — MasterProfesiPegawai already exists)

**Interfaces:**
- Produces: 25 `Pegawai` rows with `profesi_master` FK set, 5 `MasterProfesiPegawai` entries (Dokter Umum, Sp.JP, Sp.PD, Sp.B, Sub Spesialis)

**Context:** The Excel spec provides 25 fictional doctors. `MasterProfesiPegawai` already has `keluarga` MEDIS. `Pegawai` already has `kategori` PPA/NON_PPA and `profesi_master` FK.

- [ ] **Step 1: Create management command file**

Create `sdm/management/commands/seed_staf_medis.py`:

```python
"""Seed 25 fictional medical staff from the Master_Staf_Medis_ARIMA spec."""
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from sdm.models import MasterProfesiPegawai, Pegawai


PROFESI_SEED = [
    ('DR_UMUM', 'Dokter Umum', 'MEDIS'),
    ('SP_JP', 'Dokter Spesialis Jantung dan Pembuluh Darah', 'MEDIS'),
    ('SP_PD', 'Dokter Spesialis Penyakit Dalam', 'MEDIS'),
    ('SP_B', 'Dokter Spesialis Bedah', 'MEDIS'),
    ('SUB_SP', 'Sub Spesialis', 'MEDIS'),
]

STAF_SEED = [
    # (profesi_code, nama, kategori, status, tanggal_masuk)
    ('DR_UMUM', 'dr. Aditya Pratama Wijaya', 'PPA', 'AKTIF', '2021-01-12'),
    ('DR_UMUM', 'dr. Nabila Putri Kusuma', 'PPA', 'AKTIF', '2022-05-03'),
    ('DR_UMUM', 'dr. Reza Mahendra Saputra', 'PPA', 'AKTIF', '2023-08-15'),
    ('DR_UMUM', 'dr. Larasati Dewi Anggraini', 'PPA', 'AKTIF', '2020-02-10'),
    ('DR_UMUM', 'dr. Farhan Hakim Nugroho', 'PPA', 'AKTIF', '2026-09-01'),
    ('SP_JP', 'dr. Hendra Gunawan, Sp.JP(K)', 'PPA', 'AKTIF', '2019-03-14'),
    ('SP_JP', 'dr. Ratna Sari Dewi, Sp.JP', 'PPA', 'AKTIF', '2021-07-20'),
    ('SP_JP', 'dr. Bima Sakti Perdana, Sp.JP', 'PPA', 'AKTIF', '2022-11-05'),
    ('SP_JP', 'dr. Cynthia Maharani, Sp.JP', 'PPA', 'AKTIF', '2023-04-18'),
    ('SP_JP', 'dr. Dimas Arya Ramadhan, Sp.JP', 'PPA', 'AKTIF', '2026-08-10'),
    ('SP_PD', 'dr. Bambang Sutrisno, Sp.PD', 'PPA', 'AKTIF', '2018-02-02'),
    ('SP_PD', 'dr. Maya Kartika Sari, Sp.PD', 'PPA', 'AKTIF', '2020-06-19'),
    ('SP_PD', 'dr. Irfan Maulana Yusuf, Sp.PD', 'PPA', 'AKTIF', '2021-09-11'),
    ('SP_PD', 'dr. Dian Puspita Ningrum, Sp.PD', 'PPA', 'AKTIF', '2023-01-22'),
    ('SP_PD', 'dr. Galih Prakoso Wibowo, Sp.PD', 'PPA', 'AKTIF', '2024-05-14'),
    ('SP_B', 'dr. Agung Nugroho Santoso, Sp.B', 'PPA', 'AKTIF', '2017-04-08'),
    ('SP_B', 'dr. Rina Melati Putri, Sp.B', 'PPA', 'AKTIF', '2020-08-25'),
    ('SP_B', 'dr. Taufik Hidayatullah, Sp.B', 'PPA', 'AKTIF', '2021-10-12'),
    ('SP_B', 'dr. Eko Prasetyo Utomo, Sp.B', 'PPA', 'AKTIF', '2023-03-03'),
    ('SP_B', 'dr. Fajar Siddiq Alamsyah, Sp.B', 'PPA', 'AKTIF', '2026-07-15'),
    ('SUB_SP', 'Prof. dr. Suryo Hadiwijoyo, Sp.PD-KGEH', 'PPA', 'AKTIF', '2016-01-10'),
    ('SUB_SP', 'dr. Kartika Candra Kirana, Sp.B(K)Onk', 'PPA', 'AKTIF', '2019-05-17'),
    ('SUB_SP', 'dr. Wahyu Setiawan, Sp.JP(K)FIHA', 'PPA', 'AKTIF', '2021-09-21'),
    ('SUB_SP', 'dr. Novianti Rahmawati, Sp.PD-KHOM', 'PPA', 'AKTIF', '2022-02-09'),
    ('SUB_SP', 'dr. Darmawan Kusuma, Sp.B-KBD', 'PPA', 'AKTIF', '2023-06-14'),
]


class Command(BaseCommand):
    help = 'Seed 25 fictional medical staff per ARIMA spec'

    def handle(self, *args, **options):
        for code, nama, keluarga in PROFESI_SEED:
            MasterProfesiPegawai.objects.get_or_create(
                code=code, defaults={'nama': nama, 'keluarga': keluarga}
            )
            self.stdout.write(f'  Profesi: {code} — {nama}')

        created_count = 0
        for prof_code, nama, kat, status, tgl in STAF_SEED:
            profesi_obj = MasterProfesiPegawai.objects.get(code=prof_code)
            _, created = Pegawai.objects.get_or_create(
                nama_lengkap=nama,
                defaults={
                    'kategori': kat,
                    'profesi': profesi_obj.nama,
                    'profesi_master': profesi_obj,
                    'status': status,
                    'data_origin': 'DEMO',
                },
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(
            f'Selesai: {created_count} pegawai baru dibuat.'
        ))
```

- [ ] **Step 2: Run the seed command locally**

```bash
python manage.py seed_staf_medis
```
Expected: 5 profesi created, 25 pegawai created (or skipped if already exist).

- [ ] **Step 3: Verify via Django shell**

```bash
python manage.py shell -c "from sdm.models import Pegawai; print(Pegawai.objects.filter(data_origin='DEMO', kategori='PPA').count())"
```
Expected: `25`

- [ ] **Step 4: Commit**

```bash
git add sdm/management/commands/seed_staf_medis.py
git commit -m "feat(sdm): seed 25 fictional medical staff from ARIMA spec"
```

---

### Task 2: Jadwal Praktek Models

**Files:**
- Create: `sdm/models/jadwal_praktek.py`
- Modify: `sdm/models/__init__.py` (add imports)

**Interfaces:**
- Consumes: `Pegawai`, `akreditasi.UnitKerja`, `PenugasanKlinis`
- Produces: `JadwalPraktekRutin`, `JadwalPraktekHarian`, `PengajuanIzinDokter`, `TindakLanjutPasienJadwal`, `LogAuditJadwal`

- [ ] **Step 1: Create `sdm/models/jadwal_praktek.py`**

```python
"""Doctor practice schedule models (HC-Jadwal Praktek)."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal


class JadwalPraktekRutin(models.Model):
    """Weekly recurring schedule template per doctor per poli."""
    HARI_CHOICES = [
        (0, 'Senin'), (1, 'Selasa'), (2, 'Rabu'),
        (3, 'Kamis'), (4, 'Jumat'), (5, 'Sabtu'), (6, 'Minggu'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dokter = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT,
        related_name='jadwal_rutin', verbose_name='Dokter',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='jadwal_praktek_rutin', verbose_name='Unit / Poliklinik',
    )
    ruang_praktek = models.CharField('Ruang Praktek', max_length=100, blank=True)
    hari = models.IntegerField('Hari', choices=HARI_CHOICES)
    jam_mulai = models.TimeField('Jam Mulai')
    jam_selesai = models.TimeField('Jam Selesai')
    durasi_per_pasien_menit = models.PositiveIntegerField(
        'Durasi per Pasien (Menit)', default=15
    )
    kuota_jkn = models.PositiveIntegerField('Kuota JKN/BPJS', default=20)
    kuota_non_jkn = models.PositiveIntegerField('Kuota Non-JKN/Umum', default=10)
    batas_daftar_menit = models.PositiveIntegerField(
        'Batas Daftar Sebelum Selesai (Menit)', default=60,
        help_text='Pendaftaran ditutup N menit sebelum jam_selesai.',
    )
    is_active = models.BooleanField('Aktif', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jadwal_rutin_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Jadwal Praktek Rutin'
        verbose_name_plural = 'Jadwal Praktek Rutin'
        ordering = ['dokter__nama_lengkap', 'hari', 'jam_mulai']
        indexes = [
            models.Index(
                fields=['dokter', 'hari', 'is_active'],
                name='sdm_jadwal_rutin_dr_hari_idx',
            ),
            models.Index(
                fields=['unit_kerja', 'hari', 'is_active'],
                name='sdm_jadwal_rutin_unit_hari_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(jam_selesai__gt=models.F('jam_mulai')),
                name='sdm_jadwal_rutin_jam_valid',
            ),
        ]

    @property
    def kuota_total(self):
        return self.kuota_jkn + self.kuota_non_jkn

    def clean(self):
        super().clean()
        if self.jam_mulai and self.jam_selesai and self.jam_selesai <= self.jam_mulai:
            raise ValidationError({
                'jam_selesai': 'Jam selesai harus setelah jam mulai.'
            })

    def __str__(self):
        hari_label = dict(self.HARI_CHOICES).get(self.hari, '?')
        return f'{self.dokter} — {hari_label} {self.jam_mulai}-{self.jam_selesai}'


class JadwalPraktekHarian(models.Model):
    """Daily operational schedule derived from rutin or manual override."""
    STATUS_CHOICES = [
        ('AKTIF', 'Aktif'),
        ('MUNDUR', 'Mundur / Tunda'),
        ('DIGANTIKAN', 'Digantikan'),
        ('BATAL', 'Batal / Libur'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jadwal_rutin = models.ForeignKey(
        JadwalPraktekRutin, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jadwal_harian',
        verbose_name='Jadwal Rutin Acuan',
    )
    tanggal = models.DateField('Tanggal')
    dokter_rencana = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT,
        related_name='jadwal_harian_rencana', verbose_name='Dokter Rencana',
    )
    dokter_aktual = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jadwal_harian_aktual',
        verbose_name='Dokter Aktual',
    )
    dokter_pengganti = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jadwal_harian_pengganti',
        verbose_name='Dokter Pengganti',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='jadwal_praktek_harian', verbose_name='Unit / Poliklinik',
    )
    jam_mulai_rencana = models.TimeField('Jam Mulai Rencana')
    jam_selesai_rencana = models.TimeField('Jam Selesai Rencana')
    jam_mulai_aktual = models.TimeField('Jam Mulai Aktual', null=True, blank=True)
    kuota_jkn = models.PositiveIntegerField('Kuota JKN', default=20)
    kuota_non_jkn = models.PositiveIntegerField('Kuota Non-JKN', default=10)
    terpakai_jkn = models.PositiveIntegerField('Terpakai JKN', default=0)
    terpakai_non_jkn = models.PositiveIntegerField('Terpakai Non-JKN', default=0)
    status_sesi = models.CharField(
        'Status Sesi', max_length=12, choices=STATUS_CHOICES, default='AKTIF',
    )
    alasan_perubahan = models.TextField('Alasan Perubahan', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Jadwal Praktek Harian'
        verbose_name_plural = 'Jadwal Praktek Harian'
        ordering = ['tanggal', 'jam_mulai_rencana']
        indexes = [
            models.Index(
                fields=['tanggal', 'unit_kerja', 'status_sesi'],
                name='sdm_jadwal_harian_tgl_idx',
            ),
            models.Index(
                fields=['dokter_rencana', 'tanggal'],
                name='sdm_jadwal_harian_dr_tgl_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['jadwal_rutin', 'tanggal'],
                condition=Q(jadwal_rutin__isnull=False),
                name='sdm_jadwal_harian_rutin_tgl_uniq',
            ),
        ]

    @property
    def kuota_total(self):
        return self.kuota_jkn + self.kuota_non_jkn

    @property
    def terpakai_total(self):
        return self.terpakai_jkn + self.terpakai_non_jkn

    @property
    def sisa_kuota(self):
        return max(0, self.kuota_total - self.terpakai_total)

    @property
    def keterlambatan_menit(self):
        if not self.jam_mulai_aktual or not self.jam_mulai_rencana:
            return None
        from datetime import datetime, date
        rencana = datetime.combine(date.min, self.jam_mulai_rencana)
        aktual = datetime.combine(date.min, self.jam_mulai_aktual)
        delta = (aktual - rencana).total_seconds() / 60
        return max(0, int(delta))

    def __str__(self):
        return f'{self.dokter_rencana} — {self.tanggal} @ {self.unit_kerja}'
```

- [ ] **Step 2: Add remaining models in same file (PengajuanIzinDokter, TindakLanjutPasienJadwal, LogAuditJadwal)**

Append to `sdm/models/jadwal_praktek.py`:

```python
class PengajuanIzinDokter(models.Model):
    """Leave/absence request for a doctor."""
    JENIS_CHOICES = [
        ('CUTI', 'Cuti Tahunan'),
        ('DIKLAT', 'Diklat / Seminar'),
        ('DINAS_LUAR', 'Dinas Luar'),
        ('SAKIT', 'Sakit'),
        ('MENDESAK', 'Keperluan Mendesak'),
    ]
    STATUS_CHOICES = [
        ('MENUNGGU', 'Menunggu Persetujuan'),
        ('DISETUJUI', 'Disetujui'),
        ('DITOLAK', 'Ditolak'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dokter = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT,
        related_name='izin_dokter', verbose_name='Dokter',
    )
    jenis = models.CharField('Jenis Ketidakhadiran', max_length=12, choices=JENIS_CHOICES)
    tanggal_mulai = models.DateField('Tanggal Mulai')
    tanggal_selesai = models.DateField('Tanggal Selesai')
    dokter_pengganti = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pengganti_izin',
        verbose_name='Usulan Dokter Pengganti',
    )
    status = models.CharField(
        'Status', max_length=10, choices=STATUS_CHOICES, default='MENUNGGU',
    )
    catatan = models.TextField('Catatan', blank=True)
    disetujui_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='izin_dokter_approved',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengajuan Izin Dokter'
        verbose_name_plural = 'Pengajuan Izin Dokter'
        ordering = ['-tanggal_mulai']
        constraints = [
            models.CheckConstraint(
                condition=Q(tanggal_selesai__gte=models.F('tanggal_mulai')),
                name='sdm_izin_dokter_tgl_valid',
            ),
        ]

    def __str__(self):
        return f'{self.dokter} — {self.get_jenis_display()} ({self.tanggal_mulai} s/d {self.tanggal_selesai})'


class TindakLanjutPasienJadwal(models.Model):
    """Follow-up record for patients affected by schedule changes."""
    STATUS_CHOICES = [
        ('BELUM', 'Belum Dihubungi'),
        ('DIALIHKAN', 'Dialihkan ke Pengganti'),
        ('RESCHEDULE', 'Dijadwalkan Ulang'),
        ('BATAL', 'Dibatalkan Pasien'),
        ('TERKONFIRMASI', 'Terkonfirmasi'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jadwal_harian = models.ForeignKey(
        JadwalPraktekHarian, on_delete=models.CASCADE,
        related_name='tindak_lanjut_pasien', verbose_name='Jadwal Harian',
    )
    nama_pasien = models.CharField('Nama Pasien', max_length=200)
    nomor_rm = models.CharField('Nomor RM', max_length=50, blank=True)
    no_telepon = models.CharField('No. Telepon', max_length=30, blank=True)
    status = models.CharField(
        'Status Konfirmasi', max_length=15, choices=STATUS_CHOICES, default='BELUM',
    )
    catatan = models.TextField('Catatan Petugas', blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tindak_lanjut_jadwal_updated',
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tindak Lanjut Pasien Jadwal'
        verbose_name_plural = 'Tindak Lanjut Pasien Jadwal'
        ordering = ['jadwal_harian__tanggal', 'created_at']

    def __str__(self):
        return f'{self.nama_pasien} — {self.get_status_display()}'


class LogAuditJadwal(models.Model):
    """Append-only audit trail for schedule changes."""
    JENIS_CHOICES = [
        ('BUAT', 'Jadwal Dibuat'),
        ('UBAH', 'Jadwal Diubah'),
        ('BATAL', 'Jadwal Dibatalkan'),
        ('GANTI_DOKTER', 'Dokter Diganti'),
        ('CATAT_JAM', 'Jam Aktual Dicatat'),
        ('ESKALASI', 'Eskalasi ke Risk Register'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jadwal_harian = models.ForeignKey(
        JadwalPraktekHarian, on_delete=models.CASCADE,
        related_name='audit_logs', verbose_name='Jadwal Harian',
    )
    waktu_aksi = models.DateTimeField('Waktu Aksi', default=timezone.now)
    pengguna = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_jadwal_created',
    )
    jenis_aksi = models.CharField('Jenis Aksi', max_length=15, choices=JENIS_CHOICES)
    ringkasan = models.TextField('Ringkasan Perubahan')
    snapshot_sebelum = models.JSONField('Data Sebelum', default=dict, blank=True)
    snapshot_sesudah = models.JSONField('Data Sesudah', default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log Audit Jadwal'
        verbose_name_plural = 'Log Audit Jadwal'
        ordering = ['-waktu_aksi']

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Log audit jadwal bersifat immutable.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_jenis_aksi_display()} — {self.waktu_aksi}'
```

- [ ] **Step 3: Register in `sdm/models/__init__.py`**

Add imports:
```python
from .jadwal_praktek import (
    JadwalPraktekRutin,
    JadwalPraktekHarian,
    PengajuanIzinDokter,
    TindakLanjutPasienJadwal,
    LogAuditJadwal,
)
```

Add to `__all__`:
```python
'JadwalPraktekRutin',
'JadwalPraktekHarian',
'PengajuanIzinDokter',
'TindakLanjutPasienJadwal',
'LogAuditJadwal',
```

- [ ] **Step 4: Generate and apply migration**

```bash
python manage.py makemigrations sdm --name jadwal_praktek_models
python manage.py migrate
```
Expected: 0 errors, 5 new tables created.

- [ ] **Step 5: Commit**

```bash
git add sdm/models/jadwal_praktek.py sdm/models/__init__.py sdm/migrations/
git commit -m "feat(sdm): add jadwal praktek models (rutin, harian, izin, tindak lanjut, audit log)"
```

---

### Task 3: APM Bridge — JadwalDokterPoli FK to Pegawai

**Files:**
- Modify: `pasien/models.py` (add `pegawai` FK to `JadwalDokterPoli`)
- Create: `pasien/migrations/XXXX_jadwal_dokter_pegawai_fk.py` (auto-generated)

**Interfaces:**
- Consumes: `sdm.Pegawai`
- Produces: nullable FK `JadwalDokterPoli.pegawai` enabling HC-authoritative sync

- [ ] **Step 1: Add nullable FK field to JadwalDokterPoli**

In `pasien/models.py`, add to `JadwalDokterPoli` class after `kode_dokter_bpjs`:

```python
pegawai = models.ForeignKey(
    'sdm.Pegawai', on_delete=models.SET_NULL,
    null=True, blank=True, related_name='jadwal_apm',
    verbose_name='Pegawai HC',
    help_text='Tautan ke master pegawai HC; kosong untuk jadwal lama.',
)
```

- [ ] **Step 2: Generate and apply migration**

```bash
python manage.py makemigrations pasien --name jadwal_dokter_pegawai_fk
python manage.py migrate
```

- [ ] **Step 3: Commit**

```bash
git add pasien/models.py pasien/migrations/
git commit -m "feat(pasien): add optional pegawai FK to JadwalDokterPoli for HC bridge"
```

---

### Task 4: Jadwal Praktek Services

**Files:**
- Create: `sdm/services/jadwal_praktek.py`

**Interfaces:**
- Consumes: `JadwalPraktekRutin`, `JadwalPraktekHarian`, `PengajuanIzinDokter`, `PenugasanKlinis`, `JadwalDokterPoli`
- Produces: `cek_bentrok_jadwal()`, `validasi_kredensial_dokter()`, `generate_jadwal_harian()`, `proses_izin_dokter()`, `sync_jadwal_ke_apm()`

- [ ] **Step 1: Create service file with conflict checker and credential validator**

Create `sdm/services/jadwal_praktek.py`:

```python
"""Jadwal Praktek business logic layer."""
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone


def cek_bentrok_jadwal(dokter_id, hari, jam_mulai, jam_selesai, exclude_id=None):
    """Check if a doctor already has overlapping schedule on the same day."""
    from sdm.models import JadwalPraktekRutin
    qs = JadwalPraktekRutin.objects.filter(
        dokter_id=dokter_id, hari=hari, is_active=True,
    ).filter(
        Q(jam_mulai__lt=jam_selesai) & Q(jam_selesai__gt=jam_mulai)
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def cek_bentrok_ruangan(unit_kerja_id, ruang, hari, jam_mulai, jam_selesai, exclude_id=None):
    """Check if a room is already occupied at overlapping times."""
    from sdm.models import JadwalPraktekRutin
    if not ruang:
        return False
    qs = JadwalPraktekRutin.objects.filter(
        unit_kerja_id=unit_kerja_id, ruang_praktek=ruang,
        hari=hari, is_active=True,
    ).filter(
        Q(jam_mulai__lt=jam_selesai) & Q(jam_selesai__gt=jam_mulai)
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def validasi_kredensial_dokter(dokter_id):
    """Return (is_valid, warnings) for a doctor's credential status."""
    from sdm.models import PenugasanKlinis, DokumenPegawai, VersiDokumen
    today = timezone.localdate()
    warnings = []

    # Check active SPK
    spk_aktif = PenugasanKlinis.objects.filter(
        employee_id=dokter_id, is_active=True,
        berlaku_mulai__lte=today,
    ).filter(
        Q(berlaku_sampai__isnull=True) | Q(berlaku_sampai__gte=today)
    ).exists()
    if not spk_aktif:
        warnings.append('SPK/RKK tidak aktif atau kedaluwarsa.')

    # Check SIP validity
    sip_docs = VersiDokumen.objects.filter(
        document__employee_id=dokter_id,
        document__jenis_berkas='SIP',
        status='VERIFIED',
    ).order_by('-valid_until').first()
    if not sip_docs:
        warnings.append('SIP belum terverifikasi.')
    elif sip_docs.valid_until and sip_docs.valid_until < today:
        warnings.append(f'SIP kedaluwarsa sejak {sip_docs.valid_until}.')
    elif sip_docs.valid_until and sip_docs.valid_until <= today + timedelta(days=30):
        warnings.append(f'SIP akan kedaluwarsa pada {sip_docs.valid_until}.')

    return (len(warnings) == 0, warnings)


def generate_jadwal_harian(tanggal):
    """Generate daily schedule rows from active rutin templates for a given date."""
    from sdm.models import JadwalPraktekRutin, JadwalPraktekHarian
    hari = tanggal.weekday()
    rutin_qs = JadwalPraktekRutin.objects.filter(hari=hari, is_active=True)
    created = 0
    for r in rutin_qs:
        _, was_created = JadwalPraktekHarian.objects.get_or_create(
            jadwal_rutin=r, tanggal=tanggal,
            defaults={
                'dokter_rencana': r.dokter,
                'unit_kerja': r.unit_kerja,
                'jam_mulai_rencana': r.jam_mulai,
                'jam_selesai_rencana': r.jam_selesai,
                'kuota_jkn': r.kuota_jkn,
                'kuota_non_jkn': r.kuota_non_jkn,
            },
        )
        if was_created:
            created += 1
    return created


def proses_izin_dokter(izin):
    """When leave is approved, mark affected daily schedules as BATAL or DIGANTIKAN."""
    from sdm.models import JadwalPraktekHarian, LogAuditJadwal
    affected = JadwalPraktekHarian.objects.filter(
        dokter_rencana=izin.dokter,
        tanggal__gte=izin.tanggal_mulai,
        tanggal__lte=izin.tanggal_selesai,
        status_sesi='AKTIF',
    )
    for jh in affected:
        old_status = jh.status_sesi
        if izin.dokter_pengganti:
            jh.status_sesi = 'DIGANTIKAN'
            jh.dokter_pengganti = izin.dokter_pengganti
            jh.dokter_aktual = izin.dokter_pengganti
        else:
            jh.status_sesi = 'BATAL'
        jh.alasan_perubahan = f'{izin.get_jenis_display()}: {izin.catatan}'
        jh.save()
        LogAuditJadwal.objects.create(
            jadwal_harian=jh,
            jenis_aksi='GANTI_DOKTER' if izin.dokter_pengganti else 'BATAL',
            ringkasan=f'Izin {izin.get_jenis_display()} disetujui. '
                       f'Status: {old_status} → {jh.status_sesi}',
        )


def sync_jadwal_ke_apm(jadwal_harian):
    """Sync HC schedule state to APM JadwalDokterPoli."""
    from pasien.models import JadwalDokterPoli
    if not jadwal_harian.dokter_rencana:
        return
    apm_rows = JadwalDokterPoli.objects.filter(
        pegawai=jadwal_harian.dokter_rencana
    )
    for apm in apm_rows:
        if jadwal_harian.status_sesi == 'BATAL':
            apm.status_ketersediaan = 'LIBUR'
        elif jadwal_harian.status_sesi == 'AKTIF':
            apm.status_ketersediaan = 'BUKA'
        apm.save(update_fields=['status_ketersediaan', 'updated_at'])
```

- [ ] **Step 2: Commit**

```bash
git add sdm/services/jadwal_praktek.py
git commit -m "feat(sdm): jadwal praktek services (conflict, credential, sync)"
```

---

### Task 5: Pola Ketenagaan Gap Analysis Service

**Files:**
- Create: `sdm/services/pola_ketenagaan.py`

**Interfaces:**
- Consumes: `HasilFormasi`, `PenempatanPegawai`, `MasterProfesiPegawai`, `Pegawai`
- Produces: `hitung_gap_ketenagaan()`, `hitung_metrik_dashboard()`

- [ ] **Step 1: Create gap analysis service**

Create `sdm/services/pola_ketenagaan.py`:

```python
"""Pola Ketenagaan gap analysis and dashboard metrics."""
from collections import defaultdict
from django.db.models import Count, Q, Sum
from django.utils import timezone


def hitung_gap_ketenagaan(unit_id=None, periode_tahun=None):
    """Calculate staffing gap per unit per profession family."""
    from sdm.models import (
        HasilFormasi, RencanaFormasi, PenempatanPegawai, Pegawai,
        MasterProfesiPegawai,
    )
    today = timezone.localdate()
    if not periode_tahun:
        periode_tahun = today.year

    # Get approved formasi results
    qs = HasilFormasi.objects.select_related(
        'rencana', 'rencana__unit_kerja',
    ).filter(
        rencana__status='APPROVED',
        rencana__periode_mulai__year__lte=periode_tahun,
        rencana__periode_selesai__year__gte=periode_tahun,
    )
    if unit_id:
        qs = qs.filter(rencana__unit_kerja_id=unit_id)

    results = []
    for hasil in qs:
        rencana = hasil.rencana
        # Find rumpun from profesi_master
        profesi_obj = MasterProfesiPegawai.objects.filter(
            nama__iexact=rencana.profesi
        ).first()
        rumpun = profesi_obj.keluarga if profesi_obj else 'NON_KLINIS'

        gap = hasil.gap_fte
        if gap > 0:
            status = 'Surplus'
            badge = 'info'
        elif gap == 0:
            status = 'Sesuai Standar'
            badge = 'success'
        elif gap >= -1:
            status = 'Defisit Ringan'
            badge = 'warning'
        else:
            status = 'Defisit Kritis'
            badge = 'danger'

        results.append({
            'unit_nama': rencana.unit_kerja.nama if rencana.unit_kerja else '',
            'unit_id': str(rencana.unit_kerja_id),
            'rumpun': rumpun,
            'profesi': rencana.profesi,
            'standar_fte': float(hasil.required_fte),
            'standar_headcount': hasil.required_headcount,
            'eksisting_fte': float(hasil.actual_fte),
            'gap_fte': float(gap),
            'status': status,
            'badge': badge,
            'formasi_id': str(rencana.id),
        })
    return results


def hitung_metrik_dashboard():
    """Aggregate HC dashboard metrics for the pola ketenagaan cards."""
    from sdm.models import (
        Pegawai, PenempatanPegawai, AturanDokumen,
        DokumenPegawai, VersiDokumen, ProgramDiklat,
        PesertaDiklat, MasterProfesiPegawai,
    )
    today = timezone.localdate()

    total_aktif = Pegawai.objects.filter(status='AKTIF').count()
    ppa_count = Pegawai.objects.filter(
        status='AKTIF', kategori='PPA'
    ).count()
    non_ppa_count = Pegawai.objects.filter(
        status='AKTIF', kategori='NON_PPA'
    ).count()

    # Distribution by keluarga profesi
    distribusi = list(
        Pegawai.objects.filter(
            status='AKTIF', profesi_master__isnull=False,
        ).values(
            'profesi_master__keluarga'
        ).annotate(
            jumlah=Count('id')
        ).order_by('profesi_master__keluarga')
    )

    # Document compliance
    doc_pending = VersiDokumen.objects.filter(
        status='PENDING',
        document__employee__status='AKTIF',
    ).count()
    doc_expiring = VersiDokumen.objects.filter(
        status='VERIFIED',
        valid_until__gte=today,
        valid_until__lte=today + timezone.timedelta(days=30),
        document__employee__status='AKTIF',
    ).count()
    doc_expired = VersiDokumen.objects.filter(
        status='VERIFIED',
        valid_until__lt=today,
        document__employee__status='AKTIF',
    ).count()

    # Gap summary
    gap_data = hitung_gap_ketenagaan()
    total_deficit = sum(1 for g in gap_data if g['badge'] == 'danger')

    return {
        'total_aktif': total_aktif,
        'ppa_count': ppa_count,
        'non_ppa_count': non_ppa_count,
        'distribusi_rumpun': distribusi,
        'doc_pending': doc_pending,
        'doc_expiring': doc_expiring,
        'doc_expired': doc_expired,
        'gap_data': gap_data,
        'total_deficit_kritis': total_deficit,
    }
```

- [ ] **Step 2: Commit**

```bash
git add sdm/services/pola_ketenagaan.py
git commit -m "feat(sdm): pola ketenagaan gap analysis and dashboard metrics service"
```

---

### Task 6: Jadwal Praktek Views & URLs

**Files:**
- Create: `sdm/jadwal_views.py`
- Modify: `sdm/urls.py` (add jadwal-praktek routes)
- Modify: `sdm/navigation.py` (add sidebar item)

**Interfaces:**
- Consumes: `JadwalPraktekRutin`, `JadwalPraktekHarian`, `PengajuanIzinDokter`, jadwal_praktek services
- Produces: views for list, create, detail, matrix, harian, izin, catat-jam

- [ ] **Step 1: Create `sdm/jadwal_views.py`**

```python
"""Views for the Jadwal Praktek Dokter sub-module."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from sdm.models import (
    JadwalPraktekRutin, JadwalPraktekHarian,
    PengajuanIzinDokter, LogAuditJadwal,
    Pegawai,
)
from sdm.services.jadwal_praktek import (
    cek_bentrok_jadwal, cek_bentrok_ruangan,
    validasi_kredensial_dokter, generate_jadwal_harian,
    proses_izin_dokter, sync_jadwal_ke_apm,
)
from akreditasi.models import UnitKerja


@login_required
def jadwal_list(request):
    """List all rutin schedules with filter by unit/dokter."""
    unit_id = request.GET.get('unit')
    qs = JadwalPraktekRutin.objects.select_related(
        'dokter', 'unit_kerja',
    ).filter(is_active=True)
    if unit_id:
        qs = qs.filter(unit_kerja_id=unit_id)

    # Credential warnings per doctor
    dokter_warnings = {}
    for jadwal in qs:
        if jadwal.dokter_id not in dokter_warnings:
            is_valid, warns = validasi_kredensial_dokter(jadwal.dokter_id)
            dokter_warnings[jadwal.dokter_id] = warns

    context = {
        'jadwal_list': qs,
        'dokter_warnings': dokter_warnings,
        'unit_list': UnitKerja.objects.all().order_by('nama'),
        'selected_unit': unit_id,
    }
    return render(request, 'sdm/jadwal_praktek/list.html', context)


@login_required
def jadwal_create(request):
    """Create a new rutin schedule with conflict checking."""
    if request.method == 'POST':
        dokter_id = request.POST.get('dokter')
        unit_id = request.POST.get('unit_kerja')
        hari = int(request.POST.get('hari', 0))
        jam_mulai = request.POST.get('jam_mulai')
        jam_selesai = request.POST.get('jam_selesai')
        ruang = request.POST.get('ruang_praktek', '')

        from datetime import time
        jm = time.fromisoformat(jam_mulai)
        js = time.fromisoformat(jam_selesai)

        if cek_bentrok_jadwal(dokter_id, hari, jm, js):
            messages.error(request, 'Bentrok jadwal: dokter sudah memiliki jadwal pada jam tersebut.')
            return redirect('sdm:jadwal_create')
        if cek_bentrok_ruangan(unit_id, ruang, hari, jm, js):
            messages.error(request, 'Bentrok ruangan: ruang sudah digunakan pada jam tersebut.')
            return redirect('sdm:jadwal_create')

        jadwal = JadwalPraktekRutin.objects.create(
            dokter_id=dokter_id,
            unit_kerja_id=unit_id,
            ruang_praktek=ruang,
            hari=hari,
            jam_mulai=jm,
            jam_selesai=js,
            kuota_jkn=int(request.POST.get('kuota_jkn', 20)),
            kuota_non_jkn=int(request.POST.get('kuota_non_jkn', 10)),
            durasi_per_pasien_menit=int(request.POST.get('durasi', 15)),
            created_by=request.user,
        )
        messages.success(request, f'Jadwal praktek {jadwal} berhasil dibuat.')
        return redirect('sdm:jadwal_list')

    context = {
        'dokter_list': Pegawai.objects.filter(
            status='AKTIF', kategori='PPA'
        ).order_by('nama_lengkap'),
        'unit_list': UnitKerja.objects.all().order_by('nama'),
        'hari_choices': JadwalPraktekRutin.HARI_CHOICES,
    }
    return render(request, 'sdm/jadwal_praktek/form.html', context)


@login_required
def jadwal_harian_list(request):
    """Daily operational schedule view with auto-generation."""
    tanggal_str = request.GET.get('tanggal')
    if tanggal_str:
        from django.utils.dateparse import parse_date
        tanggal = parse_date(tanggal_str) or timezone.localdate()
    else:
        tanggal = timezone.localdate()

    # Auto-generate if none exist for this date
    generate_jadwal_harian(tanggal)

    qs = JadwalPraktekHarian.objects.select_related(
        'dokter_rencana', 'dokter_aktual', 'dokter_pengganti', 'unit_kerja',
    ).filter(tanggal=tanggal).order_by('jam_mulai_rencana')

    context = {
        'tanggal': tanggal,
        'jadwal_harian': qs,
    }
    return render(request, 'sdm/jadwal_praktek/harian.html', context)


@login_required
def jadwal_catat_jam(request, jadwal_id):
    """Record actual start time for a daily schedule."""
    jh = get_object_or_404(JadwalPraktekHarian, pk=jadwal_id)
    if request.method == 'POST':
        from datetime import time
        jam_str = request.POST.get('jam_mulai_aktual')
        if jam_str:
            jh.jam_mulai_aktual = time.fromisoformat(jam_str)
            jh.save(update_fields=['jam_mulai_aktual', 'updated_at'])
            LogAuditJadwal.objects.create(
                jadwal_harian=jh, pengguna=request.user,
                jenis_aksi='CATAT_JAM',
                ringkasan=f'Jam aktual dicatat: {jh.jam_mulai_aktual}',
            )
            messages.success(request, 'Jam mulai aktual berhasil dicatat.')
    return redirect('sdm:jadwal_harian_list')


@login_required
def jadwal_izin_create(request):
    """Create a leave/absence request for a doctor."""
    if request.method == 'POST':
        izin = PengajuanIzinDokter.objects.create(
            dokter_id=request.POST.get('dokter'),
            jenis=request.POST.get('jenis'),
            tanggal_mulai=request.POST.get('tanggal_mulai'),
            tanggal_selesai=request.POST.get('tanggal_selesai'),
            dokter_pengganti_id=request.POST.get('pengganti') or None,
            catatan=request.POST.get('catatan', ''),
        )
        messages.success(request, f'Pengajuan izin {izin} berhasil dibuat.')
        return redirect('sdm:jadwal_list')

    context = {
        'dokter_list': Pegawai.objects.filter(
            status='AKTIF', kategori='PPA'
        ).order_by('nama_lengkap'),
        'jenis_choices': PengajuanIzinDokter.JENIS_CHOICES,
    }
    return render(request, 'sdm/jadwal_praktek/izin_form.html', context)


@login_required
def jadwal_izin_approve(request, izin_id):
    """Approve a leave request and cascade to daily schedules."""
    izin = get_object_or_404(PengajuanIzinDokter, pk=izin_id)
    if request.method == 'POST':
        izin.status = 'DISETUJUI'
        izin.disetujui_oleh = request.user
        izin.save()
        proses_izin_dokter(izin)
        messages.success(request, f'Izin {izin.dokter} disetujui. Jadwal terdampak telah diperbarui.')
    return redirect('sdm:jadwal_list')
```

- [ ] **Step 2: Add URL patterns to `sdm/urls.py`**

Add after the logbook routes (before `analitik/`):

```python
from sdm import jadwal_views

# In urlpatterns list:
path('jadwal-praktek/', jadwal_views.jadwal_list, name='jadwal_list_praktek'),
path('jadwal-praktek/baru/', jadwal_views.jadwal_create, name='jadwal_create_praktek'),
path('jadwal-praktek/harian/', jadwal_views.jadwal_harian_list, name='jadwal_harian_list'),
path('jadwal-praktek/harian/<uuid:jadwal_id>/catat-jam/', jadwal_views.jadwal_catat_jam, name='jadwal_catat_jam'),
path('jadwal-praktek/izin/baru/', jadwal_views.jadwal_izin_create, name='jadwal_izin_create'),
path('jadwal-praktek/izin/<uuid:izin_id>/setujui/', jadwal_views.jadwal_izin_approve, name='jadwal_izin_approve'),
```

- [ ] **Step 3: Add sidebar navigation item in `sdm/navigation.py`**

Add a "Jadwal Praktek" item to the HC sidebar nav, positioned after "Logbook" and before "Analitik". Examine the existing navigation structure first, then add:

```python
{
    'label': 'Jadwal Praktek',
    'url_name': 'sdm:jadwal_list_praktek',
    'icon': 'calendar',
    'children': [
        {'label': 'Jadwal Rutin', 'url_name': 'sdm:jadwal_list_praktek'},
        {'label': 'Jadwal Harian', 'url_name': 'sdm:jadwal_harian_list'},
        {'label': 'Pengajuan Izin', 'url_name': 'sdm:jadwal_izin_create'},
    ],
},
```

- [ ] **Step 4: Commit**

```bash
git add sdm/jadwal_views.py sdm/urls.py sdm/navigation.py
git commit -m "feat(sdm): jadwal praktek views, URLs, and navigation"
```

---

### Task 7: Pola Ketenagaan Dashboard Enhancement

**Files:**
- Modify: `sdm/views.py` (inject gap metrics into dashboard context)

**Interfaces:**
- Consumes: `hitung_metrik_dashboard()` from `sdm/services/pola_ketenagaan.py`
- Produces: enriched dashboard context with gap data, distribution, compliance counts

- [ ] **Step 1: Inject pola ketenagaan metrics into existing dashboard view**

In `sdm/views.py`, find the `dashboard` function and add after existing context building:

```python
from sdm.services.pola_ketenagaan import hitung_metrik_dashboard, hitung_gap_ketenagaan

# Inside dashboard():
pola_metrics = hitung_metrik_dashboard()
gap_data = hitung_gap_ketenagaan(unit_id=request.GET.get('unit'))
context.update({
    'pola_metrics': pola_metrics,
    'gap_data': gap_data,
})
```

- [ ] **Step 2: Commit**

```bash
git add sdm/views.py
git commit -m "feat(sdm): inject pola ketenagaan gap metrics into HC dashboard"
```

---

### Task 8: Templates — Jadwal Praktek

**Files:**
- Create: `templates/sdm/jadwal_praktek/list.html`
- Create: `templates/sdm/jadwal_praktek/form.html`
- Create: `templates/sdm/jadwal_praktek/harian.html`
- Create: `templates/sdm/jadwal_praktek/izin_form.html`

**Interfaces:**
- Consumes: context from Task 6 views
- Produces: rendered HTML pages for jadwal praktek sub-module

- [ ] **Step 1: Create `list.html` — weekly rutin schedule matrix**

Template shows all active rutin schedules grouped by day, with credential warning badges per doctor, and filter by unit. Follow existing `templates/sdm/` patterns (extends base, Tailwind classes, sidebar nav).

Key elements:
- Filter bar: unit select dropdown
- Table columns: Hari, Dokter, Poliklinik, Jam, Kuota JKN/Non-JKN, Status Kredensial
- Warning badge if `dokter_warnings[jadwal.dokter_id]` is non-empty
- Action buttons: Tambah Jadwal, Lihat Harian

- [ ] **Step 2: Create `form.html` — create/edit rutin schedule form**

Form fields: dokter (select), unit_kerja (select), hari (select), jam_mulai (time), jam_selesai (time), ruang_praktek (text), kuota_jkn (number), kuota_non_jkn (number), durasi_per_pasien_menit (number).

- [ ] **Step 3: Create `harian.html` — daily operational schedule view**

Shows daily schedule rows for a selected date:
- Date picker at top
- Table: Dokter Rencana, Dokter Aktual/Pengganti, Unit, Jam Rencana/Aktual, Kuota (JKN/Non-JKN/Terpakai), Status Sesi, Keterlambatan, Aksi (Catat Jam, Set Pengganti)
- Color-coded status badges (Aktif=green, Mundur=yellow, Digantikan=blue, Batal=red)

- [ ] **Step 4: Create `izin_form.html` — leave request form**

Form fields: dokter (select), jenis (select), tanggal_mulai (date), tanggal_selesai (date), dokter_pengganti (select, optional), catatan (textarea).

- [ ] **Step 5: Commit**

```bash
git add templates/sdm/jadwal_praktek/
git commit -m "feat(sdm): jadwal praktek templates (list, form, harian, izin)"
```

---

### Task 9: Templates — Pola Ketenagaan Dashboard Cards & Gap Table

**Files:**
- Modify: `templates/sdm/dashboard.html`

**Interfaces:**
- Consumes: `pola_metrics`, `gap_data` from Task 7 context

- [ ] **Step 1: Add KPI cards to dashboard**

Add after existing dashboard cards:

Cards to add:
1. **Pegawai Aktif** — `pola_metrics.total_aktif` with PPA/Non-PPA breakdown
2. **Distribusi Rumpun** — mini bar chart or counts per keluarga
3. **Dokumen Menunggu** — `pola_metrics.doc_pending` (clickable to kredensial list)
4. **Kedaluwarsa ≤ 30 Hari** — `pola_metrics.doc_expiring`
5. **Gap Pola Ketenagaan** — total standar vs eksisting, `pola_metrics.total_deficit_kritis` unit defisit kritis

- [ ] **Step 2: Add gap analysis table**

Below the cards, add "Peta Pemenuhan Pola Ketenagaan (Medis & Non-Medis)" table:

Columns: Unit Kerja, Rumpun, Profesi, Standar FTE, Eksisting FTE, Gap, Status, Aksi (Eskalasi Risk Register if deficit)

Color-coded badges:
- `success` (green) = Sesuai Standar
- `info` (blue) = Surplus
- `warning` (yellow) = Defisit Ringan
- `danger` (red) = Defisit Kritis

- [ ] **Step 3: Commit**

```bash
git add templates/sdm/dashboard.html
git commit -m "feat(sdm): pola ketenagaan dashboard cards and gap analysis table"
```

---

### Task 10: Tests — Models & Services

**Files:**
- Create: `sdm/tests/test_jadwal_praktek.py`
- Create: `sdm/tests/test_pola_ketenagaan.py`

**Interfaces:**
- Consumes: all models from Task 2, all services from Tasks 4-5

- [ ] **Step 1: Create `test_jadwal_praktek.py`**

```python
"""Tests for jadwal praktek models and services."""
from datetime import date, time, timedelta
from django.test import TestCase
from sdm.models import (
    Pegawai, MasterProfesiPegawai,
    JadwalPraktekRutin, JadwalPraktekHarian,
    PengajuanIzinDokter, LogAuditJadwal,
)
from sdm.services.jadwal_praktek import (
    cek_bentrok_jadwal, generate_jadwal_harian, proses_izin_dokter,
)
from akreditasi.models import UnitKerja


class JadwalPraktekRutinModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(
            nama='Poli Jantung', code='POL-JTG',
        )
        cls.profesi = MasterProfesiPegawai.objects.create(
            code='SP_JP_T', nama='Sp.JP Test', keluarga='MEDIS',
        )
        cls.dokter = Pegawai.objects.create(
            nama_lengkap='dr. Test Sp.JP', kategori='PPA',
            profesi='Sp.JP Test', profesi_master=cls.profesi,
        )

    def test_create_jadwal_rutin(self):
        jadwal = JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit,
            hari=0, jam_mulai=time(8, 0), jam_selesai=time(12, 0),
            kuota_jkn=20, kuota_non_jkn=10,
        )
        self.assertEqual(jadwal.kuota_total, 30)
        self.assertTrue(jadwal.is_active)

    def test_jam_validation(self):
        from django.core.exceptions import ValidationError
        jadwal = JadwalPraktekRutin(
            dokter=self.dokter, unit_kerja=self.unit,
            hari=0, jam_mulai=time(12, 0), jam_selesai=time(8, 0),
        )
        with self.assertRaises(ValidationError):
            jadwal.full_clean()


class BentrokJadwalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(nama='Poli Test', code='POL-T')
        cls.profesi = MasterProfesiPegawai.objects.create(
            code='DR_T', nama='Dokter Test', keluarga='MEDIS',
        )
        cls.dokter = Pegawai.objects.create(
            nama_lengkap='dr. Bentrok', kategori='PPA',
            profesi='Dokter Test', profesi_master=cls.profesi,
        )
        cls.jadwal = JadwalPraktekRutin.objects.create(
            dokter=cls.dokter, unit_kerja=cls.unit,
            hari=0, jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )

    def test_overlap_detected(self):
        self.assertTrue(cek_bentrok_jadwal(
            self.dokter.id, 0, time(10, 0), time(14, 0)
        ))

    def test_no_overlap(self):
        self.assertFalse(cek_bentrok_jadwal(
            self.dokter.id, 0, time(13, 0), time(16, 0)
        ))

    def test_different_day_no_overlap(self):
        self.assertFalse(cek_bentrok_jadwal(
            self.dokter.id, 1, time(8, 0), time(12, 0)
        ))


class GenerateJadwalHarianTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(nama='Poli Gen', code='POL-G')
        cls.profesi = MasterProfesiPegawai.objects.create(
            code='DR_G', nama='Dokter Gen', keluarga='MEDIS',
        )
        cls.dokter = Pegawai.objects.create(
            nama_lengkap='dr. Gen', kategori='PPA',
            profesi='Dokter Gen', profesi_master=cls.profesi,
        )

    def test_generate_creates_rows(self):
        # Monday = 0
        JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit,
            hari=0, jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )
        # Find the next Monday
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        senin = today + timedelta(days=days_ahead)

        created = generate_jadwal_harian(senin)
        self.assertEqual(created, 1)
        self.assertTrue(
            JadwalPraktekHarian.objects.filter(tanggal=senin).exists()
        )

    def test_idempotent(self):
        JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit,
            hari=0, jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        senin = today + timedelta(days=days_ahead)

        generate_jadwal_harian(senin)
        second_run = generate_jadwal_harian(senin)
        self.assertEqual(second_run, 0)


class IzinDokterTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(nama='Poli Izin', code='POL-I')
        cls.profesi = MasterProfesiPegawai.objects.create(
            code='DR_I', nama='Dokter Izin', keluarga='MEDIS',
        )
        cls.dokter = Pegawai.objects.create(
            nama_lengkap='dr. Izin', kategori='PPA',
            profesi='Dokter Izin', profesi_master=cls.profesi,
        )
        cls.pengganti = Pegawai.objects.create(
            nama_lengkap='dr. Pengganti', kategori='PPA',
            profesi='Dokter Izin', profesi_master=cls.profesi,
        )

    def test_proses_izin_marks_batal(self):
        today = date.today()
        target = today + timedelta(days=7)
        jh = JadwalPraktekHarian.objects.create(
            tanggal=target, dokter_rencana=self.dokter,
            unit_kerja=self.unit,
            jam_mulai_rencana=time(8, 0), jam_selesai_rencana=time(12, 0),
        )
        izin = PengajuanIzinDokter.objects.create(
            dokter=self.dokter, jenis='CUTI',
            tanggal_mulai=target, tanggal_selesai=target,
        )
        proses_izin_dokter(izin)
        jh.refresh_from_db()
        self.assertEqual(jh.status_sesi, 'BATAL')

    def test_proses_izin_marks_digantikan(self):
        today = date.today()
        target = today + timedelta(days=7)
        jh = JadwalPraktekHarian.objects.create(
            tanggal=target, dokter_rencana=self.dokter,
            unit_kerja=self.unit,
            jam_mulai_rencana=time(8, 0), jam_selesai_rencana=time(12, 0),
        )
        izin = PengajuanIzinDokter.objects.create(
            dokter=self.dokter, jenis='DIKLAT',
            tanggal_mulai=target, tanggal_selesai=target,
            dokter_pengganti=self.pengganti,
        )
        proses_izin_dokter(izin)
        jh.refresh_from_db()
        self.assertEqual(jh.status_sesi, 'DIGANTIKAN')
        self.assertEqual(jh.dokter_pengganti, self.pengganti)
```

- [ ] **Step 2: Create `test_pola_ketenagaan.py`**

```python
"""Tests for pola ketenagaan gap analysis."""
from django.test import TestCase
from sdm.models import Pegawai, MasterProfesiPegawai
from sdm.services.pola_ketenagaan import hitung_metrik_dashboard


class MetrikDashboardTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profesi = MasterProfesiPegawai.objects.create(
            code='DR_MT', nama='Dokter Metrik', keluarga='MEDIS',
        )
        for i in range(3):
            Pegawai.objects.create(
                nama_lengkap=f'dr. Metrik {i}', kategori='PPA',
                profesi='Dokter Metrik', profesi_master=cls.profesi,
            )

    def test_counts_active_employees(self):
        metrics = hitung_metrik_dashboard()
        self.assertGreaterEqual(metrics['total_aktif'], 3)
        self.assertGreaterEqual(metrics['ppa_count'], 3)

    def test_distribution_includes_medis(self):
        metrics = hitung_metrik_dashboard()
        keluarga_list = [
            d['profesi_master__keluarga'] for d in metrics['distribusi_rumpun']
        ]
        self.assertIn('MEDIS', keluarga_list)
```

- [ ] **Step 3: Run tests**

```bash
python manage.py test sdm.tests.test_jadwal_praktek sdm.tests.test_pola_ketenagaan --keepdb -v2
```
Expected: All tests pass, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add sdm/tests/test_jadwal_praktek.py sdm/tests/test_pola_ketenagaan.py
git commit -m "test(sdm): jadwal praktek and pola ketenagaan tests"
```

---

## Explicitly NOT in This Plan

The following items surfaced during analysis but are **out of scope**:

1. **Non-Medis seed data** — The spec describes Keperawatan, Nakes Lain, and Non-Medis staffing patterns, but only 25 Medis staff are provided in the Excel. Non-Medis seed data can be added in a follow-up plan.
2. **WhatsApp integration for jadwal changes** — The spec mentions notifying patients via WhatsApp when schedules change. This requires the WhatsApp bridge infrastructure and is a separate feature.
3. **Risk Register escalation button** — The spec describes auto-escalation to Risk Register when deficit persists. The `akreditasi` app's risk model structure needs verification first. The service layer is prepared but the view/button is deferred until the FK target is confirmed.
4. **Kalkulator Gillies/Douglas/WISN expansion** — The spec references multiple calculation methods. The existing `BebanKerja` model already supports WISN. Adding Gillies/Douglas as additional `metode` choices is a separate enhancement.
5. **APM kiosk auto-sync** — Real-time sync from HC jadwal to APM kiosk display requires a signal/webhook mechanism that is out of scope for this plan.
6. **PDF export for Pola Ketenagaan report** — The spec mentions "Cetak Dokumen SK Pola Ketenagaan". This is a ReportLab PDF task that can be added as a follow-up.

---

## Execution Status (native run, 2026-11-22)

Checkboxes above are left unticked on purpose: this block is the authoritative
record of what actually ran. Several steps were executed with a corrected
instruction (see Deviations), so a blanket tick would be false.

### Done — verified in this session

| Task | Landed | Evidence |
|------|--------|----------|
| 1 — Seed staf medis | `sdm/management/commands/seed_staf_medis.py`; 25 `Pegawai` + `RiwayatKepegawaian` + `PenempatanPegawai` + `PengajuanKredensial` + 17 `PenugasanKlinis` (SPK) | `seed_staf_medis` printed "25 pegawai baru dibuat"; re-run printed "0 pegawai baru dibuat" (idempotent). Shell counts: pegawai DEMO 31 (25 baru + 6 pra-ada), riwayat 25, pengajuan 25, SPK aktif 17 |
| 2 — Models jadwal praktek | `sdm/models/jadwal_praktek.py` (5 model) + `sdm/migrations/0068_jadwal_praktek_models.py` | `makemigrations` created 0068; `migrate` applied OK; `manage.py check` clean |
| 3 — APM bridge | `pasien/models.py` FK `pegawai` + `pasien/migrations/0038_jadwal_dokter_pegawai_fk.py` | migration applied OK |
| 4 — Services jadwal | `sdm/services/jadwal_praktek.py` (bentrok dokter/ruang, validasi kredensial, generate harian idempoten, kaskade izin, sync APM) | 26 passing tests in `test_jadwal_praktek.py` |
| 5 — Services pola ketenagaan | `sdm/services/pola_ketenagaan.py` (gap per rumpun, klasifikasi, ringkasan dasbor) | 19 passing tests in `test_pola_ketenagaan.py` |
| 6 — Views/URLs/nav | `sdm/jadwal_views.py`, `sdm/jadwal_forms.py`, 8 routes in `sdm/urls.py`, `NavGroup` baru di `sdm/navigation.py`, `nav_jadwal` di context processor | 6 pages rendered 200 against the dev DB with expected content (smoke script) |
| 7 — Dashboard enhancement | `sdm/views.py` injects `hitung_ringkasan_pola`; dashboard renders gap section | `test_dashboard_renders_gap_section` passes; dashboard render len 76 833 bytes |
| 8 — Templates jadwal | `templates/sdm/jadwal_praktek/{_nav,daftar,form,harian,izin_form,izin_daftar}.html` | all 6 compile via `get_template`; all render 200 |
| 9 — Dashboard cards/table | `templates/sdm/dashboard.html` — kartu distribusi rumpun + tabel gap | rendered in smoke run, `Peta Pemenuhan Pola Ketenagaan` present |
| 10 — Tests | `sdm/tests/test_jadwal_praktek.py` (22), `sdm/tests/test_pola_ketenagaan.py` (12) | `Ran 34 tests ... OK` |

Regression suites re-run green: navigation/sidebar/dashboard/release/wsgi (50 tests, OK) and
`pasien.tests_apm_models` + `pasien.tests_apm_hari_praktik` + `sdm.tests.test_risiko_formasi` +
`sdm.tests.test_pegawai_models` (49 tests, OK).

### Deviations from the plan text (implementation followed the repo, not the plan)

1. **Bootstrap 5, not Tailwind.** The plan said Tailwind; every `templates/sdm/` page uses Bootstrap 5 (`card`, `form-select`, `bi-*`). Templates follow the repo.
2. **`UnitKerja.name`, not `.nama`.** `akreditasi.UnitKerja` has `name` + unique `code`; the plan's `.nama` would raise `AttributeError`. All queries and tests use `name`/`code`.
3. **Navigation is a dataclass tree.** The plan's dict-shaped nav item would break `navigation_tree()`. Implemented as a `NavGroup` with three `NavItem`s.
4. **Eleven nav groups, not ten.** The new "Jadwal Praktek Dokter" group changes the documented contract, so `test_navigation.py` was updated (`test_ten_groups…` → `test_eleven_groups…`) and both module docstrings corrected.
5. **`build_hc_dashboard` was not duplicated.** The repo already computes staffing/compliance; `pola_ketenagaan.py` adds only the rumpun grouping and gap classification that were missing.
6. **Group-by bug fixed.** `Pegawai.Meta.ordering` leaked into `GROUP BY` and collapsed every rumpun count to 1; fixed with `.order_by()` before `values().annotate()`. Caught by `test_distribution_reports_every_rumpun_bucket` — the service, not the test, was wrong.
7. **Test fixtures widened, checks untouched.** `visible_employees()` correctly returns nothing for employees with no `PenempatanPegawai` and for roles whose `RolePermissionConfig` flag is off; the fixtures now create placements and enable the flags rather than loosening authorization.
8. **APM bridge left one-way and optional.** `JadwalDokterPoli.pegawai` is nullable and `sync_jadwal_ke_apm()` only writes `status_ketersediaan`; rows without a link are untouched (`test_rows_without_employee_link_are_untouched`).

### Round 2 — remaining scope, now completed (2026-11-22, same session)

| Item | Landed | Evidence |
|------|--------|----------|
| SIP/STR seeding | `seed_staf_medis._seed_izin` writes `IzinProfesiPegawai` STR (LIFETIME) + SIP (3 yr, `is_local_rs=True`) for every clinical profession; validity is anchored to the current year, not to TMT | `STR 50 / SIP 46` rows; validator returns `warnings=[]` for a seeded doctor |
| License-aware credential check | `validasi_kredensial_dokter` now reads `IzinProfesiPegawai` first and falls back to verified `VersiDokumen` | 3 new tests: master licence satisfies SIP, LIFETIME never expires, expired still warns |
| SPK validity repair | `_seed_kredensial` uses `update_or_create` with `berlaku_sampai = today + 2 yr` and upgrades an existing request to DISETUJUI | smoke: `legalitas dokter seed bersih … warnings=[]` |
| Risk Register escalation | `sdm/services/eskalasi_risiko.py` + `pola_eskalasi` view + POST button per deficit row | 4 tests (creates, idempotent, rejects surplus, view redirects); smoke created `Defisit pola ketenagaan: Dokter Umum — IRJ (2026)` |
| SK Pola Ketenagaan PDF | `render_sk_pola_pdf` (landscape A4, kop, dasar hukum, gap table, rumpun distribution, signature block) + `pola_sk_pdf` view + download button | 2 tests + real artifact `C:\Users\cubeb\Downloads\SK_Pola_Ketenagaan_ARIMA.pdf` (3 383 bytes, 4 rows, total 21.43 FTE) |
| Non-medis / nursing / nakes seed | 26 professions × 4 rumpun, 60 staff rows; `--demo-formasi` seeds JKE + 4 approved plans + results via the real `calculate_formasi` | counts: MEDIS 27, KEPERAWATAN 13, NAKES_LAIN 12, NON_KLINIS 13 |
| Gillies & Douglas calculators | `sdm/services/gillies.py` with hand-computed assertions and input rejection | 9 tests in `test_gillies.py` |

### Two real defects found and fixed during round 2

1. **Inverted gap sign.** `HasilFormasi.gap_fte` is `required − actual`, so a *positive* value means shortage. The first cut classified `gap > 0` as "Surplus" and would have labelled a 6.68-FTE shortfall as surplus on the dashboard and in the SK. The service now converts once (`actual − required`) and exposes `gap_repo_fte` alongside; both directions are pinned by tests.
2. **Stale seeded validity.** SIP and SPK were dated from TMT, so every senior staff member looked expired and every schedule badge was yellow for the wrong reason. Both are now anchored to the current year.

### Still not done — genuinely out of reach here

1. **WhatsApp notification on schedule change.** Needs the WhatsApp bridge credentials and an approved template; nothing in this repo can send it.
2. **APM kiosk real-time push.** `sync_jadwal_ke_apm()` writes `status_ketersediaan` on demand; a push/webhook on save would need a signal + queue decision.
3. **Production data.** All seeded rows are `data_origin='DEMO'` on the local dev database only. Nothing was written to Supabase or deployed.

### Commands that reproduce the verification

```bash
python manage.py check
python manage.py test sdm.tests.test_jadwal_praktek sdm.tests.test_pola_ketenagaan \
  sdm.tests.test_gillies --keepdb                      # 54 tests
python manage.py test sdm.tests.test_dashboard sdm.tests.test_navigation \
  sdm.tests.test_sidebar_hc_nav sdm.tests.test_sidebar_navigation \
  sdm.tests.test_nav_kredensial_pribadi sdm.tests.test_release \
  sdm.tests.test_wsgi_migrations --keepdb              # 50 tests
python manage.py test pasien.tests_apm_models pasien.tests_apm_hari_praktik \
  sdm.tests.test_risiko_formasi sdm.tests.test_pegawai_models \
  sdm.tests.test_penempatan sdm.tests.test_legalitas --keepdb   # 62 tests
python manage.py seed_staf_medis --demo-formasi        # idempotent, demo data only
```


