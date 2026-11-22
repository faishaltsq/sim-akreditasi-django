"""Tests for the Gillies and Douglas nursing-staff calculators.

Both formulas must be dimensionally correct — a required-FTE helper that is
merely "greater than zero" hides a wrong divisor, so these tests pin the
hand-computed value, not just the sign.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from sdm.services.gillies import hitung_douglas, hitung_gillies

BASIS = dict(
    bor=Decimal('0.78'),
    tempat_tidur=20,
    jam_perawatan_per_pasien=Decimal('4'),
    jam_kerja_efektif_per_hari=Decimal('7'),
    hari_kerja_per_tahun=280,
    hari_libur_cuti_per_tahun=85,
)


class GilliesTests(TestCase):
    def test_hand_computed_value(self):
        # 0.78 x 20 x 4 = 62.4 jam asuhan/hari
        # 62.4 / 7 = 8.9142857 perawat per hari
        # faktor koreksi (280 + 85) / 280 = 1.3035714
        # 8.9142857 x 1.3035714 = 11.6204... -> 11.62 FTE
        hasil = hitung_gillies(**BASIS)
        self.assertEqual(hasil['jam_perawatan_harian'], Decimal('62.40'))
        self.assertEqual(hasil['kebutuhan_harian'], Decimal('8.91'))
        self.assertEqual(hasil['kebutuhan_fte'], Decimal('11.62'))
        self.assertEqual(hasil['kebutuhan_dibulatkan'], 12)
        self.assertEqual(hasil['metode'], 'GILLIES')

    def test_empty_bed_makes_zero_not_an_error(self):
        hasil = hitung_gillies(**{**BASIS, 'bor': Decimal('0')})
        self.assertEqual(hasil['kebutuhan_fte'], Decimal('0.00'))
        self.assertEqual(hasil['kebutuhan_dibulatkan'], 0)

    def test_bor_as_percentage_is_rejected(self):
        with self.assertRaises(ValidationError):
            hitung_gillies(**{**BASIS, 'bor': Decimal('78')})

    def test_zero_effective_hours_is_rejected(self):
        with self.assertRaises(ValidationError):
            hitung_gillies(**{**BASIS, 'jam_kerja_efektif_per_hari': Decimal('0')})

    def test_missing_input_is_not_treated_as_zero(self):
        with self.assertRaises(ValidationError):
            hitung_gillies(**{**BASIS, 'jam_perawatan_per_pasien': None})

    def test_working_days_plus_leave_cannot_exceed_year(self):
        with self.assertRaises(ValidationError):
            hitung_gillies(
                **{**BASIS, 'hari_kerja_per_tahun': 300,
                   'hari_libur_cuti_per_tahun': 100}
            )


class DouglasTests(TestCase):
    def test_adds_non_care_percentage_on_top_of_gillies(self):
        gillies = hitung_gillies(**BASIS)
        douglas = hitung_douglas(**BASIS)
        # default 15% administrasi + 5% pendidikan + 10% istirahat = 30%
        self.assertEqual(douglas['persen_non_asuhan'], Decimal('30'))
        self.assertEqual(douglas['faktor_non_asuhan'], Decimal('1.3000'))
        self.assertEqual(douglas['dasar_gillies_fte'], gillies['kebutuhan_fte'])
        self.assertEqual(douglas['kebutuhan_fte'], Decimal('15.11'))
        self.assertEqual(douglas['metode'], 'DOUGLAS')

    def test_zero_allowances_equals_gillies(self):
        gillies = hitung_gillies(**BASIS)
        douglas = hitung_douglas(
            **BASIS, persen_administrasi=0, persen_pendidikan=0, persen_istirahat=0,
        )
        self.assertEqual(douglas['kebutuhan_fte'], gillies['kebutuhan_fte'])

    def test_total_allowance_of_one_hundred_percent_is_rejected(self):
        with self.assertRaises(ValidationError):
            hitung_douglas(
                **BASIS, persen_administrasi=60, persen_pendidikan=20,
                persen_istirahat=20,
            )
