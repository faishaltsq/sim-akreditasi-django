"""Clinical evaluation (OPPE/FPPE) models (Task A7)."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class EvaluasiPraktikKlinis(models.Model):
    """OPPE (periodic) or FPPE (triggered) clinical practice evaluation case."""

    TIPE_CHOICES = [
        ('OPPE', 'Ongoing Professional Practice Evaluation'),
        ('FPPE', 'Focused Professional Practice Evaluation'),
    ]
    STATUS_CHOICES = [
        ('OPEN', 'Terbuka'),
        ('IN_REVIEW', 'Ditinjau'),
        ('FINALIZED', 'Diselesaikan'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipe = models.CharField('Tipe Evaluasi', max_length=10, choices=TIPE_CHOICES)
    employee = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='evaluasi_praktik_klinis',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        related_name='evaluasi_praktik_klinis',
        verbose_name='Unit Kerja',
    )
    privilege_snapshot = models.ForeignKey(
        'sdm.PrivilegeSnapshot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluasi_cases',
        verbose_name='Snapshot Kewenangan',
    )
    period_or_trigger = models.CharField(
        'Referensi Periode/Pemicu', max_length=200
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluasi_reviewed',
        verbose_name='Penilai',
    )
    restricted_indicators = models.TextField(
        'Indikator Terbatas', blank=True,
        help_text='Catatan indikator tanpa detail klinis pasien.',
    )
    recommendation = models.TextField('Rekomendasi', blank=True)
    follow_up = models.TextField('Tindak Lanjut', blank=True)
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='OPEN'
    )
    finalized_at = models.DateTimeField('Waktu Diselesaikan', null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluasi_finalized',
        verbose_name='Diselesaikan Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Evaluasi Praktik Klinis'
        verbose_name_plural = 'Evaluasi Praktik Klinis'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_tipe_display()} — {self.employee} — {self.period_or_trigger}'


class KasusFPPE(models.Model):
    """FPPE case linked to a trigger reference (incident/privilege/new privilege)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evaluasi = models.ForeignKey(
        EvaluasiPraktikKlinis,
        on_delete=models.PROTECT,
        related_name='fppe_cases',
        verbose_name='Evaluasi Klinis',
    )
    trigger_reference = models.CharField('Referensi Pemicu', max_length=200)
    review_deadline = models.DateTimeField('Tenggat Tinjauan')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Kasus FPPE'
        verbose_name_plural = 'Kasus FPPE'
        ordering = ['review_deadline']

    def __str__(self):
        return f'FPPE {self.trigger_reference}'
