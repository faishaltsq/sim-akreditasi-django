from decimal import Decimal
from django.core.management import call_command
from django.test import TestCase

from klinis.models import (
    KelompokLayanan,
    MasterIcd10,
    MasterIcd9,
    KasusTersering,
    KasusTindakan,
    SdkiDiagnosis,
    SlkiLuaran,
    SikiIntervensi,
    Pemetaan3S,
    AturanEpAsesmen,
)


class SeedKatalogKlinisTest(TestCase):
    def setUp(self):
        call_command('seed_katalog_klinis')

    def test_record_counts(self):
        self.assertEqual(KelompokLayanan.objects.count(), 14)
        self.assertEqual(KasusTersering.objects.count(), 215)
        self.assertEqual(KasusTersering.objects.filter(icd10__isnull=False).count(), 210)
        self.assertEqual(KasusTersering.objects.filter(icd10__isnull=True).count(), 5)
        self.assertGreaterEqual(KasusTindakan.objects.count(), 380)
        self.assertEqual(AturanEpAsesmen.objects.count(), 4)
        self.assertEqual(SdkiDiagnosis.objects.count(), 27)
        self.assertEqual(SlkiLuaran.objects.count(), 20)
        self.assertEqual(SikiIntervensi.objects.count(), 18)
        self.assertEqual(Pemetaan3S.objects.count(), 22)

    def test_idempotency(self):
        # Second run should not change counts
        call_command('seed_katalog_klinis')
        self.assertEqual(KelompokLayanan.objects.count(), 14)
        self.assertEqual(KasusTersering.objects.count(), 215)
        self.assertEqual(KasusTindakan.objects.count(), 397)
        self.assertEqual(AturanEpAsesmen.objects.count(), 4)

    def test_mata_pasca_has_null_tariffs(self):
        mata_pasca_tindakan = KasusTindakan.objects.filter(kasus__kelompok__kode='MATA_PASCA')
        self.assertGreater(mata_pasca_tindakan.count(), 0)
        for t in mata_pasca_tindakan:
            self.assertIsNone(t.tarif_umum)
            self.assertIsNone(t.tarif_bpjs)

    def test_non_null_tariffs_are_positive(self):
        priced_actions = KasusTindakan.objects.exclude(tarif_umum__isnull=True)
        self.assertGreater(priced_actions.count(), 0)
        for t in priced_actions:
            self.assertGreater(t.tarif_umum, Decimal('0'))
            self.assertGreater(t.tarif_bpjs, Decimal('0'))

    def test_truncated_tatalaksana_flagged(self):
        flagged = KasusTersering.objects.filter(perlu_verifikasi=True)
        self.assertGreater(flagged.count(), 0)
        # Check that T4 R15 or T14 R15 is flagged
        t14_last = KasusTersering.objects.get(kelompok__kode='IGD', urutan=15)
        self.assertTrue(t14_last.perlu_verifikasi)

    def test_sdki_nifas_reclassification(self):
        nifas_sdki = KasusTersering.objects.filter(kelompok__kode='NIFAS', icd10__isnull=True)
        self.assertEqual(nifas_sdki.count(), 5)
        codes = set(nifas_sdki.values_list('sdki_kode', flat=True))
        self.assertIn('D.0012', codes)
        self.assertIn('D.0039', codes)
        self.assertIn('D.0056', codes)
        self.assertIn('D.0080', codes)
        self.assertIn('D.0111', codes)

    def test_igd_tariff_ceiling(self):
        for t in KasusTindakan.objects.filter(kasus__kelompok__kode='IGD'):
            self.assertLessEqual(t.tarif_umum or 0, Decimal('15000000'))

    def test_sdki_catalog_superset_of_legacy(self):
        from pasien.views import SDKI_CODES
        codes = set(SdkiDiagnosis.objects.values_list('kode', flat=True))
        missing = {c for c, _ in SDKI_CODES} - codes
        self.assertFalse(missing, f'SDKI codes missing from catalog: {missing}')

    def test_ep_rules_resolve_against_catalog(self):
        from akreditasi.models import StandardItem
        for rule in AturanEpAsesmen.objects.all():
            self.assertTrue(
                StandardItem.objects.filter(sub_standard=rule.sub_standard).exists(),
                f'{rule.sub_standard} not in accreditation catalog'
            )

