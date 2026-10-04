from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()


class SidebarPatientVisibilityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.unit_lab, _ = UnitKerja.objects.get_or_create(
            code='LAB-BDRS', defaults={'name': 'Laboratorium', 'level': 3}
        )
        self.user_lab = User.objects.create_user('analis_vis', 'analisvis@rs.id', 'pass123')
        profile, _ = UserProfile.objects.get_or_create(user=self.user_lab)
        profile.role = 'STAF_NAKES'
        profile.profesi = 'ANALIS_LAB'
        profile.unit_kerja = self.unit_lab
        profile.save()

    def _get_dashboard(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('akreditasi:dashboard'))

    def test_lab_sidebar_shows_laboratorium(self):
        resp = self._get_dashboard(self.user_lab)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Laboratorium')

    def test_lab_sidebar_hides_pendaftaran(self):
        resp = self._get_dashboard(self.user_lab)
        self.assertNotContains(resp, 'Pendaftaran &amp; Admisi')

    def test_lab_sidebar_hides_igd(self):
        resp = self._get_dashboard(self.user_lab)
        self.assertNotContains(resp, 'Gawat Darurat (IGD)')

    def test_lab_sidebar_hides_rajal(self):
        resp = self._get_dashboard(self.user_lab)
        self.assertNotContains(resp, 'Poli Rawat Jalan')

    def test_lab_sidebar_hides_ranap(self):
        resp = self._get_dashboard(self.user_lab)
        self.assertNotContains(resp, 'Rawat Inap &amp; Bed')

    def test_superadmin_sees_all_menus(self):
        admin = User.objects.create_superuser('supervis', 'supervis@rs.id', 'pass123')
        UserProfile.objects.get_or_create(user=admin)
        resp = self._get_dashboard(admin)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Pendaftaran')
        self.assertContains(resp, 'Laboratorium')
