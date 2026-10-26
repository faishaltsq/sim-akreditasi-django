"""Lampiran formasi: private supporting files for a staffing request (F-A4)."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class LampiranFormasi(models.Model):
    """A private attachment justifying a formation plan.

    Files are stored through the private-storage path; a lampiran never gets a
    public URL and never leaves its unit scope. Deletion is PROTECT on the
    document so an approved plan's evidence cannot vanish.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rencana = models.ForeignKey(
        'sdm.RencanaFormasi', on_delete=models.CASCADE,
        related_name='lampiran', verbose_name='Rencana Formasi',
    )
    versi_dokumen = models.ForeignKey(
        'sdm.VersiDokumen', on_delete=models.PROTECT,
        related_name='lampiran_formasi', verbose_name='Versi Dokumen',
    )
    keterangan = models.CharField('Keterangan', max_length=200, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lampiran_formasi_uploaded', verbose_name='Diunggah Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lampiran Formasi'
        verbose_name_plural = 'Lampiran Formasi'
        ordering = ['rencana_id', 'pk']

    def clean(self):
        if self.versi_dokumen_id and self.rencana_id:
            has_unit = self.versi_dokumen.document.employee.penempatan.filter(
                unit_kerja_id=self.rencana.unit_kerja_id,
            ).exists()
            if not has_unit:
                raise ValidationError({
                    'versi_dokumen': (
                        'Lampiran harus milik pegawai yang ditempatkan pada unit '
                        'rencana formasi ini.'
                    )
                })

    def __str__(self):
        return f'Lampiran {self.rencana_id} — {self.versi_dokumen_id}'
