from django.db import models
from django.conf import settings
from django.utils import timezone


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

    @property
    def can_edit(self):
        return self.role in ('SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA', 'KEPALA_UNIT')

    @property
    def can_manage_users(self):
        return self.role in ('SUPER_ADMIN', 'ADMIN_RS')

    @property
    def can_manage_structure(self):
        return self.role in ('SUPER_ADMIN', 'ADMIN_RS')

    @property
    def can_upload(self):
        return self.role in ('SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA', 'KEPALA_UNIT', 'STAF_NAKES')

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
