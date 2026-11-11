from datetime import date, datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import JadwalDokterPoli, KunjunganPasien, Pasien


class ApmQueueAllocationTest(TestCase):
    def setUp(self):
        self.patient = Pasien.objects.create(
            no_rm='RM-QUEUE-001', nama_lengkap='Pasien Antrean',
            tanggal_lahir=date(1990, 1, 1), jenis_kelamin='L',
        )
        self.doctor = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Pertama', poliklinik='POLI_JANTUNG',
            jam_mulai=time(12), jam_selesai=time(16), kuota_maksimal=2,
            durasi_per_pasien_menit=15, status_ketersediaan='BUKA',
        )
        self.payload = {
            'tipe_pasien':'LAMA', 'no_rm':self.patient.no_rm,
            'nama_lengkap':self.patient.nama_lengkap, 'tanggal_lahir':'1990-01-01',
            'jenis_layanan':'RAJAL', 'penjamin':'UMUM', 'jadwal_id':self.doctor.pk,
        }
        clock = patch('pasien.apm_views.timezone.now', return_value=timezone.make_aware(datetime(2026,11,11,9)))
        clock.start()
        self.addCleanup(clock.stop)

    def book(self, **overrides):
        response = self.client.post(reverse('pasien:apm_api_daftar'), {**self.payload, **overrides})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_cancellation_releases_quota_without_reusing_a_ticket_number(self):
        first, second = self.book(), self.book()
        self.assertEqual(self.doctor.get_sisa_kuota(), 0)
        full = self.client.post(reverse('pasien:apm_api_daftar'), self.payload)
        self.assertEqual(full.status_code, 400)
        cancelled = self.client.post(reverse('pasien:apm_batal_mandiri'), {'token':first['token_batal']}, HTTP_ACCEPT='application/json')
        self.assertTrue(cancelled.json()['success'])
        self.assertEqual(self.doctor.get_sisa_kuota(), 1)
        third = self.book()
        self.assertEqual([first['nomor_antrean'], second['nomor_antrean'], third['nomor_antrean']], ['JTG-001','JTG-002','JTG-003'])
        self.assertEqual(self.doctor.get_sisa_kuota(), 0)
        self.assertNotEqual(third['estimasi_pelayanan'], second['estimasi_pelayanan'])

    def test_same_clinic_different_doctors_use_distinct_queue_numbers(self):
        second_doctor = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Kedua', poliklinik='POLI_JANTUNG',
            jam_mulai=time(12), jam_selesai=time(16), kuota_maksimal=2,
            status_ketersediaan='BUKA',
        )
        first = self.book()
        second = self.book(jadwal_id=second_doctor.pk)
        self.assertEqual(first['nomor_antrean'], 'JTG-001')
        self.assertEqual(second['nomor_antrean'], 'JTG-002')
        self.assertEqual(self.doctor.get_sisa_kuota(), 1)
        self.assertEqual(second_doctor.get_sisa_kuota(), 1)

    def test_manual_admission_and_kiosk_share_the_same_sequence(self):
        from pasien.views import generate_nomor_antrean
        first = self.book()
        manual = generate_nomor_antrean('RAJAL', 'Jantung')
        third = self.book()
        self.assertEqual([first['nomor_antrean'], manual, third['nomor_antrean']], ['JTG-001', 'JTG-002', 'JTG-003'])

    def test_counter_resets_each_day_and_rolls_back_with_its_transaction(self):
        from datetime import timedelta
        from django.db import transaction
        from pasien.services.antrean import allocate_queue_number
        today = timezone.localdate()
        self.assertEqual(allocate_queue_number('IGD', tanggal=today), 'IGD-001')
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.assertEqual(allocate_queue_number('IGD', tanggal=today), 'IGD-002')
                raise RuntimeError('abort test transaction')
        self.assertEqual(allocate_queue_number('IGD', tanggal=today), 'IGD-002')
        self.assertEqual(allocate_queue_number('IGD', tanggal=today + timedelta(days=1)), 'IGD-001')

    def test_legacy_visit_without_estimation_still_reserves_a_doctor_slot(self):
        KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='REG-LEGACY-SLOT', tanggal_masuk=timezone.now(),
            jenis_kunjungan='RAJAL', poliklinik=self.doctor.poliklinik, dpjp=self.doctor.nama_dokter,
        )
        self.assertEqual(self.book()['estimasi_pelayanan'], '12:15')
        self.assertEqual(self.doctor.get_sisa_kuota(), 0)

    def test_existing_issued_ticket_is_respected_when_counter_is_initialized(self):
        KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='REG-OLD-QUEUE', tanggal_masuk=timezone.now(),
            jenis_kunjungan='RAJAL', poliklinik='POLI_JANTUNG', dpjp='dr. Riwayat',
            nomor_antrean='JTG-015', status='BATAL', is_apm=True,
        )
        self.assertEqual(self.book()['nomor_antrean'], 'JTG-016')
