"""F0.6 — flag rilis POLI-JANTUNG terbaca terpisah dari flag IGD.

ADR-8 menetapkan ``POLI_JANTUNG_WORKFLOW_ENABLED`` sebagai flag tersendiri
(default ``false``) supaya menyalakan modul poliklinik jantung tidak ikut
menyalakan — atau mematikan — alur IGD. Modul ini menguji jalur parsing yang
sebenarnya: modul ``config.settings`` diimpor ulang di subprocess dengan
variabel lingkungan yang dikendalikan, lalu kedua nilai dibandingkan untuk
empat kombinasi. ``.env`` tidak bisa menimpa nilai itu karena
``_load_local_env`` melewati kunci yang sudah ada di ``os.environ``.
"""
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = Path(settings.BASE_DIR)

_READ_FLAGS = (
    'import config.settings as s; '
    'print(s.POLI_JANTUNG_WORKFLOW_ENABLED, s.IGD_WORKFLOW_ENABLED)'
)

def baca_flag(poli, igd):
    """Impor config.settings di subprocess dengan env terkendali."""
    env = os.environ.copy()
    env['POLI_JANTUNG_WORKFLOW_ENABLED'] = poli
    env['IGD_WORKFLOW_ENABLED'] = igd
    hasil = subprocess.run(
        [sys.executable, '-c', _READ_FLAGS],
        cwd=str(BASE_DIR), env=env, capture_output=True, text=True,
    )
    if hasil.returncode != 0:
        raise AssertionError(f'Impor config.settings gagal: {hasil.stderr}')
    return hasil.stdout.strip()

class PoliJantungFlagTest(SimpleTestCase):
    """Empat kombinasi flag harus terbaca apa adanya, tanpa saling menimpa."""

    KOMBINASI = [
        ('true', 'true', 'True True'),
        ('true', 'false', 'True False'),
        ('false', 'true', 'False True'),
        ('false', 'false', 'False False'),
    ]

    def test_empat_kombinasi_terbaca_independen(self):
        for poli, igd, diharapkan in self.KOMBINASI:
            with self.subTest(poli=poli, igd=igd):
                self.assertEqual(baca_flag(poli, igd), diharapkan)

    def test_nilai_kosong_berarti_mati(self):
        """Tanpa nilai yang menyalakan, kedua flag mati — default rilis."""
        self.assertEqual(baca_flag('', ''), 'False False')

    def test_variasi_nilai_benar_dikenali(self):
        """Pola yang sama dengan flag IGD: 'true' dan '1' menyalakan."""
        self.assertEqual(baca_flag('1', '0'), 'True False')
