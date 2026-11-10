from datetime import date
from django.test import TestCase
from pasien.services.ktp_validator import (
    parse_flexible_date,
    decode_nik,
    validate_nik_with_demographics,
)


class KtpValidatorTest(TestCase):
    def test_parse_flexible_date_supports_iso_mdy_dmy_and_2digit_year(self):
        self.assertEqual(parse_flexible_date('1990-05-15'), date(1990, 5, 15))
        self.assertEqual(parse_flexible_date('05/20/90', prefer='MDY'), date(1990, 5, 20))
        self.assertEqual(parse_flexible_date('05/20/1990', prefer='MDY'), date(1990, 5, 20))
        self.assertEqual(parse_flexible_date('12/31/55', prefer='MDY'), date(1955, 12, 31))
        self.assertEqual(parse_flexible_date('01/05/12', prefer='MDY'), date(2012, 1, 5))
        # Unambiguous DMY when day > 12 even if prefer MDY
        self.assertEqual(parse_flexible_date('25/09/1988', prefer='MDY'), date(1988, 9, 25))
        # Explicit DMY for KTP OCR (05-08-1990 = 5 Agustus 1990)
        self.assertEqual(parse_flexible_date('05-08-1990', prefer='DMY'), date(1990, 8, 5))
        self.assertIsNone(parse_flexible_date(''))
        self.assertIsNone(parse_flexible_date('99/99/9999'))

    def test_decode_nik_male_and_female_offset(self):
        # Male born 15-05-1990 in Jawa Barat (32)
        res_l = decode_nik('3273011505900001')
        self.assertTrue(res_l['valid'])
        self.assertEqual(res_l['jenis_kelamin'], 'L')
        self.assertEqual(res_l['tanggal_lahir'], date(1990, 5, 15))
        self.assertEqual(res_l['nama_provinsi'], 'Jawa Barat')

        # Female born 25-09-1988 in DKI Jakarta (31) -> day 25+40 = 65
        res_p = decode_nik('3171026509880003')
        self.assertTrue(res_p['valid'])
        self.assertEqual(res_p['jenis_kelamin'], 'P')
        self.assertEqual(res_p['tanggal_lahir'], date(1988, 9, 25))
        self.assertEqual(res_p['nama_provinsi'], 'DKI Jakarta')

    def test_decode_nik_rejects_invalid_length_or_date(self):
        self.assertFalse(decode_nik('12345')['valid'])
        self.assertFalse(decode_nik('3273019999900001')['valid'])

    def test_validate_nik_with_demographics_flags_mismatches(self):
        # Female NIK compared against Male input
        check = validate_nik_with_demographics('3171026509880003', jenis_kelamin='L', tanggal_lahir='09/25/88')
        self.assertTrue(check['valid'])
        self.assertEqual(len(check['warnings']), 1)
        self.assertIn('Perempuan', check['warnings'][0])

        # Matching demographics -> zero warnings
        check_ok = validate_nik_with_demographics('3171026509880003', jenis_kelamin='P', tanggal_lahir='09/25/1988')
        self.assertTrue(check_ok['valid'])
        self.assertEqual(check_ok['warnings'], [])
