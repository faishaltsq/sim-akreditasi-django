"""Tests for the one-page FTE calculator (Task 3).

The arithmetic must stay identical to calculate_formasi (sdm/models/formasi.py:320);
a divergence here would make the preview lie about the saved plan.
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
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    RencanaFormasi,
    calculate_formasi,
)
from sdm.services.fte_kalkulator import (
    band_gap,
    compute_fte,
    existing_fte_for,
    jke_minutes,
)


class KalkulatorFteArithmeticTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Kalkulator', code='HC-KAL')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Kalkulator', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=timezone.localdate() - timedelta(days=60),
            alokasi_fte=Decimal('0.75'),
        )
        self.plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai=timezone.localdate() - timedelta(days=30),
            periode_selesai=timezone.localdate() + timedelta(days=30),
            effective_minutes_per_employee=Decimal('89940.00'),
            support_allowance_pct=Decimal('15.00'),
        )
        AktivitasBebanKerja.objects.create(
            rencana=self.plan,
            nama='Asuhan',
            volume=Decimal('100.00'),
            standard_minutes=Decimal('10.00'),
        )

    def test_compute_fte_matches_calculate_formasi(self):
        activities = [
            (activity.nama, activity.volume, activity.standard_minutes)
            for activity in self.plan.activities.all()
        ]
        result = compute_fte(
            activities,
            Decimal('89940.00'),
            Decimal('15.00'),
            existing_fte=Decimal('0.75'),
        )
        expected = calculate_formasi(self.plan)
        self.assertEqual(result['required_fte'], expected['required_fte'])
        self.assertEqual(result['gap_fte'], expected['gap_fte'])
        self.assertEqual(result['sufficiency_pct'], expected['sufficiency_pct'])
        self.assertEqual(
            result['required_headcount'], expected['required_headcount']
        )
        self.assertEqual(result['actual_fte'], expected['actual_fte'])

    def test_jke_minutes_matches_referensi_fixture(self):
        """The repo fixture (sdm/tests/test_referensi.py:33-45) uses 20 training
        hours; expressed in the spec's day unit that is 20/7 days."""
        self.assertEqual(
            jke_minutes(250, 12, 5, 16, Decimal('20.00') / Decimal('7.00'),
                        Decimal('7.00')),
            Decimal('89940.00'),
        )

    def test_jke_minutes_converts_training_days_to_hours(self):
        """Five training days at 7 h/day is 35 h: 217 x 7 - 35 = 1484 h."""
        self.assertEqual(
            jke_minutes(250, 12, 5, 16, 5, Decimal('7.00')),
            Decimal('89040.00'),
        )

    def test_band_gap_covers_three_outcomes(self):
        self.assertEqual(band_gap(Decimal('1.00')), 'UNDERSTAFFED')
        self.assertEqual(band_gap(Decimal('0.00')), 'OPTIMAL')
        self.assertEqual(band_gap(Decimal('-1.00')), 'OVERSTAFFED')

    def test_existing_fte_for_sums_active_assignments(self):
        total = existing_fte_for(
            self.unit.pk, 'Perawat', timezone.localdate()
        )
        self.assertEqual(total, Decimal('0.75'))


class KalkulatorFteViewTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Tampilan', code='HC-KTV')
        self.user = get_user_model().objects.create_user('kalkulator')
        UserProfile.objects.create(
            user=self.user, role='ADMIN_RS', unit_kerja=self.unit
        )
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_plan_hc_workforce = True
        config.save(update_fields=['can_plan_hc_workforce', 'updated_at'])
        HcGrant.objects.create(
            user=self.user, capability='can_plan_hc_workforce',
            unit_kerja=self.unit, granted_by=self.user,
        )
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        payload = {
            'unit_kerja': self.unit.pk,
            'profesi': 'Perawat',
            'hari_kerja': '250',
            'cuti_tahunan': '12',
            'hari_sakit_rata2': '5',
            'libur_nasional': '16',
            'pendidikan_pelatihan': '5',
            'jam_kerja_per_hari': '7.00',
            'support_allowance_pct': '15.00',
            'activities': 'Triase | 100.00 | 10.00\nMonitoring | 50.00 | 20.00',
        }
        payload.update(overrides)
        return payload

    def test_post_returns_result_context(self):
        response = self.client.post(reverse('sdm:kalkulator_fte'), self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['result'])
        self.assertEqual(response.context['band'], 'UNDERSTAFFED')
        self.assertEqual(
            response.context['result']['total_minutes'], Decimal('2000.00')
        )

    def test_invalid_activities_line_is_rejected(self):
        response = self.client.post(
            reverse('sdm:kalkulator_fte'),
            self._payload(activities='Baris tanpa pemisah'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['result'])
        self.assertTrue(response.context['form'].errors)

    def test_simpan_creates_draft_plan_with_activities(self):
        response = self.client.post(
            reverse('sdm:kalkulator_fte_simpan'), self._payload()
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RencanaFormasi.objects.count(), 1)
        plan = RencanaFormasi.objects.get()
        self.assertEqual(plan.status, 'DRAFT')
        self.assertEqual(plan.metode, 'ACTIVITY_FTE')
        self.assertEqual(plan.effective_minutes_per_employee, Decimal('89040.00'))
        self.assertTrue(plan.override_alasan)
        self.assertEqual(plan.activities.count(), 2)

    def test_saved_draft_plan_is_absent_from_peta(self):
        self.client.post(reverse('sdm:kalkulator_fte_simpan'), self._payload())
        response = self.client.get(reverse('sdm:formasi_peta'))
        self.assertEqual(response.status_code, 200)
        plans = list(response.context.get('plans', []))
        self.assertFalse(
            any(plan.status == 'APPROVED' for plan in plans)
        )

    def test_export_returns_csv_with_bom_and_summary_rows(self):
        response = self.client.get(
            reverse('sdm:kalkulator_fte_export'), self._payload()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        body = response.content.decode('utf-8')
        self.assertTrue(body.startswith('\ufeff'))
        self.assertIn('required_fte', body)
        self.assertIn('gap_fte', body)
        self.assertIn('UNDERSTAFFED', body)

    def test_export_rejects_invalid_parameters(self):
        response = self.client.get(
            reverse('sdm:kalkulator_fte_export'),
            self._payload(activities='tidak valid'),
        )
        self.assertEqual(response.status_code, 400)
