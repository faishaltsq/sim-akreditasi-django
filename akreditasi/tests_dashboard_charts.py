"""Dashboard: JS inline harus lolos parse setelah dirender Django.

Satu syntax error di blok <script> dashboard membatalkan SELURUH blok —
Chart.js tidak pernah dipanggil, dan keempat kanvas (mutu bulanan, renstra,
tren tahunan, kepatuhan EP) tampil kosong tanpa pesan error apa pun di UI.

Penyebab nyata yang pernah lolos: objek font Chart.js ditulis dengan koma
sebagai pengganti titik dua — `{ family: "Inter", sans-serif, size: 11 }` —
yang di JavaScript adalah SyntaxError, bukan nilai valid.

Yang diperiksa adalah HTML HASIL RENDER, bukan sumber templat: sumbernya
memang berisi tag {{ }} / {% %} yang baru sah setelah dievaluasi Django.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile

TEMPLATE = (Path(__file__).resolve().parent.parent
            / 'templates' / 'akreditasi' / 'dashboard.html')


class DashboardInlineScriptTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.user = U.objects.create_user(
            'chartjs', 'chartjs@example.test', 'x', is_superuser=True, is_staff=True)
        prof, _ = UserProfile.objects.get_or_create(user=cls.user)
        prof.role = 'SUPER_ADMIN'
        prof.save()

    def _render(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('akreditasi:dashboard'))
        self.assertEqual(r.status_code, 200, 'dashboard tidak boleh error')
        html = r.content.decode('utf-8')
        return re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)

    def test_tidak_ada_sisa_tag_template_setelah_render(self):
        """Tag {{ }} / {% %} yang lolos ke JS hampir selalu jadi syntax error."""
        for i, blok in enumerate(self._render()):
            sisa = re.findall(r'\{\{.*?\}\}|\{%.*?%\}', blok)
            self.assertFalse(
                sisa, f'blok script #{i} masih berisi tag template: {sisa[:3]}')

    def test_blok_script_lolos_parse_javascript(self):
        """Bukti langsung: jalankan node --check pada tiap blok hasil render."""
        node = shutil.which('node')
        if not node:
            self.skipTest('node tidak tersedia untuk memeriksa sintaks')

        tmp = Path(tempfile.mkdtemp())
        try:
            for i, blok in enumerate(self._render()):
                if len(blok.strip()) < 40:
                    continue
                f = tmp / f'blok{i}.js'
                f.write_text(blok, encoding='utf-8')
                chk = subprocess.run([node, '--check', str(f)],
                                     capture_output=True, text=True)
                self.assertEqual(
                    chk.returncode, 0,
                    f'blok script #{i} gagal parse:\n{chk.stderr[:600]}')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_objek_font_chart_memakai_titik_dua(self):
        """Koma di posisi properti adalah SyntaxError yang mematikan semua chart."""
        html = TEMPLATE.read_text(encoding='utf-8')
        rusak = re.findall(r'family:\s*"[^"]*"\s*,\s*[a-z-]+\s*,', html)
        self.assertFalse(
            rusak,
            'objek font Chart.js memakai koma sebagai pengganti titik dua '
            f'(SyntaxError, mematikan semua grafik): {rusak[:3]}')

    def test_kanvas_grafik_masih_ada(self):
        """Grafik tidak boleh hilang saat merapikan tampilan."""
        html = TEMPLATE.read_text(encoding='utf-8')
        for cid in ('chartMutuBulanan', 'chartRenstraTahunan',
                    'chartTahunanMulti', 'kepatuhanChart'):
            self.assertIn(f'id="{cid}"', html,
                          f'kanvas {cid} hilang dari dashboard')
