"""Workload planning model (Task A4).

WISN is a separately validated method and is NOT relabelled activity FTE.
`calculate_wisn` uses an independently reviewed formula/worksheet.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class BebanKerja(models.Model):
    """Approved workload snapshot for unit/profession/period (WISN input).

    Beds/BOR and visits/service volume are contextual inputs, not unexplained
    FTE multipliers. Unknowns are stored as unknown.
    """

    METODE_CHOICES = [
        ('ACTIVITY_FTE', 'Activity-based FTE'),
        ('WISN', 'Workload Indicator of Staffing Need'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        related_name='beban_kerja',
        verbose_name='Unit Kerja',
    )
    profesi = models.CharField('Profesi', max_length=120)
    periode_mulai = models.DateField('Periode Mulai')
    periode_selesai = models.DateField('Periode Selesai')
    metode = models.CharField(
        'Metode Perhitungan', max_length=20, choices=METODE_CHOICES,
        default='ACTIVITY_FTE',
    )
    calculation_version = models.CharField('Versi Kalkulasi', max_length=40)
    jam_operasional_per_hari = models.DecimalField(
        'Jam Operasional per Hari', max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    hari_operasional_per_minggu = models.DecimalField(
        'Hari Operasional per Minggu', max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    bed_capacity = models.PositiveIntegerField('Kapasitas Tempat Tidur', null=True, blank=True)
    bor = models.DecimalField(
        'BOR (desimal)', max_digits=5, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    kunjungan_periode = models.PositiveIntegerField('Kunjungan dalam Periode', null=True, blank=True)
    volume_layanan_periode = models.PositiveIntegerField('Volume Layanan dalam Periode', null=True, blank=True)
    standard_minutes_per_kunjungan = models.PositiveIntegerField(
        'Standar Menit per Kunjungan', null=True, blank=True,
        help_text='Dari studi waktu reviewed rumah sakit.',
    )
    faktor_pengantar_kategori = models.DecimalField(
        'Faktor Pengantar Kategori', max_digits=5, decimal_places=4,
        default=Decimal('1.0000'), validators=[MinValueValidator(Decimal('0'))],
    )
    faktor_pengantar_individu = models.DecimalField(
        'Faktor Pengantar Individu', max_digits=5, decimal_places=4,
        default=Decimal('1.0000'), validators=[MinValueValidator(Decimal('0'))],
    )
    is_approved = models.BooleanField('Disetujui', default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='beban_kerja_approved',
    )
    approved_at = models.DateTimeField('Waktu Disetujui', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='beban_kerja_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Beban Kerja'
        verbose_name_plural = 'Beban Kerja'
        ordering = ['-periode_mulai', '-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['unit_kerja', 'profesi', 'periode_mulai', 'periode_selesai', 'metode'],
                name='sdm_beban_kerja_unit_profesi_periode_metode_uniq',
            ),
            models.CheckConstraint(
                condition=Q(periode_selesai__gte=models.F('periode_mulai')),
                name='sdm_beban_kerja_periode_valid',
            ),
            models.CheckConstraint(
                condition=Q(bor__isnull=True) | (Q(bor__gte=Decimal('0')) & Q(bor__lte=Decimal('1'))),
                name='sdm_beban_kerja_bor_0_1',
            ),
        ]

    def __str__(self):
        return f'{self.unit_kerja_id} — {self.profesi} — {self.metode}'
