"""Phase 6 tests — portal mobile tanpa login (BL-04) + QR check-in."""
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.mobile_views import _buat_akses_tiket, _buat_token, _qr_payload
from pasien.models import JadwalDokterPoli, KunjunganPasien, Pasien


class MobileBase(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-MOB-001', nama_lengkap='Siti Aminah',
            tanggal_lahir=datetime.date(1992, 7, 8), jenis_kelamin='P',
            no_hp='', no_bpjs='0007778889990', nik='3201234567890123',
        )
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP', poliklinik='POLI_JANTUNG',
            jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 0),
            kuota_maksimal=10, status_ketersediaan='BUKA',
            kode_poli_bpjs='JTG', kode_dokter_bpjs=12345,
        )
        self.token = _buat_token(self.pasien)


class BerandaVerifikasiTest(MobileBase):
    def test_beranda_tanpa_login(self):
        response = self.client.get(reverse('pasien:mandiri_beranda'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('GAWAT DARURAT', html)
        self.assertIn('tanpa akun', html)

    def test_verifikasi_sukses_mengarahkan_ke_jadwal(self):
        response = self.client.post(reverse('pasien:mandiri_verifikasi'), {
            'identitas': '0007778889990', 'nama_lengkap': 'Siti Aminah',
            'tanggal_lahir': '08/07/1992', 'no_wa': '081277778888',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/mandiri/jadwal/?token=', response['Location'])
        self.pasien.refresh_from_db()
        self.assertEqual(self.pasien.no_hp, '081277778888')

    def test_identitas_salah_pesan_seragam(self):
        salah_nama = self.client.post(reverse('pasien:mandiri_verifikasi'), {
            'identitas': '0007778889990', 'nama_lengkap': 'Orang Lain',
            'tanggal_lahir': '08/07/1992', 'no_wa': '081277778888',
        })
        tidak_ada = self.client.post(reverse('pasien:mandiri_verifikasi'), {
            'identitas': '0000000000000', 'nama_lengkap': 'Siti Aminah',
            'tanggal_lahir': '08/07/1992', 'no_wa': '081277778888',
        })
        self.assertEqual(salah_nama.status_code, 403)
        self.assertEqual(tidak_ada.status_code, 403)
        for response in (salah_nama, tidak_ada):
            self.assertIn('Data identitas tidak cocok atau tidak ditemukan.', response.content.decode())

    def test_nomor_wa_tidak_valid(self):
        response = self.client.post(reverse('pasien:mandiri_verifikasi'), {
            'identitas': '0007778889990', 'tanggal_lahir': '08/07/1992', 'no_wa': '123',
        })
        self.assertEqual(response.status_code, 400)

    def test_beranda_dengan_token_valid_langsung_ke_jadwal(self):
        response = self.client.get(reverse('pasien:mandiri_beranda'), {'token': self.token})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/mandiri/jadwal/', response['Location'])


class JadwalDanBookingTest(MobileBase):
    def test_jadwal_tanpa_token_dialihkan(self):
        response = self.client.get(reverse('pasien:mandiri_jadwal'))
        self.assertEqual(response.status_code, 302)

    def test_token_palsu_ditolak(self):
        response = self.client.get(reverse('pasien:mandiri_jadwal'), {'token': 'palsu'})
        self.assertEqual(response.status_code, 302)

    def test_jadwal_menampilkan_dokter_dan_sisa_kuota(self):
        response = self.client.get(reverse('pasien:mandiri_jadwal'), {'token': self.token})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('dr. Faisal, Sp.JP', html)
        self.assertIn('Sisa 10', html)

    def test_booking_membuat_kunjungan_tanpa_duplikasi_pasien(self):
        jumlah_awal = Pasien.objects.count()
        response = self.client.post(reverse('pasien:mandiri_booking'), {
            'token': self.token, 'jadwal_id': self.jadwal.pk,
            'poliklinik': 'POLI_JANTUNG', 'penjamin': 'UMUM',
        })
        self.assertEqual(response.status_code, 302, response.content)
        self.assertIn('/mandiri/tiket/', response['Location'])
        self.assertEqual(Pasien.objects.count(), jumlah_awal)
        kunjungan = KunjunganPasien.objects.get()
        self.assertEqual(kunjungan.pasien_id, self.pasien.pk)
        self.assertTrue(kunjungan.is_apm)

    def test_booking_bpjs_tanpa_rujukan_ditolak(self):
        response = self.client.post(reverse('pasien:mandiri_booking'), {
            'token': self.token, 'jadwal_id': self.jadwal.pk,
            'poliklinik': 'POLI_JANTUNG', 'penjamin': 'BPJS',
        })
        self.assertEqual(response.status_code, 409)
        self.assertIn('rujukan', response.content.decode().lower())
        self.assertFalse(KunjunganPasien.objects.exists())


class TiketDanQrTest(MobileBase):
    def buat_kunjungan(self):
        return KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-MOB-001', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP', nomor_antrean='JTG-001',
            kode_booking='APM-MOB-001', is_apm=True,
            estimasi_pelayanan=datetime.time(9, 0),
        )

    def test_tiket_tanpa_akses_ditolak(self):
        self.buat_kunjungan()
        response = self.client.get(reverse('pasien:mandiri_tiket'), {'token': self.token})
        self.assertEqual(response.status_code, 403)

    def test_tiket_menampilkan_qr_dan_estimasi(self):
        kunjungan = self.buat_kunjungan()
        akses = _buat_akses_tiket(kunjungan)
        response = self.client.get(reverse('pasien:mandiri_tiket'), {'token': self.token, 'akses': akses})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('APM-MOB-001', html)
        self.assertIn('/mandiri/qr/', html)
        self.assertIn('08:00', html)
        self.assertIn('Poli Jantung &amp; Pembuluh Darah', html)
        self.assertIn('no-store', response['Cache-Control'])

    def test_akses_tiket_terikat_pasien(self):
        kunjungan = self.buat_kunjungan()
        akses = _buat_akses_tiket(kunjungan)
        lain = Pasien.objects.create(
            no_rm='RM-MOB-002', nama_lengkap='Pasien Lain',
            tanggal_lahir=datetime.date(1990, 1, 1), jenis_kelamin='L', no_hp='081200000001',
        )
        response = self.client.get(reverse('pasien:mandiri_tiket'), {
            'token': _buat_token(lain), 'akses': akses,
        })
        self.assertEqual(response.status_code, 403)

    def test_qr_menghasilkan_svg(self):
        kunjungan = self.buat_kunjungan()
        response = self.client.get(reverse('pasien:mandiri_qr'), {
            'token': self.token, 'akses': _buat_akses_tiket(kunjungan),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/svg+xml')

    def test_checkin_menerima_qr_bertanda_tangan(self):
        kunjungan = self.buat_kunjungan()
        response = self.client.post(reverse('pasien:apm_api_checkin'), {
            'kode': _qr_payload(kunjungan),
            'nama_lengkap': self.pasien.nama_lengkap,
            'tanggal_lahir': '08/07/1992',
        })
        self.assertEqual(response.status_code, 200, response.content)
        kunjungan.refresh_from_db()
        self.assertTrue(kunjungan.is_checkin)

    def test_checkin_menolak_qr_rusak(self):
        self.buat_kunjungan()
        response = self.client.post(reverse('pasien:apm_api_checkin'), {
            'kode': 'bukan-qr-tanda-tangan',
            'nama_lengkap': self.pasien.nama_lengkap,
            'tanggal_lahir': '08/07/1992',
        })
        self.assertEqual(response.status_code, 403)