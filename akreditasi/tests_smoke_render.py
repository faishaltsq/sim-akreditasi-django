"""Smoke render semua halaman GET tanpa argumen — regresi /control/ & route hasil merge."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, get_resolver, reverse, URLPattern, URLResolver
import re

SKIP = re.compile(r'logout|delete|hapus|update|toggle|reset|create|/ai/|download|cetak|pdf|csv|export', re.I)


def _walk(res, prefix=""):
    for p in res.url_patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


class SmokeRenderTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.user = U.objects.filter(is_superuser=True).first() or U.objects.create_superuser(
            username='smoke', email='smoke@example.test', password='x')

    def test_semua_halaman_get_render(self):
        self.client.force_login(self.user)
        bad = []
        checked = 0
        for pat in sorted({x for x in _walk(get_resolver()) if not x.startswith('admin/')}):
            if '<' in pat or SKIP.search(pat):
                continue
            url = '/' + pat.lstrip('/')
            try:
                r = self.client.get(url)
            except Exception as exc:
                bad.append('%s -> %s: %s' % (url, type(exc).__name__, str(exc)[:180]))
                continue
            checked += 1
            if r.status_code >= 500:
                bad.append('%s -> %s' % (url, r.status_code))
        self.assertGreater(checked, 40, 'terlalu sedikit halaman terperiksa')
        self.assertEqual(bad, [], 'halaman gagal render:\n' + '\n'.join(bad))

    def test_semua_nama_route_bisa_di_reverse(self):
        """Route yang hilang saat merge bikin NoReverseMatch di template mana pun."""
        wajib = [
            'kontrol_hub', 'kontrol_risiko', 'kontrol_emr', 'kontrol_dokumen',
            'kontrol_ringkasan_ai', 'laporan_mutu_daftar', 'logbook_daftar',
            'pencarian', 'indikator_inm_matrix', 'dashboard',
        ]
        hilang = []
        for nama in wajib:
            try:
                reverse('akreditasi:' + nama)
            except NoReverseMatch:
                hilang.append(nama)
        self.assertEqual(hilang, [], 'route hilang: %s' % hilang)
