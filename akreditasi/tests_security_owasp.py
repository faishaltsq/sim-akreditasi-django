"""OWASP Top 10 (2021) security tests — akreditasi app.

Mencakup A01 Broken Access Control pada gate ``admin_required``:

- ``akreditasi/views.py:63-70`` — ``_is_admin`` mengembalikan True hanya untuk
  ``is_superuser`` atau ``role in ('SUPER_ADMIN', 'ADMIN_RS')``. STAF_NAKES dan
  ASESOR **tidak** termasuk, jadi unit CRUD, pokja, profil RS, dan log audit
  menolak mereka.
- ``admin_required`` sepenuhnya berbasis string peran: ia tidak pernah membaca
  ``RolePermissionConfig`` atau ``custom_permissions``. Mencabut
  ``can_manage_units`` di Pusat Kontrol karena itu tidak menutup ``unit_edit``.

Catatan perilaku: ``admin_required`` dibangun dari ``user_passes_test``
(``akreditasi/views.py:93``), yang mengalihkan pengguna gagal uji ke halaman
login (HTTP 302) alih-alih mengembalikan 403 — termasuk pengguna yang sudah
terautentikasi. Assertion di bawah menerima keduanya sebagai bentuk penolakan,
selama bukan 200.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import RolePermissionConfig
from akreditasi.tests_utils import login, make_unit, make_user


class UnitEditAdminGateTest(TestCase):
    """Batas ``admin_required``: STAF_NAKES/KEPALA_UNIT/ASESOR ditolak, ADMIN_RS masuk.

    Test ini memaku pelindung yang sudah benar; semuanya harus LULUS.
    """

    def setUp(self):
        self.unit = make_unit('OWASP-UNIT', 'Unit OWASP', level=2)
        self.staf = make_user('owasp.staf', 'STAF_NAKES', unit=self.unit, profesi='PERAWAT')
        self.kepala = make_user('owasp.kepala', 'KEPALA_UNIT', unit=self.unit)
        self.asesor = make_user('owasp.asesor', 'ASESOR')
        self.admin_rs = make_user('owasp.adminrs', 'ADMIN_RS')

    def _assert_denied(self, user, url_name, *args):
        """Pengguna tanpa wewenang tidak boleh mendapat 200 (302-ke-login atau 403)."""
        login(self.client, user)
        response = self.client.get(reverse(url_name, args=args))
        self.assertNotEqual(
            response.status_code, 200,
            f'{url_name} tidak boleh melayani {user.profile.role} dengan 200.',
        )
        self.assertIn(
            response.status_code, (302, 403),
            f'{url_name} harus menolak {user.profile.role} dengan 302/403, '
            f'bukan {response.status_code}.',
        )
        if response.status_code == 302:
            self.assertIn(
                'login', response.get('Location', ''),
                f'{url_name} mengalihkan {user.profile.role} ke halaman non-login.',
            )
        self.client.logout()

    def test_staf_nakes_ditolak_unit_list(self):
        self._assert_denied(self.staf, 'akreditasi:unit_list')

    def test_staf_nakes_ditolak_unit_edit(self):
        self._assert_denied(self.staf, 'akreditasi:unit_edit', self.unit.id)

    def test_staf_nakes_ditolak_unit_delete(self):
        self._assert_denied(self.staf, 'akreditasi:unit_delete', self.unit.id)

    def test_staf_nakes_ditolak_pokja_manage(self):
        self._assert_denied(self.staf, 'akreditasi:pokja_manage')

    def test_staf_nakes_ditolak_audit_log(self):
        self._assert_denied(self.staf, 'akreditasi:audit_log')

    def test_kepala_unit_ditolak_unit_edit(self):
        self._assert_denied(self.kepala, 'akreditasi:unit_edit', self.unit.id)

    def test_asesor_ditolak_audit_log(self):
        self._assert_denied(self.asesor, 'akreditasi:audit_log')

    def test_admin_rs_diizinkan_unit_list(self):
        login(self.client, self.admin_rs)
        response = self.client.get(reverse('akreditasi:unit_list'))
        self.assertEqual(
            response.status_code, 200,
            'ADMIN_RS harus dapat membuka unit_list.',
        )


class AdminGateIgnoresPermissionConfigTest(TestCase):
    """``admin_required`` mengabaikan RolePermissionConfig (A01).

    Mencabut ``can_manage_units`` untuk ADMIN_RS di Pusat Kontrol tidak menutup
    ``unit_edit``/``unit_delete``, karena ``_is_admin`` (views.py:63-70) hanya
    memeriksa string peran. Ini kerentanan nyata: matriks izin yang dikelola
    admin tidak mengikat gate ini.
    """

    def setUp(self):
        self.unit = make_unit('OWASP-PERMCFG', 'Unit PermCfg', level=2)
        self.admin_rs = make_user('owasp.permcfg.admin', 'ADMIN_RS')
        cfg = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        cfg.can_manage_units = False
        cfg.save(update_fields=['can_manage_units'])
        login(self.client, self.admin_rs)

    def test_can_manage_units_false_tetap_dapat_membuka_unit_edit(self):
        """ADMIN_RS tanpa can_manage_units masih dapat membuka unit_edit."""
        response = self.client.get(
            reverse('akreditasi:unit_edit', args=[self.unit.id])
        )
        if response.status_code == 200:
            self.fail(
                'GATE RBAC TIDAK MENGIKAT MATRIKS IZIN: ADMIN_RS dengan '
                'can_manage_units=False di RolePermissionConfig tetap dapat '
                'membuka akreditasi:unit_edit (HTTP 200). admin_required '
                "berbasis string peran ('SUPER_ADMIN'/'ADMIN_RS') dan tidak "
                'pernah memanggil has_permission(), sehingga mencabut '
                'can_manage_units di Pusat Kontrol tidak menutup unit CRUD. '
                'Perbaikan: jadikan admin_required memeriksa '
                'profile.has_permission("can_manage_units").'
            )
        self.assertIn(response.status_code, (302, 403))


class AuditLogAdminOnlyTest(TestCase):
    """``audit_log_view`` (akreditasi/views.py:1578) hanya untuk admin."""

    def setUp(self):
        self.staf = make_user('owasp.audit.staf', 'STAF_NAKES')
        self.admin_rs = make_user('owasp.audit.admin', 'ADMIN_RS')

    def test_staf_nakes_ditolak(self):
        login(self.client, self.staf)
        response = self.client.get(reverse('akreditasi:audit_log'))
        self.assertNotEqual(response.status_code, 200)
        self.assertIn(response.status_code, (302, 403))

    def test_admin_rs_diizinkan(self):
        login(self.client, self.admin_rs)
        response = self.client.get(reverse('akreditasi:audit_log'))
        self.assertEqual(response.status_code, 200)
