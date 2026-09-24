from django.test import TestCase, Client
from django.contrib.auth.models import User
from accounts.models import UserProfile, NakesCredential
from akreditasi.models import UnitKerja, QualityRecord, StandardItem, Category, Framework


class PortalNakesTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.framework = Framework.objects.create(name='STARKES', cycle_type='PDCA')
        self.category = Category.objects.create(framework=self.framework, code='SKP', name='Sasaran Keselamatan Pasien')
        self.item = StandardItem.objects.create(
            category=self.category,
            sub_standard='SKP 1',
            sub_title='Identifikasi Pasien',
            code='SKP 1 EP 1',
            description='Rumah sakit menerapkan proses identifikasi pasien yang tepat.'
        )
        self.unit_igd = UnitKerja.objects.create(name='Instalasi Gawat Darurat', code='IGD')
        self.unit_icu = UnitKerja.objects.create(name='Intensive Care Unit', code='ICU')
        self.record_igd = QualityRecord.objects.create(
            standard_item=self.item,
            unit=self.unit_igd,
            score=10,
            quality_target='Kepatuhan identifikasi 100%'
        )

        self.user_nakes = User.objects.create_user(username='perawat1', password='password123')
        self.profile_nakes = UserProfile.objects.create(
            user=self.user_nakes,
            role='STAF_NAKES',
            full_name='Ns. Ani Rahayu, S.Kep',
            profesi='PERAWAT',
            nip_nrp='199001012020012001',
            unit_kerja=self.unit_igd
        )

    def test_nakes_role_properties(self):
        self.assertTrue(self.profile_nakes.is_nakes)
        self.assertFalse(self.profile_nakes.can_manage_users)
        self.assertEqual(self.profile_nakes.role_level, 1)
        self.assertTrue(self.profile_nakes.can_upload)

    def test_portal_nakes_login_required(self):
        response = self.client.get('/portal-nakes/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_nakes_dashboard_redirects_to_portal(self):
        self.client.login(username='perawat1', password='password123')
        response = self.client.get('/')
        self.assertRedirects(response, '/portal-nakes/')

    def test_portal_nakes_renders_unit_data(self):
        self.client.login(username='perawat1', password='password123')
        response = self.client.get('/portal-nakes/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Instalasi Gawat Darurat')
        self.assertContains(response, 'SKP 1 EP 1')
        # Nakes ICU tidak boleh melihat data unit IGD ini
        self.assertNotContains(response, 'Intensive Care Unit')

    def test_nakes_credential_create(self):
        cred = NakesCredential.objects.create(
            user_profile=self.profile_nakes,
            doc_type='STR',
            title='STR Perawat — Ns. Ani',
            document_number='STR-TEST-001',
            status='PENDING'
        )
        self.assertEqual(cred.status, 'PENDING')
        self.assertEqual(self.profile_nakes.credentials.count(), 1)

    def test_rekap_kps_nakes_forbidden(self):
        self.client.login(username='perawat1', password='password123')
        response = self.client.get('/rekap-kps/')
        self.assertEqual(response.status_code, 403)
