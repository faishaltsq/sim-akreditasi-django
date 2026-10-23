"""Level 3 performance appraisal and training-needs analysis."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class ProgramDiklat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nama = models.CharField('Nama Program', max_length=200)
    kategori = models.CharField('Kategori', max_length=80, blank=True)
    jp = models.DecimalField(
        'Jam Pelajaran (JP)', max_digits=6, decimal_places=2, default=Decimal('0.00')
    )
    professional_credits = models.DecimalField(
        'SKP Profesi', max_digits=6, decimal_places=2, default=Decimal('0.00')
    )
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Program Diklat'
        verbose_name_plural = 'Program Diklat'
        ordering = ['nama']

    def __str__(self):
        return self.nama


class SesiDiklat(models.Model):
    program = models.ForeignKey(
        ProgramDiklat, on_delete=models.CASCADE, related_name='sessions',
        verbose_name='Program',
    )
    tanggal = models.DateField('Tanggal Sesi')
    lokasi = models.CharField('Lokasi', max_length=200, blank=True)
    kapasitas = models.PositiveIntegerField('Kapasitas', default=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sesi Diklat'
        verbose_name_plural = 'Sesi Diklat'
        ordering = ['-tanggal']

    def __str__(self):
        return f'{self.program} — {self.tanggal}'


class PesertaDiklat(models.Model):
    STATUS_CHOICES = [
        ('TERDAFTAR', 'Terdaftar'),
        ('HADIR', 'Hadir'),
        ('LULUS', 'Lulus'),
        ('TIDAK_LULUS', 'Tidak Lulus'),
        ('BATAL', 'Dibatalkan'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sesi = models.ForeignKey(
        SesiDiklat, on_delete=models.CASCADE, related_name='participants',
        verbose_name='Sesi',
    )
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='training_participations',
        verbose_name='Pegawai',
    )
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='TERDAFTAR'
    )
    qr_token = models.CharField('Token QR', max_length=80, blank=True)
    qr_expires_at = models.DateTimeField('Token Kedaluwarsa', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Peserta Diklat'
        verbose_name_plural = 'Peserta Diklat'
        ordering = ['sesi_id', 'employee__nama_lengkap']
        constraints = [
            models.UniqueConstraint(
                fields=['sesi', 'employee'], name='sdm_peserta_session_uniq'
            ),
        ]

    def __str__(self):
        return f'{self.employee_id} @ {self.sesi_id}'


class KehadiranDiklat(models.Model):
    peserta = models.OneToOneField(
        PesertaDiklat, on_delete=models.CASCADE, related_name='attendance',
        verbose_name='Peserta',
    )
    hadir = models.BooleanField('Hadir', default=False)
    menit_hadir = models.PositiveIntegerField('Menit Hadir', default=0)
    dicatat_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_attendance_recorded', verbose_name='Dicatat Oleh',
    )
    koreksi_alasan = models.TextField('Alasan Koreksi Manual', blank=True)
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kehadiran Diklat'
        verbose_name_plural = 'Kehadiran Diklat'

    def __str__(self):
        return f'{self.peserta_id}: {"hadir" if self.hadir else "tidak hadir"}'


class EvaluasiDiklat(models.Model):
    peserta = models.OneToOneField(
        PesertaDiklat, on_delete=models.CASCADE, related_name='evaluation',
        verbose_name='Peserta',
    )
    nilai = models.DecimalField(
        'Nilai', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    lulus = models.BooleanField('Lulus', default=False)
    catatan = models.TextField('Catatan', blank=True)
    evaluated_at = models.DateTimeField('Waktu Evaluasi', default=timezone.now)

    class Meta:
        verbose_name = 'Evaluasi Diklat'
        verbose_name_plural = 'Evaluasi Diklat'

    def __str__(self):
        return f'{self.peserta_id}: {"lulus" if self.lulus else "belum"}'


class SertifikatDiklat(models.Model):
    """Issued completion certificate; only for participants who passed evaluation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    peserta = models.OneToOneField(
        PesertaDiklat, on_delete=models.PROTECT, related_name='certificate',
        verbose_name='Peserta',
    )
    nomor = models.CharField('Nomor Sertifikat', max_length=80, unique=True)
    issued_at = models.DateTimeField('Waktu Terbit', default=timezone.now)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_certificates_issued', verbose_name='Diterbitkan Oleh',
    )

    class Meta:
        verbose_name = 'Sertifikat Diklat'
        verbose_name_plural = 'Sertifikat Diklat'
        ordering = ['-issued_at']

    def __str__(self):
        return self.nomor
