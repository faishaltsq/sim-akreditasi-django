"""Level 2 workflows: recruitment, PSV, clinical privileging, orientation."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ProgramOrientasi(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nama = models.CharField('Nama Program', max_length=200)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT, null=True, blank=True,
        related_name='sdm_orientation_programs',
        verbose_name='Unit Kerja',
        help_text='Kosong berarti orientasi umum rumah sakit.',
    )
    berlaku_hari = models.PositiveIntegerField('Batas Hari', default=30)
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Program Orientasi'
        verbose_name_plural = 'Program Orientasi'
        ordering = ['nama']

    def __str__(self):
        return self.nama


class AktivitasOrientasi(models.Model):
    program = models.ForeignKey(
        ProgramOrientasi, on_delete=models.CASCADE, related_name='activities',
        verbose_name='Program',
    )
    nama = models.CharField('Nama Aktivitas', max_length=200)
    wajib = models.BooleanField('Wajib', default=True)
    urutan = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Aktivitas Orientasi'
        verbose_name_plural = 'Aktivitas Orientasi'
        ordering = ['program_id', 'urutan', 'pk']

    def __str__(self):
        return self.nama


class PenugasanOrientasi(models.Model):
    STATUS_CHOICES = [
        ('BERJALAN', 'Berjalan'),
        ('SELESAI', 'Selesai'),
        ('DIBATALKAN', 'Dibatalkan'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='orientations',
        verbose_name='Pegawai',
    )
    program = models.ForeignKey(
        ProgramOrientasi, on_delete=models.PROTECT, related_name='assignments',
        verbose_name='Program',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT, null=True, blank=True,
        related_name='sdm_orientation_assignments', verbose_name='Unit Kerja',
    )
    tanggal_mulai = models.DateField('Tanggal Mulai', default=timezone.localdate)
    tenggat = models.DateField('Tenggat')
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='BERJALAN'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Penugasan Orientasi'
        verbose_name_plural = 'Penugasan Orientasi'
        ordering = ['-tanggal_mulai']

    @property
    def progress_pct(self):
        activities = self.completions.all()
        required = self.program.activities.filter(wajib=True).count()
        if not required:
            return None
        done = activities.filter(selesai=True, activity__wajib=True).count()
        return round(done / required * 100, 1)

    def __str__(self):
        return f'{self.employee_id} — {self.program}'


class PenyelesaianOrientasi(models.Model):
    assignment = models.ForeignKey(
        PenugasanOrientasi, on_delete=models.CASCADE, related_name='completions',
        verbose_name='Penugasan',
    )
    activity = models.ForeignKey(
        AktivitasOrientasi, on_delete=models.PROTECT,
        related_name='completions', verbose_name='Aktivitas',
    )
    selesai = models.BooleanField('Selesai', default=False)
    selesai_at = models.DateTimeField('Waktu Selesai', null=True, blank=True)
    signer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_orientation_signoffs', verbose_name='Penanda Tangan',
    )
    notes = models.TextField('Catatan', blank=True)

    class Meta:
        verbose_name = 'Penyelesaian Orientasi'
        verbose_name_plural = 'Penyelesaian Orientasi'
        ordering = ['assignment_id', 'activity__urutan']
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'activity'],
                name='sdm_orientation_completion_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.assignment_id}: {self.activity_id}'
