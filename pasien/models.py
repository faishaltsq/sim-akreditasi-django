"""
Modul Manajemen Pasien MonsisKami (ARIMA System)
Tahap 1–5: Pendaftaran → Pelayanan → Ranap → Billing → Discharge
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


# ── 1. Master Pasien ─────────────────────────────────────────────────────────

class Pasien(models.Model):
    JENIS_KELAMIN = [('L', 'Laki-laki'), ('P', 'Perempuan')]
    GOLDAR = [('A', 'A'), ('B', 'B'), ('AB', 'AB'), ('O', 'O'), ('-', 'Tidak Diketahui')]

    no_rm          = models.CharField('No. Rekam Medis', max_length=20, unique=True)
    nik            = models.CharField('NIK', max_length=16, blank=True)
    nama_lengkap   = models.CharField('Nama Lengkap', max_length=200)
    tanggal_lahir  = models.DateField('Tanggal Lahir')
    jenis_kelamin  = models.CharField('Jenis Kelamin', max_length=1, choices=JENIS_KELAMIN)
    golongan_darah = models.CharField('Golongan Darah', max_length=3, choices=GOLDAR, default='-')
    alamat         = models.TextField('Alamat', blank=True)
    no_hp          = models.CharField('No. HP', max_length=20, blank=True)
    no_bpjs        = models.CharField('No. BPJS', max_length=20, blank=True)
    alergi_obat    = models.TextField('Alergi Obat', blank=True, help_text='Pisahkan dengan koma')
    alergi_lain    = models.TextField('Alergi Lain', blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pasien'
        verbose_name_plural = 'Data Pasien'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.no_rm}] {self.nama_lengkap}'

    @property
    def umur(self):
        from datetime import date
        today = date.today()
        b = self.tanggal_lahir
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

    @property
    def has_alergi(self):
        return bool(self.alergi_obat or self.alergi_lain)


# ── 2. Bed Management ────────────────────────────────────────────────────────

class Ruangan(models.Model):
    KELAS = [('VIP', 'VIP'), ('1', 'Kelas I'), ('2', 'Kelas II'), ('3', 'Kelas III'), ('ICU', 'ICU'), ('IGD', 'IGD'), ('OK', 'Kamar Operasi')]
    JENIS = [('RANAP', 'Rawat Inap'), ('IGD', 'IGD'), ('RAJAL', 'Rawat Jalan'), ('OK', 'Kamar Operasi'), ('ICU', 'ICU')]

    kode    = models.CharField('Kode Ruangan', max_length=20, unique=True)
    nama    = models.CharField('Nama Ruangan', max_length=100)
    kelas   = models.CharField('Kelas', max_length=5, choices=KELAS)
    jenis   = models.CharField('Jenis', max_length=10, choices=JENIS, default='RANAP')
    kapasitas = models.IntegerField('Kapasitas Bed', default=1)

    class Meta:
        verbose_name = 'Ruangan'
        verbose_name_plural = 'Ruangan'
        ordering = ['kelas', 'kode']

    def __str__(self):
        return f'[{self.kode}] {self.nama} ({self.get_kelas_display()})'


class Bed(models.Model):
    STATUS = [
        ('TERSEDIA', 'Tersedia'),
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
        ('RANAP',     'Rawat Inap'),
        ('PULANG',    'Pulang'),
        ('RUJUK',     'Dirujuk Keluar'),
        ('MENINGGAL', 'Meninggal'),
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

    kunjungan  = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='billing')
    kategori   = models.CharField('Kategori', max_length=15, choices=KATEGORI)
    nama_item  = models.CharField('Nama Item', max_length=200)
    kuantitas  = models.DecimalField('Kuantitas', max_digits=8, decimal_places=2, default=1)
    harga_satuan = models.DecimalField('Harga Satuan (Rp)', max_digits=12, decimal_places=2, default=0)
    kode_icd   = models.CharField('Kode ICD-10/9-CM', max_length=20, blank=True)
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

    class Meta:
        verbose_name = 'Discharge Record'
        verbose_name_plural = 'Discharge Records'

    def __str__(self):
        return f'Discharge [{self.kunjungan.pasien.nama_lengkap}] {self.tanggal_discharge.strftime("%d/%m/%Y")}'
