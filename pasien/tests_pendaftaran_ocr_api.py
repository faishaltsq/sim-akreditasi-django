import json
from unittest import mock
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from pasien.models import Pasien, KunjunganPasien
from akreditasi.models import UnitKerja
from accounts.models import UserProfile
from pasien.services import ktp_ocr


class PendaftaranOcrApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas_ocr', password='password123')
        self.unit_admisi, _ = UnitKerja.objects.get_or_create(
            code='ADMISI',
            defaults={'name': 'Unit Pendaftaran & Admisi', 'level': 3}
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='ADMIN_RS',
            unit_kerja=self.unit_admisi
        )
        self.client.login(username='petugas_ocr', password='password123')

    def _enable_ai(self):
        from akreditasi.system_models import SystemConfig
        config = SystemConfig.get_solo()
        config.ai_enabled = True
        config.ai_api_key = 'sk-test-key-12345'
        config.save()

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_api_ocr_ktp_multipart_upload_returns_extracted_json(self, mock_ai):
        self._enable_ai()
        mock_ai.return_value = {
            'success': True,
            'data': {
                'nik': '3273016508900002',
                'nama': 'Siti Rahmawati',
                'tempat_lahir': 'Bandung',
                'tanggal_lahir': '1990-08-25',
                'gender': 'P',
                'golongan_darah': 'O',
                'alamat': 'Jl. Riau No. 123',
                'rt_rw': '004/002',
                'kelurahan': 'Cihapit',
                'kecamatan': 'Bandung Wetan',
                'kota_kabupaten': 'Kota Bandung',
                'provinsi': 'Jawa Barat',
                'agama': 'ISLAM',
                'status_perkawinan': 'MENIKAH',
                'pekerjaan': 'Wiraswasta'
            },
            'error': None
        }

        image = SimpleUploadedFile('ktp.jpg', b'\xff\xd8fakektpimage', content_type='image/jpeg')
        url = reverse('pasien:api_ocr_ktp')
        res = self.client.post(url, {'foto_ktp': image})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['nik'], '3273016508900002')
        self.assertEqual(data['data']['nama_lengkap'], 'SITI RAHMAWATI')
        self.assertEqual(data['data']['jenis_kelamin'], 'P')
        self.assertEqual(data['data']['tempat_lahir'], 'Bandung')
        self.assertEqual(data['data']['tanggal_lahir_mdy'], '08/25/1990')
        self.assertEqual(data['data']['kelurahan'], 'Cihapit')
        self.assertFalse(data['is_existing_patient'])

    def test_api_cek_nik_detects_existing_and_new_patient(self):
        # Create an existing patient
        Pasien.objects.create(
            no_rm='RM-EXIST-01',
            nik='3273011505900001',
            nama_lengkap='Budi Lama',
            tanggal_lahir='1990-05-15',
            jenis_kelamin='L'
        )

        url = reverse('pasien:api_cek_nik')

        # 1. Existing NIK
        res_exist = self.client.get(url + '?nik=3273011505900001')
        self.assertEqual(res_exist.status_code, 200)
        d_exist = res_exist.json()
        self.assertTrue(d_exist['valid'])
        self.assertTrue(d_exist['exists'])
        self.assertEqual(d_exist['pasien']['no_rm'], 'RM-EXIST-01')

        # 2. New NIK
        res_new = self.client.get(url + '?nik=3273016508900002')
        self.assertEqual(res_new.status_code, 200)
        d_new = res_new.json()
        self.assertTrue(d_new['valid'])
        self.assertFalse(d_new['exists'])
        self.assertEqual(d_new['decoded']['nama_provinsi'], 'Jawa Barat')

    def test_kunjungan_baru_saves_foto_ktp_and_flexible_date(self):
        image = SimpleUploadedFile('ktp_baru.jpg', b'\xff\xd8ktpbytes', content_type='image/jpeg')
        payload = {
            'is_pasien_baru': '1',
            'nama_lengkap': 'Agus KTP Baru',
            'nik': '3201011005850005',
            'tempat_lahir': 'Bogor',
            'tanggal_lahir': '05/10/85',  # MM/DD/YY flexible manual input
            'jenis_kelamin': 'L',
            'agama': 'ISLAM',
            'status_perkawinan': 'MENIKAH',
            'pendidikan_terakhir': 'SD_SMP_SMA',
            'pekerjaan': 'PNS',
            'alamat': 'Jl. Pajajaran No. 10',
            'penjamin': 'UMUM',
            'catatan_admisi': 'Pusing sejak kemarin',
            'jenis_kunjungan': 'IGD',
            'foto_ktp': image,
        }
        res = self.client.post(reverse('pasien:kunjungan_baru'), payload, follow=True)
        self.assertEqual(res.status_code, 200)

        p = Pasien.objects.filter(nik='3201011005850005').first()
        self.assertIsNotNone(p)
        self.assertEqual(p.nama_lengkap, 'Agus KTP Baru')
        # Verify flexible date parsed correctly into 1985-05-10
        self.assertEqual(p.tanggal_lahir.year, 1985)
        self.assertEqual(p.tanggal_lahir.month, 5)
        self.assertEqual(p.tanggal_lahir.day, 10)
        # Verify foto_ktp is stored
        self.assertTrue(bool(p.foto_ktp))
        self.assertIn('pasien/ktp/', p.foto_ktp.name)
