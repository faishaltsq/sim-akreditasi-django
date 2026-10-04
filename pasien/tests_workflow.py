from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from pasien.models import Pasien, Ruangan, Bed, KunjunganPasien, DischargeRecord

class PasienWorkflowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('dokter1', 'doc@rs.com', 'pass123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-TEST-001',
            nama_lengkap='Budi Santoso',
            tanggal_lahir='1985-05-15',
            jenis_kelamin='L'
        )
        self.ruangan = Ruangan.objects.create(kode='R-VIP-01', nama='VIP Anggrek', kelas='VIP', jenis='RANAP', kapasitas=1)
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='B1', status='TERSEDIA')

    def test_igd_to_ranap_transfer(self):
        kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-IGD-001',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            triage='KUNING',
            status='TRIAGE'
        )
        kunjungan.admit_to_ranap(bed=self.bed, dpjp='dr. Hartono, Sp.JP')
        kunjungan.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(kunjungan.jenis_kunjungan, 'RANAP')
        self.assertEqual(kunjungan.status, 'RANAP')
        self.assertEqual(kunjungan.bed, self.bed)
        self.assertEqual(self.bed.status, 'TERISI')

    def test_rajal_discharge(self):
        kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-RAJAL-001',
            jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(),
            status='DAFTAR'
        )
        kunjungan.discharge_patient(kondisi='MEMBAIK', resume='Observasi stabil, kontrol 1 minggu lagi', user=self.user)
        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'PULANG')
        self.assertTrue(DischargeRecord.objects.filter(kunjungan=kunjungan).exists())
