"""Track C6: Dasbor dan sidebar berskop edisi — pemakaian resolve_catalogue di semua pembaca."""

from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.contrib.auth import get_user_model

from akreditasi.catalogue import resolve_catalogue
from akreditasi.models import (
    Framework, Category, StandardItem, QualityRecord, UnitKerja,
)

User = get_user_model()


class EditionScopedReadTests(TestCase):
    def setUp(self):
        cache.clear()
        Framework.objects.filter(lifecycle='ACTIVE').update(
            lifecycle='ARCHIVED', is_active=False)
        self.active = Framework.objects.create(
            name='STARKES 2024 Aktif', version='2024', edition='2024',
            lifecycle='ACTIVE', is_active=True,
        )
        self.archived = Framework.objects.create(
            name='STARKES 2022 Arsip', version='2022', edition='2022',
            lifecycle='ARCHIVED', is_active=False,
        )
        self.superuser = User.objects.create_superuser('sa', 'sa@x.com', 'pw')
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_resolve_catalogue_returns_active_by_default(self):
        self.assertEqual(resolve_catalogue(self.superuser), self.active)

    def test_resolve_catalogue_selects_archived_explicitly(self):
        self.assertEqual(
            resolve_catalogue(self.superuser, framework_id=self.archived.pk),
            self.archived,
        )

    def test_dashboard_uses_active_framework_not_mixed_editions(self):
        cat_a = Category.objects.create(
            framework=self.active, code='TKRS', name='TKRS', order=1
        )
        cat_x = Category.objects.create(
            framework=self.archived, code='TKRS', name='TKRS', order=1
        )
        item_a = StandardItem.objects.create(
            category=cat_a, sub_standard='TKRS 1', code='TKRS 1 EP a',
            description='2024', order=1,
        )
        item_x = StandardItem.objects.create(
            category=cat_x, sub_standard='TKRS 1', code='TKRS 1 EP a',
            description='2022', order=1,
        )
        QualityRecord.objects.create(
            standard_item=item_a, unit=UnitKerja.objects.create(name='U', code='U'),
            score=10, assessment_state='ASSESSED',
        )
        QualityRecord.objects.create(
            standard_item=item_x, unit=UnitKerja.objects.create(name='U2', code='U2'),
            score=10, assessment_state='ASSESSED',
        )
        resp = self.client.get(reverse('akreditasi:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['framework'], self.active)

    def test_unknown_framework_selection_fails_closed(self):
        with self.assertRaises(Exception):
            resolve_catalogue(self.superuser, framework_id=999999)
