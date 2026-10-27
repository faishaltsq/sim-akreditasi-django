from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Pegawai(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    KATEGORI_CHOICES = [
        ('PPA', 'Profesional Pemberi Asuhan'),
        ('NON_PPA', 'Non-PPA'),
    ]
    STATUS_CHOICES = [
        ('AKTIF', 'Aktif'),
        ('NONAKTIF', 'Nonaktif'),
    ]
    DATA_ORIGIN_CHOICES = [
        ('UNCLASSIFIED', 'Belum Diklasifikasi'),
        ('DEMO', 'Data Demo / Seeder'),
        ('VERIFIED_IMPORT', 'Impor Terverifikasi'),
        ('MANUAL', 'Input Manual'),
    ]

    akun = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pegawai_hc',
        verbose_name='Akun Pengguna',
    )
    nomor_pegawai = models.CharField(
        'Nomor Pegawai', max_length=50, blank=True, default=''
    )
    nama_lengkap = models.CharField('Nama Lengkap', max_length=200)
    kategori = models.CharField('Kategori Staf', max_length=10, choices=KATEGORI_CHOICES)
    profesi = models.CharField('Profesi', max_length=120, blank=True)
    profesi_master = models.ForeignKey(
        'sdm.MasterProfesiPegawai',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pegawai_master',
        verbose_name='Profesi (Master)',
        help_text='Tautan ke master profesi yang ditinjau; teks bebas lama tetap disimpan di kolom profesi.',
    )
    jenjang_master = models.ForeignKey(
        'sdm.MasterJenjangProfesi',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pegawai_jenjang',
        verbose_name='Jenjang Karir (Master)',
        help_text='Jenjang karir aktif; menyaring katalog RKK dan kewenangan.',
    )
    jabatan = models.CharField('Jabatan', max_length=150, blank=True)
    status = models.CharField(
        'Status Kepegawaian', max_length=10, choices=STATUS_CHOICES, default='AKTIF'
    )
    data_origin = models.CharField(
        'Sumber Data', max_length=20, choices=DATA_ORIGIN_CHOICES,
        default='UNCLASSIFIED', blank=False,
        help_text='Provenensi baris data. UNCLASSIFIED untuk baris seeder yang belum diverifikasi.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pegawai'
        verbose_name_plural = 'Pegawai'
        ordering = ['nama_lengkap', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['nomor_pegawai'],
                condition=~Q(nomor_pegawai=''),
                name='sdm_pegawai_nomor_nonblank_uniq',
            ),
        ]

    def __str__(self):
        return self.nama_lengkap


class PenempatanPegawai(models.Model):
    pegawai = models.ForeignKey(
        Pegawai,
        on_delete=models.PROTECT,
        related_name='penempatan',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        related_name='penempatan_pegawai',
        verbose_name='Unit Kerja',
    )
    unit_induk = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='penempatan_sub_unit',
        verbose_name='Unit Induk',
        help_text='Unit kerja utama ketika penempatan berada pada sub-unit.',
    )
    atasan_langsung = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bawahan_langsung',
        verbose_name='Atasan Langsung',
    )
    tanggal_mulai = models.DateField('Tanggal Mulai')
    tanggal_selesai = models.DateField('Tanggal Selesai', null=True, blank=True)
    alokasi_fte = models.DecimalField(
        'Alokasi FTE',
        max_digits=4,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.01')),
            MaxValueValidator(Decimal('1.00')),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Penempatan Pegawai'
        verbose_name_plural = 'Penempatan Pegawai'
        ordering = ['-tanggal_mulai', 'pk']
        indexes = [
            models.Index(
                fields=['pegawai', 'tanggal_mulai', 'tanggal_selesai'],
                name='sdm_penempatan_pegawai_tgl_idx',
            ),
            models.Index(
                fields=['unit_kerja', 'tanggal_mulai', 'tanggal_selesai'],
                name='sdm_penempatan_unit_tgl_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(alokasi_fte__gte=Decimal('0.01'))
                & Q(alokasi_fte__lte=Decimal('1.00')),
                name='sdm_penempatan_fte_0_1',
            ),
            models.CheckConstraint(
                condition=Q(tanggal_selesai__isnull=True)
                | Q(tanggal_selesai__gte=F('tanggal_mulai')),
                name='sdm_penempatan_tanggal_valid',
            ),
        ]

    def clean(self):
        super().clean()
        if self.unit_induk_id and self.unit_kerja_id:
            if self.unit_induk_id == self.unit_kerja_id:
                raise ValidationError({
                    'unit_induk': 'Unit induk tidak boleh sama dengan unit penempatan.'
                })
            if self.unit_kerja.parent_id != self.unit_induk_id:
                raise ValidationError({
                    'unit_induk': 'Unit penempatan harus merupakan turunan langsung unit induk.'
                })
        if self.atasan_langsung_id and self.pegawai_id:
            if self.atasan_langsung_id == self.pegawai_id:
                raise ValidationError({
                    'atasan_langsung': 'Pegawai tidak dapat menjadi atasan dirinya sendiri.'
                })

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.tanggal_mulai <= today and (
            self.tanggal_selesai is None or self.tanggal_selesai >= today
        )


class MasterProfesiPegawai(models.Model):
    """Reviewed profession master grouping medical, nursing/midwifery,
    other health and nonclinical staff."""
    KELUARGA_CHOICES = [
        ('MEDIS', 'Medis'),
        ('KEPERAWATAN_KEBIDANAN', 'Keperawatan & Kebidanan'),
        ('NAKES_LAIN', 'Tenaga Kesehatan Lainnya'),
        ('NON_KLINIS', 'Non Klinis'),
    ]
    code = models.CharField('Kode Profesi', max_length=30, unique=True)
    nama = models.CharField('Nama Profesi', max_length=120)
    keluarga = models.CharField('Kelompok Profesi', max_length=30, choices=KELUARGA_CHOICES)
    is_active = models.BooleanField('Aktif', default=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hc_professions_reviewed',
        verbose_name='Ditinjau Oleh',
    )
    reviewed_at = models.DateTimeField('Waktu Tinjauan', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Master Profesi Pegawai'
        verbose_name_plural = 'Master Profesi Pegawai'
        ordering = ['keluarga', 'nama']

    def __str__(self):
        return f'{self.code} — {self.nama}'
