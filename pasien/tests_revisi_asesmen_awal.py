from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, AsesmenRisikoKlinis
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()

class AsesmenAwalDetailTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dokter_asesmen', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='KEPALA_UNIT',
            unit_kerja=self.unit_igd
        )
        self.client.login(username='dokter_asesmen', password='password123')

        self.pasien = Pasien.objects.create(
            no_rm='RM-ASESMEN-001',
            nama_lengkap='Ny. Ani Rahayu',
            nik='3201234567890002',
            tanggal_lahir='1985-05-12',
            jenis_kelamin='P',
            alamat='Jl. Sehat Sejahtera No. 12',
            no_hp='081299887766'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-ASESMEN-001',
            jenis_kunjungan='IGD',
            status='TRIAGE',
            triage='KUNING',
            tanggal_masuk=timezone.now(),
            catatan_admisi='Nyeri perut kanan bawah mendadak sejak 6 jam lalu'
        )

    def test_kunjungan_detail_renders_asesmen_awal_above_cppt(self):
        """Asesmen Awal section must be rendered and positioned above CPPT in kunjungan_detail."""
        res = self.client.get(reverse('pasien:kunjungan_detail', kwargs={'pk': self.kunjungan.pk}))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('headingAsesmenAwal', content)
        self.assertIn('headingCppt', content)
        # Check position: headingAsesmenAwal appears BEFORE headingCppt
        pos_asesmen = content.find('headingAsesmenAwal')
        pos_cppt = content.find('headingCppt')
        self.assertGreater(pos_cppt, pos_asesmen, "Asesmen Awal must appear before CPPT")

    def test_kunjungan_detail_renders_head_to_toe_and_mst(self):
        """Asesmen Awal section includes MST Nutrition screening, Pain scale, and Head-To-Toe exam."""
        res = self.client.get(reverse('pasien:kunjungan_detail', kwargs={'pk': self.kunjungan.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Malnutrition Screening Tool')
        self.assertContains(res, 'PEMERIKSAAN FISIK HEAD-TO-TOE')
        self.assertContains(res, 'KEPALA &amp; LEHER')
        self.assertContains(res, 'DADA &amp; TORAKS')
        self.assertContains(res, 'ABDOMEN')
        self.assertContains(res, 'EKSTREMITAS')
        # Check that interactive checkboxes exist (tinggal mencentang)
        self.assertContains(res, 'kd_normo')
        self.assertContains(res, 'dt_simetris')
        self.assertContains(res, 'ab_datar')
        self.assertContains(res, 'ek_hangat')

    def test_igd_dashboard_modal_renders_interactive_checkboxes(self):
        """IGD dashboard Asesmen Awal modal renders interactive checklists per Word doc."""
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'aw_paten_')
        self.assertContains(res, 'br_spontan_')
        self.assertContains(res, 'cr_akral_h_')
        self.assertContains(res, 'ds_cm_')
        self.assertContains(res, 'ex_utuh_')

    def test_save_asesmen_awal_from_kunjungan_detail(self):
        """POST to igd_asesmen_awal_save with next_url redirects back to kunjungan_detail and updates fields."""
        url = reverse('pasien:igd_asesmen_awal_save', kwargs={'pk': self.kunjungan.pk})
        data = {
            'next_url': reverse('pasien:kunjungan_detail', kwargs={'pk': self.kunjungan.pk}),
            'keadaan_umum': 'Sedang',
            'kesadaran': 'Compos Mentis',
            'ttv_skala_nyeri': '5',
            'nyeri_karakteristik': 'Tajam/Tusuk',
            'skrining_gizi_mst': '2',
            'fungsional_adl': 'Mandiri',
            'status_psikososial': 'Tenang / Kooperatif',
            'anamnesis_rps': 'Nyeri tekan pada perut kanan bawah (McBurney sign positif)',
            'fisik_toraks': 'Simetris, vesikuler (+/+), murmur (-)',
            'fisik_abdomen': 'Supel, nyeri tekan RLQ (+), defens muskular (-)',
            'diagnosa_masuk': 'K35.8 - Apendisitis Akut',
            'diagnosa_keperawatan_sdki': 'D.0077 - Nyeri Akut',
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, 302)
        self.assertIn(f'/pasien/kunjungan/{self.kunjungan.pk}/', res.url)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.keadaan_umum, 'Sedang')
        self.assertEqual(self.kunjungan.kesadaran, 'Compos Mentis')
        self.assertEqual(self.kunjungan.nyeri_karakteristik, 'Tajam/Tusuk')
        self.assertEqual(self.kunjungan.fungsional_adl, 'Mandiri')
