"""Level 2 workflows: recruitment, PSV, clinical privileging, orientation."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

# Ambang lulus post-test orientasi (dokumen KPS 4 & 8: minimal 80).
PASSING_GRADE = 80


class ProgramOrientasi(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    JENIS_CHOICES = [
        ('UMUM', 'Orientasi Umum'),
        ('KHUSUS', 'Orientasi Khusus Unit'),
    ]
    KELOMPOK_CHOICES = [
        ('MEDIS', 'Staf Medis'),
        ('KEPERAWATAN', 'Staf Keperawatan & Kebidanan'),
        ('NAKES_LAIN', 'Nakes Lainnya'),
        ('NON_KLINIS', 'Non-Klinis / Admin'),
        ('', 'Semua kelompok'),
    ]
    nama = models.CharField('Nama Program', max_length=200)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT, null=True, blank=True,
        related_name='sdm_orientation_programs',
        verbose_name='Unit Kerja',
        help_text='Kosong berarti orientasi umum rumah sakit.',
    )
    jenis = models.CharField(
        'Jenis Orientasi', max_length=8, choices=JENIS_CHOICES, default='KHUSUS',
    )
    kelompok_staf = models.CharField(
        'Kelompok Staf', max_length=12, choices=KELOMPOK_CHOICES, blank=True,
        help_text='Kosong berarti program berlaku untuk semua kelompok.',
    )
    durasi_hari = models.PositiveIntegerField(
        'Durasi Hari', default=14,
        help_text='Durasi baku dari matriks orientasi (dokumen KPS 4 & 8).',
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


class AsesmenOrientasi(models.Model):
    """Append-only post-test result for one orientation assignment.

    Lulus bila nilai >= PASSING_GRADE (80). Nilai gagal menandai remedial;
    percobaan berikutnya ditulis sebagai baris baru (riwayat tidak diubah).
    """

    assignment = models.ForeignKey(
        PenugasanOrientasi, on_delete=models.CASCADE, related_name='assessments',
        verbose_name='Penugasan',
    )
    nilai = models.DecimalField(
        'Nilai', max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    lulus = models.BooleanField('Lulus', editable=False)
    percobaan = models.PositiveIntegerField('Percobaan', editable=False)
    penguji = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_orientation_assessments', verbose_name='Penguji',
    )
    catatan = models.TextField('Catatan', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Asesmen Orientasi'
        verbose_name_plural = 'Asesmen Orientasi'
        ordering = ['assignment_id', 'percobaan']
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'percobaan'],
                name='sdm_orientasi_asesmen_percobaan_uniq',
            ),
        ]

    def save(self, *args, **kwargs):
        self._prep()
        super().save(*args, **kwargs)

    def _prep(self):
        if self.percobaan is None:
            last = AsesmenOrientasi.objects.filter(
                assignment=self.assignment,
            ).order_by('-percobaan').first()
            self.percobaan = (last.percobaan + 1) if last else 1
        self.lulus = self.nilai >= PASSING_GRADE

    def __str__(self):
        return f'{self.assignment_id}#{self.percobaan}: {self.nilai}'
