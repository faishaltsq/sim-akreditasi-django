"""Track C2: Identitas edisi dan kunci alami berskop — tidak ada fallbacks tanpa cakupan."""

from django.test import TestCase

from akreditasi.catalogue import resolve_catalogue, require_catalogue_write
from akreditasi.models import (
    Category, Framework, StandardItem, UnitKerja, QualityRecord,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class EditionIdentityTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Uji', code='HC-UJI')

    def test_same_code_in_two_frameworks_allowed(self):
        """Kode EP sama diperbolehkan di dua framework berbeda (scoped)."""
        f2022 = Framework.objects.create(name='F 2022', version='2022', edition='2022',
                                         lifecycle='ARCHIVED', is_active=False)
        f2024 = Framework.objects.create(name='F 2024', version='2024', edition='2024',
                                         lifecycle='ACTIVE', is_active=True)
        c2022 = Category.objects.create(framework=f2022, code='TKRS', name='TKRS', order=1)
        c2024 = Category.objects.create(framework=f2024, code='TKRS', name='TKRS', order=1)
        StandardItem.objects.create(category=c2022, sub_standard='TKRS 1', code='TKRS 1 EP a',
                                    description='lama', order=1)
        StandardItem.objects.create(category=c2024, sub_standard='TKRS 1', code='TKRS 1 EP a',
                                    description='baru', order=1)
        self.assertEqual(StandardItem.objects.filter(category=c2022, code='TKRS 1 EP a').count(), 1)
        self.assertEqual(StandardItem.objects.filter(category=c2024, code='TKRS 1 EP a').count(), 1)

    def test_duplicate_code_within_one_framework_rejected(self):
        """Kode EP duplikat dalam satu framework ditolak (unique_together)."""
        fw = Framework.objects.create(name='F', version='2024', edition='2024',
                                      lifecycle='ACTIVE', is_active=True)
        cat = Category.objects.create(framework=fw, code='TKRS', name='TKRS', order=1)
        StandardItem.objects.create(category=cat, sub_standard='TKRS 1', code='TKRS 1 EP a',
                                    description='a', order=1)
        with self.assertRaises(Exception):
            StandardItem.objects.create(category=cat, sub_standard='TKRS 1', code='TKRS 1 EP a',
                                        description='b', order=2)

    def test_resolve_catalogue_returns_active_when_no_id(self):
        fw = Framework.objects.create(name='Aktif', version='2024', edition='2024',
                                      lifecycle='ACTIVE', is_active=True)
        self.assertEqual(resolve_catalogue(None), fw)

    def test_resolve_catalogue_fails_closed_no_fallback(self):
        # Clear every ACTIVE row first: migrations install one ACTIVE catalogue,
        # and this test asserts the *absence* of any active edition.
        Framework.objects.update(lifecycle='ARCHIVED', is_active=False)
        Framework.objects.create(name='Arsip', version='2022', edition='2022',
                                 lifecycle='ARCHIVED', is_active=False)
        with self.assertRaises(Exception):
            resolve_catalogue(None)

    def test_resolve_catalogue_explicit_archived_permitted(self):
        fw = Framework.objects.create(name='Arsip', version='2022', edition='2022',
                                      lifecycle='ARCHIVED', is_active=False)
        self.assertEqual(resolve_catalogue(None, framework_id=fw.pk), fw)

    def test_resolve_catalogue_rejects_staged(self):
        fw = Framework.objects.create(name='Draft', version='2024', edition='2024',
                                      lifecycle='DRAFT', is_active=False)
        with self.assertRaises(Exception):
            resolve_catalogue(None, framework_id=fw.pk)

    def test_resolve_catalogue_unknown_id_raises(self):
        with self.assertRaises(Framework.DoesNotExist):
            resolve_catalogue(None, framework_id=999999)

    def test_require_catalogue_write_rejects_archived_even_superadmin(self):
        fw = Framework.objects.create(name='Arsip', version='2022', edition='2022',
                                      lifecycle='ARCHIVED', is_active=False)
        cat = Category.objects.create(framework=fw, code='TKRS', name='TKRS', order=1)
        item = StandardItem.objects.create(category=cat, sub_standard='TKRS 1',
                                           code='TKRS 1 EP a', description='x', order=1)
        rec = QualityRecord.objects.create(standard_item=item, unit=self.unit, score=10)
        superuser = User.objects.create_superuser('sa', 'sa@x.com', 'pw')
        with self.assertRaises(Exception):
            require_catalogue_write(superuser, item=rec, operation='score')

    def test_require_catalogue_write_allows_active(self):
        fw = Framework.objects.create(name='Aktif', version='2024', edition='2024',
                                      lifecycle='ACTIVE', is_active=True)
        cat = Category.objects.create(framework=fw, code='TKRS', name='TKRS', order=1)
        item = StandardItem.objects.create(category=cat, sub_standard='TKRS 1',
                                           code='TKRS 1 EP a', description='x', order=1)
        rec = QualityRecord.objects.create(standard_item=item, unit=self.unit, score=10)
        superuser = User.objects.create_superuser('sa2', 'sa2@x.com', 'pw')
        require_catalogue_write(superuser, item=rec, operation='score')  # tidak ada pengecualian
