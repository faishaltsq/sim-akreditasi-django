from datetime import date
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import KunjunganPasien, Pasien


class ApmReceiptAccessTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-SEC-001', nama_lengkap='Pasien Aman',
            tanggal_lahir=date(1990, 1, 1), jenis_kelamin='L',
        )

    def register(self):
        return self.client.post(reverse('pasien:apm_api_daftar'), {
            'tipe_pasien': 'BARU', 'nama_lengkap': 'Pasien Struk',
            'tanggal_lahir': '1991-02-03', 'jenis_kelamin': 'L',
            'jenis_layanan': 'IGD', 'penjamin': 'UMUM',
        }).json()

    def test_sequential_visit_id_alone_cannot_read_receipt(self):
        visit = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-SECRET-001',
            tanggal_masuk=timezone.now(), jenis_kunjungan='RAJAL', is_apm=True,
        )
        response = self.client.get(reverse('pasien:apm_cetak_struk', args=[visit.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, self.pasien.nama_lengkap, status_code=403)

    def test_expired_receipt_capability_is_rejected(self):
        from unittest.mock import patch
        from django.core import signing
        visit = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-EXPIRED-001',
            tanggal_masuk=timezone.now(), jenis_kunjungan='RAJAL', is_apm=True,
        )
        with patch('django.core.signing.time.time', return_value=0):
            access = signing.dumps(visit.pk, salt='apm-receipt')
        response = self.client.get(reverse('pasien:apm_cetak_struk', args=[visit.pk]), {'access':access})
        self.assertEqual(response.status_code, 403)

    def test_registration_receipt_link_is_signed_and_bound_to_visit(self):
        data = self.register()
        url = data['struk_url']
        self.assertIn('access', parse_qs(urlsplit(url).query))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        other = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-OTHER-001',
            tanggal_masuk=timezone.now(), jenis_kunjungan='RAJAL', is_apm=True,
        )
        other_url = reverse('pasien:apm_cetak_struk', args=[other.pk]) + '?' + urlsplit(url).query
        self.assertEqual(self.client.get(other_url).status_code, 403)


class ApmIdentityVerificationTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-IDENTITY-001', nama_lengkap='Pasien Terverifikasi',
            tanggal_lahir=date(1990, 1, 1), jenis_kelamin='L',
            nik='3273010101900001', no_hp='081299998888', alamat='Alamat privat',
        )
        self.identity = {'nama_lengkap': self.pasien.nama_lengkap, 'tanggal_lahir': '1990-01-01'}

    def test_lookup_requires_identity_and_never_discloses_demographics(self):
        url = reverse('pasien:apm_api_cari_pasien')
        response = self.client.get(url, {'q': self.pasien.no_rm})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(self.pasien.nama_lengkap, response.content.decode())
        response = self.client.get(url, {'q': self.pasien.no_rm, **self.identity})
        self.assertTrue(response.json()['found'])
        self.assertEqual(set(response.json()['pasien']), {'no_rm', 'nama_lengkap'})
        self.assertIn('no-store', response['Cache-Control'])

    def test_wrong_identity_and_unknown_identifier_have_same_response(self):
        url = reverse('pasien:apm_api_cari_pasien')
        bad = self.client.get(url, {'q': self.pasien.no_rm, **self.identity, 'nama_lengkap': 'Orang Lain'})
        unknown = self.client.get(url, {'q': 'RM-UNKNOWN', **self.identity})
        self.assertEqual(bad.json(), unknown.json())
        self.assertFalse(bad.json()['found'])

    def test_direct_existing_registration_requires_matching_identity(self):
        payload = {'tipe_pasien':'LAMA', 'no_rm': self.pasien.no_rm, 'jenis_layanan':'IGD'}
        response = self.client.post(reverse('pasien:apm_api_daftar'), payload)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(KunjunganPasien.objects.exists())
        response = self.client.post(reverse('pasien:apm_api_daftar'), {**payload, **self.identity})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(KunjunganPasien.objects.get().pasien_id, self.pasien.pk)

    def test_new_patient_cannot_reuse_another_identity(self):
        response = self.client.post(reverse('pasien:apm_api_daftar'), {
            'tipe_pasien':'BARU', 'jenis_layanan':'IGD', 'nik':self.pasien.nik,
            'nama_lengkap':'Orang Lain', 'tanggal_lahir':'1991-01-01', 'jenis_kelamin':'L',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(KunjunganPasien.objects.exists())
        self.assertEqual(Pasien.objects.count(), 1)

    def test_invalid_birthdate_is_not_replaced_with_today(self):
        response = self.client.post(reverse('pasien:apm_api_daftar'), {
            'tipe_pasien':'BARU', 'jenis_layanan':'IGD', 'nama_lengkap':'Tanggal Salah',
            'tanggal_lahir':'not-a-date', 'jenis_kelamin':'L',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Pasien.objects.count(), 1)
        self.assertFalse(KunjunganPasien.objects.exists())

    def test_checkin_requires_identity_and_retries_preserve_progress(self):
        from unittest.mock import patch
        visit = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-CHECKIN-SEC',
            tanggal_masuk=timezone.now(), jenis_kunjungan='RAJAL', is_apm=True,
            kode_booking='APM-IDENTITY-CHECKIN', penjamin='BPJS',
        )
        url = reverse('pasien:apm_api_checkin')
        with patch('pasien.apm_views.update_task_id') as update:
            self.assertEqual(self.client.get(url, {'kode':visit.kode_booking}).status_code, 405)
            self.assertEqual(self.client.post(url, {'kode':visit.kode_booking}).status_code, 403)
            visit.refresh_from_db()
            self.assertFalse(visit.is_checkin)
            self.assertEqual(self.client.post(url, {'kode':visit.kode_booking, **self.identity}).status_code, 200)
            visit.refresh_from_db()
            original_time = visit.waktu_checkin
            visit.status_antrean = 'DIPANGGIL'
            visit.save(update_fields=['status_antrean'])
            self.assertEqual(self.client.post(url, {'kode':visit.kode_booking, **self.identity}).status_code, 200)
            visit.refresh_from_db()
            self.assertEqual(visit.waktu_checkin, original_time)
            self.assertEqual(visit.status_antrean, 'DIPANGGIL')
            update.assert_called_once()

    def test_rejected_schedule_does_not_leave_patient_or_phone_changes(self):
        url = reverse('pasien:apm_api_daftar')
        response = self.client.post(url, {
            'tipe_pasien':'BARU', 'jenis_layanan':'RAJAL', 'jadwal_id':999999,
            'nama_lengkap':'Tidak Jadi Daftar', 'tanggal_lahir':'1992-01-01', 'jenis_kelamin':'L',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Pasien.objects.count(), 1)
        response = self.client.post(url, {
            'tipe_pasien':'LAMA', 'jenis_layanan':'RAJAL', 'jadwal_id':999999,
            'no_rm':self.pasien.no_rm, 'no_wa':'081211111111', **self.identity,
        })
        self.assertEqual(response.status_code, 400)
        self.pasien.refresh_from_db()
        self.assertEqual(self.pasien.no_hp, '081299998888')

    def test_malformed_registration_json_returns_validation_error(self):
        url = reverse('pasien:apm_api_daftar')
        for payload in ([], None, {'tipe_pasien':None}, {'nama_lengkap':123}, {'jadwal_id':'abc'}):
            with self.subTest(payload=payload):
                response = self.client.post(url, payload, content_type='application/json')
                self.assertEqual(response.status_code, 400)
        self.assertFalse(KunjunganPasien.objects.exists())

    def test_mutation_endpoints_require_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        for name in ('apm_api_daftar', 'apm_api_checkin', 'apm_batal_mandiri'):
            with self.subTest(endpoint=name):
                self.assertEqual(client.post(reverse('pasien:' + name), {}).status_code, 403)
