"""Reference standards and effective working time (F-A2).

Two independent reference layers feed workforce planning:

* :class:`JamKerjaEfektif` — how many productive minutes one employee
  delivers in a year, derived from working days minus documented deductions.
  Versioned per year and immutable once approved, so a printed staffing report
  stays reproducible after the hospital revises its assumptions.
* :class:`StandarKetenagaan` — reviewed regulatory ratios and standard
  workloads. Retiring a standard never deletes it, because historical plans
  must still show the value they were approved against.

Neither model invents a number. An unknown deduction is unknown, not zero, and
`full_clean()` refuses to approve an incomplete row.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

DAYS_PER_YEAR = Decimal('365')
MINUTES_PER_HOUR = Decimal('60')


class JamKerjaEfektif(models.Model):
    """Approved productive minutes per employee per year (JKE).

    ``hari_produktif`` and ``menit_efektif_per_tahun`` are derived, never
    stored: storing them would let a stale value survive an edit to an input.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tahun = models.PositiveIntegerField('Tahun')
    versi = models.PositiveIntegerField('Versi', default=1)
    hari_kerja = models.PositiveIntegerField(
        'Hari Kerja per Tahun',
        help_text='Hari kerja terjadwal sebelum dikurangi cuti, sakit, dan libur.',
    )
    cuti_tahunan = models.PositiveIntegerField('Cuti Tahunan (hari)')
    hari_sakit_rata2 = models.PositiveIntegerField('Rata-rata Sakit (hari)')
    libur_nasional = models.PositiveIntegerField('Libur Nasional (hari)')
    jam_pelatihan = models.DecimalField(
        'Jam Pelatihan per Tahun', max_digits=7, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    jam_kerja_per_hari = models.DecimalField(
        'Jam Kerja per Hari', max_digits=4, decimal_places=2,
        default=Decimal('7.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    sumber = models.CharField(
        'Sumber Acuan', max_length=200, blank=True,
        help_text='Regulasi, keputusan direktur, atau studi waktu yang mendasari angka ini.',
    )
    is_approved = models.BooleanField('Disetujui', default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jke_approved', verbose_name='Disetujui Oleh',
    )
    approved_at = models.DateTimeField('Waktu Disetujui', null=True, blank=True)
    is_active = models.BooleanField('Berlaku', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jke_created', verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Jam Kerja Efektif'
        verbose_name_plural = 'Jam Kerja Efektif'
        ordering = ['-tahun', '-versi']
        constraints = [
            models.UniqueConstraint(
                fields=['tahun', 'versi'], name='sdm_jke_tahun_versi_uniq',
            ),
            models.UniqueConstraint(
                fields=['tahun'],
                condition=Q(is_active=True) & Q(is_approved=True),
                name='sdm_jke_satu_aktif_per_tahun',
            ),
            models.CheckConstraint(
                condition=Q(jam_kerja_per_hari__gt=0),
                name='sdm_jke_jam_kerja_positif',
            ),
        ]

    # ── derived values ─────────────────────────────────────────────────────

    @property
    def hari_produktif(self):
        """Scheduled working days minus every documented absence."""
        return (
            self.hari_kerja
            - self.cuti_tahunan
            - self.hari_sakit_rata2
            - self.libur_nasional
        )

    @property
    def jam_efektif_per_tahun(self):
        """Productive hours, after removing in-service training hours."""
        return (
            Decimal(self.hari_produktif) * self.jam_kerja_per_hari
            - self.jam_pelatihan
        )

    @property
    def menit_efektif_per_tahun(self):
        return (self.jam_efektif_per_tahun * MINUTES_PER_HOUR).quantize(
            Decimal('0.01')
        )

    # ── validation ─────────────────────────────────────────────────────────

    def clean(self):
        super().clean()
        fields = (
            'hari_kerja', 'cuti_tahunan', 'hari_sakit_rata2', 'libur_nasional',
            'jam_pelatihan', 'jam_kerja_per_hari',
        )
        missing = [f for f in fields if getattr(self, f) is None]
        if missing:
            raise ValidationError({
                f: 'Wajib diisi; komponen yang kosong bukan nol.'
                for f in missing
            })
        if self.hari_kerja and self.hari_kerja > DAYS_PER_YEAR:
            raise ValidationError(
                {'hari_kerja': 'Hari kerja tidak boleh melebihi 365 hari.'}
            )
        if self.hari_produktif <= 0:
            raise ValidationError({
                'hari_kerja': (
                    'Pengurangan cuti, sakit, dan libur menghabiskan seluruh hari kerja; '
                    f'hari produktif = {self.hari_produktif}.'
                )
            })
        if self.jam_efektif_per_tahun <= 0:
            raise ValidationError({
                'jam_pelatihan': (
                    'Jam pelatihan melebihi total jam kerja tahunan; '
                    f'jam efektif = {self.jam_efektif_per_tahun}.'
                )
            })

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous is not None and previous.is_approved:
                raise ValidationError(
                    'Jam kerja efektif yang sudah disetujui bersifat immutable; '
                    'buat versi baru.'
                )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_approved:
            raise ValidationError(
                'Jam kerja efektif yang sudah disetujui tidak dapat dihapus.'
            )
        return super().delete(*args, **kwargs)

    # ── lifecycle ──────────────────────────────────────────────────────────

    def approve(self, *, by, supersede_previous=False):
        """Approve this version, optionally deactivating the year's old one."""
        self.full_clean()
        active_sibling = type(self).objects.filter(
            tahun=self.tahun, is_active=True, is_approved=True,
        ).exclude(pk=self.pk).first()
        if active_sibling is not None and not supersede_previous:
            raise ValidationError({
                '__all__': (
                    f'Tahun {self.tahun} sudah punya JKE aktif '
                    f'v{active_sibling.versi}. Gunakan supersede_previous untuk '
                    'menggantikannya.'
                )
            })
        if supersede_previous:
            type(self).objects.filter(
                tahun=self.tahun, is_active=True,
            ).exclude(pk=self.pk).update(is_active=False, updated_at=timezone.now())
        self.is_approved = True
        self.is_active = True
        self.approved_by = by
        self.approved_at = timezone.now()
        self.save(update_fields=[
            'is_approved', 'is_active', 'approved_by', 'approved_at', 'updated_at',
        ])
        return self

    def __str__(self):
        return f'JKE {self.tahun} v{self.versi} — {self.menit_efektif_per_tahun} menit'


class StandarKetenagaan(models.Model):
    """Reviewed regulatory ratio, standard workload, or correction factor.

    ``sumber_regulasi`` is mandatory: an uncited ratio is an opinion, not a
    standard, and an accreditation surveyor will ask for the citation.
    """

    JENIS_CHOICES = [
        ('RASIO_REGULASI', 'Rasio Regulasi'),
        ('STANDAR_WAKTU', 'Standar Waktu Tindakan'),
        ('FAKTOR_KOREKSI', 'Faktor Koreksi'),
        ('AMBANG_RISIKO', 'Ambang Risiko Ketenagaan'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='standar_ketenagaan', verbose_name='Unit Kerja',
        null=True, blank=True,
        help_text='Kosong berarti berlaku untuk seluruh rumah sakit.',
    )
    profesi = models.CharField('Profesi', max_length=120)
    jenis = models.CharField('Jenis Standar', max_length=20, choices=JENIS_CHOICES)
    nama = models.CharField('Nama Standar', max_length=200)
    nilai = models.DecimalField(
        'Nilai', max_digits=12, decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0001'))],
    )
    satuan = models.CharField('Satuan', max_length=80)
    sumber_regulasi = models.CharField('Sumber Regulasi', max_length=300)
    berlaku_mulai = models.DateField('Berlaku Mulai')
    berlaku_sampai = models.DateField('Berlaku Sampai', null=True, blank=True)
    is_active = models.BooleanField('Aktif', default=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='standar_ketenagaan_reviewed', verbose_name='Ditinjau Oleh',
    )
    reviewed_at = models.DateTimeField('Waktu Tinjauan', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Standar Ketenagaan'
        verbose_name_plural = 'Standar Ketenagaan'
        ordering = ['unit_kerja_id', 'profesi', 'jenis', '-berlaku_mulai']
        indexes = [
            models.Index(
                fields=['unit_kerja', 'profesi', 'jenis', 'is_active'],
                name='sdm_standar_unit_jenis_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(berlaku_sampai__isnull=True)
                | Q(berlaku_sampai__gte=models.F('berlaku_mulai')),
                name='sdm_standar_periode_valid',
            ),
        ]

    def clean(self):
        super().clean()
        if not (self.sumber_regulasi or '').strip():
            raise ValidationError({
                'sumber_regulasi': (
                    'Sumber regulasi wajib dicantumkan; rasio tanpa acuan '
                    'tidak dapat dipertahankan saat survei.'
                )
            })
        if not (self.satuan or '').strip():
            raise ValidationError({'satuan': 'Satuan wajib diisi.'})

    def retire(self, *, at=None):
        """Deactivate without deleting: historical plans still reference this."""
        self.is_active = False
        self.berlaku_sampai = at or timezone.localdate()
        self.save(update_fields=['is_active', 'berlaku_sampai', 'updated_at'])
        return self

    def __str__(self):
        return f'{self.nama} = {self.nilai} {self.satuan}'
