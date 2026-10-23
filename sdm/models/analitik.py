"""Level 5 analytics, compliance audit, talent and decision support."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SnapshotAnalitikSDM(models.Model):
    """Immutable analytics snapshot with explicit calculation provenance."""

    METRIC_CHOICES = [
        ('TURNOVER', 'Turnover'),
        ('STAFFING_BOR', 'Ketenagaan vs BOR'),
        ('PRODUCTIVITY', 'Produktivitas'),
        ('TREND', 'Tren Ketenagaan'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT, null=True, blank=True,
        related_name='sdm_snapshots', verbose_name='Unit Kerja',
    )
    metrik = models.CharField('Metrik', max_length=20, choices=METRIC_CHOICES)
    periode_mulai = models.DateField('Periode Mulai')
    periode_selesai = models.DateField('Periode Selesai')
    calculation_version = models.CharField('Versi Kalkulasi', max_length=40)
    filters = models.JSONField('Filter', default=dict, blank=True)
    source_coverage = models.JSONField('Cakupan Sumber', default=dict, blank=True)
    value = models.DecimalField(
        'Nilai', max_digits=14, decimal_places=4, null=True, blank=True
    )
    denominator = models.DecimalField(
        'Denominator', max_digits=14, decimal_places=4, null=True, blank=True
    )
    is_available = models.BooleanField('Tersedia', default=False)
    unavailable_reason = models.CharField('Alasan Tidak Tersedia', max_length=200, blank=True)
    generated_at = models.DateTimeField('Waktu Dibuat', default=timezone.now)

    class Meta:
        verbose_name = 'Snapshot Analitik SDM'
        verbose_name_plural = 'Snapshot Analitik SDM'
        ordering = ['-generated_at']
        indexes = [
            models.Index(
                fields=['metrik', 'unit_kerja', '-periode_selesai'],
                name='sdm_snapshot_metric_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(periode_selesai__gte=models.F('periode_mulai')),
                name='sdm_snapshot_period_valid',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Snapshot analitik bersifat immutable.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_metrik_display()} — {self.periode_selesai}'


class PenilaianTalent(models.Model):
    """Versioned performance-versus-competency assessment (9-box)."""

    AXIS_CHOICES = [
        ('RENDAH', 'Rendah'),
        ('SEDANG', 'Sedang'),
        ('TINGGI', 'Tinggi'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='talent_assessments',
        verbose_name='Pegawai',
    )
    versi = models.PositiveIntegerField('Versi', default=1)
    kinerja = models.CharField('Kinerja', max_length=10, choices=AXIS_CHOICES, blank=True)
    kompetensi = models.CharField(
        'Kompetensi', max_length=10, choices=AXIS_CHOICES, blank=True
    )
    threshold_version = models.CharField('Versi Ambang', max_length=40)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sdm_talent_reviews', verbose_name='Peninjau',
    )
    disputed = models.BooleanField('Dalam Sengketa', default=False)
    notes = models.TextField('Catatan', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Penilaian Talent'
        verbose_name_plural = 'Penilaian Talent'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'versi'], name='sdm_talent_employee_version_uniq'
            ),
        ]

    @property
    def box(self):
        if not self.kinerja or not self.kompetensi or self.disputed:
            return None
        return f'{self.kinerja}/{self.kompetensi}'

    def __str__(self):
        return f'{self.employee_id} v{self.versi} — {self.box or "belum terklasifikasi"}'


class RencanaSuksesi(models.Model):
    posisi = models.CharField('Posisi Kunci', max_length=200)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_succession_plans', verbose_name='Unit Kerja',
    )
    kandidat = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='succession_candidacies',
        verbose_name='Kandidat',
    )
    kesiapan = models.CharField('Kesiapan', max_length=60, blank=True)
    catatan = models.TextField('Catatan', blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_succession_reviews', verbose_name='Ditinjau Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rencana Suksesi'
        verbose_name_plural = 'Rencana Suksesi'
        ordering = ['posisi', '-created_at']

    def __str__(self):
        return f'{self.posisi} — {self.kandidat_id}'


class SkenarioSDM(models.Model):
    """Rule/scenario recommendation; human approval is mandatory and never automated."""

    JENIS_CHOICES = [
        ('ROTASI', 'Saran Rotasi'),
        ('ANGGARAN_DIKLAT', 'Perkiraan Anggaran Diklat'),
        ('KEKURANGAN_SPESIALIS', 'Ambang Kekurangan Spesialis'),
    ]
    STATUS_CHOICES = [
        ('DRAF', 'Draf'),
        ('DISETUJUI', 'Disetujui Manusia'),
        ('DITOLAK', 'Ditolak'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jenis = models.CharField('Jenis', max_length=20, choices=JENIS_CHOICES)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_scenarios', verbose_name='Unit Kerja',
    )
    asumsi = models.JSONField('Asumsi', default=dict, blank=True)
    provenance = models.JSONField('Provenance', default=dict, blank=True)
    keterbatasan = models.TextField('Keterbatasan Data', blank=True)
    rekomendasi = models.TextField('Rekomendasi')
    status = models.CharField(
        'Status', max_length=10, choices=STATUS_CHOICES, default='DRAF'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_scenarios_approved', verbose_name='Disetujui Oleh',
    )
    approved_at = models.DateTimeField('Waktu Persetujuan', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Skenario SDM'
        verbose_name_plural = 'Skenario SDM'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_jenis_display()} — {self.status}'
