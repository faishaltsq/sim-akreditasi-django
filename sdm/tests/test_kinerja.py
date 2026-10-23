from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    ButirPenilaian,
    HcGrant,
    KebutuhanPelatihan,
    PenilaianKinerja,
    PeriodeKinerja,
    Pegawai,
    PenempatanPegawai,
    PesertaDiklat,
    ProgramDiklat,
    SesiDiklat,
    SumberKebutuhanPelatihan,
)
from sdm.services.kinerja import (
    acknowledge_appraisal,
    approve_training_need,
    complete_training,
    file_appeal,
    finalize_appraisal,
    propose_training_needs,
    record_attendance,
    register_participant,
)


class LevelThreeBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Level3', code='HC-L3')
        self.user = self._user('level3-hr')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_manage_hc_appraisals = True
        config.can_manage_hc_training = True
        config.save(update_fields=[
            'can_manage_hc_appraisals', 'can_manage_hc_training', 'updated_at',
        ])
        for capability in ('can_manage_hc_appraisals', 'can_manage_hc_training'):
            HcGrant.objects.create(
                user=self.user, capability=capability, unit_kerja=self.unit
            )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Level3', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=20),
            alokasi_fte=Decimal('1.00'),
        )
        self.period = PeriodeKinerja.objects.create(
            nama='Semester 1', tanggal_mulai=self.today - timedelta(days=180),
            tanggal_selesai=self.today,
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user

    def _appraisal(self, *, score=Decimal('2.00')):
        appraisal = PenilaianKinerja.objects.create(
            periode=self.period, employee=self.employee, reviewer=self.user
        )
        ButirPenilaian.objects.create(
            appraisal=appraisal, kategori='TARGET', nama='Target asuhan',
            weight=Decimal('1.00'), score=score,
        )
        return appraisal


class AppraisalTests(LevelThreeBase):
    def test_duplicate_period_for_same_employee_is_rejected(self):
        from django.db import IntegrityError, transaction

        self._appraisal()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PenilaianKinerja.objects.create(
                periode=self.period, employee=self.employee
            )

    def test_finalization_requires_all_items_scored_and_a_reviewer(self):
        appraisal = PenilaianKinerja.objects.create(
            periode=self.period, employee=self.employee
        )
        ButirPenilaian.objects.create(
            appraisal=appraisal, kategori='TARGET', nama='Belum dinilai',
            weight=Decimal('1.00'), score=None,
        )

        with self.assertRaises(ValidationError):
            finalize_appraisal(appraisal, actor=self.user)

    def test_weighted_score_uses_configured_weights(self):
        appraisal = PenilaianKinerja.objects.create(
            periode=self.period, employee=self.employee, reviewer=self.user
        )
        ButirPenilaian.objects.create(
            appraisal=appraisal, kategori='TARGET', nama='A',
            weight=Decimal('3.00'), score=Decimal('4.00'),
        )
        ButirPenilaian.objects.create(
            appraisal=appraisal, kategori='PERILAKU', nama='B',
            weight=Decimal('1.00'), score=Decimal('2.00'),
        )

        self.assertEqual(appraisal.weighted_score, Decimal('3.50'))

    def test_finalized_appraisal_cannot_be_edited(self):
        appraisal = self._appraisal()
        finalize_appraisal(appraisal, actor=self.user)
        appraisal.status = 'DRAFT'

        with self.assertRaises(ValidationError):
            finalize_appraisal(appraisal, actor=self.user)

    def test_acknowledgment_requires_the_employee_account(self):
        appraisal = self._appraisal()
        finalize_appraisal(appraisal, actor=self.user)

        with self.assertRaises(PermissionDenied):
            acknowledge_appraisal(appraisal, actor=self.user)

    def test_employee_can_acknowledge_and_appeal_a_final_appraisal(self):
        owner = get_user_model().objects.create_user(username='appraised-employee')
        self.employee.akun = owner
        self.employee.save(update_fields=['akun', 'updated_at'])
        appraisal = self._appraisal()
        finalize_appraisal(appraisal, actor=self.user)
        appraisal.refresh_from_db()

        acknowledge_appraisal(appraisal, actor=owner)
        file_appeal(appraisal, actor=owner, notes='Skor target tidak sesuai bukti.')
        appraisal.refresh_from_db()

        self.assertIsNotNone(appraisal.acknowledged_at)
        self.assertIn('tidak sesuai', appraisal.appeal_notes)


class TrainingNeedsTests(LevelThreeBase):
    def test_low_final_score_creates_one_proposal_with_provenance(self):
        appraisal = self._appraisal(score=Decimal('2.00'))
        finalize_appraisal(appraisal, actor=self.user)

        created = propose_training_needs(
            unit=self.unit, actor=self.user, period=self.period
        )

        self.assertEqual(len(created), 1)
        need = created[0]
        self.assertEqual(need.rule_version, 'tna-rules-v1')
        self.assertEqual(need.sources.count(), 1)

    def test_high_score_creates_no_automatic_proposal(self):
        appraisal = self._appraisal(score=Decimal('4.00'))
        finalize_appraisal(appraisal, actor=self.user)

        created = propose_training_needs(
            unit=self.unit, actor=self.user, period=self.period
        )

        self.assertEqual(created, [])

    def test_repeated_runs_do_not_duplicate_proposals(self):
        appraisal = self._appraisal(score=Decimal('1.00'))
        finalize_appraisal(appraisal, actor=self.user)

        propose_training_needs(unit=self.unit, actor=self.user, period=self.period)
        second = propose_training_needs(
            unit=self.unit, actor=self.user, period=self.period
        )

        self.assertEqual(second, [])
        self.assertEqual(KebutuhanPelatihan.objects.count(), 1)

    def test_manual_need_requires_hr_approval_before_use(self):
        created = propose_training_needs(
            unit=self.unit, actor=self.user,
            manual_needs=[{
                'employee': self.employee,
                'topik': 'BHD',
                'alasan': 'Temuan MFK',
                'ref': 'MFK-2026-01',
            }],
        )

        self.assertEqual(created[0].status, 'DIUSULKAN')
        approve_training_need(created[0], actor=self.user)
        created[0].refresh_from_db()
        self.assertEqual(created[0].status, 'DISETUJUI')


class TrainingDeliveryTests(LevelThreeBase):
    def setUp(self):
        super().setUp()
        self.program = ProgramDiklat.objects.create(
            nama='BHD', jp=Decimal('8.00'), professional_credits=Decimal('2.00')
        )
        self.session = SesiDiklat.objects.create(
            program=self.program, tanggal=self.today, kapasitas=2
        )

    def test_registration_creates_a_session_bound_short_lived_token(self):
        participant = register_participant(
            self.session, self.employee, actor=self.user
        )

        self.assertTrue(participant.qr_token)
        self.assertGreater(participant.qr_expires_at, timezone.now())

    def test_capacity_limit_is_enforced(self):
        other = Pegawai.objects.create(nama_lengkap='Kedua', kategori='PPA')
        third = Pegawai.objects.create(nama_lengkap='Ketiga', kategori='PPA')
        for employee in (other, third):
            PenempatanPegawai.objects.create(
                pegawai=employee, unit_kerja=self.unit,
                tanggal_mulai=self.today - timedelta(days=5),
                alokasi_fte=Decimal('1.00'),
            )
        register_participant(self.session, self.employee, actor=self.user)
        register_participant(self.session, other, actor=self.user)

        with self.assertRaises(ValidationError):
            register_participant(self.session, third, actor=self.user)

    def test_completion_requires_attendance_and_evaluation(self):
        participant = register_participant(
            self.session, self.employee, actor=self.user
        )

        with self.assertRaises(ValidationError):
            complete_training(
                participant, actor=self.user, score=Decimal('80.00'), passed=True
            )

        record_attendance(participant, actor=self.user, minutes=480)
        complete_training(
            participant, actor=self.user, score=Decimal('80.00'), passed=True
        )
        participant.refresh_from_db()
        self.assertEqual(participant.status, 'LULUS')

    def test_failed_evaluation_does_not_issue_completion(self):
        participant = register_participant(
            self.session, self.employee, actor=self.user
        )
        record_attendance(participant, actor=self.user, minutes=480)

        complete_training(
            participant, actor=self.user, score=Decimal('40.00'), passed=False
        )

        participant.refresh_from_db()
        self.assertEqual(participant.status, 'TIDAK_LULUS')

    def test_manual_attendance_correction_requires_a_reason(self):
        participant = register_participant(
            self.session, self.employee, actor=self.user
        )
        record_attendance(participant, actor=self.user, minutes=480)

        with self.assertRaises(ValidationError):
            record_attendance(participant, actor=self.user, minutes=0)

    def test_jp_and_professional_credits_stay_separate(self):
        self.assertEqual(self.program.jp, Decimal('8.00'))
        self.assertEqual(self.program.professional_credits, Decimal('2.00'))
