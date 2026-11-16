from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from klinis.services.saran import saran_untuk
from klinis.models import KasusTersering, KasusTindakan, KelompokLayanan, MasterIcd10, MasterIcd9
from decimal import Decimal
from types import SimpleNamespace
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


class DiagnosisProcedureMappingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = KelompokLayanan.objects.create(kode='MAP-IGD', nama='Mapping IGD')
        cls.other_group = KelompokLayanan.objects.create(kode='MAP-OTHER', nama='Other service')
        cls.diagnosis = MasterIcd10.objects.create(kode='Z.MAP1', nama='Identical diagnosis name')
        cls.other_diagnosis = MasterIcd10.objects.create(kode='Z.MAP2', nama='Identical diagnosis name')
        cls.procedure = MasterIcd9.objects.create(kode='M.01', nama='Canonical procedure')
        cls.unpriced = MasterIcd9.objects.create(kode='M.02', nama='Unpriced procedure')
        cls.foreign = MasterIcd9.objects.create(kode='M.03', nama='Foreign procedure')
        early = KasusTersering.objects.create(kelompok=cls.group, icd10=cls.other_diagnosis, urutan=1)
        case = KasusTersering.objects.create(kelompok=cls.group, icd10=cls.diagnosis, urutan=2)
        duplicate = KasusTersering.objects.create(kelompok=cls.group, icd10=cls.diagnosis, urutan=3)
        foreign = KasusTersering.objects.create(kelompok=cls.other_group, icd10=cls.diagnosis, urutan=1)
        KasusTindakan.objects.create(kasus=early, icd9=cls.procedure, tarif_umum=Decimal('12.34'), tarif_bpjs=Decimal('8.90'))
        KasusTindakan.objects.create(kasus=early, icd9=cls.foreign)
        KasusTindakan.objects.create(kasus=case, icd9=cls.procedure, urutan=1, tarif_umum=Decimal('99'))
        KasusTindakan.objects.create(kasus=case, icd9=cls.unpriced, urutan=2)
        KasusTindakan.objects.create(kasus=duplicate, icd9=cls.procedure)
        KasusTindakan.objects.create(kasus=foreign, icd9=cls.procedure, tarif_umum=Decimal('777'))
        KasusTindakan.objects.create(kasus=foreign, icd9=cls.foreign)

    def suggestions(self, code=None, **kwargs):
        from klinis.services.saran import tindakan_untuk_diagnosis
        visit = SimpleNamespace(unit_kerja_id=None, jenis_kunjungan=self.group.kode, penjamin='UMUM')
        return tindakan_untuk_diagnosis(visit, code or self.diagnosis.kode, **kwargs)

    def test_exact_fk_group_dedup_order_and_resolver_price(self):
        rows = self.suggestions()
        self.assertEqual([row['kode'] for row in rows], ['M.01', 'M.02'])
        self.assertEqual(rows[0]['nama'], 'Canonical procedure')
        self.assertEqual(rows[0]['tarif'], '12.34')  # Canonical resolver, not diagnosis-local price.
        self.assertIsNone(rows[1]['tarif'])
        self.assertTrue(all(not isinstance(row['tarif'], float) for row in rows))

    def test_query_limit_unmapped_and_unknown_service(self):
        self.assertEqual([r['kode'] for r in self.suggestions(query='unpriced')], ['M.02'])
        self.assertEqual([r['kode'] for r in self.suggestions(query='M.01')], ['M.01'])
        self.assertEqual(len(self.suggestions(limit=1)), 1)
        self.assertEqual(self.suggestions(limit=0), [])
        self.assertEqual(self.suggestions(code='Z.UNMAPPED'), [])
        from klinis.services.saran import tindakan_untuk_diagnosis
        visit = SimpleNamespace(unit_kerja_id=None, jenis_kunjungan='NO-GROUP', penjamin='UMUM')
        self.assertEqual(tindakan_untuk_diagnosis(visit, self.diagnosis.kode), [])

    def test_bpjs_and_other_group_use_existing_resolver(self):
        from klinis.services.saran import tindakan_untuk_diagnosis
        visit = SimpleNamespace(unit_kerja_id=None, jenis_kunjungan=self.group.kode, penjamin='BPJS')
        self.assertEqual(tindakan_untuk_diagnosis(visit, self.diagnosis.kode)[0]['tarif'], '8.90')
        visit.jenis_kunjungan = self.other_group.kode
        visit.penjamin = 'UMUM'
        self.assertEqual(tindakan_untuk_diagnosis(visit, self.diagnosis.kode)[0]['tarif'], '777.00')
