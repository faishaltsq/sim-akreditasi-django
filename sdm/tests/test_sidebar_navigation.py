"""The sidebar must expose the Human Capital menu the user can actually open.

The HC module was reachable only by typing `/human-capital/` directly: no entry
existed in the sidebar, so operators could not find it. These tests pin the menu
against the same capability grants that gate the views, so the menu never
advertises a page that would raise PermissionDenied.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant


class HumanCapitalSidebarTests(TestCase):
    def setUp(self):
        cache.clear()
        self.unit = UnitKerja.objects.create(name='Unit Sidebar HC', code='HC-NAV')
        self.user = get_user_model().objects.create_user(
            username='hc-nav-user', password='x'
        )
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)

    def _allow(self, *capabilities):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        for capability in capabilities:
            setattr(config, capability, True)
        config.save()
        for capability in capabilities:
            HcGrant.objects.create(
                user=self.user, capability=capability, unit_kerja=self.unit
            )

    def _sidebar(self):
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode('utf-8')

    def test_menu_is_absent_without_any_hc_grant(self):
        body = self._sidebar()

        self.assertNotIn('Dasbor SDM', body)
        self.assertNotIn('/human-capital/', body)

    def test_dashboard_entry_appears_with_a_view_grant(self):
        self._allow('can_view_hc')
        body = self._sidebar()

        self.assertIn('Human capital', body)
        self.assertIn('Dasbor SDM', body)
        self.assertIn('/human-capital/', body)

    def test_employee_directory_only_appears_with_its_capability(self):
        self._allow('can_view_hc')
        body = self._sidebar()
        self.assertIn('Direktori pegawai', body)

        # A grant that does not cover the directory must not advertise it.
        HcGrant.objects.filter(user=self.user, capability='can_view_hc').delete()
        self._allow('can_manage_hc_training')
        body = self._sidebar()
        self.assertNotIn('Direktori pegawai', body)
        self.assertIn('Diklat &amp; sertifikasi', body)

    def test_every_menu_entry_resolves_to_a_live_route(self):
        from django.urls import reverse

        self._allow(
            'can_view_hc',
            'can_plan_hc_workforce',
            'can_manage_hc_recruitment',
            'can_review_hc_credentials',
            'can_manage_hc_orientation',
            'can_manage_hc_appraisals',
            'can_manage_hc_training',
            'hc_health_write',
            'can_view_hc_analytics',
        )
        body = self._sidebar()

        # No NoReverseMatch leaked into the render, and every target is present.
        for name in (
            'sdm:dashboard',
            'sdm:pegawai_list',
            'sdm:formasi_list',
            'sdm:rekrutmen_list',
            'sdm:kredensial_list',
            'sdm:orientasi_list',
            'sdm:kinerja_list',
            'sdm:diklat_list',
            'sdm:k3_list',
            'sdm:analitik_dashboard',
        ):
            self.assertIn(reverse(name), body)
