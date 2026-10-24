"""Track C1: Katalog sumber — validasi berkas sumber, hash, halaman, inventaris direview."""

from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.core.exceptions import ValidationError

from akreditasi.catalogue_services import validate_catalogue_source

REAL_FILE = Path('fixtures/standar_akreditasi_2024.json')


def _make_page(text):
    return type('P', (), {'extract_text': lambda self: text})()


class ValidateCatalogueSourceTests(SimpleTestCase):
    """Sumber yang tidak ada / hash tidak cocok harus gagal sebelum menyentuh baris."""

    def test_missing_source_raises(self):
        with self.assertRaises(ValidationError):
            validate_catalogue_source(
                path='fixtures/catalogue_2024/nonexistent.pdf',
                manifest={'sha256': 'abc', 'pages': 1},
            )

    def test_hash_mismatch_raises(self):
        with self.assertRaises(ValidationError):
            validate_catalogue_source(
                path=str(REAL_FILE),
                manifest={'sha256': '0' * 64, 'pages': 1},
            )


class ValidateCatalogueSourceFullTests(TestCase):
    """Validasi lengkap dengan PDF tiruan melalui pypdf.PdfReader di-mock."""

    @patch('pypdf.PdfReader')
    def test_valid_source_returns_ok(self, mock_reader_cls):
        mock_reader_cls.return_value = type(
            'R', (), {'pages': [_make_page(
                'Elemen Penilaian TKRS 1\n'
                'a) Representasi pemilih/Dewan Pengawas dipilih oleh pemilik. '
                'R Penetapan oleh pemilik.\n'
            ), _make_page('')]}
        )
        manifest = {
            'sha256': '',
            'pages': 2,
            'document_type': 'STANDARD_DECREE',
            'decree_number': 'HK.01.07/MENKES/1596/2024',
            'instrument_type': 'Standar Akreditasi RS',
            'expected_inventory': [{'code': 'TKRS 1', 'ep_count': 1}],
        }
        result = validate_catalogue_source(path=str(REAL_FILE), manifest=manifest)
        self.assertTrue(result['ok'])
        self.assertEqual(result['pages'], 2)
        self.assertEqual(result['document_type'], 'STANDARD_DECREE')
        self.assertEqual(result['extracted_count'], 1)
        self.assertEqual(result['unique_ep_count'], 1)

    @patch('pypdf.PdfReader')
    def test_pages_mismatch_raises(self, mock_reader_cls):
        mock_reader_cls.return_value = type(
            'R', (), {'pages': [_make_page(''), _make_page('')]}
        )
        manifest = {'sha256': '', 'pages': 5}
        with self.assertRaises(ValidationError):
            validate_catalogue_source(path=str(REAL_FILE), manifest=manifest)

    @patch('pypdf.PdfReader')
    def test_duplicate_ep_flagged_as_anomaly(self, mock_reader_cls):
        text = (
            'Elemen Penilaian TKRS 1\n'
            'a) Item pertama.\n'
            'Elemen Penilaian TKRS 1\n'
            'b) Item kedua duplikat kode.\n'
        )
        mock_reader_cls.return_value = type('R', (), {'pages': [_make_page(text)]})
        manifest = {'sha256': '', 'pages': 1, 'expected_inventory': []}
        result = validate_catalogue_source(path=str(REAL_FILE), manifest=manifest)
        self.assertFalse(result['ok'])
        self.assertTrue(
            any('tidak terdaftar' in a for a in result['anomalies'])
            or any('duplikat' in a for a in result['anomalies'])
        )
