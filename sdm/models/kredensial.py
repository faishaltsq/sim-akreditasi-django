"""Level 2 workflows: recruitment, PSV, clinical privileging, orientation."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class VerifikasiSumber(models.Model):
    """Manual primary-source verification (PSV) tied to an exact document version."""

    OUTCOME_CHOICES = [
        ('VALID', 'Sah'),
        ('TIDAK_VALID', 'Tidak Sah'),
        ('PERLU_KONFIRMASI', 'Perlu Konfirmasi'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='psv_records',
        verbose_name='Pegawai',
    )
    version = models.ForeignKey(
        'sdm.VersiDokumen', on_delete=models.PROTECT, related_name='psv_records',
        verbose_name='Versi Dokumen',
    )
    issuer = models.CharField('Penerbit Sumber', max_length=200)
    reference = models.CharField('Nomor Referensi', max_length=200)
    method = models.CharField('Metode Verifikasi', max_length=120)
    outcome = models.CharField('Hasil', max_length=20, choices=OUTCOME_CHOICES)
    verified_at = models.DateTimeField('Waktu Verifikasi', default=timezone.now)
    verifier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sdm_psv_verified', verbose_name='Verifikator',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Verifikasi Sumber Utama'
        verbose_name_plural = 'Verifikasi Sumber Utama'
        ordering = ['-verified_at']
        indexes = [
            models.Index(fields=['employee', 'outcome'], name='sdm_psv_emp_outcome_idx'),
        ]

    def clean(self):
        if self.version_id and self.employee_id:
            if self.version.document.employee_id != self.employee_id:
                raise ValidationError(
                    {'version': 'Versi dokumen bukan milik pegawai ini.'}
                )

    def __str__(self):
        return f'PSV {self.reference} — {self.get_outcome_display()}'


class PengajuanKredensial(models.Model):
    STATUS_CHOICES = [
        ('DIAJUKAN', 'Diajukan'),
        ('DITINJAU', 'Ditinjau Komite'),
        ('DIREKOMENDASI', 'Direkomendasikan'),
        ('DISETUJUI', 'Disetujui'),
        ('DITOLAK', 'Ditolak'),
        ('DICABUT', 'Dicabut'),
    ]
    JENIS_CHOICES = [
        ('AWAL', 'Kredensial Awal'),
        ('REKREDENSIAL', 'Re-Kredensial 3 Tahunan'),
        ('PENAMBAHAN', 'Penambahan Kewenangan'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='credential_requests',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_credential_requests', verbose_name='Unit Kerja',
    )
    jenis = models.CharField(
        'Jenis Pengajuan', max_length=20, choices=JENIS_CHOICES, default='AWAL'
    )
    logbook = models.ForeignKey(
        'sdm.VersiDokumen', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='credential_logbook',
        verbose_name='Logbook / Portofolio',
    )
    status = models.CharField(
        'Status', max_length=20, choices=STATUS_CHOICES, default='DIAJUKAN'
    )
    committee_notes = models.TextField('Catatan Komite', blank=True)
    recommendation = models.TextField('Rekomendasi', blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_credentials_submitted', verbose_name='Diajukan Oleh',
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sdm_credentials_decided', verbose_name='Diputuskan Oleh',
    )
    decided_at = models.DateTimeField('Waktu Keputusan', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengajuan Kredensial'
        verbose_name_plural = 'Pengajuan Kredensial'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='sdm_kred_status_idx'),
        ]

    def __str__(self):
        return f'RKK {self.employee_id} — {self.get_status_display()}'


class RincianKewenangan(models.Model):
    USULAN_CHOICES = [
        ('MANDIRI', 'Mandiri'),
        ('SUPERVISI', 'Supervisi'),
        ('MANDIRI_TERBATAS', 'Mandiri Terbatas'),
    ]
    # Catalog supervision level -> requested privilege level (KatalogTindakan.TINGKAT_CHOICES).
    USULAN_DARI_TINGKAT = {
        'M': 'MANDIRI',
        'S': 'SUPERVISI',
        'MT': 'MANDIRI_TERBATAS',
    }
    REKOMENDASI_CHOICES = [
        ('MANDIRI', 'Disetujui Mandiri'),
        ('SUPERVISI', 'Disetujui dengan Supervisi'),
        ('MANDIRI_TERBATAS', 'Disetujui Mandiri Terbatas'),
        ('DITOLAK', 'Ditolak'),
    ]
    STATUS_SPK_CHOICES = [
        ('DISETUJUI_MANDIRI', 'Disetujui Mandiri'),
        ('DISETUJUI_SUPERVISI', 'Disetujui dengan Supervisi'),
        ('DISETUJUI_MANDIRI_TERBATAS', 'Disetujui Mandiri Terbatas'),
        ('TIDAK_DIBERIKAN', 'Tidak Diberikan'),
    ]
    pengajuan = models.ForeignKey(
        PengajuanKredensial, on_delete=models.CASCADE, related_name='privileges',
        verbose_name='Pengajuan Kredensial',
    )
    kewenangan = models.CharField('Kewenangan Klinis', max_length=200)
    catalog_item = models.ForeignKey(
        'sdm.KatalogTindakan', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rincian',
        verbose_name='Katalog Tindakan',
    )
    usulan = models.CharField(
        'Usulan Pegawai', max_length=16, choices=USULAN_CHOICES,
        default='MANDIRI',
    )
    rekomendasi = models.CharField(
        'Rekomendasi Komite', max_length=16, choices=REKOMENDASI_CHOICES,
        blank=True,
    )
    status_spk = models.CharField(
        'Status SPK Direktur', max_length=26, choices=STATUS_SPK_CHOICES,
        blank=True,
    )
    batasan = models.TextField('Keterangan / Batasan', blank=True)
    catatan = models.TextField('Catatan', blank=True)

    class Meta:
        verbose_name = 'Rincian Kewenangan'
        verbose_name_plural = 'Rincian Kewenangan'
        ordering = ['pengajuan_id', 'pk']

    def __str__(self):
        if not self.kewenangan and self.catalog_item_id:
            return self.catalog_item.nama
        return self.kewenangan


class KeputusanKredensial(models.Model):
    OUTCOME_CHOICES = [
        ('DISETUJUI', 'Disetujui'),
        ('DITOLAK', 'Ditolak'),
    ]
    pengajuan = models.OneToOneField(
        PengajuanKredensial, on_delete=models.PROTECT, related_name='decision',
        verbose_name='Pengajuan Kredensial',
    )
    outcome = models.CharField('Keputusan', max_length=20, choices=OUTCOME_CHOICES)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sdm_credential_decisions', verbose_name='Diputuskan Oleh',
    )
    decided_at = models.DateTimeField('Waktu Keputusan', default=timezone.now)
    notes = models.TextField('Catatan', blank=True)

    class Meta:
        verbose_name = 'Keputusan Kredensial'
        verbose_name_plural = 'Keputusan Kredensial'
        ordering = ['-decided_at']

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Keputusan kredensial bersifat immutable.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.pengajuan_id} — {self.get_outcome_display()}'


class PenugasanKlinis(models.Model):
    """Authorized SPK output; a document review alone never creates one."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'sdm.Pegawai', on_delete=models.PROTECT, related_name='clinical_assignments',
        verbose_name='Pegawai',
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja', on_delete=models.PROTECT,
        related_name='sdm_clinical_assignments', verbose_name='Unit Kerja',
    )
    decision = models.ForeignKey(
        KeputusanKredensial, on_delete=models.PROTECT,
        related_name='clinical_assignments', verbose_name='Keputusan Kredensial',
    )
    nomor_spk = models.CharField('Nomor SPK', max_length=80, unique=True)
    versi = models.PositiveIntegerField('Versi SPK', default=1)
    berlaku_mulai = models.DateField('Berlaku Mulai')
    berlaku_sampai = models.DateField('Berlaku Sampai', null=True, blank=True)
    is_active = models.BooleanField('Aktif', default=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='sdm_spk_issued', verbose_name='Diterbitkan Oleh',
    )
    issued_at = models.DateTimeField('Waktu Terbit', default=timezone.now)

    class Meta:
        verbose_name = 'Penugasan Klinis'
        verbose_name_plural = 'Penugasan Klinis'
        ordering = ['-issued_at']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'versi'], name='sdm_spk_employee_version_uniq'
            ),
            models.CheckConstraint(
                condition=models.Q(berlaku_sampai__isnull=True)
                | models.Q(berlaku_sampai__gte=models.F('berlaku_mulai')),
                name='sdm_spk_period_valid',
            ),
        ]

    def __str__(self):
        return f'{self.nomor_spk} — {self.employee_id}'


class PenilaianTindakan(models.Model):
    """Peer review (mitra bestari) verdict for one privilege line."""

    REKOMENDASI_CHOICES = RincianKewenangan.REKOMENDASI_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pengajuan = models.ForeignKey(
        PengajuanKredensial, on_delete=models.CASCADE,
        related_name='penilaian_tindakan', verbose_name='Pengajuan Kredensial',
    )
    rincian = models.ForeignKey(
        RincianKewenangan, on_delete=models.PROTECT, related_name='penilaian',
        verbose_name='Rincian Kewenangan',
    )
    rekomendasi = models.CharField(
        'Rekomendasi', max_length=16, choices=REKOMENDASI_CHOICES
    )
    catatan_khusus = models.TextField('Catatan Khusus / Syarat', blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sdm_peer_reviews',
        verbose_name='Dinilai Oleh',
    )
    reviewed_at = models.DateTimeField('Waktu Penilaian', auto_now=True)

    class Meta:
        verbose_name = 'Penilaian Mitra Bestari'
        verbose_name_plural = 'Penilaian Mitra Bestari'
        ordering = ['pengajuan_id', 'rincian_id']
        constraints = [
            models.UniqueConstraint(
                fields=['pengajuan', 'rincian'],
                name='sdm_penilaian_pengajuan_rincian_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.rincian_id} — {self.get_rekomendasi_display()}'


class DokumenSyaratKredensial(models.Model):
    """C-3: one supporting-document requirement row per credential request."""

    DOMAIN_CHOICES = [
        ('LEGA', 'Legalitas & Identitas'),
        ('KOMP', 'Kompetensi & CPD'),
        ('SEHAT', 'Kesehatan Fisik & Mental'),
        ('ETIK', 'Etik, Disiplin, Riwayat Hukum'),
        ('KINE', 'Kinerja & Portofolio'),
        ('PROS', 'Administrasi Proses'),
    ]
    JENIS_CHOICES = [
        ('CV', 'CV'),
        ('SERTIFIKAT_KOMPETENSI', 'Sertifikat Kompetensi'),
        ('LOGBOOK_36BULAN', 'Logbook 36 Bulan'),
        ('SEHAT_JASMANI', 'Pemeriksaan Kesehatan Jasmani'),
        ('SEHAT_PSIKOLOGIS', 'Asesmen Psikologis'),
        ('BEBAS_SANKSI', 'Surat Bebas Sanksi'),
        ('MALPRACTICE_RECORD', 'Riwayat Malpraktik'),
        ('KEANGGOTAAN', 'Keanggotaan Organisasi Profesi'),
        ('PENGANTAR_KSM', 'Pengantar/Rekomendasi KSM'),
        ('BERITA_ACARA', 'Berita Acara Rapat'),
        ('REKOMENDASI_KOMITE', 'Rekomendasi Komite'),
        ('SURAT_PERMOHONAN', 'Surat Permohonan'),
        ('LAINNYA', 'Dokumen Pendukung Lain'),
    ]
    STATUS_CHOICES = [
        ('TERPENUHI', 'Terpenuhi'),
        ('KURANG', 'Kurang'),
        ('INFO', 'Informasi'),
    ]
    WORKFLOW_JENIS = ('SURAT_PERMOHONAN', 'BERITA_ACARA', 'REKOMENDASI_KOMITE')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pengajuan = models.ForeignKey(
        PengajuanKredensial, on_delete=models.CASCADE, related_name='requirements',
        verbose_name='Pengajuan Kredensial',
    )
    domain = models.CharField('Domain', max_length=6, choices=DOMAIN_CHOICES)
    jenis = models.CharField('Persyaratan', max_length=30, choices=JENIS_CHOICES)
    label = models.CharField('Label Khusus', max_length=200, blank=True)
    document_version = models.ForeignKey(
        'sdm.VersiDokumen', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='syarat_kredensial', verbose_name='Berkas Tertaut',
    )
    logbook_ok = models.BooleanField('Logbook Terpenuhi', default=False)
    status = models.CharField(
        'Status', max_length=12, choices=STATUS_CHOICES, default='KURANG'
    )
    note = models.CharField('Catatan', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Syarat Dokumen Kredensial'
        verbose_name_plural = 'Syarat Dokumen Kredensial'
        ordering = ['domain', 'jenis']
        constraints = [
            models.UniqueConstraint(
                fields=['pengajuan', 'jenis'],
                name='sdm_syarat_pengajuan_jenis_uniq',
            ),
        ]

    def clean(self):
        if self.jenis in self.WORKFLOW_JENIS:
            if self.status != 'INFO':
                raise ValidationError({
                    'status': 'Baris alur kerja tidak dapat ditandai manual.'
                })
            return
        if self.status == 'TERPENUHI':
            if not self.document_version_id and not self.logbook_ok:
                raise ValidationError({
                    'status': 'Status terpenuhi memerlukan berkas tertaut atau logbook.'
                })
        if self.status == 'INFO' and self.document_version_id:
            raise ValidationError({
                'status': 'Baris informasional tidak boleh menautkan berkas.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_domain_display()} — {self.get_jenis_display()} ({self.get_status_display()})'
