"""Phase 4 tests — gerbang kepatuhan rujukan (BL-02/BL-03, RSK-APM-02/04)."""
import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pasien.models import (
    JadwalDokterPoli, KunjunganPasien, LogRisikoApm, Pasien, RujukanBpjs,
)
from pasien.services.bpjs_vclaim import BridgingError
from pasien.services.rujukan import (
    RujukanFormatError, evaluate_rujukan, parse_nomor_rujukan, parse_qr_rujukan,
)

PPK = '0123R001'


def buat_pasien(suffix='001'):
    return Pasien.objects.create(
        no_rm=f'RM-GATE-{suffix}', nama_lengkap=f'Pasien Gate {suffix}',
        tanggal_lahir=datetime.date(1990, 5, 15), jenis_kelamin='L',
        no_hp='08123456789', no_bpjs=f'00011122233{suffix[-2:]}',
        nik=f'3201234567890{suffix[-3:]}',
    )


def buat_rujukan(pasien, **kwargs):
    data = dict(
        pasien=pasien, no_rujukan='0123456789012345678', jenis_rujukan='FKTP',
        tgl_rujukan=timezone.localdate() - datetime.timedelta(days=10),
        tgl_kunjungan_rencana=timezone.localdate(),
        ppk_rujukan='0401B001', nama_ppk_rujukan='Puskesmas Uji',
        ppk_tujuan=PPK, diagnosa_awal='I10', nama_diagnosa_awal='Hipertensi',
        ditemukan_di_vclaim=True,
    )
    data.update(kwargs)
    return RujukanBpjs.objects.create(**data)


class ParseRujukanTest(TestCase):
    def test_menerima_19_digit_dengan_pemisah(self):
        self.assertEqual(parse_nomor_rujukan('0123-4567-8901-2345-678'), '0123456789012345678')
        self.assertEqual(parse_nomor_rujukan(' 0123 4567 8901 2345 678 '), '0123456789012345678')

    def test_menolak_panjang_salah(self):
        for nilai in ('', '123', '01234567890123456789', 'abcdefghijklmnopqrs'):
            with self.assertRaises(RujukanFormatError):
                parse_nomor_rujukan(nilai)

    def test_qr_json(self):
        self.assertEqual(
            parse_qr_rujukan('{"noRujukan":"0123456789012345678","noKartu":"0001234567890"}'),
            '0123456789012345678',
        )

    def test_qr_polos_dan_invalid(self):
        self.assertEqual(parse_qr_rujukan('0123456789012345678'), '0123456789012345678')
        with self.assertRaises(RujukanFormatError):
            parse_qr_rujukan('{"foo":"bar"}')
        with self.assertRaises(RujukanFormatError):
            parse_qr_rujukan('{bukan json}')


@override_settings(BPJS_KODE_PPK=PPK)
class EvaluateRujukanTest(TestCase):
    def setUp(self):
        self.pasien = buat_pasien('E01')

    def test_valid(self):
        hasil = evaluate_rujukan(buat_rujukan(self.pasien))
        self.assertEqual(hasil.status, 'VALID')
        self.assertTrue(hasil.boleh_lanjut)
        self.assertEqual(hasil.jalur_alternatif, 'LANJUT')

    def test_kedaluwarsa_91_hari(self):
        r = buat_rujukan(
            self.pasien, no_rujukan='0123456789012345601',
            tgl_rujukan=timezone.localdate() - datetime.timedelta(days=91),
        )
        hasil = evaluate_rujukan(r)
        self.assertEqual(hasil.status, 'KEDALUWARSA')
        self.assertFalse(hasil.boleh_lanjut)
        self.assertEqual(hasil.jalur_alternatif, 'PERBARUI_FKTP')

    def test_tepat_90_hari_masih_valid(self):
        r = buat_rujukan(
            self.pasien, no_rujukan='0123456789012345602',
            tgl_rujukan=timezone.localdate() - datetime.timedelta(days=90),
        )
        self.assertEqual(evaluate_rujukan(r).status, 'VALID')

    def test_beda_ppk_menyebut_ppk_tujuan(self):
        r = buat_rujukan(self.pasien, no_rujukan='0123456789012345603', ppk_tujuan='9999R999')
        hasil = evaluate_rujukan(r)
        self.assertEqual(hasil.status, 'BEDA_PPK')
        self.assertIn('9999R999', hasil.alasan)
        self.assertEqual(hasil.jalur_alternatif, 'LOKET_INFORMASI')

    def test_tidak_ditemukan(self):
        r = buat_rujukan(self.pasien, no_rujukan='0123456789012345604', ditemukan_di_vclaim=False)
        self.assertEqual(evaluate_rujukan(r).status, 'TIDAK_DITEMUKAN')

    def test_peserta_tidak_aktif(self):
        r = buat_rujukan(self.pasien, no_rujukan='0123456789012345605')
        hasil = evaluate_rujukan(r, peserta_aktif=False)
        self.assertEqual(hasil.status, 'TIDAK_AKTIF')
        self.assertEqual(hasil.jalur_alternatif, 'LOKET_ADMISI')


@override_settings(BPJS_KODE_PPK=PPK)
class ValidasiRujukanApiTest(TestCase):
    url = reverse('pasien:apm_api_rujukan_validasi')

    def setUp(self):
        self.pasien = buat_pasien('V01')

    def payload(self, **kwargs):
        data = {
            'identitas': self.pasien.no_bpjs,
            'nama_lengkap': self.pasien.nama_lengkap,
            'tanggal_lahir': '1990-05-15',
            'no_rujukan': '0123456789012345678',
        }
        data.update(kwargs)
        return data

    def data_vclaim(self, **kwargs):
        data = {
            'mode': 'LIVE', 'ditemukan': True, 'no_rujukan': '0123456789012345678',
            'jenis_rujukan': 'FKTP', 'tgl_rujukan': timezone.localdate() - datetime.timedelta(days=5),
            'tgl_kunjungan_rencana': timezone.localdate(),
            'ppk_rujukan': '0401B001', 'nama_ppk_rujukan': 'Puskesmas Uji',
            'ppk_tujuan': PPK, 'poli_tujuan_bpjs': 'JTG',
            'diagnosa_awal': 'I10', 'nama_diagnosa_awal': 'Hipertensi',
        }
        data.update(kwargs)
        return data

    def test_rujukan_valid(self):
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan', return_value=self.data_vclaim()):
            response = self.client.post(self.url, self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body['boleh_lanjut'])
        self.assertEqual(body['status'], 'VALID')
        self.assertEqual(body['rujukan']['diagnosa_awal'], 'I10')
        self.assertEqual(body['rujukan']['masa_berlaku_hari'], 5)

    def test_kedaluwarsa_ditolak_dan_tercatat(self):
        data = self.data_vclaim(tgl_rujukan=timezone.localdate() - datetime.timedelta(days=120))
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan', return_value=data):
            response = self.client.post(self.url, self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'KEDALUWARSA')
        self.assertFalse(body['boleh_lanjut'])
        self.assertEqual(body['jalur_alternatif'], 'PERBARUI_FKTP')

    def test_beda_ppk(self):
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan',
                   return_value=self.data_vclaim(ppk_tujuan='9999R999')):
            response = self.client.post(self.url, self.payload(), content_type='application/json')
        self.assertEqual(response.json()['status'], 'BEDA_PPK')
        self.assertFalse(response.json()['boleh_lanjut'])

    def test_tidak_ditemukan(self):
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan',
                   return_value={'mode': 'LIVE', 'ditemukan': False, 'no_rujukan': '0123456789012345678',
                                 'alasan': 'Rujukan Tidak Ditemukan'}):
            response = self.client.post(self.url, self.payload(), content_type='application/json')
        body = response.json()
        self.assertEqual(body['status'], 'TIDAK_DITEMUKAN')
        self.assertFalse(body['boleh_lanjut'])
        self.assertEqual(body['jalur_alternatif'], 'LOKET_INFORMASI')

    def test_simulasi_tidak_pernah_valid(self):
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan',
                   return_value={'mode': 'SIMULASI', 'ditemukan': False, 'no_rujukan': '0123456789012345678'}):
            response = self.client.post(self.url, self.payload(), content_type='application/json')
        self.assertFalse(response.json()['boleh_lanjut'])
        self.assertEqual(response.json()['jalur_alternatif'], 'LOKET_ADMISI')

    def test_bridging_gangguan_503_dan_rsk_apm_04(self):
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan',
                   side_effect=BridgingError('TIMEOUT', 'Timeout 10s ke BPJS', path='/Rujukan/Peserta')):
            response = self.client.post(self.url, self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'BRIDGING_DOWN')
        self.assertEqual(LogRisikoApm.objects.filter(kode_risiko='RSK-APM-04').count(), 1)

    def test_identitas_salah_ditolak(self):
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan', return_value=self.data_vclaim()):
            response = self.client.post(
                self.url, self.payload(nama_lengkap='Nama Lain'), content_type='application/json',
            )
        self.assertEqual(response.status_code, 403)

    def test_format_nomor_salah(self):
        response = self.client.post(self.url, self.payload(no_rujukan='12345'), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'FORMAT_RUJUKAN')

    def test_csrf_diwajibkan(self):
        client = self.client_class(enforce_csrf_checks=True)
        response = client.post(self.url, self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 403)


@override_settings(BPJS_KODE_PPK=PPK)
class BookingGateTest(TestCase):
    url = reverse('pasien:apm_api_daftar')

    def setUp(self):
        self.pasien = buat_pasien('B01')
        self.jadwal = JadwalDokterPoli.objects.create(
            hari_praktik='Setiap hari',
            nama_dokter='dr. Faisal, Sp.JP', poliklinik='POLI_JANTUNG',
            jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 0),
            kuota_maksimal=10, status_ketersediaan='BUKA',
            kode_poli_bpjs='JTG', kode_dokter_bpjs=12345,
        )

    def payload(self, **kwargs):
        data = {
            'tipe_pasien': 'LAMA', 'nama_lengkap': self.pasien.nama_lengkap,
            'tanggal_lahir': '1990-05-15', 'no_rm': self.pasien.no_rm,
            'no_wa': '08123456789', 'jenis_layanan': 'RAJAL',
            'poliklinik': 'POLI_JANTUNG', 'jadwal_id': self.jadwal.pk, 'penjamin': 'BPJS',
        }
        data.update(kwargs)
        return data

    def test_bpjs_tanpa_rujukan_ditolak(self):
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['status'], 'RUJUKAN_WAJIB')
        self.assertFalse(KunjunganPasien.objects.exists())
        self.assertTrue(LogRisikoApm.objects.filter(kode_risiko='RSK-APM-02', pemicu='RUJUKAN_WAJIB').exists())

    def test_bpjs_rujukan_kedaluwarsa_ditolak_dan_tercatat(self):
        buat_rujukan(
            self.pasien, tgl_rujukan=timezone.localdate() - datetime.timedelta(days=120),
        )
        response = self.client.post(self.url, self.payload(no_rujukan='0123456789012345678'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['status'], 'KEDALUWARSA')
        log = LogRisikoApm.objects.get(kode_risiko='RSK-APM-02')
        self.assertEqual(log.pemicu, 'RUJUKAN_KEDALUWARSA')
        self.assertFalse(KunjunganPasien.objects.exists())

    def test_bpjs_rujukan_valid_dan_diagnosa_terkunci(self):
        rujukan = buat_rujukan(self.pasien)
        response = self.client.post(self.url, self.payload(
            no_rujukan=rujukan.no_rujukan, diagnosa_masuk='Z99.9',
        ))
        self.assertEqual(response.status_code, 200, response.content)
        kunjungan = KunjunganPasien.objects.get()
        self.assertEqual(kunjungan.rujukan_id, rujukan.pk)
        self.assertEqual(kunjungan.diagnosa_masuk, 'I10', 'diagnosa dari rujukan tidak boleh ditimpa klien')
        self.assertEqual(kunjungan.penjamin, 'BPJS')

    def test_bpjs_validasi_langsung_bila_belum_tersimpan(self):
        data = {
            'mode': 'LIVE', 'ditemukan': True, 'no_rujukan': '0123456789012345679',
            'jenis_rujukan': 'FKTP', 'tgl_rujukan': timezone.localdate() - datetime.timedelta(days=3),
            'ppk_rujukan': '0401B001', 'ppk_tujuan': PPK, 'diagnosa_awal': 'I10',
        }
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan', return_value=data):
            response = self.client.post(self.url, self.payload(no_rujukan='0123456789012345679'))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(RujukanBpjs.objects.filter(no_rujukan='0123456789012345679').exists())

    def test_umum_tanpa_rujukan_tetap_didaftarkan(self):
        response = self.client.post(self.url, self.payload(penjamin='UMUM'))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(KunjunganPasien.objects.get().penjamin, 'UMUM')