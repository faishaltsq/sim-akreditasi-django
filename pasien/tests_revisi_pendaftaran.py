from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, Bed, Ruangan
from akreditasi.models import UnitKerja
from accounts.models import UserProfile
import json

User = get_user_model()

class PendaftaranRevisiBackendTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='petugas_admisi', password='password123')
        self.unit_admisi, _ = UnitKerja.objects.get_or_create(code='ADMISI', defaults={'name': 'Unit Pendaftaran & Admisi', 'level': 3})
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.role = 'STAF_NAKES'
        self.profile.unit_kerja = self.unit_admisi
        self.profile.save()
        self.client.login(username='petugas_admisi', password='password123')

        self.pasien = Pasien.objects.create(
            no_rm='RM-TEST-001',
            nama_lengkap='Budi Santoso',
            nik='3301010101900001',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-TEST-001',
            jenis_kunjungan='RAJAL',
            poliklinik='POLI_PD',
            status='DAFTAR',
            tanggal_masuk=timezone.now(),
            nomor_antrean='A-001'
        )

    def test_fast_track_igd_creation(self):
        """Emergency desk can admit an urgent patient with minimal info in <1 step."""
        post_data = {
            'nama_pasien': 'Pasien Trauma Kritis',
            'jenis_kelamin': 'L',
            'estimasi_usia': 35,
            'triage': 'MERAH',
            'keluhan': 'Kecelakaan lalu lintas, penurunan kesadaran'
        }
        res = self.client.post(reverse('pasien:fast_track_igd'), post_data)
        self.assertEqual(res.status_code, 302)
        kunj = KunjunganPasien.objects.filter(pasien__nama_lengkap='Pasien Trauma Kritis').first()
        self.assertIsNotNone(kunj)
        self.assertEqual(kunj.jenis_kunjungan, 'IGD')
        self.assertEqual(kunj.triage, 'MERAH')
        self.assertIn('Kecelakaan', kunj.catatan_admisi)

    def test_api_cek_bpjs(self):
        """Mock BPJS verification endpoint returns eligibility, hak rawat, and active status."""
        res = self.client.get(reverse('pasien:api_cek_bpjs') + '?no_kartu=0001234567890&nik=3301010101900001')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['status'])
        self.assertIn('peserta', data)
        self.assertIn('hak_kelas', data['peserta'])
        self.assertEqual(data['peserta']['status_peserta'], 'AKTIF')

    def test_kunjungan_batal(self):
        """Admission staff can cancel a mistakenly created visit."""
        url = reverse('pasien:kunjungan_batal', kwargs={'pk': self.kunjungan.pk})
        res = self.client.post(url, {'alasan_batal': 'Pasien batal berobat'})
        self.assertEqual(res.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status, 'BATAL')
        self.assertIn('batal berobat', self.kunjungan.catatan_admisi)

    def test_cetak_tracer(self):
        """Cetak tracer slip renders printable patient routing card."""
        url = reverse('pasien:cetak_tracer', kwargs={'pk': self.kunjungan.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'TRACER REKAM MEDIS')
        self.assertContains(res, 'RM-TEST-001')
        self.assertContains(res, 'Budi Santoso')
        self.assertContains(res, 'A-001')
