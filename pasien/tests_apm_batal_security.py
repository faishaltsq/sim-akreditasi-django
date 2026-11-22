"""Regresi keamanan pembatalan mandiri APM (F-04 … F-07).

Cakupan:
- F-04 status guard: kunjungan yang sedang/telah dilayani tidak boleh dibatalkan.
- F-05 jendela T-60: IGD / estimasi kosong tidak lagi default 120 menit.
- F-06 idempotensi: pembatalan ulang tidak mengirim WhatsApp / menulis log ganda.
- F-07 throttle + token acak ``secrets.token_urlsafe(32)``.
"""
import re
from datetime import date, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import JadwalDokterPoli, KonfigurasiApm, KunjunganPasien, Pasien, WhatsAppLog

URL_BATAL = 'pasien:apm_batal_mandiri'
PESAN_DILAYANI = 'pasien sedang atau telah dilayani'
PESAN_LOKET = 'hubungi petugas loket pendaftaran'
POLA_TOKEN = re.compile(r'^[A-Za-z0-9_-]{43}$')


class ApmBatalMandiriSecurityTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-BATAL-001', nama_lengkap='Pasien Batal',
            tanggal_lahir=date(1990, 5, 17), jenis_kelamin='L',
            nik='3273010101900002', no_hp='081200001111',
        )

    def _buat_kunjungan(self, token, **overrides):
        sekarang = timezone.localtime()
        data = {
            'pasien': self.pasien,
            'no_kunjungan': f'REG-BATAL-{token}',
            'jenis_kunjungan': 'RAJAL',
            'tanggal_masuk': sekarang,
            'poliklinik': 'POLI_JANTUNG',
            'dpjp': 'dr. Faisal, Sp.JP',
            'nomor_antrean': 'JTG-001',
            'kode_booking': f'APM-{token}',
            'token_batal': token,
            'estimasi_pelayanan': (sekarang + timedelta(hours=3)).time(),
            'is_apm': True,
        }
        data.update(overrides)
        return KunjunganPasien.objects.create(**data)

    def _post(self, token):
        return self.client.post(
            reverse(URL_BATAL), {'token': token}, HTTP_ACCEPT='application/json',
        )

    # ── F-04: status guard ────────────────────────────────────────────────

    def test_kunjungan_dipanggil_tidak_dapat_dibatalkan(self):
        kunjungan = self._buat_kunjungan('tok-dipanggil', status_antrean='DIPANGGIL')
        respons = self._post('tok-dipanggil')
        self.assertEqual(respons.status_code, 409)
        self.assertFalse(respons.json()['success'])
        self.assertIn(PESAN_DILAYANI, respons.json()['message'])
        self.assertEqual(respons.json()['alasan'], 'SUDAH_DILAYANI')
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'DAFTAR')
        self.assertFalse(kunjungan.is_noshow)

    def test_kunjungan_sedang_dilayani_tidak_dapat_dibatalkan(self):
        kunjungan = self._buat_kunjungan('tok-dilayani', status_antrean='SEDANG_DILAYANI')
        respons = self._post('tok-dilayani')
        self.assertEqual(respons.status_code, 409)
        self.assertFalse(respons.json()['success'])
        self.assertIn(PESAN_DILAYANI, respons.json()['message'])
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'DAFTAR')
        self.assertFalse(kunjungan.is_noshow)

    def test_kunjungan_selesai_tidak_dapat_dibatalkan(self):
        kunjungan = self._buat_kunjungan(
            'tok-selesai', status='SELESAI', status_antrean='SELESAI',
        )
        respons = self._post('tok-selesai')
        self.assertEqual(respons.status_code, 409)
        self.assertFalse(respons.json()['success'])
        self.assertIn(PESAN_DILAYANI, respons.json()['message'])
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'SELESAI')

    def test_halaman_get_kunjungan_dipanggil_menjelaskan_alasan_tanpa_form(self):
        self._buat_kunjungan('tok-get-dipanggil', status_antrean='DIPANGGIL')
        respons = self.client.get(reverse(URL_BATAL), {'token': 'tok-get-dipanggil'})
        self.assertEqual(respons.status_code, 200)
        self.assertContains(respons, 'pasien sedang atau telah dilayani')
        self.assertNotContains(respons, 'Konfirmasi Batalkan Janji')

    # ── F-05: IGD / estimasi kosong tidak default 120 menit ───────────────

    def test_kunjungan_igd_tidak_dapat_dibatalkan_mandiri(self):
        kunjungan = self._buat_kunjungan('tok-igd', jenis_kunjungan='IGD', poliklinik='IGD')
        respons = self._post('tok-igd')
        self.assertEqual(respons.status_code, 409)
        self.assertFalse(respons.json()['success'])
        self.assertIn(PESAN_LOKET, respons.json()['message'])
        self.assertEqual(respons.json()['alasan'], 'PERLU_LOKET')
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'DAFTAR')
        self.assertFalse(kunjungan.is_noshow)

    def test_estimasi_pelayanan_kosong_tidak_lagi_default_120_menit(self):
        kunjungan = self._buat_kunjungan('tok-tanpa-estimasi', estimasi_pelayanan=None)
        respons = self._post('tok-tanpa-estimasi')
        self.assertEqual(respons.status_code, 409)
        self.assertFalse(respons.json()['success'])
        self.assertIn(PESAN_LOKET, respons.json()['message'])
        self.assertEqual(respons.json()['alasan'], 'PERLU_LOKET')
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'DAFTAR')
        self.assertFalse(kunjungan.is_noshow)
        self.assertFalse(WhatsAppLog.objects.filter(kunjungan=kunjungan).exists())

    def test_jendela_t60_tetap_berlaku_untuk_rajal(self):
        sekarang = timezone.localtime()
        self._buat_kunjungan(
            'tok-t60-ok', estimasi_pelayanan=(sekarang + timedelta(minutes=90)).time(),
        )
        self._buat_kunjungan(
            'tok-t60-tolak', estimasi_pelayanan=(sekarang + timedelta(minutes=30)).time(),
        )
        diterima = self._post('tok-t60-ok')
        self.assertEqual(diterima.status_code, 200)
        self.assertTrue(diterima.json()['success'])
        ditolak = self._post('tok-t60-tolak')
        self.assertEqual(ditolak.status_code, 200)
        self.assertFalse(ditolak.json()['success'])
        self.assertIn('No-Show', ditolak.json()['message'])

    # ── F-06: idempotensi pembatalan ulang ────────────────────────────────

    def test_pembatalan_ulang_idempoten_tanpa_kirim_wa_ganda(self):
        kunjungan = self._buat_kunjungan('tok-idempoten')
        with patch('pasien.apm_views.kirim_pesan_wa') as kirim:
            pertama = self._post('tok-idempoten')
            kedua = self._post('tok-idempoten')
        self.assertEqual(pertama.status_code, 200)
        self.assertTrue(pertama.json()['success'])
        self.assertNotIn('already_cancelled', pertama.json())
        self.assertEqual(kedua.status_code, 200)
        self.assertTrue(kedua.json()['success'])
        self.assertTrue(kedua.json()['already_cancelled'])
        self.assertEqual(kirim.call_count, 1)
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'BATAL')
        self.assertFalse(kunjungan.is_noshow)

    def test_pembatalan_ulang_tidak_menulis_log_whatsapp_ganda(self):
        konf = KonfigurasiApm.get_solo()
        konf.wa_provider = 'SIMULASI'
        konf.save()
        kunjungan = self._buat_kunjungan('tok-log-wa')
        self.assertTrue(self._post('tok-log-wa').json()['success'])
        self.assertTrue(self._post('tok-log-wa').json()['already_cancelled'])
        self.assertEqual(
            WhatsAppLog.objects.filter(kunjungan=kunjungan, jenis_pesan='BATAL_APM').count(), 1,
        )

    def test_halaman_get_kunjungan_sudah_batal_idempoten(self):
        self._buat_kunjungan('tok-get-batal', status='BATAL')
        respons = self.client.get(reverse(URL_BATAL), {'token': 'tok-get-batal'})
        self.assertEqual(respons.status_code, 200)
        self.assertContains(respons, 'sudah dibatalkan sebelumnya')
        self.assertNotContains(respons, 'Konfirmasi Batalkan Janji')

    # ── F-07: throttling ──────────────────────────────────────────────────

    def test_endpoint_pembatalan_dibatasi_throttle(self):
        self._buat_kunjungan('tok-throttle')
        for urutan in range(1, 11):
            respons = self._post('tok-throttle')
            self.assertEqual(respons.status_code, 200, f'permintaan ke-{urutan}')
        terakhir = self._post('tok-throttle')
        self.assertEqual(terakhir.status_code, 429)
        self.assertFalse(terakhir.json()['success'])
        self.assertIn('Terlalu banyak percobaan', terakhir.json()['message'])
        self.assertEqual(terakhir['Retry-After'], '60')

    # ── F-07: token pembatalan acak ───────────────────────────────────────

    def test_token_batal_registrasi_mandiri_memakai_token_urlsafe(self):
        jadwal = JadwalDokterPoli.objects.create(
            hari_praktik='Setiap hari', nama_dokter='dr. Token', poliklinik='POLI_JANTUNG',
            jam_mulai=time(6, 0), jam_selesai=time(23, 0), kuota_maksimal=10,
            durasi_per_pasien_menit=15, status_ketersediaan='BUKA',
        )
        payload = {
            'tipe_pasien': 'BARU', 'nama_lengkap': 'Pasien Token',
            'tanggal_lahir': '1993-03-04', 'jenis_kelamin': 'P',
            'jenis_layanan': 'RAJAL', 'penjamin': 'UMUM', 'jadwal_id': jadwal.pk,
        }
        token = self.client.post(reverse('pasien:apm_api_daftar'), payload).json()['token_batal']
        self.assertRegex(token, POLA_TOKEN)
        self.assertEqual(len(token), 43)

    def test_token_batal_igd_fasttrack_memakai_token_urlsafe(self):
        respons = self.client.post(reverse('pasien:apm_api_igd_fasttrack'), {
            'nama_lengkap': 'Pasien Darurat', 'no_wa': '081277778888',
        })
        self.assertEqual(respons.status_code, 200)
        kunjungan = KunjunganPasien.objects.get(kode_booking=respons.json()['kode_booking'])
        self.assertRegex(kunjungan.token_batal, POLA_TOKEN)
