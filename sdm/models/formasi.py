"""Activity-based FTE planning with immutable approved result versions (HC-01)."""
import uuid
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


CALCULATION_VERSION = 'activity-fte-v1'
FTE_QUANTUM = Decimal('0.01')


class RencanaFormasi(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draf'),
        ('REVIEW', 'Menunggu Tinjauan'),
        ('APPROVED', 'Disetujui'),
        ('SUPERSEDED', 'Digantikan'),
    ]
    METHOD_CHOICES = [
        ('ACTIVITY_FTE', 'Activity-based FTE'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_rencana_formasi', verbose_name='Unit Kerja',
    )
    profesi = models.CharField('Profesi', max_length=120)
    periode_mulai = models.DateField('Periode Mulai')
    periode_selesai = models.DateField('Periode Selesai')
    metode = models.CharField(
        'Metode', max_length=20, choices=METHOD_CHOICES, default='ACTIVITY_FTE'
    )
    calculation_version = models.CharField(
        'Versi Kalkulasi', max_length=40, default=CALCULATION_VERSION
    )
    effective_minutes_per_employee = models.DecimalField(
        'Menit Efektif per Pegawai', max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    support_allowance_pct = models.DecimalField(
        'Tunjangan Waktu Pendukung (%)', max_digits=6, decimal_places=2,
        default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))],
    )
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='DRAFT'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_formasi_approved', verbose_name='Disetujui Oleh',
    )
    approved_at = models.DateTimeField('Waktu Persetujuan', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_formasi_created', verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rencana Formasi'
        verbose_name_plural = 'Rencana Formasi'
        ordering = ['-periode_mulai', 'unit_kerja__code', 'profesi']
        indexes = [
            models.Index(
                fields=['unit_kerja', 'profesi', 'periode_mulai'],
                name='sdm_formasi_unit_prof_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(periode_selesai__gte=models.F('periode_mulai')),
                name='sdm_formasi_periode_valid',
            ),
            models.CheckConstraint(
                condition=Q(effective_minutes_per_employee__gt=0),
                name='sdm_formasi_effective_positive',
            ),
            models.CheckConstraint(
                condition=Q(support_allowance_pct__gte=0),
                name='sdm_formasi_allowance_nonnegative',
            ),
        ]

    def clean(self):
        if self.periode_selesai and self.periode_mulai and (
            self.periode_selesai < self.periode_mulai
        ):
            raise ValidationError(
                {'periode_selesai': 'Periode selesai tidak boleh mendahului mulai.'}
            )

    def __str__(self):
        return f'{self.unit_kerja_id} — {self.profesi} — {self.periode_mulai}'


class AktivitasBebanKerja(models.Model):
    rencana = models.ForeignKey(
        RencanaFormasi, on_delete=models.CASCADE, related_name='activities',
        verbose_name='Rencana Formasi',
    )
    nama = models.CharField('Nama Aktivitas', max_length=200)
    volume = models.DecimalField(
        'Volume per Periode', max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    standard_minutes = models.DecimalField(
        'Standar Menit per Aktivitas', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    service_category = models.CharField('Kategori Layanan', max_length=120, blank=True)
    equipment_assumption = models.CharField(
        'Asumsi Peralatan', max_length=200, blank=True
    )
    qualification_note = models.CharField(
        'Catatan Kualifikasi', max_length=200, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aktivitas Beban Kerja'
        verbose_name_plural = 'Aktivitas Beban Kerja'
        ordering = ['rencana_id', 'pk']
        constraints = [
            models.CheckConstraint(
                condition=Q(volume__gte=0), name='sdm_aktivitas_volume_nonnegative'
            ),
            models.CheckConstraint(
                condition=Q(standard_minutes__gte=0),
                name='sdm_aktivitas_minutes_nonnegative',
            ),
        ]

    def __str__(self):
        return f'{self.nama} ({self.volume} × {self.standard_minutes} menit)'


class HasilFormasi(models.Model):
    """Immutable approved calculation result for one plan version."""

    rencana = models.OneToOneField(
        RencanaFormasi, on_delete=models.PROTECT, related_name='result',
        verbose_name='Rencana Formasi',
    )
    calculation_version = models.CharField('Versi Kalkulasi', max_length=40)
    required_fte = models.DecimalField('Kebutuhan FTE', max_digits=12, decimal_places=4)
    required_headcount = models.PositiveIntegerField('Kebutuhan Kepala')
    actual_fte = models.DecimalField('FTE Aktual', max_digits=12, decimal_places=4)
    gap_fte = models.DecimalField('Selisih FTE', max_digits=12, decimal_places=4)
    sufficiency_pct = models.DecimalField(
        'Kecukupan (%)', max_digits=7, decimal_places=2, null=True, blank=True
    )
    inputs_digest = models.CharField('Digest Input', max_length=64)
    calculated_at = models.DateTimeField('Waktu Kalkulasi', default=timezone.now)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_hasil_formasi_approved', verbose_name='Disetujui Oleh',
    )

    class Meta:
        verbose_name = 'Hasil Formasi'
        verbose_name_plural = 'Hasil Formasi'
        ordering = ['-calculated_at']

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Hasil formasi yang disetujui bersifat immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Hasil formasi yang disetujui tidak dapat dihapus.')

    def __str__(self):
        return f'Hasil {self.rencana_id} — {self.required_fte} FTE'


def _quantize(value):
    return value.quantize(FTE_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_formasi(plan):
    """Compute needs/actual/gap with Decimal arithmetic; never returns a bad result."""
    from sdm.models import PenempatanPegawai

    if not plan.effective_minutes_per_employee or (
        plan.effective_minutes_per_employee <= 0
    ):
        raise ValidationError(
            {'effective_minutes_per_employee': 'Menit efektif harus lebih dari nol.'}
        )
    activities = list(plan.activities.all())
    if not activities:
        raise ValidationError(
            {'activities': 'Rencana harus memiliki minimal satu aktivitas.'}
        )

    total_minutes = Decimal('0.00')
    for activity in activities:
        if activity.volume < 0 or activity.standard_minutes < 0:
            raise ValidationError(
                {'activities': 'Volume dan standar menit tidak boleh negatif.'}
            )
        total_minutes += activity.volume * activity.standard_minutes

    allowance = Decimal('1.00') + (plan.support_allowance_pct / Decimal('100.00'))
    required_fte = _quantize(
        total_minutes * allowance / plan.effective_minutes_per_employee
    )
    required_headcount = int(
        (total_minutes * allowance / plan.effective_minutes_per_employee).to_integral_value(
            rounding=ROUND_CEILING
        )
    )

    actual_fte = Decimal('0.00')
    assignments = PenempatanPegawai.objects.filter(
        unit_kerja_id=plan.unit_kerja_id,
        pegawai__profesi__iexact=plan.profesi,
        tanggal_mulai__lte=plan.periode_selesai,
    ).filter(
        Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=plan.periode_selesai)
    )
    for assignment in assignments:
        actual_fte += assignment.alokasi_fte
    actual_fte = _quantize(actual_fte)

    gap_fte = _quantize(required_fte - actual_fte)
    sufficiency_pct = None
    if required_fte > 0:
        sufficiency_pct = (
            actual_fte / required_fte * Decimal('100.00')
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    import hashlib
    import json

    digest = hashlib.sha256(
        json.dumps({
            'version': plan.calculation_version,
            'effective_minutes': str(plan.effective_minutes_per_employee),
            'allowance_pct': str(plan.support_allowance_pct),
            'activities': sorted(
                (
                    [str(a.volume), str(a.standard_minutes), a.nama]
                    for a in activities
                )
            ),
        }, sort_keys=True, default=str).encode('utf-8')
    ).hexdigest()

    return {
        'required_fte': required_fte,
        'required_headcount': required_headcount,
        'actual_fte': actual_fte,
        'gap_fte': gap_fte,
        'sufficiency_pct': sufficiency_pct,
        'inputs_digest': digest,
        'calculation_version': plan.calculation_version,
    }
