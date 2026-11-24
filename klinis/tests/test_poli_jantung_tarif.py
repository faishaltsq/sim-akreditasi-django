"""F0.8 — fondasi tarif Poliklinik Jantung.

Tiga kontrak yang dikunci:

1. ``KelompokLayanan`` POLI_JANTUNG terikat ke UnitKerja POLI-JANTUNG sehingga
   ``_kelompok_for`` menemukan kelompok untuk kunjungan rawat jalan jantung.
2. ``resolve()`` mengembalikan ``Decimal`` untuk kode yang ada di salinan
   kasus JANTUNG — kelompok saja tidak cukup karena ``resolve()`` membaca
   ``KasusTindakan`` per kelompok.
3. ``TarifPenunjang`` hanya dibuat untuk item yang prosedurnya punya harga
   otoritatif; item lain tetap tanpa baris (bukan Rp 0).
"""
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from akreditasi.models import UnitKerja
from klinis.data.tarif_penunjang import BERLAKU_SEJAK
from klinis.models import (
    ItemPenunjang, KasusTersering, KasusTindakan, KelompokLayanan, TarifPenunjang,
)
from klinis.services.tarif import resolve
from pasien.models import KunjunganPasien

ITEM_EKG = 'penunjang-diagnostik-elektrofisiologi-kardiologi-1'
ITEM_ECHO = 'penunjang-diagnostik-radiologi-pencitraan-ultrasonografi-usg-7'

class PoliJantungTarifSeedTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.get_or_create(
            code='POLI-JANTUNG',
            defaults={'name': 'Poliklinik Jantung', 'level': 4},
        )[0]
        call_command('seed_katalog_klinis', verbosity=0)
        call_command('import_penunjang_catalogue', '--apply', verbosity=0)
        call_command('seed_poli_jantung_tarif', verbosity=0)

    def _kunjungan(self, penjamin):
        return KunjunganPasien(
            jenis_kunjungan='RAJAL', unit_kerja=self.unit, penjamin=penjamin)

    def test_kelompok_terikat_unit_poli_jantung(self):
        kelompok = KelompokLayanan.objects.get(kode='POLI_JANTUNG')
        self.assertEqual(kelompok.unit_kerja_id, self.unit.pk)

    def test_salinan_kasus_dan_tindakan_jantung(self):
        sumber = KasusTersering.objects.filter(kelompok__kode='JANTUNG')
        salinan = KasusTersering.objects.filter(kelompok__kode='POLI_JANTUNG')
        self.assertEqual(salinan.count(), sumber.count())
        self.assertEqual(
            KasusTindakan.objects.filter(kasus__kelompok__kode='POLI_JANTUNG').count(),
            KasusTindakan.objects.filter(kasus__kelompok__kode='JANTUNG').count(),
        )

    def test_resolve_rajal_jantung_mengembalikan_decimal(self):
        for penjamin, diharapkan in (('UMUM', Decimal('150000.00')),
                                     ('BPJS', Decimal('120000.00'))):
            with self.subTest(penjamin=penjamin):
                hasil = resolve(self._kunjungan(penjamin), '89.52')
                self.assertIsInstance(hasil, Decimal)
                self.assertEqual(hasil, diharapkan)

    def test_resolve_none_untuk_kode_di_luar_salinan(self):
        self.assertIsNone(resolve(self._kunjungan('UMUM'), '99.9999'))

    def test_seed_idempoten(self):
        sebelum = (
            KelompokLayanan.objects.filter(kode='POLI_JANTUNG').count(),
            KasusTersering.objects.filter(kelompok__kode='POLI_JANTUNG').count(),
            KasusTindakan.objects.filter(kasus__kelompok__kode='POLI_JANTUNG').count(),
            TarifPenunjang.objects.count(),
        )
        call_command('seed_poli_jantung_tarif', verbosity=0)
        sesudah = (
            KelompokLayanan.objects.filter(kode='POLI_JANTUNG').count(),
            KasusTersering.objects.filter(kelompok__kode='POLI_JANTUNG').count(),
            KasusTindakan.objects.filter(kasus__kelompok__kode='POLI_JANTUNG').count(),
            TarifPenunjang.objects.count(),
        )
        self.assertEqual(sesudah, sebelum)

    def test_tarif_penunjang_hanya_item_bersumber(self):
        baris = TarifPenunjang.objects.select_related('item').order_by('item__kode')
        self.assertEqual(
            [(r.item.kode, r.penjamin, r.nominal) for r in baris],
            [(ITEM_EKG, 'UMUM', Decimal('150000.00')),
             (ITEM_ECHO, 'UMUM', Decimal('600000.00'))],
        )
        for r in baris:
            self.assertEqual(r.valid_from, BERLAKU_SEJAK)
            self.assertIsNone(r.valid_to)

    def test_item_tanpa_padanan_tetap_tanpa_tarif(self):
        lab = ItemPenunjang.objects.filter(jenis_order='LAB').first()
        self.assertIsNotNone(lab)
        self.assertFalse(TarifPenunjang.objects.filter(item=lab).exists())
        self.assertEqual(
            ItemPenunjang.objects.filter(tarif_penunjang__isnull=True).count(),
            92,
        )
