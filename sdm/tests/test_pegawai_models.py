from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import Pegawai, PenempatanPegawai


class PegawaiModelTests(TestCase):
    def test_employee_primary_key_is_an_opaque_uuid(self):
        employee = Pegawai.objects.create(
            nama_lengkap='Pegawai UUID', kategori='NON_PPA'
        )

        self.assertIsInstance(employee.pk, UUID)

    def test_employee_without_account_and_non_ppa_are_supported(self):
        employee = Pegawai.objects.create(
            nama_lengkap='Staf Administrasi',
            kategori='NON_PPA',
        )

        self.assertIsNone(employee.akun)
        self.assertEqual(employee.kategori, 'NON_PPA')

    def test_nonblank_employee_number_must_be_unique(self):
        Pegawai.objects.create(nama_lengkap='Pegawai Satu', nomor_pegawai='HC-001', kategori='NON_PPA')

        with self.assertRaises(IntegrityError), transaction.atomic():
            Pegawai.objects.create(nama_lengkap='Pegawai Dua', nomor_pegawai='HC-001', kategori='NON_PPA')

    def test_blank_employee_numbers_can_repeat(self):
        Pegawai.objects.create(nama_lengkap='Pegawai Satu', nomor_pegawai='', kategori='NON_PPA')
        Pegawai.objects.create(nama_lengkap='Pegawai Dua', nomor_pegawai='', kategori='NON_PPA')

        self.assertEqual(Pegawai.objects.filter(nomor_pegawai='').count(), 2)

    def test_deleting_linked_account_preserves_employee(self):
        user = get_user_model().objects.create_user(username='staff-hc')
        employee = Pegawai.objects.create(nama_lengkap='Pegawai Terkait', kategori='NON_PPA', akun=user)
        employee_id = employee.pk

        user.delete()
        employee.refresh_from_db()

        self.assertEqual(employee.pk, employee_id)
        self.assertIsNone(employee.akun)


class PenempatanPegawaiModelTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Human Capital', code='HC-TEST')
        self.employee = Pegawai.objects.create(nama_lengkap='Pegawai Tes', kategori='NON_PPA')
        self.today = timezone.localdate()

    def test_assignment_is_inactive_outside_its_date_range(self):
        assignment = PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=20),
            tanggal_selesai=self.today - timedelta(days=1),
            alokasi_fte=Decimal('1.00'),
        )

        self.assertFalse(assignment.is_current)

    def test_assignment_is_current_on_inclusive_start_and_end_dates(self):
        assignment = PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today,
            tanggal_selesai=self.today,
            alokasi_fte=Decimal('0.50'),
        )

        self.assertTrue(assignment.is_current)

    def test_allocation_must_be_positive_and_at_most_one_fte(self):
        for allocation in (Decimal('0.00'), Decimal('1.01')):
            with self.subTest(allocation=allocation):
                assignment = PenempatanPegawai(
                    pegawai=self.employee,
                    unit_kerja=self.unit,
                    tanggal_mulai=self.today,
                    alokasi_fte=allocation,
                )
                with self.assertRaises(ValidationError):
                    assignment.full_clean()

    def test_end_date_cannot_precede_start_date(self):
        assignment = PenempatanPegawai(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today,
            tanggal_selesai=self.today - timedelta(days=1),
            alokasi_fte=Decimal('1.00'),
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_database_rejects_invalid_allocation_and_date_range(self):
        invalid_assignments = (
            {'alokasi_fte': Decimal('0.00')},
            {'alokasi_fte': Decimal('1.01')},
            {'alokasi_fte': Decimal('1.00'), 'tanggal_selesai': self.today - timedelta(days=1)},
        )
        for values in invalid_assignments:
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    PenempatanPegawai.objects.create(
                        pegawai=self.employee,
                        unit_kerja=self.unit,
                        tanggal_mulai=self.today,
                        **values,
                    )
