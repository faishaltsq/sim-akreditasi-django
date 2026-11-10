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

from .models import StandardItem, UnitKerja, active_framework


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
# 1b. Helper autolink Fokus EP akreditasi
# ---------------------------------------------------------------------------

def ep_kandidat(unit):
    """Kandidat ``StandardItem`` yang relevan untuk satu unit kerja.

    Menyaring katalog EP framework aktif memakai ``UnitKerja.standar_terkait``
    (JSONField ``{"TKRS": ["TKRS 1", ...]}``). Tanpa pemetaan, hasil kosong —
    petugas tetap bisa mengetik kode EP bebas (``fokus_ep_teks``).
    """
    if unit is None:
        return StandardItem.objects.none()
    pemetaan = unit.standar_terkait or {}
    if not isinstance(pemetaan, dict) or not pemetaan:
        return StandardItem.objects.none()

    qs = StandardItem.objects.filter(category__framework=active_framework())
    filter_q = None
    for kode_pokja, substandar_list in pemetaan.items():
        q_pokja = models.Q(category__code=kode_pokja)
        if substandar_list:
            q_pokja &= models.Q(sub_standard__in=substandar_list)
        filter_q = q_pokja if filter_q is None else (filter_q | q_pokja)
    if filter_q is None:
        return StandardItem.objects.none()
    return qs.filter(filter_q).select_related('category').order_by('category__order', 'order', 'code')


def resolve_fokus_ep(kode):
    """Temukan ``StandardItem`` dari kode EP (mis. ``'TKRS 1 EP a'``).

    Pencocokan dibatasi ke framework aktif supaya kode edisi lama tidak
    menunjuk EP yang sudah dicabut. Kode tak dikenal → ``None``.
    """
    kode = (kode or '').strip()
    if not kode:
        return None
    return StandardItem.objects.filter(
        category__framework=active_framework(), code__iexact=kode,
    ).select_related('category').first()


def resolve_ep_aktivitas(master=None, nama='', uraian=''):
    """Rekomendasikan string kode EP STARKES berdasarkan master aktivitas atau keyword teks."""
    if master and getattr(master, 'ep_rekomendasi', None):
        return master.ep_rekomendasi.strip()

    combined = f'{nama} {uraian}'.lower()
    if not combined.strip():
        return ''

    # Kata kunci spesifik dan padanannya
    if any(k in combined for k in ['mahasiswa', 'magang', 'praktik klinik', 'pembimbing klinik', 'ci ']):
        return 'IPKP 1 / IPKP 2 / IPKP 3 / KPS 8'
    if any(k in combined for k in ['penelitian', 'riset', 'ethical clearance', 'responden', 'studi kasus']):
        return 'IPKP 3 / TKRS 9'
    if any(k in combined for k in ['bhd', 'ppi', 'k3rs', 'apar', 'mandatory', 'pelatihan wajib']):
        return 'KPS 8 / SKP / PPI / MFK'
    if any(k in combined for k in ['jam pelatihan', 'training hours', 'matriks kompetensi', '20 jpl', 'jpl']):
        return 'KPS 8.1 / TKRS 9'
    if any(k in combined for k in ['orientasi', 'pegawai baru', 'peserta didik']):
        return 'KPS 8 / TKRS 9'
    if any(k in combined for k in ['kak', 'tor', 'iht', 'in-house training']):
        return 'KPS 8 / TKRS 9'
    if any(k in combined for k in ['eksternal', 'seminar', 'workshop luar']):
        return 'KPS 8 / KPS 8.1'
    if any(k in combined for k in ['evaluasi pasca', 'pre-test', 'post-test', 'umpan balik', 'efektivitas']):
        return 'KPS 8.1'
    if any(k in combined for k in ['arsip', 'digitalisasi', 'dokumen akreditasi', 'repository', 'repositori']):
        return 'KPS 8 / TKRS 9 / MRMIK'
    if any(k in combined for k in ['sosialisasi', 'sop baru', 'kebijakan baru', 'regulasi baru']):
        return 'TKRS 9 / KPS 8'
    if any(k in combined for k in ['rapat pimpinan', 'direksi', 'manajemen']):
        return 'TKRS 9'
    if any(k in combined for k in ['rapat koordinasi', 'antar unit', 'internal']):
        return 'TKRS 9'
    if 'rapat' in combined or 'workshop' in combined or 'fgd' in combined:
        return 'KPS 8'

    return ''


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
    jam_mulai = models.TimeField('Jam Mulai Dinas', null=True, blank=True)
    jam_selesai = models.TimeField('Jam Selesai Dinas', null=True, blank=True)
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


# ---------------------------------------------------------------------------
# 5. MasterAktivitasNonMedis — Katalog Aktivitas Terstandar (Diklat, SDM, dll.)
# ---------------------------------------------------------------------------

class MasterAktivitasNonMedis(models.Model):
    kode = models.CharField('Kode Aktivitas', max_length=30, unique=True, db_index=True)
    kategori_unit = models.CharField('Kategori Unit', max_length=50, default='DIKLAT', db_index=True)
    nama = models.CharField('Nama Aktivitas', max_length=200)
    deskripsi = models.TextField('Detail / Penjelasan Operasional Standar', blank=True)
    ep_rekomendasi = models.CharField('Rekomendasi EP STARKES', max_length=120, blank=True)
    standar_terkait = models.JSONField('Standar Terkait (List)', default=list, blank=True)
    urutan = models.PositiveSmallIntegerField('Urutan', default=1)
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Master Aktivitas Non-Medis'
        verbose_name_plural = 'Master Aktivitas Non-Medis'
        ordering = ['kategori_unit', 'urutan', 'kode']

    def __str__(self):
        return f'{self.kode} — {self.nama}'


# ---------------------------------------------------------------------------
# 6. AktivitasNonMedis — Baris Rincian Aktivitas Harian Logbook
# ---------------------------------------------------------------------------

def _path_bukti_aktivitas(instance, filename):
    return f'logbook-nonmedis/{instance.logbook_id}/aktivitas/{filename}'


class AktivitasNonMedis(models.Model):
    logbook = models.ForeignKey(LogbookNonMedis, on_delete=models.CASCADE, related_name='aktivitas_list')
    master = models.ForeignKey(MasterAktivitasNonMedis, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='aktivitas_logbook')
    urutan = models.PositiveSmallIntegerField('No. Urut', default=1)
    jam_mulai = models.TimeField('Jam Mulai', null=True, blank=True)
    jam_selesai = models.TimeField('Jam Selesai', null=True, blank=True)
    nama_aktivitas = models.CharField('Nama Aktivitas', max_length=250)
    detail_uraian = models.TextField('Detail Aktivitas / Uraian Bebas', blank=True)
    ep_starkes = models.CharField('Kesesuaian EP STARKES', max_length=120, blank=True)
    pelaksana_nama = models.CharField('Nama Staf / Pelaksana', max_length=150, blank=True)
    nama_bukti = models.CharField('Nama Bukti Dokumen', max_length=200, blank=True)
    dokumen_bukti = models.FileField('Dokumen Bukti', upload_to=_path_bukti_aktivitas, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Aktivitas Harian Non-Medis'
        verbose_name_plural = 'Aktivitas Harian Non-Medis'
        ordering = ['urutan', 'jam_mulai', 'id']

    def __str__(self):
        return f'{self.logbook} #{self.urutan} — {self.nama_aktivitas}'

    @property
    def waktu_display(self):
        if self.jam_mulai and self.jam_selesai:
            return f"{self.jam_mulai.strftime('%H.%M')} - {self.jam_selesai.strftime('%H.%M')}"
        elif self.jam_mulai:
            return f"{self.jam_mulai.strftime('%H.%M')}"
        return ""

    @property
    def durasi_jam(self):
        if not self.jam_mulai or not self.jam_selesai:
            return 0.0
        t1 = self.jam_mulai.hour + self.jam_mulai.minute / 60.0
        t2 = self.jam_selesai.hour + self.jam_selesai.minute / 60.0
        diff = t2 - t1
        return max(0.0, round(diff, 2))
