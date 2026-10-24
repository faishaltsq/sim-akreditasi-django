"""Test builder tautan modul operasional (murni, tanpa query DB)."""
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase
from django.urls import reverse


class ModuleActionsTest(SimpleTestCase):
    def setUp(self):
        self.unit = SimpleNamespace(pk=71, code='POLI-PD')

    def actions(self, portal, **kwargs):
        from akreditasi.kontrol_navigation import module_actions
        return module_actions(portal, unit=self.unit, year=2026, **kwargs)

    def test_risk_preserves_resolved_unit(self):
        action = self.actions('risiko')[0]
        self.assertEqual(urlsplit(action['href']).path,
                         reverse('akreditasi:risiko_daftar'))
        self.assertEqual(parse_qs(urlsplit(action['href']).query), {'unit': ['71']})

    def test_monev_preserves_year_and_unit(self):
        action = next(a for a in self.actions('risiko') if a['key'] == 'monev')
        self.assertEqual(parse_qs(urlsplit(action['href']).query),
                         {'unit': ['71'], 'tahun': ['2026']})

    def test_rekap_requires_manager(self):
        self.assertNotIn('rekap', [a['key'] for a in self.actions('dokumen')])
        self.assertIn('rekap', [a['key'] for a in
                              self.actions('dokumen', is_manager=True)])

    def test_no_fake_unit_filter_on_documents(self):
        self.assertEqual(self.actions('dokumen')[0]['href'],
                         reverse('akreditasi:dokumen_hub'))

    def test_laporan_actions_add_no_query_the_target_ignores(self):
        """``laporan_mutu_daftar`` tidak membaca request.GET sama sekali.

        Tautan yang mengiklankan ``?tahun=`` adalah filter palsu; target juga
        tidak mendukung ``unit``, jadi href harus persis rute tanpa query.
        """
        for portal, kwargs in (('risiko', {}), ('dokumen', {})):
            with self.subTest(portal=portal):
                laporan = [a for a in self.actions(portal, **kwargs)
                           if a['key'] == 'laporan']
                self.assertEqual(len(laporan), 1)
                self.assertEqual(laporan[0]['href'],
                                 reverse('akreditasi:laporan_mutu_daftar'))
                self.assertEqual(urlsplit(laporan[0]['href']).query, '')

    def test_no_unit_means_no_actions(self):
        from akreditasi.kontrol_navigation import module_actions
        self.assertEqual(module_actions('risiko', unit=None, year=2026), [])

    def test_unknown_portal_has_no_actions(self):
        self.assertEqual(self.actions('unknown'), [])

    def test_outpatient_uses_canonical_choice_label(self):
        actions = self.actions('emr', allowed_patient_modules={'rajal'})
        self.assertEqual(len(actions), 1)
        self.assertEqual(urlsplit(actions[0]['href']).path,
                         reverse('pasien:rajal_dashboard'))
        self.assertEqual(parse_qs(urlsplit(actions[0]['href']).query),
                         {'poli': ['Poli Penyakit Dalam (Interna)']})

    def test_igd_requires_igd_module(self):
        self.unit.code = 'IGD'
        self.assertEqual(self.actions('emr', allowed_patient_modules={'rajal'}), [])
        actions = self.actions('emr', allowed_patient_modules={'igd'})
        self.assertEqual(actions[0]['href'], reverse('pasien:igd_dashboard'))

    def test_beds_require_ownership_and_ranap_permission(self):
        self.unit.code = 'BANGSAL-DEWASA'
        self.assertEqual(self.actions('emr', allowed_patient_modules={'ranap'},
                                      layanan={'owns_beds': False}), [])
        actions = self.actions('emr', allowed_patient_modules={'ranap'},
                               layanan={'owns_beds': True})
        self.assertEqual(actions[0]['href'], reverse('pasien:bed_management'))
        self.assertEqual(actions[0]['scope'], 'Seluruh RS')

    def test_unmapped_unit_has_no_generic_patient_shortcuts(self):
        self.unit.code = 'KOMITE-MUTU'
        self.assertEqual(self.actions('emr', allowed_patient_modules={'rajal', 'igd', 'ranap'},
                                      layanan={'owns_beds': False}), [])

    def test_outpatient_without_permission_has_no_action(self):
        self.assertEqual(self.actions('emr', allowed_patient_modules=set()), [])


class PortalNavigationTest(SimpleTestCase):
    PORTALS = (
        {'key': 'risiko', 'url_name': 'akreditasi:kontrol_risiko'},
        {'key': 'emr', 'url_name': 'akreditasi:kontrol_emr'},
        {'key': 'dokumen', 'url_name': 'akreditasi:kontrol_dokumen'},
        {'key': 'human_capital', 'url_name': 'sdm:dashboard'},
    )

    def nav(self, **kwargs):
        from akreditasi.kontrol_navigation import portal_navigation
        return portal_navigation(
            self.PORTALS, unit=SimpleNamespace(pk=71),
            active_portal=kwargs.pop('active_portal', 'risiko'),
            can_view_hc=kwargs.pop('can_view_hc', False),
        )

    def test_hub_entry_first_and_carries_resolved_unit(self):
        first = self.nav()[0]
        self.assertEqual(first['key'], 'hub')
        self.assertEqual(first['href'],
                         reverse('akreditasi:kontrol_hub') + '?unit=71')
        self.assertFalse(first['active'])

    def test_active_portal_flagged_once(self):
        items = self.nav(active_portal='emr')
        self.assertEqual([i['key'] for i in items if i['active']], ['emr'])

    def test_human_capital_hidden_without_permission(self):
        self.assertNotIn('human_capital', [i['key'] for i in self.nav()])

    def test_human_capital_has_no_unit_query(self):
        items = self.nav(can_view_hc=True)
        hc = next(i for i in items if i['key'] == 'human_capital')
        self.assertEqual(hc['href'], reverse('sdm:dashboard'))

    def test_no_unit_emits_no_malformed_query(self):
        from akreditasi.kontrol_navigation import portal_navigation
        items = portal_navigation(self.PORTALS, unit=None,
                                  active_portal='hub', can_view_hc=True)
        for item in items:
            self.assertNotIn('None', item['href'])
            self.assertNotIn('?', item['href'])
