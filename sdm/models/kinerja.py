"""Level 3 performance appraisal and training-needs analysis."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class PeriodeKinerja(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draf'),
        ('FINAL', 'Final'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nama = models.CharField('Nama Periode', max_length=120)
    tanggal_mulai = models.DateField('Mulai')
    tanggal_selesai = models.DateField('Selesai')
    status = models.CharField(
        'Status', max_length=10, choices=STATUS_CHOICES, default='DRAFT'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Periode Kinerja'
        verbose_name_plural = 'Periode Kinerja'
        ordering = ['-tanggal_mulai']
        constraints = [
            models.CheckConstraint(
                condition=Q(tanggal_selesai__gte=F('tanggal_mulai')),
                name='sdm_periode_kinerja_valid',
            ),
        ]

    def __str__(self):
        return self.nama


class PenilaianKinerja(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draf'),
        ('FINAL', 'Final'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    periode = models.ForeignKey(
        PeriodeKinerja, on_delete=models.PROTECT, related_name='appraisals',
        verbose_name='Periode',
    )
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='appraisals',
        verbose_name='Pegawai',
    )
    status = models.CharField(
        'Status', max_length=10, choices=STATUS_CHOICES, default='DRAFT'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_appraisals_reviewed', verbose_name='Penilai',
    )
    acknowledged_at = models.DateTimeField('Diakui Pada', null=True, blank=True)
    appeal_notes = models.TextField('Catatan Keberatan', blank=True)
    finalized_at = models.DateTimeField('Difinalkan Pada', null=True, blank=True)
    # Siklus ARIMA: evaluasi mandiri, kalibrasi Komite Mutu/BPP, hasil
    # feedback meeting, dan kategori akhir yang mengikat saat finalisasi.
    self_assessment = models.TextField('Evaluasi Mandiri', blank=True)
    self_assessed_at = models.DateTimeField('Evaluasi Mandiri Pada', null=True, blank=True)
    kalibrasi_catatan = models.TextField('Catatan Kalibrasi (Mutu/BPP)', blank=True)
    calibrated_at = models.DateTimeField('Dikalibrasi Pada', null=True, blank=True)
    feedback_notes = models.TextField('Catatan Feedback Meeting', blank=True)
    feedback_at = models.DateTimeField('Feedback Pada', null=True, blank=True)
    KATEGORI_AKHIR_CHOICES = [
        ('SANGAT_MEMUASKAN', 'Sangat Memuaskan'),
        ('MEMUASKAN', 'Memuaskan'),
        ('SESUAI_HARAPAN', 'Sesuai Harapan'),
        ('PERLU_PERBAIKAN', 'Perlu Perbaikan'),
        ('TIDAK_MEMUASKAN', 'Tidak Memuaskan'),
    ]
    kategori_akhir = models.CharField(
        'Kategori Akhir', max_length=20, choices=KATEGORI_AKHIR_CHOICES,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Penilaian Kinerja'
        verbose_name_plural = 'Penilaian Kinerja'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['periode', 'employee'], name='sdm_appraisal_period_uniq'
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-created_at'], name='sdm_appraisal_status_idx'),
        ]

    @property
    def weighted_score(self):
        items = list(self.items.all())
        if not items:
            return None
        total_weight = sum((item.weight for item in items), Decimal('0.00'))
        if total_weight <= 0:
            return None
        scored = [item for item in items if item.score is not None]
        if not scored:
            return None
        earned = sum((item.score * item.weight for item in scored), Decimal('0.00'))
        return round(earned / total_weight, 2)

    def hitung_kategori(self):
        """Banding kategori dari weighted score skala 5 (None bila belum penuh)."""
        skor = self.weighted_score
        if skor is None:
            return ''
        if skor >= Decimal('4.55'):
            return 'SANGAT_MEMUASKAN'
        if skor >= Decimal('4.05'):
            return 'MEMUASKAN'
        if skor >= Decimal('3.55'):
            return 'SESUAI_HARAPAN'
        if skor >= Decimal('3.00'):
            return 'PERLU_PERBAIKAN'
        return 'TIDAK_MEMUASKAN'

    def __str__(self):
        return f'{self.employee_id} — {self.periode}'


class ButirPenilaian(models.Model):
    KATEGORI_CHOICES = [
        ('TARGET', 'Target Kinerja'),
        ('RISIKO', 'Kontribusi Risiko & Akreditasi'),
        ('PERILAKU', 'Perilaku / Kompetensi'),
    ]
    appraisal = models.ForeignKey(
        PenilaianKinerja, on_delete=models.CASCADE, related_name='items',
        verbose_name='Penilaian',
    )
    kategori = models.CharField('Kategori', max_length=10, choices=KATEGORI_CHOICES)
    nama = models.CharField('Butir', max_length=200)
    weight = models.DecimalField(
        'Bobot', max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    score = models.DecimalField(
        'Skor', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    notes = models.TextField('Catatan', blank=True)
    # Pilar ARIMA: target/realisasi teks pendek, provenance JSON, dan tautan
    # langsung ke indikator mutu bila butir ditarik dari INM/IMRS.
    target = models.CharField('Target', max_length=60, blank=True)
    realisasi = models.CharField('Realisasi', max_length=60, blank=True)
    sumber_refs = models.JSONField('Sumber Data', default=list, blank=True)
    indikator = models.ForeignKey(
        'akreditasi.IndikatorMutu', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='butir_penilaian',
        verbose_name='Indikator Mutu',
    )

    class Meta:
        verbose_name = 'Butir Penilaian'
        verbose_name_plural = 'Butir Penilaian'
        ordering = ['appraisal_id', 'kategori', 'pk']
        constraints = [
            models.CheckConstraint(
                condition=Q(weight__gte=0), name='sdm_butir_weight_nonnegative'
            ),
        ]

    def __str__(self):
        return self.nama


class KebutuhanPelatihan(models.Model):
    STATUS_CHOICES = [
        ('DIUSULKAN', 'Diusulkan'),
        ('DISETUJUI', 'Disetujui HR'),
        ('DITOLAK', 'Ditolak'),
        ('TERWUJUD', 'Terwujud dalam Diklat'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='training_needs',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_training_needs', verbose_name='Unit Kerja',
    )
    topik = models.CharField('Topik Pelatihan', max_length=200)
    alasan_agregat = models.TextField('Alasan Agregat', blank=True)
    rule_version = models.CharField('Versi Aturan', max_length=40, blank=True)
    source_refs = models.JSONField('Referensi Sumber', default=list, blank=True)
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='DIUSULKAN'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_training_needs_approved', verbose_name='Disetujui Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Kebutuhan Pelatihan'
        verbose_name_plural = 'Kebutuhan Pelatihan'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'topik', 'rule_version'],
                name='sdm_tna_employee_topic_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.topik} — {self.employee_id}'


class SumberKebutuhanPelatihan(models.Model):
    need = models.ForeignKey(
        KebutuhanPelatihan, on_delete=models.CASCADE, related_name='sources',
        verbose_name='Kebutuhan',
    )
    source_type = models.CharField('Jenis Sumber', max_length=40)
    source_id = models.CharField('ID Sumber', max_length=64, blank=True)
    source_date = models.DateField('Tanggal Sumber', null=True, blank=True)
    note = models.TextField('Catatan', blank=True)

    class Meta:
        verbose_name = 'Sumber Kebutuhan Pelatihan'
        verbose_name_plural = 'Sumber Kebutuhan Pelatihan'
        ordering = ['need_id', 'pk']

    def __str__(self):
        return f'{self.source_type}:{self.source_id}'


class TahapPenilaian(models.Model):
    """Append-only stage transition penilaian kinerja (siklus ARIMA).

    Routing tetap pada urutan tahap di ``sdm.services.workflow_kinerja``;
    tabel ini mencatat siapa, kapan, dan catatan pada tiap tahap.
    """

    TAHAP_CHOICES = [
        ('DATA_TERKUMPUL', 'Sinkronisasi Data'),
        ('SELF_ASSESSMENT', 'Evaluasi Mandiri'),
        ('REVIEW_ATASAN', 'Review Atasan'),
        ('KALIBRASI_MUTU', 'Kalibrasi Komite Mutu/BPP'),
        ('FEEDBACK', 'Feedback Meeting'),
        ('TERKUNCI', 'Penguncian Nilai'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appraisal = models.ForeignKey(
        PenilaianKinerja, on_delete=models.CASCADE, related_name='tahapan',
        verbose_name='Penilaian',
    )
    tahap = models.CharField('Tahap', max_length=30, choices=TAHAP_CHOICES)
    aktor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_appraisal_stages', verbose_name='Pelaku',
    )
    catatan = models.TextField('Catatan', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tahap Penilaian'
        verbose_name_plural = 'Tahap Penilaian'
        ordering = ['-created_at', '-pk']
        indexes = [
            models.Index(
                fields=['appraisal', '-created_at'], name='sdm_tahap_apr_crt_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Tahap penilaian bersifat immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Tahap penilaian tidak dapat dihapus.')

    def __str__(self):
        return f'{self.appraisal_id} — {self.get_tahap_display()}'
