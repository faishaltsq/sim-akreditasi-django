"""Structured clinical logbook entries (C-2) and preseptor verification."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class EntriLogbookKlinis(models.Model):
    """One performed clinical action row; recap aggregates a 36-month window."""

    KATEGORI_CHOICES = [
        ('M', 'Mandiri'),
        ('S', 'Supervisi'),
        ('K', 'Kolaborasi'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='logbook_entries',
        verbose_name='Pegawai',
    )
    tanggal = models.DateField('Tanggal Tindakan')
    waktu = models.DateTimeField('Waktu Tindakan', null=True, blank=True)
    pasien_ref = models.CharField(
        'Inisial / No. RM Pasien', max_length=60, blank=True, default='',
        help_text='Hanya simpan inisial atau nomor rekam medis yang dipotong, bukan identitas lengkap pasien.',
    )
    kategori = models.CharField(
        'Kategori', max_length=1, choices=KATEGORI_CHOICES, default='M',
    )
    shift = models.CharField(
        'Shift', max_length=6,
        choices=[('PAGI', 'Pagi'), ('SIANG', 'Siang'), ('MALAM', 'Malam')],
        blank=True, default='',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT, related_name='logbook_entries',
        verbose_name='Unit Kerja',
    )
    katalog_tindakan = models.ForeignKey(
        'sdm.KatalogTindakan', on_delete=models.PROTECT, null=True, blank=True,
        related_name='logbook_entries', verbose_name='Tindakan (Katalog)',
    )
    tindakan = models.CharField('Tindakan (Teks Bebas)', max_length=200, blank=True)
    jumlah_mandiri = models.PositiveIntegerField('Jumlah Mandiri', default=0)
    jumlah_supervisi = models.PositiveIntegerField('Jumlah Supervisi', default=0)
    jumlah_kolaborasi = models.PositiveIntegerField('Jumlah Kolaborasi', default=0)
    catatan = models.TextField('Catatan', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logbook_entries_created', verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Entri Logbook Klinis'
        verbose_name_plural = 'Entri Logbook Klinis'
        ordering = ['-tanggal', '-created_at']
        indexes = [
            models.Index(fields=['employee', '-tanggal'], name='sdm_log_emp_tgl_idx'),
            models.Index(fields=['employee', 'waktu'], name='sdm_log_emp_waktu_idx'),
        ]

    def clean(self):
        if bool(self.katalog_tindakan_id) == bool(self.tindakan.strip()):
            raise ValidationError({
                'katalog_tindakan': 'Pilih salah satu: tindakan katalog atau teks bebas.',
                'tindakan': 'Pilih salah satu: tindakan katalog atau teks bebas.',
            })
        if not (self.jumlah_mandiri or self.jumlah_supervisi or self.jumlah_kolaborasi):
            raise ValidationError({
                'jumlah_mandiri': 'Minimal satu jumlah (mandiri, supervisi, atau kolaborasi) harus lebih dari nol.',
            })

    def save(self, *args, **kwargs):
        if not getattr(self, '_allow_verified_write', False):
            if self.pk and EntriLogbookKlinis.objects.filter(
                pk=self.pk, verifikasi__status=VerifikasiLogbook.VERIFIED,
            ).exists():
                raise ValidationError(
                    'Entri yang sudah diverifikasi tidak dapat diubah.'
                )
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.verifikasi.filter(status=VerifikasiLogbook.VERIFIED).exists():
            raise ValidationError('Entri yang sudah diverifikasi tidak dapat dihapus.')
        return super().delete(*args, **kwargs)

    @property
    def verifikasi_terakhir(self):
        """Latest preseptor decision, or ``None`` when the entry is unverified."""
        return self.verifikasi.first()

    @property
    def sudah_diverifikasi(self):
        """True when the latest decision is VERIFIED; the entry is then locked."""
        latest = self.verifikasi_terakhir
        return latest is not None and latest.status == VerifikasiLogbook.VERIFIED

    def __str__(self):
        label = self.katalog_tindakan.nama if self.katalog_tindakan else self.tindakan
        return f'{self.tanggal} {label} ({self.employee_id})'


class VerifikasiLogbook(models.Model):
    """Append-only preseptor decision on one logbook entry.

    A rejected entry may be verified again later, so rows are never updated
    or deleted; the newest row decides the entry's state.
    """

    VERIFIED = 'VERIFIED'
    REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (VERIFIED, 'Diverifikasi'),
        (REJECTED, 'Ditolak'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entri = models.ForeignKey(
        EntriLogbookKlinis, on_delete=models.PROTECT, related_name='verifikasi',
        verbose_name='Entri Logbook',
    )
    verifikator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='logbook_verifikasi', verbose_name='Verifikator',
    )
    status = models.CharField('Status', max_length=10, choices=STATUS_CHOICES)
    catatan = models.TextField('Catatan', blank=True)
    verified_at = models.DateTimeField('Waktu Verifikasi', default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Verifikasi Logbook'
        verbose_name_plural = 'Verifikasi Logbook'
        ordering = ['-verified_at', '-created_at']
        indexes = [
            models.Index(fields=['entri', '-verified_at'], name='sdm_verif_log_entri_idx'),
        ]

    def __str__(self):
        return f'{self.entri_id} — {self.get_status_display()}'
