from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from akreditasi.models import UnitKerja
from sdm.models import Pegawai, PenempatanPegawai
from sdm.services.penempatan import save_assignment


class PenempatanAllocationTests(TestCase):
    def setUp(self):
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Formasi', kategori='NON_PPA'
        )
        self.unit = UnitKerja.objects.create(name='Unit Formasi', code='FORMASI-TEST')

    def assignment(self, start, end, fte):
        return PenempatanPegawai(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=start,
            tanggal_selesai=end,
            alokasi_fte=Decimal(fte),
        )

    def test_overlapping_allocations_cannot_exceed_one_fte(self):
        save_assignment(self.assignment(date(2026, 1, 1), date(2026, 6, 30), '0.70'))

        with self.assertRaises(ValidationError):
            save_assignment(self.assignment(date(2026, 4, 1), date(2026, 8, 31), '0.40'))

    def test_nonoverlapping_assignments_can_each_use_full_time(self):
        save_assignment(self.assignment(date(2026, 1, 1), date(2026, 6, 30), '1.00'))
        later = save_assignment(
            self.assignment(date(2026, 7, 1), date(2026, 12, 31), '1.00')
        )

        self.assertEqual(PenempatanPegawai.objects.count(), 2)
        self.assertEqual(later.alokasi_fte, Decimal('1.00'))

    def test_disjoint_overlaps_are_checked_by_peak_period_not_total_sum(self):
        save_assignment(self.assignment(date(2026, 1, 1), date(2026, 6, 30), '0.80'))
        save_assignment(self.assignment(date(2026, 7, 1), date(2026, 12, 31), '0.80'))
        whole_year = save_assignment(
            self.assignment(date(2026, 1, 1), date(2026, 12, 31), '0.20')
        )

        self.assertIsNotNone(whole_year.pk)

    def test_open_ended_overlap_is_enforced(self):
        save_assignment(self.assignment(date(2026, 1, 1), None, '0.60'))

        with self.assertRaises(ValidationError):
            save_assignment(self.assignment(date(2026, 5, 1), None, '0.50'))

    def test_update_excludes_the_same_assignment_from_overlap_sum(self):
        assignment = save_assignment(
            self.assignment(date(2026, 1, 1), date(2026, 12, 31), '0.50')
        )
        assignment.alokasi_fte = Decimal('0.75')
        saved = save_assignment(assignment)

        self.assertEqual(saved.alokasi_fte, Decimal('0.75'))
        self.assertEqual(PenempatanPegawai.objects.count(), 1)
