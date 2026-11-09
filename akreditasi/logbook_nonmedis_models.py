"""Logbook Harian Non-Medis untuk seluruh unit kerja (ARIMA).

Berbeda dari ``logbook_models.py`` (medis IGD/Ranap yang merekap angka seksi-I
dari EMR), modul ini mencatat aktivitas harian **per pegawai per unit kerja**,
tanpa tarikan EMR. Fokusnya: checklist kepatuhan SOP/validasi/target, uraian
aktivitas layanan, identifikasi risiko operasional beserta mitigasi, dan
lampiran bukti yang terautolink ke Elemen Penilaian (EP) akreditasi.

Isian murni manual karena hal yang dicatat memang tidak ada di EMR: uraian
tugas administratif, kendala layanan, dan bukti kerja non-klinis.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from .models import StandardItem, UnitKerja


# ---------------------------------------------------------------------------
# 1. Konstanta
# ---------------------------------------------------------------------------

SHIFT_CHOICES = [
    ('', '—'),
    ('PAGI', 'Pagi (07.00–14.00)'),
    ('SIANG', 'Siang (14.00–21.00)'),
    ('MALAM', 'Malam (21.00–07.00)'),
]

STATUS_CHOICES = [
    ('DRAF', 'Draf'),
    ('DISETUJUI', 'Disetujui Kepala Unit'),
]

# Checklist kepatuhan umum yang berlaku untuk seluruh unit kerja non-medis.
# Bentuk tuple: (kunci, no_urut, parameter).
CHECKLIST_UMUM = [
    ('SOP', 1, 'Kesesuaian Prosedur Layanan dengan SOP'),
    ('VALIDASI', 2, 'Validasi Data / Identifikasi Pasien / Pengunjung'),
    ('TARGET', 3, 'Evaluasi Ketercapaian Target Harian'),
]


def checklist_template():
    """Daftar checklist umum (dapat diperluas per unit di masa depan)."""
    return CHECKLIST_UMUM


# ---------------------------------------------------------------------------
# 2. LogbookNonMedis — satu entri per pegawai + tanggal + unit
# ---------------------------------------------------------------------------

class LogbookNonMedis(models.Model):
    unit = models.ForeignKey(UnitKerja, on_delete=models.PROTECT,
                             related_name='logbook_nonmedis', verbose_name='Unit Kerja')
    pegawai = models.ForeignKey('sdm.Pegawai', on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='logbook_nonmedis',
                                verbose_name='Pelaksana / Pegawai')
    pelaksana_nama = models.CharField('Nama Pelaksana', max_length=150, blank=True)
    tanggal = models.DateField('Hari, Tanggal')
    shift = models.CharField('Shift', max_length=6, choices=SHIFT_CHOICES, blank=True, default='')

    fokus_ep = models.ForeignKey(StandardItem, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='logbook_nonmedis',
                                 verbose_name='Fokus EP Akreditasi (Autolink)')
    fokus_ep_teks = models.CharField('Fokus EP (Teks Bebas)', max_length=120, blank=True)

    uraian_aktivitas = models.TextField('Uraian Aktivitas / Layanan', blank=True)
    target_harian = models.CharField('Evaluasi Ketercapaian Target Harian', max_length=250, blank=True)
    risiko_identifikasi = models.TextField('Identifikasi Potensi Risiko', blank=True)
    risiko_mitigasi = models.TextField('Rencana Mitigasi / Penanganan', blank=True)

    status = models.CharField('Status', max_length=12, choices=STATUS_CHOICES, default='DRAF')

    dibuat_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='logbook_nonmedis_dibuat')
    disetujui_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='logbook_nonmedis_disetujui')
    disetujui_pada = models.DateTimeField('Disetujui Pada', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Logbook Harian Non-Medis'
        verbose_name_plural = 'Logbook Harian Non-Medis'
        ordering = ['-tanggal', 'unit__name']
        constraints = [
            models.UniqueConstraint(fields=['unit', 'pegawai', 'tanggal'],
                                    name='logbook_nonmedis_unik_harian'),
        ]

    def __str__(self):
        pelaksana = self.pegawai.nama_lengkap if self.pegawai_id else (self.pelaksana_nama or '—')
        return f'{self.unit.name} — {pelaksana} — {self.tanggal:%d/%m/%Y}'

    # ── Status ────────────────────────────────────────────────────────────
    @property
    def boleh_ubah(self):
        return self.status == 'DRAF'

    @property
    def terkunci(self):
        return self.status == 'DISETUJUI'

    # ── Checklist ─────────────────────────────────────────────────────────
    def ensure_checklist(self):
        """Buat baris checklist yang belum ada. Idempoten."""
        dibuat = 0
        for kunci, no_urut, parameter in checklist_template():
            _, baru = ChecklistNonMedis.objects.get_or_create(
                logbook=self, kunci=kunci,
                defaults={'no_urut': no_urut, 'parameter': parameter})
            if baru:
                dibuat += 1
        return dibuat


# ---------------------------------------------------------------------------
# 3. ChecklistNonMedis — butir kepatuhan per entri
# ---------------------------------------------------------------------------

class ChecklistNonMedis(models.Model):
    STATUS_CHOICES = [
        ('TERLAKSANA', 'Terlaksana'),
        ('TIDAK', 'Tidak Terlaksana'),
        ('NA', 'Tidak Berlaku'),
    ]

    logbook = models.ForeignKey(LogbookNonMedis, on_delete=models.CASCADE, related_name='checklist')
    kunci = models.CharField('Kunci Butir', max_length=40)
    no_urut = models.PositiveSmallIntegerField('No. Urut', default=1)
    parameter = models.CharField('Parameter yang Dinilai', max_length=250)
    status = models.CharField('Status', max_length=12, choices=STATUS_CHOICES, default='TERLAKSANA')
    keterangan = models.TextField('Keterangan / Temuan', blank=True)

    class Meta:
        verbose_name = 'Checklist Logbook Non-Medis'
        verbose_name_plural = 'Checklist Logbook Non-Medis'
        ordering = ['no_urut']
        constraints = [
            models.UniqueConstraint(fields=['logbook', 'kunci'],
                                    name='logbook_nonmedis_checklist_unik'),
        ]

    def __str__(self):
        return f'{self.kunci} — {self.parameter[:50]}'


# ---------------------------------------------------------------------------
# 4. BuktiNonMedis — lampiran berkas bukti audit
# ---------------------------------------------------------------------------

def _path_bukti_nonmedis(instance, filename):
    return f'logbook-nonmedis/{instance.logbook_id}/{filename}'


class BuktiNonMedis(models.Model):
    logbook = models.ForeignKey(LogbookNonMedis, on_delete=models.CASCADE, related_name='bukti')
    judul = models.CharField('Judul Berkas', max_length=200)
    berkas = models.FileField('Berkas', upload_to=_path_bukti_nonmedis)
    ukuran = models.CharField('Ukuran', max_length=20, blank=True)
    diunggah_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bukti Logbook Non-Medis'
        verbose_name_plural = 'Bukti Logbook Non-Medis'
        ordering = ['-created_at']

    def __str__(self):
        return self.judul
