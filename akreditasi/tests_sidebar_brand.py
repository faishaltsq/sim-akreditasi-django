"""Brand sidebar: tinggi harus sepadan topbar dan subjudul tidak boleh dipotong.

Bug yang dikunci: blok brand memakai min-height dengan tiga baris teks,
sehingga isinya meluber melewati tepi atas dan bawah header. Subjudul juga
berbagi baris dengan ikon dan tombol, menyisakan ~133px — tidak cukup untuk
"Akreditasi & Manajemen Risiko", sehingga terpotong ellipsis dan terbaca kabur.
"""
import re

from django.conf import settings
from django.test import SimpleTestCase


class SidebarBrandLayoutTest(SimpleTestCase):
    def _css(self):
        path = settings.BASE_DIR / 'static' / 'css' / 'style.css'
        return path.read_text(encoding='utf-8')

    def _brand_block(self):
        css = self._css()
        m = re.search(r'\.sidebar-brand\s*\{(.*?)\}', css, re.S)
        self.assertIsNotNone(m, 'blok .sidebar-brand tidak ditemukan')
        return m.group(1)

    def test_tinggi_brand_tepat_setinggi_topbar(self):
        """min-height membiarkan isi mendorong header lebih tinggi dari topbar."""
        block = self._brand_block()
        self.assertRegex(
            block, r'height\s*:\s*var\(--topbar-h\)',
            'brand harus memakai height tetap, bukan min-height, agar tidak meluber')
        self.assertNotRegex(
            block, r'min-height\s*:',
            'min-height membuat brand tumbuh melebihi topbar saat teks panjang')

    def test_subjudul_punya_baris_sendiri(self):
        """Subjudul berada di blok teks sendiri, bukan berbagi baris dengan ikon."""
        css = self._css()
        m = re.search(r'\.sidebar-brand-text small\s*\{([^}]*)\}', css, re.S)
        self.assertIsNotNone(m, 'blok .sidebar-brand-text small tidak ditemukan')
        self.assertRegex(
            m.group(1), r'display\s*:\s*block',
            'subjudul harus jadi baris sendiri agar nama RS panjang tidak '
            'berebut lebar dengan judul')

    def test_subjudul_tidak_disembunyikan_di_mode_penuh(self):
        css = self._css()
        self.assertNotRegex(
            css, r'(?<!sb-collapsed )\.sidebar-brand-text small\s*\{[^}]*display\s*:\s*none',
            'subjudul tidak boleh disembunyikan pada mode sidebar penuh')
