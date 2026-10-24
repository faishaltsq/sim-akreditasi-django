"""Sidebar desktop selalu penuh, tanpa kontrol ciut/perluas."""

from django.conf import settings
from django.test import SimpleTestCase


class SidebarExpandedTest(SimpleTestCase):
    def test_tombol_collapse_desktop_dihapus(self):
        template = (settings.BASE_DIR / 'templates/base.html').read_text(encoding='utf-8')
        self.assertNotIn('sidebarCollapseBtn', template)
        self.assertNotIn('sidebar-collapse-btn', template)

    def test_preferensi_lama_tidak_memulihkan_mode_ciut(self):
        template = (settings.BASE_DIR / 'templates/base.html').read_text(encoding='utf-8')
        script = (settings.BASE_DIR / 'static/js/v3-shell.js').read_text(encoding='utf-8')
        self.assertNotIn('localStorage.getItem', template)
        self.assertNotIn('localStorage.getItem', script)
        self.assertNotIn('localStorage.setItem', script)
        self.assertIn("localStorage.removeItem('arima.v3.sidebar.collapsed')", script)

    def test_css_tidak_menyediakan_mode_rail(self):
        css = (settings.BASE_DIR / 'static/css/v3-tokens.css').read_text(encoding='utf-8')
        self.assertNotIn('.sb-collapsed', css)
        self.assertNotIn('.sidebar-collapse-btn', css)

    def test_menu_mobile_tetap_bisa_dibuka_dan_ditutup(self):
        template = (settings.BASE_DIR / 'templates/base.html').read_text(encoding='utf-8')
        self.assertIn('data-bs-target="#mobileSidebar"', template)
        self.assertIn('data-bs-dismiss="offcanvas"', template)
