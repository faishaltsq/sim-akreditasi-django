from django.test import TestCase, Client
from django.contrib.auth.models import User
from accounts.models import UserProfile, NakesCredential
from akreditasi.models import UnitKerja, QualityRecord, StandardItem, Category, Framework


class PortalNakesTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.framework, _ = Framework.objects.get_or_create(name='STARKES', defaults={'cycle_type': 'PDCA'})
        self.category, _ = Category.objects.get_or_create(framework=self.framework, code='SKP', defaults={'name': 'Sasaran Keselamatan Pasien'})
        self.item, _ = StandardItem.objects.get_or_create(
            code='SKP 1 EP 1',
            defaults={
                'category': self.category,
                'sub_standard': 'SKP 1',
                'sub_title': 'Identifikasi Pasien',
                'description': 'Rumah sakit menerapkan proses identifikasi pasien yang tepat.'
            }
        )
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat'})
        self.unit_icu, _ = UnitKerja.objects.get_or_create(code='ICU', defaults={'name': 'Intensive Care Unit'})
        self.record_igd, _ = QualityRecord.objects.get_or_create(
            standard_item=self.item,
            defaults={
                'unit': self.unit_igd,
                'score': 10,
                'quality_target': 'Kepatuhan identifikasi 100%'
            }
        )
        if self.record_igd.unit != self.unit_igd:
            self.record_igd.unit = self.unit_igd
            self.record_igd.save()

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

    def test_nakes_dashboard_accessible_with_unit_scope(self):
        self.client.login(username='perawat1', password='password123')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

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
