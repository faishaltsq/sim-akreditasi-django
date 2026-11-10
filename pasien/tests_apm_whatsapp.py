from django.test import TestCase
from django.utils import timezone
from datetime import date, time
from pasien.models import Pasien, KunjunganPasien, WhatsAppLog
from pasien.services.whatsapp import format_tiket_wa, kirim_pesan_wa

class ApmWhatsAppTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-98230001',
            nama_lengkap='Tn. Ahmad',
            tanggal_lahir=date(1985, 3, 20),
            jenis_kelamin='L',
            no_hp='081299998888'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-20261110-0014',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            poliklinik='Poli Spesialis Jantung',
            dpjp='dr. Faisal, Sp.JP',
            nomor_antrean='B-014',
            estimasi_pelayanan=time(10, 30),
            token_batal='TRX-998231',
            is_apm=True
        )

    def test_verbatim_ticket_format(self):
        msg = format_tiket_wa(self.kunjungan, base_url='https://arima.rs')
        self.assertIn('BUKTI PENDAFTARAN MANDIRI (APM)', msg)
        self.assertIn('No. Rekam Medis: RM-98230001', msg)
        self.assertIn('Nama Pasien: Tn. Ahmad', msg)
        self.assertIn('Tujuan Poli: Poli Spesialis Jantung', msg)
        self.assertIn('Dokter DPJP: dr. Faisal, Sp.JP', msg)
        self.assertIn('No. Antrean Poli: B-014', msg)
        self.assertIn('Estimasi Waktu Pemeriksaan: 10:30 WIB', msg)
        self.assertIn('HIMBAUAN PENTING:', msg)
        self.assertIn('10:00 WIB', msg) # 30 mins before
        self.assertIn('09:30 WIB', msg) # 60 mins before
        self.assertIn('https://arima.rs/pasien/apm/batal/?token=TRX-998231', msg)

    def test_kirim_pesan_wa_simulated(self):
        res = kirim_pesan_wa(
            nomor='081299998888',
            pesan='Test WA Message',
            jenis_pesan='TIKET_APM',
            kunjungan=self.kunjungan
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['mode'], 'simulated')
        self.assertTrue(WhatsAppLog.objects.filter(nomor_tujuan__endswith='81299998888').exists())
