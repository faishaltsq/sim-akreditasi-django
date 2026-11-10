from django.test import TestCase
from django.utils import timezone
from datetime import date
from pasien.models import Pasien, KunjunganPasien, AntreanBpjsTaskLog
from pasien.services.bpjs_antrean import update_task_id, TASK_ID_NAMES, get_task_timeline

class ApmBpjsTaskTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-TASK-001',
            nama_lengkap='Pasien BPJS',
            tanggal_lahir=date(1992, 1, 1),
            jenis_kelamin='L',
            no_bpjs='0001234567890'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-BPJS-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            penjamin='BPJS',
            kode_booking='APM-20261110-001'
        )

    def test_record_task_id_1_to_7(self):
        for tid in range(1, 8):
            res = update_task_id(self.kunjungan, tid)
            self.assertTrue(res['success'])
            self.assertEqual(res['task_id'], tid)
            self.assertIn(tid, TASK_ID_NAMES)

        logs = AntreanBpjsTaskLog.objects.filter(kunjungan=self.kunjungan)
        self.assertEqual(logs.count(), 7)
        timeline = get_task_timeline(self.kunjungan)
        self.assertEqual(len(timeline), 7)

    def test_invalid_task_id_rejected(self):
        with self.assertRaises(ValueError):
            update_task_id(self.kunjungan, 8)
