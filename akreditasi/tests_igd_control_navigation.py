from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()


class IGDControlNavigationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='admin_igd', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(
            code='IGD',
            defaults={'name': 'Instalasi Gawat Darurat', 'level': 3}
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.role = 'SUPER_ADMIN'
        self.profile.unit_kerja = self.unit_igd
        self.profile.save()
        self.client.login(username='admin_igd', password='password123')

    def test_alur_pelayanan_igd_routes_exist(self):
        routes = [
            '/control/igd/triage/',
            '/control/igd/asesmen-ppa/',
            '/control/igd/penunjang/',
            '/control/igd/tindakan/',
            '/control/igd/disposisi/',
            '/control/igd/administrasi/',
        ]
        for r in routes:
            res = self.client.get(r)
            self.assertIn(res.status_code, (200, 302), f"Route {r} failed with status {res.status_code}")

    def test_mutu_logbook_igd_routes_exist(self):
        routes = [
            '/control/igd/logbook/',
            '/control/igd/triage-audit/',
            '/control/igd/indicators/',
            '/control/igd/inventory/',
            '/control/igd/handover/',
        ]
        for r in routes:
            res = self.client.get(r)
            self.assertIn(res.status_code, (200, 302), f"Route {r} failed with status {res.status_code}")
