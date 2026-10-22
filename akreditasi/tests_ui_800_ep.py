"""Tests untuk Task 5 — UI pada skala 800 EP STARKES 2024.

Cakupan:
  * Pagination ``ep_list`` (800 EP tidak lagi dirender sekaligus).
  * Natural sorting kode standar (PKPO 3 sebelum PKPO 3.1; PPI 2 sebelum PPI 10).
  * Metrik ``ep_total`` / ``ep_selesai`` / ``ep_coverage_pct`` pada ``Category``.
  * Import mengisi ``target_ep_count`` sehingga coverage punya penyebut nyata.
"""

import json
import re
from pathlib import Path

from django.core.paginator import Paginator
from django.test import TestCase
from django.urls import reverse

from akreditasi.models import Category, Framework, QualityRecord, StandardItem, UnitKerja
from akreditasi.instrumen_2024 import natural_sort_key, sort_standards
from akreditasi.views import EP_PAGE_SIZE

FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures' / 'standar_akreditasi_2024.json'


def load_fixture():
    """Golden fixture = list of 227 standard records."""
    with open(FIXTURE, encoding='utf-8') as fh:
        return json.load(fh)


def make_framework():
    return Framework.objects.create(
        name='STARKES Edisi 2024 / Kemenkes RI',
        cycle_type='PDCA',
        version='2024',
    )


def make_category(code, name, order, framework):
    return Category.objects.create(code=code, name=name, order=order, framework=framework)


# ---------------------------------------------------------------------------
# Natural sorting
# ---------------------------------------------------------------------------
class NaturalSortTests(TestCase):
    def test_numeric_part_compares_numerically(self):
        codes = ['PPI 10', 'PPI 2', 'PPI 1']
        self.assertEqual(sort_standards(codes), ['PPI 1', 'PPI 2', 'PPI 10'])

    def test_parent_standard_precedes_its_children(self):
        codes = ['PKPO 3.3', 'PKPO 3.1', 'PKPO 3']
        self.assertEqual(sort_standards(codes), ['PKPO 3', 'PKPO 3.1', 'PKPO 3.3'])

    def test_lexicographic_order_would_be_wrong(self):
        """Menegaskan natural sort memang memperbaiki urutan string biasa."""
        codes = ['TKRS 10', 'TKRS 2']
        self.assertNotEqual(sorted(codes), sort_standards(codes))
        self.assertEqual(sorted(codes), ['TKRS 10', 'TKRS 2'])
        self.assertEqual(sort_standards(codes), ['TKRS 2', 'TKRS 10'])

    def test_sort_is_stable_and_total(self):
        codes = ['HPK 3', 'HPK 1', 'HPK 2']
        self.assertEqual(sort_standards(codes), ['HPK 1', 'HPK 2', 'HPK 3'])

    def test_key_is_comparable_across_mixed_tokens(self):
        key = natural_sort_key('PP 10.2')
        self.assertIsInstance(key, list)
        self.assertTrue(all(isinstance(part, tuple) for part in key))

    def test_all_fixture_codes_sort_without_error(self):
        data = load_fixture()
        codes = [r['standard_code'] for r in data]
        self.assertEqual(len(codes), 227)
        ordered = sort_standards(codes)
        self.assertEqual(len(ordered), 227)
        self.assertEqual(set(ordered), set(codes))

    def test_mixed_chapter_prefixes_sort_by_number_within_chapter(self):
        codes = ['MFK 10', 'MFK 2', 'AKP 3', 'AKP 1']
        ordered = sort_standards(codes)
        self.assertEqual(ordered, ['AKP 1', 'AKP 3', 'MFK 2', 'MFK 10'])


# ---------------------------------------------------------------------------
# Category EP metrics
# ---------------------------------------------------------------------------
class CategoryEpMetricTests(TestCase):
    def setUp(self):
        fw = make_framework()
        self.cat = make_category('TKRS', 'Tata Kelola', 1, fw)
        self.other = make_category('KPS', 'KPatient', 2, fw)
        self.unit = UnitKerja.objects.create(code='U1', name='Unit 1')
        self.cat_items = []
        for i in range(3):
            item = StandardItem.objects.create(
                category=self.cat, code=f'TKRS 1 EP {i}', sub_standard='TKRS 1',
                description='d')
            self.cat_items.append(item)
        StandardItem.objects.create(
            category=self.other, code='KPS 1 EP 0', sub_standard='KPS 1', description='d')

    def test_ep_total_counts_only_own_items(self):
        self.assertEqual(self.cat.ep_total, 3)
        self.assertEqual(self.other.ep_total, 1)

    def test_ep_selesai_zero_without_records(self):
        self.assertEqual(self.cat.ep_selesai, 0)

    def test_ep_selesai_counts_positive_scores_only(self):
        QualityRecord.objects.create(standard_item=self.cat_items[0], unit=self.unit, score=10)
        QualityRecord.objects.create(standard_item=self.cat_items[1], unit=self.unit, score=0)
        cat = Category.objects.get(pk=self.cat.pk)
        self.assertEqual(cat.ep_selesai, 1)

    def test_ep_coverage_pct_uses_target(self):
        cat = Category.objects.get(pk=self.cat.pk)
        cat.target_ep_count = 4
        self.assertEqual(cat.ep_coverage_pct, 75)

    def test_ep_coverage_pct_zero_when_no_target(self):
        self.assertEqual(self.cat.ep_coverage_pct, 0)

    def test_ep_coverage_pct_100_when_complete(self):
        cat = Category.objects.get(pk=self.cat.pk)
        cat.target_ep_count = 3
        self.assertEqual(cat.ep_coverage_pct, 100)

    def test_max_possible_score_still_consistent(self):
        self.assertEqual(self.cat.max_possible_score, 30)


# ---------------------------------------------------------------------------
# Import fills target_ep_count
# ---------------------------------------------------------------------------
class TargetEpCountImportTests(TestCase):
    def test_import_sets_target_ep_count_per_category(self):
        from django.core.management import call_command
        call_command('import_instrumen_2024', '--dry-run')

        # Dry-run tidak boleh menulis; jalankan sungguhan di DB test.
        call_command('import_instrumen_2024')
        cats = Category.objects.exclude(target_ep_count=0)
        self.assertTrue(cats.exists(), 'import harus mengisi target_ep_count')
        total = sum(c.target_ep_count for c in cats)
        self.assertEqual(total, 800)

    def test_imported_total_matches_fixture(self):
        from django.core.management import call_command
        call_command('import_instrumen_2024')
        data = load_fixture()
        expected = {}
        for rec in data:
            expected[rec['bab_code']] = expected.get(rec['bab_code'], 0) + rec['ep_count']
        for bab, count in expected.items():
            cat = Category.objects.get(code=bab)
            self.assertEqual(cat.target_ep_count, count, f'{bab} target tidak cocok')
            self.assertEqual(cat.ep_total, count, f'{bab} EP terpasang tidak cocok')


# ---------------------------------------------------------------------------
# ep_list pagination
# ---------------------------------------------------------------------------
class EpListPaginationTests(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command('import_instrumen_2024')
        self.user = self._make_user()

    def _make_user(self):
        from django.contrib.auth.models import User
        u = User.objects.create_user('ep_pag', password='x')
        u.is_staff = True
        u.save()
        return u

    def test_page_size_is_bounded(self):
        self.assertLessEqual(EP_PAGE_SIZE, 100)

    def test_first_page_is_truncated(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('akreditasi:ep_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['items']), EP_PAGE_SIZE)
        self.assertEqual(resp.context['total_matched'], 800)

    def test_paginator_has_16_pages_for_800_ep(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('akreditasi:ep_list'))
        self.assertEqual(resp.context['page'].paginator.num_pages, 16)

    def test_last_page_has_remainder(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('akreditasi:ep_list'), {'page': 16})
        self.assertEqual(len(resp.context['items']), 800 - (15 * EP_PAGE_SIZE))

    def test_out_of_range_page_falls_back_to_last(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('akreditasi:ep_list'), {'page': 999})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['page'].number, 16)

    def test_invalid_page_param_does_not_500(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('akreditasi:ep_list'), {'page': 'abc'})
        self.assertEqual(resp.status_code, 200)

    def test_no_ep_duplicated_across_pages(self):
        self.client.force_login(self.user)
        seen = []
        for p in range(1, 17):
            resp = self.client.get(reverse('akreditasi:ep_list'), {'page': p})
            seen.extend(i.code for i in resp.context['items'])
        self.assertEqual(len(seen), 800)
        self.assertEqual(len(set(seen)), 800)

    def test_filter_reduces_total(self):
        self.client.force_login(self.user)
        tkrs = Category.objects.get(code='TKRS')
        resp = self.client.get(reverse('akreditasi:ep_list'), {'cat': str(tkrs.id)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_matched'], 71)

    def test_search_filter_works(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('akreditasi:ep_list'), {'q': 'EP a'})
        self.assertEqual(resp.status_code, 200)
        self.assertLess(resp.context['total_matched'], 800)

    def test_sub_list_is_scoped_to_selected_category(self):
        self.client.force_login(self.user)
        tkrs = Category.objects.get(code='TKRS')
        resp = self.client.get(reverse('akreditasi:ep_list'), {'cat': str(tkrs.id)})
        subs = list(resp.context['sub_list'])
        self.assertTrue(subs)
        for s in subs:
            self.assertTrue(s.startswith('TKRS'), f'{s} bukan milik TKRS')

    def test_sub_list_all_categories_when_not_filtered(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('akreditasi:ep_list'))
        self.assertEqual(len(resp.context['sub_list']), 227)

    def test_sub_list_is_naturally_sorted(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('akreditasi:ep_list'))
        subs = list(resp.context['sub_list'])
        self.assertEqual(subs, sort_standards(subs))
        idx_2 = subs.index('PPI 2')
        idx_10 = subs.index('PPI 10')
        self.assertLess(idx_2, idx_10)


# ---------------------------------------------------------------------------
# Matriks PDCA sub-standard ordering
# ---------------------------------------------------------------------------
class MatriksPdcaSortTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('matriks_user', password='x')
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def test_sub_standards_naturally_sorted(self):
        resp = self.client.get(reverse('akreditasi:matriks_pdca'))
        self.assertEqual(resp.status_code, 200)
        subs = list(resp.context['sub_standards'])
        self.assertTrue(subs)
        self.assertEqual(subs, sort_standards(subs))

    def test_pkpo_3_precedes_pkpo_31(self):
        fw = make_framework()
        cat = make_category('PKPO', 'PKPO', 99, fw)
        for code, sub in (('PKPO 3 EP 0', 'PKPO 3'),
                          ('PKPO 3.1 EP 0', 'PKPO 3.1'),
                          ('PKPO 3.2 EP 0', 'PKPO 3.2')):
            StandardItem.objects.create(category=cat, code=code, sub_standard=sub,
                                        description='d')
        resp = self.client.get(reverse('akreditasi:matriks_pdca'), {'cat': str(cat.id)})
        subs = list(resp.context['sub_standards'])
        self.assertEqual(subs, ['PKPO 3', 'PKPO 3.1', 'PKPO 3.2'])


# ---------------------------------------------------------------------------
# Sidebar / dashboard counter wiring
# ---------------------------------------------------------------------------
class SidebarCounterTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('sb_user', password='x')
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def test_sidebar_renders_ep_counters(self):
        fw = make_framework()
        cat = make_category('TKRS', 'Tata Kelola', 1, fw)
        StandardItem.objects.create(category=cat, code='TKRS 1 EP 0',
                                    sub_standard='TKRS 1', description='d')
        resp = self.client.get(reverse('akreditasi:dashboard'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('/1 EP', html)

    def test_context_processor_precomputes_ep_values(self):
        from akreditasi.context_processors import sidebar_context
        fw = make_framework()
        cat = make_category('TKRS', 'Tata Kelola', 1, fw)
        StandardItem.objects.create(category=cat, code='TKRS 1 EP 0',
                                    sub_standard='TKRS 1', description='d')
        ctx = sidebar_context(self._fake_request())
        cats = ctx['sidebar_categories']
        self.assertTrue(cats)
        self.assertEqual(cats[0].ep_total, 1)
        self.assertEqual(cats[0].ep_selesai, 0)

    def _fake_request(self):
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.user = self.user
        return req
