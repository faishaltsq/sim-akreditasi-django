from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from pasien.models import KunjunganPasien, Pasien
from accounts.models import UserProfile
from akreditasi.models import UnitKerja

User = get_user_model()


class DiagnosaPickerTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dokter_picker', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='DOKTER',
            unit_kerja=self.unit_igd
        )
        self.client.login(username='dokter_picker', password='password123')

    def test_api_sdki_search(self):
        response = self.client.get(reverse('pasien:api_sdki') + '?q=nyeri')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any('Nyeri' in item['nama'] for item in data))

    def test_igd_ttv_update_saves_both_diagnoses(self):
        import datetime
        from django.utils import timezone
        pasien = Pasien.objects.create(nama_lengkap='Pasien Uji Diagnosa', no_rm='RM-998811', tanggal_lahir=datetime.date(1990, 1, 1))
        k = KunjunganPasien.objects.create(
            pasien=pasien,
            jenis_kunjungan='IGD',
            status='DAFTAR',
            tanggal_masuk=timezone.now()
        )
        url = reverse('pasien:igd_ttv_update', kwargs={'pk': k.pk})
        post_data = {
            'ttv_sistole': 120,
            'ttv_diastole': 80,
            'ttv_nadi': 80,
            'ttv_rr': 20,
            'ttv_suhu': 38.0,
            'ttv_spo2': 98,
            'ttv_gcs': '15',
            'ttv_skala_nyeri': 8,
            'diagnosa_masuk': 'A01.0 - Demam Tifoid',
            'diagnosa_keperawatan_sdki': 'D.0130 - Hipertermia',
            'icd9_tindakan': 'Pasang Infus RL',
        }
        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 302)
        k.refresh_from_db()
        self.assertEqual(k.diagnosa_masuk, 'A01.0 - Demam Tifoid')
        self.assertEqual(k.diagnosa_keperawatan_sdki, 'D.0130 - Hipertermia')
        self.assertEqual(k.icd9_tindakan, 'Pasang Infus RL')

    def test_igd_dashboard_renders_datalists(self):
        response = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="globalIcd10List"')
        self.assertContains(response, 'id="globalSdkiList"')
        self.assertContains(response, 'D.0077 - Nyeri Akut')
        self.assertContains(response, 'I10 - Hipertensi Esensial')
