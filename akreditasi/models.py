from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Framework(models.Model):
    name = models.CharField('Nama Standar', max_length=200)
    cycle_type = models.CharField('Siklus Kendali Mutu', max_length=20, default='PDCA')
    version = models.CharField('Versi / Edisi', max_length=50, default='2026')
    edition = models.CharField('Edisi Standar', max_length=20, default='2022')
    source_type = models.CharField(
        'Jenis Sumber',
        max_length=20,
        choices=[
            ('STANDARD_DECREE', 'Standar Keputusan'),
            ('SURVEY_INSTRUMENT', 'Instrumen Survei'),
            ('ARCHIVE', 'Arsip'),
            ('DRAFT', 'Draft Katalog'),
        ],
        default='ARCHIVE',
    )
    lifecycle = models.CharField(
        'Siklus Katalog',
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('VALIDATED', 'Divalidasi'),
            ('ACTIVE', 'Aktif'),
            ('ARCHIVED', 'Arsip'),
        ],
        default='ACTIVE',
    )
    source_hash = models.CharField('SHA-256 Sumber', max_length=64, blank=True)
    source_pages = models.PositiveIntegerField('Jumlah Halaman Sumber', default=0)
    reviewed_at = models.DateTimeField('Ditinjau Pada', null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_frameworks',
    )
    is_active = models.BooleanField(
        'Katalog Aktif', default=True,
        help_text='Hanya satu katalog yang boleh aktif; katalog lama diarsipkan. Hanya lifecycle=ACTIVE yang boleh aktif.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Standar Akreditasi'
        verbose_name_plural = 'Standar Akreditasi'
        ordering = ['-version', 'pk']
        # NOTE: no database-level "single ACTIVE" constraint here.
        # The invariant is enforced by catalogue_services.activate_catalogue
        # (lock + explicit previous-active check) because a hard constraint
        # makes legitimate staging/fixture transitions impossible and turns a
        # service-level rule into an opaque IntegrityError.
        constraints = []

    def __str__(self):
        return f"{self.name} ({self.cycle_type})"

    # Legacy/typo lifecycle values mapped onto the canonical vocabulary.
    LEGACY_LIFECYCLE_ALIASES = {
        'ARCHIVE': 'ARCHIVED',
        'ARCHIVED_LEGACY': 'ARCHIVED',
        'INACTIVE': 'ARCHIVED',
        'PUBLISHED': 'ACTIVE',
        'LIVE': 'ACTIVE',
    }

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.is_active and self.lifecycle != 'ACTIVE':
            raise ValidationError(
                {'is_active': 'Hanya framework dengan lifecycle=ACTIVE yang boleh ditandai aktif.'}
            )

    def save(self, *args, **kwargs):
        # Normalise legacy lifecycle spellings (e.g. the historical 'ARCHIVE'
        # typo) so Framework.active() and every edition-scoped read agree on a
        # single canonical vocabulary. We deliberately do NOT force is_active
        # here: that combination is repaired by the data migration and rejected
        # by the service layer (require_catalogue_write), and forcing it in
        # save() would break legitimate fixtures/tests that build transitional
        # states.
        canonical = self.LEGACY_LIFECYCLE_ALIASES.get(self.lifecycle, self.lifecycle)
        if canonical != self.lifecycle:
            self.lifecycle = canonical
        super().save(*args, **kwargs)

    @classmethod
    def active(cls):
        """Return the catalogue in use, restricted to lifecycle='ACTIVE'.

        Historical data migrations call this while the table may predate the
        `is_active` / `lifecycle` columns, so a missing column must fall back
        instead of aborting the migration.
        """
        from django.db import connection

        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                connection.cursor(), cls._meta.db_table
            )
        }
        if 'is_active' not in columns or 'lifecycle' not in columns:
            return None

        chosen = cls.objects.filter(lifecycle='ACTIVE', is_active=True).order_by('-version', 'pk').first()
        return chosen or cls.objects.filter(lifecycle='ACTIVE').order_by('-version', 'pk').first()

def active_framework():
    """Instrumen yang sedang dipakai UI: framework terbaru yang terpasang.

    Siklus akreditasi berjalan maju, jadi edisi terakhir yang diimpor adalah
    edisi yang berlaku. Fungsi ini dipakai sidebar, matriks PDCA, dan daftar EP
    supaya data edisi lama tidak pernah tercampur dengan edisi aktif — dulu
    pemanggil memakai ``Framework.objects.first()``, yang justru mengunci ke
    edisi paling tua.
    """
    return Framework.objects.order_by('-id').first()


TIPE_UNIT_CHOICES = [
    ('PIMPINAN', 'Pimpinan / Pemilik / Dewas'),
    ('DIREKTORAT', 'Direktorat / Bidang'),
    ('KOMITE', 'Komite Medis / Keperawatan / Mutu'),
    ('SPI', 'Satuan Pengawas Internal'),
    ('BAGIAN', 'Bagian / Sub-Bagian Administrasi'),
    ('INSTALASI', 'Instalasi Pelayanan Medis / Penunjang'),
    ('KSM', 'Kelompok Staf Medis (KSM Spesialis)'),
    ('RUANGAN', 'Ruangan Perawatan / Tindakan'),
    ('DEPO', 'Depo Farmasi / Satelit'),
    ('LAINNYA', 'Unit Penunjang Lainnya'),
]


class UnitKerja(models.Model):
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Induk Unit Kerja'
    )
    level = models.PositiveSmallIntegerField('Tingkat Hierarki', default=1)
    name = models.CharField('Nama Unit Kerja', max_length=200)
    code = models.CharField('Kode Unit', max_length=30, unique=True)
    pic_name = models.CharField('Penanggung Jawab (PIC)', max_length=150, blank=True)
    description = models.TextField('Keterangan / Fungsi', blank=True)
    order = models.PositiveIntegerField('Urutan Tampilan', default=0)
    tipe_unit = models.CharField('Jenis / Kategori Unit', max_length=40, choices=TIPE_UNIT_CHOICES, blank=True, default='LAINNYA')
    is_active = models.BooleanField('Unit Aktif', default=True, help_text='Nonaktifkan unit tanpa menghapus data akreditasi historis.')
    standar_terkait = models.JSONField(
        'Standar Akreditasi Terkait Unit',
        default=dict,
        blank=True,
        help_text='Daftar Bab Pokja dan Kode Standar STARKES yang menjadi tanggung jawab unit ini, misal: {"PKPO": ["PKPO 1", "PKPO 2"]}'
    )

    class Meta:
        verbose_name = 'Unit Kerja'
        verbose_name_plural = 'Unit Kerja'
        ordering = ['level', 'order', 'code']

    def __str__(self):
        prefix = '—' * (self.level - 1) + (' ' if self.level > 1 else '')
        return f"{prefix}[{self.code}] {self.name}"

    def get_full_hierarchy(self):
        names = [self.code]
        curr = self.parent
        while curr:
            names.insert(0, curr.code)
            curr = curr.parent
        return ' > '.join(names)

    def save(self, *args, **kwargs):
        # Jika ada induk (parent), level otomatis parent.level + 1
        # Jika tanpa induk, gunakan level yang ditentukan (default 1 jika kosong/0)
        if self.parent:
            self.level = self.parent.level + 1
        elif not self.level:
            self.level = 1
        super().save(*args, **kwargs)


class Category(models.Model):
    KELOMPOK_CHOICES = [
        ('MANAJEMEN', 'Kelompok Manajemen Rumah Sakit'),
        ('PELAYANAN', 'Kelompok Pelayanan Berfokus pada Pasien'),
        ('SASARAN_KP', 'Kelompok Sasaran Keselamatan Pasien'),
        ('PROGNAS', 'Kelompok Program Nasional'),
        ('PENDIDIKAN', 'Kelompok Integrasi Pendidikan Kesehatan'),
    ]

    framework = models.ForeignKey(Framework, on_delete=models.CASCADE, related_name='categories')
    code = models.CharField('Kode Pokja', max_length=20)
    name = models.CharField('Nama Pokja', max_length=200)
    description = models.TextField('Deskripsi', blank=True)
    kelompok = models.CharField('Kelompok Standar', max_length=20, choices=KELOMPOK_CHOICES, default='MANAJEMEN')
    target_ep_count = models.PositiveIntegerField('Target Jumlah EP STARKES', default=0)
    unit_pengampu = models.TextField('Unit Pengampu & Terlibat', blank=True)
    order = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Kelompok Kerja (Pokja)'
        verbose_name_plural = 'Kelompok Kerja (Pokja)'
        ordering = ['order', 'code']
        unique_together = [('framework', 'code')]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def total_score(self):
        # _pre_total diisi sidebar_context (1 query agregat untuk semua pokja);
        # fallback: aggregate + memo per-instance untuk pemakaian di luar sidebar
        if '_pre_total' in self.__dict__:
            return self._pre_total
        if '_total_score_cache' not in self.__dict__:
            from django.db.models import Sum
            agg = QualityRecord.objects.filter(
                standard_item__category=self
            ).aggregate(s=Sum('score'))
            self._total_score_cache = agg['s'] or 0
        return self._total_score_cache

    @property
    def max_possible_score(self):
        if '_pre_max' in self.__dict__:
            return self._pre_max
        if '_max_possible_score_cache' not in self.__dict__:
            self._max_possible_score_cache = self.items.count() * 10
        return self._max_possible_score_cache

    @property
    def ep_total(self):
        """Jumlah Elemen Penilaian (EP) milik pokja ini.

        Dibagi 10 dari ``max_possible_score`` supaya tidak menambah query:
        keduanya berasal dari hitungan EP yang sama.
        """
        if '_pre_ep_total' in self.__dict__:
            return self._pre_ep_total
        return self.max_possible_score // 10

    @property
    def ep_selesai(self):
        """Jumlah EP yang sudah dinilai (QualityRecord dengan skor > 0)."""
        if '_pre_ep_selesai' in self.__dict__:
            return self._pre_ep_selesai
        if '_ep_selesai_cache' not in self.__dict__:
            self._ep_selesai_cache = self.items.filter(
                record__score__gt=0).count()
        return self._ep_selesai_cache

    @property
    def ep_coverage_pct(self):
        """Persentase EP terpasang dibanding target STARKES 2024.

        ``target_ep_count`` diisi oleh ``import_instrumen_2024`` dari fixture
        PDF, jadi 100% berarti seluruh EP bab ini sudah ada di sistem.
        """
        target = self.target_ep_count
        if not target:
            return 0
        return round((self.ep_total / target) * 100)


    @property
    def ep_gap(self):
        """EP target yang belum terpasang; 0 bila tanpa target atau sudah penuh.

        Dipakai sidebar untuk membedakan "belum dinilai" dari "katalog belum
        terpasang": angka EP rendah dengan target tinggi berarti impun instrumen
        belum lengkap, bukan penilaian yang tertinggal.
        """
        target = self.target_ep_count
        if not target:
            return 0
        return max(target - self.ep_total, 0)

    @property
    def percentage(self):
        max_score = self.max_possible_score
        if max_score == 0:
            return 0
        return round((self.total_score / max_score) * 100)

    @property
    def status_level(self):
        from .system_models import SystemConfig
        cfg = SystemConfig.get_solo()
        pct = self.percentage
        if pct >= cfg.threshold_paripurna:
            return {'label': 'PARIPURNA (A)', 'badge': 'success'}
        elif pct >= cfg.threshold_utama:
            return {'label': 'UTAMA (B)', 'badge': 'primary'}
        elif pct >= cfg.threshold_madya:
            return {'label': 'MADYA (C)', 'badge': 'warning'}
        return {'label': 'BELUM MEMENUHI', 'badge': 'danger'}


class StandardItem(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    sub_standard = models.CharField('Sub-Standar', max_length=50)  # misal: TKRS 1
    sub_title = models.CharField('Judul Sub-Standar', max_length=250)  # misal: Representasi Pemilik
    code = models.CharField('Kode Elemen Penilaian (EP)', max_length=50)  # misal: TKRS 1 EP a
    source_ep_code = models.CharField('Kode EP Sumber Asli', max_length=50, blank=True)
    description_full = models.TextField('Teks Lengkap Standar/EP', blank=True)
    page_reference = models.CharField('Referensi Halaman', max_length=100, blank=True)
    rdwos_instruction = models.TextField('Instruksi Bukti RDWOS', blank=True)
    description = models.TextField('Bunyi Standar / Elemen Penilaian')
    order = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Elemen Penilaian (EP)'
        verbose_name_plural = 'Elemen Penilaian (EP)'
        ordering = ['category__order', 'order', 'code']
        constraints = [
            # Kode EP hanya unik di dalam pokjanya. Dua edisi instrumen boleh
            # memakai kode yang sama (``TKRS 1 EP a`` ada di 2022 maupun 2024);
            # yang tidak boleh adalah satu pokja memuat kode ganda. Uniqueness
            # global membuat edisi baru tidak bisa berdampingan dengan edisi
            # lama, sehingga migrasi selalu menuntut penghapusan data dulu.
            models.UniqueConstraint(fields=['category', 'code'],
                                    name='uniq_standarditem_category_code'),
        ]

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
    ASSESSMENT_STATE_CHOICES = [
        ('UNASSESSED', 'Belum Dinilai'),
        ('ASSESSED', 'Dinilai'),
        ('REVIEW_REQUIRED', 'Perlu Tinjauan Ulang'),
    ]

    assessment_state = models.CharField('Status Asesmen', max_length=20, choices=ASSESSMENT_STATE_CHOICES, default='UNASSESSED')

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
    visi = models.TextField('Visi Rumah Sakit', blank=True)
    misi = models.TextField('Misi Rumah Sakit', blank=True, help_text='Pisahkan tiap poin misi dengan baris baru')
    tujuan = models.TextField('Tujuan Strategis', blank=True, help_text='Tujuan umum RS jangka panjang')
    motto = models.CharField('Motto / Tagline RS', max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Rumah Sakit'
        verbose_name_plural = 'Profil Rumah Sakit'

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        DEFAULT_VISI = "Menjadi Rumah Sakit Rujukan Unggul yang Terpercaya, Modern, dan Berdaya Saing Global Melalui Pelayanan Kesehatan Paripurna Berbasis Keselamatan Pasien dan Tata Kelola Digital."
        DEFAULT_MISI = (
            "1. Menyelenggarakan pelayanan kesehatan yang komprehensif, bermutu tinggi, dan berorientasi pada keselamatan pasien.\n"
            "2. Mengembangkan kompetensi dan profesionalisme seluruh sumber daya manusia kesehatan secara berkesinambungan.\n"
            "3. Mengembangkan tata kelola rumah sakit yang transparan, akuntabel, dan berbasis teknologi informasi terintegrasi.\n"
            "4. Mewujudkan sarana, prasarana, dan fasilitas pelayanan yang ramah lingkungan (Green Hospital) serta adaptif terhadap kemajuan zaman."
        )
        DEFAULT_MOTTO = "Melayani dengan Hati, Mengutamakan Keselamatan, Mengabdi untuk Negeri."
        DEFAULT_TUJUAN = "Mewujudkan tata kelola klinis dan manajemen yang unggul, mencapai standar akreditasi paripurna STARKES, serta menjamin kesinambungan pelayanan kesehatan yang berkualitas bagi seluruh lapisan masyarakat."

        obj, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'name': 'RS MonsisKami',
                'tipe': 'Rumah Sakit Tipe B',
                'kota': 'Jakarta',
                'akreditasi_tahun': 2026,
                'visi': DEFAULT_VISI,
                'misi': DEFAULT_MISI,
                'motto': DEFAULT_MOTTO,
                'tujuan': DEFAULT_TUJUAN,
            }
        )
        # Jika sudah ada di DB tapi field visi masih kosong, populate default
        if not obj.visi:
            obj.visi = DEFAULT_VISI
            obj.misi = DEFAULT_MISI
            obj.motto = DEFAULT_MOTTO
            obj.tujuan = DEFAULT_TUJUAN
            obj.save(update_fields=['visi', 'misi', 'motto', 'tujuan'])
        return obj

    @property
    def misi_list(self):
        """Return list baris misi tanpa penomoran manual dan tanpa baris kosong."""
        import re
        if not self.misi:
            return []
        items = []
        for line in self.misi.splitlines():
            line = line.strip()
            if not line:
                continue
            # Buang penomoran manual di depan seperti '1. ', '1) ', '- '
            cleaned = re.sub(r'^\s*(\d+[\.\)]\s*|-\s*)', '', line).strip()
            if cleaned:
                items.append(cleaned)
        return items


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


# Import models Fase 2 & 5 (Risiko PDCA, Insiden, Indikator Mutu)
from .risiko_models import (  # noqa: E402, F401
    RisikoUnit,
    TindakLanjutRisiko,
    InsidenKeselamatan,
    IndikatorMutu,
    CatatanIndikator,
)
from .system_models import SystemConfig  # noqa: E402, F401
from .logbook_models import (  # noqa: E402, F401
    LogbookHarian,
    LogbookPasien,
    LogbookChecklist,
    LogbookBukti,
    LogbookKejadian,
)

class SumberKatalog(models.Model):
    """Manifest sumber katalog standar (edisi/dekre/instrumen/arsip)."""
    framework = models.ForeignKey(
        'Framework', on_delete=models.CASCADE, related_name='sumber_katalog_entries'
    )
    source_path = models.CharField('Path Sumber', max_length=500)
    sha256 = models.CharField('SHA-256 Berkas Sumber', max_length=64, blank=True)
    document_type = models.CharField('Tipe Dokumen', max_length=50, blank=True)
    decree_number = models.CharField('Nomor Keputusan', max_length=100, blank=True)
    instrument_type = models.CharField('Jenis Instrumen', max_length=50, blank=True)
    pages = models.PositiveIntegerField('Jumlah Halaman', default=0)
    extracted_at = models.DateTimeField('Diekstrak Pada', null=True, blank=True)
    reviewed = models.BooleanField('Direview', default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sumber_katalog_reviews',
    )
    manifest_json = models.JSONField('Manifest JSON', default=dict, blank=True)

    class Meta:
        verbose_name = 'Sumber Katalog'
        verbose_name_plural = 'Sumber Katalog'
        ordering = ['-extracted_at', 'pk']

    def __str__(self):
        return f"{self.framework} - {self.document_type}"


class PemetaanEdisi(models.Model):
    """Keputusan pemetaan item antar edisi katalog standar."""
    CLASSIFICATION_CHOICES = [
        ('UNCHANGED', 'Tidak Berubah'),
        ('CHANGED', 'Berubah'),
        ('SPLIT', 'Dipisah'),
        ('MERGED', 'Digabung'),
        ('RETIRED', 'Dicabut'),
        ('NEW', 'Baru'),
        ('UNRESOLVED', 'Tidak Terpecahkan'),
    ]
    SCORE_POLICY_CHOICES = [
        ('REASSESS', 'Dinilai Ulang'),
        ('CARRY_ASSESSMENT', 'Bawa Asesmen'),
    ]

    source_framework = models.ForeignKey(
        'Framework', on_delete=models.CASCADE, related_name='pemetaan_source'
    )
    source_item_id = models.PositiveIntegerField('ID Item Sumber')
    source_code = models.CharField('Kode Sumber', max_length=50)
    source_text_hash = models.CharField('Hash Teks Sumber', max_length=64, blank=True)

    target_framework = models.ForeignKey(
        'Framework', on_delete=models.CASCADE, related_name='pemetaan_target'
    )
    target_item_id = models.PositiveIntegerField('ID Item Target')
    target_code = models.CharField('Kode Target', max_length=50)
    target_text_hash = models.CharField('Hash Teks Target', max_length=64, blank=True)

    classification = models.CharField(
        'Klasifikasi Pemetaan', max_length=20, choices=CLASSIFICATION_CHOICES, default='UNRESOLVED'
    )
    evidence_rule_map = models.JSONField('Aturan Bukti', default=dict, blank=True)
    score_policy = models.CharField(
        'Kebijakan Skor', max_length=20, choices=SCORE_POLICY_CHOICES, default='CARRY_ASSESSMENT'
    )
    reason = models.TextField('Alasan Pemetaan', blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='pemetaan_reviews',
    )
    reviewed_at = models.DateTimeField('Ditinjau Pada', null=True, blank=True)
    approved = models.BooleanField('Disetujui', default=False)

    class Meta:
        verbose_name = 'Pemetaan Edisi'
        verbose_name_plural = 'Pemetaan Edisi'
        ordering = ['-reviewed_at', 'pk']

    def __str__(self):
        return f"{self.source_code} -> {self.target_code} ({self.classification})"


class TautanAsesmenLintasEdisi(models.Model):
    """Tautan asesmen QualityRecord lintas edisi (sumber -> target)."""
    source_record = models.ForeignKey(
        'QualityRecord',
        on_delete=models.CASCADE,
        related_name='tautan_asesmen_source',
        verbose_name='QualityRecord Sumber',
    )
    target_record = models.ForeignKey(
        'QualityRecord',
        on_delete=models.CASCADE,
        related_name='tautan_asesmen_target',
        verbose_name='QualityRecord Target',
    )
    mapping = models.ForeignKey(
        PemetaanEdisi,
        on_delete=models.CASCADE,
        related_name='tautan_asesmen',
        verbose_name='Pemetaan Edisi',
    )
    state = models.CharField('Status', max_length=20, choices=QualityRecord.ASSESSMENT_STATE_CHOICES, default='UNASSESSED')

    class Meta:
        verbose_name = 'Tautan Asesmen Lintas Edisi'
        verbose_name_plural = 'Tautan Asesmen Lintas Edisi'
        ordering = ['-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['source_record', 'target_record', 'mapping'],
                name='unique_asesmen_link_per_mapping',
            ),
        ]

    def __str__(self):
        return f"Asesmen {self.source_record} -> {self.target_record}"


class TautanBuktiLintasEdisi(models.Model):
    """Tautan bukti EvidenceFile lintas edisi (sumber -> target)."""
    source_file = models.ForeignKey(
        'EvidenceFile',
        on_delete=models.CASCADE,
        related_name='tautan_bukti_source',
        verbose_name='Berkas Sumber',
    )
    target_file = models.ForeignKey(
        'EvidenceFile',
        on_delete=models.CASCADE,
        related_name='tautan_bukti_target',
        verbose_name='Berkas Target',
    )
    mapping = models.ForeignKey(
        PemetaanEdisi,
        on_delete=models.CASCADE,
        related_name='tautan_bukti',
        verbose_name='Pemetaan Edisi',
    )
    status = models.CharField('Status Tautan', max_length=30, default='LINKED')

    class Meta:
        verbose_name = 'Tautan Bukti Lintas Edisi'
        verbose_name_plural = 'Tautan Bukti Lintas Edisi'
        ordering = ['-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['source_file', 'target_file', 'mapping'],
                name='unique_bukti_link_per_mapping',
            ),
        ]

    def __str__(self):
        return f"Bukti {self.source_file} -> {self.target_file}"


class AktivasiKatalog(models.Model):
    """Catatan aktivasi katalog standar (framework yang diaktifkan)."""
    STATUS_CHOICES = [
        ('PLANNED', 'Direncanakan'),
        ('ACTIVE', 'Aktif'),
        ('ROLLED_BACK', 'Dikembalikan'),
        ('FAILED', 'Gagal'),
    ]

    framework = models.ForeignKey(
        'Framework', on_delete=models.CASCADE, related_name='aktivasi_entries', verbose_name='Framework Diaktifkan'
    )
    activated_at = models.DateTimeField('Diaktifkan Pada', auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='aktivasi_katalog',
    )
    previous_framework = models.ForeignKey(
        'Framework',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='aktivasi_as_previous',
        verbose_name='Framework Sebelumnya',
    )
    source_hash = models.CharField('SHA-256 Sumber', max_length=64, blank=True)
    plan_hash = models.CharField('SHA-256 Rencana', max_length=64, blank=True)
    backup_reference = models.CharField('Referensi Cadangan', max_length=200, blank=True)
    status = models.CharField('Status Aktivasi', max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    run_metadata = models.JSONField('Metadata Pelaksanaan', default=dict, blank=True)

    class Meta:
        verbose_name = 'Aktivasi Katalog'
        verbose_name_plural = 'Aktivasi Katalog'
        ordering = ['-activated_at', 'pk']

    def __str__(self):
        return f"Aktivasi {self.framework} ({self.status})"
