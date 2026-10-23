"""Level 2 workflows: recruitment, PSV, clinical privileging, orientation."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Lowongan(models.Model):
    STATUS_CHOICES = [
        ('DIBUKA', 'Dibuka'),
        ('DITUTUP', 'Ditutup'),
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
        'Status', max_length=10, choices=STATUS_CHOICES, default='DIBUKA'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_lowongan_created', verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lowongan'
        verbose_name_plural = 'Lowongan'
        ordering = ['-created_at']

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
