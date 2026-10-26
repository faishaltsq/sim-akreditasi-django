"""Tests for F-A2: reference standards and effective working time.

`JamKerjaEfektif` is the single approved source for "how many productive
minutes does one employee deliver per year". It is versioned and immutable
once approved, so a plan's printed report stays reproducible even after the
hospital revises its assumptions.
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from akreditasi.models import UnitKerja
from sdm.models import JamKerjaEfektif, RencanaFormasi, StandarKetenagaan


class JamKerjaEfektifTests(TestCase):
    def _jke(self, **overrides):
        data = dict(
            tahun=2026,
            hari_kerja=250,
            cuti_tahunan=12,
            hari_sakit_rata2=5,
            libur_nasional=16,
            jam_pelatihan=20,
            jam_kerja_per_hari=Decimal('7.00'),
        )
        data.update(overrides)
        return JamKerjaEfektif(**data)

    def test_productive_days_subtract_every_documented_deduction(self):
        """250 working days minus 12 leave, 5 sick, 16 holidays = 217 days."""
        jke = self._jke()
        self.assertEqual(jke.hari_produktif, 217)

    def test_effective_minutes_subtract_training_hours(self):
        """217 days x 7 h = 1519 h, minus 20 h training = 1499 h = 89940 min."""
        jke = self._jke()
        self.assertEqual(jke.jam_efektif_per_tahun, Decimal('1499.00'))
        self.assertEqual(jke.menit_efektif_per_tahun, Decimal('89940.00'))

    def test_missing_component_never_silently_becomes_zero(self):
        """A blank deduction is unknown, not zero: the result must be refused."""
        jke = self._jke(cuti_tahunan=None)
        with self.assertRaises(ValidationError):
            jke.full_clean()

    def test_deductions_cannot_exceed_available_working_days(self):
        jke = self._jke(hari_kerja=100, cuti_tahunan=60, hari_sakit_rata2=50,
                        libur_nasional=10)
        with self.assertRaises(ValidationError):
            jke.full_clean()

    def test_effective_minutes_cannot_be_non_positive(self):
        jke = self._jke(jam_pelatihan=Decimal('5000.00'))
        with self.assertRaises(ValidationError):
            jke.full_clean()

    def test_approved_year_is_immutable(self):
        jke = self._jke()
        jke.full_clean()
        jke.save()
        jke.approve(by=None)
        jke.hari_kerja = 300
        with self.assertRaises(ValidationError):
            jke.save()

    def test_approving_a_second_version_without_supersede_is_refused(self):
        first = self._jke()
        first.full_clean()
        first.save()
        first.approve(by=None)
        second = self._jke(hari_kerja=251, versi=2)
        second.full_clean()
        second.save()  # a draft is always allowed
        with self.assertRaises(ValidationError):
            second.approve(by=None)
        first.refresh_from_db()
        self.assertTrue(first.is_active)

    def test_a_new_version_supersedes_the_previous_one_when_told_to(self):
        first = self._jke()
        first.full_clean()
        first.save()
        first.approve(by=None)
        second = self._jke(hari_kerja=251, versi=2)
        second.full_clean()
        second.save()
        second.approve(by=None, supersede_previous=True)
        first.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
        self.assertTrue(second.is_approved)


class StandarKetenagaanTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='ICU', code='ICU-01')

    def test_ratio_requires_a_named_regulatory_source(self):
        standar = StandarKetenagaan(
            unit_kerja=self.unit, profesi='Perawat', jenis='RASIO_REGULASI',
            nilai=Decimal('1.00'), satuan='perawat per pasien per shift',
        )
        with self.assertRaises(ValidationError):
            standar.full_clean()

    def test_retired_standard_stays_readable_for_historical_reports(self):
        standar = StandarKetenagaan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', jenis='RASIO_REGULASI',
            nilai=Decimal('1.00'), satuan='perawat per pasien per shift',
            sumber_regulasi='Kepmenkes 1128/2022', berlaku_mulai=date(2022, 1, 1),
        )
        standar.retire()
        standar.refresh_from_db()
        self.assertFalse(standar.is_active)
        self.assertEqual(standar.nilai, Decimal('1.00'))
        self.assertEqual(standar.sumber_regulasi, 'Kepmenkes 1128/2022')


class PlanEffectiveMinutesResolutionTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Rawat Inap', code='RI-01')
        self.jke = JamKerjaEfektif(
            tahun=2026, hari_kerja=250, cuti_tahunan=12, hari_sakit_rata2=5,
            libur_nasional=16, jam_pelatihan=20, jam_kerja_per_hari=Decimal('7.00'),
        )
        self.jke.full_clean()
        self.jke.save()

    def _plan(self, **overrides):
        data = dict(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=date(2026, 1, 1),
            periode_selesai=date(2026, 12, 31),
            effective_minutes_per_employee=Decimal('1000.00'),
        )
        data.update(overrides)
        return RencanaFormasi(**data)

    def test_approved_year_supplies_the_effective_minutes(self):
        self.jke.approve(by=None)
        plan = self._plan(jam_kerja_efektif=self.jke)
        self.assertEqual(plan.resolve_effective_minutes(), Decimal('89940.00'))

    def test_unapproved_year_refuses_and_reports_why(self):
        plan = self._plan(jam_kerja_efektif=self.jke)
        with self.assertRaises(ValidationError) as ctx:
            plan.resolve_effective_minutes()
        self.assertIn('Belum disetujui', str(ctx.exception))

    def test_manual_override_is_recorded_as_an_override(self):
        self.jke.approve(by=None)
        plan = self._plan(
            effective_minutes_per_employee=Decimal('75000.00'),
            override_alasan='Studi waktu unit khusus 2026',
        )
        self.assertEqual(plan.resolve_effective_minutes(), Decimal('75000.00'))
        self.assertTrue(plan.is_manual_override)

    def test_override_without_a_reason_is_rejected(self):
        plan = self._plan(effective_minutes_per_employee=Decimal('75000.00'))
        with self.assertRaises(ValidationError):
            plan.full_clean()
