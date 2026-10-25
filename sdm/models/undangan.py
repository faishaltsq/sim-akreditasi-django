"""Account invitation model (Task B6)."""

from django.conf import settings
import uuid
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class UndanganAkunPegawai(models.Model):
    """Single-use, expiring invitation for optional staff account activation."""

    STATE_CHOICES = [
        ('SENT', 'Terkirim'),
        ('ACCEPTED', 'Diterima'),
        ('EXPIRED', 'Kadaluarsa'),
        ('REVOKED', 'Dicabut'),
        ('FAILED', 'Gagal Terkirim'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='invitations',
        verbose_name='Pegawai',
    )
    email = models.EmailField('Email Tujuan')
    email_version = models.PositiveIntegerField('Versi Email', default=1)
    intended_role = models.CharField('Peran yang Dimaksud', max_length=30, default='STAF_NAKES')
    idempotency_key = models.CharField(
        'Kunci Idempotensi', max_length=100, null=True, blank=True, unique=True
    )
    intended_is_active = models.BooleanField(
        'Akun Aktif Setelah Aktivasi', default=True
    )
    token_digest = models.CharField('Digest Token', max_length=128)
    expiry = models.DateTimeField('Kadaluarsa Pada')
    state = models.CharField('Status', max_length=12, choices=STATE_CHOICES, default='SENT')
    sent_at = models.DateTimeField('Waktu Kirim', null=True, blank=True)
    failed_at = models.DateTimeField('Waktu Gagal', null=True, blank=True)
    accepted_at = models.DateTimeField('Waktu Terima', null=True, blank=True)
    revoked_at = models.DateTimeField('Waktu Cabut', null=True, blank=True)
    attempt_count = models.PositiveIntegerField('Jumlah Percobaan', default=0)
    last_error = models.TextField('Terakhir Error', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hc_invitations_created',
        verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Undangan Akun Pegawai'
        verbose_name_plural = 'Undangan Akun Pegawai'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'email', 'state'],
                condition=models.Q(state='SENT'),
                name='sdm_undangan_one_sent_per_employee_email',
            ),
        ]

    def __str__(self):
        return f'Undangan {self.email} — {self.get_state_display()}'

    @property
    def is_active(self):
        return (
            self.state == 'SENT'
            and self.expiry
            and self.expiry > timezone.now()
        )
