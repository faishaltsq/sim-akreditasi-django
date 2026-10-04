from django.test import TestCase
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, OrderPenunjang

class IgdAdvancedTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-IGD-ADV01',
            nama_lengkap='Joko Widodo',
            tanggal_lahir='1975-08-17',
            jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-IGD-ADV01',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            triage='MERAH',
            status='TRIAGE'
        )

    def test_gcs_and_pain_scale_saving(self):
        self.kunjungan.ttv_gcs = 'E4V5M6 (15)'
        self.kunjungan.ttv_skala_nyeri = 7
        self.kunjungan.save()
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.ttv_gcs, 'E4V5M6 (15)')
        self.assertEqual(self.kunjungan.ttv_skala_nyeri, 7)

    def test_critical_value_alert_flag(self):
        order = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan,
            jenis='LAB',
            prioritas='CITO',
            nama_pemeriksaan='Kalium Darah',
            is_critical_value=True,
            critical_value_catatan='K = 2.1 mEq/L (Severe Hypokalemia)'
        )
        self.assertTrue(order.is_critical_value)
