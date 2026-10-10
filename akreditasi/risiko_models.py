"""
Fase 2 — Manajemen Risiko PDCA + AI
Fase 5 — Insiden Anonim, Indikator Mutu Prioritas (IMP)
"""
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import UnitKerja, StandardItem


# ---------------------------------------------------------------------------
# 1. RisikoUnit — manajemen risiko per unit (PDCA)
# ---------------------------------------------------------------------------

class RisikoUnit(models.Model):
    PERIODE_CHOICES = [
        ('TRIWULAN_1', 'Triwulan I (Jan–Mar)'),
        ('TRIWULAN_2', 'Triwulan II (Apr–Jun)'),
        ('TRIWULAN_3', 'Triwulan III (Jul–Sep)'),
        ('TRIWULAN_4', 'Triwulan IV (Okt–Des)'),
        ('TAHUNAN', 'Tahunan'),
    ]

    KATEGORI_CHOICES = [
        ('KLINIS',               'Risiko Klinis (Clinical Risk)'),
        ('OPERASIONAL',          'Risiko Operasional (Operational Risk)'),
        ('FINANSIAL',            'Risiko Finansial (Financial Risk)'),
        ('REPUTASI',             'Risiko Reputasi (Reputational Risk)'),
        ('HUKUM_KEPATUHAN',      'Risiko Hukum & Kepatuhan (Legal & Compliance)'),
        ('FASILITAS_LINGKUNGAN', 'Risiko Fasilitas, B3 & Lingkungan (Facility & Env.)'),
        # backward compatibility for existing records
        ('MANAJERIAL',           'Risiko Manajerial (Legacy)'),
    ]

    STRATEGI_CHOICES = [
        ('HINDARI',  'Hindari (Avoid)'),
        ('KURANGI',  'Kurangi (Reduce)'),
        ('TRANSFER', 'Transfer'),
        ('TERIMA',   'Terima (Accept)'),
    ]

    STATUS_CHOICES = [
        ('IDENTIFIKASI', 'Identifikasi'),
        ('PLAN',         'Plan'),
        ('DO',           'Do'),
        ('EVALUASI',     'Evaluasi/Check'),
        ('SELESAI',      'Selesai/Act'),
        ('ACCEPTED',     'Diterima (Accepted Risk)'),
    ]

    # Section E — Hiliran Metode Evaluasi Mendalam (STARKES PMKP 7 & 8)
    METODE_EVALUASI_CHOICES = [
        ('STANDAR', 'Standar Pemantauan PDCA'),
        ('FMEA',    'FMEA — Failure Mode and Effects Analysis (Proaktif)'),
        ('RCA',     'RCA — Root Cause Analysis (Reaktif)'),
    ]

    DAMPAK_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]

    unit             = models.ForeignKey(UnitKerja, on_delete=models.CASCADE, verbose_name='Unit Kerja')
    tahun            = models.IntegerField('Tahun', default=2026)
    periode          = models.CharField('Periode', max_length=12, choices=PERIODE_CHOICES)
    kategori_risiko  = models.CharField('Kategori Risiko', max_length=30, choices=KATEGORI_CHOICES)
    jenis_risiko     = models.TextField('Jenis Risiko')

    # Standar 5.15 — identifikasi risiko: masalah dan data pendukung
    masalah          = models.TextField('Masalah', blank=True, default='')
    data_pendukung   = models.TextField('Data / Bukti Pendukung', blank=True, default='')

    deskripsi_risiko = models.TextField('Deskripsi Risiko')

    dampak           = models.IntegerField('Dampak (1–5)', validators=DAMPAK_VALIDATORS)
    probabilitas     = models.IntegerField('Probabilitas (1–5)', validators=DAMPAK_VALIDATORS)

    strategi_mitigasi = models.CharField('Strategi Mitigasi', max_length=10, choices=STRATEGI_CHOICES)
    rencana_aksi      = models.TextField('Rencana Aksi')
    pj_mitigasi       = models.CharField('PJ Mitigasi', max_length=150)
    biaya_mitigasi    = models.DecimalField('Estimasi Biaya Mitigasi (Rp)', max_digits=14, decimal_places=2, default=0)
    target_selesai    = models.DateField('Target Selesai', null=True, blank=True)
    bukti_pelaksanaan = models.TextField('Bukti Pelaksanaan', blank=True)

    dampak_residual      = models.IntegerField('Dampak Residual (1–5)', null=True, blank=True, validators=DAMPAK_VALIDATORS)
    probabilitas_residual = models.IntegerField('Probabilitas Residual (1–5)', null=True, blank=True, validators=DAMPAK_VALIDATORS)

    # Integrasi Indikator Mutu (Section C dokumen permintaan user)
    indikator_mutu_terkait   = models.ForeignKey(
        'IndikatorMutu', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='risiko_terkait', verbose_name='Indikator Mutu Terkait'
    )
    target_capaian_indikator = models.DecimalField(
        'Target Capaian Indikator (%)', max_digits=5, decimal_places=2,
        null=True, blank=True
    )

    status     = models.CharField('Status PDCA', max_length=12, choices=STATUS_CHOICES, default='IDENTIFIKASI')

    # ── Section E: Hiliran Metode Evaluasi Mendalam (FMEA & RCA) ──────────
    metode_evaluasi       = models.CharField(
        'Metode Evaluasi Mendalam', max_length=10,
        choices=METODE_EVALUASI_CHOICES, default='STANDAR',
        help_text='Standar PDCA, FMEA (proaktif), atau RCA (reaktif).'
    )
    tim_evaluasi          = models.CharField('Tim Evaluasi / Investigasi', max_length=255, blank=True, default='')
    failure_mode_fmea     = models.TextField('Mode Kegagalan & Efek Potensial (FMEA)', blank=True, default='')
    akar_masalah_rca      = models.TextField('Analisis Akar Masalah (RCA 5-Whys / Fishbone)', blank=True, default='')
    tindakan_korektif_rca = models.TextField('Rencana Tindakan Korektif & Solusi Permanen', blank=True, default='')
    rpn_fmea              = models.IntegerField('RPN — Risk Priority Number (FMEA)', null=True, blank=True)
    tanggal_evaluasi      = models.DateField('Tanggal Evaluasi / Investigasi', null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='risiko_dibuat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Risiko Unit'
        verbose_name_plural = 'Risiko Unit'
        ordering            = ['-tahun', 'periode']

    def __str__(self):
        return f"[{self.unit}] {self.jenis_risiko} ({self.periode} {self.tahun})"

    @property
    def jenis_risiko_list(self):
        """Mengembalikan list dari jenis risiko jika ada multiple (dipisahkan newline, titik-koma, atau koma)."""
        if not self.jenis_risiko:
            return []
        import re
        # Pecah berdasarkan newline, titik-koma, atau bullet point
        items = re.split(r'[\r\n;]+', self.jenis_risiko)
        result = []
        for it in items:
            cleaned = re.sub(r'^\s*[-•*\d.]+\s*', '', it).strip()
            if cleaned:
                result.append(cleaned)
        return result if result else [self.jenis_risiko.strip()]

    @property
    def skor_inherent(self):
        return self.dampak * self.probabilitas

    @property
    def rpn_calc(self):
        """RPN FMEA: Severity × Occurrence × Detection (approx dari dampak × probabilitas × 5).
        Jika rpn_fmea diisi manual, pakai nilai manual."""
        if self.rpn_fmea:
            return self.rpn_fmea
        if self.metode_evaluasi == 'FMEA':
            return self.dampak * self.probabilitas * 5
        return None

    @property
    def metode_evaluasi_badge(self):
        return {
            'STANDAR': ('secondary', 'bi-arrow-repeat', 'Standar PDCA'),
            'FMEA':    ('warning text-dark', 'bi-diagram-3-fill', 'FMEA Proaktif'),
            'RCA':     ('danger', 'bi-search', 'RCA Reaktif'),
        }.get(self.metode_evaluasi, ('secondary', 'bi-arrow-repeat', 'Standar PDCA'))

    @property
    def is_fmea(self):
        return self.metode_evaluasi == 'FMEA'

    @property
    def is_rca(self):
        return self.metode_evaluasi == 'RCA'

    @property
    def skor_residual(self):
        if self.dampak_residual is not None and self.probabilitas_residual is not None:
            return self.dampak_residual * self.probabilitas_residual
        return None

    @property
    def risk_level(self):
        from .system_models import SystemConfig
        cfg = SystemConfig.get_solo()
        skor = self.skor_inherent
        if skor >= cfg.risk_threshold_sangat_tinggi:
            return 'SANGAT_TINGGI'
        if skor >= cfg.risk_threshold_tinggi:
            return 'TINGGI'
        if skor >= cfg.risk_threshold_sedang:
            return 'SEDANG'
        if skor >= cfg.risk_threshold_rendah:
            return 'RENDAH'
        return 'SANGAT_RENDAH'

    @property
    def risk_color(self):
        return {
            'SANGAT_TINGGI': '#dc2626',
            'TINGGI':        '#ea580c',
            'SEDANG':        '#ca8a04',
            'RENDAH':        '#16a34a',
            'SANGAT_RENDAH': '#64748b',
        }[self.risk_level]


# ---------------------------------------------------------------------------
# 2. TindakLanjutRisiko — detail aksi DO
# ---------------------------------------------------------------------------

class TindakLanjutRisiko(models.Model):
    STATUS_AKSI_CHOICES = [
        ('BELUM',  'Belum Dimulai'),
        ('SEDANG', 'Sedang Berjalan'),
        ('SELESAI', 'Selesai'),
    ]

    risiko         = models.ForeignKey(RisikoUnit, on_delete=models.CASCADE, related_name='tindak_lanjut')
    urutan         = models.IntegerField('Urutan Aksi')
    aksi           = models.CharField('Aksi', max_length=500)
    status_aksi    = models.CharField('Status Aksi', max_length=10, choices=STATUS_AKSI_CHOICES, default='BELUM')
    tanggal_mulai  = models.DateField('Tanggal Mulai', null=True, blank=True)
    tanggal_selesai = models.DateField('Tanggal Selesai', null=True, blank=True)
    bukti_upload   = models.FileField('Bukti Upload', upload_to='risiko/bukti/', null=True, blank=True)
    catatan        = models.TextField('Catatan', blank=True)

    class Meta:
        verbose_name        = 'Tindak Lanjut Risiko'
        verbose_name_plural = 'Tindak Lanjut Risiko'
        ordering            = ['risiko', 'urutan']

    def __str__(self):
        return f"{self.risiko} — Aksi #{self.urutan}: {self.aksi[:60]}"


# ---------------------------------------------------------------------------
# 3. InsidenKeselamatan — laporan insiden anonim
# ---------------------------------------------------------------------------

class InsidenKeselamatan(models.Model):
    JENIS_CHOICES = [
        ('KNC',           'KNC — Kejadian Nyaris Cedera'),
        ('KTD',           'KTD — Kejadian Tidak Diharapkan'),
        ('KTC',           'KTC — Kejadian Tidak Cedera'),
        ('SENTINEL',      'Kejadian Sentinel'),
        ('KEJADIAN_LAIN', 'Kejadian Lain'),
    ]

    KEPARAHAN_CHOICES = [
        ('TIDAK_CEDERA', 'Tidak Cedera'),
        ('MINOR',        'Minor'),
        ('MODERAT',      'Moderat'),
        ('MAYOR',        'Mayor'),
        ('SENTINEL',     'Sentinel'),
    ]

    STATUS_INVESTIGASI_CHOICES = [
        ('DILAPORKAN',  'Dilaporkan'),
        ('VERIFIKASI',  'Verifikasi'),
        ('INVESTIGASI', 'Investigasi'),
        ('SELESAI',     'Selesai'),
    ]

    unit               = models.ForeignKey(UnitKerja, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Unit Terkait')
    tanggal_kejadian   = models.DateField('Tanggal Kejadian')
    waktu_kejadian     = models.TimeField('Waktu Kejadian', null=True, blank=True)
    jenis_insiden      = models.CharField('Jenis Insiden', max_length=15, choices=JENIS_CHOICES)
    tingkat_keparahan  = models.CharField('Tingkat Keparahan', max_length=15, choices=KEPARAHAN_CHOICES)
    lokasi_kejadian    = models.CharField('Lokasi Kejadian', max_length=200)
    deskripsi_kejadian = models.TextField('Deskripsi Kejadian')
    tindakan_segera    = models.TextField('Tindakan Segera', blank=True)
    pasien_terpapar    = models.BooleanField('Pasien Terpapar', default=False)
    pelapor_anonim     = models.BooleanField('Pelapor Anonim', default=True)

    status_investigasi = models.CharField('Status Investigasi', max_length=12, choices=STATUS_INVESTIGASI_CHOICES, default='DILAPORKAN')
    pj_investigasi     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='insiden_investigasi', verbose_name='PJ Investigasi')
    rca_dilakukan      = models.BooleanField('RCA Dilakukan', default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Insiden Keselamatan'
        verbose_name_plural = 'Insiden Keselamatan'
        ordering            = ['-tanggal_kejadian']

    def __str__(self):
        return f"[{self.jenis_insiden}] {self.tanggal_kejadian} — {self.lokasi_kejadian}"


# ---------------------------------------------------------------------------
# 4. IndikatorMutu — IMP-RS & IMP-Unit
# ---------------------------------------------------------------------------

class IndikatorMutu(models.Model):
    JENIS_CHOICES = [
        ('IMP_RS',    'IMP Rumah Sakit'),
        ('IMP_UNIT',  'IMP Unit'),
        ('NASIONAL',  'Indikator Nasional Mutu'),
        ('SNI',       'Standar Nasional Indonesia'),
    ]

    DIMENSI_CHOICES = [
        ('EFEKTIF',           'Efektif'),
        ('EFISIEN',           'Efisien'),
        ('AKSESIBEL',         'Aksesibel'),
        ('AMAN',              'Aman'),
        ('BERPUSAT_PASIEN',   'Berpusat pada Pasien'),
        ('TEPAT_WAKTU',       'Tepat Waktu'),
        ('ADIL',              'Adil'),
    ]

    nama_indikator = models.CharField('Nama Indikator', max_length=300)
    kode_indikator = models.CharField('Kode Indikator', max_length=50, unique=True)
    unit           = models.ForeignKey(UnitKerja, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Unit Kerja')
    jenis          = models.CharField('Jenis Indikator', max_length=10, choices=JENIS_CHOICES)
    dimensi_mutu   = models.CharField('Dimensi Mutu', max_length=20, choices=DIMENSI_CHOICES)
    numerator      = models.CharField('Numerator', max_length=300)
    denominator    = models.CharField('Denominator', max_length=300)
    target_nilai   = models.DecimalField('Target Nilai', max_digits=5, decimal_places=2)
    satuan         = models.CharField('Satuan', max_length=20, default='%')
    ep_terkait     = models.ForeignKey(StandardItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='indikator_mutu', verbose_name='EP Terkait')
    rencana_aksi   = models.TextField('Rencana Aksi (Preset)', blank=True, default='')
    pj             = models.CharField('Penanggung Jawab', max_length=200, blank=True, default='')
    aktif          = models.BooleanField('Aktif', default=True)

    class Meta:
        verbose_name        = 'Indikator Mutu'
        verbose_name_plural = 'Indikator Mutu'
        ordering            = ['jenis', 'kode_indikator']

    def __str__(self):
        return f"[{self.kode_indikator}] {self.nama_indikator}"


# ---------------------------------------------------------------------------
# 5. CatatanIndikator — pencatatan hasil IMP per periode
# ---------------------------------------------------------------------------

class CatatanIndikator(models.Model):
    BULAN_VALIDATORS = [MinValueValidator(1), MaxValueValidator(12)]

    indikator        = models.ForeignKey(IndikatorMutu, on_delete=models.CASCADE, related_name='catatan')
    bulan            = models.IntegerField('Bulan', validators=BULAN_VALIDATORS)
    tahun            = models.IntegerField('Tahun', default=2026)
    nilai_numerator  = models.DecimalField('Nilai Numerator', max_digits=10, decimal_places=2)
    nilai_denominator = models.DecimalField('Nilai Denominator', max_digits=10, decimal_places=2)
    catatan          = models.TextField('Catatan', blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Catatan Indikator'
        verbose_name_plural = 'Catatan Indikator'
        ordering            = ['-tahun', '-bulan']
        unique_together     = [('indikator', 'bulan', 'tahun')]

    def __str__(self):
        return f"{self.indikator.kode_indikator} — {self.bulan}/{self.tahun}"

    @property
    def nilai_capaian(self):
        if self.nilai_denominator and self.nilai_denominator > 0:
            return (self.nilai_numerator / self.nilai_denominator) * Decimal('100')
        return Decimal('0')


    @property
    def tercapai(self):
        return self.nilai_capaian >= self.indikator.target_nilai


# ── 6. Renstra RS Roadmap (Dynamic Admin CRUD) ────────────────────────────────

class RenstraRoadmap(models.Model):
    tahun = models.PositiveIntegerField('Tahun Renstra', unique=True, db_index=True)
    isu_strategis = models.CharField('Isu Strategis', max_length=200)
    sub_tema = models.CharField('Sub-Tema / Fokus Utama', max_length=250, blank=True)
    deskripsi = models.TextField('Deskripsi Rencana Strategis', blank=True)
    ikon = models.CharField('Class Bootstrap Icon', max_length=50, default='bi-flag',
                            help_text='Contoh: bi-cpu, bi-gear-wide-connected, bi-hospital, bi-tree, bi-trophy')
    warna_hex = models.CharField('Kode Warna Hex', max_length=20, default='#0d6efd',
                                 help_text='Contoh: #0d6efd, #6f42c1, #198754, #20c997, #fd7e14')
    urutan = models.PositiveSmallIntegerField('Urutan Tampil', default=1)
    aktif = models.BooleanField('Aktif Ditampilkan', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Roadmap Renstra Tahunan'
        verbose_name_plural = 'Roadmap Renstra RS (2026–2030)'
        ordering = ['urutan', 'tahun']

    def __str__(self):
        return f'Renstra {self.tahun} — {self.isu_strategis}'


class RenstraFokusItem(models.Model):
    roadmap = models.ForeignKey(RenstraRoadmap, on_delete=models.CASCADE, related_name='fokus_items')
    nomor = models.PositiveSmallIntegerField('Nomor Urut Fokus', default=1)
    nama_fokus = models.CharField('Nama Indikator / Program Fokus', max_length=255)
    indikator_mutu = models.ForeignKey('IndikatorMutu', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='renstra_fokus',
                                       help_text='Tautkan ke Master Indikator Mutu (opsional)')
    kode_ref = models.CharField('Kode Ref Cadangan', max_length=50, blank=True,
                                help_text='Contoh: IMP-RM-01, INM-08')
    target_label = models.CharField('Target Label Teks', max_length=100, default='100%')
    target_nilai = models.DecimalField('Nilai Target Numerik', max_digits=8, decimal_places=2, default=100.0)
    satuan = models.CharField('Satuan', max_length=30, default='%')
    unit_kerja_label = models.CharField('Unit Kerja Penanggung Jawab', max_length=150, blank=True)

    class Meta:
        verbose_name = 'Butir Fokus Indikator Renstra'
        verbose_name_plural = 'Butir Fokus Indikator Renstra'
        ordering = ['nomor']

    def __str__(self):
        return f'{self.roadmap.tahun} #{self.nomor}: {self.nama_fokus}'
