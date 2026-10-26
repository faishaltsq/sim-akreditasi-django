"""RED/GREEN tests for Task A4 + F-A1: workload planning and separate WISN method.

The available-working-time arithmetic is pinned against hand-computed
worksheets. WISN must never be relabelled activity FTE, and a plan with
incomplete or impossible inputs must refuse to produce a number.
"""

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
            calculation_version='wisn-v2',
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

    # ── available working time: the arithmetic that was wrong ──────────────

    def test_available_hours_match_hand_computed_worksheet(self):
        """30-day period, 8 h/day, 5 days/week.

        30 days x 5/7 = 150/7 operating days; x 8 h = 1200/7 = 171.4286 h.
        The previous implementation divided by 7 twice and returned 24.49 h.
        """
        result = calculate_wisn(self._plan())
        self.assertEqual(result['available_hours'], Decimal('171.4286'))
        self.assertEqual(result['available_minutes'], Decimal('10285.7143'))

    def test_required_fte_is_exact_for_the_reference_case(self):
        """55440 adjusted minutes over 72000/7 available minutes = 5.39 exactly."""
        result = calculate_wisn(self._plan())
        self.assertEqual(result['standard_workload_minutes'], Decimal('48000.0000'))
        self.assertEqual(result['adjusted_workload_minutes'], Decimal('55440.0000'))
        self.assertEqual(result['required_fte'], Decimal('5.3900'))

    def test_31_day_period_scales_by_calendar_days(self):
        plan = self._plan(periode_selesai=self.today + timedelta(days=30))
        result = calculate_wisn(plan)
        self.assertEqual(result['available_hours'], Decimal('177.1429'))
        self.assertEqual(result['required_fte'], Decimal('5.2161'))

    def test_seven_day_service_counts_every_calendar_day(self):
        """A 24/7 unit (ICU) operates 30 of 30 days: 240 h available."""
        plan = self._plan(hari_operasional_per_minggu=Decimal('7.00'))
        result = calculate_wisn(plan)
        self.assertEqual(result['available_hours'], Decimal('240.0000'))
        self.assertEqual(result['required_fte'], Decimal('3.8500'))

    def test_single_day_period_never_divides_by_zero(self):
        plan = self._plan(periode_selesai=self.today)
        result = calculate_wisn(plan)
        self.assertGreater(result['available_minutes'], Decimal('0'))
        self.assertGreater(result['required_fte'], Decimal('0'))

    # ── refusals ───────────────────────────────────────────────────────────

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

    def test_rejects_more_than_seven_operating_days_per_week(self):
        plan = self._plan(hari_operasional_per_minggu=Decimal('8.00'))
        with self.assertRaises(Exception):
            calculate_wisn(plan)

    def test_rejects_zero_operating_days_per_week(self):
        plan = self._plan(hari_operasional_per_minggu=Decimal('0.00'))
        with self.assertRaises(Exception):
            calculate_wisn(plan)

    # ── method honesty ─────────────────────────────────────────────────────

    def test_wisn_not_activity_fte(self):
        result = calculate_wisn(self._plan())
        self.assertEqual(result['calculation_version'], 'wisn-v2')
        self.assertNotEqual(result['calculation_version'], 'activity-fte-v1')
        self.assertEqual(result['metode'], 'WISN')

    def test_result_carries_every_input_needed_for_an_audit_worksheet(self):
        result = calculate_wisn(self._plan())
        for key in (
            'periode_mulai', 'periode_selesai', 'days_in_period',
            'operating_days_in_period', 'jam_operasional_per_hari',
            'hari_operasional_per_minggu', 'kunjungan_periode',
            'standard_minutes_per_kunjungan', 'available_hours',
            'available_minutes', 'standard_workload_minutes',
            'allowance_factor', 'adjusted_workload_minutes', 'required_fte',
            'calculation_version', 'coverage_complete',
        ):
            self.assertIn(key, result, msg=f'hasil WISN tidak memuat {key}')
        self.assertEqual(result['days_in_period'], 30)
