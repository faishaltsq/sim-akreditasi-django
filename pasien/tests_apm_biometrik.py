"""Phase 8 & 9 tests — penerbitan SEP saat check-in dan gerbang biometrik."""
import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pasien.models import (
    JadwalDokterPoli, KonfigurasiApm, KonfigurasiBiometrikPoli,
    KunjunganPasien, LogBiometrik, LogRisikoApm, Pasien, RujukanBpjs, WhatsAppLog,
)
from pasien.services.bpjs_vclaim import BridgingError

PPK = '0123R001'


def siapkan_pasien(suffix='001'):
    return Pasien.objects.create(
        no_rm=f'RM-BIO-{suffix}', nama_lengkap=f'Pasien Bio {suffix}',
        tanggal_lahir=datetime.date(1990, 5, 15), jenis_kelamin='L',
        no_hp=f'08127777{suffix[-4:]}', no_bpjs='0001234567890',
    )


class Base(TestCase):
    def setUp(self):
        self.pasien = siapkan_pasien('0001')
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP', poliklinik='POLI_JANTUNG',
            jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 0),
            kuota_maksimal=20, status_ketersediaan='BUKA',
            kode_poli_bpjs='JTG', kode_dokter_bpjs=12345,
        )
        self.rujukan = RujukanBpjs.objects.create(
            pasien=self.pasien, no_rujukan='0123456789012345678',
            tgl_rujukan=timezone.localdate(), ppk_rujukan='0401B001',
            ppk_tujuan=PPK, diagnosa_awal='I10', status_validasi='VALID',
        )

    def buat_kunjungan(self, *, penjamin='BPJS', poliklinik='POLI_JANTUNG', suffix='001', estimasi=None):
        return KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan=f'REG-BIO-{suffix}', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), poliklinik=poliklinik, dpjp='dr. Faisal, Sp.JP',
            nomor_antrean=f'JTG-{suffix}', kode_booking=f'APM-BIO-{suffix}',
            is_apm=True, penjamin=penjamin, rujukan=self.rujukan if penjamin == 'BPJS' else None,
            diagnosa_masuk='I10',
            estimasi_pelayanan=estimasi or (timezone.localtime() + datetime.timedelta(hours=2)).time(),
        )

    def checkin(self, kode):
        return self.client.post(reverse('pasien:apm_api_checkin'), {
            'kode': kode,
            'nama_lengkap': self.pasien.nama_lengkap,
            'tanggal_lahir': '15/05/1990',
        })


@override_settings(BPJS_KODE_PPK=PPK, BPJS_ALLOW_SIMULATION=True)
class SepCheckinTest(Base):
    def test_checkin_bpjs_menerbitkan_sep_dan_templat_2(self):
        kunjungan = self.buat_kunjungan()
        response = self.checkin('APM-BIO-001')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['sep']['success'])
        kunjungan.refresh_from_db()
        self.assertTrue(kunjungan.no_sep.startswith('SIM-'))
        self.assertEqual(kunjungan.sep_mode, 'SIMULASI')
        self.assertTrue(kunjungan.no_referensi_antrean)
        self.assertTrue(WhatsAppLog.objects.filter(jenis_pesan='CHECKIN_SEP').exists())

    def test_double_checkin_tidak_menerbitkan_sep_kedua(self):
        kunjungan = self.buat_kunjungan()
        self.checkin('APM-BIO-001')
        pertama = kunjungan.__class__.objects.get(pk=kunjungan.pk).no_sep
        response = self.checkin('APM-BIO-001')
        self.assertEqual(response.status_code, 200)
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.no_sep, pertama)
        self.assertEqual(KunjunganPasien.objects.filter(no_sep=pertama).count(), 1)

    def test_kunjungan_umum_tidak_memanggil_bridging(self):
        kunjungan = self.buat_kunjungan(penjamin='UMUM', suffix='002')
        with patch('pasien.services.bpjs_vclaim.terbitkan_sep', side_effect=AssertionError('tidak boleh')):
            response = self.checkin('APM-BIO-002')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['sep'])

    @override_settings(BPJS_ALLOW_SIMULATION=False)
    def test_bridging_gagal_tidak_mencetak_sep(self):
        kunjungan = self.buat_kunjungan(suffix='003')
        response = self.checkin('APM-BIO-003')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['sep']['success'])
        self.assertEqual(data['sep']['jalur_alternatif'], 'LOKET_ADMISI')
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.sep_mode, 'GAGAL')
        self.assertEqual(kunjungan.no_sep, '')
        self.assertTrue(LogRisikoApm.objects.filter(kode_risiko='RSK-APM-04').exists())

    def test_task_id_3_hanya_setelah_sep_sukses(self):
        kunjungan = self.buat_kunjungan(suffix='004')
        self.checkin('APM-BIO-004')
        kunjungan.refresh_from_db()
        self.assertTrue(kunjungan.bpjs_task_logs.filter(task_id=3).exists())


@override_settings(BPJS_KODE_PPK=PPK, BPJS_ALLOW_SIMULATION=True)
class BiometrikGateTest(Base):
    def setUp(self):
        super().setUp()
        self.konf = KonfigurasiBiometrikPoli.objects.create(poliklinik='POLI_JANTUNG')

    def biometrik(self, kode, **extra):
        data = {
            'kode': kode,
            'nama_lengkap': self.pasien.nama_lengkap,
            'tanggal_lahir': '15/05/1990',
            'metode': 'FINGERPRINT',
        }
        data.update(extra)
        return self.client.post(reverse('pasien:apm_api_biometrik'), data, content_type='application/json')

    def test_poli_biometrik_memblokir_checkin(self):
        kunjungan = self.buat_kunjungan(suffix='010')
        response = self.checkin('APM-BIO-010')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['status'], 'BIOMETRIK_BELUM_VALID')
        kunjungan.refresh_from_db()
        self.assertFalse(kunjungan.is_checkin)
        self.assertEqual(kunjungan.biometrik_status, 'MENUNGGU')
        self.assertEqual(kunjungan.no_sep, '')

    def test_verifikasi_biometrik_valid_lalu_checkin(self):
        kunjungan = self.buat_kunjungan(suffix='011')
        hasil = self.biometrik('APM-BIO-011')
        self.assertEqual(hasil.status_code, 200, hasil.content)
        self.assertEqual(hasil.json()['status'], 'VALID')
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.biometrik_status, 'VALID')
        self.assertTrue(kunjungan.log_biometrik.filter(hasil='VALID', mode='SIMULASI').exists())

        response = self.checkin('APM-BIO-011')
        self.assertEqual(response.status_code, 200, response.content)
        kunjungan.refresh_from_db()
        self.assertTrue(kunjungan.is_checkin)

    def test_tiga_kali_gagal_eskalasi_helpdesk(self):
        kunjungan = self.buat_kunjungan(suffix='012')
        for percobaan in (1, 2):
            hasil = self.biometrik('APM-BIO-012', simulasi_valid='0')
            self.assertEqual(hasil.status_code, 200)
            self.assertEqual(hasil.json()['sisa_percobaan'], 3 - percobaan)
        ketiga = self.biometrik('APM-BIO-012', simulasi_valid='0')
        self.assertEqual(ketiga.status_code, 409)
        data = ketiga.json()
        self.assertEqual(data['status'], 'ESKALASI')
        self.assertTrue(data['tiket_helpdesk'].startswith('HSD-'))

        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.biometrik_status, 'ESKALASI')
        self.assertTrue(LogRisikoApm.objects.filter(kode_risiko='RSK-APM-03', pemicu='BIOMETRIK_GAGAL_3X').exists())
        self.assertEqual(LogBiometrik.objects.filter(hasil='ESKALASI').count(), 1)
        self.assertTrue(WhatsAppLog.objects.filter(jenis_pesan='ESKALASI_BIOMETRIK').exists())

    def test_poli_tanpa_aturan_biometrik_tidak_diwajibkan(self):
        self.konf.aktif = False
        self.konf.save()
        kunjungan = self.buat_kunjungan(suffix='013')
        hasil = self.biometrik('APM-BIO-013')
        self.assertEqual(hasil.json()['status'], 'TIDAK_WAJIB')
        response = self.checkin('APM-BIO-013')
        self.assertEqual(response.status_code, 200)
        kunjungan.refresh_from_db()
        self.assertTrue(kunjungan.is_checkin)

    def test_pengecualian_usia_tidak_perlu_biometrik(self):
        self.konf.usia_min_pengecualian = 17
        self.konf.usia_max_pengecualian = 35
        self.konf.save()
        kunjungan = self.buat_kunjungan(suffix='014')
        response = self.checkin('APM-BIO-014')
        self.assertEqual(response.status_code, 200, response.content)
        kunjungan.refresh_from_db()
        self.assertTrue(kunjungan.is_checkin)

    def test_identitas_salah_ditolak(self):
        self.buat_kunjungan(suffix='015')
        hasil = self.client.post(reverse('pasien:apm_api_biometrik'), {
            'kode': 'APM-BIO-015', 'nama_lengkap': 'Orang Lain', 'tanggal_lahir': '15/05/1990',
        }, content_type='application/json')
        self.assertEqual(hasil.status_code, 403)


class ModeDeviceTest(TestCase):
    def test_mode_device_fail_closed(self):
        from pasien.services.biometrik import BiometricGateway, BiometricUnavailable

        pasien = siapkan_pasien('0099')
        kunjungan = KunjunganPasien.objects.create(
            pasien=pasien, no_kunjungan='REG-BIO-099', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP', is_apm=True,
        )
        with self.assertRaises(BiometricUnavailable):
            BiometricGateway(mode='DEVICE').verify(kunjungan=kunjungan, percobaan=1)


class SesiResetTest(TestCase):
    def test_reset_sesi_post_only_dan_csrf(self):
        url = reverse('pasien:apm_api_sesi_reset')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 204)
        client = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(client.post(url).status_code, 403)