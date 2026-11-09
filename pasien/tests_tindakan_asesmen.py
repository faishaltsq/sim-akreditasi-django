from decimal import Decimal

from django.test import TestCase

from pasien.models import TindakanAsesmen


class TindakanAsesmenModelTest(TestCase):
    def test_tarif_efektif_prefers_override(self):
        t = TindakanAsesmen(tarif_acuan=Decimal('150000'), tarif=Decimal('175000'))
        self.assertEqual(t.tarif_efektif, Decimal('175000'))

    def test_tarif_efektif_falls_back_to_acuan(self):
        t = TindakanAsesmen(tarif_acuan=Decimal('150000'), tarif=None)
        self.assertEqual(t.tarif_efektif, Decimal('150000'))

    def test_tarif_efektif_none_when_unpriced(self):
        self.assertIsNone(TindakanAsesmen().tarif_efektif)

    def test_ep_lengkap_without_ep(self):
        self.assertTrue(TindakanAsesmen(ep_status='BELUM').ep_lengkap)

    def test_ep_lengkap_false_when_belum(self):
        t = TindakanAsesmen(standard_item_id=1, ep_status='BELUM')
        self.assertFalse(t.ep_lengkap)

    def test_ep_lengkap_true_when_terpenuhi_or_na(self):
        self.assertTrue(TindakanAsesmen(standard_item_id=1, ep_status='TERPENUHI').ep_lengkap)
        self.assertTrue(TindakanAsesmen(standard_item_id=1, ep_status='NA').ep_lengkap)
