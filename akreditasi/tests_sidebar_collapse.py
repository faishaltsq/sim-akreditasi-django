"""Tombol collapse sidebar harus tetap tampil saat sidebar dalam mode rail.

Bug yang dikunci: `.sb-collapsed .sidebar-collapse-btn { display: none }`
menyembunyikan satu-satunya kontrol untuk kembali ke mode penuh, sehingga
sidebar yang sudah diciutkan tidak bisa diperluas lagi.
"""
import re

from django.conf import settings
from django.test import SimpleTestCase


class SidebarCollapseButtonTest(SimpleTestCase):
    def _css(self):
        path = settings.BASE_DIR / 'static' / 'css' / 'v3-tokens.css'
        return path.read_text(encoding='utf-8')

    def test_tombol_tidak_disembunyikan_saat_collapsed(self):
        css = self._css()
        # Cari blok aturan yang menyembunyikan tombol collapse saat .sb-collapsed.
        pola = re.compile(
            r'\.sb-collapsed[^{}]*\.sidebar-collapse-btn[^{}]*\{[^}]*display\s*:\s*none',
            re.S)
        self.assertIsNone(
            pola.search(css),
            'tombol collapse disembunyikan saat sidebar collapsed — '
            'pengguna tidak bisa memperluas menu lagi')

    def test_teks_brand_tetap_disembunyikan(self):
        """Rail hanya ikon: teks brand memang harus hilang."""
        css = self._css()
        self.assertRegex(
            css, r'\.sb-collapsed\s+\.sidebar-brand-text\s*\{\s*display\s*:\s*none',
            'teks brand seharusnya disembunyikan pada mode rail')
