from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('SUPER_ADMIN', 'Super Admin (Developer / IT RS)'),
        ('ADMIN_RS', 'Admin Akreditasi RS (Tim Mutu)'),
        ('KOORDINATOR_POKJA', 'Koordinator Pokja (Ketua Kelompok Kerja)'),
        ('KEPALA_UNIT', 'Kepala Unit Kerja'),
        ('ASESOR', 'Asesor / Viewer (Baca Saja)'),
    ]

    ROLE_HIERARCHY = {
        'SUPER_ADMIN': 5,
        'ADMIN_RS': 4,
        'KOORDINATOR_POKJA': 3,
        'KEPALA_UNIT': 2,
        'ASESOR': 1,
    }

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
        return self.role in ('SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA', 'KEPALA_UNIT')

    @property
    def is_read_only(self):
        return self.role == 'ASESOR'

    @property
    def role_badge_class(self):
        map_badge = {
            'SUPER_ADMIN': 'danger',
            'ADMIN_RS': 'primary',
            'KOORDINATOR_POKJA': 'info',
            'KEPALA_UNIT': 'success',
            'ASESOR': 'secondary',
        }
        return map_badge.get(self.role, 'secondary')
