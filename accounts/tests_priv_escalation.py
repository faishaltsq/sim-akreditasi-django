"""Regression tests for vertical privilege escalation in the accounts app.

Covers three attack surfaces identified in the authorization review:

1. ``user_create`` / ``user_edit`` accept ``role='SUPER_ADMIN'`` from any caller
   who passes ``admin_only`` (is_superuser OR profile.can_manage_users). An
   ADMIN_RS holds ``can_manage_users=True``, so it can mint a superuser.
2. ``update_user_custom_permissions`` is gated only by ``control_center_access``
   and writes an arbitrary ``custom_permissions`` JSON blob onto *any* user id,
   including the caller's own profile.
3. ``update_role_permissions`` / ``reset_role_permissions`` are likewise gated
   only by ``control_center_access``; the ``LOCKOUT_SAFE_PERMS`` skip applies
   solely to ``role_code == 'SUPER_ADMIN'``, so a non-superuser control-center
   holder can flip every other role's permissions.

Tests that demonstrate a live vulnerability assert the *current* behaviour and
then ``self.fail(...)`` with an Indonesian description, so the weakness
surfaces in CI instead of passing silently. Tests that pin a guard which is
already correct use ordinary assertions.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    LOCKOUT_SAFE_PERMS,
    PERMISSION_DEFAULTS,
    RolePermissionConfig,
    UserProfile,
)


class _AccountFixturesMixin:
    """Shared user factory for the escalation suites."""

    password = 'pass123-rahasia'

    def _make_user(self, username, role, *, unit=None, can_manage_users=None,
                   can_access_control_center=None):
        """Create a user with a profile, optionally pinning role permissions."""
        user = User.objects.create_user(
            username=username, email=f'{username}@rs.test', password=self.password
        )
        profile = UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
        if role == 'SUPER_ADMIN':
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=['is_staff', 'is_superuser'])

        overrides = {}
        if can_manage_users is not None:
            overrides['can_manage_users'] = can_manage_users
        if can_access_control_center is not None:
            overrides['can_access_control_center'] = can_access_control_center
        if overrides:
            cfg = RolePermissionConfig.get_config_for_role(role)
            for field, value in overrides.items():
                setattr(cfg, field, value)
            cfg.save()
        return user

    def _login(self, user):
        self.assertTrue(
            self.client.login(username=user.username, password=self.password),
            f'login gagal untuk {user.username}',
        )


class UserCreateRoleEscalationTest(_AccountFixturesMixin, TestCase):
    """ADMIN_RS must not be able to mint a SUPER_ADMIN through user_create."""

    def setUp(self):
        self.admin_rs = self._make_user(
            'admin.rs', 'ADMIN_RS',
            can_manage_users=True,
            can_access_control_center=True,
        )

    def _create_payload(self, username, role):
        """POST payload matching UserCreateForm + UserProfileForm field names.

        UserCreateForm.Meta.fields = username, first_name, last_name, email,
        password1, password2. UserProfileForm.Meta.fields = role, full_name,
        jabatan, nip_nrp, profesi, telepon, unit_kerja, pokja_access,
        is_active_member.
        """
        return {
            'username': username,
            'first_name': 'Escalated',
            'last_name': 'Account',
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

    def test_admin_rs_cannot_create_super_admin(self):
        """ADMIN_RS POSTing role=SUPER_ADMIN must not produce is_superuser=True."""
        self._login(self.admin_rs)
        response = self.client.post(
            reverse('accounts:user_create'),
            self._create_payload('escalated.super', 'SUPER_ADMIN'),
        )
        # The view redirects to user_list on success.
        self.assertIn(response.status_code, (200, 302), 'user_create tidak merespons')

        created = User.objects.filter(username='escalated.super').first()
        if created is None:
            # Escalation was rejected outright — the guard holds.
            self.assertIsNone(created)
            return

        if created.is_superuser or created.is_staff:
            self.fail(
                'ESKALASI HAK AKSES: ADMIN_RS (can_manage_users=True) berhasil '
                'membuat akun dengan role=SUPER_ADMIN melalui accounts:user_create, '
                f'sehingga akun "{created.username}" mendapat is_superuser='
                f'{created.is_superuser} dan is_staff={created.is_staff}. '
                'user_create hanya dijaga admin_only (is_superuser OR '
                'can_manage_users) dan tidak memvalidasi bahwa pemanggil berhak '
                'menetapkan role SUPER_ADMIN. Perbaikan: batasi penetapan role '
                'SUPER_ADMIN hanya untuk is_superuser.'
            )
        # Escalation rejected but the account was still created with a lesser role.
        self.assertFalse(created.is_superuser)

    def test_admin_rs_cannot_escalate_via_user_edit(self):
        """ADMIN_RS editing an existing account to SUPER_ADMIN must be blocked."""
        victim = self._make_user('calon.super', 'STAF_NAKES')
        self._login(self.admin_rs)
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
                'ESKALASI HAK AKSES: ADMIN_RS berhasil mengubah akun '
                f'"{victim.username}" menjadi SUPER_ADMIN melalui '
                'accounts:user_edit (is_superuser=%s, role=%s). '
                'user_edit menetapkan is_staff/is_superuser langsung dari '
                'profile.role tanpa memeriksa apakah pemanggil adalah superuser.'
                % (victim.is_superuser, victim.profile.role)
            )
        self.assertFalse(victim.is_superuser)


class UserDeleteEscalationTest(_AccountFixturesMixin, TestCase):
    """user_delete only blocks self-deletion — an ADMIN_RS can delete a SUPER_ADMIN."""

    def setUp(self):
        self.admin_rs = self._make_user(
            'admin.penghapus', 'ADMIN_RS',
            can_manage_users=True,
            can_access_control_center=True,
        )
        self.super_admin = self._make_user('super.target', 'SUPER_ADMIN')

    def test_admin_rs_cannot_delete_super_admin(self):
        """Deleting a higher-privileged account must be blocked."""
        self._login(self.admin_rs)
        response = self.client.post(
            reverse('accounts:user_delete', args=[self.super_admin.id])
        )
        self.assertIn(response.status_code, (200, 302), 'user_delete tidak merespons')

        still_exists = User.objects.filter(pk=self.super_admin.pk).exists()
        if not still_exists:
            self.fail(
                'ESKALASI HAK AKSES (PENGHAPUSAN): ADMIN_RS berhasil menghapus '
                f'akun SUPER_ADMIN "{self.super_admin.username}" melalui '
                'accounts:user_delete. View hanya mencegah penghapusan akun '
                'sendiri (target_user == request.user) dan tidak membandingkan '
                'tingkat hierarki peran, sehingga admin tingkat bawah dapat '
                'melumpuhkan akun superuser (denial of administration).'
            )
        self.assertTrue(still_exists)

    def test_admin_rs_cannot_delete_another_admin_rs(self):
        """Peer-admin deletion is likewise unguarded."""
        peer = self._make_user('admin.sejawat', 'ADMIN_RS', can_manage_users=True)
        self._login(self.admin_rs)
        self.client.post(reverse('accounts:user_delete', args=[peer.id]))
        if not User.objects.filter(pk=peer.pk).exists():
            self.fail(
                'PENGHAPUSAN AKUN SEJAWAT: ADMIN_RS berhasil menghapus sesama '
                'ADMIN_RS melalui accounts:user_delete. Tidak ada pemeriksaan '
                'hierarki peran maupun perlindungan akun admin terakhir.'
            )
        self.assertTrue(User.objects.filter(pk=peer.pk).exists())

    def test_self_delete_is_blocked(self):
        """Pinning the guard that does exist."""
        self._login(self.admin_rs)
        self.client.post(reverse('accounts:user_delete', args=[self.admin_rs.id]))
        self.assertTrue(
            User.objects.filter(pk=self.admin_rs.pk).exists(),
            'penghapusan akun sendiri seharusnya ditolak',
        )


class CustomPermissionWriteTest(_AccountFixturesMixin, TestCase):
    """custom_permissions is an unvalidated JSON blob writable for any user id."""

    def setUp(self):
        self.cc_holder = self._make_user(
            'kontrol.holder', 'KOORDINATOR_POKJA',
            can_access_control_center=True,
            can_manage_users=False,
        )
        self.victim = self._make_user('staf.biasa', 'STAF_NAKES')

    def _url(self, user):
        return reverse('accounts:update_user_custom_permissions', args=[user.id])

    def test_control_center_holder_can_grant_manage_users_to_other(self):
        """Writing can_manage_users=True onto a low-privilege account."""
        self._login(self.cc_holder)
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
                f'("{self.cc_holder.username}") berhasil menulis '
                'custom_permissions {"can_manage_users": true} ke akun '
                f'"{self.victim.username}" melalui '
                'accounts:update_user_custom_permissions. Endpoint hanya dijaga '
                'control_center_access dan tidak memvalidasi kunci izin maupun '
                'hak pemanggil atas akun target. Perbaikan: whitelist kunci izin '
                'dan tolak pemberian izin yang melebihi izin pemberi.'
            )
        self.assertFalse(granted)

    def test_control_center_holder_can_grant_permissions_to_self(self):
        """Self-grant: writing can_manage_users=True onto the caller's profile."""
        self._login(self.cc_holder)
        before = self.cc_holder.profile.has_permission('can_manage_users')
        response = self.client.post(
            self._url(self.cc_holder),
            data='{"custom_permissions": {"can_manage_users": true}}',
            content_type='application/json',
        )
        self.assertIn(response.status_code, (200, 400), 'endpoint tidak merespons')

        self.cc_holder.profile.refresh_from_db()
        after = self.cc_holder.profile.has_permission('can_manage_users')
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

    def test_unknown_permission_keys_are_rejected(self):
        """Arbitrary JSON keys must not be silently persisted."""
        self._login(self.cc_holder)
        self.client.post(
            self._url(self.victim),
            data='{"custom_permissions": {"can_teleport": true, "__proto__": 1}}',
            content_type='application/json',
        )
        self.victim.profile.refresh_from_db()
        stored = self.victim.profile.custom_permissions or {}
        if 'can_teleport' in stored or '__proto__' in stored:
            self.fail(
                'VALIDASI IZIN KOSONG: custom_permissions menerima kunci izin '
                f'tidak dikenal tanpa validasi (tersimpan: {sorted(stored)}). '
                'custom_permissions adalah JSONField bebas; tidak ada whitelist '
                'kunci, sehingga kunci salah ketik atau berbahaya tetap '
                'tersimpan dan ikut dievaluasi oleh has_permission().'
            )
        self.assertNotIn('can_teleport', stored)


class RolePermissionTamperTest(_AccountFixturesMixin, TestCase):
    """A non-superuser control-center holder must not rewrite the role matrix."""

    def setUp(self):
        self.cc_holder = self._make_user(
            'tamper.holder', 'ADMIN_RS',
            can_access_control_center=True,
            can_manage_users=True,
        )

    def test_non_super_admin_cannot_flip_lockout_safe_perm(self):
        """LOCKOUT_SAFE_PERMS must be immutable for every role, not just SUPER_ADMIN."""
        cfg = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        before = cfg.can_manage_system_settings
        self._login(self.cc_holder)
        response = self.client.post(
            reverse('accounts:update_role_permissions'),
            data='{"ADMIN_RS": {"can_manage_system_settings": true}}',
            content_type='application/json',
        )
        self.assertIn(response.status_code, (200, 400), 'endpoint tidak merespons')

        cfg.refresh_from_db()
        after = cfg.can_manage_system_settings
        if after != before:
            self.fail(
                'PENYALAHGUNAAN MATRIKS IZIN: pemegang can_access_control_center '
                f'("{self.cc_holder.username}", role ADMIN_RS) berhasil mengubah '
                f'can_manage_system_settings untuk role ADMIN_RS dari {before} '
                f'menjadi {after} melalui accounts:update_role_permissions. '
                'Skip LOCKOUT_SAFE_PERMS hanya berlaku untuk '
                "role_code == 'SUPER_ADMIN', sehingga izin kunci untuk role lain "
                'dapat diubah oleh siapa pun yang bisa membuka Pusat Kontrol.'
            )
        self.assertEqual(after, before)

    def test_non_super_admin_cannot_grant_control_center_to_staf_nakes(self):
        """STAF_NAKES must not be promoted into the Control Center."""
        cfg = RolePermissionConfig.get_config_for_role('STAF_NAKES')
        before = cfg.can_access_control_center
        self._login(self.cc_holder)
        response = self.client.post(
            reverse('accounts:update_role_permissions'),
            data='{"STAF_NAKES": {"can_access_control_center": true}}',
            content_type='application/json',
        )
        self.assertIn(response.status_code, (200, 400), 'endpoint tidak merespons')

        cfg.refresh_from_db()
        after = cfg.can_access_control_center
        if after and not before:
            self.fail(
                'ESKALASI PERAN MASAL: pemegang can_access_control_center '
                'berhasil memberi can_access_control_center kepada seluruh role '
                'STAF_NAKES melalui accounts:update_role_permissions. Setiap staf '
                'nakes kemudian dapat membuka Pusat Kontrol Admin dan mengubah '
                'matriks izin lebih lanjut.'
            )
        self.assertEqual(after, before)

    def test_reset_role_permissions_requires_control_center(self):
        """reset_role_permissions must reject a caller without Control Center."""
        outsider = self._make_user(
            'tanpa.kontrol', 'STAF_NAKES',
            can_access_control_center=False,
        )
        self._login(outsider)
        response = self.client.post(reverse('accounts:reset_role_permissions'))
        self.assertIn(
            response.status_code, (302, 403),
            'reset_role_permissions harus mengalihkan atau menolak',
        )
        if response.status_code == 302 and 'login' not in response.get('Location', ''):
            self.fail(
                'KONTROL AKSES LEMAH: pengguna tanpa can_access_control_center '
                'berhasil memanggil accounts:reset_role_permissions dan diarahkan '
                'ke halaman sukses, bukan 403.'
            )

    def test_super_admin_lockout_safe_perms_survive_tamper_attempt(self):
        """SUPER_ADMIN keeps its lockout-safe permissions after a tamper POST."""
        self._login(self.cc_holder)
        self.client.post(
            reverse('accounts:update_role_permissions'),
            data='{"SUPER_ADMIN": {"can_manage_users": false, '
                 '"can_access_control_center": false}}',
            content_type='application/json',
        )
        cfg = RolePermissionConfig.get_config_for_role('SUPER_ADMIN')
        for perm in LOCKOUT_SAFE_PERMS:
            self.assertTrue(
                getattr(cfg, perm),
                f'LOCKOUT_SAFE_PERMS "{perm}" untuk SUPER_ADMIN terhapus',
            )

    def test_defaults_are_restorable(self):
        """reset_to_defaults must reproduce PERMISSION_DEFAULTS exactly."""
        self._login(self.cc_holder)
        self.client.post(reverse('accounts:reset_role_permissions'))
        for role, defaults in PERMISSION_DEFAULTS.items():
            cfg = RolePermissionConfig.get_config_for_role(role)
            for field, expected in defaults.items():
                self.assertEqual(
                    getattr(cfg, field), expected,
                    f'default {role}.{field} tidak pulih setelah reset',
                )
