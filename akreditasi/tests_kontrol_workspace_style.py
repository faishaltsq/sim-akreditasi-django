"""Kontrak stylesheet workspace Integrated Control.

Tes ini membaca berkas CSS langsung (tanpa DB, tanpa request) supaya brand,
aksesibilitas, dan larangan blur/font eksternal tidak bisa hilang diam-diam.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


def _static_root():
    base = getattr(settings, 'BASE_DIR', None)
    return Path(base) if base else Path(__file__).resolve().parent.parent


def _css():
    return (_static_root() / 'static/css/kontrol-workspace.css').read_text(
        encoding='utf-8')


def _block(css, opener):
    """Isi blok kurawal pertama yang diawali `opener`, via pencocokan kurung."""
    start = css.index(opener) + len(opener)
    start = css.index('{', start) + 1
    depth = 1
    for idx in range(start, len(css)):
        if css[idx] == '{':
            depth += 1
        elif css[idx] == '}':
            depth -= 1
            if depth == 0:
                return css[start:idx]
    raise AssertionError(f'blok tidak tertutup: {opener}')


def _declarations(css, selector):
    """Deklarasi untuk selector persis di dalam `css` (blok terluar)."""
    import re
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    found = []
    for chunk in css.split('}'):
        if '{' not in chunk:
            continue
        head, body = chunk.split('{', 1)
        if head.strip() == selector:
            found.append(body)
    if not found:
        raise AssertionError(f'selector tidak ditemukan: {selector}')
    return ' '.join(' '.join(found).split())


class ControlWorkspaceStyleTest(SimpleTestCase):
    def test_brand_and_accessibility_contract(self):
        css = (_static_root() / 'static/css/kontrol-workspace.css').read_text(
            encoding='utf-8')
        for required in ('#14213D', '#4F5BD5', '#37429E',
                         ':focus-visible', 'prefers-reduced-motion',
                         '@media print', 'inter-latin.woff2', 'manrope-latin.woff2'):
            with self.subTest(required=required):
                self.assertIn(required, css)
        self.assertNotIn('backdrop-filter', css)
        self.assertNotIn('!important', css)
        self.assertNotIn('fonts.googleapis.com', css)

    def test_legacy_shell_has_no_topbar_blur(self):
        css = (_static_root() / 'static/css/kontrol.css').read_text(encoding='utf-8')
        self.assertNotIn('backdrop-filter', css)

    def test_mobile_header_main_resets_flex_basis(self):
        """P1: induk jadi column, jadi basis 420px terbaca sebagai tinggi kosong."""
        css = _css()
        mobile = _block(css, '@media (max-width: 767px)')
        decls = _declarations(
            mobile, '.kontrol-workspace .kontrol-header-main')
        self.assertIn('flex:0 0 auto', decls.replace('flex: 0 0 auto', 'flex:0 0 auto'))
        self.assertIn('min-height:0', decls.replace('min-height: 0', 'min-height:0'))
        self.assertNotIn('flex:1 1 420px', decls.replace('flex: 1 1 420px', 'flex:1 1 420px'))

    def test_mobile_header_override_not_duplicated(self):
        css = _css()
        self.assertEqual(css.count('@media (max-width: 767px)'), 1)
        self.assertEqual(
            css.count('.kontrol-workspace .kontrol-header-main'), 2)

    def test_desktop_header_main_keeps_basis(self):
        css = _css()
        desktop = css.split('@media (max-width: 767px)')[0]
        decls = _declarations(desktop, '.kontrol-workspace .kontrol-header-main')
        self.assertIn('flex:1 1 420px', decls.replace('flex: 1 1 420px', 'flex:1 1 420px'))

    def test_populated_matrix_count_uses_dark_foreground(self):
        """P4: latar severity lama semi-transparan; teks putih cuma 1.745–3.655:1."""
        css = _css()
        decls = _declarations(css, '.kontrol-workspace .matrix-cell.has-data')
        self.assertIn('color:#06121f', decls.replace('color: #06121F', 'color:#06121f'))
        self.assertNotIn('color:#ffffff', decls.replace('color: #FFFFFF', 'color:#ffffff'))
        # Severity tetap milik kontrol.css; stylesheet ini tidak boleh mewarnai ulang.
        self.assertEqual(css.count('.matrix-cell.level-'), 0)

    def test_module_link_scope_label_readable(self):
        """P3: <small> menjelaskan cakupan; minimum metadata ringkas 13px."""
        css = _css()
        decls = _declarations(
            css, '.kontrol-workspace .kontrol-module-link small')
        self.assertIn('font-size:13px', decls.replace('font-size: 13px', 'font-size:13px'))
        self.assertIn('line-height:1.5', decls.replace('line-height: 1.5', 'line-height:1.5'))

    def test_readable_body_and_panel_heading_scale(self):
        css = _css()
        body = _declarations(css, 'body.kontrol-workspace')
        self.assertIn("font: 16px/1.6 'Inter'", body)
        heading = _declarations(css, '.kontrol-workspace .panel-head h2')
        self.assertIn('font-size: 16px', heading)
        self.assertIn('line-height: 1.35', heading)

    def test_desktop_workspace_uses_compact_spacing(self):
        css = _css()
        hero = _declarations(
            css, '.kontrol-workspace :is(.kontrol-hero, .kontrol-header, .kontrol-subhead)')
        self.assertIn('padding: 20px', hero)
        self.assertIn('margin: 0 0 18px', hero)
        services = _declarations(css, '.kontrol-workspace .kontrol-layanan')
        self.assertIn('margin: 0 0 16px', services)
        kpis = _declarations(css, '.kontrol-workspace .kontrol-kpis')
        self.assertIn('margin-bottom: 16px', kpis)
        grid = _declarations(css, '.kontrol-workspace .kontrol-grid-2')
        self.assertIn('margin-bottom: 16px', grid)
        panel_head = _declarations(css, '.kontrol-workspace .panel-head')
        self.assertIn('margin-bottom: 10px', panel_head)
        unit_switch = _declarations(css, '.kontrol-workspace .kontrol-unit-switch')
        self.assertIn('width: min(100%, 440px)', unit_switch)
        summary = _declarations(css, '.kontrol-workspace .kontrol-emr-summary')
        self.assertIn('grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr)', summary)
        summary_kpis = _declarations(css, '.kontrol-workspace .kontrol-emr-summary .kontrol-kpis')
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr))', summary_kpis)
        mobile = _block(css, '@media (max-width: 767px)')
        mobile_summary = _declarations(mobile, '.kontrol-workspace .kontrol-emr-summary')
        self.assertIn('grid-template-columns: minmax(0, 1fr)', mobile_summary)

    def test_readable_labels_and_service_text(self):
        css = _css()
        for selector, size in (
            ('.kontrol-workspace .kpi-label', 14),
            ('.kontrol-workspace .kpi-foot', 14),
            ('.kontrol-workspace .kpi-scope', 13),
            ('.kontrol-workspace .panel-hint', 13),
            ('.kontrol-workspace .layanan-date', 13),
            ('.kontrol-workspace .layanan-entry-text strong', 15),
            ('.kontrol-workspace .layanan-entry-text small', 14),
            ('.kontrol-workspace .kontrol-caption', 14),
        ):
            with self.subTest(selector=selector):
                self.assertIn(f'font-size: {size}px', _declarations(css, selector))

    def test_service_rows_support_long_mobile_copy(self):
        css = _css()
        mobile = _block(css, '@media (max-width: 767px)')
        row = _declarations(mobile, '.kontrol-workspace .layanan-entry')
        self.assertIn('display: grid', row)
        self.assertIn('minmax(0, 1fr)', row)
        self.assertIn("grid-template-areas: 'icon text go' '. count .'", row)
        text = _declarations(css, '.kontrol-workspace .layanan-entry-text')
        self.assertIn('min-width: 0', text)
        self.assertIn('overflow-wrap: anywhere', text)
