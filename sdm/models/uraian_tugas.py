"""Versioned job descriptions and staff acknowledgment (Task A6)."""

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class MasterUraianTugas(models.Model):
    """Versioned job description with position/unit/profession applicability and
    an approval/effective interval. Each revision requires renewed acknowledgment."""

    STATUS_CHOICES = [
        ('DRAFT', 'Draf'),
        ('APPROVED', 'Disetujui'),
        ('RETIRED', 'Dicabut'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    position_code = models.CharField('Kode Posisi', max_length=40)
    position_title = models.CharField('Judul Posisi', max_length=150)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        related_name='uraian_tugas_versions',
        verbose_name='Unit Kerja',
    )
    profession_applicability = models.CharField(
        'Kedudukan Profesi', max_length=120, blank=True,
        help_text='Kosong berarti berlaku untuk semua profesi.',
    )
    content = models.TextField('Isi Uraian Tugas')
    version = models.PositiveIntegerField('Versi', default=1, validators=[MinValueValidator(1)])
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='DRAFT'
    )
    valid_from = models.DateField('Berlaku Mulai')
    valid_until = models.DateField('Berlaku Sampai', null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uraian_tugas_approved',
        verbose_name='Disetujui Oleh',
    )
    approved_at = models.DateTimeField('Waktu Disetujui', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uraian_tugas_created',
        verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Master Uraian Tugas'
        verbose_name_plural = 'Master Uraian Tugas'
        ordering = ['position_code', '-version']
        constraints = [
            models.UniqueConstraint(
                fields=['position_code', 'version'],
                name='sdm_uraian_tugas_position_version_uniq',
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F('valid_from')),
                name='sdm_uraian_tugas_tanggal_valid',
            ),
        ]

    def __str__(self):
        return f'{self.position_code} v{self.version}'


class PenerimaanUraianTugas(models.Model):
    """Employee acknowledgment of an exact job description revision."""

    STATUS_CHOICES = [
        ('DRAFT', 'Draf'),
        ('ACKNOWLEDGED', 'Diterima'),
        ('REVOKED', 'Dicabut'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='uraian_tugas_acknowledgments',
        verbose_name='Pegawai',
    )
    uraian_tugas = models.ForeignKey(
        MasterUraianTugas,
        on_delete=models.PROTECT,
        related_name='acknowledgments',
        verbose_name='Uraian Tugas',
    )
    version_acknowledged = models.PositiveIntegerField('Versi yang Diterima')
    acknowledged_at = models.DateTimeField('Waktu Terima', default=timezone.now)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uraian_tugas_acknowledged',
        verbose_name='Diterima Oleh',
    )
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='ACKNOWLEDGED'
    )
    notes = models.TextField('Catatan', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Penerimaan Uraian Tugas'
        verbose_name_plural = 'Penerimaan Uraian Tugas'
        ordering = ['-acknowledged_at', '-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'uraian_tugas', 'version_acknowledged'],
                name='sdm_uraian_ack_employee_version_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.employee} — {self.uraian_tugas} v{self.version_acknowledged}'
