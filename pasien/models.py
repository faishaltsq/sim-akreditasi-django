"""
Modul Manajemen Pasien MonsisKami (ARIMA System)
Tahap 1–5: Pendaftaran → Pelayanan → Ranap → Billing → Discharge
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError


# ── 1. Master Pasien ─────────────────────────────────────────────────────────

from .expansion_models import (KomponenRacikan, AlergiPasienTerstruktur, MedicationSafetyReview, PpraReviewRequest, PrescriptionOperation, PharmacyServiceGrant)


class Pasien(models.Model):
    JENIS_KELAMIN = [('L', 'Laki-laki'), ('P', 'Perempuan')]
    GOLDAR = [('A', 'A'), ('B', 'B'), ('AB', 'AB'), ('O', 'O'), ('-', 'Tidak Diketahui')]
    AGAMA_CHOICES = [
        ('ISLAM', 'Islam'),
        ('KRISTEN', 'Kristen'),
        ('KATOLIK', 'Katolik'),
        ('HINDU', 'Hindu'),
        ('BUDDHA', 'Buddha'),
        ('KONGHUCU', 'Konghucu'),
        ('LAINNYA', 'Lainnya'),
    ]
    STATUS_KAWIN_CHOICES = [
        ('BELUM_MENIKAH', 'Belum Menikah'),
        ('MENIKAH', 'Menikah'),
        ('DUDA_JANDA', 'Duda / Janda'),
    ]
    PENDIDIKAN_CHOICES = [
        ('SD_SMP_SMA', 'SD / SMP / SMA'),
        ('D3_D4', 'D3 / D4'),
        ('S1_S2_S3', 'S1 / S2 / S3'),
        ('LAINNYA', 'Lainnya'),
    ]
    HUBUNGAN_PJ_CHOICES = [
        ('SUAMI_ISTRI', 'Suami / Istri'),
        ('ORANG_TUA', 'Orang Tua'),
        ('ANAK', 'Anak'),
        ('KERABAT_LAIN', 'Kerabat / Lainnya'),
    ]

    no_rm               = models.CharField('No. Rekam Medis', max_length=20, unique=True)
    nik                 = models.CharField('NIK', max_length=16, blank=True)
    nama_lengkap        = models.CharField('Nama Lengkap', max_length=200)
    tempat_lahir        = models.CharField('Tempat Lahir', max_length=100, blank=True)
    tanggal_lahir       = models.DateField('Tanggal Lahir')
    jenis_kelamin       = models.CharField('Jenis Kelamin', max_length=1, choices=JENIS_KELAMIN)
    agama               = models.CharField('Agama', max_length=20, choices=AGAMA_CHOICES, blank=True)
    status_perkawinan   = models.CharField('Status Perkawinan', max_length=20, choices=STATUS_KAWIN_CHOICES, blank=True)
    pendidikan_terakhir = models.CharField('Pendidikan Terakhir', max_length=30, choices=PENDIDIKAN_CHOICES, blank=True)
    pekerjaan           = models.CharField('Pekerjaan', max_length=100, blank=True)
    golongan_darah      = models.CharField('Golongan Darah', max_length=3, choices=GOLDAR, default='-')
    alamat              = models.TextField('Alamat Domisili Lengkap', blank=True)
    rt_rw               = models.CharField('RT / RW', max_length=20, blank=True)
    kelurahan           = models.CharField('Kelurahan / Desa', max_length=100, blank=True)
    kecamatan           = models.CharField('Kecamatan', max_length=100, blank=True)
    kota_kabupaten      = models.CharField('Kota / Kabupaten', max_length=100, blank=True)
    provinsi            = models.CharField('Provinsi', max_length=100, blank=True)
    no_hp               = models.CharField('No. HP / WhatsApp', max_length=30, blank=True)
    email               = models.EmailField('Email', blank=True)
    no_bpjs             = models.CharField('No. BPJS', max_length=30, blank=True)
    # ── Emergency Contact / Penanggung Jawab Pasien ──
    nama_pj             = models.CharField('Nama Penanggung Jawab', max_length=150, blank=True)
    hubungan_pj         = models.CharField('Hubungan dengan Pasien', max_length=50, blank=True)
    no_hp_pj            = models.CharField('No. HP / WA Penanggung Jawab', max_length=30, blank=True)
    alamat_pj           = models.TextField('Alamat Penanggung Jawab', blank=True)

    # ── Dokumen Bukti Identitas (SKP 1 & MRMIK) ──
    foto_ktp            = models.FileField('Foto / Scan KTP', upload_to='pasien/ktp/%Y/%m/', blank=True, null=True)

    alergi_obat         = models.TextField('Alergi Obat', blank=True, help_text='Pisahkan dengan koma')
    alergi_lain         = models.TextField('Alergi Lain', blank=True)
    # ── SatuSehat Kemenkes ──
    satusehat_id        = models.CharField('SatuSehat Patient ID', max_length=64, blank=True, null=True)
    satusehat_sync_at   = models.DateTimeField('Waktu Sync SatuSehat', null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pasien'
        verbose_name_plural = 'Data Pasien'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.no_rm}] {self.nama_lengkap}'

    @property
    def umur(self):
        if not self.tanggal_lahir:
            return 0
        from datetime import date
        today = date.today()
        b = self.tanggal_lahir
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

    @property
    def usia(self):
        return self.umur

    @property
    def has_alergi(self):
        return bool(self.alergi_obat or self.alergi_lain)


def generate_no_rm():
    """Generate sequential unique RM number, format: RM-YYYYMM-XXXX"""
    import datetime
    now = datetime.datetime.now()
    prefix = f"RM-{now.strftime('%Y%m')}-"
    last_pasien = Pasien.objects.filter(no_rm__startswith=prefix).order_by('-no_rm').first()
    if last_pasien and len(last_pasien.no_rm) >= len(prefix) + 4:
        try:
            last_seq = int(last_pasien.no_rm[len(prefix):])
            seq = last_seq + 1
        except ValueError:
            seq = Pasien.objects.filter(no_rm__startswith=prefix).count() + 1
    else:
        seq = Pasien.objects.filter(no_rm__startswith=prefix).count() + 1

    no_rm = f"{prefix}{seq:04d}"
    while Pasien.objects.filter(no_rm=no_rm).exists():
        seq += 1
        no_rm = f"{prefix}{seq:04d}"
    return no_rm


def generate_no_kunjungan(jenis='RAJAL'):
    """Generate sequential unique Visit number, format: REG-YYYYMMDD-XXXX or IGD-YYYYMMDD-XXXX"""
    import datetime
    now = datetime.datetime.now()
    date_str = now.strftime('%Y%m%d')
    if jenis == 'IGD':
        prefix = f"IGD-{date_str}-"
    elif jenis == 'RANAP':
        prefix = f"RNP-{date_str}-"
    else:
        prefix = f"REG-{date_str}-"

    last_kunjungan = KunjunganPasien.objects.filter(no_kunjungan__startswith=prefix).order_by('-no_kunjungan').first()
    if last_kunjungan and len(last_kunjungan.no_kunjungan) >= len(prefix) + 4:
        try:
            last_seq = int(last_kunjungan.no_kunjungan[len(prefix):])
            seq = last_seq + 1
        except ValueError:
            seq = KunjunganPasien.objects.filter(no_kunjungan__startswith=prefix).count() + 1
    else:
        seq = KunjunganPasien.objects.filter(no_kunjungan__startswith=prefix).count() + 1

    no_kunj = f"{prefix}{seq:04d}"
    while KunjunganPasien.objects.filter(no_kunjungan=no_kunj).exists():
        seq += 1
        no_kunj = f"{prefix}{seq:04d}"
    return no_kunj


# ── 2. Bed Management ────────────────────────────────────────────────────────

class Ruangan(models.Model):
    KELAS = [('VIP', 'VIP'), ('1', 'Kelas I'), ('2', 'Kelas II'), ('3', 'Kelas III'), ('ICU', 'ICU'), ('IGD', 'IGD'), ('OK', 'Kamar Operasi')]
    JENIS = [('RANAP', 'Rawat Inap'), ('IGD', 'IGD'), ('RAJAL', 'Rawat Jalan'), ('OK', 'Kamar Operasi'), ('ICU', 'ICU')]

    kode    = models.CharField('Kode Ruangan', max_length=20, unique=True)
    nama    = models.CharField('Nama Ruangan', max_length=100)
    kelas   = models.CharField('Kelas', max_length=5, choices=KELAS)
    jenis   = models.CharField('Jenis', max_length=10, choices=JENIS, default='RANAP')
    kapasitas = models.IntegerField('Kapasitas Bed', default=1)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ruangan',
        verbose_name='Unit Kerja',
    )

    class Meta:
        verbose_name = 'Ruangan'
        verbose_name_plural = 'Ruangan'
        ordering = ['kelas', 'kode']

    def __str__(self):
        return f'[{self.kode}] {self.nama} ({self.get_kelas_display()})'

    @property
    def label(self):
        """Nama ruangan + kelas, tanpa mengulang kelas yang sudah tertulis di nama."""
        nama = (self.nama or '').strip()
        kelas = self.get_kelas_display()
        if kelas and kelas.lower() not in nama.lower():
            return f'{nama} ({kelas})'
        return nama


class Bed(models.Model):
    STATUS = [
        ('TERSEDIA', 'Tersedia'),
        ('DIBOOKING', 'Dibooking / Dipesan'),
        ('TERISI',   'Terisi'),
        ('STERILISASI', 'Proses Sterilisasi'),
        ('TIDAK_AKTIF', 'Tidak Aktif'),
    ]

    ruangan  = models.ForeignKey(Ruangan, on_delete=models.CASCADE, related_name='beds')
    kode_bed = models.CharField('Kode Bed', max_length=20)
    status   = models.CharField('Status', max_length=15, choices=STATUS, default='TERSEDIA')
    catatan  = models.CharField('Catatan', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Bed'
        verbose_name_plural = 'Bed Management'
        unique_together = [('ruangan', 'kode_bed')]
        ordering = ['ruangan', 'kode_bed']

    def __str__(self):
        return f'{self.ruangan.kode}-{self.kode_bed} [{self.get_status_display()}]'


# ── 3. Kunjungan Pasien ──────────────────────────────────────────────────────

POLIKLINIK_CHOICES = [
    ('POLI_JANTUNG', 'Poli Jantung & Pembuluh Darah'),
    ('POLI_PARU', 'Poli Paru & Respirasi'),
    ('POLI_PENYAKIT_DALAM', 'Poli Penyakit Dalam (Interna)'),
    ('POLI_BEDAH', 'Poli Bedah Umum'),
    ('POLI_ANAK', 'Poli Anak (Pediatri)'),
    ('POLI_OBGYN', 'Poli Kebidanan & Kandungan (Obgyn)'),
    ('POLI_MATA', 'Poli Mata'),
    ('POLI_SARAF', 'Poli Saraf (Neurologi)'),
    ('POLI_THT', 'Poli THT-KL'),
    ('POLI_GIGI', 'Poli Gigi & Mulut'),
    ('POLI_ORTHO', 'Poli Orthopedi & Traumatologi'),
    ('POLI_KULIT', 'Poli Kulit & Kelamin'),
    ('POLI_JIWA', 'Poli Jiwa & Psikiatri'),
    ('REHAB_MEDIK', 'Poli Rehabilitasi Medik'),
    ('POLI_ENDOKRIN', 'Poli Endokrin & Metabolik'),
    ('POLI_BSARAF', 'Poli Bedah Saraf'),
    ('POLI_UMUM', 'Poli Umum'),
]

DPJP_CHOICES = [
    ('dr. Faisal, Sp.JP', 'dr. Faisal, Sp.JP — Spesialis Jantung & Pembuluh Darah'),
    ('dr. Bambang, Sp.JP, FIHA', 'dr. Bambang, Sp.JP, FIHA — Spesialis Jantung & Pembuluh Darah'),
    ('dr. Indah, Sp.P', 'dr. Indah, Sp.P — Spesialis Paru & Respirasi'),
    ('dr. Gunawan, Sp.P, FAPSR', 'dr. Gunawan, Sp.P, FAPSR — Spesialis Paru'),
    ('dr. Budi Santoso, Sp.PD', 'dr. Budi Santoso, Sp.PD — Spesialis Penyakit Dalam'),
    ('dr. Siti Rahma, Sp.PD-KGEH', 'dr. Siti Rahma, Sp.PD-KGEH — Spesialis Penyakit Dalam'),
    ('dr. Hendra, Sp.B', 'dr. Hendra, Sp.B — Spesialis Bedah Umum'),
    ('dr. Ahmad, Sp.B, FICS', 'dr. Ahmad, Sp.B, FICS — Spesialis Bedah'),
    ('dr. Nurul, Sp.A', 'dr. Nurul, Sp.A — Spesialis Anak (Pediatri)'),
    ('dr. Maya, Sp.A, M.Biomed', 'dr. Maya, Sp.A, M.Biomed — Spesialis Anak'),
    ('dr. Rina, Sp.OG', 'dr. Rina, Sp.OG — Spesialis Kebidanan & Kandungan'),
    ('dr. Dewi, Sp.OG(K)', 'dr. Dewi, Sp.OG(K) — Spesialis Kebidanan & Kandungan'),
    ('dr. Farida, Sp.M', 'dr. Farida, Sp.M — Spesialis Mata'),
    ('dr. Eko, Sp.S', 'dr. Eko, Sp.S — Spesialis Saraf (Neurologi)'),
    ('dr. Haryanto, Sp.THT-KL', 'dr. Haryanto, Sp.THT-KL — Spesialis THT-KL'),
    ('drg. Amanda, Sp.KG', 'drg. Amanda, Sp.KG — Dokter Gigi Spesialis'),
    ('drg. Rizki', 'drg. Rizki — Dokter Gigi'),
    ('dr. Kevin, Sp.OT', 'dr. Kevin, Sp.OT — Spesialis Orthopedi & Traumatologi'),
    ('dr. Citra, Sp.DV', 'dr. Citra, Sp.DV — Spesialis Kulit & Kelamin'),
    ('dr. Hadi, Sp.KJ', 'dr. Hadi, Sp.KJ — Spesialis Kedokteran Jiwa'),
    ('dr. Lina, Sp.KFR', 'dr. Lina, Sp.KFR — Spesialis Rehabilitasi Medik'),
    ('dr. Jaga IGD', 'dr. Jaga IGD — Dokter Jaga Gawat Darurat'),
    ('dr. Pratama', 'dr. Pratama — Dokter Umum'),
    ('dr. Intan', 'dr. Intan — Dokter Umum'),
]

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


class KunjunganPasien(models.Model):
    JENIS_KUNJUNGAN = [
        ('IGD',   'Gawat Darurat (IGD)'),
        ('RAJAL', 'Rawat Jalan (Poliklinik)'),
        ('RANAP', 'Rawat Inap'),
    ]
    TIPE_PENJAMIN = [
        ('UMUM',    'Umum / Tunai'),
        ('BPJS',    'BPJS Kesehatan'),
        ('ASURANSI','Asuransi Swasta'),
    ]
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
    TRIAGE_CHOICES = [
        ('MERAH',  'Merah — Prioritas I (Kritis)'),
        ('KUNING', 'Kuning — Prioritas II (Urgent)'),
        ('HIJAU',  'Hijau — Prioritas III (Non-Urgent)'),
        ('HITAM',  'Hitam — Prioritas IV (Expectant)'),
    ]

    pasien          = models.ForeignKey(Pasien, on_delete=models.CASCADE, related_name='kunjungan')
    no_kunjungan    = models.CharField('No. Kunjungan', max_length=30, unique=True)
    jenis_kunjungan = models.CharField('Jenis Kunjungan', max_length=10, choices=JENIS_KUNJUNGAN)
    tanggal_masuk   = models.DateTimeField('Tanggal Masuk')
    tanggal_keluar  = models.DateTimeField('Tanggal Keluar', null=True, blank=True)
    dpjp            = models.CharField('DPJP', max_length=150, blank=True)
    poliklinik      = models.CharField('Poliklinik / Unit', max_length=100, blank=True)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kunjungan_pasien',
        verbose_name='Unit Kerja Pelayanan',
    )
    bed             = models.ForeignKey(Bed, on_delete=models.SET_NULL, null=True, blank=True, related_name='kunjungan')
    penjamin        = models.CharField('Penjamin', max_length=10, choices=TIPE_PENJAMIN, default='UMUM')
    diagnosa_masuk  = models.CharField('Diagnosa Masuk (ICD-10)', max_length=300, blank=True)
    diagnosa_keluar = models.CharField('Diagnosa Keluar (ICD-10)', max_length=300, blank=True)
    triage          = models.CharField('Triage IGD', max_length=10, choices=TRIAGE_CHOICES, blank=True)
    status          = models.CharField('Status Kunjungan', max_length=15, choices=STATUS_KUNJUNGAN, default='DAFTAR')
    catatan_admisi  = models.TextField('Catatan Admisi', blank=True)
    general_consent = models.BooleanField('General Consent Ditandatangani', default=False)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    # ── Discharge Planning H-1 ──
    discharge_planning_aktif   = models.BooleanField('Discharge Planning Aktif', default=False)
    discharge_planning_catatan = models.TextField('Catatan Discharge Planning', blank=True)
    discharge_planning_tgl     = models.DateField('Target Tanggal Pulang', null=True, blank=True)

    # ── SatuSehat Kemenkes Encounter ──
    satusehat_encounter_id = models.CharField('SatuSehat Encounter ID', max_length=64, blank=True, null=True)
    satusehat_status       = models.CharField('Status Sync SatuSehat', max_length=15,
                                choices=[('NOT_SYNCED','Belum Disinkronkan'),('SYNCED','Tersinkronisasi'),('FAILED','Gagal Sync')],
                                default='NOT_SYNCED')

    # ── Antrean & Status Klinis ──
    FLAG_KHUSUS_CHOICES = [
        ('NORMAL',   'Normal'),
        ('AMBULANS', 'Rujukan Ambulans'),
        ('KRITIS',   'Kondisi Kritis / Resusitasi'),
    ]
    STATUS_ANTREAN_CHOICES = [
        ('MENUNGGU',        'Menunggu'),
        ('DIPANGGIL',       'Dipanggil'),
        ('SEDANG_DILAYANI', 'Sedang Dilayani'),
        ('SELESAI',         'Selesai'),
    ]
    nomor_antrean   = models.CharField('No. Antrean', max_length=25, blank=True)
    flag_khusus     = models.CharField('Flag Kondisi Khusus', max_length=10, choices=FLAG_KHUSUS_CHOICES, default='NORMAL')
    status_antrean  = models.CharField('Status Antrean', max_length=20, choices=STATUS_ANTREAN_CHOICES, default='MENUNGGU')

    # ── APM & Online Booking ──
    kode_booking       = models.CharField('Kode Booking Antrean', max_length=30, blank=True, db_index=True)
    token_batal        = models.CharField('Token Pembatalan APM', max_length=64, blank=True, unique=True, null=True, db_index=True)
    estimasi_pelayanan = models.TimeField('Estimasi Waktu Pelayanan', null=True, blank=True)
    is_apm             = models.BooleanField('Daftar via Mandiri / APM', default=False)
    is_checkin         = models.BooleanField('Sudah Check-In di Kiosk', default=False)
    waktu_checkin      = models.DateTimeField('Waktu Check-In Kiosk', null=True, blank=True)
    is_noshow          = models.BooleanField('Tercatat No-Show', default=False)
    wa_notifikasi_sent = models.BooleanField('Notifikasi WA Terkirim', default=False)

    # ── Tanda-Tanda Vital (TTV) ──
    ttv_sistole     = models.PositiveSmallIntegerField('Tekanan Darah Sistole (mmHg)', null=True, blank=True)
    ttv_diastole    = models.PositiveSmallIntegerField('Tekanan Darah Diastole (mmHg)', null=True, blank=True)
    ttv_nadi        = models.PositiveSmallIntegerField('Nadi (bpm)', null=True, blank=True)
    ttv_rr          = models.PositiveSmallIntegerField('Laju Napas / RR (x/menit)', null=True, blank=True)
    ttv_suhu        = models.DecimalField('Suhu (°C)', max_digits=4, decimal_places=1, null=True, blank=True)
    ttv_spo2        = models.PositiveSmallIntegerField('SpO2 (%)', null=True, blank=True)
    ttv_gcs         = models.CharField('Glasgow Coma Scale (GCS)', max_length=30, blank=True, help_text='Contoh: E4V5M6 (15) atau Somnolen')
    ttv_skala_nyeri = models.PositiveSmallIntegerField('Skala Nyeri (NRS 0-10)', null=True, blank=True, help_text='0 (Tidak Nyeri) s.d 10 (Sangat Hebat)')
    icd9_tindakan   = models.CharField('Tindakan Medis (ICD-9-CM)', max_length=300, blank=True)

    # ── Asesmen Awal IGD (Revisi 02 & Formulir Standar 3.09) ──
    keadaan_umum        = models.CharField('Keadaan Umum', max_length=30, blank=True, help_text='Baik / Sedang / Lemah / Buruk')
    kesadaran           = models.CharField('Tingkat Kesadaran', max_length=30, blank=True, help_text='Compos Mentis / Apatis / Somnolen / Sopor / Koma')
    nyeri_karakteristik = models.CharField('Karakteristik Nyeri', max_length=50, blank=True, help_text='Tumpul / Tajam/Tusuk / Terbakar / Denyut / Hilang-Timbul')
    fungsional_adl      = models.CharField('Aktivitas Sehari-hari (ADL)', max_length=50, blank=True, help_text='Mandiri / Bantuan Parsial / Ketergantungan Total')
    fisik_head_to_toe   = models.JSONField('Pemeriksaan Fisik Head-To-Toe (Standar 3.09)', default=dict, blank=True)

    anamnesis_rps          = models.TextField('Riwayat Penyakit Sekarang (RPS)', blank=True)
    anamnesis_rpd          = models.TextField('Riwayat Penyakit Dahulu (RPD)', blank=True)
    anamnesis_rpk          = models.TextField('Riwayat Penyakit Keluarga (RPK)', blank=True)
    anamnesis_obat         = models.TextField('Riwayat Pengobatan / Obat Saat Ini', blank=True)
    fisik_airway           = models.TextField('Airway Assessment', blank=True)
    fisik_breathing        = models.TextField('Breathing Assessment', blank=True)
    fisik_circulation      = models.TextField('Circulation Assessment', blank=True)
    fisik_disability       = models.TextField('Disability Assessment (Neuro)', blank=True)
    fisik_exposure         = models.TextField('Exposure / Environmental', blank=True)
    status_psikososial     = models.TextField('Status Psikologis & Sosial-Ekonomi', blank=True)
    status_spiritual       = models.TextField('Status Spiritual & Budaya', blank=True)
    skrining_alergi_status = models.CharField('Hasil Skrining Alergi', max_length=20, blank=True,
        choices=[('BELUM', 'Belum dikaji'), ('TIDAK_DIKETAHUI', 'Tidak diketahui'), ('TIDAK_ADA', 'Tidak ada alergi menurut anamnesis'), ('ADA', 'Ada alergi')])
    alergi_asesmen = models.TextField('Alergi pada Episode Ini', blank=True)
    hambatan_edukasi = models.TextField('Hambatan Edukasi', blank=True)
    skrining_gizi_detail = models.JSONField('Jawaban MST', default=dict, blank=True)
    fisik_lokalis = models.TextField('Status Lokalis', blank=True)
    penanda_anatomi = models.JSONField('Penanda Anatomi', default=list, blank=True)
    evaluasi_respon_terapi = models.TextField('Respons Terapi / Evaluasi Akhir', blank=True)
    diagnosis_mode = models.CharField('Sumber Diagnosis', max_length=8, default='MANUAL', choices=[('MANUAL','Manual'),('MASTER','Master'),('AI','Bantuan AI')])
    diagnosis_provenance = models.JSONField(default=dict, blank=True)
    skrining_jatuh_skor    = models.PositiveSmallIntegerField('Skor Risiko Jatuh', null=True, blank=True)
    skrining_jatuh_grade   = models.CharField('Grade Risiko Jatuh', max_length=20, blank=True, help_text='RENDAH / SEDANG / TINGGI')
    skrining_gizi_mst      = models.PositiveSmallIntegerField('Skor Skrining Gizi (MST)', null=True, blank=True)
    skrining_jatuh_detail  = models.JSONField('Detail Skrining Jatuh (Morse)', default=dict, blank=True)

    # ── Diagnosis Keperawatan 3S (SDKI / SLKI / SIKI) ──
    diagnosa_keperawatan_sdki   = models.TextField('Diagnosis Keperawatan (SDKI)', blank=True, help_text='Contoh: D.0077 - Nyeri Akut')
    luaran_keperawatan_slki     = models.TextField('Luaran Keperawatan (SLKI)', blank=True, help_text='Contoh: L.08066 - Tingkat Nyeri Menurun')
    intervensi_keperawatan_siki = models.TextField('Intervensi Keperawatan (SIKI)', blank=True, help_text='Contoh: I.08238 - Manajemen Nyeri')

    # ── Rujukan & Konsultasi ──
    sisrute_rs_tujuan = models.CharField('RS Tujuan Rujukan (SISRUTE)', max_length=200, blank=True)
    sisrute_alasan    = models.TextField('Alasan Rujukan Eksternal', blank=True)
    konsul_ke_poli    = models.CharField('Konsul ke Poliklinik', max_length=100, blank=True)
    konsul_catatan    = models.TextField('Catatan Konsultasi Internal', blank=True)

    # ── Meninggal Dunia ──
    waktu_kematian    = models.DateTimeField('Waktu Kematian', null=True, blank=True)
    penyebab_kematian = models.TextField('Penyebab Kematian', blank=True)

    # ── Asesmen Medis Awal IGD — Revisi Formulir ARIMA (sesuai dokumen ARIMA 2026) ──

    CARA_DATANG_CHOICES = [
        ('SENDIRI',  'Sendiri / Keluarga'),
        ('RUJUKAN',  'Rujukan (RS / Puskesmas / Klinik)'),
        ('AMBULANS', 'Ambulans'),
        ('POLISI',   'Polisi'),
    ]
    TRIASE_KATEGORI_CHOICES = [
        ('KATEGORI_1', 'Kategori 1'),
        ('KATEGORI_2', 'Kategori 2'),
        ('KATEGORI_3', 'Kategori 3'),
        ('KATEGORI_4', 'Kategori 4'),
        ('KATEGORI_5', 'Kategori 5 — bukan penetapan DOA'),
    ]
    KONDISI_AKHIR_CHOICES = [
        ('MEMBAIK',    'Membaik'),
        ('STABIL',     'Stabil'),
        ('MEMBURUK',   'Memburuk'),
        ('MENINGGAL',  'Meninggal (DOA / Di IGD)'),
    ]
    DISPOSISI_CHOICES = [
        ('RAWAT_INAP', 'Rawat Inap'),
        ('RAWAT_JALAN','Rawat Jalan / Pulang'),
        ('RUJUK',      'Rujuk ke RS Lain'),
        ('PAPS',       'Pulang Atas Permintaan Sendiri (PAPS)'),
        ('KONSUL',     'Konsultasi Poli — Tetap IGD'),
        ('TRANSFER',   'Transfer Layanan ke Poli'),
        ('MENINGGAL',  'Meninggal'),
    ]

    # I. Data Waktu & Response Time
    cara_datang             = models.CharField('Cara Datang', max_length=15, choices=CARA_DATANG_CHOICES, blank=True)
    waktu_asesmen_dokter    = models.CharField('Waktu Asesmen Dokter (WIB)', max_length=10, blank=True)
    waktu_disposisi         = models.CharField('Waktu Keputusan Disposisi (WIB)', max_length=10, blank=True)

    # II. Triase ATS / ESI Level
    triase_skala = models.CharField('Sistem Triase', max_length=10, blank=True,
                                   choices=[('ATS', 'ATS'), ('ESI', 'ESI'), ('WARNA', 'Warna operasional')])
    triase_kategori         = models.CharField('Kategori pada Sistem Triase Terpilih', max_length=15, choices=TRIASE_KATEGORI_CHOICES, blank=True)

    # III. Primary Survey — GCS detail, Tanda Vital Kualifikasi
    gcs_e                   = models.PositiveSmallIntegerField('GCS E (Eyes)', null=True, blank=True)
    gcs_v                   = models.PositiveSmallIntegerField('GCS V (Verbal)', null=True, blank=True)
    gcs_m                   = models.PositiveSmallIntegerField('GCS M (Motor)', null=True, blank=True)
    suhu_lokasi             = models.CharField('Lokasi Pengukuran Suhu', max_length=20, blank=True, help_text='Aksila / Oral / Rectal')
    nadi_kekuatan           = models.CharField('Kekuatan Nadi', max_length=15, blank=True, help_text='Kuat / Lemah')
    nadi_irama              = models.CharField('Irama Nadi', max_length=15, blank=True, help_text='Reguler / Ireguler')
    pernapasan_pola         = models.CharField('Pola Pernapasan', max_length=20, blank=True, help_text='Spontan / Adekuat / Takipnea')
    spo2_alat               = models.CharField('SpO2 via Alat', max_length=30, blank=True, help_text='Udara Bebas / Nasal Kanul / NRM')
    skala_nyeri_sifat       = models.CharField('Sifat Nyeri', max_length=30, blank=True, help_text='Akut / Kronis / Hilang Timbul / Menusuk / Panas')
    metode_risiko_jatuh     = models.CharField('Metode Skrining Risiko Jatuh', max_length=30, blank=True, help_text='Morse Fall Scale / Humpty Dumpty / Get Up and Go')

    # IV. Asesmen Psikososiospiritual
    status_emosional        = models.CharField('Status Emosional', max_length=30, blank=True, help_text='Kooperatif / Cemas / Agresif / Depresi')
    hambatan_komunikasi     = models.CharField('Hambatan Komunikasi', max_length=60, blank=True)
    kebutuhan_spiritual     = models.CharField('Kebutuhan Edukasi / Spiritual', max_length=100, blank=True)

    # V. Anamnesis — RPD Checklist (JSON list: ['HT', 'DM', 'Asma', ...])
    rpd_checklist           = models.JSONField('RPD Checklist (HT, DM, Asma, Jantung, ...)', default=list, blank=True)

    # VI. Secondary Survey — Pemeriksaan Fisik Lengkap (JSON per organ)
    secondary_survey_detail = models.JSONField('Secondary Survey Detail (Mata, THT, Kepala-Leher, Thorax, Abdomen, Ekstremitas)', default=dict, blank=True)

    # VII. Pemeriksaan Penunjang
    penunjang_radiologi_checklist  = models.JSONField('Radiologi Checklist (Thorax, CT, USG, X-Ray ...)', default=list, blank=True)
    penunjang_ekg                  = models.CharField('Hasil EKG', max_length=100, blank=True)
    penunjang_hasil_kritis         = models.TextField('Hasil Kritis Penunjang', blank=True)

    # VIII–IX. Diagnosis & Tatalaksana
    tatalaksana_resusitasi         = models.TextField('Resusitasi / Stabilisasi', blank=True)
    tatalaksana_terapi             = models.TextField('Terapi Farmakologi IGD', blank=True)
    tatalaksana_tindakan_check     = models.JSONField('Tindakan Medis IGD (Checklist)', default=list, blank=True)

    # X. Disposisi & Handover SBAR
    disposisi_kondisi_akhir        = models.CharField('Kondisi Akhir IGD', max_length=15, choices=KONDISI_AKHIR_CHOICES, blank=True)
    disposisi_tindak_lanjut        = models.CharField('Tindak Lanjut Disposisi', max_length=15, choices=DISPOSISI_CHOICES, blank=True)
    disposisi_ruang_rawat          = models.CharField('Ruang Rawat Inap / DPJP', max_length=200, blank=True)
    disposisi_kontrol_poli         = models.CharField('Kontrol Poli (Rawat Jalan)', max_length=100, blank=True)
    disposisi_kontrol_tgl          = models.CharField('Tanggal Kontrol', max_length=20, blank=True)
    disposisi_rujuk_rs             = models.CharField('RS Tujuan Rujukan', max_length=200, blank=True)
    disposisi_rujuk_alasan         = models.TextField('Alasan Rujukan', blank=True)
    sbar_situation                 = models.TextField('SBAR — Situation', blank=True)
    sbar_background                = models.TextField('SBAR — Background', blank=True)
    sbar_assessment                = models.TextField('SBAR — Assessment', blank=True)
    sbar_recommendation            = models.TextField('SBAR — Recommendation', blank=True)
    petugas_handover_perawat       = models.CharField('Nama Perawat Handover', max_length=150, blank=True)
    petugas_handover_jam           = models.CharField('Jam Handover Perawat', max_length=10, blank=True)
    petugas_handover_dokter        = models.CharField('Nama Dokter IGD / DPJP', max_length=150, blank=True)
    petugas_handover_dokter_jam    = models.CharField('Jam TTD Dokter IGD', max_length=10, blank=True)
    asesmen_catatan_waktu          = models.TextField('Catatan / Penyesuaian Waktu Pelayanan', blank=True)

    class Meta:
        verbose_name = 'Kunjungan Pasien'
        verbose_name_plural = 'Kunjungan Pasien'
        ordering = ['-tanggal_masuk']

    def __str__(self):
        return f'[{self.no_kunjungan}] {self.pasien.nama_lengkap} ({self.get_jenis_kunjungan_display()})'

    @property
    def lama_rawat(self):
        """Length of Stay dalam hari."""
        from django.utils import timezone
        end = self.tanggal_keluar or timezone.now()
        delta = end - self.tanggal_masuk
        return max(delta.days, 1)

    @property
    def is_aktif(self):
        return self.status not in ('PULANG', 'RUJUK', 'MENINGGAL')

    @property
    def bed_aktif(self):
        """Bed yang benar-benar ditempati pasien sekarang, atau ``None``.

        Hanya kunjungan rawat inap yang punya lokasi bed: ``bed_id`` saja tidak
        cukup, karena penempatan yang belum selesai (atau data lama) bisa
        meninggalkan bed terpasang pada kunjungan IGD/rajal yang belum — atau
        tidak pernah — diadmisikan. Setiap jalur yang mengadmisikan ke bangsal
        menandai kunjungannya ``RANAP`` (``BookingKamar.checkin``,
        ``admit_to_ranap``), jadi kedua penanda ini adalah invariannya.
        """
        if self.bed_id and (self.jenis_kunjungan == 'RANAP' or self.status == 'RANAP'):
            return self.bed
        return None

    @property
    def is_asesmen_awal_lengkap(self):
        """Compliance check: anamnesis, ABCDE airway / head-to-toe, diagnosis medis, AND diagnosis keperawatan 3S."""
        has_fisik = bool(
            self.fisik_airway.strip()
            or (self.fisik_head_to_toe and isinstance(self.fisik_head_to_toe, dict) and self.fisik_head_to_toe.get('kepala_leher', '').strip())
        )
        return bool(
            self.anamnesis_rps.strip()
            and has_fisik
            and self.diagnosa_masuk.strip()
            and self.diagnosa_keperawatan_sdki.strip()
        )

    @property
    def status_ep_ringkas(self):
        from klinis.models import AturanEpAsesmen
        rules = set(AturanEpAsesmen.objects.filter(wajib=True).values_list('sub_standard', flat=True))
        if not rules:
            return '-'
        rows = self.korelasi_ep.select_related('standard_item')
        terpenuhi = {r.standard_item.sub_standard for r in rows if r.status == 'TERPENUHI'}
        if rules <= terpenuhi:
            return 'TERPENUHI'
        return 'SEBAGIAN' if terpenuhi & rules else 'BELUM'

    @property
    def news_score(self):
        return self.hitung_news_score()[0]

    @property
    def news_category(self):
        return self.hitung_news_score()[1]

    def hitung_news_score(self):
        """
        National Early Warning Score (NEWS-2) from 5 TTV parameters.
        Returns: (int score, str category) — ('NORMAL'|'RENDAH'|'SEDANG'|'TINGGI').
        Gracefully handles None/missing values by treating them as 0 score.
        """
        score = 0
        # Respiratory Rate (RR)
        rr = self.ttv_rr
        if rr is not None:
            if rr <= 8 or rr >= 25:
                score += 3
            elif 21 <= rr <= 24:
                score += 2
            elif 9 <= rr <= 11:
                score += 1
        # SpO2 (saturation)
        spo2 = self.ttv_spo2
        if spo2 is not None:
            if spo2 <= 91:
                score += 3
            elif 92 <= spo2 <= 93:
                score += 2
            elif 94 <= spo2 <= 95:
                score += 1
        # Systolic BP
        bp = self.ttv_sistole
        if bp is not None:
            if bp <= 90 or bp >= 220:
                score += 3
            elif 91 <= bp <= 100:
                score += 2
            elif 101 <= bp <= 110:
                score += 1
        # Heart Rate (Pulse)
        hr = self.ttv_nadi
        if hr is not None:
            if hr <= 40 or hr >= 131:
                score += 3
            elif 111 <= hr <= 130:
                score += 2
            elif (41 <= hr <= 50) or (91 <= hr <= 110):
                score += 1
        # Temperature
        temp = self.ttv_suhu
        if temp is not None:
            if temp <= 35.0:
                score += 3
            elif temp >= 39.1:
                score += 2
            elif (35.1 <= temp <= 36.0) or (38.1 <= temp <= 39.0):
                score += 1
        if score == 0:
            category = 'NORMAL'
        elif score <= 4:
            category = 'RENDAH'
        elif score <= 6:
            category = 'SEDANG'
        else:
            category = 'TINGGI'
        return score, category

    def admit_to_ranap(self, bed, dpjp=None, catatan=''):
        """Transfer / admit patient to Inpatient (RANAP) and lock the bed."""
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
                self.catatan_admisi = f"{self.catatan_admisi}\n[Admisi Ranap] {catatan}".strip()
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
            total = sum(b.subtotal for b in self.billing.all())
            DischargeRecord.objects.update_or_create(
                kunjungan=self,
                defaults={
                    'tanggal_discharge': tgl,
                    'kondisi_pulang':    kondisi,
                    'resume_medis':      resume or 'Pelayanan selesai.',
                    'edukasi_pulang':    edukasi,
                    'obat_pulang':       obat,
                    'jadwal_kontrol':    kontrol,
                    'total_tagihan':     total,
                    'status_clearance':  'CLEARANCE',
                    'dibuat_oleh':       user,
                }
            )

    def save(self, *args, **kwargs):
        if self.jenis_kunjungan == 'IGD':
            self.poliklinik = 'IGD'
            if not self.unit_kerja_id or getattr(self.unit_kerja, 'code', None) != 'IGD':
                from akreditasi.models import UnitKerja
                igd_unit = UnitKerja.objects.filter(code='IGD').first()
                if igd_unit:
                    self.unit_kerja = igd_unit
        elif not self.unit_kerja_id:
            if self.bed and getattr(self.bed, 'ruangan', None) and getattr(self.bed.ruangan, 'unit_kerja', None):
                self.unit_kerja = self.bed.ruangan.unit_kerja
            elif self.jenis_kunjungan:
                from akreditasi.models import UnitKerja
                from .unit_scope import DEFAULT_UNIT_BY_JENIS
                code = DEFAULT_UNIT_BY_JENIS.get(self.jenis_kunjungan)
                if code:
                    unit = UnitKerja.objects.filter(code__iexact=code).first()
                    if unit:
                        self.unit_kerja = unit
        super().save(*args, **kwargs)


# ── 4. Asesmen Risiko Klinis ─────────────────────────────────────────────────

class AsesmenRisikoKlinis(models.Model):
    JENIS_ASESMEN = [
        ('JATUH_MORSE',    'Risiko Jatuh — Morse Fall Scale (Dewasa)'),
        ('JATUH_HUMPTY',   'Risiko Jatuh — Humpty Dumpty (Anak)'),
        ('NYERI',          'Asesmen Nyeri (NRS/VAS)'),
        ('NUTRISI',        'Asesmen Nutrisi (MNA/NRS-2002)'),
        ('PPI',            'Pencegahan Infeksi (PPI Bundle)'),
        ('ALERGI',         'Asesmen Alergi'),
    ]
    GRADE = [
        ('RENDAH',   'Rendah'),
        ('SEDANG',   'Sedang'),
        ('TINGGI',   'Tinggi'),
        ('SANGAT_TINGGI', 'Sangat Tinggi'),
    ]

    kunjungan    = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='asesmen_risiko')
    jenis        = models.CharField('Jenis Asesmen', max_length=20, choices=JENIS_ASESMEN)
    skor         = models.IntegerField('Skor', default=0)
    grade        = models.CharField('Grade Risiko', max_length=15, choices=GRADE, blank=True)
    temuan       = models.TextField('Temuan / Detail Asesmen', blank=True)
    intervensi   = models.TextField('Intervensi yang Dilakukan', blank=True)
    dinilai_oleh = models.CharField('Dinilai Oleh', max_length=150, blank=True)
    tanggal      = models.DateTimeField('Tanggal Asesmen', auto_now_add=True)

    class Meta:
        verbose_name = 'Asesmen Risiko Klinis'
        verbose_name_plural = 'Asesmen Risiko Klinis'
        ordering = ['-tanggal']

    def __str__(self):
        return f'{self.get_jenis_display()} — {self.kunjungan.pasien.nama_lengkap} ({self.grade})'


# ── 5. CPPT (Catatan Perkembangan Pasien Terintegrasi) ───────────────────────

class CPPT(models.Model):
    PROFESI = [
        ('DOKTER',   'Dokter / DPJP'),
        ('PERAWAT',  'Perawat'),
        ('FARMASI',  'Farmasi / Apoteker'),
        ('GIZI',     'Gizi / Dietisien'),
        ('REHAB',    'Rehabilitasi Medik'),
        ('BIDAN',    'Bidan'),
        ('LAINNYA',  'PPA Lainnya'),
    ]

    kunjungan      = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='cppt')
    profesi        = models.CharField('Profesi PPA', max_length=10, choices=PROFESI)
    nama_ppa       = models.CharField('Nama PPA', max_length=150)
    tanggal        = models.DateTimeField('Tanggal & Jam')
    subjektif      = models.TextField('S — Subjektif (Keluhan)')
    objektif       = models.TextField('O — Objektif (Pemeriksaan)')
    asesmen        = models.TextField('A — Asesmen (Diagnosa)')
    plan           = models.TextField('P — Plan (Rencana)')
    verifikasi_dpjp = models.BooleanField('Terverifikasi DPJP', default=False)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='cppt_authored')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'CPPT'
        verbose_name_plural = 'CPPT (Catatan Perkembangan Pasien)'
        ordering = ['-tanggal']

    def __str__(self):
        return f'CPPT [{self.get_profesi_display()}] — {self.kunjungan.pasien.nama_lengkap} {self.tanggal.strftime("%d/%m/%Y %H:%M")}'


# ── 6. Billing ───────────────────────────────────────────────────────────────

class BillingItem(models.Model):
    KATEGORI = [
        ('JASA_MEDIS',  'Jasa Medis / Tindakan'),
        ('OBAT',        'Obat & BMHP'),
        ('LAB',         'Laboratorium'),
        ('RADIOLOGI',   'Radiologi / Imaging'),
        ('KAMAR',       'Biaya Kamar / Akomodasi'),
        ('ADMIN',       'Administrasi'),
        ('LAINNYA',     'Lainnya'),
    ]

    SUMBER = [('MANUAL', 'Input Manual'), ('ASESMEN', 'Otomatis dari Asesmen')]

    kunjungan  = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='billing')
    kategori   = models.CharField('Kategori', max_length=15, choices=KATEGORI)
    nama_item  = models.CharField('Nama Item', max_length=200)
    kuantitas  = models.DecimalField('Kuantitas', max_digits=8, decimal_places=2, default=1)
    harga_satuan = models.DecimalField('Harga Satuan (Rp)', max_digits=12, decimal_places=2, default=0)
    kode_icd   = models.CharField('Kode ICD-10/9-CM', max_length=20, blank=True)
    sumber     = models.CharField('Sumber', max_length=10, choices=SUMBER, default='MANUAL')
    tanggal    = models.DateTimeField('Tanggal', auto_now_add=True)
    dicatat_oleh = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Billing Item'
        verbose_name_plural = 'Billing Pasien'
        ordering = ['-tanggal']

    def __str__(self):
        return f'{self.nama_item} — {self.kunjungan.pasien.nama_lengkap}'

    @property
    def subtotal(self):
        return self.kuantitas * self.harga_satuan


# ── 7. Discharge / Pulang ────────────────────────────────────────────────────

class DischargeRecord(models.Model):
    KONDISI_PULANG = [
        ('MEMBAIK',    'Kondisi Membaik'),
        ('SEMBUH',     'Sembuh'),
        ('APS',        'Atas Permintaan Sendiri (APS)'),
        ('RUJUK',      'Dirujuk ke RS Lain'),
        ('MENINGGAL',  'Meninggal'),
    ]
    STATUS_CLEARANCE = [
        ('PROSES',    'Proses Verifikasi'),
        ('CLEARANCE', 'Clearance / Bebas Administrasi'),
    ]

    kunjungan         = models.OneToOneField(KunjunganPasien, on_delete=models.CASCADE, related_name='discharge')
    tanggal_discharge = models.DateTimeField('Tanggal Discharge')
    kondisi_pulang    = models.CharField('Kondisi Saat Pulang', max_length=15, choices=KONDISI_PULANG)
    resume_medis      = models.TextField('Resume Medis (Discharge Summary)')
    edukasi_pulang    = models.TextField('Edukasi & Instruksi Pulang', blank=True)
    obat_pulang       = models.TextField('Obat Pulang', blank=True)
    jadwal_kontrol    = models.DateField('Jadwal Kontrol Ulang', null=True, blank=True)
    total_tagihan     = models.DecimalField('Total Tagihan (Rp)', max_digits=14, decimal_places=2, default=0)
    status_clearance  = models.CharField('Status Clearance', max_length=15, choices=STATUS_CLEARANCE, default='PROSES')
    dibuat_oleh       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    # ── PAPS (Pulang Atas Permintaan Sendiri) ──
    paps_alasan       = models.TextField('Alasan PAPS', blank=True)
    paps_nama_penolak = models.CharField('Nama Pasien / Keluarga Penolak', max_length=150, blank=True)

    # ── SKDP (Surat Keterangan Dalam Perawatan) ──
    skdp_nomor        = models.CharField('Nomor SKDP', max_length=50, blank=True)
    skdp_diagnosa     = models.CharField('Diagnosa SKDP', max_length=250, blank=True)
    skdp_terapi       = models.TextField('Rencana Terapi Lanjutan', blank=True)

    class Meta:
        verbose_name = 'Discharge Record'
        verbose_name_plural = 'Discharge Records'

    def __str__(self):
        return f'Discharge [{self.kunjungan.pasien.nama_lengkap}] {self.tanggal_discharge.strftime("%d/%m/%Y")}'


# ── 7b. Order Penunjang (Laboratorium & Radiologi) ───────────────────────────

class OrderPenunjang(models.Model):
    catalogue_item = models.ForeignKey('klinis.ItemPenunjang', null=True, blank=True, on_delete=models.PROTECT)
    catalogue_snapshot = models.JSONField(default=dict, blank=True)
    batch_id = models.UUIDField(null=True, blank=True)
    preparation = models.JSONField(default=dict, blank=True)
    diagnosis = models.ForeignKey('DiagnosisKunjungan', null=True, blank=True, on_delete=models.PROTECT)
    ordered_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    destination = models.ForeignKey('akreditasi.UnitKerja', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    JENIS_CHOICES = [
        ('LAB',       'Laboratorium'),
        ('RADIOLOGI', 'Radiologi / Imaging'),
        ('EKG',       'Elektrokardiografi'),
        ('LAINNYA',   'Penunjang Lainnya'),
    ]
    PRIORITAS_CHOICES = [
        ('CITO',  'CITO / Segera'),
        ('RUTIN', 'Rutin'),
    ]
    STATUS_CHOICES = [
        ('ORDERED', 'Terkirim'),
        ('PROSES',  'Dalam Pemeriksaan'),
        ('SELESAI', 'Selesai / Hasil Tersedia'),
    ]

    kunjungan         = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='order_penunjang')
    jenis             = models.CharField('Jenis Penunjang', max_length=15, choices=JENIS_CHOICES)
    nama_pemeriksaan  = models.CharField('Nama Pemeriksaan / Tindakan', max_length=255)
    catatan_klinis    = models.TextField('Catatan Klinis / Indikasi', blank=True)
    prioritas         = models.CharField('Prioritas', max_length=10, choices=PRIORITAS_CHOICES, default='RUTIN')
    status            = models.CharField('Status Order', max_length=15, choices=STATUS_CHOICES, default='ORDERED')
    dokter_pengirim        = models.CharField('Dokter Pengirim', max_length=150, blank=True)
    hasil_pemeriksaan      = models.TextField('Hasil Pemeriksaan', blank=True)
    result_recorded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    result_recorded_at = models.DateTimeField(null=True, blank=True)
    is_critical_value      = models.BooleanField('Critical Value Alert', default=False)
    critical_value_catatan = models.CharField('Catatan Nilai Kritis', max_length=200, blank=True)
    parameter_list         = models.JSONField('Daftar Parameter Pemeriksaan', default=list, blank=True)
    kondisi_sampel         = models.CharField('Kondisi Sampel', max_length=30, blank=True, help_text='Puasa / Tidak Puasa / Hamil')
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Penunjang'
        verbose_name_plural = 'Order Penunjang (Lab / Radiologi)'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_jenis_display()}] {self.nama_pemeriksaan} — {self.kunjungan.pasien.nama_lengkap}'


# ── 8. E-Prescribing & Farmasi ────────────────────────────────────────────────

class ResepElektronik(models.Model):
    version = models.PositiveIntegerField(default=0)
    serving_unit = models.ForeignKey('akreditasi.UnitKerja', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    submitted_snapshot = models.JSONField(default=dict, blank=True)
    policy_version = models.CharField(max_length=100, blank=True)
    financial_pending = models.BooleanField(default=False)
    STATUS_RESEP = [
        ('DRAFT',       'Draft Dokter'),
        ('DIKIRIM',     'Terkirim ke Farmasi'),
        ('DISPENSING',  'Sedang Diracik / Dispensing'),
        ('SELESAI',     'Selesai & Diserahkan'),
        ('BATAL',       'Dibatalkan'),
    ]
    JENIS_RESEP = [
        ('RAWAT_INAP',  'Rawat Inap (Depo Ranap)'),
        ('RAWAT_JALAN', 'Rawat Jalan (Depo Rajal)'),
        ('IGD',         'IGD Cito'),
        ('PULANG',      'Obat Pulang / Discharge'),
    ]

    no_resep         = models.CharField('No. Resep', max_length=30, unique=True)
    kunjungan        = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='resep_list')
    dokter_peresep   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resep_dibuat')
    tanggal_resep    = models.DateTimeField('Waktu Dibuat', auto_now_add=True)
    jenis_resep      = models.CharField('Jenis Resep', max_length=15, choices=JENIS_RESEP, default='RAWAT_INAP')
    status           = models.CharField('Status Farmasi', max_length=15, choices=STATUS_RESEP, default='DIKIRIM')
    catatan_dokter   = models.CharField('Catatan Dokter / Iter', max_length=250, blank=True)
    catatan_apoteker = models.CharField('Catatan / Telaah Apoteker', max_length=250, blank=True)
    apoteker         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resep_diproses')
    waktu_selesai    = models.DateTimeField('Waktu Selesai Penyerahan', null=True, blank=True)

    class Meta:
        verbose_name = 'Resep Elektronik'
        verbose_name_plural = 'Resep Elektronik (Farmasi)'
        ordering = ['-tanggal_resep']

    def __str__(self):
        return f'{self.no_resep} — {self.kunjungan.pasien.nama_lengkap} ({self.get_status_display()})'

    @property
    def total_biaya(self):
        return sum((item.subtotal for item in self.items.all() if item.subtotal is not None), 0)


class ResepDetail(models.Model):
    product = models.ForeignKey('klinis.ProdukFarmasi', null=True, blank=True, on_delete=models.PROTECT)
    product_snapshot = models.JSONField(default=dict, blank=True)
    regimen = models.JSONField(default=dict, blank=True)
    quantity_decimal = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    reference_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quantity_reason = models.TextField(blank=True)
    kind = models.CharField(max_length=8, blank=True)
    billing_item = models.OneToOneField('BillingItem', null=True, blank=True, on_delete=models.PROTECT, related_name='prescription_detail')
    BENTUK_SEDIAAN = [
        ('TABLET',  'Tablet / Kaplet'),
        ('KAPSUL',  'Kapsul'),
        ('SIRUP',   'Sirup / Suspensi'),
        ('INJEKSI', 'Injeksi / Ampul / Vial'),
        ('INFUS',   'Cairan Infus'),
        ('SALEP',   'Salep / Krim / Tetes'),
        ('PUYER',   'Puyer / Racikan'),
    ]

    resep          = models.ForeignKey(ResepElektronik, on_delete=models.CASCADE, related_name='items')
    nama_obat      = models.CharField('Nama Obat / Alkes', max_length=150)
    bentuk_sediaan = models.CharField('Bentuk', max_length=10, choices=BENTUK_SEDIAAN, default='TABLET')
    dosis          = models.CharField('Dosis', max_length=50, help_text='Contoh: 500 mg, 1 gr, 100 ml')
    aturan_pakai   = models.CharField('Signa / Aturan Pakai', max_length=100, help_text='Contoh: 3x1 tablet sesudah makan')
    jumlah         = models.PositiveIntegerField('Jumlah', default=1)
    harga_satuan   = models.DecimalField('Harga Satuan (Rp)', max_digits=12, decimal_places=2, default=0)
    catatan_khusus = models.CharField('Catatan Khusus (Sebelum/Sesudah Makan, dll)', max_length=150, blank=True)

    class Meta:
        verbose_name = 'Detail Obat Resep'
        verbose_name_plural = 'Detail Obat Resep'

    def __str__(self):
        return f'{self.nama_obat} ({self.aturan_pakai}) x {self.jumlah}'

    @property
    def subtotal(self):
        if self.product_id:
            return self.quantity_decimal * self.reference_price if self.quantity_decimal is not None and self.reference_price is not None else None
        return self.jumlah * self.harga_satuan


# ── 10. Pemesanan Kamar (Bed Booking) ────────────────────────────────────────

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

    def __str__(self):
        return f'{self.nomor_booking} - {self.pasien.nama_lengkap} -> {self.bed}'

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


# ── 11. General Consent Rawat Inap (STARKES HPK) ───────────────────────────

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

    kunjungan                  = models.OneToOneField('KunjunganPasien', on_delete=models.CASCADE, related_name='general_consent_doc')
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

    def __str__(self):
        return f'General Consent Ranap - {self.kunjungan.pasien.nama_lengkap} (Wali: {self.nama_pj})'

    @property
    def is_lengkap(self):
        return bool(self.nama_pj and self.nik_pj and self.setuju_perawatan_umum and self.setuju_pelepasan_informasi)


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


# ── 12. Korelasi EP Akreditasi & Lampiran Asesmen ──────────────────────────────

class KorelasiEpAsesmen(models.Model):
    STATUS = [
        ('TERPENUHI', 'Terpenuhi'),
        ('BELUM',     'Belum Terpenuhi'),
        ('NA',        'Tidak Berlaku'),
    ]
    kunjungan     = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='korelasi_ep')
    standard_item = models.ForeignKey('akreditasi.StandardItem', on_delete=models.CASCADE, related_name='korelasi_asesmen')
    status        = models.CharField('Status Pemenuhan', max_length=12, choices=STATUS, default='BELUM')
    catatan       = models.TextField('Catatan Verifikasi / Bukti', blank=True)
    diverifikasi_oleh = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verifikasi_ep_asesmen')
    diverifikasi_pada = models.DateTimeField('Waktu Verifikasi', null=True, blank=True)

    class Meta:
        verbose_name = 'Korelasi EP Asesmen'
        verbose_name_plural = 'Korelasi EP Asesmen'
        unique_together = [('kunjungan', 'standard_item')]

    def __str__(self):
        return f'{self.kunjungan.no_kunjungan} — {self.standard_item.sub_standard} ({self.get_status_display()})'


class LampiranAsesmen(models.Model):
    JENIS = [
        ('ASESMEN',   'Dokumen Asesmen'),
        ('PENUNJANG', 'Hasil Penunjang'),
        ('RUJUKAN',   'Surat Rujukan'),
        ('LAINNYA',   'Lainnya'),
    ]
    kunjungan     = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='lampiran_asesmen')
    jenis         = models.CharField('Jenis Lampiran', max_length=12, choices=JENIS, default='ASESMEN')
    file          = models.FileField('File Dokumen', upload_to='asesmen/%Y/%m/')
    nama_asli     = models.CharField('Nama Asli File', max_length=255)
    ukuran        = models.PositiveIntegerField('Ukuran File (bytes)', default=0)
    diunggah_oleh = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='unggah_lampiran_asesmen')
    diunggah_pada = models.DateTimeField('Waktu Unggah', auto_now_add=True)

    class Meta:
        verbose_name = 'Lampiran Asesmen'
        verbose_name_plural = 'Lampiran Asesmen'
        ordering = ['-diunggah_pada']

    def __str__(self):
        return f'{self.nama_asli} ({self.kunjungan.no_kunjungan})'


# ── 13. Baris Tindakan Asesmen (tarif editable + EP per item) ─────────────────

class TindakanAsesmen(models.Model):
    lokasi_anatomis = models.CharField(max_length=200, blank=True)
    catatan_klinis = models.TextField(blank=True)
    recorded_at = models.DateTimeField(null=True, blank=True)
    assistance_provenance = models.JSONField(default=dict, blank=True)
    JENIS = [
        ('ICD9', 'ICD-9-CM'),
        ('SIKI', 'SIKI'),
        ('BEBAS', 'Manual / Bebas'),
    ]
    SUMBER = [
        ('MASTER', 'Master'),
        ('SARAN', 'Saran Sistem'),
        ('MANUAL', 'Input Manual'),
        ('AI', 'Bantuan AI yang Diterima'),
    ]
    EP_STATUS = [
        ('TERPENUHI', 'Terpenuhi'),
        ('BELUM', 'Belum Lengkap'),
        ('NA', 'Tidak Berlaku'),
    ]

    kunjungan   = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='tindakan_asesmen')
    urutan      = models.PositiveIntegerField('Urutan', default=1)
    jenis       = models.CharField('Jenis Tindakan', max_length=6, choices=JENIS, default='ICD9')
    icd9        = models.ForeignKey('klinis.MasterIcd9', null=True, blank=True,
                                    on_delete=models.PROTECT, related_name='tindakan_asesmen')
    siki        = models.ForeignKey('klinis.SikiIntervensi', null=True, blank=True,
                                    on_delete=models.PROTECT, related_name='tindakan_asesmen')
    kode        = models.CharField('Kode Tindakan', max_length=20, blank=True)
    nama        = models.CharField('Nama Tindakan (dapat diedit)', max_length=200)
    sumber_data = models.CharField('Sumber Data', max_length=8, choices=SUMBER, default='MANUAL')
    tarif_acuan = models.DecimalField('Tarif Acuan Master (Rp)', max_digits=12, decimal_places=2,
                                      null=True, blank=True)
    tarif       = models.DecimalField('Tarif Final / Override (Rp)', max_digits=12, decimal_places=2,
                                      null=True, blank=True)
    catatan_tarif = models.TextField('Catatan Perubahan Tarif', blank=True)
    standard_item = models.ForeignKey('akreditasi.StandardItem', null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='tindakan_asesmen')
    ep_status     = models.CharField('Status EP', max_length=12, choices=EP_STATUS, default='BELUM')
    ep_catatan    = models.TextField('Catatan Bukti EP', blank=True)
    billing_item  = models.OneToOneField(BillingItem, null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name='tindakan_asesmen')
    execution_status = models.CharField(max_length=10, default='LEGACY', choices=[('LEGACY','Historis'),('PLANNED','Direncanakan'),('PERFORMED','Dilaksanakan'),('CANCELLED','Dibatalkan')])
    execution_team = models.CharField(max_length=12, blank=True, choices=[('MEDIS','Medis'),('KEPERAWATAN','Keperawatan')])
    tarif_penjamin = models.CharField(max_length=10, blank=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    performed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    performed_at = models.DateTimeField(null=True, blank=True)
    execution_cppt = models.ForeignKey(CPPT, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    diubah_oleh   = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name='tindakan_asesmen_diubah')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tindakan Asesmen'
        verbose_name_plural = 'Tindakan Asesmen'
        unique_together = [('kunjungan', 'urutan')]
        ordering = ['urutan']

    def __str__(self):
        return f'{self.kode} {self.nama} ({self.kunjungan.no_kunjungan})'

    @property
    def tarif_efektif(self):
        """Override bila diisi, jika tidak tarif acuan master. None = belum ditetapkan."""
        return self.tarif if self.tarif is not None else self.tarif_acuan

    @property
    def ep_lengkap(self):
        return self.standard_item_id is None or self.ep_status in ('TERPENUHI', 'NA')


# ── 12. Anjungan Pendaftaran Mandiri (APM) & Antrean Online ──────────────────

class DiagnosisKunjungan(models.Model):
    kunjungan = models.ForeignKey(KunjunganPasien, on_delete=models.PROTECT, related_name='diagnoses')
    icd10 = models.ForeignKey('klinis.MasterIcd10', null=True, blank=True, on_delete=models.PROTECT)
    kode = models.CharField(max_length=10, blank=True)
    nama = models.CharField(max_length=2000)
    mode = models.CharField(max_length=6, choices=[('MANUAL', 'Manual'), ('MASTER', 'Master'), ('AI', 'AI')])
    is_primary = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    provenance = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['kunjungan'], condition=models.Q(active=True, is_primary=True), name='unique_active_primary_diagnosis')]


class IgdAssessmentWorkflow(models.Model):
    signatures = models.JSONField(default=dict, blank=True)
    exemptions = models.JSONField(default=dict, blank=True)
    kunjungan = models.OneToOneField(KunjunganPasien, on_delete=models.PROTECT, related_name='igd_workflow')
    origin_unit = models.ForeignKey('akreditasi.UnitKerja', null=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=5, choices=[('DRAFT', 'Draft'), ('FINAL', 'Final')], default='DRAFT')
    version = models.PositiveIntegerField(default=0)
    last_step = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(11)])
    schema_version = models.PositiveSmallIntegerField(default=1)
    updated_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)
    finalized_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    finalized_at = models.DateTimeField(null=True, blank=True)


class IgdVitalObservation(models.Model):
    workflow = models.ForeignKey(IgdAssessmentWorkflow, on_delete=models.PROTECT, related_name='observations')
    phase = models.CharField(max_length=10, choices=[('INITIAL', 'Awal'), ('EVALUATION', 'Evaluasi')])
    observed_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    data = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    corrects = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ['observed_at', 'pk']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Observasi tidak dapat ditimpa; catat pengukuran/koreksi baru.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Riwayat observasi tidak dapat dihapus.')


class IgdAssessmentRevision(models.Model):
    workflow = models.ForeignKey(IgdAssessmentWorkflow, on_delete=models.PROTECT, related_name='revisions')
    revision = models.PositiveIntegerField()
    snapshot = models.JSONField(encoder=DjangoJSONEncoder)
    reason = models.TextField(blank=True)
    signed_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['workflow', 'revision'], name='unique_igd_signed_revision')]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Revisi bertanda tangan tidak dapat ditimpa.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Revisi bertanda tangan tidak dapat dihapus.')


class IgdWorkflowAction(models.Model):
    workflow = models.ForeignKey(IgdAssessmentWorkflow, on_delete=models.PROTECT, related_name='actions')
    request_id = models.UUIDField()
    operation = models.CharField(max_length=30)
    digest = models.CharField(max_length=64)
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    result = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['workflow', 'request_id'], name='unique_igd_action_request')]


class AntreanHarianCounter(models.Model):
    tanggal = models.DateField()
    prefix = models.CharField(max_length=8)
    nomor_terakhir = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tanggal', 'prefix'], name='unique_antrean_harian_prefix'),
        ]


class JadwalDokterPoli(models.Model):
    STATUS_CHOICES = [
        ('BUKA', 'Buka / Kuota Tersedia'),
        ('PENUH', 'Kuota Penuh'),
        ('LIBUR', 'Libur / Tutup'),
    ]

    nama_dokter             = models.CharField('Nama Lengkap Dokter', max_length=150)
    gelar                   = models.CharField('Gelar / Spesialisasi', max_length=150, blank=True)
    poliklinik              = models.CharField('Poliklinik Tujuan', max_length=100, choices=POLIKLINIK_CHOICES)
    hari_praktik            = models.CharField('Hari Praktik', max_length=100, default='Senin - Jumat')
    jam_mulai               = models.TimeField('Jam Mulai Praktik')
    jam_selesai             = models.TimeField('Jam Selesai Praktik')
    kuota_maksimal          = models.PositiveIntegerField('Kuota Maksimal Harian', default=20)
    durasi_per_pasien_menit = models.PositiveIntegerField('Durasi per Pasien (Menit)', default=15)
    status_ketersediaan     = models.CharField('Status Ketersediaan', max_length=20, choices=STATUS_CHOICES, default='BUKA')
    foto_dokter             = models.FileField('Foto Dokter', upload_to='dokter/foto/%Y/', blank=True, null=True)
    foto_url                = models.URLField('URL Foto Avatar Dokter', blank=True)
    keterangan              = models.TextField('Keterangan / Pengumuman', blank=True)
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Jadwal Dokter Poli (APM)'
        verbose_name_plural = 'Jadwal Dokter Poli (APM)'
        ordering = ['poliklinik', 'nama_dokter']

    def __str__(self):
        return f"{self.nama_dokter} — {self.get_poliklinik_display()} ({self.jam_mulai.strftime('%H:%M')} - {self.jam_selesai.strftime('%H:%M')})"

    def get_terdaftar_hari_ini(self, tanggal=None):
        from django.utils import timezone
        tgl = tanggal or timezone.localdate()
        return KunjunganPasien.objects.filter(
            tanggal_masuk__date=tgl,
            jenis_kunjungan='RAJAL',
            dpjp=self.nama_dokter,
            poliklinik=self.poliklinik
        ).exclude(status='BATAL').count()

    def get_sisa_kuota(self, tanggal=None):
        terdaftar = self.get_terdaftar_hari_ini(tanggal)
        return max(0, self.kuota_maksimal - terdaftar)

    def is_tersedia(self, tanggal=None):
        if self.status_ketersediaan != 'BUKA':
            return False
        return self.get_sisa_kuota(tanggal) > 0

    def get_next_estimasi_jam(self, tanggal=None):
        from django.utils import timezone
        appointments = list(KunjunganPasien.objects.filter(
            tanggal_masuk__date=tanggal or timezone.localdate(),
            jenis_kunjungan='RAJAL', dpjp=self.nama_dokter, poliklinik=self.poliklinik,
        ).exclude(status='BATAL').values_list('estimasi_pelayanan', flat=True))
        occupied = {value for value in appointments if value is not None}
        unknown = appointments.count(None)
        for position in range(1, self.kuota_maksimal + 1):
            candidate = self.hitung_estimasi_jam(position)
            if candidate in occupied:
                continue
            if unknown:
                unknown -= 1
                occupied.add(candidate)
                continue
            return candidate
        return None

    def hitung_estimasi_jam(self, urutan=None):
        import datetime
        if urutan is None:
            urutan = self.get_terdaftar_hari_ini() + 1
        minutes_offset = (max(1, urutan) - 1) * self.durasi_per_pasien_menit
        base_dt = datetime.datetime.combine(datetime.date.today(), self.jam_mulai)
        est_dt = base_dt + datetime.timedelta(minutes=minutes_offset)
        return est_dt.time()


class WhatsAppLog(models.Model):
    JENIS_PILIHAN = [
        ('TIKET_APM', 'Tiket Pendaftaran APM'),
        ('REMINDER_H1', 'Pengingat H-1 Antrean'),
        ('BATAL_APM', 'Konfirmasi Pembatalan APM'),
        ('NOTIFIKASI_IGD', 'Alert Fast-Track IGD'),
        ('LAINNYA', 'Lainnya'),
    ]
    STATUS_PILIHAN = [
        ('SENT', 'Terkirim'),
        ('FAILED', 'Gagal'),
        ('SIMULASI', 'Simulasi / Dummy'),
    ]

    nomor_tujuan = models.CharField('Nomor WhatsApp Tujuan', max_length=30)
    jenis_pesan  = models.CharField('Jenis Notifikasi', max_length=30, choices=JENIS_PILIHAN, default='TIKET_APM')
    pesan        = models.TextField('Isi Pesan WhatsApp')
    status       = models.CharField('Status Pengiriman', max_length=20, choices=STATUS_PILIHAN, default='SIMULASI')
    kunjungan    = models.ForeignKey(KunjunganPasien, on_delete=models.SET_NULL, null=True, blank=True, related_name='wa_logs')
    response_api = models.JSONField('Response Gateway API', default=dict, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log Notifikasi WhatsApp'
        verbose_name_plural = 'Log Notifikasi WhatsApp'
        ordering = ['-created_at']

    def __str__(self):
        return f"WA to {self.nomor_tujuan} [{self.jenis_pesan}] - {self.status}"


class AntreanBpjsTaskLog(models.Model):
    TASK_CHOICES = [
        (1, 'Mulai waktu tunggu admisi'),
        (2, 'Akhir waktu tunggu admisi / mulai pelayanan admisi'),
        (3, 'Akhir pelayanan admisi / check-in APM / mulai waktu tunggu poli'),
        (4, 'Mulai pemeriksaan dokter'),
        (5, 'Selesai pemeriksaan dokter / mulai waktu tunggu farmasi'),
        (6, 'Mulai pelayanan farmasi'),
        (7, 'Selesai pelayanan farmasi / serah terima obat'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Terkirim ke BPJS'),
        ('FAILED', 'Gagal Kirim'),
        ('SIMULATED', 'Simulasi BPJS'),
    ]

    kunjungan     = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='bpjs_task_logs')
    task_id       = models.PositiveSmallIntegerField('Task ID (1-7)', choices=TASK_CHOICES)
    nama_task     = models.CharField('Nama Task ID', max_length=150, blank=True)
    waktu         = models.DateTimeField('Waktu Kejadian (WIB)', default=timezone.now)
    status_kirim  = models.CharField('Status Bridging BPJS', max_length=20, choices=STATUS_CHOICES, default='SIMULATED')
    response_bpjs = models.JSONField('Response BPJS API', default=dict, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log Antrean BPJS 7 Task ID'
        verbose_name_plural = 'Log Antrean BPJS 7 Task ID'
        ordering = ['kunjungan', 'task_id']

    def __str__(self):
        return f"[{self.kunjungan.no_kunjungan}] Task {self.task_id}: {self.nama_task} ({self.status_kirim})"





