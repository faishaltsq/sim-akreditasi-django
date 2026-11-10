from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from pasien.models import Pasien


class PasienKtpModelTest(TestCase):
    def test_pasien_foto_ktp_field_can_be_stored(self):
        dummy_image = SimpleUploadedFile(
            name='ktp_test.jpg',
            content=b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00',
            content_type='image/jpeg'
        )
        pasien = Pasien.objects.create(
            no_rm='RM-KTP-001',
            nik='3273010101900001',
            nama_lengkap='Budi Santoso KTP',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='L',
            foto_ktp=dummy_image
        )
        self.assertTrue(bool(pasien.foto_ktp))
        self.assertIn('pasien/ktp/', pasien.foto_ktp.name)
        self.assertTrue(pasien.foto_ktp.name.endswith('ktp_test.jpg'))
