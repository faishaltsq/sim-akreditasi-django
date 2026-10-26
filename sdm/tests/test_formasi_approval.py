"""Tests for F-A5: three-stage formation approval with a budget gate.

The submission path is now:

    DRAFT -> REVIEW_HRD (unit head) -> REVIEW_ANGGARAN (finance)
              -> REVIEW_DIREKSI (director) -> APPROVED

Every transition writes exactly one PeristiwaSDM and refuses when the actor
does not hold the capability for that stage, is not scoped to the plan's unit,
or is the submitter acting alone.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AktivitasBebanKerja,
    AnggaranFormasi,
    HcGrant,
    HasilFormasi,
    PeristiwaSDM,
    RencanaFormasi,
)
from sdm.services.formasi import (
    review_budget,
    review_director,
    review_hrd,
    save_plan,
    submit_for_review,
)


class FormasiApprovalFlowTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Contoh', code='UNIT-C')
        self.head = self._make_user('kepala-unit', {
            'can_plan_hc_workforce': True,
            'can_verify_hc_formasi': True,
            'can_verify_hc_formasi_budget': True,
            'can_approve_hc_formasi': True,
        })
        self.hrd = self._make_user('hrd', {
            'can_verify_hc_formasi': True,
        })
        self.finance = self._make_user('finance', {
            'can_verify_hc_formasi_budget': True,
        })
        self.director = self._make_user('direktur', {
            'can_approve_hc_formasi': True,
        })

        self.plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=self.today,
            periode_selesai=self.today + timedelta(days=30),
            effective_minutes_per_employee=Decimal('1000.00'),
            support_allowance_pct=Decimal('10.00'),
            created_by=self.head,
        )
        AktivitasBebanKerja.objects.create(
            rencana=self.plan, nama='Asuhan', volume=Decimal('100.00'),
            standard_minutes=Decimal('10.00'),
        )

    def _make_user(self, username, caps):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        for cap, val in caps.items():
            setattr(config, cap, val)
        config.save(update_fields=list(caps) + ['updated_at'])
        for cap in caps:
            HcGrant.objects.create(user=user, capability=cap, unit_kerja=self.unit)
        return user

    def test_happy_path_passes_all_four_stages(self):
        submit_for_review(self.plan, user=self.head)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'REVIEW_HRD')

        review_hrd(self.plan, user=self.hrd)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'REVIEW_ANGGARAN')

        review_budget(self.plan, user=self.finance, tahunan=Decimal('100000000'),
                      sumber_anggaran='RKA SDM 2026', plafond=Decimal('200000000'),
                      catatan='Masuk plafon')
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'REVIEW_DIREKSI')

        review_director(self.plan, user=self.director)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'APPROVED')

        self.assertEqual(
            PeristiwaSDM.objects.filter(target_tipe='formasi_plan').count(), 4
        )
        self.assertEqual(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='formasi_approved'
            ).count(), 1
        )
        result = HasilFormasi.objects.get(rencana=self.plan)
        self.assertIsNotNone(result.required_fte)

    def test_submitter_cannot_approve_their_own_plan(self):
        submit_for_review(self.plan, user=self.head)
        review_hrd(self.plan, user=self.hrd)
        review_budget(self.plan, user=self.finance, tahunan=Decimal('100000000'),
                      sumber_anggaran='RKA SDM 2026', plafond=Decimal('200000000'))

        with self.assertRaises(PermissionDenied):
            review_director(self.plan, user=self.head)

    def test_out_of_order_transition_is_refused(self):
        # Skip HRD review.
        with self.assertRaises(ValidationError):
            review_budget(self.plan, user=self.finance, tahunan=Decimal('100'),
                          sumber_anggaran='x', plafond=Decimal('200'))

    def test_actor_outside_unit_is_refused(self):
        other = UnitKerja.objects.create(name='Lain', code='UNIT-L')
        outsider = get_user_model().objects.create_user(username='outsider')
        HcGrant.objects.create(
            user=outsider, capability='can_approve_hc_formasi', unit_kerja=other
        )
        submit_for_review(self.plan, user=self.head)
        review_hrd(self.plan, user=self.hrd)
        review_budget(self.plan, user=self.finance, tahunan=Decimal('1000000'),
                      sumber_anggaran='x', plafond=Decimal('200000000'))

        with self.assertRaises(PermissionDenied):
            review_director(self.plan, user=outsider)

    def test_approved_plan_cannot_be_reapproved(self):
        submit_for_review(self.plan, user=self.head)
        review_hrd(self.plan, user=self.hrd)
        review_budget(self.plan, user=self.finance, tahunan=Decimal('1000000'),
                      sumber_anggaran='x', plafond=Decimal('200000000'))
        review_director(self.plan, user=self.director)

        with self.assertRaises(ValidationError):
            review_director(self.plan, user=self.director)

    def test_budget_deficit_refuses_approval(self):
        submit_for_review(self.plan, user=self.head)
        review_hrd(self.plan, user=self.hrd)
        with self.assertRaises(ValidationError) as ctx:
            review_budget(
                self.plan, user=self.finance, tahunan=Decimal('100000000'),
                sumber_anggaran='RKA SDM 2026', plafond=Decimal('50000000'),
            )
        self.assertIn('plafon', str(ctx.exception).lower())

    def test_superseding_an_approved_plan_restarts_all_stages(self):
        submit_for_review(self.plan, user=self.head)
        review_hrd(self.plan, user=self.hrd)
        review_budget(self.plan, user=self.finance, tahunan=Decimal('100000000'),
                      sumber_anggaran='x', plafond=Decimal('200000000'))
        review_director(self.plan, user=self.director)

        new_plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=self.today + timedelta(days=31),
            periode_selesai=self.today + timedelta(days=60),
            effective_minutes_per_employee=Decimal('1000.00'),
            created_by=self.head,
        )
        AktivitasBebanKerja.objects.create(
            rencana=new_plan, nama='Asuhan', volume=Decimal('100.00'),
            standard_minutes=Decimal('10.00'),
        )
        submit_for_review(new_plan, user=self.head)
        review_hrd(new_plan, user=self.hrd)
        review_budget(new_plan, user=self.finance, tahunan=Decimal('1000000'),
                      sumber_anggaran='x', plafond=Decimal('200000000'))
        review_director(new_plan, user=self.director)
        self.assertEqual(
            RencanaFormasi.objects.get(pk=self.plan.pk).status, 'SUPERSEDED'
        )

    def test_creators_keep_a_record_of_who_did_what(self):
        submit_for_review(self.plan, user=self.head)
        review_hrd(self.plan, user=self.hrd)
        review_budget(self.plan, user=self.finance, tahunan=Decimal('100000000'),
                      sumber_anggaran='RKA SDM 2026', plafond=Decimal('200000000'))
        review_director(self.plan, user=self.director)

        events = list(
            PeristiwaSDM.objects.filter(target_tipe='formasi_plan')
            .order_by('created_at')
            .values_list('jenis_peristiwa', 'actor__username')
        )
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0], ('formasi_submitted', 'kepala-unit'))
        self.assertEqual(events[1], ('formasi_reviewed_hrd', 'hrd'))
        self.assertEqual(events[2], ('formasi_reviewed_budget', 'finance'))
        self.assertEqual(events[3], ('formasi_approved', 'direktur'))

    def test_rejection_records_a_reason_and_does_not_destroy_the_result(self):
        submit_for_review(self.plan, user=self.head)
        review_hrd(self.plan, user=self.hrd)
        with self.assertRaises(ValidationError):
            review_budget(
                self.plan, user=self.finance, tahunan=Decimal('100000000'),
                sumber_anggaran='x', plafond=Decimal('50000000'),
            )
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'REVIEW_ANGGARAN')
        self.assertTrue(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='formasi_budget_rejected'
            ).exists()
        )


from django.core.exceptions import PermissionDenied, ValidationError  # noqa: E402
