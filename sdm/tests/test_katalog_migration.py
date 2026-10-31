from django.apps import apps
from django.test import TestCase

from sdm.management.commands.seed_katalog_rkk import apply_seed
from sdm.models import KatalogTindakan, MasterJenjangProfesi, MasterProfesiPegawai


class ApplySeedAppsParameterTests(TestCase):
    def test_apply_seed_accepts_apps_registry(self):
        created = apply_seed(apps=apps)
        self.assertIsInstance(created, tuple)
        self.assertEqual(len(created), 3)

    def test_migration_seeded_expected_totals(self):
        self.assertGreaterEqual(MasterProfesiPegawai.objects.count(), 23)
        self.assertGreaterEqual(MasterJenjangProfesi.objects.count(), 118)
        self.assertGreaterEqual(KatalogTindakan.objects.count(), 499)

    def test_idempotent_reseed(self):
        created_again = apply_seed(apps=apps)
        self.assertEqual(created_again, (0, 0, 0))
