"""Level 2 workflows: recruitment, PSV, clinical privileging, orientation."""
import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def generate_recruitment_token():
    """Token capability portal rekrutmen (43 char, 256 bit entropi)."""
    return secrets.token_urlsafe(32)


class Lowongan(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draf'),
        ('DIBUKA', 'Dibuka'),
        ('DITUTUP', 'Ditutup'),
        ('DIBATALKAN', 'Dibatalkan'),
    ]
    JALUR_CHOICES = [
        ('INTERNAL', 'Internal (promosi / mutasi)'),
        ('EKSTERNAL', 'Eksternal (portal karir)'),
        ('KEDUANYA', 'Internal & Eksternal'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_lowongan', verbose_name='Unit Kerja',
    )
    profesi = models.CharField('Profesi', max_length=120)
    judul = models.CharField('Judul Lowongan', max_length=200)
    jumlah_kebutuhan = models.PositiveIntegerField('Jumlah Kebutuhan', default=1)
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='DRAFT'
    )
    jalur = models.CharField(
        'Jalur Rekrutmen', max_length=10, choices=JALUR_CHOICES, default='EKSTERNAL',
        help_text='Internal untuk promosi/mutasi, eksternal untuk portal karir.',
    )
    # ── Kriteria penyaringan (dipakai Fase C3 auto-filter) ──
    kualifikasi_pendidikan = models.CharField(
        'Kualifikasi Pendidikan', max_length=200, blank=True,
        help_text='Ijazah minimum yang dipersyaratkan, mis. D3 Keperawatan.',
    )
    ipk_minimal = models.DecimalField(
        'IPK Minimal', max_digits=3, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('4.00'))],
    )
    batas_usia = models.PositiveSmallIntegerField(
        'Batas Usia (tahun)', null=True, blank=True,
    )
    pengalaman_minimal_bulan = models.PositiveSmallIntegerField(
        'Pengalaman Minimal (bulan)', null=True, blank=True,
    )
    # ── Jendela pendaftaran ──
    tanggal_buka = models.DateField('Tanggal Buka', null=True, blank=True)
    tanggal_tutup = models.DateField('Tanggal Tutup', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_lowongan_created', verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lowongan'
        verbose_name_plural = 'Lowongan'
        ordering = ['-created_at']

    def clean(self):
        """Reject a registration window that closes before it opens.

        The window drives the public portal's visibility, so an inverted range
        would either hide a live vacancy forever or expose a closed one.
        """
        super().clean()
        if (
            self.tanggal_buka and self.tanggal_tutup
            and self.tanggal_tutup < self.tanggal_buka
        ):
            raise ValidationError({
                'tanggal_tutup': 'Tanggal tutup tidak boleh sebelum tanggal buka.',
            })

    @property
    def is_pendaftaran_terbuka(self):
        """True only while the vacancy is open and today falls in the window."""
        if self.status != 'DIBUKA':
            return False
        today = timezone.localdate()
        if self.tanggal_buka and today < self.tanggal_buka:
            return False
        if self.tanggal_tutup and today > self.tanggal_tutup:
            return False
        return True

    def __str__(self):
        return f'{self.judul} — {self.profesi}'


class Pelamar(models.Model):
    """A candidate who applied without an account, reached by access token.

    The public portal never exposes a login wall and never enumerates ids:
    every candidate row carries a ``token`` that acts as the capability to read
    and amend that one application. Losing the token means SDM must re-issue
    one, which is why it is stored rather than hashed.
    """

    PENDIDIKAN_CHOICES = [
        ('SMA_SMK', 'SMA / SMK'),
        ('D3', 'Diploma III (D3)'),
        ('S1', 'Sarjana (S1)'),
        ('S2', 'Magister (S2)'),
        ('S3', 'Doktor (S3)'),
    ]
    URUTAN_PENDIDIKAN = {
        'SMA_SMK': 1, 'D3': 2, 'S1': 3, 'S2': 4, 'S3': 5,
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(
        'Token Akses', max_length=64, unique=True,
        default=generate_recruitment_token,
        help_text='Capability URL untuk pelamar mengakses lamaran sendiri.',
    )
    nama_lengkap = models.CharField('Nama Lengkap', max_length=200)
    email = models.EmailField('Email', blank=True)
    telepon = models.CharField('Telepon', max_length=40, blank=True)
    # ── Data penyaringan (diisi pelamar saat mendaftar) ──
    pendidikan_terakhir = models.CharField(
        'Pendidikan Terakhir', max_length=10, choices=PENDIDIKAN_CHOICES,
        blank=True, default='',
    )
    ipk = models.DecimalField(
        'IPK', max_digits=3, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('4.00'))],
    )
    tanggal_lahir = models.DateField('Tanggal Lahir', null=True, blank=True)
    pengalaman_bulan = models.PositiveSmallIntegerField(
        'Pengalaman Kerja (bulan)', null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pelamar'
        verbose_name_plural = 'Pelamar'
        ordering = ['-created_at']

    def __str__(self):
        return self.nama_lengkap


class Lamaran(models.Model):
    STATUS_CHOICES = [
        ('MASUK', 'Lamaran Masuk'),
        ('SELEKSI_ADMIN', 'Seleksi Administrasi'),
        ('TES_KOMPETENSI', 'Tes Kompetensi'),
        ('WAWANCARA', 'Wawancara'),
        ('MCU', 'Pemeriksaan Kesehatan (MCU)'),
        ('OFFERING', 'Penawaran Kerja'),
        ('DITERIMA', 'Diterima'),
        ('DITOLAK', 'Ditolak'),
    ]
    # Alur dokumen: MASUK → SELEKSI_ADMIN → TES_KOMPETENSI → WAWANCARA → MCU
    # → OFFERING → DITERIMA. Setiap tahap boleh langsung DITOLAK; tidak ada
    # lompatan ke depan supaya bukti audit per tahap (KPS) tetap lengkap.
    ALLOWED_TRANSITIONS = {
        'MASUK': {'SELEKSI_ADMIN', 'DITOLAK'},
        'SELEKSI_ADMIN': {'TES_KOMPETENSI', 'DITOLAK'},
        'TES_KOMPETENSI': {'WAWANCARA', 'DITOLAK'},
        'WAWANCARA': {'MCU', 'DITOLAK'},
        'MCU': {'OFFERING', 'DITOLAK'},
        'OFFERING': {'DITERIMA', 'DITOLAK'},
        'DITERIMA': set(),
        'DITOLAK': set(),
    }
    # Tahapan yang menuntut penilaian tercatat sebelum boleh dilanjutkan.
    TAHAP_BER_NILAI = {'SELEKSI_ADMIN', 'TES_KOMPETENSI', 'WAWANCARA', 'MCU'}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lowongan = models.ForeignKey(
        Lowongan, on_delete=models.PROTECT, related_name='applications',
        verbose_name='Lowongan',
    )
    pelamar = models.ForeignKey(
        Pelamar, on_delete=models.PROTECT, related_name='lamaran',
        null=True, blank=True, verbose_name='Pelamar (Portal Publik)',
        help_text='Terisi bila lamaran masuk lewat portal publik; kosong untuk '
                  'lamaran yang dicatat langsung oleh SDM.',
    )
    nama_pelamar = models.CharField('Nama Pelamar', max_length=200)
    kontak = models.CharField('Kontak', max_length=200, blank=True)
    status = models.CharField(
        'Status', max_length=20, choices=STATUS_CHOICES, default='MASUK'
    )
    idempotency_key = models.CharField(
        'Kunci Idempotensi', max_length=80, unique=True, null=True, blank=True
    )
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applications', verbose_name='Pegawai Hasil Rekrutmen',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lamaran'
        verbose_name_plural = 'Lamaran'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.nama_pelamar} — {self.get_status_display()}'


class RiwayatSeleksi(models.Model):
    lamaran = models.ForeignKey(
        Lamaran, on_delete=models.CASCADE, related_name='history',
        verbose_name='Lamaran',
    )
    status_sebelum = models.CharField('Status Sebelumnya', max_length=20, blank=True)
    status_sesudah = models.CharField('Status Sesudahnya', max_length=20)
    catatan = models.TextField('Catatan', blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_selection_history', verbose_name='Pelaku',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Riwayat Seleksi'
        verbose_name_plural = 'Riwayat Seleksi'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.lamaran_id}: {self.status_sebelum} → {self.status_sesudah}'


class PenilaianTahap(models.Model):
    """Append-only verdict for one selection stage of one application.

    Every stage that gates progress (administrasi, CBT, wawancara, MCU) writes
    a row here rather than overwriting a single status field, so the audit trail
    the accreditation standard asks for survives re-scoring and appeals.
    """

    TAHAP_CHOICES = [
        ('SELEKSI_ADMIN', 'Seleksi Administrasi'),
        ('TES_KOMPETENSI', 'Tes Kompetensi'),
        ('WAWANCARA', 'Wawancara'),
        ('MCU', 'Pemeriksaan Kesehatan (MCU)'),
    ]
    HASIL_CHOICES = [
        ('LULUS', 'Lulus'),
        ('TIDAK_LULUS', 'Tidak Lulus'),
        ('DIPERTIMBANGKAN', 'Dipertimbangkan'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lamaran = models.ForeignKey(
        Lamaran, on_delete=models.CASCADE, related_name='penilaian',
        verbose_name='Lamaran',
    )
    tahap = models.CharField('Tahap', max_length=20, choices=TAHAP_CHOICES)
    hasil = models.CharField('Hasil', max_length=20, choices=HASIL_CHOICES)
    skor = models.DecimalField(
        'Skor', max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Skor mentah tahap ini; bobot gabungan dihitung di service.',
    )
    catatan = models.TextField('Catatan Penguji', blank=True)
    penguji = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_stage_assessments', verbose_name='Penguji',
    )
    dinilai_at = models.DateTimeField('Waktu Penilaian', default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Penilaian Tahap'
        verbose_name_plural = 'Penilaian Tahap'
        ordering = ['-dinilai_at', '-created_at']
        indexes = [
            models.Index(fields=['lamaran', 'tahap'], name='sdm_penilaian_tahap_idx'),
        ]

    def __str__(self):
        return f'{self.lamaran_id} — {self.get_tahap_display()}: {self.get_hasil_display()}'


class BerkasPelamar(models.Model):
    """One uploaded supporting document for an application.

    Verification state is per document, not per application: the screening
    matrix needs to say "ijazah valid, STR perlu klarifikasi" rather than a
    single pass/fail for the whole submission.
    """

    STATUS_CHOICES = [
        ('MENUNGGU', 'Menunggu Verifikasi'),
        ('VALID', 'Valid'),
        ('PERLU_KLARIFIKASI', 'Perlu Klarifikasi'),
        ('TIDAK_LENGKAP', 'Tidak Lengkap'),
    ]
    JENIS_CHOICES = [
        ('KTP', 'KTP'),
        ('IJAZAH', 'Ijazah'),
        ('TRANSKRIP', 'Transkrip Nilai'),
        ('STR', 'STR (Surat Tanda Registrasi)'),
        ('SIP', 'SIP (Surat Izin Praktik)'),
        ('SERTIFIKAT', 'Sertifikat Pelatihan / BTCLS / PPI / K3RS'),
        ('CV', 'Curriculum Vitae'),
        ('LAINNYA', 'Lainnya'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lamaran = models.ForeignKey(
        Lamaran, on_delete=models.CASCADE, related_name='berkas',
        verbose_name='Lamaran',
    )
    jenis = models.CharField(
        'Jenis Dokumen', max_length=60, choices=JENIS_CHOICES,
        help_text='Jenis berkas pendukung yang diunggah pelamar.',
    )
    berkas = models.FileField(
        'Berkas', upload_to='rekrutmen/berkas/', null=True, blank=True,
    )
    status = models.CharField(
        'Status Verifikasi', max_length=20, choices=STATUS_CHOICES,
        default='MENUNGGU',
    )
    catatan = models.TextField('Catatan Verifikator', blank=True)
    diverifikasi_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_berkas_verified', verbose_name='Diverifikasi Oleh',
    )
    diverifikasi_at = models.DateTimeField(
        'Waktu Verifikasi', null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Berkas Pelamar'
        verbose_name_plural = 'Berkas Pelamar'
        ordering = ['lamaran', 'jenis']
        constraints = [
            models.UniqueConstraint(
                fields=['lamaran', 'jenis'],
                name='sdm_berkas_pelamar_jenis_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.lamaran_id} — {self.jenis}: {self.get_status_display()}'

class HasilMCU(models.Model):
    """Pre-employment medical check-up result (STARKES KPS 3).

    The outcome drives the MCU stage: only FIT and FIT_WITH_NOTE may proceed to
    the offering stage. UNFIT is a terminal administrative state, so the row is
    kept rather than deleted — it is part of the audit trail.
    """

    STATUS_CHOICES = [
        ('FIT', 'Fit'),
        ('FIT_NOTE', 'Fit with Note'),
        ('UNFIT', 'Unfit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lamaran = models.OneToOneField(
        Lamaran, on_delete=models.CASCADE, related_name='hasil_mcu',
        verbose_name='Lamaran',
    )
    status = models.CharField(
        'Status MCU', max_length=10, choices=STATUS_CHOICES,
    )
    tanggal_periksa = models.DateField('Tanggal Pemeriksaan', null=True, blank=True)
    penyelenggara = models.CharField(
        'Laboratorium / K3RS', max_length=200, blank=True,
    )
    catatan = models.TextField('Catatan Medis', blank=True)
    berkas = models.FileField(
        'Berkas Hasil', upload_to='rekrutmen/mcu/', null=True, blank=True,
    )
    diperiksa_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_mcu_recorded', verbose_name='Dicatat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hasil MCU'
        verbose_name_plural = 'Hasil MCU'
        ordering = ['-created_at']

    def __str__(self):
        return f'MCU {self.lamaran_id} — {self.get_status_display()}'

    @property
    def boleh_lanjut(self):
        """Only FIT and FIT WITH NOTE may continue to the offering stage."""
        return self.status in ('FIT', 'FIT_NOTE')


class KonfirmasiOffering(models.Model):
    """Candidate's acceptance of the digital offering letter.

    The token is the capability: the candidate never logs in, and the record
    proves who accepted, when, and from where.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lamaran = models.OneToOneField(
        Lamaran, on_delete=models.CASCADE, related_name='konfirmasi_offering',
        verbose_name='Lamaran',
    )
    token = models.CharField(
        'Token Konfirmasi', max_length=64, unique=True,
        default=generate_recruitment_token,
    )
    nomor_surat = models.CharField(
        'Nomor Surat', max_length=100, blank=True,
        help_text='Dibuat dari pola yang dikelola admin; bukan dikarang sistem.',
    )
    berkas = models.FileField(
        'Surat Penawaran', upload_to='rekrutmen/offering/', null=True, blank=True,
    )
    disetujui = models.BooleanField('Disetujui', null=True, blank=True)
    disetujui_at = models.DateTimeField('Waktu Persetujuan', null=True, blank=True)
    ip_pemersetujui = models.GenericIPAddressField(
        'IP Penyetuju', null=True, blank=True,
    )
    catatan_kandidat = models.TextField('Catatan Kandidat', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_offering_created', verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Konfirmasi Offering'
        verbose_name_plural = 'Konfirmasi Offering'
        ordering = ['-created_at']

    def __str__(self):
        return f'Offering {self.lamaran_id} — {self.nomor_surat or "(tanpa nomor)"}'
