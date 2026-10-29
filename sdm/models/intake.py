"""Staff intake and extended employment records (Task B2)."""

from decimal import Decimal
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class UrutanNomorPegawai(models.Model):
    """Configured numbering scope/period/format and next counter for NIP generation."""

    scope = models.CharField('Cakupan Nomor', max_length=60)
    period_start = models.DateField('Periode Mulai')
    period_end = models.DateField('Periode Akhir', null=True, blank=True)
    format_pattern = models.CharField('Pola Nomor', max_length=100)
    next_counter = models.PositiveIntegerField('Counter Selanjutnya', default=1)
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Urutan Nomor Pegawai'
        verbose_name_plural = 'Urutan Nomor Pegawai'
        ordering = ['scope', 'period_start']
        constraints = [
            models.UniqueConstraint(
                fields=['scope', 'period_start'],
                name='sdm_urutan_nomor_scope_period_uniq',
            ),
            models.CheckConstraint(
                condition=Q(period_end__isnull=True) | Q(period_end__gte=F('period_start')),
                name='sdm_urutan_nomor_period_valid',
            ),
        ]

    def __str__(self):
        return f'{self.scope} — {self.format_pattern}'


class ProfilPribadiPegawai(models.Model):
    """Restricted personal data, one per employee. Audit field changes without
    recording raw sensitive values."""

    GENDER_CHOICES = [
        ('LAKI_LAKI', 'Laki-laki'),
        ('PEREMPUAN', 'Perempuan'),
    ]
    MARITAL_CHOICES = [
        ('BELUM_KAWIN', 'Belum Kawin'),
        ('KAWIN', 'Kawin'),
        ('CERAI_HIDUP', 'Cerai Hidup'),
        ('CERAI_MATI', 'Cerai Mati'),
    ]
    RELIGION_CHOICES = [
        ('ISLAM', 'Islam'),
        ('KRISTEN_PROTESTAN', 'Kristen Protestant'),
        ('KRISTEN_KATOLIK', 'Katolik'),
        ('HINDU', 'Hindu'),
        ('BUDDHA', 'Buddha'),
        ('KONGHUCU', 'Konghucu'),
        ('LAINNYA', 'Lainnya'),
    ]

    employee = models.OneToOneField(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='profil_pribadi',
        verbose_name='Pegawai',
    )
    nik = models.CharField('NIK', max_length=16, blank=True, default='')
    nama_depan = models.CharField('Nama Depan', max_length=100, blank=True)
    nama_belakang = models.CharField('Nama Belakang', max_length=100, blank=True)
    gelar_depan = models.CharField('Gelar Depan', max_length=50, blank=True)
    gelar_belakang = models.CharField('Gelar Belakang', max_length=50, blank=True)
    tempat_lahir = models.CharField('Tempat Lahir', max_length=100, blank=True)
    tanggal_lahir = models.DateField('Tanggal Lahir', null=True, blank=True)
    gender = models.CharField('Jenis Kelamin', max_length=12, choices=GENDER_CHOICES, blank=True)
    agama = models.CharField('Agama', max_length=20, choices=RELIGION_CHOICES, blank=True)
    status_pernikahan = models.CharField(
        'Status Pernikahan', max_length=12, choices=MARITAL_CHOICES, blank=True
    )
    telepon = models.CharField('Nomor Telepon', max_length=30, blank=True)
    email_terverifikasi = models.EmailField('Email Terverifikasi', blank=True)
    alamat_ktp = models.TextField('Alamat KTP', blank=True)
    alamat_domisili = models.TextField('Alamat Domisili', blank=True)
    alamat_sama_dengan_ktp = models.BooleanField('Domisili Sama dengan KTP', default=True)
    golongan_darah = models.CharField(
        'Golongan Darah', max_length=3,
        choices=[('A', 'A'), ('B', 'B'), ('AB', 'AB'), ('O', 'O')], blank=True,
    )
    rt_rw = models.CharField('RT/RW', max_length=10, blank=True)
    kelurahan = models.CharField('Kelurahan/Desa', max_length=100, blank=True)
    kecamatan = models.CharField('Kecamatan', max_length=100, blank=True)
    kabupaten_kota = models.CharField('Kabupaten/Kota', max_length=100, blank=True)
    provinsi = models.CharField('Provinsi', max_length=100, blank=True)
    kode_pos = models.CharField('Kode Pos', max_length=10, blank=True)
    foto_profil_versi = models.ForeignKey(
        'sdm.VersiDokumen',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profil_foto_utama',
        verbose_name='Versi Foto Profil',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Pribadi Pegawai'
        verbose_name_plural = 'Profil Pribadi Pegawai'
        constraints = [
            models.UniqueConstraint(
                fields=['nik'],
                condition=~Q(nik=''),
                name='sdm_profil_pribadi_nik_nonblank_uniq',
            ),
        ]

    def __str__(self):
        return f'Profil {self.employee}'


class DataBpjsPegawai(models.Model):
    """Kepesertaan BPJS Kesehatan & Ketenagakerjaan; berkas mengikuti
    repositori DokumenPegawai, bukan kolom berkas mentah."""
    STATUS_KESEHATAN = [
        ('AKTIF', 'Aktif'), ('NONAKTIF', 'Non-Aktif'), ('TANGGUNGAN', 'Tanggungan'),
    ]
    KELAS_CHOICES = [
        ('KELAS_1', 'Kelas 1'), ('KELAS_2', 'Kelas 2'),
        ('KELAS_3', 'Kelas 3'), ('VIP', 'VIP'),
    ]
    STATUS_TK = [('AKTIF', 'Aktif'), ('NONAKTIF', 'Non-Aktif')]
    employee = models.OneToOneField(
        'sdm.Pegawai', on_delete=models.CASCADE,
        related_name='data_bpjs', verbose_name='Pegawai',
    )
    no_bpjs_kesehatan = models.CharField('No. BPJS Kesehatan', max_length=20, blank=True)
    status_bpjs_kesehatan = models.CharField(
        'Status BPJS Kesehatan', max_length=12, choices=STATUS_KESEHATAN, blank=True,
    )
    faskes_1 = models.CharField('Faskes Tingkat 1', max_length=150, blank=True)
    kelas_rawat = models.CharField('Kelas Rawat', max_length=10, choices=KELAS_CHOICES, blank=True)
    tanggungan_keluarga = models.PositiveIntegerField('Jumlah Tanggungan', default=0)
    no_bpjs_tk = models.CharField('No. BPJS Ketenagakerjaan (KPJ)', max_length=20, blank=True)
    status_bpjs_tk = models.CharField(
        'Status BPJS TK', max_length=12, choices=STATUS_TK, blank=True,
    )
    tmt_bpjs_tk = models.DateField('TMT Kepesertaan BPJS TK', null=True, blank=True)
    program_jkm = models.BooleanField('Program JKM', default=True)
    program_jkk = models.BooleanField('Program JKK', default=True)
    program_jht = models.BooleanField('Program JHT', default=True)
    program_jp = models.BooleanField('Program JP', default=False)
    kartu_kesehatan_versi = models.ForeignKey(
        'sdm.VersiDokumen', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bpjs_kesehatan_kartu', verbose_name='Kartu BPJS Kesehatan',
    )
    kartu_tk_versi = models.ForeignKey(
        'sdm.VersiDokumen', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bpjs_tk_kartu', verbose_name='Kartu BPJS TK',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Data BPJS Pegawai'
        verbose_name_plural = 'Data BPJS Pegawai'

    def __str__(self):
        return f'BPJS {self.employee}'


class RiwayatKepegawaian(models.Model):
    """Employment history with actual TMT and contract data, distinct from
    placement records (PenempatanPegawai)."""

    KATEGORI_CHOICES = [
        ('TETAP', 'Tetap'),
        ('PKWT', 'Perjanjian Waktu Tertentu'),
        ('MITRA', 'Dokter Mitra'),
        ('LEPAS', 'Tenaga Lepas'),
        ('MAGANG', 'Magang'),
        ('RESIDEN', 'Residen'),
    ]

    pegawai = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='riwayat_kepegawaian',
        verbose_name='Pegawai',
    )
    kategori_pegawai = models.CharField(
        'Kategori Pegawai', max_length=10, choices=KATEGORI_CHOICES
    )
    tanggal_tmt = models.DateField('TMT Kepegawaian', null=True, blank=True)
    tanggal_akhir = models.DateField('Tanggal Akhir', null=True, blank=True)
    nomor_kontrak = models.CharField('Nomor Kontrak', max_length=100, blank=True)
    tanggal_mulai_kontrak = models.DateField('Tanggal Mulai Kontrak', null=True, blank=True)
    tanggal_selesai_kontrak = models.DateField('Tanggal Selesai Kontrak', null=True, blank=True)
    jam_kontrak_per_minggu = models.DecimalField(
        'Jam Kerja Kontrak per Minggu',
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        null=True,
        blank=True,
    )
    jam_fulltime_referensi = models.DecimalField(
        'Jam Fulltime Referensi per Minggu',
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        null=True,
        blank=True,
    )
    jabatan_struktural = models.CharField('Jabatan Struktural', max_length=150, blank=True)
    review_status = models.CharField('Status Tinjauan', max_length=20, default='UNREVIEWED')
    provenance = models.TextField('Provenensi Data', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Riwayat Kepegawaian'
        verbose_name_plural = 'Riwayat Kepegawaian'
        ordering = ['-tanggal_tmt', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=Q(tanggal_akhir__isnull=True) | Q(tanggal_akhir__gte=F('tanggal_tmt')),
                name='sdm_riwayat_kepegawaian_tanggal_valid',
            ),
            models.CheckConstraint(
                condition=Q(tanggal_selesai_kontrak__isnull=True)
                | Q(tanggal_selesai_kontrak__gte=F('tanggal_mulai_kontrak')),
                name='sdm_riwayat_kepegawaian_kontrak_valid',
            ),
        ]

    def __str__(self):
        return f'Riwayat {self.pegawai} — {self.kategori_pegawai}'


class RiwayatPendidikanPegawai(models.Model):
    """Structured education history linked to exact approved document versions."""

    TINGKAT_CHOICES = [
        ('D3', 'D3'),
        ('S1', 'S1'),
        ('PROFESI', 'Profesi'),
        ('S2', 'S2'),
        ('SP1', 'Spesialis 1'),
        ('SP2', 'Spesialis 2'),
        ('OTHER', 'Lainnya'),
    ]

    pegawai = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='riwayat_pendidikan',
        verbose_name='Pegawai',
    )
    tingkat = models.CharField('Tingkat Pendidikan', max_length=10, choices=TINGKAT_CHOICES)
    institusi = models.CharField('Institusi', max_length=200)
    program_studi = models.CharField('Program Studi', max_length=200, blank=True)
    tanggal_lulus = models.DateField('Tanggal Lulus', null=True, blank=True)
    ijazah_versi = models.ForeignKey(
        'sdm.VersiDokumen',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pendidikan_ijazah',
        verbose_name='Versi Ijazah',
    )
    transkrip_versi = models.ForeignKey(
        'sdm.VersiDokumen',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pendidikan_transkrip',
        verbose_name='Versi Transkrip',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Riwayat Pendidikan Pegawai'
        verbose_name_plural = 'Riwayat Pendidikan Pegawai'
        ordering = ['-tanggal_lulus', '-pk']

    def __str__(self):
        return f'{self.tingkat} {self.institusi} — {self.pegawai}'


class IzinProfesiPegawai(models.Model):
    """Typed professional licenses (STR/SIP/SIPA/OTHER) with practice site and
    validity mode. Multiple SIPs allowed; local-RS flag identifies the
    applicable practice site."""

    SUBTYPE_CHOICES = [
        ('STR', 'STR'),
        ('SIP', 'SIP'),
        ('SIPA', 'SIPA'),
        ('OTHER', 'Lainnya'),
    ]
    VALIDITY_MODE_CHOICES = [
        ('DATED', 'Tanggal Berlaku'),
        ('LIFETIME', 'Seumur Hidup'),
    ]

    pegawai = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='izin_profesi',
        verbose_name='Pegawai',
    )
    subtype = models.CharField('Jenis Izin', max_length=10, choices=SUBTYPE_CHOICES)
    nomor_izin = models.CharField('Nomor Izin', max_length=100)
    pemberi_izin = models.CharField('Pemberi Izin', max_length=200)
    profesi = models.CharField('Profesi Izin', max_length=120)
    validity_mode = models.CharField(
        'Mode Masa Berlaku', max_length=10, choices=VALIDITY_MODE_CHOICES, default='DATED'
    )
    tanggal_terbit = models.DateField('Tanggal Terbit', null=True, blank=True)
    tanggal_berakhir = models.DateField('Berlaku Sampai', null=True, blank=True)
    organisasi_praktik = models.CharField('Organisasi Praktik', max_length=200, blank=True)
    lokasi_praktik = models.CharField('Lokasi Praktik', max_length=200, blank=True)
    is_local_rs = models.BooleanField('Praktik di RS Ini', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Izin Profesi Pegawai'
        verbose_name_plural = 'Izin Profesi Pegawai'
        ordering = ['subtype', 'nomor_izin']
        constraints = [
            models.CheckConstraint(
                condition=Q(tanggal_berakhir__isnull=True)
                | Q(tanggal_berakhir__gte=F('tanggal_terbit')),
                name='sdm_izin_profesi_tanggal_valid',
            ),
        ]

    def __str__(self):
        return f'{self.subtype} {self.nomor_izin} — {self.pegawai}'


class DrafInputPegawai(models.Model):
    """Persisted draft for the resumable five-step intake."""

    STATE_CHOICES = [
        ('DRAFT', 'Draf'),
        ('SUBMITTED', 'Diajukan'),
        ('FINALIZED', 'Diselesaikan'),
        ('EXPIRED', 'Kadaluarsa'),
        ('REVOKED', 'Dicabut'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='hc_intake_drafts',
        verbose_name='Pemilik Draf',
    )
    edited_employee = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='intake_drafts',
        verbose_name='Pegawai yang Diedit',
    )
    finalized_employee = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finalized_intake_drafts',
        verbose_name='Pegawai Hasil',
    )
    finalization_key = models.CharField(
        'Kunci Finalisasi', max_length=100, null=True, blank=True, unique=True
    )
    current_step = models.PositiveSmallIntegerField('Langkah Saat Ini', default=1)
    draft_data = models.JSONField('Data Draf', default=dict, blank=True)
    version = models.PositiveIntegerField('Versi Konkursi', default=1)
    expires_at = models.DateTimeField('Kadaluarsa Pada')
    state = models.CharField('Status', max_length=12, choices=STATE_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Draf Input Pegawai'
        verbose_name_plural = 'Draf Input Pegawai'
        ordering = ['-updated_at']

    def __str__(self):
        return f'Draf {self.id} — {self.get_state_display()}'


class BatchImporPegawai(models.Model):
    """Versioned Excel import batch with preview, idempotency and explicit apply."""

    STATE_CHOICES = [
        ('DRAFT', 'Draf'),
        ('PREVIEWED', 'Ditinjau'),
        ('APPLIED', 'Terimpor'),
        ('BLOCKED', 'Diblokir'),
        ('REVOKED', 'Dicabut'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='hc_import_batches',
        verbose_name='Pengunggah Impor',
    )
    template_version = models.CharField('Versi Template', max_length=30)
    file_hash = models.CharField('SHA-256 Berkas', max_length=64)
    idempotency_key = models.CharField('Kunci Idempotensi', max_length=100, unique=True)
    scope = models.CharField('Cakupan', max_length=60, default='all')
    preview_hash = models.CharField('Hash Pratinjau', max_length=64, blank=True)
    state = models.CharField('Status', max_length=12, choices=STATE_CHOICES, default='DRAFT')
    row_create = models.PositiveIntegerField('Baris Dibuat', default=0)
    row_update = models.PositiveIntegerField('Baris Diperbarui', default=0)
    row_blocked = models.PositiveIntegerField('Baris Diblokir', default=0)
    decisions = models.JSONField('Keputusan Impor', default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Batch Impor Pegawai'
        verbose_name_plural = 'Batch Impor Pegawai'
        ordering = ['-created_at']

    def __str__(self):
        return f'Impor {self.id} — {self.get_state_display()}'


class LampiranDrafPegawai(models.Model):
    """Private object staged against an intake draft before finalization."""

    ARTIFACT_CHOICES = [
        ('FOTO_PROFIL', 'Pas Foto Resmi'),
        ('KTP', 'KTP'),
        ('IJAZAH', 'Ijazah'),
        ('TRANSKRIP', 'Transkrip Nilai'),
        ('STR', 'STR'),
        ('SIP', 'SIP'),
        ('SIPA', 'SIPA'),
        ('KONTRAK', 'Kontrak Kerja'),
        ('SK_PENGANGKATAN', 'SK Pengangkatan'),
        ('SPK_RKK', 'SPK RKK'),
        ('URAIAN_TUGAS', 'Uraian Tugas'),
        ('SERTIFIKAT', 'Sertifikat'),
        ('OTHER', 'Lainnya'),
    ]
    STATE_CHOICES = [
        ('STAGED', 'Menunggu Finalisasi'),
        ('BOUND', 'Terhubung ke Dokumen'),
        ('DELETED', 'Dihapus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(
        'sdm.DrafInputPegawai',
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Draf',
    )
    artifact_kind = models.CharField(
        'Jenis Berkas', max_length=20, choices=ARTIFACT_CHOICES
    )
    storage_key = models.CharField('Kunci Penyimpanan Privat', max_length=255, unique=True)
    sha256 = models.CharField('SHA-256', max_length=64)
    size_bytes = models.PositiveBigIntegerField('Ukuran (byte)')
    content_type = models.CharField('MIME Type', max_length=100)
    original_filename = models.CharField('Nama Berkas Asli', max_length=255)
    state = models.CharField('Status', max_length=10, choices=STATE_CHOICES, default='STAGED')
    bound_version = models.ForeignKey(
        'sdm.VersiDokumen',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_attachments',
        verbose_name='Versi Dokumen Terhubung',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lampiran Draf Pegawai'
        verbose_name_plural = 'Lampiran Draf Pegawai'
        ordering = ['-created_at', '-pk']
        indexes = [
            models.Index(fields=['draft', 'state'], name='sdm_lampiran_draft_state_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['draft', 'artifact_kind'],
                condition=Q(
                    state='STAGED',
                    artifact_kind__in=('FOTO_PROFIL', 'KTP'),
                ),
                name='sdm_lampiran_singleton_staged_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.get_artifact_kind_display()} — {self.original_filename}'
