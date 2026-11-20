"""Phase 7 tests — tiga templat WhatsApp PRD, masking, idempotensi, retry, throttle."""
import datetime
import os
from unittest.mock import patch
from urllib.error import URLError

from django.test import TestCase, override_settings
from django.utils import timezone

from akreditasi.models import RumahSakitProfile
from pasien.models import (
    JadwalDokterPoli, KonfigurasiApm, KonfigurasiBiometrikPoli,
    KunjunganPasien, Pasien, WhatsAppLog,
)
from pasien.services.whatsapp import (
    format_konfirmasi_booking, format_konfirmasi_checkin_sep,
    format_pergeseran_jadwal, kirim_pesan_wa, kirim_templat,
    mask_nama, mask_nomor, mask_sep, normalisasi_nomor,
)


class TemplateBase(TestCase):
    def setUp(self):
        RumahSakitProfile.objects.all().delete()
        self.profil = RumahSakitProfile.objects.create(name='RSU Uji Sehat')
        self.pasien = Pasien.objects.create(
            no_rm='RM-WA-001', nama_lengkap='Ahmad Subarjo',
            tanggal_lahir=datetime.date(1985, 3, 20), jenis_kelamin='L',
            no_hp='081299998888',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-WA-001', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP', nomor_antrean='JTG-014',
            kode_booking='APM-20261120-0001', token_batal='TRX-998231',
            estimasi_pelayanan=datetime.time(10, 30), is_apm=True,
            tanggal_kunjungan=datetime.date(2026, 11, 20),
        )


class TemplatTest(TemplateBase):
    def test_templat_1_verbatim(self):
        pesan = format_konfirmasi_booking(self.kunjungan, base_url='https://arima.rs')
        baris = pesan.split('\n')
        self.assertEqual(baris[0], '*RSU Uji Sehat*')
        self.assertEqual(baris[1], 'Bukti Pendaftaran Rawat Jalan Mandiri')
        self.assertTrue(baris[3].startswith('Yth. *Ahm'))
        self.assertNotIn('Subarjo', baris[3])
        self.assertEqual(baris[4], 'Kode Booking: *APM-20261120-0001*  |  No. Antrean Poli: *JTG-014*')
        self.assertEqual(baris[5], 'Tanggal Kunjungan: 20/11/2026')
        self.assertEqual(baris[7], 'Layanan poli spesialis: *Poli Jantung & Pembuluh Darah*')
        self.assertEqual(baris[8], 'Oleh dokter: *dr. Faisal, Sp.JP*')
        self.assertIn('estimasi pemeriksaan pukul *10:30 WIB*', baris[9])
        self.assertIn('dianjurkan tiba pukul *10:00 WIB*', baris[11])
        self.assertIn('Scan QR Check-In', baris[11])
        self.assertIn('Simpan pesan ini dan tunjukkan QR Code booking', pesan)
        self.assertIn('/pasien/apm/batal/?token=TRX-998231', pesan)

    def test_templat_2_verbatim(self):
        self.kunjungan.no_sep = '0123R0011026V000123'
        pesan = format_konfirmasi_checkin_sep(self.kunjungan)
        self.assertTrue(pesan.startswith('*RSU Uji Sehat*\nKonfirmasi Check-In & Penerbitan SEP'))
        self.assertIn('No. SEP: *' + mask_sep(self.kunjungan.no_sep) + '*', pesan)
        self.assertIn('No. Antrean Poli: *JTG-014*', pesan)
        self.assertIn('estimasi pemeriksaan pukul *10:30 WIB*', pesan)
        self.assertIn('Silakan menuju ruang tunggu *Poli Jantung & Pembuluh Darah*', pesan)
        self.assertIn('*30 menit lebih awal*', pesan)

    def test_templat_3_verbatim(self):
        pesan = format_pergeseran_jadwal(
            self.kunjungan,
            estimasi_lama=datetime.time(10, 30),
            estimasi_baru=datetime.time(11, 15),
        )
        self.assertTrue(pesan.startswith('*RSU Uji Sehat*\nPemberitahuan Pembaruan Estimasi Waktu Pemeriksaan'))
        self.assertIn('Yth. *Ahm', pesan)
        self.assertIn('(Kode Booking: *APM-20261120-0001* / Antrean: *JTG-014*)', pesan)
        self.assertIn('Layanan poli spesialis: *Poli Jantung & Pembuluh Darah*  |  Oleh dokter: *dr. Faisal, Sp.JP*', pesan)
        self.assertIn('Estimasi pemeriksaan terbaru: pukul *11:15 WIB*', pesan)
        self.assertIn('sekitar pukul *10:45 WIB*', pesan)
        self.assertIn('Terima kasih atas pengertian Anda.', pesan)

    def test_nama_rs_mengikuti_profil(self):
        pesan = format_konfirmasi_booking(self.kunjungan)
        self.assertTrue(pesan.startswith('*RSU Uji Sehat*'))
        self.profil.name = 'RS Klinik Sehat Bersama'
        self.profil.save()
        self.assertTrue(format_konfirmasi_booking(self.kunjungan).startswith('*RS Klinik Sehat Bersama*'))

    def test_masking_tidak_membocorkan_identitas_penuh(self):
        pesan = format_konfirmasi_booking(self.kunjungan)
        self.assertNotIn('Ahmad Subarjo', pesan)
        self.assertNotIn('081299998888', pesan)
        self.assertEqual(mask_nama('Ahmad Subarjo'), 'Ahm***')
        self.assertEqual(mask_nama('Ani'), 'A**')
        self.assertEqual(mask_nama(''), '-')
        self.assertEqual(mask_nomor('6281299998888'), '****8888')
        self.assertEqual(mask_sep('0123R0011026V000123'), '***************0123')

    def test_blok_biometrik_muncul_untuk_poli_wajib(self):
        KonfigurasiBiometrikPoli.objects.create(poliklinik='POLI_JANTUNG')
        pesan = format_konfirmasi_booking(self.kunjungan)
        self.assertIn('mewajibkan verifikasi sidik jari / face recognition', pesan)

    def test_blok_biometrik_kosong_untuk_poli_biasa(self):
        self.kunjungan.poliklinik = 'POLI_UMUM'
        self.kunjungan.save(update_fields=['poliklinik'])
        pesan = format_konfirmasi_booking(self.kunjungan)
        self.assertNotIn('mewajibkan verifikasi sidik jari', pesan)

    def test_blok_biometrik_dikecualikan_usia(self):
        KonfigurasiBiometrikPoli.objects.create(
            poliklinik='POLI_JANTUNG', usia_min_pengecualian=17, usia_max_pengecualian=60,
        )
        self.pasien.tanggal_lahir = datetime.date(1940, 1, 1)
        self.pasien.save(update_fields=['tanggal_lahir'])
        pesan = format_konfirmasi_booking(self.kunjungan)
        self.assertNotIn('mewajibkan verifikasi sidik jari', pesan)


class PengirimanTest(TemplateBase):
    def test_idempotensi_per_versi_estimasi(self):
        pertama = kirim_templat(self.kunjungan, 'KONFIRMASI_BOOKING')
        kedua = kirim_templat(self.kunjungan, 'KONFIRMASI_BOOKING')
        self.assertTrue(pertama['success'])
        self.assertEqual(kedua['mode'], 'duplicate')
        self.assertEqual(WhatsAppLog.objects.filter(jenis_pesan='KONFIRMASI_BOOKING').count(), 1)

    def test_versi_baru_mengirim_pesan_baru(self):
        kirim_templat(self.kunjungan, 'KONFIRMASI_BOOKING')
        self.kunjungan.estimasi_versi = 1
        self.kunjungan.save(update_fields=['estimasi_versi'])
        hasil = kirim_templat(self.kunjungan, 'KONFIRMASI_BOOKING')
        self.assertNotEqual(hasil['mode'], 'duplicate')
        self.assertEqual(WhatsAppLog.objects.filter(jenis_pesan='KONFIRMASI_BOOKING').count(), 2)

    def test_throttle_per_nomor(self):
        pertama = kirim_pesan_wa('081299998888', 'pesan 1')
        kedua = kirim_pesan_wa('081299998888', 'pesan 2')
        self.assertTrue(pertama['success'])
        self.assertEqual(kedua['mode'], 'throttled')
        self.assertEqual(WhatsAppLog.objects.filter(status='THROTTLED').count(), 1)

    def test_nomor_tidak_valid_ditolak(self):
        hasil = kirim_pesan_wa('12345', 'pesan')
        self.assertFalse(hasil['success'])
        self.assertEqual(hasil['mode'], 'invalid_number')

    def test_normalisasi_nomor(self):
        self.assertEqual(normalisasi_nomor('0812-9999-8888'), '6281299998888')
        self.assertEqual(normalisasi_nomor('+62 812 9999 8888'), '6281299998888')
        self.assertEqual(normalisasi_nomor('abc'), '')

    @override_settings()
    def test_retry_sampai_berhasil(self):
        konf = KonfigurasiApm.get_solo()
        konf.wa_provider = 'FONNTE'
        konf.wa_retry_maks = 3
        konf.save()
        with patch.dict(os.environ, {'FONNTE_TOKEN': 'token-uji'}):
            with patch('pasien.services.whatsapp._sleep') as tidur:
                with patch(
                    'pasien.services.whatsapp._kirim_fonnte',
                    side_effect=[URLError('putus'), URLError('putus'), (True, {'status': True})],
                ):
                    hasil = kirim_pesan_wa('081200004444', 'pesan retry')
        self.assertTrue(hasil['success'])
        self.assertEqual(hasil['percobaan'], 3)
        self.assertEqual(tidur.call_count, 2)

    @override_settings()
    def test_gagal_setelah_retry_maksimal(self):
        konf = KonfigurasiApm.get_solo()
        konf.wa_provider = 'FONNTE'
        konf.wa_retry_maks = 2
        konf.save()
        with patch.dict(os.environ, {'FONNTE_TOKEN': 'token-uji'}):
            with patch('pasien.services.whatsapp._sleep'):
                with patch('pasien.services.whatsapp._kirim_fonnte', side_effect=URLError('putus')):
                    hasil = kirim_pesan_wa('081200005555', 'pesan gagal')
        self.assertFalse(hasil['success'])
        self.assertEqual(hasil['percobaan'], 2)
        self.assertEqual(WhatsAppLog.objects.filter(status='FAILED').count(), 1)

    def test_provider_simulasi_tidak_memanggil_gateway(self):
        konf = KonfigurasiApm.get_solo()
        konf.wa_provider = 'SIMULASI'
        konf.save()
        with patch('pasien.services.whatsapp._kirim_fonnte', side_effect=AssertionError('tidak boleh dipanggil')):
            hasil = kirim_pesan_wa('081200006666', 'pesan simulasi')
        self.assertEqual(hasil['mode'], 'simulated')