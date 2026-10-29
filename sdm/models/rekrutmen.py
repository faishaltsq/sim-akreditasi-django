"""Level 2 workflows: recruitment, PSV, clinical privileging, orientation."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


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


class Lamaran(models.Model):
    STATUS_CHOICES = [
        ('MASUK', 'Lamaran Masuk'),
        ('SELEKSI_ADMIN', 'Seleksi Administrasi'),
        ('TES_KOMPETENSI', 'Tes Kompetensi'),
        ('WAWANCARA', 'Wawancara'),
        ('DITERIMA', 'Diterima'),
        ('DITOLAK', 'Ditolak'),
    ]
    ALLOWED_TRANSITIONS = {
        'MASUK': {'SELEKSI_ADMIN', 'DITOLAK'},
        'SELEKSI_ADMIN': {'TES_KOMPETENSI', 'DITOLAK'},
        'TES_KOMPETENSI': {'WAWANCARA', 'DITOLAK'},
        'WAWANCARA': {'DITERIMA', 'DITOLAK'},
        'DITERIMA': set(),
        'DITOLAK': set(),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lowongan = models.ForeignKey(
        Lowongan, on_delete=models.PROTECT, related_name='applications',
        verbose_name='Lowongan',
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
