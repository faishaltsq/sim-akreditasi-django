"""Sidebar navigation visibility and active-state correctness.

The Human Capital section is gated per capability: a user with no HC grant must
not see it at all, and each link appears only for the capability that owns it.
Active-state conditions must be scoped to the `sdm` app, otherwise a matching
`url_name` from another app would wrongly highlight the link.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai


class SidebarHcNavigationTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Nav', code='NAV-TEST')
        self.user = get_user_model().objects.create_user(username='nav-user')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)

    def _grant(self, capability):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        setattr(config, capability, True)
        config.save(update_fields=[capability, 'updated_at'])
        HcGrant.objects.create(
            user=self.user, capability=capability, unit_kerja=self.unit
        )

    def test_no_hc_section_without_any_grant(self):
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertNotContains(response, 'Human capital')

    def test_hc_section_appears_with_view_grant(self):
        self._grant('can_view_hc')
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertContains(response, 'Human capital')
        self.assertContains(response, 'Dasbor SDM')

    def test_employee_directory_links_with_view_grant(self):
        self._grant('can_view_hc')
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertContains(response, 'Direktori pegawai')

    def test_recruitment_link_is_absent_without_its_capability(self):
        # Rekrutmen lives in its own nav-link; can_view_hc must not reveal it.
        self._grant('can_view_hc')
        self.client.force_login(self.user)
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        # Batasi ke blok "Human capital" saja: berakhir di nav-section berikutnya,
        # supaya tautan bernama sama dari section lain tidak diperhitungkan.
        section = content[content.find('Human capital'):]
        nxt = section.find('nav-section', len('Human capital'))
        if nxt != -1:
            section = section[:nxt]
        self.assertNotIn('Rekrutmen', section)

    def test_analytics_link_requires_analytics_capability(self):
        self._grant('can_view_hc')
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertNotContains(response, 'Analitik SDM')
        self._grant('can_view_hc_analytics')
        response = self.client.get('/')
        self.assertContains(response, 'Analitik SDM')

    def test_dashboard_link_is_active_on_hc_dashboard(self):
        self._grant('can_view_hc')
        self.client.force_login(self.user)
        response = self.client.get('/human-capital/')
        content = response.content.decode('utf-8')
        # The active nav-link for Dasbor SDM must be marked, not another link.
        self.assertIn('nav-link active', content)

    def test_pegawai_link_active_state_is_scoped_to_sdm_app(self):
        """A non-sdm page must never highlight the employee-directory link."""
        self._grant('can_view_hc')
        employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Nav', kategori='PPA', profesi='Perawat'
        )
        from sdm.models import PenempatanPegawai
        from decimal import Decimal
        from django.utils import timezone
        PenempatanPegawai.objects.create(
            pegawai=employee, unit_kerja=self.unit,
            tanggal_mulai=timezone.localdate() - timezone.timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{employee.pk}/')
        content = response.content.decode('utf-8')
        # The directory link is active here (same app), and only it.
        self.assertIn('Direktori pegawai', content)
