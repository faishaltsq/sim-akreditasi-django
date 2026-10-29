"""Fase C4: bank soal & sesi ujian kompetensi (CBT) untuk rekrutmen."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from decimal import Decimal


class PaketSoal(models.Model):
    """A named set of questions used for one vacancy's competency test."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lowongan = models.ForeignKey(
        'sdm.Lowongan', on_delete=models.PROTECT, related_name='paket_soal',
        verbose_name='Lowongan',
    )
    nama = models.CharField('Nama Paket', max_length=200)
    durasi_menit = models.PositiveSmallIntegerField(
        'Durasi (menit)', default=60,
        validators=[MinValueValidator(1), MaxValueValidator(480)],
    )
    # Passing grade ditaruh sebagai field yang bisa diatur admin, bukan konstanta
    # yang di-hardcode: nilainya berasal dari SK komite, bukan dari tebakan kode.
    passing_grade = models.DecimalField(
        'Passing Grade', max_digits=5, decimal_places=2, default=Decimal('70.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text='Nilai minimum lulus (0–100); ditetapkan komite, bukan oleh sistem.',
    )
    is_active = models.BooleanField('Aktif', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_paket_soal_created', verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paket Soal'
        verbose_name_plural = 'Paket Soal'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['lowongan', 'nama'],
                name='sdm_paket_soal_nama_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.nama} ({self.lowongan.judul})'


class Soal(models.Model):
    """One multiple-choice question belonging to a packet."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paket = models.ForeignKey(
        PaketSoal, on_delete=models.CASCADE, related_name='soal',
        verbose_name='Paket',
    )
    nomor = models.PositiveSmallIntegerField('Nomor Urut')
    pertanyaan = models.TextField('Pertanyaan')
    pilihan_a = models.CharField('Pilihan A', max_length=300)
    pilihan_b = models.CharField('Pilihan B', max_length=300)
    pilihan_c = models.CharField('Pilihan C', max_length=300)
    pilihan_d = models.CharField('Pilihan D', max_length=300)
    jawaban_benar = models.CharField(
        'Jawaban Benar', max_length=1,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')],
    )
    bobot = models.DecimalField(
        'Bobot', max_digits=5, decimal_places=2, default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )

    class Meta:
        verbose_name = 'Soal'
        verbose_name_plural = 'Soal'
        ordering = ['paket', 'nomor']
        constraints = [
            models.UniqueConstraint(
                fields=['paket', 'nomor'], name='sdm_soal_nomor_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.paket.nama} #{self.nomor}'


class SesiUjian(models.Model):
    """One candidate's attempt at one packet.

    The order of questions is fixed at session creation and stored on the
    session, so refreshing the page or reconnecting never re-shuffles the
    paper mid-attempt. The deadline is a server-side timestamp: a candidate
    cannot extend the window by editing the client clock.
    """

    STATUS_CHOICES = [
        ('BERLANGSUNG', 'Berlangsung'),
        ('SELESAI', 'Selesai'),
        ('KEDALUWARSA', 'Kedaluwarsa'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(
        'Token Akses', max_length=64, unique=True, default=uuid.uuid4,
    )
    lamaran = models.ForeignKey(
        'sdm.Lamaran', on_delete=models.CASCADE, related_name='sesi_ujian',
        verbose_name='Lamaran',
    )
    paket = models.ForeignKey(
        PaketSoal, on_delete=models.PROTECT, related_name='sesi',
        verbose_name='Paket Soal',
    )
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='BERLANGSUNG',
    )
    urutan_soal = models.JSONField(
        'Urutan Soal', default=list,
        help_text='Daftar id soal teracak untuk sesi ini.',
    )
    mulai_at = models.DateTimeField('Mulai', default=timezone.now)
    batas_waktu = models.DateTimeField('Batas Waktu')
    selesai_at = models.DateTimeField('Selesai', null=True, blank=True)
    nilai = models.DecimalField(
        'Nilai', max_digits=5, decimal_places=2, null=True, blank=True,
    )
    lulus = models.BooleanField('Lulus', null=True, blank=True)
    # Anti-cheating ringan: berapa kali kandidat meninggalkan halaman ujian.
    pindah_fokus = models.PositiveSmallIntegerField('Pindah Fokus', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sesi Ujian'
        verbose_name_plural = 'Sesi Ujian'
        ordering = ['-mulai_at']
        indexes = [
            models.Index(fields=['lamaran', 'status'], name='sdm_sesi_ujian_idx'),
        ]

    def __str__(self):
        return f'Sesi {self.paket.nama} — {self.get_status_display()}'

    def sisa_detik(self):
        """Remaining seconds; never negative, and zero once the deadline passed."""
        if self.status != 'BERLANGSUNG':
            return 0
        delta = (self.batas_waktu - timezone.now()).total_seconds()
        return max(0, int(delta))

    def is_kedaluwarsa(self):
        return (
            self.status == 'BERLANGSUNG'
            and timezone.now() >= self.batas_waktu
        )


class JawabanUjian(models.Model):
    """One answer recorded for one question in one session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sesi = models.ForeignKey(
        SesiUjian, on_delete=models.CASCADE, related_name='jawaban',
        verbose_name='Sesi',
    )
    soal = models.ForeignKey(
        Soal, on_delete=models.PROTECT, related_name='jawaban',
        verbose_name='Soal',
    )
    jawaban = models.CharField(
        'Jawaban', max_length=1, blank=True,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')],
    )
    dijawab_at = models.DateTimeField('Dijawab', auto_now=True)

    class Meta:
        verbose_name = 'Jawaban Ujian'
        verbose_name_plural = 'Jawaban Ujian'
        ordering = ['soal__nomor']
        constraints = [
            models.UniqueConstraint(
                fields=['sesi', 'soal'], name='sdm_jawaban_sesi_soal_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.soal_id} → {self.jawaban or "—"}'
