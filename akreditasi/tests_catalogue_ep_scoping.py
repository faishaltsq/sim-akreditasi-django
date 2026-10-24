"""Regression tests: EP/matrix screens must never union two catalogue editions.

Bug: ``ep_list`` queried ``Category.objects.all()`` / ``StandardItem.objects``
without a framework filter, so after a second edition was installed the page
showed both editions' EP together. These tests pin the fix.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from akreditasi import catalogue
from akreditasi.models import Category, Framework, StandardItem, UnitKerja


class EditionScopingRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='scope-admin', password='x'
        )
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        UnitKerja.objects.create(name='Unit Uji', code='UJI-1')

        self.fw_old = Framework.objects.create(
            name='Edisi 2022', edition='2022', version='2022',
            lifecycle='ARCHIVED', is_active=False,
        )
        self.fw_new = Framework.objects.create(
            name='Edisi 2024', edition='2024', version='2024',
            lifecycle='ACTIVE', is_active=True,
        )
        self.cat_old = Category.objects.create(
            framework=self.fw_old, code='OLD', name='Lama', order=1,
        )
        self.cat_new = Category.objects.create(
            framework=self.fw_new, code='NEW', name='Baru', order=1,
        )
        for index in range(3):
            StandardItem.objects.create(
                category=self.cat_old, sub_standard='OLD 1',
                code=f'OLD 1 EP {index}', description='lama', order=index,
            )
        for index in range(5):
            StandardItem.objects.create(
                category=self.cat_new, sub_standard='NEW 1',
                code=f'NEW 1 EP {index}', description='baru', order=index,
            )

    def test_scope_items_returns_one_edition_only(self):
        self.assertEqual(catalogue.scope_items(self.fw_new).count(), 5)
        self.assertEqual(catalogue.scope_items(self.fw_old).count(), 3)

    def test_scope_categories_returns_one_edition_only(self):
        self.assertEqual(
            list(catalogue.scope_categories(self.fw_new).values_list('code', flat=True)),
            ['NEW'],
        )

    def test_ep_list_page_shows_only_active_edition(self):
        self.client.force_login(self.user)

        response = self.client.get('/ep/list/')

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('NEW 1 EP 0', body)
        self.assertNotIn('OLD 1 EP 0', body)

    def test_ep_list_archive_selection_is_read_only_scoped(self):
        self.client.force_login(self.user)

        response = self.client.get(
            '/ep/list/', {'framework': self.fw_old.pk}
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('OLD 1 EP 0', body)
        self.assertNotIn('NEW 1 EP 0', body)

    def test_read_resolver_falls_back_to_single_edition_when_none_active(self):
        # Remove every ACTIVE row, including the one installed by migrations.
        Framework.objects.update(lifecycle='ARCHIVED', is_active=False)

        resolved = catalogue.select_catalogue_for_read(self.user)

        # Falls back to exactly one edition (newest by edition), never a union.
        self.assertEqual(resolved.pk, self.fw_new.pk)

    def test_resolve_catalogue_still_fails_closed_without_active(self):
        Framework.objects.update(lifecycle='ARCHIVED', is_active=False)

        with self.assertRaises(Exception):
            catalogue.resolve_catalogue(self.user)

    def test_legacy_archive_spelling_is_normalised_on_save(self):
        legacy = Framework.objects.create(
            name='Legacy', edition='2021', version='2021',
            lifecycle='ARCHIVE', is_active=False,
        )

        legacy.refresh_from_db()
        self.assertEqual(legacy.lifecycle, 'ARCHIVED')
