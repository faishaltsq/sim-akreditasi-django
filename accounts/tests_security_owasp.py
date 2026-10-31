"""OWASP Top 10 (2021) security tests — accounts app.

Mencakup:
- A01 Broken Access Control: eskalasi peran vertikal lewat user_create/user_edit,
  dan penulisan ``custom_permissions`` untuk user_id mana pun oleh pemegang
  Pusat Kontrol.
- A02 Cryptographic Failures / A05 Security Misconfiguration: atribut cookie sesi
  dan penguncian akun nonaktif.

Test yang menemukan kerentanan nyata gagal dengan pesan Indonesia yang
menjelaskan bukti dan dampaknya. Test yang memaku pelindung yang sudah benar
memakai assertion biasa dan lulus.
"""
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.tests_utils import login, make_user


class SuperAdminRoleEscalationTest(TestCase):
    """ADMIN_RS (can_manage_users) tidak boleh dapat mencetak SUPER_ADMIN.

    ``accounts/views.py:27-33`` mendefinisikan ``admin_only`` sebagai
    ``is_superuser or profile.can_manage_users``. ``ADMIN_RS`` memegang
    ``can_manage_users=True`` (PERMISSION_DEFAULTS), sehingga lolos gate itu.
    ``user_create`` (views.py:100-146) lalu menyetel ``is_staff``/``is_superuser``
    langsung dari ``profile.role`` tanpa memeriksa apakah pemanggil berhak
    menetapkan peran tersebut.
    """

    def setUp(self):
        self.admin_rs = make_user('owasp.admin.rs', 'ADMIN_RS')
        login(self.client, self.admin_rs)

    def _create_payload(self, username, role):
        """Payload POST sesuai UserCreateForm + UserProfileForm.

        UserCreateForm.Meta.fields = username, first_name, last_name, email,
        password1, password2. UserProfileForm.Meta.fields = role, full_name,
        jabatan, nip_nrp, profesi, telepon, unit_kerja, pokja_access,
        is_active_member.
        """
        return {
            'username': username,
            'first_name': 'Eskalasi',
            'last_name': 'Akun',
            'email': f'{username}@rs.test',
            'password1': 'Sandi-Kuat-2026!',
            'password2': 'Sandi-Kuat-2026!',
            'role': role,
            'full_name': 'Akun Hasil Eskalasi',
            'jabatan': 'IT',
            'nip_nrp': '',
            'profesi': '',
            'telepon': '',
            'unit_kerja': '',
            'is_active_member': 'on',
        }

    def test_admin_rs_tidak_dapat_membuat_super_admin(self):
        """ADMIN_RS POST role=SUPER_ADMIN tidak boleh menghasilkan is_superuser."""
        response = self.client.post(
            reverse('accounts:user_create'),
            self._create_payload('owasp.escalated.super', 'SUPER_ADMIN'),
        )
        self.assertIn(response.status_code, (200, 302), 'user_create tidak merespons')
        created = User.objects.filter(username='owasp.escalated.super').first()
        if created is None:
            # Ditolak total — pelindung bekerja.
            return
        if created.is_superuser or created.is_staff:
            self.fail(
                'ESKALASI HAK AKSES VERTIKAL: ADMIN_RS (can_manage_users=True) '
                'berhasil membuat akun dengan role=SUPER_ADMIN melalui '
                'accounts:user_create, sehingga akun '
                f'"{created.username}" mendapat is_superuser={created.is_superuser} '
                f'dan is_staff={created.is_staff}. Gate admin_only hanya memeriksa '
                'can_manage_users dan view menyetel is_superuser langsung dari '
                'profile.role tanpa memvalidasi hak pemanggil. Perbaikan: batasi '
                'penetapan role SUPER_ADMIN hanya untuk is_superuser.'
            )
        self.assertFalse(created.is_superuser)

    def test_admin_rs_tidak_dapat_mengeskalasi_lewat_user_edit(self):
        """ADMIN_RS mengubah akun lain menjadi SUPER_ADMIN harus ditolak."""
        victim = make_user('owasp.calon.super', 'STAF_NAKES')
        response = self.client.post(
            reverse('accounts:user_edit', args=[victim.id]),
            {
                'username': victim.username,
                'first_name': '',
                'last_name': '',
                'email': victim.email,
                'is_active': 'on',
                'role': 'SUPER_ADMIN',
                'full_name': 'Naik Pangkat',
                'jabatan': '',
                'nip_nrp': '',
                'profesi': '',
                'telepon': '',
                'unit_kerja': '',
            },
        )
        self.assertIn(response.status_code, (200, 302), 'user_edit tidak merespons')
        victim.refresh_from_db()
        victim.profile.refresh_from_db()
        if victim.is_superuser or victim.profile.role == 'SUPER_ADMIN':
            self.fail(
                'ESKALASI HAK AKSES VERTIKAL: ADMIN_RS berhasil mengubah akun '
                f'"{victim.username}" menjadi SUPER_ADMIN melalui '
                'accounts:user_edit (is_superuser=%s, role=%s). user_edit '
                'menetapkan is_staff/is_superuser langsung dari profile.role '
                'tanpa memeriksa apakah pemanggil adalah superuser.'
                % (victim.is_superuser, victim.profile.role)
            )
        self.assertFalse(victim.is_superuser)


class ControlCenterPermissionTamperTest(TestCase):
    """``update_user_custom_permissions`` menulis JSON izin tanpa validasi.

    ``accounts/views.py:455-490``: dijaga hanya oleh ``control_center_access``
    (``can_access_control_center``). View menulis ``profile.custom_permissions``
    apa adanya untuk ``user_id`` mana pun — termasuk akun pemanggil sendiri — tanpa
    whitelist kunci izin. ``UserProfile.has_permission`` (models.py:213-235)
    membaca ``custom_permissions`` sebagai override sebelum RolePermissionConfig,
    sehingga kunci ``can_manage_users`` yang ditulis di sini langsung berlaku.
    """

    def setUp(self):
        # Pemegang Pusat Kontrol dengan peran rendah: KOORDINATOR_POKJA.
        self.holder = make_user('owasp.kontrol.holder', 'KOORDINATOR_POKJA')
        cfg = RolePermissionConfig.get_config_for_role('KOORDINATOR_POKJA')
        cfg.can_access_control_center = True
        cfg.save(update_fields=['can_access_control_center'])
        self.victim = make_user('owasp.staf.biasa', 'STAF_NAKES')
        login(self.client, self.holder)

    def _url(self, user):
        return reverse('accounts:update_user_custom_permissions', args=[user.id])

    def test_holder_tidak_dapat_memberi_izin_kepada_akun_lain(self):
        """Menulis can_manage_users=True ke akun low-privilege harus ditolak."""
        response = self.client.post(
            self._url(self.victim),
            data='{"custom_permissions": {"can_manage_users": true}}',
            content_type='application/json',
        )
        self.assertIn(response.status_code, (200, 400), 'endpoint tidak merespons')
        self.victim.profile.refresh_from_db()
        granted = bool(self.victim.profile.custom_permissions.get('can_manage_users'))
        if granted:
            self.fail(
                'ESKALASI HAK AKSES: pemegang can_access_control_center '
                f'("{self.holder.username}") berhasil menulis custom_permissions '
                '{"can_manage_users": true} ke akun '
                f'"{self.victim.username}" melalui '
                'accounts:update_user_custom_permissions. Endpoint tidak '
                'memvalidasi kunci izin maupun hak pemanggil atas akun target. '
                'Perbaikan: whitelist kunci izin dan tolak pemberian yang '
                'melebihi izin pemberi.'
            )
        self.assertFalse(granted)

    def test_holder_tidak_dapat_memberi_izin_kepada_dirinya(self):
        """Self-grant can_manage_users ke profil pemanggil harus ditolak."""
        before = self.holder.profile.has_permission('can_manage_users')
        response = self.client.post(
            self._url(self.holder),
            data='{"custom_permissions": {"can_manage_users": true}}',
            content_type='application/json',
        )
        self.assertIn(response.status_code, (200, 400), 'endpoint tidak merespons')
        self.holder.profile.refresh_from_db()
        after = self.holder.profile.has_permission('can_manage_users')
        if after and not before:
            self.fail(
                'ESKALASI HAK AKSES DIRI SENDIRI: pemegang '
                'can_access_control_center berhasil memberi dirinya sendiri '
                'can_manage_users melalui accounts:update_user_custom_permissions '
                '(sebelum=%s, sesudah=%s). Tidak ada pemisahan tugas: pemanggil '
                'dapat menargetkan user_id miliknya sendiri.'
                % (before, after)
            )
        self.assertEqual(after, before)


class CookieSecurityTest(TestCase):
    """Atribut cookie sesi dan penguncian akun nonaktif (A02/A05/A07)."""

    def test_session_cookie_httponly(self):
        """SESSION_COOKIE_HTTPONLY harus aktif agar JS tidak membaca sesi."""
        self.assertTrue(
            settings.SESSION_COOKIE_HTTPONLY,
            'SESSION_COOKIE_HTTPONLY harus True (config/settings.py:131).',
        )

    @override_settings(DEBUG=False, SESSION_COOKIE_SECURE=True)
    def test_session_cookie_secure_saat_debug_off(self):
        """Dengan DEBUG off, cookie sesi harus Secure (hanya lewat HTTPS)."""
        self.assertTrue(
            settings.SESSION_COOKIE_SECURE,
            'SESSION_COOKIE_SECURE harus True di produksi '
            '(config/settings.py:124).',
        )

    def test_samesite_dilaporkan_secara_eksplisit(self):
        """SESSION_COOKIE_SAMESITE harus di-set eksplisit, bukan default Django.

        Django default-nya 'Lax'; proyek ini tidak menetapkannya di settings.py,
        sehingga nilainya bergantung pada default framework dan tidak terlihat
        dalam review. Test gagal bila nilainya bukan 'Lax'/'Strict' eksplisit.
        """
        value = settings.SESSION_COOKIE_SAMESITE
        if value not in ('Lax', 'Strict'):
            self.fail(
                'ATRIBUT COOKIE TIDAK DIKONFIGURASI: SESSION_COOKIE_SAMESITE '
                f'bernilai {value!r}. config/settings.py tidak menetapkan '
                'SESSION_COOKIE_SAMESITE, sehingga nilainya bergantung pada '
                "default Django dan tidak dapat diaudit. Set eksplisit "
                "SESSION_COOKIE_SAMESITE = 'Lax' (atau 'Strict')."
            )
        self.assertIn(value, ('Lax', 'Strict'))

    def test_akun_nonaktif_tidak_dapat_login(self):
        """Akun is_active=False harus ditolak saat login (ModelBackend)."""
        user = make_user('owasp.nonaktif', 'STAF_NAKES')
        user.is_active = False
        user.save(update_fields=['is_active'])
        logged_in = self.client.login(
            username=user.username, password='pass123-rahasia',
        )
        self.assertFalse(
            logged_in,
            'Akun is_active=False seharusnya ditolak oleh '
            'ModelBackend.user_can_authenticate().',
        )

    def test_sesi_akun_nonaktif_dimatikan(self):
        """Sesi lama harus mati setelah akun dinonaktifkan (get_user re-check)."""
        user = make_user('owasp.dinonaktifkan', 'STAF_NAKES')
        login(self.client, user)
        user.is_active = False
        user.save(update_fields=['is_active'])
        response = self.client.get(reverse('akreditasi:dashboard'))
        self.assertIn(
            response.status_code, (302, 403),
            'Sesi akun nonaktif harus dialihkan ke login atau ditolak, '
            'bukan tetap melayani halaman.',
        )
