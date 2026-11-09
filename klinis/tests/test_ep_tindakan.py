from django.core.management import call_command
from django.test import TestCase

from klinis.models import AturanEpTindakan
from klinis.services.ep_tindakan import primary_for, resolve_for


class EpTindakanRuleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_katalog_klinis', verbosity=0)

    def test_infus_maps_to_pap3_with_skp1_secondary(self):
        subs = [r.sub_standard for r in resolve_for('ICD9', '99.18')]
        self.assertEqual(subs[0], 'PAP 3')
        self.assertIn('SKP 1', subs)

    def test_injection_maps_to_skp3(self):
        self.assertEqual(primary_for('ICD9', '99.29').sub_standard, 'SKP 3')

    def test_unknown_code_returns_empty_list(self):
        self.assertEqual(resolve_for('ICD9', '87.03'), [])

    def test_unknown_sub_standard_is_dropped(self):
        AturanEpTindakan.objects.create(
            jenis='ICD9', kode='88.76', sub_standard='KPR 3', label='tidak ada', urutan=1,
        )
        self.assertEqual(resolve_for('ICD9', '88.76'), [])

    def test_siki_rule_resolves(self):
        self.assertEqual(primary_for('SIKI', 'I.08238').sub_standard, 'PP 2')

    def test_every_seeded_rule_points_to_real_catalog_row(self):
        from akreditasi.models import StandardItem
        missing = (
            set(AturanEpTindakan.objects.values_list('sub_standard', flat=True))
            - set(StandardItem.objects.values_list('sub_standard', flat=True))
        )
        self.assertFalse(missing, f'Aturan EP menunjuk sub_standard tidak ada: {missing}')

    def test_seed_is_idempotent(self):
        before = AturanEpTindakan.objects.count()
        call_command('seed_katalog_klinis', verbosity=0)
        self.assertEqual(AturanEpTindakan.objects.count(), before)
