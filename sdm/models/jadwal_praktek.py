"""Model Jadwal Praktek Dokter untuk modul Human Capital.

Memisahkan pola jadwal mingguan (rutin) dari jadwal operasional harian,
mengakomodasi cuti/izin dokter beserta penggantinya, mencatat tindak lanjut
pasien terdampak, dan menyimpan jejak audit append-only untuk keperluan
evaluasi mutu serta survei akreditasi (STARKES 2024 — HPK, KPS, TKRS).
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class JadwalPraktekRutin(models.Model):
    """Pola jadwal mingguan tetap per dokter pada satu unit/poliklinik."""

    HARI_CHOICES = [
        (0, 'Senin'), (1, 'Selasa'), (2, 'Rabu'), (3, 'Kamis'),
        (4, 'Jumat'), (5, 'Sabtu'), (6, 'Minggu'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dokter = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT,
        related_name='jadwal_rutin', verbose_name='Dokter',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='jadwal_praktek_rutin', verbose_name='Unit / Poliklinik',
    )
    ruang_praktek = models.CharField('Ruang Praktek', max_length=100, blank=True)
    hari = models.IntegerField('Hari', choices=HARI_CHOICES)
    jam_mulai = models.TimeField('Jam Mulai')
    jam_selesai = models.TimeField('Jam Selesai')
    durasi_per_pasien_menit = models.PositiveIntegerField(
        'Durasi per Pasien (Menit)', default=15,
    )
    kuota_jkn = models.PositiveIntegerField('Kuota JKN / BPJS', default=20)
    kuota_non_jkn = models.PositiveIntegerField('Kuota Non-JKN / Umum', default=10)
    batas_daftar_menit = models.PositiveIntegerField(
        'Batas Daftar Sebelum Selesai (Menit)', default=60,
        help_text='Pendaftaran ditutup N menit sebelum jam selesai.',
    )
    is_active = models.BooleanField('Aktif', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jadwal_rutin_created',
        verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Jadwal Praktek Rutin'
        verbose_name_plural = 'Jadwal Praktek Rutin'
        ordering = ['dokter__nama_lengkap', 'hari', 'jam_mulai']
        indexes = [
            models.Index(
                fields=['dokter', 'hari', 'is_active'],
                name='sdm_jp_rutin_dr_hari_idx',
            ),
            models.Index(
                fields=['unit_kerja', 'hari', 'is_active'],
                name='sdm_jp_rutin_unit_hari_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(jam_selesai__gt=models.F('jam_mulai')),
                name='sdm_jp_rutin_jam_valid',
            ),
        ]

    @property
    def kuota_total(self):
        return self.kuota_jkn + self.kuota_non_jkn

    @property
    def hari_label(self):
        return dict(self.HARI_CHOICES).get(self.hari, '?')

    def clean(self):
        super().clean()
        if self.jam_mulai and self.jam_selesai and self.jam_selesai <= self.jam_mulai:
            raise ValidationError({
                'jam_selesai': 'Jam selesai harus setelah jam mulai.'
            })

    def __str__(self):
        return (
            f'{self.dokter} — {self.hari_label} '
            f'{self.jam_mulai.strftime("%H:%M")}-{self.jam_selesai.strftime("%H:%M")}'
        )


class JadwalPraktekHarian(models.Model):
    """Jadwal efektif per tanggal; acuan operasional pendaftaran dan antrean."""

    STATUS_CHOICES = [
        ('AKTIF', 'Aktif'),
        ('MUNDUR', 'Mundur / Tunda'),
        ('DIGANTIKAN', 'Digantikan'),
        ('BATAL', 'Batal / Libur'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jadwal_rutin = models.ForeignKey(
        JadwalPraktekRutin, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jadwal_harian',
        verbose_name='Jadwal Rutin Acuan',
    )
    tanggal = models.DateField('Tanggal')
    dokter_rencana = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT,
        related_name='jadwal_harian_rencana', verbose_name='Dokter Rencana',
    )
    dokter_aktual = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jadwal_harian_aktual',
        verbose_name='Dokter Aktual',
    )
    dokter_pengganti = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jadwal_harian_pengganti',
        verbose_name='Dokter Pengganti',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='jadwal_praktek_harian', verbose_name='Unit / Poliklinik',
    )
    jam_mulai_rencana = models.TimeField('Jam Mulai Rencana')
    jam_selesai_rencana = models.TimeField('Jam Selesai Rencana')
    jam_mulai_aktual = models.TimeField('Jam Mulai Aktual', null=True, blank=True)
    kuota_jkn = models.PositiveIntegerField('Kuota JKN', default=20)
    kuota_non_jkn = models.PositiveIntegerField('Kuota Non-JKN', default=10)
    terpakai_jkn = models.PositiveIntegerField('Terpakai JKN', default=0)
    terpakai_non_jkn = models.PositiveIntegerField('Terpakai Non-JKN', default=0)
    status_sesi = models.CharField(
        'Status Sesi', max_length=12, choices=STATUS_CHOICES, default='AKTIF',
    )
    alasan_perubahan = models.TextField('Alasan Perubahan', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Jadwal Praktek Harian'
        verbose_name_plural = 'Jadwal Praktek Harian'
        ordering = ['tanggal', 'jam_mulai_rencana']
        indexes = [
            models.Index(
                fields=['tanggal', 'unit_kerja', 'status_sesi'],
                name='sdm_jp_harian_tgl_idx',
            ),
            models.Index(
                fields=['dokter_rencana', 'tanggal'],
                name='sdm_jp_harian_dr_tgl_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['jadwal_rutin', 'tanggal'],
                condition=Q(jadwal_rutin__isnull=False),
                name='sdm_jp_harian_rutin_tgl_uniq',
            ),
        ]

    @property
    def kuota_total(self):
        return self.kuota_jkn + self.kuota_non_jkn

    @property
    def terpakai_total(self):
        return self.terpakai_jkn + self.terpakai_non_jkn

    @property
    def sisa_kuota(self):
        return max(0, self.kuota_total - self.terpakai_total)

    @property
    def keterlambatan_menit(self):
        """Selisih jam mulai aktual terhadap rencana, dalam menit (>= 0)."""
        if not self.jam_mulai_aktual or not self.jam_mulai_rencana:
            return None
        from datetime import date, datetime
        rencana = datetime.combine(date.min, self.jam_mulai_rencana)
        aktual = datetime.combine(date.min, self.jam_mulai_aktual)
        return max(0, int((aktual - rencana).total_seconds() // 60))

    @property
    def dokter_efektif(self):
        return self.dokter_pengganti or self.dokter_aktual or self.dokter_rencana

    def __str__(self):
        return f'{self.dokter_rencana} — {self.tanggal} @ {self.unit_kerja}'


class PengajuanIzinDokter(models.Model):
    """Pengajuan cuti/diklat/dinas luar/sakit yang mengunci slot jadwal."""

    JENIS_CHOICES = [
        ('CUTI', 'Cuti Tahunan'),
        ('DIKLAT', 'Diklat / Seminar'),
        ('DINAS_LUAR', 'Dinas Luar'),
        ('SAKIT', 'Sakit'),
        ('MENDESAK', 'Keperluan Mendesak'),
    ]
    STATUS_CHOICES = [
        ('MENUNGGU', 'Menunggu Persetujuan'),
        ('DISETUJUI', 'Disetujui'),
        ('DITOLAK', 'Ditolak'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dokter = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT,
        related_name='izin_dokter', verbose_name='Dokter',
    )
    jenis = models.CharField(
        'Jenis Ketidakhadiran', max_length=12, choices=JENIS_CHOICES,
    )
    tanggal_mulai = models.DateField('Tanggal Mulai')
    tanggal_selesai = models.DateField('Tanggal Selesai')
    dokter_pengganti = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pengganti_izin',
        verbose_name='Usulan Dokter Pengganti',
    )
    status = models.CharField(
        'Status', max_length=10, choices=STATUS_CHOICES, default='MENUNGGU',
    )
    catatan = models.TextField('Catatan', blank=True)
    disetujui_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='izin_dokter_approved',
        verbose_name='Disetujui Oleh',
    )
    disetujui_pada = models.DateTimeField('Waktu Persetujuan', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengajuan Izin Dokter'
        verbose_name_plural = 'Pengajuan Izin Dokter'
        ordering = ['-tanggal_mulai', '-pk']
        indexes = [
            models.Index(
                fields=['dokter', 'status'], name='sdm_jp_izin_dr_status_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(tanggal_selesai__gte=models.F('tanggal_mulai')),
                name='sdm_jp_izin_tgl_valid',
            ),
        ]

    def clean(self):
        super().clean()
        if self.dokter_pengganti_id and self.dokter_id:
            if self.dokter_pengganti_id == self.dokter_id:
                raise ValidationError({
                    'dokter_pengganti': 'Dokter pengganti tidak boleh sama dengan dokter yang izin.'
                })

    def __str__(self):
        return (
            f'{self.dokter} — {self.get_jenis_display()} '
            f'({self.tanggal_mulai} s/d {self.tanggal_selesai})'
        )


class TindakLanjutPasienJadwal(models.Model):
    """Daftar pasien terdaftar pada sesi yang berubah/batal dan status tindak lanjutnya."""

    STATUS_CHOICES = [
        ('BELUM', 'Belum Dihubungi'),
        ('DIALIHKAN', 'Dialihkan ke Dokter Pengganti'),
        ('RESCHEDULE', 'Dijadwalkan Ulang'),
        ('BATAL', 'Dibatalkan Pasien'),
        ('TERKONFIRMASI', 'Terkonfirmasi'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jadwal_harian = models.ForeignKey(
        JadwalPraktekHarian, on_delete=models.CASCADE,
        related_name='tindak_lanjut_pasien', verbose_name='Jadwal Harian',
    )
    nama_pasien = models.CharField('Nama Pasien', max_length=200)
    nomor_rm = models.CharField('Nomor Rekam Medis', max_length=50, blank=True)
    no_telepon = models.CharField('No. Telepon', max_length=30, blank=True)
    status = models.CharField(
        'Status Konfirmasi', max_length=15, choices=STATUS_CHOICES, default='BELUM',
    )
    catatan = models.TextField('Catatan Petugas', blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tindak_lanjut_jadwal_updated',
        verbose_name='Diperbarui Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tindak Lanjut Pasien Jadwal'
        verbose_name_plural = 'Tindak Lanjut Pasien Jadwal'
        ordering = ['jadwal_harian__tanggal', 'created_at']

    def __str__(self):
        return f'{self.nama_pasien} — {self.get_status_display()}'


class LogAuditJadwal(models.Model):
    """Jejak audit append-only atas setiap perubahan jadwal dan penggantian dokter."""

    JENIS_CHOICES = [
        ('BUAT', 'Jadwal Dibuat'),
        ('UBAH', 'Jadwal Diubah'),
        ('BATAL', 'Jadwal Dibatalkan'),
        ('GANTI_DOKTER', 'Dokter Diganti'),
        ('CATAT_JAM', 'Jam Aktual Dicatat'),
        ('ESKALASI', 'Eskalasi ke Risk Register'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jadwal_harian = models.ForeignKey(
        JadwalPraktekHarian, on_delete=models.CASCADE,
        related_name='audit_logs', verbose_name='Jadwal Harian',
    )
    waktu_aksi = models.DateTimeField('Waktu Aksi', default=timezone.now)
    pengguna = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_jadwal_created',
        verbose_name='Pelaku',
    )
    jenis_aksi = models.CharField('Jenis Aksi', max_length=15, choices=JENIS_CHOICES)
    ringkasan = models.TextField('Ringkasan Perubahan')
    snapshot_sebelum = models.JSONField('Data Sebelum', default=dict, blank=True)
    snapshot_sesudah = models.JSONField('Data Sesudah', default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log Audit Jadwal'
        verbose_name_plural = 'Log Audit Jadwal'
        ordering = ['-waktu_aksi', '-pk']
        indexes = [
            models.Index(
                fields=['jadwal_harian', '-waktu_aksi'],
                name='sdm_jp_audit_jadwal_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Log audit jadwal bersifat immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Log audit jadwal tidak dapat dihapus.')

    def __str__(self):
        return f'{self.get_jenis_aksi_display()} — {self.waktu_aksi:%d-%m-%Y %H:%M}'
