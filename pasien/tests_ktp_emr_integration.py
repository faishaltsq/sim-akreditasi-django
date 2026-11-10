from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from pasien.models import Pasien, KunjunganPasien
from akreditasi.models import UnitKerja
from accounts.models import UserProfile


class KtpEmrIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dokter_emr', password='password123')
        self.unit_admisi, _ = UnitKerja.objects.get_or_create(
            code='ADMISI',
            defaults={'name': 'Unit Pendaftaran & Admisi', 'level': 3}
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='ADMIN_RS',
            unit_kerja=self.unit_admisi
        )
        self.client.login(username='dokter_emr', password='password123')

        foto = SimpleUploadedFile('ktp_test.jpg', b'\xff\xd8fakektp', content_type='image/jpeg')
        self.pasien = Pasien.objects.create(
            no_rm='RM-KTP-99',
            nik='3273016508900005',
            nama_lengkap='Siti KTP EMR',
            tanggal_lahir='1990-08-25',
            jenis_kelamin='P',
            foto_ktp=foto
        )
        self.kunjungan = KunjunganPasien.objects.create(
            no_kunjungan='KUNJ-KTP-99',
            pasien=self.pasien,
            jenis_kunjungan='IGD',
            penjamin='UMUM',
            status='DAFTAR',
            tanggal_masuk=timezone.now()
        )

    def test_pasien_detail_displays_ktp_and_skp1_badge(self):
        url = reverse('pasien:pasien_detail', kwargs={'pk': self.pasien.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('SKP 1', content)
        self.assertIn('KTP', content)

    def test_kunjungan_detail_displays_ktp_preview_trigger(self):
        url = reverse('pasien:kunjungan_detail', kwargs={'pk': self.kunjungan.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('modalLihatKtp', content)

    def test_cetak_formulir_pendaftaran_displays_mrmik_skp1_verification(self):
        url = reverse('pasien:cetak_formulir_pendaftaran', kwargs={'pk': self.kunjungan.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('SKP 1', content)
        self.assertIn('MRMIK', content)
