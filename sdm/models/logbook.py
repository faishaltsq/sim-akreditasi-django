"""Structured clinical logbook entries (C-2)."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class EntriLogbookKlinis(models.Model):
    """One performed clinical action row; recap aggregates a 36-month window."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='logbook_entries',
        verbose_name='Pegawai',
    )
    tanggal = models.DateField('Tanggal Tindakan')
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
            models.Index(fields=['employee', '-tanggal'], name='sdm_log emp_tgl_idx'),
        ]

    def clean(self):
        if bool(self.katalog_tindakan_id) == bool(self.tindakan.strip()):
            raise ValidationError({
                'katalog_tindakan': 'Pilih salah satu: tindakan katalog atau teks bebas.',
                'tindakan': 'Pilih salah satu: tindakan katalog atau teks bebas.',
            })
        if self.jumlah_mandiri == 0 and self.jumlah_supervisi == 0:
            raise ValidationError({
                'jumlah_mandiri': 'Minimal satu jumlah (mandiri atau supervisi) harus lebih dari nol.',
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        label = self.katalog_tindakan.nama if self.katalog_tindakan else self.tindakan
        return f'{self.tanggal} {label} ({self.employee_id})'
