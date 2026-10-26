"""Tests for F-A3: gap analysis with risk coding.

The risk colour must be reproducible: the thresholds used at approval time are
stored on the immutable result, so a report printed today shows the same colour
after the hospital revises its thresholds next year.

A plan with no approved result is `Belum dapat dihitung` — never green. Missing
configuration is `Belum dikonfigurasi` — never a guessed default.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AktivitasBebanKerja,
    HasilFormasi,
    HcGrant,
    RencanaFormasi,
    StandarKetenagaan,
)
from sdm.services.formasi import review_budget, review_director, review_hrd, save_plan, submit_for_review
from sdm.services.risiko import classify_risiko, resolve_ambang_risiko


class ClassifyRisikoTests(TestCase):
    def test_surplus_when_actual_exceeds_requirement(self):
        self.assertEqual(
            classify_risiko(Decimal('120.00'), ambang_marginal=Decimal('95.00'),
                            ambang_kritis=Decimal('80.00')),
            'SURPLUS',
        )

    def test_ideal_at_exactly_one_hundred(self):
        self.assertEqual(
            classify_risiko(Decimal('100.00'), ambang_marginal=Decimal('95.00'),
                            ambang_kritis=Decimal('80.00')),
            'IDEAL',
        )

    def test_ideal_at_the_marginal_boundary(self):
        self.assertEqual(
            classify_risiko(Decimal('95.00'), ambang_marginal=Decimal('95.00'),
                            ambang_kritis=Decimal('80.00')),
            'IDEAL',
        )

    def test_marginal_just_below_the_ideal_band(self):
        self.assertEqual(
            classify_risiko(Decimal('94.99'), ambang_marginal=Decimal('95.00'),
                            ambang_kritis=Decimal('80.00')),
            'MARGINAL',
        )

    def test_marginal_at_the_critical_boundary(self):
        """Exactly at the critical threshold is still marginal, not critical.

        `DEFISIT_KRITIS` means *below* the critical threshold; a unit sitting
        precisely on it has not crossed the line.
        """
        self.assertEqual(
            classify_risiko(Decimal('80.00'), ambang_marginal=Decimal('95.00'),
                            ambang_kritis=Decimal('80.00')),
            'MARGINAL',
        )

    def test_critical_just_below_the_boundary(self):
        self.assertEqual(
            classify_risiko(Decimal('79.99'), ambang_marginal=Decimal('95.00'),
                            ambang_kritis=Decimal('80.00')),
            'DEFISIT_KRITIS',
        )

    def test_zero_sufficiency_is_critical_not_ideal(self):
        self.assertEqual(
            classify_risiko(Decimal('0.00'), ambang_marginal=Decimal('95.00'),
                            ambang_kritis=Decimal('80.00')),
            'DEFISIT_KRITIS',
        )

    def test_missing_threshold_is_never_guessed(self):
        self.assertEqual(
            classify_risiko(Decimal('90.00'), ambang_marginal=None,
                            ambang_kritis=None),
            'BELUM_DIKONFIGURASI',
        )

    def test_missing_sufficiency_is_never_guessed(self):
        self.assertEqual(
            classify_risiko(None, ambang_marginal=Decimal('95.00'),
                            ambang_kritis=Decimal('80.00')),
            'BELUM_DIKONFIGURASI',
        )


class ResolveAmbangTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Rawat Inap', code='RI-AMB')

    def _ambang(self, nama, nilai, **kw):
        return StandarKetenagaan.objects.create(
            unit_kerja=kw.get('unit_kerja'),
            profesi=kw.get('profesi', 'Perawat'),
            jenis='AMBANG_RISIKO',
            nama=nama,
            nilai=Decimal(nilai),
            satuan='% kecukupan',
            sumber_regulasi=kw.get(
                'sumber_regulasi', 'Kebijakan Direktur SDM 2026'
            ),
            berlaku_mulai=kw.get('berlaku_mulai', timezone.localdate()),
            is_active=kw.get('is_active', True),
        )

    def test_reads_both_thresholds_for_the_unit_and_profession(self):
        self._ambang('Ambang Defisit Kritis', '80.00')
        self._ambang('Ambang Ketercukupan Marginal', '95.00')
        result = resolve_ambang_risiko(self.unit, 'Perawat')
        self.assertEqual(result, (Decimal('95.00'), Decimal('80.00')))

    def test_returns_none_pair_when_nothing_is_configured(self):
        self.assertIsNone(resolve_ambang_risiko(self.unit, 'Perawat'))

    def test_inactive_threshold_is_ignored(self):
        self._ambang('Ambang Defisit Kritis', '80.00', is_active=False)
        self._ambang('Ambang Ketercukupan Marginal', '95.00', is_active=False)
        self.assertIsNone(resolve_ambang_risiko(self.unit, 'Perawat'))

    def test_hospital_wide_threshold_applies_when_unit_has_none(self):
        self._ambang('Ambang Defisit Kritis', '75.00', unit_kerja=None)
        self._ambang('Ambang Ketercukupan Marginal', '90.00', unit_kerja=None)
        result = resolve_ambang_risiko(self.unit, 'Perawat')
        self.assertEqual(result, (Decimal('90.00'), Decimal('75.00')))

    def test_unit_specific_threshold_wins_over_hospital_wide(self):
        self._ambang('Ambang Defisit Kritis', '75.00', unit_kerja=None)
        self._ambang('Ambang Ketercukupan Marginal', '90.00', unit_kerja=None)
        self._ambang('Ambang Defisit Kritis', '85.00', unit_kerja=self.unit)
        self._ambang('Ambang Ketercukupan Marginal', '97.00', unit_kerja=self.unit)
        result = resolve_ambang_risiko(self.unit, 'Perawat')
        self.assertEqual(result, (Decimal('97.00'), Decimal('85.00')))


class ApprovalStoresRisikoTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Risiko', code='HC-RISK')
        self.creator = self._user('risk-creator')
        self.approver = self._user('risk-approver')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_plan_hc_workforce = True
        config.can_verify_hc_formasi = True
        config.can_verify_hc_formasi_budget = True
        config.can_approve_hc_formasi = True
        config.save(update_fields=['can_plan_hc_workforce', 'can_verify_hc_formasi', 'can_verify_hc_formasi_budget', 'can_approve_hc_formasi', 'updated_at'])
        for user in (self.creator, self.approver):
            HcGrant.objects.create(
                user=user, capability='can_plan_hc_workforce', unit_kerja=self.unit
            )
            HcGrant.objects.create(
                user=user, capability='can_verify_hc_formasi', unit_kerja=self.unit
            )
            HcGrant.objects.create(
                user=user, capability='can_verify_hc_formasi_budget', unit_kerja=self.unit
            )
            HcGrant.objects.create(
                user=user, capability='can_approve_hc_formasi', unit_kerja=self.unit
            )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user

    def _plan(self, volume='100.00'):
        plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=self.today,
            periode_selesai=self.today + timedelta(days=30),
            effective_minutes_per_employee=Decimal('1000.00'),
            override_alasan='studi waktu unit',
            created_by=self.creator,
        )
        AktivitasBebanKerja.objects.create(
            rencana=plan, nama='Asuhan', volume=Decimal(volume),
            standard_minutes=Decimal('10.00'),
        )
        return plan

    def test_approval_records_the_risk_band_and_the_thresholds_used(self):
        StandarKetenagaan.objects.create(
            unit_kerja=None, profesi='Perawat', jenis='AMBANG_RISIKO',
            nama='Ambang Defisit Kritis', nilai=Decimal('80.00'),
            satuan='% kecukupan', sumber_regulasi='SK Direktur 2026',
            berlaku_mulai=self.today,
        )
        StandarKetenagaan.objects.create(
            unit_kerja=None, profesi='Perawat', jenis='AMBANG_RISIKO',
            nama='Ambang Ketercukupan Marginal', nilai=Decimal('95.00'),
            satuan='% kecukupan', sumber_regulasi='SK Direktur 2026',
            berlaku_mulai=self.today,
        )
        plan = self._plan()
        submit_for_review(plan, user=self.creator)
        review_hrd(plan, user=self.approver)
        review_budget(plan, user=self.approver, tahunan=Decimal('1000000'),
                      sumber_anggaran='x', plafond=Decimal('200000000'))
        review_director(plan, user=self.approver)

        result = HasilFormasi.objects.get(rencana=plan)
        # required 1.00 FTE, actual 0.00 -> 0% sufficiency
        self.assertEqual(result.status_risiko, 'DEFISIT_KRITIS')
        self.assertEqual(result.ambang_marginal_pct, Decimal('95.00'))
        self.assertEqual(result.ambang_kritis_pct, Decimal('80.00'))

    def test_approval_without_thresholds_records_belum_dikonfigurasi(self):
        plan = self._plan()
        submit_for_review(plan, user=self.creator)
        review_hrd(plan, user=self.approver)
        review_budget(plan, user=self.approver, tahunan=Decimal('1000000'),
                      sumber_anggaran='x', plafond=Decimal('200000000'))
        review_director(plan, user=self.approver)

        result = HasilFormasi.objects.get(rencana=plan)
        self.assertEqual(result.status_risiko, 'BELUM_DIKONFIGURASI')
        self.assertIsNone(result.ambang_marginal_pct)


class GapMapViewTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='IGD', code='IGD-MAP')
        self.other = UnitKerja.objects.create(name='ICU', code='ICU-MAP')
        self.user = self._user('map-user')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_plan_hc_workforce = True
        config.save(update_fields=['can_plan_hc_workforce', 'updated_at'])
        HcGrant.objects.create(
            user=self.user, capability='can_plan_hc_workforce', unit_kerja=self.unit
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user

    def _approved_plan(self, unit, profesi='Perawat', volume='100.00'):
        plan = RencanaFormasi.objects.create(
            unit_kerja=unit, profesi=profesi,
            periode_mulai=self.today,
            periode_selesai=self.today + timedelta(days=30),
            effective_minutes_per_employee=Decimal('1000.00'),
            override_alasan='studi waktu unit',
        )
        AktivitasBebanKerja.objects.create(
            rencana=plan, nama='Asuhan', volume=Decimal(volume),
            standard_minutes=Decimal('10.00'),
        )
        HasilFormasi.objects.create(
            rencana=plan,
            calculation_version='activity-fte-v1',
            required_fte=Decimal('1.0000'),
            required_headcount=1,
            actual_fte=Decimal('0.5000'),
            gap_fte=Decimal('0.5000'),
            sufficiency_pct=Decimal('50.00'),
            inputs_digest='a' * 64,
            status_risiko='DEFISIT_KRITIS',
            ambang_marginal_pct=Decimal('95.00'),
            ambang_kritis_pct=Decimal('80.00'),
        )
        plan.status = 'APPROVED'
        plan.approved_at = timezone.now()
        plan.save(update_fields=['status', 'approved_at', 'updated_at'])
        return plan

    def test_requires_the_workforce_capability(self):
        self.client.force_login(get_user_model().objects.create_user(username='nobody'))
        response = self.client.get(reverse('sdm:formasi_peta'))
        self.assertEqual(response.status_code, 403)

    def test_renders_only_plans_in_the_users_unit_scope(self):
        self._approved_plan(self.unit, profesi='Perawat')
        self._approved_plan(self.other, profesi='Bidan')
        self.client.force_login(self.user)

        response = self.client.get(reverse('sdm:formasi_peta'))

        self.assertEqual(response.status_code, 200)
        profesi = {row['profesi'] for row in response.context['rows']}
        self.assertEqual(profesi, {'Perawat'})

    def test_plan_without_an_approved_result_is_not_coloured(self):
        RencanaFormasi.objects.create(
            unit_kerja=self.unit, profesi='Draf',
            periode_mulai=self.today,
            periode_selesai=self.today + timedelta(days=30),
            effective_minutes_per_employee=Decimal('1000.00'),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('sdm:formasi_peta'))

        self.assertEqual(response.context['rows'], [])
        self.assertContains(response, 'Belum dapat dihitung')

    def test_only_defisit_filter_keeps_critical_and_marginal_rows(self):
        self._approved_plan(self.unit, profesi='Kritis')
        ideal = self._approved_plan(self.unit, profesi='Ideal')
        ideal.result.status_risiko = 'IDEAL'
        ideal.result.save = None
        HasilFormasi.objects.filter(pk=ideal.result.pk).update(status_risiko='IDEAL')

        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:formasi_peta'), {'hanya_defisit': '1'})

        profesi = {row['profesi'] for row in response.context['rows']}
        self.assertEqual(profesi, {'Kritis'})

    def test_query_count_does_not_grow_with_the_number_of_plans(self):
        """The N+1 guard: doubling the data must not double the queries."""
        self._approved_plan(self.unit, profesi='Perawat')
        self.client.force_login(self.user)
        self.client.get(reverse('sdm:formasi_peta'))
        with self.assertNumQueries(self._baseline_queries()) as first:
            self.client.get(reverse('sdm:formasi_peta'))
        baseline = len(first.captured_queries)

        for profesi in ('Bidan', 'Apoteker', 'Radiografer', 'Analis'):
            self._approved_plan(self.unit, profesi=profesi)

        with self.assertNumQueries(baseline) as second:
            self.client.get(reverse('sdm:formasi_peta'))

        self.assertEqual(len(second.captured_queries), baseline)

    def _baseline_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse('sdm:formasi_peta'))
        return len(ctx.captured_queries)

    def test_totals_sum_only_the_displayed_rows(self):
        self._approved_plan(self.unit, profesi='Perawat')
        self._approved_plan(self.unit, profesi='Bidan')
        self.client.force_login(self.user)

        response = self.client.get(reverse('sdm:formasi_peta'))

        totals = response.context['totals']
        self.assertEqual(totals['jumlah_baris'], 2)
        self.assertEqual(totals['required_fte'], Decimal('2.0000'))
        self.assertEqual(totals['actual_fte'], Decimal('1.0000'))

    def test_deficit_row_offers_a_prefilled_submission_link(self):
        self._approved_plan(self.unit, profesi='Perawat')
        self.client.force_login(self.user)

        response = self.client.get(reverse('sdm:formasi_peta'))

        row = response.context['rows'][0]
        self.assertIn('buat_usulan_url', row)
        self.assertIn('profesi=Perawat', row['buat_usulan_url'])
