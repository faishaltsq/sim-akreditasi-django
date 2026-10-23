"""Level 2 workflows: recruitment, PSV, clinical privileging, orientation."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class VerifikasiSumber(models.Model):
    """Manual primary-source verification (PSV) tied to an exact document version."""

    OUTCOME_CHOICES = [
        ('VALID', 'Sah'),
        ('TIDAK_VALID', 'Tidak Sah'),
        ('PERLU_KONFIRMASI', 'Perlu Konfirmasi'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='psv_records',
        verbose_name='Pegawai',
    )
    version = models.ForeignKey(
        'sdm.VersiDokumen', on_delete=models.PROTECT, related_name='psv_records',
        verbose_name='Versi Dokumen',
    )
    issuer = models.CharField('Penerbit Sumber', max_length=200)
    reference = models.CharField('Nomor Referensi', max_length=200)
    method = models.CharField('Metode Verifikasi', max_length=120)
    outcome = models.CharField('Hasil', max_length=20, choices=OUTCOME_CHOICES)
    verified_at = models.DateTimeField('Waktu Verifikasi', default=timezone.now)
    verifier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sdm_psv_verified', verbose_name='Verifikator',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Verifikasi Sumber Utama'
        verbose_name_plural = 'Verifikasi Sumber Utama'
        ordering = ['-verified_at']
        indexes = [
            models.Index(fields=['employee', 'outcome'], name='sdm_psv_emp_outcome_idx'),
        ]

    def clean(self):
        if self.version_id and self.employee_id:
            if self.version.document.employee_id != self.employee_id:
                raise ValidationError(
                    {'version': 'Versi dokumen bukan milik pegawai ini.'}
                )

    def __str__(self):
        return f'PSV {self.reference} — {self.get_outcome_display()}'


class PengajuanKredensial(models.Model):
    STATUS_CHOICES = [
        ('DIAJUKAN', 'Diajukan'),
        ('DITINJAU', 'Ditinjau Komite'),
        ('DIREKOMENDASI', 'Direkomendasikan'),
        ('DISETUJUI', 'Disetujui'),
        ('DITOLAK', 'Ditolak'),
        ('DICABUT', 'Dicabut'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='credential_requests',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_credential_requests', verbose_name='Unit Kerja',
    )
    status = models.CharField(
        'Status', max_length=20, choices=STATUS_CHOICES, default='DIAJUKAN'
    )
    committee_notes = models.TextField('Catatan Komite', blank=True)
    recommendation = models.TextField('Rekomendasi', blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_credentials_submitted', verbose_name='Diajukan Oleh',
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_credentials_decided', verbose_name='Diputuskan Oleh',
    )
    decided_at = models.DateTimeField('Waktu Keputusan', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengajuan Kredensial'
        verbose_name_plural = 'Pengajuan Kredensial'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='sdm_kred_status_idx'),
        ]

    def __str__(self):
        return f'RKK {self.employee_id} — {self.get_status_display()}'


class RincianKewenangan(models.Model):
    pengajuan = models.ForeignKey(
        PengajuanKredensial, on_delete=models.CASCADE, related_name='privileges',
        verbose_name='Pengajuan Kredensial',
    )
    kewenangan = models.CharField('Kewenangan Klinis', max_length=200)
    catatan = models.TextField('Catatan', blank=True)

    class Meta:
        verbose_name = 'Rincian Kewenangan'
        verbose_name_plural = 'Rincian Kewenangan'
        ordering = ['pengajuan_id', 'pk']

    def __str__(self):
        return self.kewenangan


class KeputusanKredensial(models.Model):
    OUTCOME_CHOICES = [
        ('DISETUJUI', 'Disetujui'),
        ('DITOLAK', 'Ditolak'),
    ]
    pengajuan = models.OneToOneField(
        PengajuanKredensial, on_delete=models.PROTECT, related_name='decision',
        verbose_name='Pengajuan Kredensial',
    )
    outcome = models.CharField('Keputusan', max_length=20, choices=OUTCOME_CHOICES)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sdm_credential_decisions', verbose_name='Diputuskan Oleh',
    )
    decided_at = models.DateTimeField('Waktu Keputusan', default=timezone.now)
    notes = models.TextField('Catatan', blank=True)

    class Meta:
        verbose_name = 'Keputusan Kredensial'
        verbose_name_plural = 'Keputusan Kredensial'
        ordering = ['-decided_at']

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Keputusan kredensial bersifat immutable.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.pengajuan_id} — {self.get_outcome_display()}'


class PenugasanKlinis(models.Model):
    """Authorized SPK output; a document review alone never creates one."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='clinical_assignments',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_clinical_assignments', verbose_name='Unit Kerja',
    )
    decision = models.ForeignKey(
        KeputusanKredensial, on_delete=models.PROTECT,
        related_name='clinical_assignments', verbose_name='Keputusan Kredensial',
    )
    nomor_spk = models.CharField('Nomor SPK', max_length=80, unique=True)
    versi = models.PositiveIntegerField('Versi SPK', default=1)
    berlaku_mulai = models.DateField('Berlaku Mulai')
    berlaku_sampai = models.DateField('Berlaku Sampai', null=True, blank=True)
    is_active = models.BooleanField('Aktif', default=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sdm_spk_issued', verbose_name='Diterbitkan Oleh',
    )
    issued_at = models.DateTimeField('Waktu Terbit', default=timezone.now)

    class Meta:
        verbose_name = 'Penugasan Klinis'
        verbose_name_plural = 'Penugasan Klinis'
        ordering = ['-issued_at']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'versi'], name='sdm_spk_employee_version_uniq'
            ),
            models.CheckConstraint(
                condition=models.Q(berlaku_sampai__isnull=True)
                | models.Q(berlaku_sampai__gte=models.F('berlaku_mulai')),
                name='sdm_spk_period_valid',
            ),
        ]

    def __str__(self):
        return f'{self.nomor_spk} — {self.employee_id}'
