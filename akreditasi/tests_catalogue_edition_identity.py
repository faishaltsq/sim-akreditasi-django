"""Regression tests for the STARKES 2024 edition-identity defects.

Three separate bugs made production keep serving the 2022 catalogue:

1. ``import_instrumen_2024`` created the 2024 framework without ``edition``, so
   it inherited the model default ``'2022'``.
2. ``_replace`` set ``is_active`` but never ``lifecycle``, leaving every row
   non-ACTIVE and ``Framework.active()`` returning ``None``.
3. ``select_catalogue_for_read`` ordered its fallback by ``-version``, and the
   retired 2022 row carries ``version='2024-archived'`` — which sorts above the
   live ``'2024'``.

Each test pins one of them so a future import cannot silently regress to 2022.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from akreditasi import catalogue
from akreditasi.models import Category, Framework, StandardItem


class ReadResolverPrefersLiveEditionTests(TestCase):
    """The read fallback must never serve a superseded catalogue."""

    def setUp(self):
        # Migrasi 0013 menanam satu Framework STARKES 2022 pada database test
        # (dipakai suite lain yang memang butuh struktur 16 bab). Kelas ini
        # menguji resolusi edisi secara terisolasi, jadi tabel katalog
        # dikosongkan lebih dulu — tanpa itu resolver selalu menemukan katalog
        # seed dan setiap assertion membandingkan pk yang salah.
        Framework.objects.all().delete()
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='resolver-admin', password='x'
        )

    def test_fallback_skips_superseded_version_even_though_it_sorts_higher(self):
        # The exact production shape: the retired 2022 catalogue was stamped
        # '2024-archived', which is lexicographically greater than '2024'.
        retired = Framework.objects.create(
            name='STARKES Edisi 2022 / Kemenkes RI',
            edition='2022', version='2024-archived',
            lifecycle='ARCHIVED', is_active=False,
        )
        live = Framework.objects.create(
            name='STARKES Edisi 2024 / KMK HK.01.07/MENKES/1596/2024',
            edition='2024', version='2024',
            lifecycle='ARCHIVED', is_active=False,
        )
        self.assertGreater(retired.version, live.version)

        resolved = catalogue.select_catalogue_for_read(self.user)

        self.assertEqual(resolved.pk, live.pk)
        self.assertEqual(resolved.edition, '2024')

    def test_fallback_compares_edition_numerically(self):
        # Lexicographic ordering would put '999' above '2024'.
        Framework.objects.create(
            name='Katalog Lama', edition='999', version='999',
            lifecycle='ARCHIVED', is_active=False,
        )
        newest = Framework.objects.create(
            name='Katalog Baru', edition='2024', version='2024',
            lifecycle='ARCHIVED', is_active=False,
        )
        self.assertEqual(catalogue.select_catalogue_for_read(self.user).pk, newest.pk)

    def test_active_catalogue_wins_over_newer_archived_one(self):
        active = Framework.objects.create(
            name='Aktif', edition='2022', version='2022',
            lifecycle='ACTIVE', is_active=True,
        )
        Framework.objects.create(
            name='Arsip Lebih Baru', edition='2024', version='2024',
            lifecycle='ARCHIVED', is_active=False,
        )
        self.assertEqual(catalogue.select_catalogue_for_read(self.user).pk, active.pk)

    def test_staged_candidates_are_never_the_fallback(self):
        staged = Framework.objects.create(
            name='Kandidat', edition='2024', version='2024',
            lifecycle='DRAFT', is_active=False,
        )
        readable = Framework.objects.create(
            name='Arsip', edition='2022', version='2022',
            lifecycle='ARCHIVED', is_active=False,
        )
        resolved = catalogue.select_catalogue_for_read(self.user)
        self.assertEqual(resolved.pk, readable.pk)
        self.assertNotEqual(resolved.pk, staged.pk)


class EditionScopedScreensTests(TestCase):
    """The EP list must render the live 2024 edition, not the 2022 archive."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ep-admin', password='x'
        )
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])

        # Lihat catatan di ReadResolverPrefersLiveEditionTests: buang katalog
        # hasil seed migrasi 0013 agar layar EP hanya memuat dua edisi yang
        # dibuat di sini.
        Framework.objects.all().delete()
        cache.clear()

        self.retired = Framework.objects.create(
            name='STARKES Edisi 2022 / Kemenkes RI',
            edition='2022', version='2024-archived',
            lifecycle='ARCHIVED', is_active=False,
        )
        self.live = Framework.objects.create(
            name='STARKES Edisi 2024 / KMK HK.01.07/MENKES/1596/2024',
            edition='2024', version='2024',
            lifecycle='ARCHIVED', is_active=False,
        )
        cat_retired = Category.objects.create(
            framework=self.retired, code='OLD', name='Lama', order=1,
        )
        cat_live = Category.objects.create(
            framework=self.live, code='NEW', name='Baru', order=1,
        )
        StandardItem.objects.create(
            category=cat_retired, sub_standard='OLD 1',
            code='OLD 1 EP a', description='teks lama', order=1,
        )
        StandardItem.objects.create(
            category=cat_live, sub_standard='NEW 1',
            code='NEW 1 EP a', description='teks baru', order=1,
        )

    def test_ep_list_banner_reports_the_2024_edition(self):
        self.client.force_login(self.user)
        response = self.client.get('/ep/list/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_framework'].pk, self.live.pk)
        body = response.content.decode('utf-8')
        self.assertIn('STARKES Edisi 2024', body)
        self.assertIn('Edisi 2024', body)
        self.assertNotIn('STARKES Edisi 2022 / Kemenkes RI', body)

    def test_ep_list_never_mixes_the_two_editions(self):
        self.client.force_login(self.user)
        response = self.client.get('/ep/list/')

        body = response.content.decode('utf-8')
        self.assertIn('NEW 1 EP a', body)
        self.assertNotIn('OLD 1 EP a', body)


class LoginBannerEditionTests(TestCase):
    """The login banner must name the live edition, not a hardcoded year."""

    def setUp(self):
        # The sidebar caches the catalogue identity; a warm cache from an
        # earlier test would mask the resolution this test is pinning.
        cache.clear()

    def test_login_banner_follows_the_active_catalogue(self):
        Framework.objects.create(
            name='STARKES Edisi 2024 / KMK HK.01.07/MENKES/1596/2024',
            edition='2024', version='2024',
            lifecycle='ACTIVE', is_active=True,
        )
        response = self.client.get('/accounts/login/')

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('STANDAR STARKES 2024', body)
        # The stale hardcoded target year must not survive.
        self.assertNotIn('STANDAR STARKES 2026', body)
