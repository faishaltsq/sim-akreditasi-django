from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

class PasienModelExpansionTest(TestCase):
    def test_pasien_demographic_and_emergency_contact_fields(self):
        p = Pasien.objects.create(
            no_rm="RM-2026-0001",
            nik="3201234567890001",
            nama_lengkap="Budi Santoso",
            tempat_lahir="Bandung",
            tanggal_lahir="1990-05-15",
            jenis_kelamin="L",
            agama="ISLAM",
            status_perkawinan="MENIKAH",
            pendidikan_terakhir="S1",
            pekerjaan="PNS",
            alamat="Jl. Merdeka No. 10",
            rt_rw="002/005",
            kelurahan="Babakan",
            kecamatan="Coblong",
            kota_kabupaten="Bandung",
            provinsi="Jawa Barat",
            no_hp="081234567890",
            email="budi@example.com",
            nama_pj="Siti Aminah",
            hubungan_pj="Istri",
            no_hp_pj="081298765432",
            alamat_pj="Jl. Merdeka No. 10",
        )
        self.assertEqual(p.tempat_lahir, "Bandung")
        self.assertEqual(p.agama, "ISLAM")
        self.assertEqual(p.status_perkawinan, "MENIKAH")
        self.assertEqual(p.pendidikan_terakhir, "S1")
        self.assertEqual(p.pekerjaan, "PNS")
        self.assertEqual(p.rt_rw, "002/005")
        self.assertEqual(p.kelurahan, "Babakan")
        self.assertEqual(p.kecamatan, "Coblong")
        self.assertEqual(p.kota_kabupaten, "Bandung")
        self.assertEqual(p.provinsi, "Jawa Barat")
        self.assertEqual(p.email, "budi@example.com")
        self.assertEqual(p.nama_pj, "Siti Aminah")
        self.assertEqual(p.hubungan_pj, "Istri")
        self.assertEqual(p.no_hp_pj, "081298765432")
        self.assertEqual(p.alamat_pj, "Jl. Merdeka No. 10")


class AutoNumberGenerationTest(TestCase):
    def test_generate_no_rm_format_and_sequence(self):
        from pasien.models import generate_no_rm
        rm1 = generate_no_rm()
        self.assertTrue(rm1.startswith("RM-"))
        p1 = Pasien.objects.create(
            no_rm=rm1,
            nama_lengkap="Pasien 1",
            tanggal_lahir="1990-01-01",
            jenis_kelamin="L"
        )
        rm2 = generate_no_rm()
        self.assertNotEqual(rm1, rm2)

    def test_generate_no_kunjungan_format(self):
        from pasien.models import generate_no_kunjungan
        kunj_no = generate_no_kunjungan(jenis='IGD')
        self.assertTrue(kunj_no.startswith("IGD-") or kunj_no.startswith("KUNJ-"))


class ApiCariPasienTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas_cari', password='password123')
        self.client.login(username='petugas_cari', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm="RM-001099",
            nik="3273010101900001",
            nama_lengkap="Ahmad Dahlan",
            tanggal_lahir="1990-01-01",
            jenis_kelamin="L",
            no_hp="0811223344",
            no_bpjs="00012345678",
            alamat="Jl. Ahmad Yani No. 12"
        )

    def test_search_by_rm(self):
        res = self.client.get(reverse('pasien:api_cari_pasien') + '?q=001099')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['nama_lengkap'], "Ahmad Dahlan")
        self.assertEqual(data['results'][0]['no_rm'], "RM-001099")

    def test_search_by_nama(self):
        res = self.client.get(reverse('pasien:api_cari_pasien') + '?q=Ahmad')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['results'][0]['no_rm'], "RM-001099")


class PendaftaranDuaKotakFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admisi_flow', password='password123')
        self.client.login(username='admisi_flow', password='password123')
        self.pasien_lama = Pasien.objects.create(
            no_rm="RM-LAMA-001",
            nik="3201000000000001",
            nama_lengkap="Haji Sulaiman",
            tanggal_lahir="1975-03-10",
            jenis_kelamin="L"
        )

    def test_daftar_pasien_lama_auto_kunjungan(self):
        payload = {
            'pasien_id': self.pasien_lama.pk,
            'jenis_kunjungan': 'IGD',
            'triage': 'KUNING',
            'dpjp': 'dr. Jaga IGD',
            'penjamin': 'BPJS',
            'catatan_admisi': 'Sesak napas mendadak',
            'general_consent': '1',
        }
        res = self.client.post(reverse('pasien:kunjungan_baru'), payload, follow=True)
        self.assertEqual(res.status_code, 200)
        k = KunjunganPasien.objects.filter(pasien=self.pasien_lama).first()
        self.assertIsNotNone(k)
        self.assertTrue(k.no_kunjungan.startswith("IGD-"))
        self.assertEqual(k.triage, 'KUNING')
        self.assertEqual(k.catatan_admisi, 'Sesak napas mendadak')

    def test_daftar_pasien_baru_atomic_creation(self):
        payload = {
            'is_pasien_baru': '1',
            'nama_lengkap': 'Dewi Lestari',
            'nik': '3201998877660001',
            'tempat_lahir': 'Surabaya',
            'tanggal_lahir': '1995-08-20',
            'jenis_kelamin': 'P',
            'agama': 'ISLAM',
            'status_perkawinan': 'BELUM_MENIKAH',
            'pendidikan_terakhir': 'S1_S2_S3',
            'pekerjaan': 'Karyawan Swasta',
            'alamat': 'Jl. Diponegoro No. 45',
            'rt_rw': '003/001',
            'kelurahan': 'Wonokromo',
            'kecamatan': 'Wonokromo',
            'kota_kabupaten': 'Surabaya',
            'provinsi': 'Jawa Timur',
            'no_hp': '081233445566',
            'email': 'dewi@example.com',
            'penjamin': 'BPJS',
            'no_bpjs': '000987654321',
            'nama_pj': 'Bambang Sudarmono',
            'hubungan_pj': 'Orang Tua',
            'no_hp_pj': '081299887766',
            'alamat_pj': 'Jl. Diponegoro No. 45',
            'catatan_admisi': 'Demam tinggi 3 hari dan mual',
            'jenis_kunjungan': 'RAJAL',
            'poliklinik': 'POLI_PENYAKIT_DALAM',
            'dpjp': 'dr. Budi Santoso, Sp.PD',
        }
        res = self.client.post(reverse('pasien:kunjungan_baru'), payload, follow=True)
        self.assertEqual(res.status_code, 200)
        p = Pasien.objects.filter(nik='3201998877660001').first()
        self.assertIsNotNone(p)
        self.assertEqual(p.nama_lengkap, 'Dewi Lestari')
        self.assertEqual(p.nama_pj, 'Bambang Sudarmono')
        self.assertTrue(p.no_rm.startswith("RM-"))
        self.assertEqual(p.kunjungan.count(), 1)
        k = p.kunjungan.first()
        self.assertEqual(k.jenis_kunjungan, 'RAJAL')
        self.assertEqual(k.poliklinik, 'POLI_PENYAKIT_DALAM')
        self.assertEqual(k.catatan_admisi, 'Demam tinggi 3 hari dan mual')


class PendaftaranDuaKotakTemplateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='staff_reg', password='password123')
        self.unit_admisi, _ = UnitKerja.objects.get_or_create(code='ADMISI', defaults={'name': 'Unit Pendaftaran & Admisi', 'level': 3})
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='KEPALA_UNIT',
            unit_kerja=self.unit_admisi
        )
        self.client.login(username='staff_reg', password='password123')

    def test_pendaftaran_dashboard_renders_two_boxes(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'PASIEN LAMA')
        self.assertContains(res, 'PASIEN BARU')
        self.assertContains(res, 'inputCariPasienLama')
        self.assertContains(res, 'IDENTITAS PRIBADI PASIEN')
        self.assertContains(res, 'PENANGGUNG JAWAB PASIEN')




