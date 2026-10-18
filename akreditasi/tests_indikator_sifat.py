"""Tests for tipe_pengukuran + faktor_pengali arithmetic and the polarity filter."""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User

from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu


class TipePengukuranTestCase(TestCase):
    """The arithmetic fix: per-mille and mean indicators get their real factor."""

    def setUp(self):
        self.unit = UnitKerja.objects.create(
            name='ICU Sifat', code='ICU-SIFAT', level=3
        )
        self.persen = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan EWS', kode_indikator='SIFAT-PSN',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=90.0,
            satuan='%', arah_target='MIN', tipe_pengukuran='persen',
            faktor_pengali=100,
        )
        self.permil = IndikatorMutu.objects.create(
            nama_indikator='Angka Kejadian VAP', kode_indikator='SIFAT-PML',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=2.5,
            satuan='‰', arah_target='MAX', tipe_pengukuran='rate_absolut',
            faktor_pengali=1000,
        )
        self.rerata = IndikatorMutu.objects.create(
            nama_indikator='Rerata Jam Pelatihan', kode_indikator='SIFAT-JAM',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='EFISIEN',
            numerator='n', denominator='d', target_nilai=20.0,
            satuan='Jam', arah_target='MIN', tipe_pengukuran='rate_absolut',
            faktor_pengali=1,
        )

    def _catatan(self, model, num, den):
        from akreditasi.risiko_models import CatatanIndikator
        return CatatanIndikator.objects.create(
            indikator=model, bulan=1, tahun=2026,
            nilai_numerator=num, nilai_denominator=den,
        )

    def test_persen_still_times_hundred(self):
        c = self._catatan(self.persen, 80, 100)
        self.assertEqual(c.nilai_capaian, Decimal('80'))

    def test_permil_times_thousand(self):
        c = self._catatan(self.permil, 5, 1000)
        self.assertEqual(c.nilai_capaian, Decimal('5.0'))

    def test_permil_outbreak_above_target_is_not_tercapai(self):
        c = self._catatan(self.permil, 50, 1000)
        self.assertEqual(c.nilai_capaian, Decimal('50'))
        self.assertFalse(c.tercapai)

    def test_rerata_factor_one(self):
        c = self._catatan(self.rerata, 340, 17)
        self.assertEqual(c.nilai_capaian, Decimal('20'))

    def test_zero_denominator_returns_zero(self):
        c = self._catatan(self.permil, 5, 0)
        self.assertEqual(c.nilai_capaian, Decimal('0'))

    def test_wrong_factor_on_persen_row_does_not_change_arithmetic(self):
        self.persen.faktor_pengali = 1000
        self.persen.save()
        c = self._catatan(self.persen, 80, 100)
        self.assertEqual(c.nilai_capaian, Decimal('80'))
        self.persen.faktor_pengali = 100
        self.persen.save()

    def test_default_tipe_is_persen(self):
        ind = IndikatorMutu.objects.create(
            nama_indikator='Baru', kode_indikator='SIFAT-BRU',
            jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=10.0,
        )
        self.assertEqual(ind.tipe_pengukuran, 'persen')
        self.assertEqual(ind.faktor_pengali, 100)
