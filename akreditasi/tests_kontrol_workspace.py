"""Test integrasi konteks workspace Integrated Control.

Menguji kontrak konteks: unit ter-resolve, tab permission-aware, aksi modul
kontekstual, dan tidak ada tautan unit palsu.
"""
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from akreditasi.models import UnitKerja


class ControlWorkspaceTest(TestCase):
    def setUp(self):
        cache.clear()
        self.unit = UnitKerja.objects.create(
            code='POLI-PD', name='Poliklinik Penyakit Dalam',
            level=3, is_active=True,
        )
        self.other = UnitKerja.objects.create(
            code='KTRL-OTHER', name='Other unit', level=3, is_active=True,
        )
        self.user = get_user_model().objects.create_user(username='control-workspace')
        UserProfile.objects.create(
            user=self.user, role='KEPALA_UNIT', unit_kerja=self.unit,
        )
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()

    def test_navigation_uses_resolved_unit_not_untrusted_query(self):
        res = self.client.get(reverse('akreditasi:kontrol_risiko'),
                              {'unit': self.other.pk})
        self.assertEqual(res.status_code, 200)
        for item in res.context['portal_navigation']:
            self.assertEqual(parse_qs(urlsplit(item['href']).query).get('unit'),
                             [str(self.unit.pk)])
        self.assertEqual(
            parse_qs(urlsplit(res.context['module_actions'][0]['href']).query)['unit'],
            [str(self.unit.pk)])

    def test_human_capital_is_not_advertised_without_permission(self):
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        self.assertNotIn('human_capital', [item['key'] for item in res.context['portal_navigation']])
        self.assertFalse(res.context['can_view_hc'])

    def test_emr_links_directly_to_eligible_poli(self):
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        self.assertContains(res, 'Buka poli')
        self.assertContains(res, reverse('pasien:rajal_dashboard'))

    def test_risk_has_one_primary_direct_module_action_above_kpis(self):
        body = self.client.get(reverse('akreditasi:kontrol_risiko')).content.decode()
        self.assertIn('data-module-primary', body)
        self.assertLess(body.index('data-module-primary'), body.index('kontrol-kpis'))

    def test_layanan_page_retains_control_navigation(self):
        res = self.client.get(reverse('akreditasi:kontrol_layanan'))
        self.assertContains(res, 'aria-label="Navigasi Integrated Control"')

    def test_light_workspace_stylesheet_and_main_landmark(self):
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        self.assertContains(res, 'kontrol-workspace.css')
        self.assertContains(res, 'id="kontrol-main"')
        self.assertNotContains(res, 'kontrol-backdrop')

    def test_risk_actions_are_contextual_not_generic(self):
        res = self.client.get(reverse('akreditasi:kontrol_risiko'))
        actions = res.context['module_actions']
        self.assertEqual(actions[0]['key'], 'risiko')
        self.assertEqual(actions[0]['scope'], 'Unit aktif')
        indikator = next(a for a in actions if a['key'] == 'indikator')
        self.assertNotIn('unit=', indikator['href'])
        self.assertIn('tahun=', indikator['href'])

    def test_documents_hide_rekap_for_non_manager(self):
        profile = self.user.profile
        profile.role = 'STAF'
        profile.save(update_fields=['role'])
        cache.clear()
        res = self.client.get(reverse('akreditasi:kontrol_dokumen'))
        keys = [a['key'] for a in res.context['module_actions']]
        self.assertNotIn('rekap', keys)
        self.assertIn('dokumen', keys)

    def test_active_portal_and_meta_come_from_context(self):
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        self.assertEqual(res.context['active_portal'], 'emr')
        self.assertEqual(res.context['portal_meta']['key'], 'emr')
        self.assertEqual(
            res.context['portal_meta']['url_name'], 'akreditasi:kontrol_emr')

    def test_layanan_page_does_not_highlight_emr_tab(self):
        res = self.client.get(reverse('akreditasi:kontrol_layanan'))
        self.assertEqual(res.context['active_portal'], 'layanan')
        active = [i['key'] for i in res.context['portal_navigation'] if i['active']]
        self.assertEqual(active, [])

    def test_hub_has_no_module_toolbar_actions(self):
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        self.assertEqual(res.context['module_actions'], [])
        self.assertEqual(res.context['active_portal'], 'hub')

    def test_hub_risk_card_icon_is_a_real_bootstrap_icon(self):
        """``bi-shield-fail`` tidak ada di Bootstrap Icons 1.11 → kotak kosong."""
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        self.assertContains(res, 'bi bi-shield-check')
        self.assertNotContains(res, 'bi-shield-fail')

    def test_human_capital_tab_present_with_real_grant(self):
        from accounts.models import RolePermissionConfig
        from sdm.models import HcGrant

        config = RolePermissionConfig.get_config_for_role('KEPALA_UNIT')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=self.user, capability='can_view_hc', unit_kerja=self.unit)
        cache.clear()
        res = self.client.get(reverse('akreditasi:kontrol_risiko'))
        self.assertTrue(res.context['can_view_hc'])
        self.assertIn('human_capital',
                      [i['key'] for i in res.context['portal_navigation']])

    def test_expired_grant_does_not_advertise_human_capital(self):
        from datetime import timedelta

        from django.utils import timezone
        from accounts.models import RolePermissionConfig
        from sdm.models import HcGrant

        config = RolePermissionConfig.get_config_for_role('KEPALA_UNIT')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        today = timezone.localdate()
        HcGrant.objects.create(
            user=self.user, capability='can_view_hc', unit_kerja=self.unit,
            valid_from=today - timedelta(days=30),
            valid_until=today - timedelta(days=1))
        cache.clear()
        res = self.client.get(reverse('akreditasi:kontrol_risiko'))
        self.assertFalse(res.context['can_view_hc'])

    def test_hospital_wide_role_keeps_selected_unit(self):
        profile = self.user.profile
        profile.role = 'ADMIN_RS'
        profile.unit_kerja = None
        profile.save(update_fields=['role', 'unit_kerja'])
        cache.clear()
        res = self.client.get(reverse('akreditasi:kontrol_risiko'),
                              {'unit': self.other.pk})
        self.assertEqual(res.context['unit'].pk, self.other.pk)
        self.assertIn('unit=' + str(self.other.pk),
                      res.context['module_actions'][0]['href'])
        for item in res.context['portal_navigation']:
            if item['key'] == 'human_capital':
                continue
            self.assertIn('unit=' + str(self.other.pk), item['href'])

    def test_no_active_unit_emits_no_malformed_links(self):
        profile = self.user.profile
        profile.role = 'ADMIN_RS'
        profile.unit_kerja = None
        profile.save(update_fields=['role', 'unit_kerja'])
        UnitKerja.objects.all().update(is_active=False)
        cache.clear()
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.context['unit'])
        self.assertEqual(res.context['module_actions'], [])
        for item in res.context['portal_navigation']:
            self.assertNotIn('None', item['href'])


class ControlWorkspaceScopeTest(TestCase):
    """Matriks izin/empty-state: pintasan tidak boleh melampaui hak akses."""

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='control-scope')

    def tearDown(self):
        cache.clear()

    def _login(self, unit, role='KEPALA_UNIT'):
        UserProfile.objects.create(user=self.user, role=role, unit_kerja=unit)
        self.client.force_login(self.user)
        cache.clear()

    def test_unit_without_clinical_entitlement_has_no_shortcut(self):
        # Kode unit non-klinis: get_allowed_patient_modules hanya memberi
        # master_pasien/riwayat, jadi tidak ada pintasan klinis.
        unit = UnitKerja.objects.create(
            code='DIREKSI', name='Direksi', level=1, is_active=True)
        self._login(unit, role='STAF')
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        self.assertEqual(res.context['module_actions'], [])
        self.assertContains(res, 'Tidak ada pintasan operasional')

    def test_unmapped_administrative_unit_has_no_clinical_shortcut(self):
        unit = UnitKerja.objects.create(
            code='KOMITE-MUTU', name='Komite Mutu', level=2, is_active=True)
        self._login(unit, role='ADMIN_RS')
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        self.assertEqual(res.context['module_actions'], [])
        self.assertNotContains(res, reverse('pasien:rajal_dashboard'))

    def test_bed_owning_unit_without_ranap_has_no_bed_action(self):
        unit = UnitKerja.objects.create(
            code='BANGSAL-DEWASA', name='Bangsal Dewasa', level=4, is_active=True)
        self._login(unit, role='STAF')
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        keys = [a['key'] for a in res.context['module_actions']]
        self.assertNotIn('beds', keys)

    def test_clinical_primary_link_is_operational_destination(self):
        unit = UnitKerja.objects.create(
            code='POLI-JANTUNG', name='Poliklinik Jantung', level=3, is_active=True)
        self._login(unit, role='ADMIN_RS')
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        primary = res.context['module_actions'][0]
        self.assertEqual(primary['key'], 'rajal')
        self.assertEqual(urlsplit(primary['href']).path,
                         reverse('pasien:rajal_dashboard'))
        self.assertNotEqual(urlsplit(primary['href']).path,
                            reverse('akreditasi:dashboard'))

    def test_exactly_one_aria_current_per_portal_page(self):
        unit = UnitKerja.objects.create(
            code='POLI-JANTUNG', name='Poliklinik Jantung', level=3, is_active=True)
        self._login(unit, role='ADMIN_RS')
        for name in ('kontrol_hub', 'kontrol_risiko', 'kontrol_emr',
                     'kontrol_dokumen'):
            with self.subTest(name=name):
                body = self.client.get(
                    reverse('akreditasi:' + name)).content.decode()
                self.assertEqual(body.count('aria-current="page"'), 1)

    def test_ai_panel_contract_unchanged(self):
        unit = UnitKerja.objects.create(
            code='POLI-JANTUNG', name='Poliklinik Jantung', level=3, is_active=True)
        self._login(unit, role='ADMIN_RS')
        body = self.client.get(reverse('akreditasi:kontrol_risiko')).content.decode()
        self.assertIn('kontrol-ai', body)
        self.assertIn('js-ai-run', body)
        self.assertEqual(
            self.client.get(reverse('akreditasi:kontrol_ringkasan_ai')).status_code,
            405)
        self.assertEqual(
            self.client.post(reverse('akreditasi:kontrol_ringkasan_ai'),
                             {'portal': 'asing'}).status_code, 400)
