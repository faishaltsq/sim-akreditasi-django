from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, DPJP_CHOICES
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()

class DPJPSelectionTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='petugas_admisi', password='password123')
        self.unit_admisi, _ = UnitKerja.objects.get_or_create(code='ADMISI', defaults={'name': 'Unit Pendaftaran & Admisi', 'level': 3})
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='KEPALA_UNIT',
            unit_kerja=self.unit_admisi
        )
        self.client.login(username='petugas_admisi', password='password123')

        self.pasien = Pasien.objects.create(
            no_rm='RM-FORM-001',
            nama_lengkap='Siti Aminah',
            nik='3201234567890001',
            tanggal_lahir='1988-08-17',
            jenis_kelamin='P',
            alamat='Jl. Merdeka No. 45 RT 02/03',
            no_hp='081234567890',
            no_bpjs='0001234567890',
            alergi_obat='Amoxicillin'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-FORM-001',
            jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            dpjp='dr. Faisal, Sp.JP',
            penjamin='BPJS',
            tanggal_masuk=timezone.now(),
            catatan_admisi='Nyeri dada kiri menjalar'
        )

    def test_pendaftaran_dashboard_contains_dpjp_choices(self):
        """Pendaftaran dashboard context contains dpjp_choices list with cardiologist."""
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('dpjp_choices', res.context)
        self.assertContains(res, 'dr. Faisal, Sp.JP')

    def test_kunjungan_baru_contains_dpjp_choices(self):
        """Kunjungan baru context contains dpjp_choices."""
        res = self.client.get(reverse('pasien:kunjungan_baru'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('dpjp_choices', res.context)
        self.assertContains(res, 'dr. Faisal, Sp.JP')

    def test_cetak_formulir_pendaftaran_view(self):
        """Official registration form A4 printable view returns 200 and prefilled data."""
        url = reverse('pasien:cetak_formulir_pendaftaran', kwargs={'pk': self.kunjungan.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'FORMULIR PENDAFTARAN PASIEN')
        self.assertContains(res, 'SITI AMINAH')
        self.assertContains(res, 'nik-box')
        self.assertContains(res, 'dr. Faisal, Sp.JP')
        self.assertContains(res, 'Poli Jantung &amp; Pembuluh Darah')

    def test_pendaftaran_dashboard_renders_print_button_and_dpjp_select(self):
        """Pendaftaran dashboard renders select for DPJP and Cetak Formulir button."""
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'dpjpSelect')
        self.assertContains(res, 'cetak-formulir-pendaftaran')
