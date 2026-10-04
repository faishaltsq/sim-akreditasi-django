from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()


class PatientRouteRBACTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.unit_lab, _ = UnitKerja.objects.get_or_create(
            code='LAB-BDRS', defaults={'name': 'Laboratorium', 'level': 3}
        )
        self.user_lab = User.objects.create_user('analis_sec', 'analis@rs.id', 'pass123')
        profile, _ = UserProfile.objects.get_or_create(user=self.user_lab)
        profile.role = 'STAF_NAKES'
        profile.profesi = 'ANALIS_LAB'
        profile.unit_kerja = self.unit_lab
        profile.save()

    def test_lab_user_blocked_from_igd(self):
        self.client.force_login(self.user_lab)
        resp = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(resp.status_code, 403)

    def test_lab_user_blocked_from_rajal(self):
        self.client.force_login(self.user_lab)
        resp = self.client.get(reverse('pasien:rajal_dashboard'))
        self.assertEqual(resp.status_code, 403)

    def test_lab_user_blocked_from_pendaftaran(self):
        self.client.force_login(self.user_lab)
        resp = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(resp.status_code, 403)

    def test_lab_user_blocked_from_bed_management(self):
        self.client.force_login(self.user_lab)
        resp = self.client.get(reverse('pasien:bed_management'))
        self.assertEqual(resp.status_code, 403)

    def test_lab_user_blocked_from_farmasi(self):
        self.client.force_login(self.user_lab)
        resp = self.client.get(reverse('pasien:farmasi_antrean'))
        self.assertEqual(resp.status_code, 403)

    def test_lab_user_can_access_laboratorium(self):
        self.client.force_login(self.user_lab)
        resp = self.client.get(reverse('pasien:laboratorium_dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_superadmin_can_access_all(self):
        admin = User.objects.create_superuser('supertest', 'super@rs.id', 'pass123')
        UserProfile.objects.get_or_create(user=admin)
        self.client.force_login(admin)
        for name in ['igd_dashboard', 'rajal_dashboard', 'pendaftaran_dashboard', 'bed_management', 'farmasi_antrean', 'laboratorium_dashboard']:
            resp = self.client.get(reverse(f'pasien:{name}'))
            self.assertIn(resp.status_code, [200, 302], msg=f'{name} should be accessible by superadmin')
