from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from pasien.models import Pasien, KunjunganPasien, GeneralConsentRawatInap

class GeneralConsentTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('nakes1', 'nakes@rs.com', 'pass123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-GC-001',
            nama_lengkap='Ahmad Fauzi',
            tanggal_lahir='1980-04-12',
            jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-RANAP-GC01',
            jenis_kunjungan='RANAP',
            tanggal_masuk=timezone.now(),
            status='RANAP'
        )

    def test_create_general_consent(self):
        consent = GeneralConsentRawatInap.objects.create(
            kunjungan=self.kunjungan,
            nama_pj='Nurul Hidayah',
            nik_pj='3301019902880001',
            hubungan='SUAMI_ISTRI',
            telepon_pj='081234567890',
            alamat_pj='Jl. Merdeka No. 45 Semarang',
            setuju_perawatan_umum=True,
            setuju_pelepasan_informasi=True,
            setuju_tata_tertib=True,
            jaminan_biaya='BPJS',
            petugas_saksi=self.user
        )
        self.assertTrue(consent.is_lengkap)
        self.assertEqual(consent.kunjungan.pasien.nama_lengkap, 'Ahmad Fauzi')
