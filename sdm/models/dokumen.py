from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class DokumenPegawai(models.Model):
    DOCUMENT_KIND_CHOICES = [
        ('KTP', 'KTP'),
        ('FOTO', 'Foto'),
        ('IJAZAH', 'Ijazah'),
        ('TRANSKRIP', 'Transkrip Nilai'),
        ('STR', 'STR'),
        ('SIP', 'SIP'),
        ('SIPA', 'SIPA'),
        ('KONTRAK', 'Kontrak Kerja'),
        ('SK_PENGANGKATAN', 'SK Pengangkatan'),
        ('SPK_RKK', 'SPK RKK'),
        ('URAIAN_TUGAS', 'Uraian Tugas'),
        ('SERTIFIKAT', 'Sertifikat'),
        ('CV', 'Daftar Riwayat Hidup (CV)'),
        ('SERTIFIKAT_KOMPETENSI', 'Sertifikat Kompetensi'),
        ('LOGBOOK', 'Logbook'),
        ('TRAINING_RECORD', 'Rekaman Pelatihan'),
        ('MCU', 'MCU (Medical Check-up)'),
        ('PSIKOLOGIS', 'Asesmen Psikologis'),
        ('BEBAS_SANKSI', 'Surat Bebas Sanksi'),
        ('MALPRACTICE_RECORD', 'Catatan Malpraktik'),
        ('KEANGGOTAAN', 'Kartu Keanggotaan Organisasi'),
        ('PENGANTAR_KSM', 'Surat Pengantar KSM/KBM'),
        ('BERITA_ACARA_RAPAT', 'Berita Acara Rapat'),
        ('REKOMENDASI_KOMITE', 'Rekomendasi Komite'),
        ('BPJS_KESEHATAN', 'Kartu BPJS Kesehatan'),
        ('BPJS_TK', 'Kartu BPJS Ketenagakerjaan'),
        ('OTHER', 'Lainnya'),
    ]
    DOCUMENT_TYPE_CHOICES = [
        ('IDENTITY', 'Identitas'),
        ('CONTRACT', 'Kontrak Kepegawaian'),
        ('EDUCATION', 'Pendidikan'),
        ('CREDENTIAL', 'Kredensial'),
        ('TRAINING', 'Pelatihan'),
        ('HEALTH', 'Kesehatan Kerja'),
        ('PROFESSIONAL', 'Rekam Profesi'),
        ('OTHER', 'Lainnya'),
    ]
    SENSITIVITY_CHOICES = [
        ('personnel', 'Kepegawaian'),
        ('health', 'Kesehatan Kerja'),
    ]

    employee = models.ForeignKey(
        'sdm.Pegawai',
        on_delete=models.PROTECT,
        related_name='documents',
        verbose_name='Pegawai',
    )
    document_type = models.CharField(
        'Jenis Dokumen', max_length=20, choices=DOCUMENT_TYPE_CHOICES
    )
    jenis_berkas = models.CharField(
        'Jenis Berkas', max_length=30, choices=DOCUMENT_KIND_CHOICES,
        default='OTHER', blank=False,
        help_text='Identitas berkas yang diuji terhadap persyaratan spesifik, bukan sekadar kelompok sensitivitas.',
    )
    title = models.CharField('Judul Dokumen', max_length=250)
    sensitivity = models.CharField(
        'Klasifikasi', max_length=12, choices=SENSITIVITY_CHOICES
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hc_documents_created',
        verbose_name='Dibuat Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dokumen Pegawai'
        verbose_name_plural = 'Dokumen Pegawai'
        ordering = ['-created_at', '-pk']
        indexes = [
            models.Index(
                fields=['employee', 'sensitivity', '-created_at'],
                name='sdm_doc_emp_sens_crt_idx',
            ),
        ]

    def clean(self):
        if self.sensitivity == 'health' and self.document_type != 'HEALTH':
            raise ValidationError({
                'document_type': 'Dokumen kesehatan kerja harus diklasifikasikan sebagai HEALTH.'
            })
        if self.document_type == 'HEALTH' and self.sensitivity != 'health':
            raise ValidationError({
                'sensitivity': 'Dokumen HEALTH harus diklasifikasikan sebagai kesehatan kerja.'
            })

    def __str__(self):
        return f'{self.title} — {self.employee}'


class VersiDokumen(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Menunggu Tinjauan'),
        ('VERIFIED', 'Terverifikasi'),
        ('REJECTED', 'Ditolak / Perlu Perbaikan'),
        ('SUPERSEDED', 'Digantikan Versi Baru'),
    ]

    document = models.ForeignKey(
        DokumenPegawai,
        on_delete=models.PROTECT,
        related_name='versions',
        verbose_name='Dokumen',
    )
    version_number = models.PositiveIntegerField(
        'Nomor Versi', validators=[MinValueValidator(1)]
    )
    original_filename = models.CharField('Nama Berkas Asli', max_length=255)
    storage_key = models.CharField('Kunci Penyimpanan Privat', max_length=255, unique=True)
    sha256 = models.CharField('SHA-256', max_length=64)
    size_bytes = models.PositiveBigIntegerField(
        'Ukuran Berkas (byte)', validators=[MinValueValidator(1)]
    )
    content_type = models.CharField('MIME Type', max_length=100)
    issued_date = models.DateField('Tanggal Terbit', null=True, blank=True)
    valid_until = models.DateField('Berlaku Sampai', null=True, blank=True)
    status = models.CharField(
        'Status Tinjauan', max_length=12, choices=STATUS_CHOICES, default='PENDING'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hc_documents_reviewed',
        verbose_name='Ditinjau Oleh',
    )
    reviewed_at = models.DateTimeField('Waktu Tinjauan', null=True, blank=True)
    review_notes = models.TextField('Catatan Tinjauan', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hc_document_versions_created',
        verbose_name='Diunggah Oleh',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Versi Dokumen Pegawai'
        verbose_name_plural = 'Versi Dokumen Pegawai'
        ordering = ['document_id', '-version_number']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'version_number'],
                name='sdm_doc_version_number_uniq',
            ),
            models.CheckConstraint(
                condition=Q(version_number__gte=1),
                name='sdm_doc_version_positive',
            ),
            models.CheckConstraint(
                condition=Q(size_bytes__gt=0),
                name='sdm_doc_version_size_positive',
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True)
                | Q(issued_date__isnull=True)
                | Q(valid_until__gte=models.F('issued_date')),
                name='sdm_doc_version_dates_valid',
            ),
        ]
        indexes = [
            models.Index(
                fields=['document', 'status', '-created_at'],
                name='sdm_doc_version_status_idx',
            ),
        ]

    def clean(self):
        if self.issued_date and self.valid_until and self.valid_until < self.issued_date:
            raise ValidationError({
                'valid_until': 'Tanggal berlaku tidak boleh mendahului tanggal terbit.'
            })

    def __str__(self):
        return f'{self.document.title} v{self.version_number}'


class TautanKredensialLama(models.Model):
    credential = models.OneToOneField(
        'accounts.NakesCredential',
        on_delete=models.PROTECT,
        related_name='hc_document_link',
        verbose_name='Kredensial Lama',
    )
    version = models.ForeignKey(
        VersiDokumen,
        on_delete=models.PROTECT,
        related_name='legacy_credentials',
        verbose_name='Versi Dokumen Kanonis',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tautan Kredensial Lama'
        verbose_name_plural = 'Tautan Kredensial Lama'
        constraints = [
            models.UniqueConstraint(
                fields=['credential'], name='sdm_legacy_cred_one_link'
            ),
        ]

    def clean(self):
        if not self.credential_id or not self.version_id:
            return
        employee_account_id = self.version.document.employee.akun_id
        credential_account_id = self.credential.user_profile.user_id
        if employee_account_id is None or employee_account_id != credential_account_id:
            raise ValidationError(
                'Kredensial lama hanya dapat ditautkan ke pegawai pada akun yang sama.'
            )

    def __str__(self):
        return f'Kredensial {self.credential_id} → versi {self.version_id}'


class AturanDokumen(models.Model):
    """Versioned applicability and validity rule for a required employee document."""

    KATEGORI_CHOICES = [
        ('PPA', 'Profesional Pemberi Asuhan'),
        ('NON_PPA', 'Non-PPA'),
    ]
    VALIDITY_CHOICES = [
        ('EXPIRY_REQUIRED', 'Wajib memiliki tanggal berlaku'),
        ('LIFETIME', 'Berlaku seumur hidup'),
        ('NOT_APPLICABLE', 'Tidak berlaku'),
    ]

    document_type = models.CharField(
        'Jenis Dokumen', max_length=20, choices=DokumenPegawai.DOCUMENT_TYPE_CHOICES
    )
    jenis_berkas_wajib = models.CharField(
        'Jenis Berkas Wajib', max_length=30,
        choices=DokumenPegawai.DOCUMENT_KIND_CHOICES,
        default='OTHER', blank=False,
        help_text='Persyaratan spesifik jenis berkas yang diijinkan untuk aturan ini.',
    )
    name = models.CharField('Nama Persyaratan', max_length=200)
    kategori = models.CharField(
        'Kategori Staf', max_length=10, choices=KATEGORI_CHOICES, blank=True
    )
    profesi = models.CharField(
        'Profesi', max_length=120, blank=True,
        help_text='Kosong berarti berlaku untuk semua profesi.',
    )
    validity_policy = models.CharField(
        'Kebijakan Masa Berlaku', max_length=20, choices=VALIDITY_CHOICES
    )
    version = models.PositiveIntegerField(
        'Versi Aturan', default=1, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField('Aktif', default=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hc_document_rules_reviewed', verbose_name='Ditinjau Oleh',
    )
    reviewed_at = models.DateTimeField('Waktu Tinjauan', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aturan Dokumen Wajib'
        verbose_name_plural = 'Aturan Dokumen Wajib'
        ordering = ['document_type', 'name', '-version']
        constraints = [
            models.UniqueConstraint(
                fields=['document_type', 'name', 'kategori', 'profesi', 'version'],
                name='sdm_aturan_dokumen_version_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['is_active', 'document_type'], name='sdm_aturan_aktif_jenis_idx'
            ),
        ]

    def applies_to(self, employee):
        if self.kategori and self.kategori != employee.kategori:
            return False
        if self.profesi and self.profesi.strip().lower() != (
            employee.profesi or ''
        ).strip().lower():
            return False
        return True

    def __str__(self):
        return f'{self.name} v{self.version}'


class PemetaanStandarSDM(models.Model):
    """Reviewed mapping between an employee requirement and the accreditation catalogue."""

    rule = models.ForeignKey(
        AturanDokumen, on_delete=models.CASCADE, related_name='standard_mappings',
        verbose_name='Aturan Dokumen',
    )
    standard_item = models.ForeignKey(
        'akreditasi.StandardItem', on_delete=models.PROTECT,
        related_name='sdm_mappings', verbose_name='Elemen Penilaian',
    )
    framework = models.ForeignKey(
        'akreditasi.Framework', on_delete=models.PROTECT,
        related_name='sdm_mappings', verbose_name='Edisi Kerangka',
    )
    reviewer_name = models.CharField('Nama Peninjau', max_length=200)
    reviewed_at = models.DateTimeField('Waktu Tinjauan', default=timezone.now)
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pemetaan Standar SDM'
        verbose_name_plural = 'Pemetaan Standar SDM'
        ordering = ['rule_id', 'standard_item__code']
        constraints = [
            models.UniqueConstraint(
                fields=['rule', 'standard_item'],
                name='sdm_pemetaan_rule_ep_uniq',
            ),
        ]

    def clean(self):
        if not (self.reviewer_name or '').strip():
            raise ValidationError({'reviewer_name': 'Nama peninjau wajib dicatat.'})

    def __str__(self):
        return f'{self.rule} → {self.standard_item.code}'
