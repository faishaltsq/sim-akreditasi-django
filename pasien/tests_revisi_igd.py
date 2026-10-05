from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, OrderPenunjang
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()

class IGDDashboardRevisiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dokter_igd', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.role = 'STAF_NAKES'
        self.profile.unit_kerja = self.unit_igd
        self.profile.save()
        self.client.login(username='dokter_igd', password='password123')

        self.pasien1 = Pasien.objects.create(
            no_rm='RM-IGD-01',
            nama_lengkap='Pasien Merah Kritis',
            tanggal_lahir='1980-01-01',
            jenis_kelamin='L'
        )
        self.kunjungan1 = KunjunganPasien.objects.create(
            pasien=self.pasien1,
            no_kunjungan='KUNJ-IGD-01',
            jenis_kunjungan='IGD',
            status='TRIAGE',
            triage='MERAH',
            tanggal_masuk=timezone.now(),
            ttv_sistole=90,
            ttv_diastole=60,
            ttv_nadi=120,
            ttv_rr=28,
            ttv_suhu=38.5,
            ttv_spo2=91,
            ttv_gcs='E3V4M5',
            ttv_skala_nyeri=8
        )

        self.pasien_hitam = Pasien.objects.create(
            no_rm='RM-IGD-02',
            nama_lengkap='Pasien Expectant P4',
            tanggal_lahir='1975-05-05',
            jenis_kelamin='P'
        )
        self.kunjungan_hitam = KunjunganPasien.objects.create(
            pasien=self.pasien_hitam,
            no_kunjungan='KUNJ-IGD-02',
            jenis_kunjungan='IGD',
            status='TRIAGE',
            triage='HITAM',
            tanggal_masuk=timezone.now()
        )

    def test_igd_dashboard_triage_hitam_filter(self):
        """Filtering by triage=HITAM should return the black triage patient and exclude red."""
        res = self.client.get(reverse('pasien:igd_dashboard') + '?triage=HITAM')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Pasien Expectant P4')
        self.assertNotContains(res, 'Pasien Merah Kritis')
        self.assertContains(res, 'Hitam (1)')

    def test_igd_dashboard_vital_signs_render(self):
        """Dashboard renders full vital signs: HR, RR, Suhu, SpO2, GCS, Skala Nyeri."""
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '90/60')
        self.assertContains(res, '120') # Nadi
        self.assertContains(res, '28')  # RR
        self.assertTrue('38.5' in res.content.decode('utf-8') or '38,5' in res.content.decode('utf-8'))
        self.assertContains(res, '91%') # SpO2
        self.assertContains(res, 'E3V4M5') # GCS

    def test_igd_ttv_update_saves_all_parameters(self):
        """POST to igd_ttv_update saves all 7 vital signs plus ICD fields."""
        url = reverse('pasien:igd_ttv_update', kwargs={'pk': self.kunjungan_hitam.pk})
        post_data = {
            'ttv_sistole': 130,
            'ttv_diastole': 85,
            'ttv_nadi': 78,
            'ttv_rr': 18,
            'ttv_suhu': 36.8,
            'ttv_spo2': 98,
            'ttv_gcs': '15',
            'ttv_skala_nyeri': 2,
            'icd9_tindakan': '99.04',
            'diagnosa_masuk': 'I10 - Hipertensi Esensial',
        }
        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 302)
        self.kunjungan_hitam.refresh_from_db()
        self.assertEqual(self.kunjungan_hitam.ttv_sistole, 130)
        self.assertEqual(self.kunjungan_hitam.ttv_diastole, 85)
        self.assertEqual(self.kunjungan_hitam.ttv_nadi, 78)
        self.assertEqual(self.kunjungan_hitam.ttv_rr, 18)
        self.assertEqual(float(self.kunjungan_hitam.ttv_suhu), 36.8)
        self.assertEqual(self.kunjungan_hitam.ttv_spo2, 98)
        self.assertEqual(self.kunjungan_hitam.ttv_gcs, '15')
        self.assertEqual(self.kunjungan_hitam.ttv_skala_nyeri, 2)
        self.assertEqual(self.kunjungan_hitam.icd9_tindakan, '99.04')
        self.assertEqual(self.kunjungan_hitam.diagnosa_masuk, 'I10 - Hipertensi Esensial')

    def test_critical_value_alert_rendered(self):
        """If patient has an order with is_critical_value=True, table should show critical badge."""
        OrderPenunjang.objects.create(
            kunjungan=self.kunjungan1,
            jenis='LAB',
            nama_pemeriksaan='Troponin I Kuantitatif',
            status='SELESAI',
            hasil_pemeriksaan='0.85 ng/mL (CRITICAL HIGH)',
            is_critical_value=True
        )
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'CRITICAL')

    def test_critical_value_auto_upgrades_triage_to_merah(self):
        """Revisi 02: Ordering a critical-value penunjang on non-MERAH patient auto-upgrades triage."""
        # Create a KUNING patient
        pasien_k = Pasien.objects.create(no_rm='RM-IGD-KUNING', nama_lengkap='Pasien Kuning', tanggal_lahir='1990-03-15', jenis_kelamin='L')
        kunjungan_k = KunjunganPasien.objects.create(
            pasien=pasien_k, no_kunjungan='KUNJ-IGD-KUNING',
            jenis_kunjungan='IGD', status='TRIAGE', triage='KUNING', tanggal_masuk=timezone.now()
        )
        url = reverse('pasien:order_penunjang_buat', kwargs={'pk': kunjungan_k.pk})
        res = self.client.post(url, {
            'jenis': 'LAB',
            'nama_pemeriksaan': 'Troponin I (CITO)',
            'prioritas': 'CITO',
            'is_critical_value': '1',
            'critical_value_catatan': 'Troponin 1.2 ng/mL TINGGI',
        })
        self.assertEqual(res.status_code, 302)
        kunjungan_k.refresh_from_db()
        self.assertEqual(kunjungan_k.triage, 'MERAH', 'Triage harus di-upgrade ke MERAH saat critical value diorder')

    def test_igd_dashboard_contains_bed_matrix(self):
        """Revisi 02: IGD dashboard should pass bed_matrix context and render bed panel."""
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('bed_matrix', res.context)

    def test_igd_dashboard_pemeriksaan_presets_in_context(self):
        """Revisi 02: pemeriksaan_presets context should contain LAB and RADIOLOGI lists."""
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('pemeriksaan_presets', res.context)
        presets = res.context['pemeriksaan_presets']
        self.assertIn('LAB', presets)
        self.assertIn('RADIOLOGI', presets)
        self.assertGreater(len(presets['LAB']), 5)
        self.assertGreater(len(presets['RADIOLOGI']), 5)
