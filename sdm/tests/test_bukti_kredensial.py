"""D-4: 13 credential evidence documents mapped to STARKES standards/EP."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.services.bukti_kredensial import DOKUMEN_BUKTI, map_to_catalog


class BuktiKatalogTests(TestCase):
    def test_thirteen_documents_declared(self):
        self.assertEqual(len(DOKUMEN_BUKTI), 13)

    def test_every_entry_has_standards_and_labels(self):
        for entry in DOKUMEN_BUKTI:
            self.assertTrue(entry['kode'], entry)
            self.assertTrue(entry['label'], entry)
            self.assertTrue(entry['standar'], entry)

    def test_codes_are_unique(self):
        codes = [entry['kode'] for entry in DOKUMEN_BUKTI]
        self.assertEqual(len(codes), len(set(codes)))

    def test_known_standards_resolve_to_catalog_items(self):
        rows = map_to_catalog()
        by_code = {row['kode']: row for row in rows}
        psv = by_code['PSV']
        self.assertIn('KPS 5', psv['standar'])
        self.assertTrue(psv['matched'], 'KPS 5 should exist in the catalogue')

    def test_every_declared_standard_resolves(self):
        # KPS 13 was a catalogue gap; it is now seeded, so no row may be red.
        rows = map_to_catalog()
        unmatched = {row['kode']: row['unmatched'] for row in rows if row['unmatched']}
        self.assertEqual(unmatched, {})

    def test_unknown_standard_is_still_reported(self):
        from unittest.mock import patch
        from sdm.services import bukti_kredensial

        fake = [{
            'kode': 'UJI', 'label': 'Uji', 'standar': ['KPS 99'], 'ep': 'EP x',
        }]
        with patch.object(bukti_kredensial, 'DOKUMEN_BUKTI', fake):
            rows = bukti_kredensial.map_to_catalog()
        self.assertEqual(rows[0]['unmatched'], ['KPS 99'])
        self.assertEqual(rows[0]['matched'], [])

    def test_every_row_carries_ep_text(self):
        for row in map_to_catalog():
            self.assertTrue(row['ep'], row['kode'])


class BuktiViewTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Bukti', code='HC-BUKTI')
        self.user = get_user_model().objects.create_user(username='bukti-user')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_review_hc_credentials = True
        config.save(update_fields=[
            'can_view_hc', 'can_review_hc_credentials', 'updated_at',
        ])
        from sdm.models import HcGrant
        HcGrant.objects.create(user=self.user, capability='can_view_hc', unit_kerja=self.unit)
        HcGrant.objects.create(
            user=self.user, capability='can_review_hc_credentials', unit_kerja=self.unit,
        )

    def test_page_renders_thirteen_rows(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:kredensial_bukti_starkes'))
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Dokumen Bukti Kredensial', content)
        from django.utils.html import escape
        for entry in DOKUMEN_BUKTI:
            self.assertIn(escape(entry['label'][:40]), content)

    def test_page_requires_login(self):
        response = self.client.get(reverse('sdm:kredensial_bukti_starkes'))
        self.assertEqual(response.status_code, 302)
