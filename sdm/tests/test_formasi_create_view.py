"""Regression test for the production bug where every new RencanaFormasi
submission failed with "Rencana formasi tidak ditemukan."

Root cause: RencanaFormasi.id is a UUIDField(primary_key=True, default=uuid.uuid4),
so plan.pk is always truthy on an unsaved instance. save_plan() used `if plan.pk:`
to detect an existing record, which made every new plan look like a lookup miss.
The canonical new-record marker is plan._state.adding.
"""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, RencanaFormasi


class FormasiCreateViewTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Formasi', code='HC-FRM')
        self.user = get_user_model().objects.create_user('hrd', password='x')
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

    def test_new_plan_is_saved_not_rejected_as_missing(self):
        response = self.client.post(reverse('sdm:formasi_create'), {
            'unit_kerja': self.unit.pk,
            'profesi': 'Perawat',
            'periode_mulai': '2025-01-11',
            'periode_selesai': '2026-02-11',
            'metode': 'ACTIVITY_FTE',
            'effective_minutes_per_employee': '75000.00',
            'override_alasan': 'Acuan JKE tahunan belum disetujui.',
            'support_allowance_pct': '10.00',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RencanaFormasi.objects.count(), 1)
        plan = RencanaFormasi.objects.get()
        self.assertEqual(plan.profesi, 'Perawat')
        self.assertEqual(plan.status, 'DRAFT')
        self.assertFalse(plan._state.adding)

    def test_existing_draft_is_still_updatable(self):
        plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            periode_mulai='2025-01-11',
            periode_selesai='2026-02-11',
            effective_minutes_per_employee=Decimal('75000.00'),
            support_allowance_pct=Decimal('10.00'),
            override_alasan='Acuan JKE tahunan belum disetujui.',
        )
        self.assertFalse(plan._state.adding)
        plan.profesi = 'Bidan'
        plan.save()
        plan.refresh_from_db()
        self.assertEqual(plan.profesi, 'Bidan')
