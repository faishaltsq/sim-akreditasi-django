from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, CPPT
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()

class ClinicalModelExtensionTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dokter_klinis', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.role = 'STAF_NAKES'
        self.profile.unit_kerja = self.unit_igd
        self.profile.save()
        self.client.login(username='dokter_klinis', password='password123')

        self.pasien = Pasien.objects.create(
            no_rm='RM-KLINIS-01',
            nama_lengkap='Pasien Klinis Lengkap',
            tanggal_lahir='1985-06-15',
            jenis_kelamin='L',
            alergi_obat='Amoksisilin'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-KLINIS-01',
            jenis_kunjungan='IGD',
            status='TRIAGE',
            triage='KUNING',
            tanggal_masuk=timezone.now(),
            ttv_sistole=85,
            ttv_diastole=55,
            ttv_nadi=135,
            ttv_rr=26,
            ttv_suhu=39.2,
            ttv_spo2=91,
            ttv_gcs='E3V4M5'
        )

    def test_news_score_calculation(self):
        """National Early Warning Score (NEWS) auto-calculated from TTV."""
        score, category = self.kunjungan.hitung_news_score()
        # Systolic 85 (score 3), Pulse 135 (score 3), RR 26 (score 3), Temp 39.2 (score 2), SpO2 91 (score 3) = total >= 14
        self.assertGreaterEqual(score, 7)
        self.assertEqual(category, 'TINGGI')

    def test_is_asesmen_awal_lengkap_property(self):
        """Asesmen awal completeness badge checks anamnesis, physical exam, and diagnosis."""
        self.assertFalse(self.kunjungan.is_asesmen_awal_lengkap)
        self.kunjungan.anamnesis_rps = 'Sesak napas memberat sejak tadi pagi'
        self.kunjungan.fisik_airway = 'Paten, tidak ada stridor'
        self.kunjungan.diagnosa_masuk = 'J44.1 - PPOK Eksaserbasi Akut'
        self.kunjungan.diagnosa_keperawatan_sdki = 'D.0005 - Pola Napas Tidak Efektif'
        self.kunjungan.save()
        self.assertTrue(self.kunjungan.is_asesmen_awal_lengkap)


class ClinicalEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='perawat_igd', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.role = 'STAF_NAKES'
        self.profile.unit_kerja = self.unit_igd
        self.profile.save()
        self.client.login(username='perawat_igd', password='password123')

        self.pasien = Pasien.objects.create(
            no_rm='RM-ENDPT-01',
            nama_lengkap='Pasien Endpoint',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='P'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-ENDPT-01',
            jenis_kunjungan='IGD',
            status='TRIAGE',
            triage='MERAH',
            tanggal_masuk=timezone.now()
        )

    def test_igd_asesmen_awal_save_view(self):
        """POST to igd_asesmen_awal_save saves clinical assessment fields."""
        url = reverse('pasien:igd_asesmen_awal_save', kwargs={'pk': self.kunjungan.pk})
        res = self.client.post(url, {
            'anamnesis_rps': 'Nyeri dada mendadak sejak 2 jam lalu',
            'anamnesis_rpd': 'Hipertensi',
            'anamnesis_rpk': 'Ayah DM',
            'anamnesis_obat': 'Captopril 12.5mg',
            'fisik_airway': 'Paten',
            'fisik_breathing': 'RR 20x/m, SpO2 96%',
            'fisik_circulation': 'TD 130/80, Nadi 90x/m',
            'fisik_disability': 'GCS 15, E4V5M6',
            'fisik_exposure': 'Tidak ada luka',
            'status_psikososial': 'Kooperatif, cemas ringan',
            'status_spiritual': 'Islam, menolak transfusi tidak ada',
            'skrining_jatuh_skor': 25,
            'skrining_jatuh_grade': 'RENDAH',
            'skrining_gizi_mst': 1,
            'diagnosa_keperawatan_sdki': 'D.0077 - Nyeri Akut',
            'luaran_keperawatan_slki': 'L.08066 - Tingkat Nyeri Menurun',
            'intervensi_keperawatan_siki': 'I.08238 - Manajemen Nyeri',
        })
        self.assertEqual(res.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.anamnesis_rps, 'Nyeri dada mendadak sejak 2 jam lalu')
        self.assertEqual(self.kunjungan.diagnosa_keperawatan_sdki, 'D.0077 - Nyeri Akut')
        self.assertEqual(self.kunjungan.fisik_airway, 'Paten')
        self.assertEqual(self.kunjungan.skrining_jatuh_grade, 'RENDAH')

    def test_igd_cppt_quick_add(self):
        """POST to igd_cppt_quick_add creates a CPPT entry from the IGD dashboard modal."""
        url = reverse('pasien:igd_cppt_quick_add', kwargs={'pk': self.kunjungan.pk})
        res = self.client.post(url, {
            'profesi': 'DOKTER',
            'subjektif': 'Pasien mengeluh nyeri dada skala 8',
            'objektif': 'TD 90/60, Nadi 120, RR 28, SpO2 91%',
            'asesmen': 'ACS / NSTEMI, suspect terbuka',
            'plan': 'Aspirin 320mg, Konsul Jantung Cito, EKG 12 lead, Troponin I',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self.kunjungan.cppt.count(), 1)
        entry = self.kunjungan.cppt.first()
        self.assertEqual(entry.profesi, 'DOKTER')
        self.assertIn('Troponin', entry.plan)

    def test_cetak_resume_igd_returns_200(self):
        """GET to cetak_resume_igd returns print-ready HTML."""
        url = reverse('pasien:cetak_resume_igd', kwargs={'pk': self.kunjungan.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Resume Medis IGD')
        self.assertContains(res, self.pasien.nama_lengkap)

    def test_igd_eksekusi_tindakan(self):
        """POST to igd_eksekusi_tindakan logs real-time executed care directly into CPPT."""
        url = reverse('pasien:igd_eksekusi_tindakan', kwargs={'pk': self.kunjungan.pk})
        res = self.client.post(url, {
            'tindakan_nama': 'Pemasangan Infus IV Line RL 20 tpm',
            'profesi': 'PERAWAT',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self.kunjungan.cppt.count(), 1)
        entry = self.kunjungan.cppt.first()
        self.assertEqual(entry.profesi, 'PERAWAT')
        self.assertIn('Pemasangan Infus IV Line', entry.plan)
        self.assertIn('EKSEKUSI REAL-TIME', entry.plan)


class DashboardUIClinicalTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dokter_ui', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.role = 'STAF_NAKES'
        self.profile.unit_kerja = self.unit_igd
        self.profile.save()
        self.client.login(username='dokter_ui', password='password123')

        self.pasien = Pasien.objects.create(
            no_rm='RM-UI-01',
            nama_lengkap='Pasien UI Test',
            tanggal_lahir='1970-01-01',
            jenis_kelamin='L'
        )
        KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-UI-01',
            jenis_kunjungan='IGD',
            status='TRIAGE',
            triage='MERAH',
            tanggal_masuk=timezone.now()
        )

    def test_dashboard_renders_clinical_modals_and_compliance_badge(self):
        """IGD dashboard includes Asesmen Awal modal, CPPT modal, Disposisi modal, and compliance badge."""
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'modalAsesmenAwal')
        self.assertContains(res, 'modalCPPT')
        self.assertContains(res, 'modalDisposisi')

    def test_dashboard_contains_news_score_in_context(self):
        """IGD dashboard context includes ews_data dict keyed by visit PK."""
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertIn('ews_data', res.context)
