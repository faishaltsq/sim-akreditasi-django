"""Regression tests for the ``admin_required`` gate in the akreditasi app.

``akreditasi/views.py:61-67``::

    def _is_admin(user):
        \"\"\"Admin RS atau Superuser.\"\"\"
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        p = getattr(user, 'profile', None)
        return p and p.role in ('SUPER_ADMIN', 'ADMIN_RS')

``admin_required = user_passes_test(_is_admin, login_url='/accounts/login/')``
guards six views::

    1356  unit_list_create
    1440  unit_edit
    1484  unit_delete
    1523  pokja_manage
    1533  profil_rs_view
    1577  audit_log_view

``STAF_NAKES`` is **not** in ``_is_admin``. It belongs to a different predicate,
``_is_nakes_or_admin`` (lines 83-90), which backs ``nakes_or_admin`` — used by
exactly one view, ``portal_nakes`` (line 1827).

So the boundary is: STAF_NAKES must be rejected (403) from every
``admin_required`` view and admitted only to ``portal_nakes``.

The one genuine weakness tested here is that ``admin_required`` is role-string
based: it never consults ``RolePermissionConfig`` or
``UserProfile.custom_permissions``, so revoking ``can_manage_units`` in the
Control Center does not close ``unit_edit``.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import Category, Framework, UnitKerja


class _AdminGateFixturesMixin:
    password = 'pass123-rahasia'

    def _make_user(self, username, role, *, unit=None):
        user = User.objects.create_user(
            username=username, email=f'{username}@rs.test', password=self.password
        )
        UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
        return user

    def _login(self, user):
        self.assertTrue(
            self.client.login(username=user.username, password=self.password),
            f'login gagal untuk {user.username}',
        )

    def _assert_denied(self, user, url, label):
        """Assert the caller is denied, with a precise failure message."""
        self._login(user)
        response = self.client.get(url)
        if response.status_code == 200:
            self.fail(
                f'KONTROL AKSES LEMAH: role {user.profile.role} berhasil membuka '
                f'{label} ({url}) dengan HTTP 200. View ini dijaga '
                '@admin_required (_is_admin = SUPER_ADMIN | ADMIN_RS).'
            )
        if response.status_code == 302:
            location = response.get('Location', '')
            self.assertIn(
                'login', location,
                f'{label} mengalihkan ke {location!r}; pengguna terautentikasi '
                'tetapi tidak berwenang seharusnya menerima 403.',
            )
        self.assertIn(response.status_code, (302, 403))


class StafNakesAdminGateTest(_AdminGateFixturesMixin, TestCase):
    """STAF_NAKES must be denied every admin_required view."""

    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Uji', code='GATE-UNIT', level=1)
        self.staf = self._make_user('staf.nakes', 'STAF_NAKES', unit=self.unit)
        self.framework = Framework.objects.create(name='STARKES-GATE', cycle_type='PDCA')

    def test_staf_nakes_denied_unit_list_create(self):
        self._assert_denied(
            self.staf, reverse('akreditasi:unit_list'), 'unit_list_create'
        )

    def test_staf_nakes_denied_unit_edit(self):
        self._assert_denied(
            self.staf,
            reverse('akreditasi:unit_edit', args=[self.unit.id]),
            'unit_edit',
        )

    def test_staf_nakes_denied_unit_delete(self):
        self._assert_denied(
            self.staf,
            reverse('akreditasi:unit_delete', args=[self.unit.id]),
            'unit_delete',
        )

    def test_staf_nakes_denied_pokja_manage(self):
        self._assert_denied(
            self.staf, reverse('akreditasi:pokja_manage'), 'pokja_manage'
        )

    def test_staf_nakes_denied_profil_rs(self):
        self._assert_denied(
            self.staf, reverse('akreditasi:profil_rs'), 'profil_rs_view'
        )

    def test_staf_nakes_denied_audit_log(self):
        self._assert_denied(
            self.staf, reverse('akreditasi:audit_log'), 'audit_log_view'
        )

    def test_staf_nakes_admitted_to_portal_nakes(self):
        """nakes_or_admin is the correct gate for STAF_NAKES — it must pass."""
        self._login(self.staf)
        response = self.client.get(reverse('akreditasi:portal_nakes'))
        self.assertNotIn(
            response.status_code, (403,),
            'STAF_NAKES harus diizinkan membuka portal_nakes melalui '
            '@nakes_or_admin',
        )
        self.assertIn(response.status_code, (200, 302))

    def test_asesor_denied_portal_nakes(self):
        """nakes_or_admin excludes ASESOR — negative control."""
        asesor = self._make_user('asesor.portal', 'ASESOR')
        self._assert_denied(
            asesor, reverse('akreditasi:portal_nakes'), 'portal_nakes'
        )


class NegativeControlAdminGateTest(_AdminGateFixturesMixin, TestCase):
    """KEPALA_UNIT and ASESOR must be denied the admin_required views."""

    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Neg', code='GATE-NEG', level=1)
        self.kepala = self._make_user('kepala.neg', 'KEPALA_UNIT', unit=self.unit)
        self.asesor = self._make_user('asesor.neg', 'ASESOR')

    def test_kepala_unit_denied_unit_edit(self):
        self._assert_denied(
            self.kepala,
            reverse('akreditasi:unit_edit', args=[self.unit.id]),
            'unit_edit',
        )

    def test_kepala_unit_denied_audit_log(self):
        self._assert_denied(
            self.kepala, reverse('akreditasi:audit_log'), 'audit_log_view'
        )

    def test_asesor_denied_unit_edit(self):
        self._assert_denied(
            self.asesor,
            reverse('akreditasi:unit_edit', args=[self.unit.id]),
            'unit_edit',
        )

    def test_asesor_denied_audit_log(self):
        self._assert_denied(
            self.asesor, reverse('akreditasi:audit_log'), 'audit_log_view'
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('akreditasi:unit_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.get('Location', ''))

    def test_admin_rs_is_admitted(self):
        """Positive control: ADMIN_RS is inside _is_admin."""
        admin_rs = self._make_user('admin.positif', 'ADMIN_RS')
        self._login(admin_rs)
        response = self.client.get(reverse('akreditasi:audit_log'))
        self.assertEqual(
            response.status_code, 200,
            'ADMIN_RS harus dapat membuka audit_log_view',
        )


class AdminGateBypassesPermissionConfigTest(_AdminGateFixturesMixin, TestCase):
    """admin_required ignores RolePermissionConfig — the role string wins."""

    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit RBAC', code='GATE-RBAC', level=1)
        self.admin_rs = self._make_user('admin.rbac', 'ADMIN_RS', unit=self.unit)

    def test_can_manage_units_false_does_not_close_unit_edit(self):
        """Flipping can_manage_units=False must actually deny access."""
        cfg = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        cfg.can_manage_units = False
        cfg.save()

        self.assertFalse(
            self.admin_rs.profile.has_permission('can_manage_units'),
            'prasyarat: can_manage_units harus False setelah diubah',
        )

        self._login(self.admin_rs)
        response = self.client.get(
            reverse('akreditasi:unit_edit', args=[self.unit.id])
        )
        if response.status_code == 200:
            self.fail(
                'IZIN DILEWATI: RolePermissionConfig.can_manage_units=False untuk '
                'ADMIN_RS, tetapi akreditasi:unit_edit tetap dapat dibuka '
                '(HTTP 200). @admin_required hanya memeriksa string role melalui '
                '_is_admin dan tidak pernah memanggil has_permission(), sehingga '
                'matriks izin di Pusat Kontrol tidak berpengaruh pada view ini. '
                'Perbaikan: ganti gate berbasis role menjadi user_passes_test('
                "lambda u: u.profile.has_permission('can_manage_units'))."
            )
        self.assertIn(response.status_code, (302, 403))

    def test_can_manage_units_false_does_not_close_unit_delete(self):
        """Same bypass on the destructive delete endpoint."""
        cfg = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        cfg.can_manage_units = False
        cfg.save()

        unit_pk = self.unit.pk
        self._login(self.admin_rs)
        response = self.client.post(
            reverse('akreditasi:unit_delete', args=[unit_pk])
        )
        if not UnitKerja.objects.filter(pk=unit_pk).exists():
            self.fail(
                'IZIN DILEWATI PADA OPERASI HAPUS: ADMIN_RS dengan '
                'can_manage_units=False berhasil menghapus unit kerja melalui '
                'akreditasi:unit_delete. Gate @admin_required tidak membaca '
                'matriks izin, sehingga pencabutan izin kelola unit di Pusat '
                'Kontrol tidak mencegah penghapusan data.'
            )
        self.assertIn(response.status_code, (302, 403))

    def test_authenticated_unauthorized_gets_403_not_redirect(self):
        """A logged-in but unauthorized user must see 403, not a login redirect."""
        outsider = self._make_user('tanpa.izin', 'ASESOR')
        self._login(outsider)
        response = self.client.get(
            reverse('akreditasi:unit_edit', args=[self.unit.id])
        )
        if response.status_code == 302:
            location = response.get('Location', '')
            if 'login' in location:
                self.fail(
                    'PENGALIHAN MENYESATKAN: pengguna yang sudah login tetapi '
                    'tidak berwenang dialihkan ke halaman login oleh '
                    '@admin_required (login_url="/accounts/login/"). '
                    'user_passes_test mengalihkan semua kegagalan ke login_url, '
                    'termasuk pengguna terautentikasi, sehingga kegagalan '
                    'otorisasi tampak seperti masalah sesi dan bukan 403.'
                )
        self.assertEqual(response.status_code, 403)
