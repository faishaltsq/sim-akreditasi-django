"""Phase 3 tests — IGD Fast-Track terisolasi (BL-01, RSK-APM-01)."""
import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import KunjunganPasien, LogRisikoApm, Pasien


class IgdFastTrackTest(TestCase):
    url = reverse('pasien:apm_api_igd_fasttrack')

    def post(self, **data):
        return self.client.post(self.url, data, content_type='application/json')

    def test_nama_wajib_diisi(self):
        response = self.post(nama_lengkap='   ')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Nama pasien wajib', response.json()['message'])

    def test_hanya_nama_cukup_untuk_mendaftar(self):
        response = self.post(nama_lengkap='Pasien Darurat')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['jenis_kunjungan'], 'IGD')
        self.assertEqual(data['triage'], 'MERAH')
        self.assertTrue(data['nomor_antrean'].startswith('IGD-'))

        kunjungan = KunjunganPasien.objects.get(no_kunjungan__startswith='REG-IGD-')
        self.assertEqual(kunjungan.jenis_kunjungan, 'IGD')
        self.assertEqual(kunjungan.flag_khusus, 'KRITIS')
        self.assertEqual(kunjungan.triage, 'MERAH')
        self.assertEqual(kunjungan.status_antrean, 'MENUNGGU')
        self.assertTrue(kunjungan.is_apm)
        self.assertEqual(kunjungan.poliklinik, 'IGD')

    def test_tidak_menyentuh_bridging_rujukan_maupun_biometrik(self):
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan', side_effect=AssertionError('rujukan tidak boleh divalidasi')):
            with patch('pasien.services.bpjs_vclaim.terbitkan_sep', side_effect=AssertionError('SEP tidak boleh diterbitkan')):
                response = self.post(nama_lengkap='Pasien Darurat')
        self.assertEqual(response.status_code, 200)

    def test_mencatat_rsk_apm_01(self):
        response = self.post(nama_lengkap='Pasien Darurat')
        self.assertEqual(response.status_code, 200)
        kunjungan = KunjunganPasien.objects.latest('pk')
        log = LogRisikoApm.objects.get(kode_risiko='RSK-APM-01')
        self.assertEqual(log.kanal, 'KIOSK')
        self.assertEqual(log.pemicu, 'IGD_FASTTRACK')
        self.assertEqual(log.severity, 'KRITIS')
        self.assertEqual(log.kunjungan_id, kunjungan.pk)

    def test_durasi_registrasi_diukur(self):
        response = self.post(nama_lengkap='Pasien Darurat')
        data = response.json()
        self.assertIn('durasi_registrasi_detik', data)
        self.assertLess(data['durasi_registrasi_detik'], 120)
        self.assertTrue(data['target_terpenuhi'])
        kunjungan = KunjunganPasien.objects.latest('pk')
        self.assertIsNotNone(kunjungan.registrasi_mulai_at)
        self.assertIsNotNone(kunjungan.registrasi_selesai_at)

    def test_pasien_lama_dipakai_ulang_lewat_nik(self):
        pasien = Pasien.objects.create(
            no_rm='RM-IGD-LAMA', nama_lengkap='Budi Darurat',
            tanggal_lahir=datetime.date(1980, 1, 1), jenis_kelamin='L',
            nik='3201234567899999', no_bpjs='0009998887776',
        )
        response = self.post(nama_lengkap='Budi Darurat', no_bpjs='0009998887776')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Pasien.objects.filter(nik='3201234567899999').count(), 1)
        kunjungan = KunjunganPasien.objects.latest('pk')
        self.assertEqual(kunjungan.pasien_id, pasien.pk)
        self.assertEqual(kunjungan.catatan_admisi, 'REGISTRASI_DARURAT')

    def test_nama_berbeda_dengan_data_terdaftar_ditandai(self):
        Pasien.objects.create(
            no_rm='RM-IGD-BEDA', nama_lengkap='Nama Terdaftar',
            tanggal_lahir=datetime.date(1980, 1, 1), jenis_kelamin='L',
            no_bpjs='0009998887775',
        )
        response = self.post(nama_lengkap='Nama Berbeda', no_bpjs='0009998887775')
        self.assertEqual(response.status_code, 200)
        kunjungan = KunjunganPasien.objects.latest('pk')
        self.assertEqual(kunjungan.catatan_admisi, 'REGISTRASI_DARURAT_IDENTITAS_MINIMAL')
        log = LogRisikoApm.objects.get(kode_risiko='RSK-APM-01')
        self.assertFalse(log.detail['identitas_terverifikasi'])

    def test_penjamin_bpjs_bila_ada_nomor_bpjs(self):
        response = self.post(nama_lengkap='Pasien Darurat', no_bpjs='0001234567890')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(KunjunganPasien.objects.latest('pk').penjamin, 'BPJS')

    def test_metode_selain_post_ditolak(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_csrf_diwajibkan(self):
        client = self.client_class(enforce_csrf_checks=True)
        response = client.post(self.url, {'nama_lengkap': 'Tanpa CSRF'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_struk_url_bertanda_tangan(self):
        response = self.post(nama_lengkap='Pasien Darurat')
        struk = response.json()['struk_url']
        self.assertIn('access=', struk)
        self.assertEqual(self.client.get(struk).status_code, 200)


class KioskBerandaTest(TestCase):
    def test_tombol_igd_ada_di_beranda(self):
        response = self.client.get(reverse('pasien:apm_kiosk'))
        html = response.content.decode()
        self.assertIn('GAWAT DARURAT', html)
        self.assertIn('id="igd-start"', html)
        self.assertIn('id="emergency-form"', html)

    def test_igd_tidak_lagi_di_langkah_layanan(self):
        html = self.client.get(reverse('pasien:apm_kiosk')).content.decode()
        self.assertNotIn('id="igd"', html)