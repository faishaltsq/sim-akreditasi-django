from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AktivitasOrientasi,
    HcGrant,
    Lamaran,
    Lowongan,
    Pegawai,
    PenempatanPegawai,
    PengajuanKredensial,
    ProgramOrientasi,
)


class LevelRouteAccessTests(TestCase):
    """Every Level 2–5 route must be reachable for a granted user and denied otherwise."""

    LEVEL_ROUTES = (
        'sdm:rekrutmen_list',
        'sdm:kredensial_list',
        'sdm:orientasi_list',
        'sdm:kinerja_list',
        'sdm:diklat_list',
        'sdm:k3_list',
        'sdm:analitik_dashboard',
    )

    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Rute', code='HC-ROUTE2')
        self.user = self._user('level-route-user')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        for field in (
            'can_view_hc', 'can_manage_hc_recruitment', 'can_review_hc_credentials',
            'can_manage_hc_orientation', 'can_manage_hc_appraisals',
            'can_manage_hc_training', 'can_view_hc_analytics', 'can_export_hc',
            'can_plan_hc_workforce',
        ):
            setattr(config, field, True)
        config.save()
        for capability in (
            'can_view_hc', 'can_manage_hc_recruitment', 'can_review_hc_credentials',
            'can_manage_hc_orientation', 'can_manage_hc_appraisals',
            'can_manage_hc_training', 'can_view_hc_analytics', 'can_export_hc',
            'can_plan_hc_workforce', 'hc_health_write',
        ):
            HcGrant.objects.create(
                user=self.user, capability=capability, unit_kerja=self.unit
            )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user

    def test_all_level_routes_render_for_a_granted_user(self):
        self.client.force_login(self.user)

        for name in self.LEVEL_ROUTES:
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200, name)

    def test_level_routes_are_denied_without_grants(self):
        outsider = get_user_model().objects.create_user(username='level-outsider')
        UserProfile.objects.create(user=outsider, role='ADMIN_RS')
        self.client.force_login(outsider)

        for name in self.LEVEL_ROUTES:
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 403, name)

    def test_analitik_export_produces_a_workbook(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('sdm:analitik_export'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response['Content-Type'].startswith(
                'application/vnd.openxmlformats-officedocument'
            )
        )
        self.assertTrue(response.content.startswith(b'PK'))

    def test_navigation_only_lists_permitted_entries(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('sdm:dashboard'))

        for label in (
            'Direktori', 'Formasi', 'Rekrutmen', 'Kredensial', 'Orientasi',
            'Kinerja', 'Diklat', 'K3', 'Analitik',
        ):
            self.assertContains(response, label)

    def test_navigation_hides_unpermitted_entries(self):
        limited = self._user('limited-viewer')
        HcGrant.objects.create(
            user=limited, capability='can_view_hc', unit_kerja=self.unit
        )
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        self.client.force_login(limited)

        response = self.client.get(reverse('sdm:dashboard'))

        self.assertContains(response, 'Direktori')
        self.assertNotContains(response, 'Rekrutmen</a>')
        self.assertNotContains(response, 'Analitik</a>')
