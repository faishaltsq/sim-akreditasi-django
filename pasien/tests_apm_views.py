from django.test import TestCase, Client
from django.utils import timezone
from datetime import date, time, timedelta, datetime
from pasien.models import Pasien, KunjunganPasien, JadwalDokterPoli
from django.urls import reverse

class ApmViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.pasien = Pasien.objects.create(
            no_rm='RM-LAMA-001',
            nama_lengkap='Pasien Lama',
            tanggal_lahir=date(1980, 1, 1),
            jenis_kelamin='L',
            nik='3273010101800001',
            no_bpjs='0001112223334',
            no_hp='081234567890'
        )
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP',
            poliklinik='POLI_JANTUNG',
            jam_mulai=time(8, 0),
            jam_selesai=time(12, 0),
            kuota_maksimal=10,
            status_ketersediaan='BUKA'
        )

    def test_api_cari_pasien_lama(self):
        # By NIK
        r1 = self.client.get(reverse('pasien:apm_api_cari_pasien'), {'q': '3273010101800001'})
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()['found'])
        self.assertEqual(r1.json()['pasien']['no_rm'], 'RM-LAMA-001')

        # By BPJS
        r2 = self.client.get(reverse('pasien:apm_api_cari_pasien'), {'q': '0001112223334'})
        self.assertTrue(r2.json()['found'])

    def test_api_jadwal_dokter(self):
        res = self.client.get(reverse('pasien:apm_api_jadwal_dokter'), {'poli': 'POLI_JANTUNG'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(len(data['jadwal']), 1)
        self.assertEqual(data['jadwal'][0]['nama_dokter'], 'dr. Faisal, Sp.JP')

    def test_api_daftar_pasien_lama_rajal(self):
        payload = {
            'tipe_pasien': 'LAMA',
            'no_rm': 'RM-LAMA-001',
            'no_wa': '081234567890',
            'jenis_layanan': 'RAJAL',
            'poliklinik': 'POLI_JANTUNG',
            'jadwal_id': self.jadwal.pk,
            'penjamin': 'BPJS'
        }
        res = self.client.post(reverse('pasien:apm_api_daftar'), payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['nomor_antrean'].startswith('JTG-') or 'B-' in data['nomor_antrean'])
        self.assertIn('token_batal', data)

    def test_api_daftar_igd_fast_track(self):
        payload = {
            'tipe_pasien': 'BARU',
            'nama_lengkap': 'Korban Kecelakaan',
            'jenis_kelamin': 'L',
            'tanggal_lahir': '1995-04-12',
            'no_wa': '085511223344',
            'jenis_layanan': 'IGD',
            'penjamin': 'UMUM'
        }
        res = self.client.post(reverse('pasien:apm_api_daftar'), payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['jenis_kunjungan'], 'IGD')
        self.assertTrue(data['nomor_antrean'].startswith('IGD-'))

    def test_api_checkin_kiosk(self):
        k = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-CHK-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            nomor_antrean='JTG-001',
            kode_booking='APM-CHK-001',
            is_apm=True
        )
        res = self.client.post(reverse('pasien:apm_api_checkin'), {'kode': 'APM-CHK-001'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        k.refresh_from_db()
        self.assertTrue(k.is_checkin)

    def test_cancellation_policy_t60(self):
        now = timezone.localtime()
        # Case A: >= 60 minutes before -> ALLOWED
        k1 = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-CAN-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=now,
            estimasi_pelayanan=(now + timedelta(hours=2)).time(),
            token_batal='tok-allowed',
            is_apm=True
        )
        res_a = self.client.post(
            reverse('pasien:apm_batal_mandiri'),
            {'token': 'tok-allowed'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res_a.status_code, 200)
        self.assertTrue(res_a.json()['success'])
        k1.refresh_from_db()
        self.assertEqual(k1.status, 'BATAL')

        # Case B: < 60 minutes before -> NO-SHOW LOCKED
        k2 = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-CAN-002',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=now,
            estimasi_pelayanan=(now + timedelta(minutes=30)).time(),
            token_batal='tok-locked',
            is_apm=True
        )
        res_b = self.client.post(
            reverse('pasien:apm_batal_mandiri'),
            {'token': 'tok-locked'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res_b.status_code, 200)
        self.assertFalse(res_b.json()['success']) # Rejected cancellation
        self.assertIn('No-Show', res_b.json()['message'])
        k2.refresh_from_db()
        self.assertTrue(k2.is_noshow)
