"""Regresi gate hari praktik dokter pada APM.

Konteks: `is_tersedia()` dulu hanya memeriksa status BUKA dan sisa kuota, sehingga
kiosk tetap menerbitkan nomor antrean untuk dokter yang tidak praktik hari itu
(mis. Sabtu untuk dokter dengan jadwal "Senin - Jumat"). Modul ini mengunci
perilaku baru: hari praktik wajib dihormati, dan alasan penolakan harus jelas.
"""
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import HARI_INDONESIA, JadwalDokterPoli, KunjunganPasien, parse_hari_praktik

NAMA_DOKTER = 'dr. Faisal, Sp.JP'


def buat_jadwal(hari_praktik, **kwargs):
    bawaan = dict(
        nama_dokter=NAMA_DOKTER, poliklinik='POLI_JANTUNG',
        jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 0),
        kuota_maksimal=20, status_ketersediaan='BUKA',
        kode_poli_bpjs='JTG', kode_dokter_bpjs=12345,
    )
    bawaan.update(kwargs)
    return JadwalDokterPoli.objects.create(hari_praktik=hari_praktik, **bawaan)


def hari_lain(tanggal):
    """Nama hari yang BUKAN hari dari `tanggal` (dipakai agar tes tidak tergantung hari)."""
    return HARI_INDONESIA[(tanggal.weekday() + 1) % 7]


class ParseHariPraktikTest(TestCase):
    def test_rentang_hari(self):
        self.assertEqual(parse_hari_praktik('Senin - Jumat'), {0, 1, 2, 3, 4})
        self.assertEqual(parse_hari_praktik('Senin - Sabtu'), {0, 1, 2, 3, 4, 5})
        self.assertEqual(parse_hari_praktik('Senin-Kamis'), {0, 1, 2, 3})
        self.assertEqual(parse_hari_praktik('Senin s/d Kamis'), {0, 1, 2, 3})

    def test_daftar_hari(self):
        self.assertEqual(parse_hari_praktik('Senin, Rabu, Jumat'), {0, 2, 4})
        self.assertEqual(parse_hari_praktik('Sabtu dan Minggu'), {5, 6})

    def test_setiap_hari_dan_data_kosong(self):
        semua = set(range(7))
        self.assertEqual(parse_hari_praktik('Setiap hari'), semua)
        self.assertEqual(parse_hari_praktik('Hari kerja'), semua)
        self.assertEqual(parse_hari_praktik(''), semua)
        self.assertEqual(parse_hari_praktik(None), semua)

    def test_teks_tidak_dikenali_tidak_memblokir_pendaftaran(self):
        # Data lama/typo tidak boleh membuat pasien kehilangan layanan.
        self.assertEqual(parse_hari_praktik('menyesuaikan'), set(range(7)))


class PraktikPadaTanggalTest(TestCase):
    """Tanggal eksplisit supaya hasil tes tidak berubah tergantung hari dijalankan."""

    def test_sabtu_bukan_hari_praktik_senin_jumat(self):
        jadwal = buat_jadwal('Senin - Jumat')
        sabtu = datetime.date(2026, 11, 21)
        self.assertEqual(sabtu.weekday(), 5)
        self.assertFalse(jadwal.praktik_pada(sabtu))
        self.assertFalse(jadwal.is_tersedia(sabtu))
        self.assertIn('tidak praktik hari ini', jadwal.alasan_tidak_tersedia(sabtu))
        self.assertIn('Senin - Jumat', jadwal.alasan_tidak_tersedia(sabtu))

    def test_sabtu_termasuk_jadwal_senin_sabtu(self):
        jadwal = buat_jadwal('Senin - Sabtu')
        sabtu = datetime.date(2026, 11, 21)
        self.assertTrue(jadwal.praktik_pada(sabtu))
        self.assertTrue(jadwal.is_tersedia(sabtu))
        self.assertEqual(jadwal.alasan_tidak_tersedia(sabtu), '')

    def test_hari_kerja_normal_tetap_tersedia(self):
        jadwal = buat_jadwal('Senin - Jumat')
        senin = datetime.date(2026, 11, 23)
        self.assertEqual(senin.weekday(), 0)
        self.assertTrue(jadwal.is_tersedia(senin))

    def test_status_libur_dan_penuh_punya_alasan_berbeda(self):
        self.assertIn('libur', buat_jadwal('Setiap hari', status_ketersediaan='LIBUR').alasan_tidak_tersedia())
        self.assertIn('penuh', buat_jadwal('Setiap hari', status_ketersediaan='PENUH').alasan_tidak_tersedia())
        penuh_kuota = buat_jadwal('Setiap hari', kuota_maksimal=0)
        self.assertIn('penuh', penuh_kuota.alasan_tidak_tersedia())


class DaftarMenghormatiHariPraktikTest(TestCase):
    url = reverse('pasien:apm_api_daftar')

    def payload(self, jadwal, **kwargs):
        data = {
            'tipe_pasien': 'BARU', 'nama_lengkap': 'basirun',
            'tanggal_lahir': '1969-10-02', 'nik': '3305162919690002',
            'jenis_kelamin': 'L', 'alamat': 'mangli', 'no_wa': '081215416402',
            'jenis_layanan': 'RAJAL', 'poliklinik': 'POLI_JANTUNG',
            'jadwal_id': jadwal.pk, 'penjamin': 'UMUM',
        }
        data.update(kwargs)
        return data

    def test_ditolak_saat_dokter_tidak_praktik_hari_ini(self):
        hari_ini = timezone.localdate()
        jadwal = buat_jadwal(hari_lain(hari_ini))
        response = self.client.post(self.url, self.payload(jadwal), content_type='application/json')
        self.assertEqual(response.status_code, 400, response.content)
        pesan = response.json()['message']
        self.assertIn('tidak praktik hari ini', pesan)
        self.assertIn(jadwal.hari_praktik, pesan)
        self.assertFalse(KunjunganPasien.objects.exists())

    def test_diterima_saat_dokter_praktik_hari_ini(self):
        hari_ini = timezone.localdate()
        jadwal = buat_jadwal(HARI_INDONESIA[hari_ini.weekday()])
        response = self.client.post(self.url, self.payload(jadwal), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['nomor_antrean'].startswith('JTG-'))

    def test_dokter_libur_dijelaskan_bukan_disebut_penuh(self):
        jadwal = buat_jadwal('Setiap hari', status_ketersediaan='LIBUR')
        response = self.client.post(self.url, self.payload(jadwal), content_type='application/json')
        self.assertEqual(response.status_code, 400, response.content)
        pesan = response.json()['message']
        self.assertIn('libur', pesan)
        self.assertNotIn('kuota', pesan.lower())


class ApiJadwalMengirimAlasanTest(TestCase):
    url = reverse('pasien:apm_api_jadwal_dokter')

    def test_api_mengirim_praktik_hari_ini_dan_alasan(self):
        hari_ini = timezone.localdate()
        tidak_praktik = buat_jadwal(hari_lain(hari_ini), nama_dokter='dr. Tidak Praktik')
        praktik = buat_jadwal(HARI_INDONESIA[hari_ini.weekday()], nama_dokter='dr. Praktik')

        response = self.client.get(self.url, {'poli': 'POLI_JANTUNG'})
        self.assertEqual(response.status_code, 200)
        data = {row['id']: row for row in response.json()['jadwal']}

        baris_tidak = data[tidak_praktik.pk]
        self.assertFalse(baris_tidak['is_tersedia'])
        self.assertFalse(baris_tidak['praktik_hari_ini'])
        self.assertIn('tidak praktik hari ini', baris_tidak['alasan_tidak_tersedia'])

        baris_praktik = data[praktik.pk]
        self.assertTrue(baris_praktik['is_tersedia'])
        self.assertTrue(baris_praktik['praktik_hari_ini'])
        self.assertEqual(baris_praktik['alasan_tidak_tersedia'], '')
