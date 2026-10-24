"""Verifikasi /control/ (Integrated Control) render untuk semua role."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.models import UnitKerja


class KontrolRenderTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        unit = UnitKerja.objects.create(
            code='KTRL-RENDER', name='Control render fixture',
            level=2, is_active=True,
        )
        cls.users = {}
        for role, _label in UserProfile.ROLE_CHOICES:
            user = User.objects.create_user(username='control-render-' + role.lower())
            UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
            cls.users[role] = user
        cls.superuser = User.objects.create_superuser(
            username='control-render-superuser', email='control-render@example.test',
        )
        UserProfile.objects.create(
            user=cls.superuser, role='SUPER_ADMIN', unit_kerja=unit,
        )

    def test_hub_render_untuk_semua_role(self):
        url = reverse('akreditasi:kontrol_hub')
        gagal = []
        diperiksa = 0
        for role, user in self.users.items():
            self.client.force_login(user)
            try:
                r = self.client.get(url)
            except Exception as exc:
                gagal.append('%s -> %s: %s' % (role, type(exc).__name__, str(exc)[:200]))
                continue
            diperiksa += 1
            if r.status_code >= 500:
                gagal.append('%s -> %s' % (role, r.status_code))
        self.assertGreater(diperiksa, 0)
        self.assertEqual(gagal, [], 'role gagal render /control/:\n' + '\n'.join(gagal))

    def test_subdasbor_render(self):
        if not self.superuser:
            self.skipTest('tidak ada superuser')
        self.client.force_login(self.superuser)
        gagal = []
        for nama in ('kontrol_risiko', 'kontrol_emr', 'kontrol_dokumen'):
            r = self.client.get(reverse('akreditasi:' + nama))
            if r.status_code >= 500:
                gagal.append('%s -> %s' % (nama, r.status_code))
        self.assertEqual(gagal, [], 'sub-dasbor gagal: %s' % gagal)

    def test_tidak_ada_filter_property_di_orm(self):
        """`tercapai` adalah @property, bukan kolom — filter ORM harus gagal jelas."""
        from akreditasi.risiko_models import CatatanIndikator
        with self.assertRaises(Exception):
            list(CatatanIndikator.objects.filter(tercapai=True))
