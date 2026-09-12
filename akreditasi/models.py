from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Framework(models.Model):
    name = models.CharField('Nama Standar', max_length=200)
    cycle_type = models.CharField('Siklus Kendali Mutu', max_length=20, default='PDCA')
    version = models.CharField('Versi / Edisi', max_length=50, default='2026')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Standar Akreditasi'
        verbose_name_plural = 'Standar Akreditasi'

    def __str__(self):
        return f"{self.name} ({self.cycle_type})"


class UnitKerja(models.Model):
    LEVEL_CHOICES = [
        (1, 'Tingkat 1 — Direktorat / Bidang'),
        (2, 'Tingkat 2 — Bagian / Instalasi / Komite'),
        (3, 'Tingkat 3 — Sub-Bagian / Ruangan / Unit Layanan'),
    ]

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Induk Unit Kerja'
    )
    level = models.PositiveSmallIntegerField(
        'Tingkat Hierarki',
        choices=LEVEL_CHOICES,
        default=1
    )
    name = models.CharField('Nama Unit Kerja', max_length=200)
    code = models.CharField('Kode Unit', max_length=30, unique=True)
    pic_name = models.CharField('Penanggung Jawab (PIC)', max_length=150, blank=True)
    description = models.TextField('Keterangan / Fungsi', blank=True)

    class Meta:
        verbose_name = 'Unit Kerja'
        verbose_name_plural = 'Unit Kerja'
        ordering = ['level', 'code']

    def __str__(self):
        prefix = '—' * (self.level - 1) + (' ' if self.level > 1 else '')
        return f"{prefix}[{self.code}] {self.name}"

    def get_full_hierarchy(self):
        names = [self.name]
        curr = self.parent
        while curr:
            names.insert(0, curr.name)
            curr = curr.parent
        return ' > '.join(names)

    def save(self, *args, **kwargs):
        if self.parent:
            self.level = min(self.parent.level + 1, 3)
        else:
            self.level = 1
        super().save(*args, **kwargs)


class Category(models.Model):
    framework = models.ForeignKey(Framework, on_delete=models.CASCADE, related_name='categories')
    code = models.CharField('Kode Pokja', max_length=20)
    name = models.CharField('Nama Pokja', max_length=200)
    description = models.TextField('Deskripsi', blank=True)
    order = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Kelompok Kerja (Pokja)'
        verbose_name_plural = 'Kelompok Kerja (Pokja)'
        ordering = ['order', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def total_score(self):
        records = QualityRecord.objects.filter(standard_item__category=self)
        return sum(r.score for r in records)

    @property
    def max_possible_score(self):
        items_count = self.items.count()
        return items_count * 10

    @property
    def percentage(self):
        max_score = self.max_possible_score
        if max_score == 0:
            return 0
        return round((self.total_score / max_score) * 100)

    @property
    def status_level(self):
        pct = self.percentage
        if pct >= 80:
            return {'label': 'PARIPURNA (A)', 'badge': 'success'}
        elif pct >= 70:
            return {'label': 'UTAMA (B)', 'badge': 'primary'}
        elif pct >= 60:
            return {'label': 'MADYA (C)', 'badge': 'warning'}
        return {'label': 'BELUM MEMENUHI', 'badge': 'danger'}


class StandardItem(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    sub_standard = models.CharField('Sub-Standar', max_length=50)  # misal: TKRS 1
    sub_title = models.CharField('Judul Sub-Standar', max_length=250)  # misal: Representasi Pemilik
    code = models.CharField('Kode Elemen Penilaian (EP)', max_length=50, unique=True)  # misal: TKRS 1 EP 1
    description = models.TextField('Bunyi Standar / Elemen Penilaian')
    order = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Elemen Penilaian (EP)'
        verbose_name_plural = 'Elemen Penilaian (EP)'
        ordering = ['category__order', 'order', 'code']

    def __str__(self):
        return f"{self.code}: {self.description[:60]}"


class EvidenceReq(models.Model):
    CATEGORY_TYPES = [
        ('R', 'R — Regulasi (SK, Pedoman, SPO)'),
        ('D', 'D — Dokumen / Bukti Fisik (Laporan, Notulen)'),
        ('W', 'W — Wawancara'),
        ('O', 'O — Observasi Lapangan'),
        ('S', 'S — Simulasi'),
    ]

    standard_item = models.ForeignKey(StandardItem, on_delete=models.CASCADE, related_name='evidence_reqs')
    category_type = models.CharField('Kategori Bukti', max_length=2, choices=CATEGORY_TYPES)
    title = models.CharField('Kebutuhan Pembuktian yang Diunggah', max_length=300)
    is_mandatory = models.BooleanField('Wajib Dilengkapi', default=True)

    class Meta:
        verbose_name = 'Kebutuhan Bukti (RDWOS)'
        verbose_name_plural = 'Kebutuhan Bukti (RDWOS)'
        ordering = ['category_type', 'id']

    def __str__(self):
        return f"[{self.category_type}] {self.title}"


class QualityRecord(models.Model):
    SCORE_CHOICES = [
        (10, '10 — Lengkap (≥80%)'),
        (5, '5 — Sebagian (20-79%)'),
        (0, '0 — Belum Terpenuhi (<20%)'),
    ]

    BUDGET_STATUS_CHOICES = [
        ('APPROVED', 'Disetujui (RKA)'),
        ('SUBMITTED', 'Dalam Pengajuan'),
        ('NON_BUDGET', 'Non-Biaya (Rp 0)'),
        ('DRAFT', 'Draft'),
    ]

    standard_item = models.OneToOneField(StandardItem, on_delete=models.CASCADE, related_name='record')
    unit = models.ForeignKey(UnitKerja, on_delete=models.PROTECT, related_name='records')

    # BASELINE DATA
    baseline_data = models.TextField('Asesmen / Kondisi Riil Saat Ini (Baseline)', blank=True)

    # PLAN
    quality_target = models.CharField('Indikator Capaian Mutu (INM/IMP/IMU)', max_length=300, blank=True)
    risk_mitigation = models.TextField('Rencana Mitigasi Risiko (Risk Register)', blank=True)

    # CHECK
    score = models.PositiveSmallIntegerField('Nilai / Skor Self-Assessment', choices=SCORE_CHOICES, default=0)
    eval_notes = models.TextField('Catatan Evaluasi / Rekomendasi Asesor', blank=True)

    # ACTION (Rencana Tindak Lanjut)
    action_plan = models.TextField('Rencana Tindak Lanjut (Action Plan)', blank=True)
    pic = models.CharField('Penanggung Jawab (PIC)', max_length=150, blank=True)
    target_date = models.CharField('Target Waktu Penyelesaian', max_length=100, blank=True)

    # ANGGARAN RKA
    est_cost = models.DecimalField('Estimasi Biaya (Rp)', max_digits=14, decimal_places=2, default=0)
    budget_source = models.CharField('Sumber Alokasi Anggaran', max_length=150, blank=True)
    budget_status = models.CharField('Status Anggaran', max_length=20, choices=BUDGET_STATUS_CHOICES, default='DRAFT')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Record Siklus PDCA'
        verbose_name_plural = 'Record Siklus PDCA'

    def __str__(self):
        return f"PDCA {self.standard_item.code} - {self.unit.name}"


class EvidenceFile(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('REVIEW', 'Review Ketua Pokja'),
        ('VALID', 'Valid / Disetujui Tim Mutu'),
    ]

    requirement = models.ForeignKey(EvidenceReq, on_delete=models.CASCADE, related_name='files')
    file = models.FileField('File Bukti', upload_to='bukti/%Y/%m/', blank=True, null=True)
    file_url = models.URLField('URL Cloud Storage (Supabase)', max_length=500, blank=True)
    file_name = models.CharField('Nama Berkas', max_length=250)
    file_size = models.CharField('Ukuran Berkas', max_length=50, default='1.2 MB')
    version = models.PositiveIntegerField('Versi', default=1)
    status = models.CharField('Status Keabsahan', max_length=20, choices=STATUS_CHOICES, default='VALID')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Berkas Bukti'
        verbose_name_plural = 'Berkas Bukti'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.file_name} (v{self.version})"

    @property
    def get_download_url(self):
        if self.file_url:
            return self.file_url
        if self.file:
            return self.file.url
        return '#'


class RumahSakitProfile(models.Model):
    name = models.CharField('Nama Rumah Sakit', max_length=300, default='Rumah Sakit Umum')
    kode_rs = models.CharField('Kode RS', max_length=50, blank=True)
    alamat = models.TextField('Alamat', blank=True)
    kota = models.CharField('Kota', max_length=100, blank=True)
    telepon = models.CharField('Telepon', max_length=50, blank=True)
    email = models.EmailField('Email', blank=True)
    website = models.URLField('Website', blank=True)
    direktur = models.CharField('Nama Direktur', max_length=200, blank=True)
    tipe = models.CharField('Tipe RS', max_length=100, blank=True, help_text='Contoh: RS Tipe B, RSUD, RSKIA')
    akreditasi_tahun = models.PositiveIntegerField('Tahun Target Akreditasi', default=2026)
    logo_url = models.URLField('URL Logo RS', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Rumah Sakit'
        verbose_name_plural = 'Profil Rumah Sakit'

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        obj, _ = cls.objects.get_or_create(
            id=1,
            defaults={'name': 'Rumah Sakit Anda'}
        )
        return obj


class AuditLog(models.Model):
    AKSI_CHOICES = [
        ('CREATE', 'Tambah'),
        ('UPDATE', 'Ubah'),
        ('DELETE', 'Hapus'),
        ('SCORE', 'Ubah Skor'),
        ('UPLOAD', 'Unggah Berkas'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    aksi = models.CharField(max_length=15, choices=AKSI_CHOICES)
    model_name = models.CharField(max_length=50)
    object_repr = models.CharField(max_length=250)
    detail = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log Audit'
        verbose_name_plural = 'Log Audit'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp:%d/%m/%Y %H:%M} - {self.aksi} - {self.object_repr}"
