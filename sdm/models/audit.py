from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ImmutableAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Peristiwa SDM bersifat immutable.')

    def delete(self):
        raise ValidationError('Peristiwa SDM tidak dapat dihapus.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('Peristiwa SDM bersifat immutable.')


class PeristiwaSDM(models.Model):
    objects = models.Manager.from_queryset(ImmutableAuditQuerySet)()

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peristiwa_sdm',
        verbose_name='Pelaku',
    )
    jenis_peristiwa = models.CharField('Jenis Peristiwa', max_length=80)
    target_tipe = models.CharField('Jenis Target', max_length=80)
    target_id = models.CharField('ID Target', max_length=64)
    status_sebelum = models.CharField('Status Sebelumnya', max_length=40, blank=True)
    status_sesudah = models.CharField('Status Sesudahnya', max_length=40, blank=True)
    alasan = models.TextField('Alasan', blank=True)
    correlation_id = models.CharField('ID Korelasi', max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Peristiwa SDM'
        verbose_name_plural = 'Peristiwa SDM'
        ordering = ['-created_at', '-pk']
        indexes = [
            models.Index(
                fields=['target_tipe', 'target_id', '-created_at'],
                name='per_evt_tgt_crt_idx',
            ),
            models.Index(
                fields=['actor', '-created_at'],
                name='per_evt_actor_crt_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Peristiwa SDM bersifat immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Peristiwa SDM tidak dapat dihapus.')

    def __str__(self):
        return f'{self.jenis_peristiwa} — {self.target_tipe}:{self.target_id}'
