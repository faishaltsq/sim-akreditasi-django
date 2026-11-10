from django.test import TestCase
from django.utils import timezone
from datetime import date, time
from pasien.models import Pasien, KunjunganPasien, JadwalDokterPoli, WhatsAppLog, AntreanBpjsTaskLog

class ApmModelsTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-TEST-APM',
            nama_lengkap='Budi APM',
            tanggal_lahir=date(1990, 5, 15),
            jenis_kelamin='L',
            no_hp='08123456789'
        )

    def test_kunjungan_apm_fields(self):
        k = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-APM-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP',
            is_apm=True,
            kode_booking='APM-20261110-001',
            token_batal='tok-test-12345',
            estimasi_pelayanan=time(10, 30)
        )
        self.assertTrue(k.is_apm)
        self.assertEqual(k.kode_booking, 'APM-20261110-001')
        self.assertEqual(k.token_batal, 'tok-test-12345')
        self.assertFalse(k.is_checkin)
        self.assertFalse(k.is_noshow)

    def test_jadwal_dokter_dan_sisa_kuota(self):
        j = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP',
            gelar='Spesialis Jantung & Pembuluh Darah',
            poliklinik='POLI_JANTUNG',
            hari_praktik='Senin - Jumat',
            jam_mulai=time(8, 0),
            jam_selesai=time(12, 0),
            kuota_maksimal=20,
            durasi_per_pasien_menit=15,
            status_ketersediaan='BUKA'
        )
        self.assertEqual(j.get_sisa_kuota(), 20)
        KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-APM-002',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP',
            is_apm=True
        )
        self.assertEqual(j.get_sisa_kuota(), 19)

    def test_whatsapp_log_creation(self):
        log = WhatsAppLog.objects.create(
            nomor_tujuan='08123456789',
            jenis_pesan='TIKET_APM',
            pesan='Bukti Pendaftaran APM',
            status='SIMULASI'
        )
        self.assertEqual(log.status, 'SIMULASI')

    def test_bpjs_7_task_log(self):
        k = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-APM-003',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now()
        )
        task = AntreanBpjsTaskLog.objects.create(
            kunjungan=k,
            task_id=3,
            nama_task='Akhir Waktu Tunggu Admisi / Check-In APM',
            status_kirim='SIMULATED'
        )
        self.assertEqual(task.task_id, 3)
