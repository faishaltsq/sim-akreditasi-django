"""Shift roster and digital attendance models (Task A10)."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class LokasiPresensi(models.Model):
    """Approved attendance location with radius (no continuous tracking)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        related_name='lokasi_presensi',
        verbose_name='Unit Kerja',
    )
    nama = models.CharField('Nama Lokasi', max_length=150)
    latitude = models.DecimalField('Latitude', max_digits=9, decimal_places=6)
    longitude = models.DecimalField('Longitude', max_digits=9, decimal_places=6)
    radius_meter = models.PositiveIntegerField(
        'Radius (meter)', default=150,
        validators=[MinValueValidator(1)],
    )
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lokasi Presensi'
        verbose_name_plural = 'Lokasi Presensi'
        ordering = ['unit_kerja_id', 'nama']

    def __str__(self):
        return f'{self.nama} ({self.radius_meter} m)'


class ShiftDinas(models.Model):
    """Versioned shift template published per unit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        related_name='shift_dinas',
        verbose_name='Unit Kerja',
    )
    nama = models.CharField('Nama Shift', max_length=100)
    jam_mulai = models.TimeField('Jam Mulai')
    jam_selesai = models.TimeField('Jam Selesai')
    lintas_hari = models.BooleanField(
        'Lintas Hari', default=False,
        help_text='True bila shift berakhir pada hari berikutnya.',
    )
    versi = models.PositiveIntegerField('Versi', default=1)
    is_published = models.BooleanField('Diterbitkan', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shift Dinas'
        verbose_name_plural = 'Shift Dinas'
        ordering = ['unit_kerja_id', 'jam_mulai']
        constraints = [
            models.UniqueConstraint(
                fields=['unit_kerja', 'nama', 'versi'],
                name='sdm_shift_unit_nama_versi_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.nama} {self.jam_mulai:%H:%M}–{self.jam_selesai:%H:%M}'


class PenugasanShift(models.Model):
    """Employee assignment to a published shift on a date."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shift = models.ForeignKey(
        ShiftDinas,
        on_delete=models.PROTECT,
        related_name='assignments',
        verbose_name='Shift',
    )
    employee = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='shift_assignments',
        verbose_name='Pegawai',
    )
    tanggal = models.DateField('Tanggal')
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Penugasan Shift'
        verbose_name_plural = 'Penugasan Shift'
        ordering = ['-tanggal', 'shift__jam_mulai']
        constraints = [
            models.UniqueConstraint(
                fields=['shift', 'employee', 'tanggal'],
                name='sdm_penugasan_shift_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.employee} @ {self.shift} {self.tanggal}'


class PeristiwaPresensi(models.Model):
    """Append-only attendance event (server receipt time + supplied event time)."""

    EVENT_CHOICES = [
        ('CHECK_IN', 'Masuk'),
        ('CHECK_OUT', 'Keluar'),
    ]
    SOURCE_CHOICES = [
        ('WEB', 'Web'),
        ('MANUAL_REVIEW', 'Tinjauan Manual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        PenugasanShift,
        on_delete=models.PROTECT,
        related_name='events',
        verbose_name='Penugasan Shift',
    )
    event = models.CharField('Peristiwa', max_length=12, choices=EVENT_CHOICES)
    event_at = models.DateTimeField('Waktu Peristiwa')
    recorded_at = models.DateTimeField('Waktu Diterima Server', default=timezone.now)
    source = models.CharField('Sumber', max_length=15, choices=SOURCE_CHOICES, default='WEB')
    latitude = models.DecimalField(
        'Latitude', max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        'Longitude', max_digits=9, decimal_places=6, null=True, blank=True
    )
    accuracy_meter = models.PositiveIntegerField('Akurasi (meter)', null=True, blank=True)
    within_radius = models.BooleanField('Dalam Radius', null=True, blank=True)
    location_note = models.CharField('Catatan Lokasi', max_length=200, blank=True)
    idempotency_key = models.CharField(
        'Kunci Idempotensi', max_length=120, unique=True
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='presensi_recorded',
        verbose_name='Dicatat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Peristiwa Presensi'
        verbose_name_plural = 'Peristiwa Presensi'
        ordering = ['-event_at', '-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'event'],
                condition=Q(event__in=['CHECK_IN', 'CHECK_OUT']),
                name='sdm_presensi_one_event_per_type',
            ),
        ]
        indexes = [
            models.Index(
                fields=['assignment', 'event_at'],
                name='sdm_presensi_time_idx',
            ),
        ]

    def __str__(self):
        return f'{self.assignment_id} {self.event} @ {self.event_at}'


class KoreksiPresensi(models.Model):
    """Append-only reviewed correction of an attendance event."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        PeristiwaPresensi,
        on_delete=models.PROTECT,
        related_name='corrections',
        verbose_name='Peristiwa Presensi',
    )
    corrected_event_at = models.DateTimeField('Waktu Peristiwa Terkoreksi')
    reason = models.TextField('Alasan Koreksi')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='presensi_corrections_reviewed',
        verbose_name='Ditinjau Oleh',
    )
    reviewed_at = models.DateTimeField('Waktu Tinjauan', default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Koreksi Presensi'
        verbose_name_plural = 'Koreksi Presensi'
        ordering = ['-reviewed_at', '-pk']

    def __str__(self):
        return f'Koreksi {self.event_id} → {self.corrected_event_at}'
