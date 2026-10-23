from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AktivitasBebanKerja,
    HcGrant,
    HasilFormasi,
    Pegawai,
    PenempatanPegawai,
    RencanaFormasi,
    calculate_formasi,
)
from sdm.services.formasi import approve_plan, save_plan, submit_for_review


class FormasiCalculationTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit FTE', code='HC-FTE')
        self.other = UnitKerja.objects.create(name='Unit Lain FTE', code='HC-FTE-2')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat FTE', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=60),
            alokasi_fte=Decimal('0.75'),
        )
        self.plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=self.today - timedelta(days=30),
            periode_selesai=self.today + timedelta(days=30),
            effective_minutes_per_employee=Decimal('1000.00'),
            support_allowance_pct=Decimal('10.00'),
        )

    def _activity(self, volume, minutes, name='Aktivitas'):
        return AktivitasBebanKerja.objects.create(
            rencana=self.plan,
            nama=name,
            volume=Decimal(volume),
            standard_minutes=Decimal(minutes),
        )

    def test_required_fte_matches_documented_formula(self):
        self._activity('100.00', '10.00')

        result = calculate_formasi(self.plan)

        # 1000 minutes * 1.10 allowance / 1000 effective minutes = 1.10
        self.assertEqual(result['required_fte'], Decimal('1.10'))
        self.assertEqual(result['required_headcount'], 2)
        self.assertEqual(result['actual_fte'], Decimal('0.75'))
        self.assertEqual(result['gap_fte'], Decimal('0.35'))

    def test_zero_effective_time_never_produces_a_result(self):
        self._activity('10.00', '10.00')
        self.plan.effective_minutes_per_employee = Decimal('0.00')

        with self.assertRaises(ValidationError):
            calculate_formasi(self.plan)

    def test_negative_activity_inputs_are_rejected(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            AktivitasBebanKerja.objects.create(
                rencana=self.plan,
                nama='Negatif',
                volume=Decimal('-5.00'),
                standard_minutes=Decimal('10.00'),
            )

        self.assertFalse(self.plan.activities.exists())

    def test_plan_without_activities_is_not_calculable(self):
        with self.assertRaises(ValidationError):
            calculate_formasi(self.plan)

    def test_allowance_is_applied_once_not_double_counted(self):
        self._activity('100.00', '10.00')
        single = calculate_formasi(self.plan)['required_fte']
        self.plan.support_allowance_pct = Decimal('0.00')
        self.plan.save(update_fields=['support_allowance_pct'])
        plain = calculate_formasi(self.plan)['required_fte']

        self.assertEqual(single, Decimal('1.10'))
        self.assertEqual(plain, Decimal('1.00'))

    def test_assignments_outside_the_period_end_are_excluded(self):
        self.employee.penempatan.all().delete()
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=90),
            tanggal_selesai=self.today - timedelta(days=40),
            alokasi_fte=Decimal('1.00'),
        )
        self._activity('100.00', '10.00')

        result = calculate_formasi(self.plan)

        self.assertEqual(result['actual_fte'], Decimal('0.00'))

    def test_split_assignment_counts_only_its_fraction(self):
        other_employee = Pegawai.objects.create(
            nama_lengkap='Perawat Split', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=other_employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('0.50'),
        )
        PenempatanPegawai.objects.create(
            pegawai=other_employee,
            unit_kerja=self.other,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('0.50'),
        )
        self._activity('100.00', '10.00')

        result = calculate_formasi(self.plan)

        self.assertEqual(result['actual_fte'], Decimal('1.25'))

    def test_foreign_unit_assignments_do_not_count(self):
        foreign_employee = Pegawai.objects.create(
            nama_lengkap='Perawat Asing', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=foreign_employee,
            unit_kerja=self.other,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        self._activity('100.00', '10.00')

        result = calculate_formasi(self.plan)

        self.assertEqual(result['actual_fte'], Decimal('0.75'))


class FormasiWorkflowTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Alur', code='HC-FLOW')
        self.creator = self._user('planner')
        self.approver = self._user('approver')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_plan_hc_workforce = True
        config.save(update_fields=['can_plan_hc_workforce', 'updated_at'])
        for user in (self.creator, self.approver):
            HcGrant.objects.create(
                user=user, capability='can_plan_hc_workforce', unit_kerja=self.unit
            )
        self.plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=self.today,
            periode_selesai=self.today + timedelta(days=30),
            effective_minutes_per_employee=Decimal('1000.00'),
            created_by=self.creator,
        )
        AktivitasBebanKerja.objects.create(
            rencana=self.plan, nama='Asuhan', volume=Decimal('100.00'),
            standard_minutes=Decimal('10.00'),
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user

    def test_approval_freezes_an_immutable_result_version(self):
        submit_for_review(self.plan, user=self.creator)
        approve_plan(self.plan, user=self.approver)

        result = HasilFormasi.objects.get(rencana=self.plan)
        self.assertEqual(result.required_fte, Decimal('1.00'))
        with self.assertRaises(ValidationError):
            result.required_fte = Decimal('99.00')
            result.save()

    def test_creator_cannot_approve_their_own_plan(self):
        submit_for_review(self.plan, user=self.creator)

        with self.assertRaises(PermissionDenied):
            approve_plan(self.plan, user=self.creator)

    def test_approved_plan_cannot_be_edited(self):
        submit_for_review(self.plan, user=self.creator)
        approve_plan(self.plan, user=self.approver)
        self.plan.profesi = 'Perawat Baru'

        with self.assertRaises(ValidationError):
            save_plan(self.plan, user=self.creator)

    def test_approving_a_new_plan_supersedes_the_previous_one(self):
        submit_for_review(self.plan, user=self.creator)
        approve_plan(self.plan, user=self.approver)
        new_plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=self.today + timedelta(days=31),
            periode_selesai=self.today + timedelta(days=60),
            effective_minutes_per_employee=Decimal('1000.00'),
            created_by=self.creator,
        )
        AktivitasBebanKerja.objects.create(
            rencana=new_plan, nama='Asuhan', volume=Decimal('100.00'),
            standard_minutes=Decimal('10.00'),
        )

        submit_for_review(new_plan, user=self.creator)
        approve_plan(new_plan, user=self.approver)

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'SUPERSEDED')

    def test_submitting_a_plan_without_activities_is_rejected(self):
        empty = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Bidan',
            periode_mulai=self.today,
            periode_selesai=self.today + timedelta(days=30),
            effective_minutes_per_employee=Decimal('1000.00'),
            created_by=self.creator,
        )

        with self.assertRaises(ValidationError):
            submit_for_review(empty, user=self.creator)
