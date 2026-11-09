from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from pasien.models import Pasien, KunjunganPasien


class MorseFallScaleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='perawat.igd', password='password123')
        self.unit_igd = UnitKerja.objects.filter(code='IGD').first()
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Morse Test',
            no_rm='RM-MFS-001',
            tanggal_lahir='1980-01-01',
            jenis_kelamin='L',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-MFS-001',
            jenis_kunjungan='IGD',
            unit_kerja=self.unit_igd,
            tanggal_masuk=timezone.now(),
            status='ASESMEN',
        )
        self.client.force_login(self.user)

    def test_morse_inputs_rendered_in_igd_dashboard(self):
        resp = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-morse-group')
        self.assertContains(resp, 'name="jatuh_riwayat"')
        self.assertContains(resp, 'name="jatuh_infus"')
        self.assertContains(resp, 'name="jatuh_alat"')
        self.assertContains(resp, 'hitungMorse')

    def test_morse_inputs_rendered_in_full_page_wizard(self):
        url = reverse('pasien:kunjungan_asesmen_awal', kwargs={'pk': self.kunjungan.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-morse-group')
        self.assertContains(resp, 'hitungMorse')

    def test_morse_post_persists_detail_and_grade(self):
        url = reverse('pasien:igd_asesmen_awal_save', kwargs={'pk': self.kunjungan.pk})
        data = {
            'anamnesis_rps': 'Pasien jatuh dari tangga 2 hari lalu',
            'skrining_jatuh_skor': '55',
            'skrining_jatuh_grade': 'TINGGI',
            'jatuh_riwayat': '1',
            'jatuh_diagnosis': '1',
            'jatuh_alat': '0',
            'jatuh_infus': '1',
            'jatuh_jalan': '0',
            'jatuh_mental': '0',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)

        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.skrining_jatuh_skor, 55)
        self.assertEqual(self.kunjungan.skrining_jatuh_grade, 'TINGGI')
        self.assertEqual(self.kunjungan.skrining_jatuh_detail.get('jatuh_riwayat'), 1)
        self.assertEqual(self.kunjungan.skrining_jatuh_detail.get('jatuh_infus'), 1)
