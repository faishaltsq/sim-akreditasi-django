from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from pasien.models import Pasien, Ruangan, Bed, KunjunganPasien, BookingKamar

class BookingKamarTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('petugas_admisi', 'admisi@rs.com', 'pass123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-BK-001',
            nama_lengkap='Siti Rahma',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='P'
        )
        self.ruangan = Ruangan.objects.create(kode='R-MAWAR-01', nama='Mawar 1', kelas='1', jenis='RANAP', kapasitas=2)
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='B1', status='TERSEDIA')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-IGD-BK01',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            status='RAWAT'
        )

    def test_create_bed_booking_locks_bed(self):
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=self.kunjungan,
            bed=self.bed,
            nomor_booking='BK-20261004-001',
            batas_waktu=timezone.now() + timedelta(hours=2),
            catatan='Rencana transfer dari IGD',
            petugas=self.user
        )
        self.bed.refresh_from_db()
        self.assertEqual(booking.status, 'BOOKED')
        self.assertEqual(self.bed.status, 'DIBOOKING')

    def test_cancel_bed_booking_releases_bed(self):
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=self.kunjungan,
            bed=self.bed,
            nomor_booking='BK-20261004-002',
            batas_waktu=timezone.now() + timedelta(hours=2),
            petugas=self.user
        )
        booking.batalkan(alasan='Pasien memilih rawat jalan')
        booking.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(booking.status, 'BATAL')
        self.assertEqual(self.bed.status, 'TERSEDIA')

    def test_checkin_bed_booking_occupies_bed(self):
        booking = BookingKamar.objects.create(
            pasien=self.pasien,
            kunjungan=self.kunjungan,
            bed=self.bed,
            nomor_booking='BK-20261004-003',
            batas_waktu=timezone.now() + timedelta(hours=2),
            petugas=self.user
        )
        booking.checkin()
        booking.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(booking.status, 'CHECKIN')
        self.assertEqual(self.bed.status, 'TERISI')
