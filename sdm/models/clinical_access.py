"""Controlled clinical privileges and trainee model (Task A5/A6)."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TraineePlacement(models.Model):
    """Trainee (mahasiswa/residen/magang) placement with temporary, supervised
    action codes and countersignature requirement. Does not inflate independent
    qualified-staff counts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pegawai = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='trainee_placements',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        related_name='trainee_placements',
        verbose_name='Unit Kerja',
        null=True, blank=True,
    )
    institution = models.CharField('Institusi Pendidikan', max_length=200)
    program = models.CharField('Program/Kohort', max_length=200)
    supervisor = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='supervised_trainees',
        verbose_name='Pembimbing',
        limit_choices_to={'kategori': 'PPA'},
    )
    tanggal_mulai = models.DateField('Tanggal Mulai')
    tanggal_selesai = models.DateField('Tanggal Selesai')
    temporary_action_codes = models.JSONField(
        'Kode Aksi Sementara', default=list, blank=True,
        help_text='Daftar kode aksi klinis yang diizinkan hanya saat berpasangan dengan pembimbing.',
    )
    requires_countersignature = models.BooleanField(
        'Wajib Tanda Tangan Pembimbing', default=True
    )
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tempat Magang'
        verbose_name_plural = 'Tempat Magang'
        ordering = ['-tanggal_mulai', 'pk']
        constraints = [
            models.CheckConstraint(
                condition=Q(tanggal_selesai__gte=models.F('tanggal_mulai')),
                name='sdm_trainee_placement_tanggal_valid',
            ),
        ]

    def __str__(self):
        return f'{self.pegawai} — {self.program}'


class ClinicalActionCode(models.Model):
    """Controlled clinical action codes (e.g. prescribe, order, sign, admit)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField('Kode Aksi', max_length=40, unique=True)
    label = models.CharField('Label', max_length=100)
    requires_countersignature_for_trainee = models.BooleanField(
        'Wajib TTD Pembimbing untuk Magang', default=True
    )
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Kode Aksi Klinis'
        verbose_name_plural = 'Kode Aksi Klinis'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.label}'


class PrivilegeSnapshot(models.Model):
    """Immutable snapshot of privileges granted to an employee for a unit/action,
    used by effective_privileges and SPK issuance."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pegawai = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='privilege_snapshots',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        related_name='privilege_snapshots',
        verbose_name='Unit Kerja',
    )
    action_code = models.ForeignKey(
        ClinicalActionCode,
        on_delete=models.PROTECT,
        related_name='privilege_snapshots',
        verbose_name='Kode Aksi',
    )
    valid_from = models.DateField('Berlaku Mulai')
    valid_until = models.DateField('Berlaku Sampai', null=True, blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='privileges_granted',
        verbose_name='Diberikan Oleh',
    )
    source_decision = models.ForeignKey(
        'sdm.PenugasanKlinis',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='privilege_snapshots',
        verbose_name='Keputusan SPK Sumber',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Snapshot Kewenangan Klinis'
        verbose_name_plural = 'Snapshot Kewenangan Klinis'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['pegawai', 'unit_kerja', 'action_code', 'valid_from'],
                name='sdm_privilege_snapshot_pegawai_unit_action_from_uniq',
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F('valid_from')),
                name='sdm_privilege_snapshot_tanggal_valid',
            ),
        ]

    def __str__(self):
        return f'{self.pegawai} — {self.action_code.code} @ {self.unit_kerja_id}'
