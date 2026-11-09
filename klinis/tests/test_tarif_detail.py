from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from akreditasi.models import UnitKerja
from klinis.services.tarif import resolve, resolve_detail
from pasien.models import KunjunganPasien, Pasien


class ResolveDetailTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Detail', no_rm='RM-DTL-001',
            tanggal_lahir='1990-01-01', jenis_kelamin='L',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-DTL-001', jenis_kunjungan='IGD',
            unit_kerja=UnitKerja.objects.filter(code='IGD').first(),
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='AKTIF',
        )

    def test_detail_carries_nominal_and_names(self):
        d = resolve_detail(self.kunjungan, '89.52')
        self.assertIsNotNone(d)
        self.assertEqual(d['nominal'], Decimal('150000.00'))
        self.assertEqual(d['icd9'].kode, '89.52')
        self.assertTrue(d['icd9'].nama)
        self.assertEqual(d['penjamin'], 'UMUM')
        self.assertEqual(d['kelompok'].kode, 'IGD')

    def test_detail_none_for_unknown_code(self):
        self.assertIsNone(resolve_detail(self.kunjungan, '99.9999'))

    def test_detail_none_when_kelompok_missing(self):
        self.kunjungan.jenis_kunjungan = 'ZZZ'
        self.kunjungan.unit_kerja = None
        self.kunjungan.save(update_fields=['jenis_kunjungan', 'unit_kerja'])
        self.assertIsNone(resolve_detail(self.kunjungan, '89.52'))

    def test_resolve_still_returns_decimal(self):
        self.assertEqual(resolve(self.kunjungan, '89.52'), Decimal('150000.00'))
        self.assertIsNone(resolve(self.kunjungan, '99.9999'))

    def test_detail_uses_bpjs_tariff_for_bpjs_visit(self):
        self.kunjungan.penjamin = 'BPJS'
        self.kunjungan.save(update_fields=['penjamin'])
        self.assertEqual(resolve_detail(self.kunjungan, '89.52')['nominal'],
                         Decimal('120000.00'))
