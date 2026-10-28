"""Sidebar aggregate cache must be dropped on catalogue activation.

`sidebar_context` caches per-pokja aggregates (score sum, EP count, assessed
count) under `sidebar_stats:<version_key>`. `invalidate_catalogue_caches`
already drops the identity and the profile/config keys, but the stats key was
left behind, so a catalogue activation kept serving the previous edition's
percentages for the whole TTL.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from accounts.models import UserProfile
from akreditasi.context_processors import (
    _CATALOGUE_IDENTITY_KEY,
    invalidate_catalogue_caches,
    sidebar_context,
)
from akreditasi.models import (
    Category,
    Framework,
    QualityRecord,
    StandardItem,
    UnitKerja,
)


class SidebarStatsInvalidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='sidebar-stats')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS')
        self.framework = Framework.objects.create(
            name='STARKES 2024', version='2024', edition='2024', is_active=True
        )
        self.category = Category.objects.create(
            framework=self.framework, code='KPS', name='Kualifikasi & Pendidikan Staf',
            target_ep_count=2,
        )
        self.item = StandardItem.objects.create(
            category=self.category, sub_standard='KPS 1', code='KPS 1 EP a'
        )
        self.unit = UnitKerja.objects.create(name='Unit Sidebar', code='SB-TEST')
        self.record = QualityRecord.objects.create(
            standard_item=self.item, unit=self.unit, score=10
        )

    def _request(self):
        class _Req:
            pass
        return _Req()

    def test_stats_cache_is_populated_and_served(self):
        req = self._request()
        req.user = self.user
        context = sidebar_context(req)
        self.assertIn('sidebar_categories', context)
        # A second warm call must not re-query: the stats key now exists.
        from django.db import connection
        with self.assertNumQueries(0):
            sidebar_context(req)
        del connection

    def test_invalidation_drops_the_stats_cache(self):
        req = self._request()
        req.user = self.user
        sidebar_context(req)

        version_key = cache.get(_CATALOGUE_IDENTITY_KEY)
        stats_key = f'sidebar_stats:{version_key}'
        self.assertIsNotNone(cache.get(stats_key))

        invalidate_catalogue_caches()
        self.assertIsNone(cache.get(stats_key))
        self.assertIsNone(cache.get(_CATALOGUE_IDENTITY_KEY))

    def test_new_edition_scores_are_served_after_activation(self):
        req = self._request()
        req.user = self.user
        context = sidebar_context(req)
        stale = {
            c.code: c.percentage for c in context['sidebar_categories']
            if c.code == 'KPS'
        }
        self.assertEqual(stale['KPS'], 100)

        # A new catalogue edition becomes live; the old aggregate must not survive.
        self.record.score = 0
        self.record.save(update_fields=['score'])
        invalidate_catalogue_caches()

        context = sidebar_context(req)
        fresh = {
            c.code: c.percentage for c in context['sidebar_categories']
            if c.code == 'KPS'
        }
        self.assertEqual(fresh['KPS'], 0)

    def test_invalidation_is_idempotent(self):
        invalidate_catalogue_caches()
        invalidate_catalogue_caches()
        self.assertIsNone(cache.get(_CATALOGUE_IDENTITY_KEY))
