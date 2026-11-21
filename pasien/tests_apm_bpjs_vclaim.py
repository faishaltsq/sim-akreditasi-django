"""Phase 2 tests — klien bridging VClaim 2.0 / Antrean Online (fail-closed)."""
import datetime
import json
from pathlib import Path
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pasien.models import JadwalDokterPoli, KunjunganPasien, Pasien, RujukanBpjs
from pasien.services import bpjs_vclaim
from pasien.services.bpjs_vclaim import (
    BridgingError,
    daftar_antrean_bpjs,
    terbitkan_sep,
    validasi_rujukan,
)

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'vclaim'

LIVE = dict(
    BPJS_CONS_ID='test-cons',
    BPJS_SECRET_KEY='test-secret',
    BPJS_USER_KEY='test-user',
    BPJS_KODE_PPK='0123R001',
    BPJS_ALLOW_SIMULATION=False,
    BPJS_VCLAIM_BASE_URL='https://vclaim.test/vclaim-rest',
    BPJS_ANTREAN_BASE_URL='https://antrean.test/antreanrs',
)


def fixture(name):
    return json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8'))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def buat_kunjungan_bpjs(suffix='001', **jadwal_kwargs):
    pasien = Pasien.objects.create(
        no_rm=f'RM-VC-{suffix}', nama_lengkap=f'Pasien VC {suffix}',
        tanggal_lahir=datetime.date(1990, 5, 15), jenis_kelamin='L',
        no_hp='08123456789', no_bpjs='0001234567890', nik='3201234567890001',
    )
    jadwal = JadwalDokterPoli.objects.create(
            hari_praktik='Setiap hari',
        nama_dokter='dr. Faisal, Sp.JP', poliklinik='POLI_JANTUNG',
        jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 0),
        kode_poli_bpjs=jadwal_kwargs.pop('kode_poli_bpjs', 'JTG'),
        kode_dokter_bpjs=jadwal_kwargs.pop('kode_dokter_bpjs', 12345),
        **jadwal_kwargs,
    )
    rujukan = RujukanBpjs.objects.create(
        pasien=pasien, no_rujukan=f'0123456789012345{suffix[:3]}',
        tgl_rujukan=datetime.date(2026, 10, 1), tgl_kunjungan_rencana=timezone.localdate(),
        ppk_rujukan='0401B001', ppk_tujuan='0123R001', diagnosa_awal='I10',
        status_validasi='VALID',
    )
    kunjungan = KunjunganPasien.objects.create(
        pasien=pasien, no_kunjungan=f'REG-VC-{suffix}', jenis_kunjungan='RAJAL',
        tanggal_masuk=timezone.now(), poliklinik='POLI_JANTUNG',
        dpjp='dr. Faisal, Sp.JP', penjamin='BPJS', is_apm=True,
        kode_booking=f'APM-VC-{suffix}', rujukan=rujukan,
    )
    return kunjungan, jadwal


@override_settings(**LIVE)
class VclaimCallTest(TestCase):
    def test_meta_data_non_200_melempar_bridging_error(self):
        with patch.object(bpjs_vclaim.requests, 'get', return_value=FakeResponse(fixture('rujukan_peserta_not_found'))):
            with self.assertRaises(BridgingError) as ctx:
                bpjs_vclaim.call('/Rujukan/Peserta/0123456789012345678')
        self.assertEqual(ctx.exception.status, 'META_ERROR')
        self.assertEqual(ctx.exception.meta_code, '201')

    def test_timeout_tidak_pernah_jadi_rujukan_valid(self):
        with patch.object(bpjs_vclaim.requests, 'get', side_effect=requests.Timeout('timeout')):
            with self.assertRaises(BridgingError) as ctx:
                validasi_rujukan('0123456789012345678', kode_ppk_rs='0123R001')
        self.assertEqual(ctx.exception.status, 'TIMEOUT')

    def test_http_500_melempar_http_error(self):
        with patch.object(bpjs_vclaim.requests, 'get', return_value=FakeResponse({}, status_code=500)):
            with self.assertRaises(BridgingError) as ctx:
                bpjs_vclaim.call('/Rujukan/Peserta/x')
        self.assertEqual(ctx.exception.status, 'HTTP_ERROR')

    def test_envelope_terenkripsi_dibuka(self):
        import base64
        key = f"{LIVE['BPJS_CONS_ID']}{LIVE['BPJS_SECRET_KEY']}{LIVE['BPJS_USER_KEY']}".encode()
        plain = json.dumps({'rujukan': {'noRujukan': 'X1'}}).encode()
        cipher = bytes(byte ^ key[i % len(key)] for i, byte in enumerate(plain))
        body = {'metaData': {'code': '200', 'message': 'OK'}, 'response': base64.b64encode(cipher).decode()}
        with patch.object(bpjs_vclaim.requests, 'get', return_value=FakeResponse(body)):
            hasil = bpjs_vclaim.call('/Rujukan/Peserta/X1')
        self.assertEqual(hasil['response']['rujukan']['noRujukan'], 'X1')

    def test_header_hmac_terbentuk(self):
        headers = bpjs_vclaim._bpjs_auth_headers('/Rujukan/Peserta/x')
        self.assertEqual(headers['X-cons-id'], LIVE['BPJS_CONS_ID'])
        self.assertEqual(headers['user_key'], LIVE['BPJS_USER_KEY'])
        self.assertEqual(len(headers['X-signature']), 64)


@override_settings(**LIVE)
class ValidasiRujukanTest(TestCase):
    def test_memetakan_field_vclaim(self):
        with patch.object(bpjs_vclaim.requests, 'get', return_value=FakeResponse(fixture('rujukan_peserta_valid'))):
            hasil = validasi_rujukan('0123456789012345678', kode_ppk_rs='0123R001')
        self.assertTrue(hasil['ditemukan'])
        self.assertEqual(hasil['ppk_tujuan'], '0123R001')
        self.assertEqual(hasil['ppk_rujukan'], '0401B001')
        self.assertEqual(hasil['diagnosa_awal'], 'I10')
        self.assertEqual(hasil['poli_tujuan_bpjs'], 'JTG')
        self.assertEqual(hasil['jenis_rujukan'], 'FKTP')
        self.assertEqual(hasil['tgl_rujukan'], '2026-10-01')

    def test_fallback_ke_rujukan_rs(self):
        responses = [FakeResponse(fixture('rujukan_peserta_not_found')), FakeResponse(fixture('rujukan_rs_valid'))]
        with patch.object(bpjs_vclaim.requests, 'get', side_effect=responses) as mocked:
            hasil = validasi_rujukan('0987654321098765432', kode_ppk_rs='0123R001')
        self.assertTrue(hasil['ditemukan'])
        self.assertEqual(hasil['jenis_rujukan'], 'ANTAR_FKRTL')
        self.assertEqual(mocked.call_count, 2)

    def test_tidak_ditemukan_di_kedua_endpoint(self):
        responses = [FakeResponse(fixture('rujukan_peserta_not_found')), FakeResponse(fixture('rujukan_peserta_not_found'))]
        with patch.object(bpjs_vclaim.requests, 'get', side_effect=responses):
            hasil = validasi_rujukan('1111111111111111111')
        self.assertFalse(hasil['ditemukan'])
        self.assertIn('Tidak Ditemukan', hasil['alasan'])


class ValidasiRujukanSimulasiTest(TestCase):
    @override_settings(BPJS_CONS_ID='', BPJS_SECRET_KEY='', BPJS_USER_KEY='', BPJS_ALLOW_SIMULATION=False)
    def test_tanpa_kredensial_fail_closed(self):
        with self.assertRaises(BridgingError) as ctx:
            validasi_rujukan('0123456789012345678')
        self.assertEqual(ctx.exception.status, 'NOT_CONFIGURED')

    @override_settings(BPJS_CONS_ID='', BPJS_SECRET_KEY='', BPJS_USER_KEY='', BPJS_ALLOW_SIMULATION=True)
    def test_simulasi_menandai_tidak_ditemukan(self):
        hasil = validasi_rujukan('0123456789012345678')
        self.assertEqual(hasil['mode'], 'SIMULASI')
        self.assertFalse(hasil['ditemukan'])


@override_settings(**LIVE)
class TerbitkanSepTest(TestCase):
    def setUp(self):
        self.kunjungan, self.jadwal = buat_kunjungan_bpjs('001')

    def test_menyimpan_no_sep_dari_respons(self):
        with patch.object(bpjs_vclaim.requests, 'post', return_value=FakeResponse(fixture('sep_insert_success'))) as mocked:
            hasil = terbitkan_sep(self.kunjungan)
        self.kunjungan.refresh_from_db()
        self.assertEqual(hasil['mode'], 'LIVE')
        self.assertEqual(self.kunjungan.no_sep, '0123R0011026V000123')
        self.assertEqual(self.kunjungan.sep_mode, 'LIVE')
        self.assertIsNotNone(self.kunjungan.sep_terbit_pada)
        payload = mocked.call_args.kwargs['json']['request']['t_sep']
        self.assertEqual(payload['rujukan']['noRujukan'], self.kunjungan.rujukan.no_rujukan)
        self.assertEqual(payload['poli']['tujuan'], 'JTG')
        self.assertEqual(payload['diagAwal'], 'I10')

    def test_idempoten_tanpa_panggilan_kedua(self):
        self.kunjungan.no_sep = 'SEP-SUDAH-ADA'
        self.kunjungan.sep_mode = 'LIVE'
        self.kunjungan.save(update_fields=['no_sep', 'sep_mode'])
        with patch.object(bpjs_vclaim.requests, 'post', side_effect=AssertionError('tidak boleh dipanggil')):
            hasil = terbitkan_sep(self.kunjungan)
        self.assertTrue(hasil['idempotent'])
        self.assertEqual(hasil['no_sep'], 'SEP-SUDAH-ADA')

    def test_meta_error_menandai_gagal_tanpa_nomor(self):
        with patch.object(bpjs_vclaim.requests, 'post', return_value=FakeResponse(fixture('sep_insert_meta_error'))):
            with self.assertRaises(BridgingError):
                terbitkan_sep(self.kunjungan)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.sep_mode, 'GAGAL')
        self.assertEqual(self.kunjungan.no_sep, '')

    def test_mapping_bpjs_kosong_ditolak(self):
        self.jadwal.kode_dokter_bpjs = None
        self.jadwal.save(update_fields=['kode_dokter_bpjs'])
        with self.assertRaises(BridgingError) as ctx:
            terbitkan_sep(self.kunjungan)
        self.assertEqual(ctx.exception.status, 'MAPPING_MISSING')

    def test_tanpa_rujukan_ditolak(self):
        self.kunjungan.rujukan = None
        self.kunjungan.save(update_fields=['rujukan'])
        with self.assertRaises(BridgingError) as ctx:
            terbitkan_sep(self.kunjungan)
        self.assertEqual(ctx.exception.status, 'DATA_INVALID')


class TerbitkanSepSimulasiTest(TestCase):
    @override_settings(BPJS_CONS_ID='', BPJS_SECRET_KEY='', BPJS_USER_KEY='', BPJS_ALLOW_SIMULATION=False)
    def test_tidak_menerbitkan_sep_tanpa_kredensial(self):
        kunjungan, _ = buat_kunjungan_bpjs('002')
        with self.assertRaises(BridgingError):
            terbitkan_sep(kunjungan)
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.no_sep, '')
        self.assertEqual(kunjungan.sep_mode, 'GAGAL')

    @override_settings(BPJS_CONS_ID='', BPJS_SECRET_KEY='', BPJS_USER_KEY='', BPJS_ALLOW_SIMULATION=True)
    def test_simulasi_ditandai_jelas(self):
        kunjungan, _ = buat_kunjungan_bpjs('003')
        hasil = terbitkan_sep(kunjungan)
        self.assertEqual(hasil['mode'], 'SIMULASI')
        self.assertTrue(hasil['no_sep'].startswith('SIM-'))
        self.assertIn('bukan SEP BPJS', hasil['message'])


@override_settings(**LIVE)
class DaftarAntreanTest(TestCase):
    def setUp(self):
        self.kunjungan, self.jadwal = buat_kunjungan_bpjs('004')

    def test_payload_antrean_lengkap(self):
        with patch.object(bpjs_vclaim.requests, 'post', return_value=FakeResponse(fixture('antrean_add_success'))) as mocked:
            hasil = daftar_antrean_bpjs(self.kunjungan)
        payload = mocked.call_args.kwargs['json']
        for field in ('kodebooking', 'jenispasien', 'nomorkartu', 'nik', 'nohp', 'kodepoli',
                      'namapoli', 'pasienbaru', 'norm', 'tanggalperiksa', 'kodedokter',
                      'jampraktek', 'jeniskunjungan', 'nomorreferensi'):
            self.assertIn(field, payload, f'payload antrean wajib punya {field}')
        self.assertEqual(payload['kodepoli'], 'JTG')
        self.assertEqual(payload['kodedokter'], 12345)
        self.assertEqual(payload['jampraktek'], '08:00-12:00')
        self.assertEqual(payload['jeniskunjungan'], 1)
        self.assertIsInstance(payload['tanggalperiksa'], int)
        self.assertEqual(payload['nomorreferensi'], self.kunjungan.rujukan.no_rujukan)
        self.assertEqual(hasil['kodebooking'], 'APM-20261008-0001')

    def test_idempoten_setelah_terdaftar(self):
        self.kunjungan.no_referensi_antrean = 'APM-VC-004'
        self.kunjungan.save(update_fields=['no_referensi_antrean'])
        with patch.object(bpjs_vclaim.requests, 'post', side_effect=AssertionError('tidak boleh dipanggil')):
            hasil = daftar_antrean_bpjs(self.kunjungan)
        self.assertTrue(hasil['idempotent'])

    def test_penjamin_non_bpjs_ditolak(self):
        self.kunjungan.penjamin = 'UMUM'
        self.kunjungan.save(update_fields=['penjamin'])
        with self.assertRaises(BridgingError) as ctx:
            daftar_antrean_bpjs(self.kunjungan)
        self.assertEqual(ctx.exception.status, 'DATA_INVALID')


class CetakSepViewTest(TestCase):
    def setUp(self):
        self.kunjungan, _ = buat_kunjungan_bpjs('005')
        self.user = User.objects.create_user('sep-operator', password='x')
        self.client.force_login(self.user)
        self.url = reverse('pasien:cetak_sep', kwargs={'pk': self.kunjungan.pk})

    def test_menolak_tanpa_nomor_sep(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 409)
        self.assertIn('tidak boleh direkayasa', response.content.decode())

    def test_menandai_sep_simulasi(self):
        self.kunjungan.no_sep = 'SIM-20261120-000001'
        self.kunjungan.sep_mode = 'SIMULASI'
        self.kunjungan.save(update_fields=['no_sep', 'sep_mode'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('SIMULASI', response.content.decode())

    def test_sep_live_tanpa_watermark(self):
        self.kunjungan.no_sep = '0123R0011026V000123'
        self.kunjungan.sep_mode = 'LIVE'
        self.kunjungan.save(update_fields=['no_sep', 'sep_mode'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('BUKAN SEP BPJS', response.content.decode())


class ShimKompatibilitasTest(TestCase):
    @override_settings(BPJS_CONS_ID='', BPJS_SECRET_KEY='', BPJS_USER_KEY='', BPJS_ALLOW_SIMULATION=False)
    def test_buat_sep_lama_tetap_mengembalikan_dict(self):
        from pasien.bpjs import buat_sep
        kunjungan, _ = buat_kunjungan_bpjs('006')
        hasil = buat_sep(kunjungan)
        self.assertFalse(hasil['success'])
        self.assertIsNone(hasil['no_sep'])
        self.assertIn('status_bridging', hasil)

    @override_settings(BPJS_CONS_ID='', BPJS_SECRET_KEY='', BPJS_USER_KEY='', BPJS_ALLOW_SIMULATION=True)
    def test_cek_eligibilitas_simulasi_tetap_kompatibel(self):
        from pasien.bpjs import cek_eligibilitas
        hasil = cek_eligibilitas('0001234567890')
        self.assertTrue(hasil['success'])
        self.assertIn('eligible', hasil)

    def test_koneksi_status_tanpa_kredensial(self):
        from pasien.bpjs import bpjs_connection_status
        with override_settings(BPJS_CONS_ID='', BPJS_SECRET_KEY='', BPJS_USER_KEY=''):
            hasil = bpjs_connection_status()
        self.assertFalse(hasil['connected'])
        self.assertEqual(hasil['mode'], 'simulated')