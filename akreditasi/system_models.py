"""
Konfigurasi Sistem Terpusat — Singleton model untuk semua parameter
customizable RS (ambang kelulusan, risiko, KPS, branding, survey freeze).
"""
from django.db import models


class SystemConfig(models.Model):
    THEME_CHOICES = [
        ('teal', 'Teal Medis (Default RS MonsisKami)'),
        ('blue', 'Hospital Royal Blue'),
        ('emerald', 'Emerald Green Health'),
        ('navy', 'Dark Navy Slate'),
    ]

    # --- Standar Ambang Kelulusan KARS (%) ---
    threshold_paripurna = models.PositiveSmallIntegerField('Minimal Paripurna (%)', default=80)
    threshold_utama = models.PositiveSmallIntegerField('Minimal Utama (%)', default=70)
    threshold_madya = models.PositiveSmallIntegerField('Minimal Madya (%)', default=60)
    threshold_dasar = models.PositiveSmallIntegerField('Minimal Dasar (%)', default=20)

    # --- Mode Survei & Keamanan ---
    survey_freeze_mode = models.BooleanField(
        'Mode Kunci Survei (Read-Only Freeze)',
        default=False,
        help_text='Saat aktif, hanya Super Admin yang bisa mengedit. Seluruh staf & pokja beralih ke Mode Baca Saja.'
    )
    survey_freeze_message = models.CharField(
        'Pesan Banner Mode Survei',
        max_length=255,
        default='Sistem sedang dalam Mode Survei Akreditasi Lapangan. Penambahan/perubahan dokumen dinonaktifkan sementara.'
    )

    # --- Kredensial Nakes (KPS) ---
    kps_alert_days = models.PositiveIntegerField('Peringatan Expired STR/SIP (Hari)', default=90)
    allow_nakes_self_upload = models.BooleanField('Izinkan Nakes Unggah Dokumen Mandiri', default=True)

    # --- Berkas Bukti RDWOS ---
    max_upload_size_mb = models.PositiveIntegerField('Batas Maksimal Berkas (MB)', default=15)
    allowed_extensions = models.CharField('Ekstensi Berkas Diizinkan', max_length=150, default='pdf,docx,xlsx,jpg,png,jpeg')

    # --- Matriks Risiko & Insiden ---
    risk_threshold_sangat_tinggi = models.PositiveSmallIntegerField('Skor Sangat Tinggi (Merah)', default=20)
    risk_threshold_tinggi = models.PositiveSmallIntegerField('Skor Tinggi (Oranye)', default=15)
    risk_threshold_sedang = models.PositiveSmallIntegerField('Skor Sedang (Kuning)', default=10)
    risk_threshold_rendah = models.PositiveSmallIntegerField('Skor Rendah (Hijau)', default=5)

    # --- Tema & Branding ---
    theme_color = models.CharField('Warna Tema Sistem', max_length=20, choices=THEME_CHOICES, default='teal')
    kop_surat_text = models.TextField(
        'Teks Kop Surat Resmi', blank=True,
        default='PEMERINTAH DAERAH / YAYASAN KESEHATAN\nRS MONSISKAMI (TIPE B)\nJl. Kesehatan No. 1, Jakarta'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Konfigurasi Sistem'
        verbose_name_plural = 'Konfigurasi Sistem'

    def __str__(self):
        return f"Konfigurasi Sistem RS (Tema: {self.theme_color}, Freeze: {self.survey_freeze_mode})"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
