"""Sidebar desktop selalu penuh, tanpa kontrol ciut/perluas."""

import os
import re
import subprocess
import sys

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

    def test_vercel_merender_url_static_berfingerprint(self):
        env = os.environ.copy()
        env.update({
            'DJANGO_SETTINGS_MODULE': 'config.settings',
            'DJANGO_DEBUG': 'False',
            'VERCEL': '1',
        })
        result = subprocess.run(
            [sys.executable, '-c', (
                "import django; django.setup(); "
                "from django.templatetags.static import static; "
                "print(static('js/v3-shell.js'))"
            )],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertRegex(
            result.stdout.strip(),
            re.compile(r'^/static/js/v3-shell\.[0-9a-f]{12}\.js$'),
        )

    def test_template_ai_memakai_url_static_berfingerprint(self):
        env = os.environ.copy()
        env.update({
            'DJANGO_SETTINGS_MODULE': 'config.settings',
            'DJANGO_DEBUG': 'False',
            'VERCEL': '1',
        })
        code = """
import re
import django
django.setup()
from django.template.loader import render_to_string
from django.test import RequestFactory
from unittest.mock import MagicMock

request = RequestFactory().get('/')
user = MagicMock()
user.username = 'smoke'
user.is_authenticated = True
user.is_superuser = True
user.get_full_name.return_value = 'Smoke'
user.profile.full_name = 'Smoke'
user.profile.role_badge_class = 'primary'
user.profile.get_role_display.return_value = 'Super Admin'
request.user = user

for name in (
    'accounts/admin_control_center.html',
    'akreditasi/insiden_form.html',
    'akreditasi/risiko_form.html',
):
    html = render_to_string(name, {'request': request, 'user': user})
    match = re.search(r'<script src="([^" ]*ai-assist[^" ]*)"></script>', html)
    if match is None:
        raise RuntimeError(f'ai-assist.js tidak dirender oleh {name}')
    print(match.group(1))
"""
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        rendered_urls = result.stdout.strip().splitlines()
        self.assertEqual(len(rendered_urls), 3)
        for url in rendered_urls:
            self.assertRegex(
                url, r'^/static/js/ai-assist\.[0-9a-f]{12}\.js$')

    def test_menu_mobile_tetap_bisa_dibuka_dan_ditutup(self):
        template = (settings.BASE_DIR / 'templates/base.html').read_text(encoding='utf-8')
        self.assertIn('data-bs-target="#mobileSidebar"', template)
        self.assertIn('data-bs-dismiss="offcanvas"', template)
