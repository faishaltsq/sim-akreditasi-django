"""Regresi: brand tidak boleh menyusut & nav yang men-scroll."""
import re

from django.conf import settings
from django.test import SimpleTestCase


class SidebarShrinkTest(SimpleTestCase):
    def _css(self):
        return (settings.BASE_DIR / 'static' / 'css' / 'v3-tokens.css').read_text(encoding='utf-8')

    def test_brand_dilindungi_dari_flex_shrink(self):
        """.sidebar-desktop adalah flex column setinggi viewport dengan 70+ item
        di dalamnya. Tanpa pelindung, flex-shrink menekan .sidebar-brand sampai
        tingginya 1px (terukur di Chromium) sehingga isinya menimpa ikon menu."""
        css = self._css()
        m = re.search(r'\.sidebar-brand\s*\{([^}]*)\}', css, re.S)
        self.assertIsNotNone(m, 'blok .sidebar-brand tidak ditemukan')
        self.assertRegex(
            m.group(1), r'flex\s*:\s*0\s+0\s+auto',
            '.sidebar-brand harus flex: 0 0 auto agar tidak menyusut')

    def test_nav_menjadi_scroller_bukan_kontainer(self):
        """Scrolling harus di .sidebar-nav; .sidebar-desktop tidak boleh
        overflow, kalau tidak tooltip rail dan tinggi brand saling bentrok."""
        css = self._css()
        self.assertRegex(
            css, r'\.sidebar-nav\s*\{[^}]*overflow-y\s*:\s*auto',
            '.sidebar-nav harus jadi scroller (overflow-y: auto)')
        self.assertRegex(
            css, r'\.sidebar-nav\s*\{[^}]*min-height\s*:\s*0',
            '.sidebar-nav butuh min-height: 0 supaya boleh menyusut di flex column')
        self.assertRegex(
            css, r'\.sidebar-desktop\s*\{\s*overflow\s*:\s*hidden\s*;\s*\}',
            '.sidebar-desktop harus overflow: hidden')

    def test_footer_juga_dilindungi(self):
        css = self._css()
        self.assertRegex(
            css, r'\.sidebar-footer\s*\{\s*flex\s*:\s*0\s+0\s+auto\s*;\s*\}',
            '.sidebar-footer harus flex: 0 0 auto')
