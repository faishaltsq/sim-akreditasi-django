from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from klinis.services.saran import saran_untuk
from pasien.models import KunjunganPasien, Pasien


class SaranIcdTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 3})
        UnitKerja.objects.get_or_create(code='ICCU', defaults={'name': 'ICCU', 'level': 3})
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user(username='dokter.saran', password='password123')
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Saran', no_rm='RM-SARAN-001',
            tanggal_lahir='1991-03-03', jenis_kelamin='P',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-SARAN-001', jenis_kunjungan='IGD',
            unit_kerja=UnitKerja.objects.filter(code='IGD').first(),
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='AKTIF',
        )
        self.kunjungan_jantung = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-SARAN-002', jenis_kunjungan='RANAP',
            unit_kerja=UnitKerja.objects.filter(code='ICCU').first(),
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='AKTIF',
        )

    def test_query_narrows_to_matching_case(self):
        items = saran_untuk(self.kunjungan, 'infark')
        self.assertTrue(items)
        self.assertTrue(all(item['skor'] > 0 for item in items))
        self.assertTrue(any('nfark' in item['nama'] for item in items))

    def test_scoped_to_kelompok(self):
        kode_igd = {item['kode'] for item in saran_untuk(self.kunjungan, '')}
        kode_jantung = {item['kode'] for item in saran_untuk(self.kunjungan_jantung, '')}
        self.assertTrue(kode_igd)
        self.assertTrue(kode_jantung)
        self.assertNotEqual(kode_igd, kode_jantung)

    def test_empty_query_returns_first_rows(self):
        self.assertLessEqual(len(saran_untuk(self.kunjungan, '')), 5)

    def test_unknown_kelompok_returns_empty(self):
        self.kunjungan.jenis_kunjungan = 'ZZZ'
        self.kunjungan.unit_kerja = None
        self.kunjungan.save(update_fields=['jenis_kunjungan', 'unit_kerja'])
        self.assertEqual(saran_untuk(self.kunjungan, 'infark'), [])

    def test_endpoint_returns_items(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse('pasien:api_saran_icd'),
            {'kunjungan': self.kunjungan.pk, 'q': 'infark'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['items'])

    def test_endpoint_requires_kunjungan_param(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('pasien:api_saran_icd'))
        self.assertEqual(resp.status_code, 400)
