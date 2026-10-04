from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from pasien.models import Pasien, Ruangan, Bed, KunjunganPasien, BookingKamar

class RajalAdvancedTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-RAJAL-ADV01',
            nama_lengkap='Bambang Pamungkas',
            tanggal_lahir='1982-06-10',
            jenis_kelamin='L'
        )
        self.ruangan = Ruangan.objects.create(kode='R-VIP-02', nama='VIP Melati', kelas='VIP', jenis='RANAP', kapasitas=1)
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='B1', status='TERSEDIA')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-RAJAL-ADV01',
            jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(),
            status='DAFTAR'
        )

    def test_poli_spri_with_bed_booking(self):
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=self.kunjungan,
            bed=self.bed,
            nomor_booking='BK-POLI-001',
            batas_waktu=timezone.now() + timedelta(hours=4),
            catatan='Indikasi Angiografi Koroner terencana'
        )
        self.assertEqual(booking.bed.status, 'DIBOOKING')
        self.assertEqual(booking.kunjungan.poliklinik, 'Poli Jantung & Pembuluh Darah')
