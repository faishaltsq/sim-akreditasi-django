"""Sidebar di-include dua kali (offcanvas mobile + rail desktop).

Kalau id elemen collapse sama di kedua salinan, `document.querySelector`
milik Bootstrap selalu menemukan salinan pertama (mobile, `display:none`),
sehingga klik di sidebar desktop tidak membuka apa pun. Test ini mengunci
kontrak: tidak boleh ada id duplikat di halaman yang memuat kedua sidebar.
"""
import re
from collections import Counter

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class SidebarUniqueIdTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.user = U.objects.filter(is_superuser=True).first() or U.objects.create_superuser(
            username='sbx', email='sbx@example.test', password='x')

    def _html(self):
        self.client.force_login(self.user)
        return self.client.get(reverse('akreditasi:dashboard')).content.decode()

    def test_tidak_ada_id_duplikat(self):
        html = self._html()
        ids = re.findall(r'\bid="([^"]+)"', html)
        dup = {k: v for k, v in Counter(ids).items() if v > 1}
        self.assertEqual(dup, {}, 'id duplikat bikin collapse Bootstrap salah sasaran: %s' % dup)

    def test_kedua_sidebar_punya_id_berbeda(self):
        html = self._html()
        # Search box ada di dua instance, masing-masing dengan sufiks sendiri.
        self.assertIn('id="sidebarPokjaSearch-mobile"', html)
        self.assertIn('id="sidebarPokjaSearch-desktop"', html)
        # Target collapse kelompok juga harus unik per instance.
        self.assertIn('kelompok-MANAJEMEN-mobile', html)
        self.assertIn('kelompok-MANAJEMEN-desktop', html)

    def test_trigger_collapse_menunjuk_target_yang_ada(self):
        """Setiap data-bs-target/href collapse harus menunjuk id yang benar-benar ada."""
        html = self._html()
        ids = set(re.findall(r'\bid="([^"]+)"', html))
        targets = set(re.findall(r'data-bs-target="#([^"]+)"', html))
        targets |= set(re.findall(r'href="#([^"]+)"', html))
        targets = {t for t in targets if t and not t.startswith('main-content')}
        hilang = sorted(t for t in targets if t not in ids)
        self.assertEqual(hilang, [], 'target collapse tanpa elemen: %s' % hilang)
