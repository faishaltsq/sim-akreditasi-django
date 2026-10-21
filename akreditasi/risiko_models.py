"""
Fase 2 — Manajemen Risiko PDCA + AI
Fase 5 — Insiden Anonim, Indikator Mutu Prioritas (IMP)
"""
from decimal import Decimal
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
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
    bukti_data_pendukung = models.FileField(
        'Bukti / Lampiran Data Pendukung',
        upload_to='risiko/bukti_data_pendukung/',
        null=True, blank=True,
        help_text='Upload file bukti/lampiran pendukung masalah (PDF, gambar, Excel, dsb.)'
    )
    tujuan           = models.TextField(
        'Tujuan Pengendalian Risiko', blank=True, default='',
        help_text='Tujuan mitigasi dan sasaran keselamatan/mutu klinis yang ingin dicapai'
    )

    deskripsi_risiko = models.TextField('Deskripsi Risiko')

    dampak           = models.IntegerField('Dampak (1–5)', validators=DAMPAK_VALIDATORS)
    probabilitas     = models.IntegerField('Probabilitas (1–5)', validators=DAMPAK_VALIDATORS)

    # Section B — Pengendalian yang Sudah Ada (Existing Control)
    pengendalian_ada = models.TextField('Pengendalian yang Sudah Ada (Existing Control)', blank=True, default='')

    strategi_mitigasi = models.CharField('Strategi Mitigasi', max_length=10, choices=STRATEGI_CHOICES)
    rencana_aksi      = models.TextField('Rencana Aksi')
    pj_mitigasi       = models.CharField('PJ Mitigasi', max_length=150)
    biaya_mitigasi    = models.DecimalField('Estimasi Biaya Mitigasi (Rp)', max_digits=14, decimal_places=2, default=0)
    target_selesai    = models.DateField('Target Selesai', null=True, blank=True)
    bukti_pelaksanaan = models.TextField('Bukti Pelaksanaan', blank=True)

    dampak_residual      = models.IntegerField('Dampak Residual (1–5)', null=True, blank=True, validators=DAMPAK_VALIDATORS)
    probabilitas_residual = models.IntegerField('Probabilitas Residual (1–5)', null=True, blank=True, validators=DAMPAK_VALIDATORS)
    deteksi_residual      = models.IntegerField('Deteksi Residu (1–5)', null=True, blank=True, validators=DAMPAK_VALIDATORS)
    rpn_residual          = models.IntegerField('RPN Residu (FMEA)', null=True, blank=True)

    # Integrasi Indikator Mutu (Section C dokumen permintaan user)
    indikator_mutu_terkait   = models.ForeignKey(
        'IndikatorMutu', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='risiko_terkait', verbose_name='Indikator Mutu Terkait'
    )
    target_capaian_indikator = models.DecimalField(
        'Target Capaian Indikator (%)', max_digits=5, decimal_places=2,
        null=True, blank=True
    )
    # Polaritas untuk risiko yang indikatornya belum ditautkan ke master.
    # Kosong = ikut master (atau MIN bila master tidak ada). Hanya dipakai
    # bila target_capaian_indikator diisi manual tanpa indikator_mutu_terkait.
    arah_capaian = models.CharField(
        'Arah Target Capaian', max_length=3, blank=True, default='',
        choices=[('', 'Ikuti Master'), ('MIN', '≥ Target (makin besar makin baik)'),
                 ('MAX', '≤ Target (makin kecil makin baik)')],
        help_text='Hanya berlaku bila indikator mutu belum ditautkan ke master.'
    )

    status     = models.CharField('Status PDCA', max_length=12, choices=STATUS_CHOICES, default='IDENTIFIKASI')

    # ── Section C/E: Hiliran Metode Evaluasi Mendalam (FMEA & RCA) ──────────
    metode_evaluasi       = models.CharField(
        'Metode Evaluasi Mendalam', max_length=10,
        choices=METODE_EVALUASI_CHOICES, default='STANDAR',
        help_text='Standar PDCA, FMEA (proaktif), atau RCA (reaktif).'
    )
    tim_evaluasi          = models.CharField('Tim Evaluasi / Investigasi', max_length=255, blank=True, default='')
    deteksi_fmea          = models.IntegerField('Tingkat Deteksi / Detection (1–5)', null=True, blank=True, validators=DAMPAK_VALIDATORS)
    failure_mode_fmea     = models.TextField('Mode Kegagalan & Efek Potensial (FMEA)', blank=True, default='')
    akar_masalah_rca      = models.TextField('Analisis Akar Masalah (RCA 5-Whys / Fishbone)', blank=True, default='')
    tindakan_korektif_rca = models.TextField('Rencana Tindakan Korektif & Solusi Permanen', blank=True, default='')
    rpn_fmea              = models.IntegerField('RPN — Risk Priority Number (FMEA)', null=True, blank=True)
    tanggal_evaluasi      = models.DateField('Tanggal Evaluasi / Investigasi', null=True, blank=True)

    # ── Section G: Monitoring, Evaluasi, RCA Fishbone & RTL ───────────────
    STATUS_PELAKSANAAN_CHOICES = [
        ('DILAKUKAN',       'Dilakukan'),
        ('SEBAGIAN',        'Dilakukan Sebagian'),
        ('TIDAK_DILAKUKAN', 'Tidak Dilakukan'),
    ]

    STATUS_RTL_CHOICES = [
        ('BELUM',   'Belum Dimulai'),
        ('PROSES',  'Dalam Proses'),
        ('SELESAI', 'Selesai'),
    ]

    JENIS_DOKUMEN_BUKTI_CHOICES = [
        ('LAPORAN_BULANAN', 'Laporan Bulanan Unit'),
        ('LAPORAN_INSIDEN', 'Laporan Insiden Keselamatan (IKP)'),
        ('FORM_AUDIT',      'Form Audit / Monitoring Kepatuhan'),
        ('FOTO_BUKTI',      'Foto Bukti Implementasi / Dokumentasi'),
        ('SOP_KEBIJAKAN',   'SOP / Kebijakan Terkait'),
        ('LAINNYA',         'Dokumen Pendukung Lainnya'),
    ]

    # Capaian Indikator Mutu
    capaian_nilai         = models.DecimalField('Nilai Capaian Indikator (%)', max_digits=5, decimal_places=2, null=True, blank=True)
    bukti_capaian         = models.FileField('Bukti Dokumen Capaian', upload_to='risiko/bukti_capaian/', null=True, blank=True)
    jenis_dokumen_capaian = models.CharField(
        'Jenis Dokumen Bukti Capaian',
        max_length=50,
        blank=True,
        default='',
        choices=JENIS_DOKUMEN_BUKTI_CHOICES,
        help_text='Kategori/klasifikasi bukti dokumen capaian indikator mutu.'
    )
    evaluasi_capaian      = models.TextField('Evaluasi Capaian Indikator Mutu', blank=True, default='')

    # Pelaksanaan Tindakan Rencana (Do)
    status_pelaksanaan    = models.CharField('Status Pelaksanaan Tindakan', max_length=20, choices=STATUS_PELAKSANAAN_CHOICES, default='DILAKUKAN')

    # Root Cause Analysis (RCA) Terstruktur — Fishbone / 5-Whys
    rca_ulang             = models.TextField('RCA Ulang / Investigasi Lanjutan', blank=True, default='')
    rca_fishbone          = models.JSONField('Analisis RCA Fishbone Terstruktur', default=dict, blank=True)

    # Rencana Tindak Lanjut (RTL)
    rencana_tindak_lanjut = models.TextField('Rencana Tindak Lanjut (RTL)', blank=True, default='')
    pj_rtl                = models.CharField('PJ Tindak Lanjut (RTL)', max_length=150, blank=True, default='')
    deadline_rtl          = models.DateField('Target Waktu / Tenggat RTL', null=True, blank=True)
    status_rtl            = models.CharField('Status RTL', max_length=15, choices=STATUS_RTL_CHOICES, default='BELUM')
    bukti_rtl             = models.FileField('Bukti Dokumen RTL', upload_to='risiko/bukti_rtl/', null=True, blank=True)

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
    def tujuan_display(self):
        """Kembalikan tujuan pengendalian risiko atau fallback cerdas berbasis kategori."""
        if self.tujuan and self.tujuan.strip():
            return self.tujuan.strip()
        kat = self.get_kategori_risiko_display() if hasattr(self, 'get_kategori_risiko_display') else 'Klinis'
        unit_name = self.unit.name if self.unit else 'unit kerja'
        return f"Mengendalikan dan memitigasi {kat.lower()} guna mencegah insiden keselamatan pasien serta memastikan kepatuhan terhadap standar pelayanan di {unit_name}."

    @property
    def capaian_evaluasi(self):
        """Satu sumber kebenaran untuk (target, arah, status, gap) capaian risiko.

        Urutan target: target rencana (diisi di tahap Plan) -> target master
        indikator -> None. Arah: arah_capaian manual -> master -> 'MIN'.
        Return dict; nilai None berarti belum bisa dievaluasi.
        """
        ind = self.indikator_mutu_terkait
        arah = (self.arah_capaian
                or (getattr(ind, 'arah_target', '') if ind else '')
                or 'MIN')
        satuan = (getattr(ind, 'satuan', '') if ind else '') or '%'

        if self.target_capaian_indikator is not None:
            target, sumber = float(self.target_capaian_indikator), 'rencana'
        elif ind is not None and ind.target_nilai is not None:
            target, sumber = float(ind.target_nilai), 'master'
        else:
            target, sumber = None, 'tidak_ada'

        # Capaian: nilai manual yang diketik di form evaluasi selalu menang;
        # bila kosong dan indikator sudah tertaut, jatuh ke agregat bulanan
        # (CatatanIndikator) sehingga halaman evaluasi tidak pernah "kosong"
        # selama unit sudah mengisi Input Capaian.
        capaian = float(self.capaian_nilai) if self.capaian_nilai is not None else None
        capaian_sumber = 'manual' if capaian is not None else None
        if capaian is None and ind is not None:
            capaian = ind.agregat_capaian(self.tahun)['capaian']
            if capaian is not None:
                capaian_sumber = 'catatan'
        if capaian is None or target is None:
            return {'target': target, 'arah': arah, 'satuan': satuan,
                    'sumber': sumber, 'capaian': capaian,
                    'capaian_sumber': capaian_sumber,
                    'tercapai': None, 'gap': None, 'gap_abs': None}

        tercapai = capaian <= target if arah == 'MAX' else capaian >= target
        # Gap selalu bertanda "seberapa baik": positif = margin aman,
        # negatif = seberapa jauh di luar target. Simetris untuk kedua arah.
        gap = (target - capaian) if arah == 'MAX' else (capaian - target)
        return {'target': target, 'arah': arah, 'satuan': satuan,
                'sumber': sumber, 'capaian': capaian,
                'capaian_sumber': capaian_sumber, 'tercapai': tercapai,
                'gap': round(gap, 2), 'gap_abs': round(abs(gap), 2)}

    @property
    def capaian_persen_display(self):
        """Format tampilan persen capaian indikator (manual, lalu agregat bulanan)."""
        val = self.capaian_evaluasi['capaian']
        if val is None:
            return "—"
        return f"{val:.1f}%"

    @property
    def capaian_status_label(self):
        """Label status singkat dari resolver; None bila belum bisa dievaluasi."""
        ev = self.capaian_evaluasi
        if ev['tercapai'] is None:
            return None
        return 'Tercapai' if ev['tercapai'] else 'Belum Tercapai'

    @property
    def linked_indikator(self):
        """Master IndikatorMutu yang ditautkan ke risiko ini (atau None).

        Tipis di atas FK indikator_mutu_terkait: template bisa guard + URL-build
        dalam satu ekspresi ({% if r.linked_indikator %}...pk...). Jika plan
        access-matrix (4.07) nanti ganti sumber linking, cukup properti ini.
        """
        return self.indikator_mutu_terkait

    @property
    def rca_fishbone_items(self):
        """Kembalikan list of (label, text) untuk fishbone yang tidak kosong."""
        if not isinstance(self.rca_fishbone, dict):
            return []
        labels = {
            'manpower': 'Manpower (SDM)',
            'process': 'Process / Method (Metode & Alur)',
            'material': 'Material (Sarana & Bahan)',
            'machine': 'Machine / Equipment (Alat & Fasilitas)',
            'environment': 'Environment / Behavior (Lingkungan & Budaya)',
            'system': 'System (Sistem & Kebijakan)',
        }
        res = []
        for k, v in self.rca_fishbone.items():
            if v and str(v).strip():
                res.append({'key': k, 'label': labels.get(k, k.capitalize()), 'text': str(v).strip()})
        return res

    @property
    def status_rtl_badge_color(self):
        m = {'BELUM': 'secondary', 'PROSES': 'warning', 'SELESAI': 'success'}
        return m.get(self.status_rtl, 'secondary')

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
    def rencana_aksi_list(self):
        """Pecah rencana_aksi menjadi list of item terstruktur bernomor atau berpoin."""
        if not self.rencana_aksi:
            return []
        import re
        text = self.rencana_aksi.strip()
        num_pattern = r'(?:^|\s+)(?=\d+[\.\)]\s+)'
        parts = [p.strip() for p in re.split(num_pattern, text) if p.strip()]
        if len(parts) > 1 or re.match(r'^\d+[\.\)]\s+', text):
            res = []
            for p in parts:
                m = re.match(r'^(\d+)[\.\)]\s*(.*)', p, re.DOTALL)
                if m:
                    res.append({'urutan': int(m.group(1)), 'text': m.group(2).strip()})
                else:
                    res.append({'urutan': len(res) + 1, 'text': p.strip()})
            return res
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return [{'urutan': i + 1, 'text': re.sub(r'^[•\-\*]\s*', '', l).strip()} for i, l in enumerate(lines)]

    @property
    def skor_inherent(self):
        return self.dampak * self.probabilitas

    @property
    def rpn_calc(self):
        """RPN FMEA: Severity × Occurrence × Detection (S × O × D).
        Jika rpn_fmea diisi manual, pakai nilai manual."""
        if self.rpn_fmea:
            return self.rpn_fmea
        if self.metode_evaluasi == 'FMEA':
            d = self.deteksi_fmea or 1
            return self.dampak * self.probabilitas * d
        return None

    @property
    def rpn_residual_calc(self):
        """RPN Residu FMEA: S_residu × O_residu × D_residu."""
        if self.rpn_residual:
            return self.rpn_residual
        if self.metode_evaluasi == 'FMEA' and self.dampak_residual and self.probabilitas_residual:
            d = self.deteksi_residual or self.deteksi_fmea or 1
            return self.dampak_residual * self.probabilitas_residual * d
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
    def status_badge_color(self):
        m = {
            'IDENTIFIKASI': 'secondary',
            'PLAN': 'primary',
            'DO': 'warning text-dark',
            'EVALUASI': 'info text-dark',
            'SELESAI': 'success',
            'ACCEPTED': 'teal text-white',
        }
        return m.get(self.status, 'secondary')

    @property
    def status_pelaksanaan_badge_color(self):
        m = {
            'DILAKUKAN': 'success',
            'SEBAGIAN': 'warning text-dark',
            'TIDAK_DILAKUKAN': 'danger',
        }
        return m.get(self.status_pelaksanaan, 'secondary')

    @property
    def skor_awal(self):
        return self.dampak * self.probabilitas

    @property
    def skor_awal_color(self):
        s = self.skor_awal
        if s >= 20: return '#dc2626'
        if s >= 15: return '#ea580c'
        if s >= 10: return '#ca8a04'
        if s >= 5: return '#16a34a'
        return '#64748b'

    @property
    def skor_akhir(self):
        if self.dampak_residual and self.probabilitas_residual:
            return self.dampak_residual * self.probabilitas_residual
        return None

    @property
    def skor_akhir_color(self):
        s = self.skor_akhir
        if not s: return '#64748b'
        if s >= 20: return '#dc2626'
        if s >= 15: return '#ea580c'
        if s >= 10: return '#ca8a04'
        if s >= 5: return '#16a34a'
        return '#64748b'

    @property
    def skor_delta(self):
        if self.skor_akhir is not None:
            return self.skor_awal - self.skor_akhir
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

    # Spec pelaksanaan: tiap aksi mitigasi membawa bukti dokumen dan tautan ke
    # standar akreditasi (pokja) beserta EP yang dilayaninya. SET_NULL bukan
    # CASCADE — menghapus standar/EP tidak boleh menghapus riwayat tindakan RS;
    # tautan jadi usang dan template menampilkan '—', aksinya tetap ada.
    standar_terkait = models.ForeignKey(
        'akreditasi.Category', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tindak_lanjut_set', verbose_name='Standar Akreditasi Terkait')
    ep_terkait      = models.ForeignKey(
        'akreditasi.StandardItem', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tindak_lanjut_set', verbose_name='EP Terkait')

    class Meta:
        verbose_name        = 'Tindak Lanjut Risiko'
        verbose_name_plural = 'Tindak Lanjut Risiko'
        ordering            = ['risiko', 'urutan']

    def clean(self):
        """Konsistensi tautan + aturan bukti dokumen.

        View selalu menurunkan standar dari EP yang dipilih; keduanya terisi
        tapi berbeda kategori berarti halaman usang (stale) dan ditolak di
        sini, bukan 500 di server.
        """
        super().clean()
        if self.ep_terkait_id and self.standar_terkait_id:
            if self.ep_terkait.category_id != self.standar_terkait_id:
                raise ValidationError({
                    'ep_terkait': 'EP harus berasal dari standar yang dipilih.'})
        if self.status_aksi == 'SELESAI' and not self.bukti_upload:
            raise ValidationError({
                'bukti_upload': 'Pelaksanaan berstatus Selesai wajib punya bukti dokumen.'})

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
        ('KPC',           'KPC — Kejadian Pasien Cedera'),
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
# 4. IndikatorMutu — INM, IMRS, IMU (3-Tier Mutu)
# ---------------------------------------------------------------------------

class IndikatorMutu(models.Model):
    JENIS_CHOICES = [
        ('INM',       'Indikator Nasional Mutu (INM)'),
        ('IMRS',      'Indikator Mutu Rumah Sakit (IMRS)'),
        ('IMU',       'Indikator Mutu Unit (IMU)'),
        # legacy — backward-compatible, mapped via jenis_standar property
        ('IMP_RS',    'IMP Rumah Sakit (Legacy)'),
        ('IMP_UNIT',  'IMP Unit (Legacy)'),
        ('NASIONAL',  'Indikator Nasional Mutu (Legacy)'),
        ('SNI',       'Standar Nasional Indonesia'),
    ]

    ARAH_CHOICES = [
        ('MIN', 'Minimal — Capaian ≥ Target (higher is better)'),
        ('MAX', 'Maksimal — Capaian ≤ Target (lower is better)'),
    ]

    EP_SUMBER_CHOICES = [
        ('',       'Belum ditautkan'),
        ('MANUAL', 'Dipilih manual'),
        ('AI',     'Rekomendasi AI'),
        ('RULE',   'Auto (unit terkait)'),
        ('LEXICAL', 'Auto (kecocokan kata)'),
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
    # Tipe pengukuran: 'persen' → (N/D) × 100, validasi 0–100.
    # 'rate_absolut' → (N/D) × faktor_pengali, tanpa batas atas (per mil,
    # rerata, jumlah kasus). Lihat CatatanIndikator.nilai_capaian.
    TIPE_PENGUKURAN_CHOICES = [
        ('persen', 'Persentase (%)'),
        ('rate_absolut', 'Angka absolut / rate (per mil, rerata, jumlah kasus)'),
    ]
    FAKTOR_PENGALI_CHOICES = [
        (1, '× 1  (rerata / jumlah kasus)'),
        (100, '× 100  (persentase)'),
        (1000, '× 1000  (per mil ‰)'),
        (100000, '× 100.000  (per 100.000)'),
    ]
    tipe_pengukuran = models.CharField(
        'Tipe Pengukuran', max_length=15, choices=TIPE_PENGUKURAN_CHOICES,
        default='persen',
        help_text='persen → (N/D) × 100, validasi 0–100. rate_absolut → '
                  '(N/D) × faktor_pengali, tanpa batas atas.'
    )
    faktor_pengali = models.IntegerField(
        'Faktor Pengali', default=100, choices=FAKTOR_PENGALI_CHOICES,
        help_text='Pengali pada rumus capaian. Autoritatif untuk aritmetika; '
                  'kolom satuan hanya label tampilan dan tidak mengubah perhitungan.'
    )
    ep_terkait     = models.ForeignKey(StandardItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='indikator_mutu', verbose_name='EP Terkait')
    ep_sumber      = models.CharField(
        'Sumber Link EP', max_length=10, choices=EP_SUMBER_CHOICES,
        default='MANUAL', blank=True,
        help_text=('Bagaimana ep_terkait terisi. Nilai kosong berarti belum '
                   'ditautkan dan baris tetap terbuka untuk auto-sync; '
                   'MANUAL tidak pernah ditimpa.')
    )
    ep_skor        = models.DecimalField(
        'Skor Kecocokan EP', max_digits=5, decimal_places=4,
        null=True, blank=True,
    )
    rencana_aksi   = models.TextField('Rencana Aksi (Preset)', blank=True, default='')
    pj             = models.CharField('Penanggung Jawab', max_length=200, blank=True, default='')
    aktif          = models.BooleanField('Aktif', default=True)
    arah_target    = models.CharField(
        'Arah Target', max_length=3, choices=ARAH_CHOICES, default='MIN',
        help_text='MIN = capaian harus ≥ target (higher is better). MAX = capaian harus ≤ target (lower is better, e.g. waktu tunggu).'
    )
    sasaran_strategis = models.ForeignKey(
        'RenstraRoadmap', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='indikator_list', verbose_name='Sasaran Strategis (Renstra)',
        help_text='Hubungkan indikator ke Roadmap Renstra tahunan RS.'
    )
    inm_induk = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='realisasi_unit', verbose_name='INM Induk',
        help_text='Kosong = indikator ini INM kanonik. Terisi = realisasi INM tersebut di satu unit.'
    )

    class Meta:
        verbose_name        = 'Indikator Mutu'
        verbose_name_plural = 'Indikator Mutu'
        ordering            = ['jenis', 'kode_indikator']

    def __str__(self):
        return f"[{self.kode_indikator}] {self.nama_indikator}"

    @property
    def jenis_standar(self):
        """Normalize legacy jenis codes to canonical 3-tier: INM, IMRS, IMU."""
        mapping = {
            'NASIONAL': 'INM',
            'IMP_RS':   'IMRS',
            'IMP_UNIT': 'IMU',
        }
        return mapping.get(self.jenis, self.jenis)

    def agregat_capaian(self, tahun):
        """Agregat capaian satu tahun dari CatatanIndikator.

        Rasio Σnumerator / Σdenominator × faktor — bukan rerata persen bulanan,
        karena rerata menyetarakan bobot bulan ber-denominator kecil dengan
        bulan ber-denominator besar. Rumus identik dengan
        CatatanIndikator.nilai_capaian (lihat baris tipe_pengukuran/faktor_pengali).
        `capaian` None bila belum ada bulan dengan denominator > 0.
        """
        cache = getattr(self, '_agregat_cache', None)
        if cache is None:
            cache = self._agregat_cache = {}
        if tahun in cache:
            return cache[tahun]

        agg = self.catatan.filter(tahun=tahun, nilai_denominator__gt=0).aggregate(
            num=Sum('nilai_numerator'),
            den=Sum('nilai_denominator'),
            bulan_terisi=Count('id'),
        )
        num, den, bulan = agg['num'], agg['den'], agg['bulan_terisi'] or 0
        capaian = None
        if den is not None and den > 0:
            if self.tipe_pengukuran == 'persen':
                faktor = Decimal('100')
            else:
                faktor = Decimal(str(self.faktor_pengali or 100))
            capaian = round(float((num / den) * faktor), 2)

        hasil = {
            'tahun': tahun, 'num': num, 'den': den,
            'bulan_terisi': bulan, 'capaian': capaian,
        }
        cache[tahun] = hasil
        return hasil


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
    bukti_dokumen    = models.FileField('Dokumen Bukti Pendukung', upload_to='indikator_bukti/%Y/%m/',
                                        null=True, blank=True,
                                        help_text='Upload bukti pelaksanaan atau laporan capaian bulanan (PDF/DOCX/JPG/PNG)')
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
        if not self.nilai_denominator or self.nilai_denominator <= 0:
            return Decimal('0')
        ind = self.indikator
        if getattr(ind, 'tipe_pengukuran', 'persen') == 'persen':
            # persen selalu dari literal 100 — faktor_pengali kolom tidak
            # pernah mengubah aritmetika persentase.
            faktor = Decimal('100')
        else:
            faktor = Decimal(str(getattr(ind, 'faktor_pengali', 100) or 100))
        num = self.nilai_numerator
        den = self.nilai_denominator
        try:
            return (num / den) * faktor
        except TypeError:
            # nilai disimpan sebagai literal float/int (bukan Decimal) —
            # lewat Decimal(str(...)) agar hasil tetap presisi.
            return (Decimal(str(num)) / Decimal(str(den))) * faktor


    @property
    def tercapai(self):
        capaian = self.nilai_capaian
        target = self.indikator.target_nilai
        arah = getattr(self.indikator, 'arah_target', 'MIN')
        if arah == 'MAX':
            # Lower is better — capaian harus ≤ target
            return capaian <= target
        return capaian >= target


    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-trigger Risk Register draft when indicator misses target
        if not self.tercapai and self.indikator.unit_id:
            capaian = self.nilai_capaian
            target = self.indikator.target_nilai
            satuan = self.indikator.satuan or '%'
            arah = getattr(self.indikator, 'arah_target', 'MIN')
            arah_label = '≥' if arah == 'MIN' else '≤'
            # Idempotent: only create ONE draft per indicator per unit
            if not RisikoUnit.objects.filter(
                unit=self.indikator.unit,
                indikator_mutu_terkait=self.indikator,
            ).exists():
                RisikoUnit.objects.create(
                    unit=self.indikator.unit,
                    indikator_mutu_terkait=self.indikator,
                    tahun=self.tahun,
                    periode='TRIWULAN_1',
                    kategori_risiko='OPERASIONAL',
                    jenis_risiko='Risiko Kegagalan Mutu & Layanan',
                    masalah=(
                        f"Capaian {self.indikator.nama_indikator} di bawah target "
                        f"({capaian:.1f} {satuan} vs target {arah_label} {target} {satuan})"
                    ),
                    deskripsi_risiko=(
                        f"Indikator [{self.indikator.kode_indikator}] "
                        f"{self.indikator.nama_indikator} tidak mencapai target Renstra. "
                        f"Capaian: {capaian:.1f} {satuan} | Target: {arah_label} {target} {satuan}."
                    ),
                    dampak=3,
                    probabilitas=3,
                    strategi_mitigasi='KURANGI',
                    rencana_aksi=self.indikator.rencana_aksi or 'Lakukan analisis akar masalah (Fishbone/5-Why) dan susun PDCA RTL.',
                    pj_mitigasi=self.indikator.pj or 'Ka. Unit',
                    status='IDENTIFIKASI',
                )
        elif self.tercapai and self.indikator.ep_terkait_id:
            # Auto-tag: update QualityRecord for the linked EP when indicator achieved
            from akreditasi.models import QualityRecord  # lazy — prevents circular import
            try:
                qr = QualityRecord.objects.get(standard_item_id=self.indikator.ep_terkait_id)
                tag = (
                    f"[{self.indikator.kode_indikator}] {self.indikator.nama_indikator}: "
                    f"Tercapai ({self.nilai_capaian:.1f}{self.indikator.satuan or '%'}) "
                    f"Bulan {self.bulan}/{self.tahun}"
                )
                qr.quality_target = tag
                if qr.score == 0:
                    qr.score = 10  # auto-promote to full score only when previously unscored
                qr.save(update_fields=['quality_target', 'score'])
            except QualityRecord.DoesNotExist:
                pass  # no QualityRecord yet — don't create, let accreditation team do it


# ── 5b. InmUnitMapping — peta distribusi INM per unit ─────────────────────────

class InmUnitMapping(models.Model):
    """Pemetaan INM - unit yang berhak melihat/menginput (peta distribusi INM).

    Tabel kosong untuk sebuah unit berarti unit tersebut belum dipetakan ->
    perilaku lama dipertahankan (unit tetap melihat daftar penuh). Auto-hide
    hanya aktif untuk unit yang sudah punya baris di sini.
    """

    ROLE_KEPALA_UNIT = 'KEPALA_UNIT'
    ROLE_DPJP = 'DPJP'
    ROLE_CHOICES = [
        (ROLE_KEPALA_UNIT, 'Semua Kepala Unit / Ruangan'),
        (ROLE_DPJP, 'Semua Dokter DPJP'),
    ]

    indikator = models.ForeignKey(
        IndikatorMutu, on_delete=models.CASCADE, related_name='pemetaan_unit'
    )
    unit = models.ForeignKey(
        UnitKerja, on_delete=models.CASCADE, related_name='pemetaan_inm',
        null=True, blank=True,
        help_text='Kosong bila cakupan ditentukan oleh role_scope, bukan unit.'
    )
    role_scope = models.CharField(
        'Cakupan Role', max_length=20, choices=ROLE_CHOICES, blank=True, default='',
        help_text='Untuk INM seperti Fornas (semua DPJP) atau Komplain (semua Ka. Instalasi).'
    )
    is_pj = models.BooleanField('Unit PJ (Penanggung Jawab Utama)', default=False)
    boleh_input = models.BooleanField('Boleh Input Capaian', default=True)
    berlaku_mulai = models.DateField('Berlaku Mulai', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pemetaan INM — Unit'
        verbose_name_plural = 'Pemetaan INM — Unit'
        constraints = [
            models.UniqueConstraint(
                fields=['indikator', 'unit', 'role_scope'],
                name='uniq_inm_unit_role',
            ),
            models.CheckConstraint(
                condition=Q(unit__isnull=False) | ~Q(role_scope=''),
                name='inm_mapping_butuh_unit_atau_role',
            ),
        ]
        ordering = ['indikator_id', 'unit_id']

    def __str__(self):
        scope = self.unit.code if self.unit_id else f"role:{self.role_scope}"
        return f"{self.indikator.kode_indikator} -> {scope}"


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
    target_persen = models.DecimalField('Target Capaian Renstra (%)', max_digits=5, decimal_places=2, default=Decimal('80.00'),
                                         help_text='Target agregat capaian indikator Renstra tahunan (misal: 2026: 75%, 2027: 80%, dst.)')
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


# ---------------------------------------------------------------------------
# 7. Laporan Mutu — dokumen formal bulanan / semester / tahunan
# ---------------------------------------------------------------------------

class LaporanMutu(models.Model):
    """Header satu dokumen Laporan Capaian Indikator Mutu.

    Angka di dalamnya dibekukan saat pembuatan (lihat LaporanMutuBaris) agar
    dokumen yang sudah diverifikasi/disetujui tidak berubah sendiri ketika
    data bulan dikoreksi. Regenerasi hanya terjadi pada status DRAF.
    """
    JENIS_CHOICES = [
        ('BULANAN',  'Laporan Capaian Indikator Mutu Bulanan'),
        ('SEMESTER', 'Laporan Capaian Indikator Mutu Semester'),
        ('TAHUNAN',  'Laporan Capaian Indikator Mutu Tahunan'),
    ]
    SCOPE_CHOICES = [
        ('UNIT', 'Unit Kerja'),
        ('RS',   'Seluruh Rumah Sakit'),
    ]
    STATUS_CHOICES = [
        ('DRAF',          'Draf'),
        ('DIVERIFIKASI',  'Diverifikasi Kepala Unit'),
        ('DISETUJUI',     'Disetujui Komite Mutu'),
        ('TERBIT',        'Diterbitkan Direksi'),
    ]

    jenis              = models.CharField('Jenis Laporan', max_length=10, choices=JENIS_CHOICES)
    tahun              = models.PositiveIntegerField('Tahun Laporan', default=2026)
    bulan              = models.PositiveSmallIntegerField('Bulan', null=True, blank=True,
                         validators=[MinValueValidator(1), MaxValueValidator(12)],
                         help_text='Hanya untuk laporan bulanan')
    semester           = models.PositiveSmallIntegerField('Semester', null=True, blank=True,
                         validators=[MinValueValidator(1), MaxValueValidator(2)],
                         help_text='Hanya untuk laporan semester (1 = Jan–Jun, 2 = Jul–Des)')
    scope              = models.CharField('Cakupan', max_length=5, choices=SCOPE_CHOICES, default='UNIT')
    unit               = models.ForeignKey(UnitKerja, on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='laporan_mutu',
                         help_text='Kosong bila cakupan seluruh RS')
    nomor              = models.CharField('Nomor Dokumen', max_length=60, blank=True, default='')
    status             = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAF')
    pembuat            = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                         related_name='laporan_mutu_dibuat', verbose_name='Dibuat Oleh')
    dibuat_pada        = models.DateTimeField(auto_now_add=True)
    diverifikasi_oleh  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='laporan_mutu_diverifikasi', verbose_name='Diverifikasi Oleh')
    diverifikasi_pada  = models.DateTimeField(null=True, blank=True)
    disetujui_oleh     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='laporan_mutu_disetujui', verbose_name='Disetujui Oleh')
    disetujui_pada     = models.DateTimeField(null=True, blank=True)
    terbit_pada        = models.DateTimeField(null=True, blank=True)
    catatan_verifikasi = models.TextField('Catatan Verifikasi', blank=True, default='')

    class Meta:
        verbose_name        = 'Laporan Mutu'
        verbose_name_plural = 'Laporan Mutu'
        ordering            = ['-tahun', '-bulan', '-semester', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['jenis', 'tahun', 'semester', 'bulan', 'scope', 'unit'],
                name='uniq_laporan_mutu_periode',
                # Cakupan RS memakai unit=NULL; tanpa ini dua laporan RS untuk
                # periode yang sama dianggap berbeda (semantik standar NULL).
                nulls_distinct=False,
            ),
        ]

    def __str__(self):
        return f'{self.get_jenis_display()} — {self.periode_label} ({self.get_scope_display()})'

    @property
    def periode_label(self):
        """Label periode untuk judul dokumen, mis. 'Januari 2026' / 'Semester I 2026'."""
        if self.jenis == 'BULANAN':
            nama_bulan = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli',
                          'Agustus', 'September', 'Oktober', 'November', 'Desember']
            return f'{nama_bulan[self.bulan - 1]} {self.tahun}'
        if self.jenis == 'SEMESTER':
            return f'Semester {"I" if self.semester == 1 else "II"} {self.tahun}'
        return f'Tahun {self.tahun}'

    @property
    def batas_waktu(self):
        from .mutu_laporan import batas_waktu_laporan
        return batas_waktu_laporan(self.jenis, self.tahun, self.bulan, self.semester)

    @property
    def terlambat(self):
        from .mutu_laporan import terlambat_laporan
        return terlambat_laporan(self.jenis, self.tahun, self.bulan, self.semester)

    @property
    def sisa_hari(self):
        """Sisa hari sampai batas pelaporan; negatif = sudah lewat."""
        from .mutu_laporan import sisa_hari_laporan
        return sisa_hari_laporan(self.jenis, self.tahun, self.bulan, self.semester)

    @property
    def telat_hari(self):
        """Jumlah hari keterlambatan, 0 bila belum lewat batas."""
        return max(0, -self.sisa_hari)

    @property
    def boleh_ubah(self):
        """Hanya draf yang boleh diubah; laporan terverifikasi dibekukan."""
        return self.status == 'DRAF'

    def _nama_user(self, user):
        if user is None:
            return ''
        return (user.get_full_name() or user.username)

    @property
    def pembuat_nama(self):
        """Nama pembuat untuk tabel daftar/cetak (tidak pernah None)."""
        return self._nama_user(self.pembuat)

    @property
    def diverifikasi_oleh_nama(self):
        return self._nama_user(self.diverifikasi_oleh)

    @property
    def diverifikasi_jabatan(self):
        if self.diverifikasi_oleh is None:
            return ''
        prof = getattr(self.diverifikasi_oleh, 'profile', None)
        return (prof.jabatan if prof and prof.jabatan else '')

    @property
    def disetujui_oleh_nama(self):
        return self._nama_user(self.disetujui_oleh)

    @property
    def scope_label(self):
        """Nama cakupan yang terbaca di daftar: nama unit, atau seluruh RS."""
        return 'Seluruh Rumah Sakit' if self.scope == 'RS' else (
            self.unit.name if self.unit_id else 'Unit Kerja')

    @property
    def status_badge(self):
        """Kelas Bootstrap badge status, dipakai daftar & detail laporan."""
        return {
            'DRAF': 'bg-secondary',
            'DIVERIFIKASI': 'bg-info text-dark',
            'DISETUJUI': 'bg-primary',
            'TERBIT': 'bg-success',
        }.get(self.status, 'bg-secondary')

    def save(self, *args, **kwargs):
        """Satu laporan per periode per cakupan, di semua backend.

        UniqueConstraint(nulls_distinct=False) tidak dibuat di SQLite
        (models.W047) sehingga pengujian jalan dengan aturan yang sama dengan
        Postgres produksi: validasi dilakukan di sini, constraint database
        tetap dipertahankan sebagai lapis kedua.
        """
        dupes = LaporanMutu.objects.filter(
            jenis=self.jenis, tahun=self.tahun, semester=self.semester,
            bulan=self.bulan, scope=self.scope, unit=self.unit,
        )
        if self.pk:
            dupes = dupes.exclude(pk=self.pk)
        if dupes.exists():
            raise ValidationError({
                'jenis': (
                    f'{self.get_jenis_display()} untuk {self.periode_label} '
                    f'({self.get_scope_display()}) sudah ada.'
                ),
            })
        super().save(*args, **kwargs)


class LaporanMutuBaris(models.Model):
    """Satu baris = satu indikator, dengan angka yang dibekukan saat laporan dibuat.

    Kolom snapshot (kode..status_tercapai) adalah salinan apa adanya dari master
    indikator dan catatan bulanan. Indikator di-SET_NULL agar dokumen lama tetap
    terbaca walaupun indikator master dihapus.
    """
    VERIFIKASI_CHOICES = [
        ('BELUM',  'Belum Diverifikasi'),
        ('SETUJU', 'Sesuai'),
        ('REVISI', 'Perlu Revisi'),
    ]

    laporan           = models.ForeignKey(LaporanMutu, on_delete=models.CASCADE, related_name='baris')
    indikator         = models.ForeignKey(IndikatorMutu, on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='laporan_baris')
    # ── snapshot master ──
    urutan            = models.PositiveSmallIntegerField('Urutan', default=0)
    kode              = models.CharField('Kode Indikator', max_length=50)
    nama              = models.CharField('Nama Indikator', max_length=300)
    jenis             = models.CharField('Jenis Indikator', max_length=10)
    unit_nama         = models.CharField('Unit Kerja', max_length=150, blank=True, default='')
    # Deskripsi rumus dari master — bukan angka. Angka periode ada di
    # nilai_numerator / nilai_denominator di bawah.
    numerator         = models.CharField('Numerator', max_length=300, blank=True, default='')
    denominator       = models.CharField('Denominator', max_length=300, blank=True, default='')
    satuan            = models.CharField('Satuan', max_length=20, blank=True, default='%')
    arah              = models.CharField('Arah Target', max_length=3, default='MIN')
    target            = models.DecimalField('Target Nilai', max_digits=8, decimal_places=2, default=Decimal('0'))
    # ── snapshot angka periode ──
    nilai_numerator   = models.DecimalField('N Periode', max_digits=12, decimal_places=2,
                         null=True, blank=True)
    nilai_denominator = models.DecimalField('D Periode', max_digits=12, decimal_places=2,
                         null=True, blank=True)
    nilai_capaian     = models.DecimalField('Capaian', max_digits=10, decimal_places=2, null=True, blank=True)
    status_tercapai   = models.BooleanField('Tercapai', null=True, blank=True)
    bulan_terisi      = models.PositiveSmallIntegerField('Bulan Terisi', default=0)
    # ── analisis & tindak lanjut (diisi saat laporan berstatus draf) ──
    analisis          = models.TextField('Analisis PDSA', blank=True, default='')
    tindak_lanjut     = models.TextField('Tindak Lanjut', blank=True, default='')
    # ── verifikasi per baris (L4 — Kepala Unit) ──
    status_verifikasi = models.CharField(max_length=10, choices=VERIFIKASI_CHOICES, default='BELUM')
    verifikator       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='laporan_baris_diverifikasi')
    verifikasi_pada   = models.DateTimeField(null=True, blank=True)
    catatan_verifikasi = models.CharField('Catatan Verifikasi', max_length=300, blank=True, default='')

    class Meta:
        verbose_name        = 'Baris Laporan Mutu'
        verbose_name_plural = 'Baris Laporan Mutu'
        ordering            = ['urutan', 'kode']
        unique_together     = [('laporan', 'kode')]

    def __str__(self):
        return f'{self.laporan_id} — [{self.kode}] {self.nama[:60]}'


class LaporanMutuSeksi(models.Model):
    """Bagian naratif laporan (ringkasan eksekutif, kendala, BAB I–VI, kesimpulan).

    Kunci dipakai agar template bisa memilih bagian yang relevan per jenis laporan
    tanpa menambah kolom per BAB.
    """
    KUNCI_CHOICES = [
        ('RINGKASAN_EKSEKUTIF', 'Ringkasan Eksekutif'),
        ('KENDALA',             'Kendala dan Hambatan'),
        ('REKOMENDASI',         'Rekomendasi dan Upaya Perbaikan'),
        ('BAB_I',               'BAB I — Bagian Umum'),
        ('BAB_II',              'BAB II — Analisa dan Evaluasi Capaian Kinerja Pelayanan Rumah Sakit'),
        ('BAB_III',             'BAB III — Analisa dan Evaluasi Program Kerja'),
        ('BAB_IV',              'BAB IV — Analisa dan Evaluasi Komponen Biaya'),
        ('BAB_V',               'BAB V — Rekap Kejadian Ikp, Klaim, dan Risiko'),
        ('BAB_VI',              'BAB VI — Kesimpulan dan Usulan'),
        ('KESIMPULAN',          'Kesimpulan dan Usulan Tindak Lanjut'),
        ('PENUTUP',             'Penutup'),
    ]

    laporan = models.ForeignKey(LaporanMutu, on_delete=models.CASCADE, related_name='seksi')
    kunci   = models.CharField('Kode Bagian', max_length=40, choices=KUNCI_CHOICES)
    judul   = models.CharField('Judul', max_length=120, blank=True, default='')
    isi     = models.TextField('Isi', blank=True, default='')

    class Meta:
        verbose_name        = 'Seksi Laporan Mutu'
        verbose_name_plural = 'Seksi Laporan Mutu'
        ordering            = ['kunci']
        unique_together     = [('laporan', 'kunci')]

    def __str__(self):
        return f'{self.laporan_id} — {self.kunci}'

