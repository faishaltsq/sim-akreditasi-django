from django.db import models
from django.conf import settings
from django.utils import timezone


# Default permission matrix per role
PERMISSION_DEFAULTS = {
    'SUPER_ADMIN': {
        'can_view_pdca': True, 'can_edit_pdca': True, 'can_score_ep': True,
        'can_view_rdwos': True, 'can_upload_rdwos': True, 'can_delete_rdwos': True,
        'can_view_risiko': True, 'can_manage_risiko': True, 'can_lapor_insiden': True,
        'can_investigate_insiden': True, 'can_view_scoring': True, 'can_export_reports': True,
        'can_manage_units': True, 'can_manage_users': True, 'can_verify_kps': True,
        'can_view_audit_log': True,
        'can_access_control_center': True,
        'can_manage_system_settings': True,
    },
    'ADMIN_RS': {
        'can_view_pdca': True, 'can_edit_pdca': True, 'can_score_ep': True,
        'can_view_rdwos': True, 'can_upload_rdwos': True, 'can_delete_rdwos': True,
        'can_view_risiko': True, 'can_manage_risiko': True, 'can_lapor_insiden': True,
        'can_investigate_insiden': True, 'can_view_scoring': True, 'can_export_reports': True,
        'can_manage_units': True, 'can_manage_users': True, 'can_verify_kps': True,
        'can_view_audit_log': True,
        'can_access_control_center': True,
        'can_manage_system_settings': False,   # Tab ambang batas, tema, freeze → hanya SUPER_ADMIN
    },
    'KOORDINATOR_POKJA': {
        'can_view_pdca': True, 'can_edit_pdca': True, 'can_score_ep': True,
        'can_view_rdwos': True, 'can_upload_rdwos': True, 'can_delete_rdwos': True,
        'can_view_risiko': True, 'can_manage_risiko': False, 'can_lapor_insiden': True,
        'can_investigate_insiden': False, 'can_view_scoring': True, 'can_export_reports': True,
        'can_manage_units': False, 'can_manage_users': False, 'can_verify_kps': True,
        'can_view_audit_log': False,
        'can_access_control_center': False,
        'can_manage_system_settings': False,
    },
    'KEPALA_UNIT': {
        'can_view_pdca': True, 'can_edit_pdca': True, 'can_score_ep': False,
        'can_view_rdwos': True, 'can_upload_rdwos': True, 'can_delete_rdwos': False,
        'can_view_risiko': True, 'can_manage_risiko': True, 'can_lapor_insiden': True,
        'can_investigate_insiden': False, 'can_view_scoring': True, 'can_export_reports': False,
        'can_manage_units': False, 'can_manage_users': False, 'can_verify_kps': True,
        'can_view_audit_log': False,
        'can_access_control_center': False,
        'can_manage_system_settings': False,
    },
    'STAF_NAKES': {
        'can_view_pdca': True, 'can_edit_pdca': False, 'can_score_ep': False,
        'can_view_rdwos': True, 'can_upload_rdwos': True, 'can_delete_rdwos': False,
        'can_view_risiko': True, 'can_manage_risiko': False, 'can_lapor_insiden': True,
        'can_investigate_insiden': False, 'can_view_scoring': False, 'can_export_reports': False,
        'can_manage_units': False, 'can_manage_users': False, 'can_verify_kps': False,
        'can_view_audit_log': False,
        'can_access_control_center': False,
        'can_manage_system_settings': False,
    },
    'ASESOR': {
        'can_view_pdca': True, 'can_edit_pdca': False, 'can_score_ep': True,
        'can_view_rdwos': True, 'can_upload_rdwos': False, 'can_delete_rdwos': False,
        'can_view_risiko': True, 'can_manage_risiko': False, 'can_lapor_insiden': False,
        'can_investigate_insiden': False, 'can_view_scoring': True, 'can_export_reports': True,
        'can_manage_units': False, 'can_manage_users': False, 'can_verify_kps': False,
        'can_view_audit_log': False,
        'can_access_control_center': False,
        'can_manage_system_settings': False,
    },
}

# Izin yang tidak boleh diblokir survey freeze (tetap bisa akses) — hanya SUPER_ADMIN override
FREEZE_PROTECTED_PERMS = {'can_view_pdca', 'can_view_rdwos', 'can_view_risiko', 'can_view_scoring', 'can_view_audit_log'}
# Izin khusus admin yang tidak boleh di-revoke dari SUPER_ADMIN
LOCKOUT_SAFE_PERMS = {'can_access_control_center', 'can_manage_users', 'can_manage_system_settings'}


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin (Developer / IT RS)'),
        ('ADMIN_RS', 'Admin Akreditasi RS (Tim Mutu)'),
        ('KOORDINATOR_POKJA', 'Koordinator Pokja (Ketua Kelompok Kerja)'),
        ('KEPALA_UNIT', 'Kepala Unit Kerja'),
        ('STAF_NAKES', 'Staf Nakes / Pelaksana Unit'),
        ('ASESOR', 'Asesor / Viewer (Baca Saja)'),
    ]

    ROLE_HIERARCHY = {
        'SUPER_ADMIN': 5,
        'ADMIN_RS': 4,
        'KOORDINATOR_POKJA': 3,
        'KEPALA_UNIT': 2,
        'STAF_NAKES': 1,
        'ASESOR': 1,
    }

    PROFESI_CHOICES = [
        ('', '— Pilih Profesi —'),
        ('DOKTER_SPESIALIS', 'Dokter Spesialis'),
        ('DOKTER_UMUM', 'Dokter Umum'),
        ('PERAWAT', 'Perawat'),
        ('BIDAN', 'Bidan'),
        ('APOTEKER', 'Apoteker'),
        ('TTK', 'Tenaga Teknis Kefarmasian'),
        ('ANALIS_LAB', 'Pranata Laboratorium Medik'),
        ('RADIOGRAFER', 'Radiografer'),
        ('NUTRISIONIS', 'Nutrisionis / Dietisien'),
        ('FISIOTERAPIS', 'Fisioterapis'),
        ('PEREKAM_MEDIS', 'Perekam Medis & Informasi Kesehatan'),
        ('LAINNYA', 'Tenaga Kesehatan Lainnya'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Akun Pengguna'
    )
    role = models.CharField(
        'Peran / Hak Akses',
        max_length=30,
        choices=ROLE_CHOICES,
        default='ASESOR'
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_profiles',
        verbose_name='Unit Kerja Terkait'
    )
    pokja_access = models.ManyToManyField(
        'akreditasi.Category',
        blank=True,
        verbose_name='Akses Pokja (Koordinator Pokja)',
        help_text='Daftar Pokja yang dapat dikelola oleh Koordinator Pokja ini.'
    )
    full_name = models.CharField('Nama Lengkap', max_length=200, blank=True)
    jabatan = models.CharField('Jabatan', max_length=150, blank=True)
    telepon = models.CharField('Nomor Telepon', max_length=30, blank=True)
    photo_url = models.URLField('URL Foto Profil', blank=True)
    is_active_member = models.BooleanField('Anggota Tim Aktif', default=True)

    # --- Field baru untuk Nakes ---
    profesi = models.CharField(
        'Profesi Klinis',
        max_length=30,
        choices=PROFESI_CHOICES,
        blank=True,
        default='',
        help_text='Wajib diisi untuk role Staf Nakes.'
    )
    nip_nrp = models.CharField(
        'NIP / NRP / No. Pegawai',
        max_length=30,
        blank=True,
        help_text='Nomor Induk Pegawai / Nomor Registrasi Pegawai.'
    )
    # Override izin kustom per pengguna (dict: {'can_edit_pdca': True, ...})
    custom_permissions = models.JSONField('Hak Akses Kustom', default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Pengguna'
        verbose_name_plural = 'Profil Pengguna'
        ordering = ['role', 'user__username']

    def __str__(self):
        return f"{self.user.username} [{self.get_role_display()}]"

    @property
    def role_level(self):
        return self.ROLE_HIERARCHY.get(self.role, 0)

    def has_permission(self, perm_code):
        """
        Evaluasi izin secara hierarkis:
        1. is_superuser / SUPER_ADMIN → selalu True
        2. Survey Freeze Mode aktif → izin edit/manage diblokir kecuali SUPER_ADMIN
        3. custom_permissions per user → override spesifik
        4. RolePermissionConfig → konfigurasi per role
        5. Fallback ke PERMISSION_DEFAULTS
        """
        if self.user.is_superuser or self.role == 'SUPER_ADMIN':
            return True

        # Survey freeze: blokir semua izin kecuali read-only saat mode aktif
        if perm_code not in FREEZE_PROTECTED_PERMS:
            from akreditasi.system_models import SystemConfig
            if SystemConfig.get_solo().survey_freeze_mode:
                return False

        # User-level custom override
        if perm_code in self.custom_permissions:
            return bool(self.custom_permissions[perm_code])

        # Role-level config dari database
        cfg = RolePermissionConfig.get_config_for_role(self.role)
        return getattr(cfg, perm_code, False)

    # --- Backward-compatible properties ---
    @property
    def can_edit(self):
        return self.has_permission('can_edit_pdca')

    @property
    def can_manage_users(self):
        return self.has_permission('can_manage_users')

    @property
    def can_manage_structure(self):
        return self.has_permission('can_manage_units')

    @property
    def can_upload(self):
        return self.has_permission('can_upload_rdwos')

    @property
    def is_read_only(self):
        return self.role == 'ASESOR'

    @property
    def is_nakes(self):
        return self.role == 'STAF_NAKES'

    @property
    def role_badge_class(self):
        map_badge = {
            'SUPER_ADMIN': 'danger',
            'ADMIN_RS': 'primary',
            'KOORDINATOR_POKJA': 'info',
            'KEPALA_UNIT': 'success',
            'STAF_NAKES': 'teal',
            'ASESOR': 'secondary',
        }
        return map_badge.get(self.role, 'secondary')

    @property
    def credential_summary(self):
        """Ringkasan kelengkapan dokumen KPS nakes."""
        creds = self.credentials.all()
        total = creds.count()
        verified = creds.filter(status='VERIFIED').count()
        expiring = creds.filter(
            status='VERIFIED',
            valid_until__isnull=False,
            valid_until__lte=timezone.now().date() + timezone.timedelta(days=90)
        ).count()
        expired = creds.filter(status='EXPIRED').count()
        return {
            'total': total,
            'verified': verified,
            'expiring_soon': expiring,
            'expired': expired,
        }


class NakesCredential(models.Model):
    """Dokumen kredensial & kualifikasi staf nakes untuk pemenuhan Bab KPS."""

    DOC_TYPE_CHOICES = [
        ('STR', 'Surat Tanda Registrasi (STR)'),
        ('SIP', 'Surat Izin Praktik (SIP)'),
        ('SPK_RKK', 'Surat Penugasan Klinis & RKK'),
        ('PELATIHAN_BHD', 'Pelatihan BHD / BLS (KPS 8)'),
        ('PELATIHAN_PPI', 'Pelatihan PPI Dasar (PPI/KPS)'),
        ('PELATIHAN_PMKP', 'Pelatihan Mutu & Keselamatan Pasien'),
        ('PELATIHAN_K3RS', 'Pelatihan K3RS & APAR/Disaster'),
        ('PELATIHAN_LAIN', 'Sertifikat Kompetensi Khusus'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Menunggu Verifikasi'),
        ('VERIFIED', 'Terverifikasi Tim Mutu/KPS'),
        ('REJECTED', 'Ditolak / Perlu Perbaikan'),
        ('EXPIRED', 'Kedaluwarsa'),
    ]

    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='credentials',
        verbose_name='Pemilik Dokumen'
    )
    doc_type = models.CharField('Jenis Dokumen', max_length=20, choices=DOC_TYPE_CHOICES)
    title = models.CharField('Nama / Judul Dokumen', max_length=250)
    document_number = models.CharField('Nomor Dokumen/Sertifikat', max_length=100, blank=True)
    issued_date = models.DateField('Tanggal Terbit / Pelaksanaan', null=True, blank=True)
    valid_until = models.DateField('Masa Berlaku Sampai', null=True, blank=True)
    file_url = models.URLField('URL Dokumen (Cloud/Supabase)', max_length=500, blank=True)
    file = models.FileField('Berkas Scan', upload_to='kps/%Y/%m/', null=True, blank=True)
    status = models.CharField(
        'Status Verifikasi',
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    verification_notes = models.TextField('Catatan Verifikator', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kredensial Nakes (KPS)'
        verbose_name_plural = 'Kredensial Nakes (KPS)'
        ordering = ['doc_type', '-created_at']

    def __str__(self):
        return f"[{self.get_doc_type_display()}] {self.title} — {self.user_profile.full_name or self.user_profile.user.username}"

    @property
    def is_expired(self):
        if self.valid_until and self.valid_until < timezone.now().date():
            return True
        return False

    @property
    def is_expiring_soon(self):
        """True jika kedaluwarsa dalam 90 hari ke depan."""
        if self.valid_until:
            delta = (self.valid_until - timezone.now().date()).days
            return 0 < delta <= 90
        return False

    @property
    def expiry_badge(self):
        if self.is_expired:
            return {'label': 'Kedaluwarsa', 'class': 'danger'}
        if self.is_expiring_soon:
            days_left = (self.valid_until - timezone.now().date()).days
            return {'label': f'Sisa {days_left} hari', 'class': 'warning'}
        if self.status == 'VERIFIED':
            return {'label': 'Aktif', 'class': 'success'}
        if self.status == 'PENDING':
            return {'label': 'Menunggu', 'class': 'secondary'}
        if self.status == 'REJECTED':
            return {'label': 'Ditolak', 'class': 'danger'}
        return {'label': self.get_status_display(), 'class': 'secondary'}

    @property
    def get_download_url(self):
        if self.file_url:
            return self.file_url
        if self.file:
            return self.file.url
        return '#'

    def auto_check_expiry(self):
        """Otomatis ubah status ke EXPIRED jika sudah lewat tanggal berlaku."""
        if self.valid_until and self.valid_until < timezone.now().date() and self.status == 'VERIFIED':
            self.status = 'EXPIRED'
            self.save(update_fields=['status', 'updated_at'])


class RolePermissionConfig(models.Model):
    """Konfigurasi 18 izin modular per peran — dapat diubah Admin via Pusat Kontrol."""
    role = models.CharField('Peran Pengguna', max_length=30, unique=True, choices=UserProfile.ROLE_CHOICES)

    # Modul PDCA & Scoring
    can_view_pdca = models.BooleanField('Lihat Matriks PDCA', default=True)
    can_edit_pdca = models.BooleanField('Edit Plan/Do/Check/Action', default=False)
    can_score_ep = models.BooleanField('Beri Skor EP (0/5/10)', default=False)

    # Modul RDWOS / Dokumen
    can_view_rdwos = models.BooleanField('Akses Dokumen RDWOS', default=True)
    can_upload_rdwos = models.BooleanField('Unggah Dokumen Bukti', default=False)
    can_delete_rdwos = models.BooleanField('Hapus Dokumen Bukti', default=False)

    # Modul Risiko & Insiden
    can_view_risiko = models.BooleanField('Lihat Register Risiko', default=True)
    can_manage_risiko = models.BooleanField('Input & Evaluasi Risiko', default=False)
    can_lapor_insiden = models.BooleanField('Melaporkan Insiden (KNC/KTD)', default=True)
    can_investigate_insiden = models.BooleanField('Investigasi & Analisis Insiden', default=False)

    # Modul Laporan & Ekspor
    can_view_scoring = models.BooleanField('Lihat Auto-Scoring KARS', default=True)
    can_export_reports = models.BooleanField('Cetak Dokumen & Ekspor Excel', default=False)

    # Modul Manajemen
    can_manage_units = models.BooleanField('Kelola Struktur Unit Kerja', default=False)
    can_manage_users = models.BooleanField('Kelola Pengguna & Hak Akses', default=False)
    can_verify_kps = models.BooleanField('Verifikasi Kredensial Nakes', default=False)
    can_view_audit_log = models.BooleanField('Lihat Log Audit Sistem', default=False)

    # Modul Pusat Kontrol Admin
    can_access_control_center = models.BooleanField('Akses Menu Pusat Kontrol Admin', default=False)
    can_manage_system_settings = models.BooleanField('Ubah Konfigurasi Sistem (Ambang Batas, Tema, Freeze)', default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Konfigurasi Izin Peran'
        verbose_name_plural = 'Konfigurasi Izin Peran'

    def __str__(self):
        return f"Izin Peran: {self.get_role_display()}"

    @classmethod
    def get_config_for_role(cls, role):
        """Ambil konfigurasi per role; buat dengan default aman jika belum ada."""
        defaults = PERMISSION_DEFAULTS.get(role, {})
        obj, _ = cls.objects.get_or_create(role=role, defaults=defaults)
        return obj

    @classmethod
    def reset_to_defaults(cls):
        """Reset semua role ke default KARS bawaan sistem."""
        for role, defaults in PERMISSION_DEFAULTS.items():
            obj, created = cls.objects.get_or_create(role=role)
            for field, value in defaults.items():
                setattr(obj, field, value)
            obj.save()
