from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from accounts.models import UserProfile
from klinis.models import (
    SdkiDiagnosis, SlkiLuaran, SikiIntervensi, Pemetaan3S, AturanEpTindakan
)
from pasien.models import Pasien, KunjunganPasien


class Cascade3STest(TestCase):
    @classmethod
    def setUpTestData(cls):
        UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 3})
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user(username='dokter.cascade', password='password123')
        self.igd = UnitKerja.objects.filter(code='IGD').first()
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={'role': 'ADMIN_RS', 'unit_kerja': self.igd}
        )
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien 3S', no_rm='RM-3S-001',
            tanggal_lahir='1995-05-05', jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-3S-001', jenis_kunjungan='IGD',
            unit_kerja=self.igd,
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='AKTIF',
        )

    def test_cascade_endpoint_requires_auth(self):
        resp = self.client.get(reverse('pasien:api_3s_cascade'))
        self.assertEqual(resp.status_code, 302)

    def test_cascade_returns_slki_and_siki_for_sdki(self):
        self.client.force_login(self.user)
        # Ambil salah satu SDKI yang ada di pemetaan
        pemetaan = Pemetaan3S.objects.first()
        self.assertIsNotNone(pemetaan)

        resp = self.client.get(
            reverse('pasien:api_3s_cascade'),
            {'sdki': pemetaan.sdki.kode, 'kunjungan': self.kunjungan.pk}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['sdki']['kode'], pemetaan.sdki.kode)
        self.assertTrue(len(data['slki_list']) >= 1)
        self.assertTrue(len(data['siki_list']) >= 1)
        self.assertIn(pemetaan.slki.kode, [s['kode'] for s in data['slki_list']])
        self.assertIn(pemetaan.siki.kode, [s['kode'] for s in data['siki_list']])

    def test_saran_icd9_returns_procedures(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse('pasien:api_saran_icd'),
            {'kunjungan': self.kunjungan.pk, 'jenis': 'ICD9'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['jenis'], 'ICD9')
        self.assertTrue(len(data['items']) >= 1)
        first = data['items'][0]
        self.assertIn('kode', first)
        self.assertIn('nama', first)
        self.assertIn('tarif', first)
