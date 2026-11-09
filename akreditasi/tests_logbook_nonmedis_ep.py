"""Test helper autolink Fokus EP untuk Logbook Non-Medis."""

from django.test import TestCase

from akreditasi.logbook_nonmedis_models import resolve_fokus_ep, ep_kandidat
from akreditasi.models import Category, Framework, StandardItem, UnitKerja


def buat_unit(kode, nama, tipe='BAGIAN', standar_terkait=None):
    return UnitKerja.objects.create(
        code=kode, name=nama, level=2, tipe_unit=tipe,
        standar_terkait=standar_terkait or {},
    )


class FokusEpAutolinkTest(TestCase):

    def setUp(self):
        self.fw = Framework.objects.create(name='STARKES', version='2024', lifecycle='ACTIVE', is_active=True)
        self.cat_tkrs = Category.objects.create(framework=self.fw, code='TKRS', name='TKRS')
        self.cat_mfk = Category.objects.create(framework=self.fw, code='MFK', name='MFK')
        self.ep_tkrs = StandardItem.objects.create(
            category=self.cat_tkrs, sub_standard='TKRS 1', code='TKRS 1 EP a',
            description='Representasi pemilik')
        self.ep_mfk = StandardItem.objects.create(
            category=self.cat_mfk, sub_standard='MFK 4', code='MFK 4 EP a',
            description='Keselamatan fasilitas')

    def test_ep_kandidat_mengikuti_standar_terkait(self):
        unit = buat_unit('PENDAFTARAN', 'Pendaftaran', standar_terkait={'TKRS': ['TKRS 1']})
        kandidat = set(ep_kandidat(unit).values_list('pk', flat=True))
        self.assertIn(self.ep_tkrs.pk, kandidat)
        self.assertNotIn(self.ep_mfk.pk, kandidat)

    def test_ep_kandidat_kosong_tanpa_pemetaan(self):
        unit = buat_unit('KEUANGAN', 'Keuangan')
        self.assertEqual(ep_kandidat(unit).count(), 0)

    def test_resolve_fokus_ep_menemukan_kode(self):
        ep = resolve_fokus_ep('TKRS 1 EP a')
        self.assertEqual(ep.pk, self.ep_tkrs.pk)

    def test_resolve_fokus_ep_tak_dikenal_none(self):
        self.assertIsNone(resolve_fokus_ep('ZZZ 99 EP z'))
