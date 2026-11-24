"""F0.1 — Catatan SOAP dasbor rajal harus benar-benar tersimpan.

Cacat lama: template ``templates/pasien/rajal_dashboard.html`` mengirim
``soap_s``/``soap_o``/``soap_a``/``soap_p`` sementara
``pasien.views.rajal_soap_simpan`` membaca ``subjektif``/``objektif``/
``asesmen``/``plan``. Keempat nilai selalu kosong, sehingga
``if s or o or a or p`` selalu ``False`` dan tidak ada ``CPPT`` yang dibuat.

Kontrak yang dikunci di sini: nama field yang dirender template adalah nama
yang dibaca view, dan POST dengan field template menghasilkan satu baris CPPT
berisi kiriman operator.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import CPPT, KunjunganPasien, Pasien


class RajalSoapSimpanTest(TestCase):
    password = 'pass123-soap'

    def setUp(self):
        self.unit_poli = UnitKerja.objects.get_or_create(
            code='POLI-JANTUNG',
            defaults={'name': 'Poliklinik Jantung', 'level': 4})[0]
        user = User.objects.create_user(
            username='dokter.jantung', email='dokter.jantung@rs.test',
            password=self.password)
        UserProfile.objects.create(
            user=user, role='STAF_NAKES', unit_kerja=self.unit_poli,
            profesi='DOKTER_SPESIALIS')
        self.assertTrue(self.client.login(
            username='dokter.jantung', password=self.password))

        self.pasien = Pasien.objects.create(
            no_rm='RM-SOAP-001', nama_lengkap='Pasien SOAP',
            tanggal_lahir='1980-01-01', jenis_kelamin='L')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='KJ-SOAP-001',
            jenis_kunjungan='RAJAL', poliklinik='POLI_JANTUNG',
            tanggal_masuk=timezone.now(), status='DAFTAR')

    def test_template_mengirim_nama_field_yang_dibaca_view(self):
        """Form SOAP di dasbor memakai nama field yang sama dengan view."""
        res = self.client.get(reverse('pasien:rajal_dashboard'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        for field in ('subjektif', 'objektif', 'asesmen', 'plan'):
            self.assertIn(f'name="{field}"', html)
        for field in ('soap_s', 'soap_o', 'soap_a', 'soap_p'):
            self.assertNotIn(f'name="{field}"', html)

    def test_post_soap_dari_template_menyimpan_satu_cppt(self):
        res = self.client.post(
            reverse('pasien:rajal_soap_simpan', args=[self.kunjungan.pk]),
            {
                'subjektif': 'Nyeri dada kiri menjalar ke lengan.',
                'objektif': 'TD 150/90, nadi 96, SpO2 98%.',
                'asesmen': 'Angina pektoris stabil.',
                'plan': 'EKG, troponin, kontrol 1 minggu.',
            },
        )
        self.assertEqual(res.status_code, 302)

        catatan = CPPT.objects.filter(kunjungan=self.kunjungan)
        self.assertEqual(catatan.count(), 1)
        cppt = catatan.get()
        self.assertEqual(cppt.subjektif, 'Nyeri dada kiri menjalar ke lengan.')
        self.assertEqual(cppt.objektif, 'TD 150/90, nadi 96, SpO2 98%.')
        self.assertEqual(cppt.asesmen, 'Angina pektoris stabil.')
        self.assertEqual(cppt.plan, 'EKG, troponin, kontrol 1 minggu.')

    def test_post_soap_kosong_tidak_membuat_cppt(self):
        res = self.client.post(
            reverse('pasien:rajal_soap_simpan', args=[self.kunjungan.pk]), {})
        self.assertEqual(res.status_code, 302)
        self.assertFalse(CPPT.objects.filter(kunjungan=self.kunjungan).exists())
