"""Self-service staff portal requests (Task B7/A9)."""

from django.conf import settings
import uuid
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class LayananMandiri(models.Model):
    """Staff self-service request (profile correction, training request, leave)."""

    KIND_CHOICES = [
        ('PROFILE_CORRECTION', 'Perbaikan Profil'),
        ('TRAINING_REQUEST', 'Permintaan Pelatihan'),
        ('LEAVE_REQUEST', 'Permintaan Cuti'),
        ('DOCUMENT_REQUEST', 'Permintaan Dokumen'),
    ]
    STATE_CHOICES = [
        ('DRAFT', 'Draf'),
        ('SUBMITTED', 'Diajukan'),
        ('IN_REVIEW', 'Ditinjau'),
        ('APPROVED', 'Disetujui'),
        ('REJECTED', 'Ditolak'),
        ('CANCELLED', 'Dibatalkan'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='self_service_requests',
        verbose_name='Pemohon',
    )
    kind = models.CharField('Jenis Pengajuan', max_length=30, choices=KIND_CHOICES)
    payload = models.JSONField('Isi Pengajuan', default=dict, blank=True)
    state = models.CharField('Status', max_length=15, choices=STATE_CHOICES, default='DRAFT')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_staff_requests',
        verbose_name='Peninjau',
    )
    decision_reason = models.TextField('Alasan Keputusan', blank=True)
    decided_at = models.DateTimeField('Waktu Keputusan', null=True, blank=True)
    idempotency_key = models.CharField('Kunci Idempotensi', max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Layanan Mandiri'
        verbose_name_plural = 'Layanan Mandiri'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'kind', 'state'],
                condition=models.Q(state='DRAFT'),
                name='sdm_layanan_mandiri_one_draft_per_kind',
            ),
        ]

    def __str__(self):
        return f'{self.get_kind_display()} — {self.employee}'
