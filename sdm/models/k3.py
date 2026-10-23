"""Level 4 occupational health and staff safety (restricted clinical boundary)."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class RisikoK3Pegawai(models.Model):
    KATEGORI_CHOICES = [
        ('BIOLOGIS', 'Biologis'),
        ('KIMIA_B3', 'Kimia / B3'),
        ('ERGONOMI', 'Ergonomi'),
        ('KEKERASAN', 'Kekerasan & Perundungan'),
        ('LAINNYA', 'Lainnya'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_k3_risks', verbose_name='Unit Kerja',
    )
    kategori = models.CharField('Kategori Bahaya', max_length=20, choices=KATEGORI_CHOICES)
    uraian = models.TextField('Uraian Bahaya')
    risiko_unit = models.ForeignKey(
        'akreditasi.RisikoUnit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_k3_links', verbose_name='Risiko Organisasi Terkait',
    )
    pengendalian = models.TextField('Pengendalian', blank=True)
    pemilik = models.CharField('Pemilik Risiko', max_length=200, blank=True)
    review_date = models.DateField('Tanggal Tinjauan', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Risiko K3 Pegawai'
        verbose_name_plural = 'Risiko K3 Pegawai'
        ordering = ['unit_kerja__code', 'kategori', '-created_at']
        indexes = [
            models.Index(fields=['unit_kerja', 'kategori'], name='sdm_k3_unit_kat_idx'),
        ]

    def __str__(self):
        return f'{self.get_kategori_display()} — {self.unit_kerja_id}'


class ImunisasiPegawai(models.Model):
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='immunizations',
        verbose_name='Pegawai',
    )
    jenis = models.CharField('Jenis Imunisasi', max_length=120)
    dosis_ke = models.PositiveIntegerField('Dosis Ke', default=1)
    tanggal = models.DateField('Tanggal Pemberian')
    berlaku_sampai = models.DateField('Berlaku Sampai', null=True, blank=True)
    pemberi = models.CharField('Pemberi', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imunisasi Pegawai'
        verbose_name_plural = 'Imunisasi Pegawai'
        ordering = ['-tanggal']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'jenis', 'dosis_ke'],
                name='sdm_imunisasi_employee_dose_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.jenis} #{self.dosis_ke}'


class PemeriksaanKesehatanKerja(models.Model):
    """MCU record; clinical detail is readable only with a health grant."""
    FIT_CHOICES = [
        ('FIT', 'Fit untuk bekerja'),
        ('FIT_DENGAN_CATATAN', 'Fit dengan catatan'),
        ('TIDAK_FIT', 'Tidak fit'),
        ('PERLU_PEMERIKSAAN_ULANG', 'Perlu pemeriksaan ulang'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='health_exams',
        verbose_name='Pegawai',
    )
    tanggal = models.DateField('Tanggal Pemeriksaan')
    status_kebugaran = models.CharField(
        'Status Kebugaran', max_length=30, choices=FIT_CHOICES
    )
    ringkasan_klinis = models.TextField('Ringkasan Klinis', blank=True)
    berlaku_sampai = models.DateField('Berlaku Sampai', null=True, blank=True)
    pemeriksa = models.CharField('Pemeriksa', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pemeriksaan Kesehatan Kerja'
        verbose_name_plural = 'Pemeriksaan Kesehatan Kerja'
        ordering = ['-tanggal']
        indexes = [
            models.Index(fields=['employee', '-tanggal'], name='sdm_mcu_emp_date_idx'),
        ]

    def __str__(self):
        return f'MCU {self.tanggal} — {self.get_status_kebugaran_display()}'


class InsidenK3Pegawai(models.Model):
    KATEGORI_CHOICES = [
        ('TERTUSUK_JARUM', 'Tertusuk jarum / benda tajam'),
        ('MUSKULOSKELETAL', 'Cedera muskuloskeletal'),
        ('PAPARAN', 'Paparan biologis / kimia'),
        ('KEKERASAN', 'Kekerasan di tempat kerja'),
        ('LAINNYA', 'Lainnya'),
    ]
    STATUS_CHOICES = [
        ('BARU', 'Baru'),
        ('INVESTIGASI', 'Investigasi'),
        ('TINDAK_LANJUT', 'Tindak Lanjut'),
        ('SELESAI', 'Selesai'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='k3_incidents',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_k3_incidents', verbose_name='Unit Kerja',
    )
    kategori = models.CharField('Kategori', max_length=20, choices=KATEGORI_CHOICES)
    tanggal = models.DateField('Tanggal Kejadian', default=timezone.localdate)
    deskripsi = models.TextField('Deskripsi (tanpa identitas pasien)')
    status = models.CharField(
        'Status', max_length=15, choices=STATUS_CHOICES, default='BARU'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_k3_investigations', verbose_name='Investigator',
    )
    closed_at = models.DateTimeField('Ditutup Pada', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Insiden K3 Pegawai'
        verbose_name_plural = 'Insiden K3 Pegawai'
        ordering = ['-tanggal', '-created_at']
        indexes = [
            models.Index(fields=['status', '-tanggal'], name='sdm_k3_status_idx'),
        ]

    def clean(self):
        if self.deskripsi and len(self.deskripsi.strip()) < 10:
            raise ValidationError({
                'deskripsi': 'Deskripsi kejadian minimal 10 karakter.'
            })

    def __str__(self):
        return f'{self.get_kategori_display()} — {self.tanggal}'


class TindakLanjutK3(models.Model):
    insiden = models.ForeignKey(
        InsidenK3Pegawai, on_delete=models.CASCADE, related_name='followups',
        verbose_name='Insiden',
    )
    tindakan = models.TextField('Tindakan')
    penanggung_jawab = models.CharField('Penanggung Jawab', max_length=200, blank=True)
    tenggat = models.DateField('Tenggat', null=True, blank=True)
    selesai = models.BooleanField('Selesai', default=False)
    selesai_at = models.DateTimeField('Selesai Pada', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tindak Lanjut K3'
        verbose_name_plural = 'Tindak Lanjut K3'
        ordering = ['insiden_id', 'pk']

    def __str__(self):
        return f'{self.insiden_id}: {self.tindakan[:40]}'


class AksesDaruratK3(models.Model):
    """Break-glass access: reason, expiry, and mandatory review."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sdm_break_glass', verbose_name='Pengguna',
    )
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='break_glass_access',
        verbose_name='Pegawai',
    )
    alasan = models.TextField('Alasan Darurat')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField('Kedaluwarsa')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_break_glass_reviews', verbose_name='Ditinjau Oleh',
    )
    reviewed_at = models.DateTimeField('Waktu Tinjauan', null=True, blank=True)
    review_notes = models.TextField('Catatan Tinjauan', blank=True)

    class Meta:
        verbose_name = 'Akses Darurat K3'
        verbose_name_plural = 'Akses Darurat K3'
        ordering = ['-created_at']

    def is_valid(self):
        return self.reviewed_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f'break-glass {self.user_id} → {self.employee_id}'
