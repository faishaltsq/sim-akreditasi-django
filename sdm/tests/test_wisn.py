"""RED tests for Task A4: workload planning and separate WISN method."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from akreditasi.models import UnitKerja
from sdm.models import BebanKerja
from sdm.services.wisn import calculate_wisn


class WISNTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Poli Umum', code='POL-UM')
        self.today = date(2026, 11, 1)

    def _plan(self, **overrides):
        data = dict(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=self.today,
            periode_selesai=self.today + timedelta(days=29),
            metode='WISN',
            calculation_version='wisn-v1',
            jam_operasional_per_hari=Decimal('8.00'),
            hari_operasional_per_minggu=Decimal('5.00'),
            kunjungan_periode=1600,
            standard_minutes_per_kunjungan=30,
            faktor_pengantar_kategori=Decimal('1.1000'),
            faktor_pengantar_individu=Decimal('1.0500'),
            is_approved=True,
        )
        data.update(overrides)
        return BebanKerja.objects.create(**data)

    def test_wisn_required_fte_computed(self):
        plan = self._plan()
        result = calculate_wisn(plan)
        self.assertEqual(result['metode'], 'WISN')
        self.assertTrue(result['coverage_complete'])
        self.assertGreater(result['required_fte'], Decimal('0'))

    def test_wisn_rejects_activity_fte_metode(self):
        plan = self._plan(metode='ACTIVITY_FTE')
        with self.assertRaises(Exception):
            calculate_wisn(plan)

    def test_wisn_rejects_unapproved_plan(self):
        plan = self._plan(is_approved=False)
        with self.assertRaises(Exception):
            calculate_wisn(plan)

    def test_wisn_rejects_missing_coverage(self):
        plan = self._plan(standard_minutes_per_kunjungan=None)
        with self.assertRaises(Exception):
            calculate_wisn(plan)

    def test_wisn_not_activity_fte(self):
        plan = self._plan()
        result = calculate_wisn(plan)
        self.assertEqual(result['calculation_version'], 'wisn-v1')
        self.assertNotEqual(result['calculation_version'], 'activity-fte-v1')
