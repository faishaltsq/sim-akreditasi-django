"""Idempotent in-app reminders for document expiry and work queues (HC-04)."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


BANDS = ('LT_30', 'LT_60', 'LT_90', 'EXPIRED')


class PengingatSDM(models.Model):
    BAND_CHOICES = [
        ('LT_30', '0–30 hari'),
        ('LT_60', '31–60 hari'),
        ('LT_90', '61–90 hari'),
        ('EXPIRED', 'Kedaluwarsa'),
        ('TASK_DUE', 'Tugas mendekati tenggat'),
        ('TASK_OVERDUE', 'Tugas lewat tenggat'),
    ]
    TARGET_CHOICES = [
        ('DOCUMENT', 'Dokumen'),
        ('ORIENTATION', 'Orientasi'),
        ('APPRAISAL', 'Penilaian Kinerja'),
        ('TRAINING', 'Diklat'),
    ]
    CHANNEL_CHOICES = [('IN_APP', 'Dalam aplikasi')]

    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.CASCADE, related_name='reminders',
        verbose_name='Pegawai',
    )
    version = models.ForeignKey(
        'sdm.VersiDokumen', on_delete=models.CASCADE, null=True, blank=True,
        related_name='reminders', verbose_name='Versi Dokumen',
    )
    band = models.CharField('Pita Peringatan', max_length=12, choices=BAND_CHOICES)
    target_type = models.CharField(
        'Jenis Target', max_length=15, choices=TARGET_CHOICES, default='DOCUMENT'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name='sdm_reminders', verbose_name='Penerima',
    )
    due_date = models.DateField('Tanggal Jatuh Tempo', null=True, blank=True)
    channel = models.CharField(
        'Kanal', max_length=12, choices=CHANNEL_CHOICES, default='IN_APP'
    )
    idempotency_key = models.CharField('Kunci Idempotensi', max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField('Dibaca Pada', null=True, blank=True)

    class Meta:
        verbose_name = 'Pengingat SDM'
        verbose_name_plural = 'Pengingat SDM'
        ordering = ['due_date', '-created_at']
        indexes = [
            models.Index(
                fields=['recipient', 'read_at', 'due_date'],
                name='sdm_pengingat_recip_idx',
            ),
        ]

    @staticmethod
    def build_key(*, employee_id, version_id, band, target_type='DOCUMENT'):
        return f'{target_type}:{employee_id}:{version_id or "none"}:{band}'

    def __str__(self):
        return f'{self.band} — {self.employee_id}'


def sync_expiry_reminders(*, as_of=None):
    """Create missing reminders once per employee/version/band; never duplicates."""
    from datetime import timedelta

    from sdm.models import VersiDokumen

    as_of = as_of or timezone.localdate()
    d30 = as_of + timedelta(days=30)
    d60 = as_of + timedelta(days=60)
    d90 = as_of + timedelta(days=90)

    versions = VersiDokumen.objects.filter(
        status='VERIFIED', valid_until__isnull=False,
    ).exclude(document__sensitivity='health').select_related(
        'document__employee__akun'
    )

    created = 0
    for version in versions:
        if version.valid_until < as_of:
            band = 'EXPIRED'
        elif version.valid_until <= d30:
            band = 'LT_30'
        elif version.valid_until <= d60:
            band = 'LT_60'
        elif version.valid_until <= d90:
            band = 'LT_90'
        else:
            continue

        employee = version.document.employee
        key = PengingatSDM.build_key(
            employee_id=employee.pk, version_id=version.pk, band=band
        )
        _, was_created = PengingatSDM.objects.get_or_create(
            idempotency_key=key,
            defaults={
                'employee': employee,
                'version': version,
                'band': band,
                'target_type': 'DOCUMENT',
                'recipient': employee.akun,
                'due_date': version.valid_until,
            },
        )
        created += int(was_created)
    return created


def visible_reminders(user, *, limit=50):
    return PengingatSDM.objects.filter(
        recipient=user, read_at__isnull=True
    ).select_related('employee', 'version__document').order_by('due_date')[:limit]


def sync_task_reminders(*, as_of=None):
    """Orientation and appraisal tasks: due-soon and overdue bands, idempotent."""
    from datetime import timedelta

    from sdm.models import PenilaianKinerja, PenugasanOrientasi

    as_of = as_of or timezone.localdate()
    soon = as_of + timedelta(days=7)
    created = 0

    orientations = PenugasanOrientasi.objects.filter(
        status='BERJALAN'
    ).select_related('employee__akun')
    for assignment in orientations:
        if assignment.tenggat < as_of:
            band = 'TASK_OVERDUE'
        elif assignment.tenggat <= soon:
            band = 'TASK_DUE'
        else:
            continue
        key = PengingatSDM.build_key(
            employee_id=assignment.employee_id,
            version_id=assignment.pk,
            band=band,
            target_type='ORIENTATION',
        )
        _, was_created = PengingatSDM.objects.get_or_create(
            idempotency_key=key,
            defaults={
                'employee': assignment.employee,
                'band': band,
                'target_type': 'ORIENTATION',
                'recipient': assignment.employee.akun,
                'due_date': assignment.tenggat,
            },
        )
        created += int(was_created)

    appraisals = PenilaianKinerja.objects.filter(
        status='DRAFT'
    ).select_related('employee__akun', 'periode')
    for appraisal in appraisals:
        due = appraisal.periode.tanggal_selesai
        if due < as_of:
            band = 'TASK_OVERDUE'
        elif due <= soon:
            band = 'TASK_DUE'
        else:
            continue
        key = PengingatSDM.build_key(
            employee_id=appraisal.employee_id,
            version_id=appraisal.pk,
            band=band,
            target_type='APPRAISAL',
        )
        _, was_created = PengingatSDM.objects.get_or_create(
            idempotency_key=key,
            defaults={
                'employee': appraisal.employee,
                'band': band,
                'target_type': 'APPRAISAL',
                'recipient': appraisal.employee.akun,
                'due_date': due,
            },
        )
        created += int(was_created)

    return created


def sync_all_reminders(*, as_of=None):
    return sync_expiry_reminders(as_of=as_of) + sync_task_reminders(as_of=as_of)
