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
    passing_grade = models.DecimalField(
        'Passing Grade', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text='Nilai minimum lulus (0–100), ditetapkan komite; kosong jika belum ditetapkan.',
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


class JadwalWawancara(models.Model):
    """One interview slot for one application, with its panel of interviewers.

    A clash check runs against the same vacancy only: two different vacancies
    may legitimately reuse a time slot with different panels.
    """

    MODE_CHOICES = [
        ('LURING', 'Luring (tatap muka)'),
        ('DARING', 'Daring (video)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lamaran = models.OneToOneField(
        'sdm.Lamaran', on_delete=models.CASCADE, related_name='jadwal_wawancara',
        verbose_name='Lamaran',
    )
    waktu = models.DateTimeField('Waktu Wawancara')
    mode = models.CharField(
        'Mode', max_length=8, choices=MODE_CHOICES, default='LURING',
    )
    lokasi_tautan = models.CharField(
        'Lokasi / Tautan', max_length=300, blank=True,
        help_text='Ruang untuk luring, tautan video untuk daring.',
    )
    penguji = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='sdm_wawancara_penguji',
        blank=True, verbose_name='Penguji',
    )
    catatan = models.TextField('Catatan', blank=True)
    undangan_terkirim_at = models.DateTimeField(
        'Undangan Terkirim', null=True, blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_jadwal_wawancara_created', verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Jadwal Wawancara'
        verbose_name_plural = 'Jadwal Wawancara'
        ordering = ['waktu']

    def __str__(self):
        return f'Wawancara {self.lamaran_id} — {self.waktu:%d %b %Y %H:%M}'


class ScorecardWawancara(models.Model):
    """One interviewer's scored sheet for one interview.

    The document names five indicators; they are stored as explicit fields so a
    report can show which dimension was weak rather than only a single average.
    """
    JENIS_CHOICES = [('HRD', 'HRD'), ('USER', 'User / Komite')]


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jadwal = models.ForeignKey(
        JadwalWawancara, on_delete=models.CASCADE, related_name='scorecard',
        verbose_name='Jadwal',
    )
    penguji = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, related_name='sdm_scorecard',
        verbose_name='Penguji',
    )
    jenis = models.CharField(
        'Jenis Penguji', max_length=4, choices=JENIS_CHOICES, blank=True,
        default='',
    )
    kompetensi_teknis = models.DecimalField(
        'Kompetensi Teknis', max_digits=5, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    soft_skill = models.DecimalField(
        'Soft Skill', max_digits=5, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    ketahanan_beban_kerja = models.DecimalField(
        'Ketahanan Beban Kerja', max_digits=5, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    integritas = models.DecimalField(
        'Sikap / Integritas', max_digits=5, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    pemahaman_visi = models.DecimalField(
        'Pemahaman Visi-Misi & AIK', max_digits=5, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    catatan = models.TextField('Catatan Penguji', blank=True)
    dinilai_at = models.DateTimeField('Dinilai', auto_now=True)

    INDIKATOR = (
        'kompetensi_teknis', 'soft_skill', 'ketahanan_beban_kerja',
        'integritas', 'pemahaman_visi',
    )

    class Meta:
        verbose_name = 'Scorecard Wawancara'
        verbose_name_plural = 'Scorecard Wawancara'
        ordering = ['-dinilai_at']
        constraints = [
            models.UniqueConstraint(
                fields=['jadwal', 'penguji'],
                name='sdm_scorecard_jadwal_penguji_uniq',
            ),
        ]

    def __str__(self):
        return f'Scorecard {self.jadwal_id} — {self.penguji_id}'

    def rata_rata(self):
        """Mean of the indicators that were actually filled in."""
        nilai = [
            getattr(self, nama) for nama in self.INDIKATOR
            if getattr(self, nama, None) is not None
        ]
        if not nilai:
            return None
        return (sum(nilai) / len(nilai)).quantize(Decimal('0.01'))
