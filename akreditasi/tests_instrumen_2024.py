"""Tests for the STARKES 2024 instrument parser and its golden fixture.

These tests pin the parser's contract rather than its implementation:

* the fixture is reproducible from the PDF and self-consistent;
* every EP's description is free of the contamination the legacy parser
  produced (score tokens, evidence letters, column headers);
* the row geometry is honoured — one EP per ruled band, evidence types and
  score read from their own columns;
* the 16 chapters are all present and every standard carries at least one EP.
"""

import json
import re
import unittest
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from akreditasi import instrumen_2024 as P
from akreditasi.models import Category, EvidenceReq, Framework, StandardItem

FIXTURE = Path(settings.BASE_DIR) / 'fixtures' / 'standar_akreditasi_2024.json'


def load_raw():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class FixtureContractTests(unittest.TestCase):
    """The fixture is the import's source of truth; check its invariants."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.records = load_raw()

    def test_fixture_exists_and_is_a_list(self):
        self.assertTrue(FIXTURE.exists(), f'missing fixture: {FIXTURE}')
        self.assertIsInstance(self.records, list)
        self.assertGreater(len(self.records), 200)

    def test_every_chapter_present(self):
        prefixes = {r['bab_code'] for r in self.records}
        missing = [b for b in P.BAB_ORDER if b not in prefixes]
        self.assertEqual(missing, [], f'chapters missing from fixture: {missing}')

    def test_bab_codes_are_canonical(self):
        # Legacy prefixes must have been normalised, never carried through.
        for legacy in P.LEGACY_ALIASES:
            self.assertNotIn(legacy, {r['bab_code'] for r in self.records})

    def test_standard_code_matches_bab_and_num(self):
        for r in self.records:
            self.assertEqual(r['standard_code'], f"{r['bab_code']} {r['standard_num']}",
                             f"inconsistent record: {r['standard_code']}")

    def test_ep_count_matches_eps(self):
        for r in self.records:
            self.assertEqual(r['ep_count'], len(r['eps']),
                             f"{r['standard_code']}: ep_count mismatch")

    def test_every_standard_has_at_least_one_ep(self):
        empty = [r['standard_code'] for r in self.records if not r['eps']]
        self.assertEqual(empty, [])

    def test_ep_letters_unique_within_standard(self):
        for r in self.records:
            letters = [e['letter'] for e in r['eps']]
            dupes = [l for l, n in Counter(letters).items() if n > 1]
            self.assertEqual(dupes, [], f"{r['standard_code']} duplicate letters {dupes}")

    def test_ep_letters_are_markers(self):
        for r in self.records:
            for ep in r['eps']:
                self.assertRegex(ep['letter'], r'^[a-z]$|^\d{1,2}$',
                                 f"{r['standard_code']}: bad letter {ep['letter']!r}")

    def test_descriptions_are_non_empty(self):
        for r in self.records:
            for ep in r['eps']:
                self.assertTrue(ep['description'].strip(),
                                f"{r['standard_code']} EP {ep['letter']} has no description")

    def test_descriptions_carry_no_score_tokens(self):
        """The legacy parser leaked '10 5 0' into descriptions; that must not recur."""
        bad = []
        for r in self.records:
            for ep in r['eps']:
                if P.TRAILING_SCORE_RE.search(ep['description']):
                    bad.append((r['standard_code'], ep['letter']))
        self.assertEqual(bad, [], f'score contamination: {bad[:10]}')

    def test_descriptions_carry_no_column_headers(self):
        bad = []
        for r in self.records:
            for ep in r['eps']:
                if P.HEADER_LEAK_RE.search(ep['description']):
                    bad.append((r['standard_code'], ep['letter']))
        self.assertEqual(bad, [], f'column-header leak: {bad[:10]}')

    def test_descriptions_do_not_end_with_a_lone_evidence_letter(self):
        # '... oleh pemilik. R' is the signature of the old column mix-up.
        bad = []
        for r in self.records:
            for ep in r['eps']:
                if re.search(r'\s[RWDOS]$', ep['description']):
                    bad.append((r['standard_code'], ep['letter']))
        self.assertEqual(bad, [], f'trailing evidence letter: {bad[:10]}')

    def test_evidence_types_are_rdwos(self):
        for r in self.records:
            for ep in r['eps']:
                for t in ep['evidence_types']:
                    self.assertIn(t, P.EVIDENCE_TYPES,
                                  f"{r['standard_code']} EP {ep['letter']}: {t!r}")

    def test_every_ep_has_an_evidence_type(self):
        missing = [(r['standard_code'], ep['letter'])
                   for r in self.records for ep in r['eps']
                   if not ep['evidence_types']]
        self.assertEqual(missing, [], f'EP without RDWOS marker: {missing[:10]}')

    def test_fixture_records_provenance(self):
        for r in self.records:
            self.assertRegex(r.get('source_pdf_sha256', ''), r'^[0-9a-f]{64}$',
                             f"{r['standard_code']}: missing PDF sha256")

    def test_known_standards_are_present(self):
        # Chapters the legacy fixture had dropped entirely.
        codes = {r['standard_code'] for r in self.records}
        for code in ('PROGNAS 1', 'PROGNAS 6.1', 'SKP 1', 'SKP 6.1',
                     'HPK 1.4', 'PPI 6', 'PAP 1.1', 'MRMIK 1'):
            self.assertIn(code, codes, f'{code} missing from fixture')


class ParserGeometryTests(unittest.TestCase):
    """The parser reads columns from the ruled grid, not from line order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.records = {r['standard_code']: r for r in load_raw()}

    def eps(self, code):
        return {e['letter']: e for e in self.records[code]['eps']}

    def test_score_and_evidence_are_separated_from_description(self):
        """TKRS 1 EP a: description stops at 'Pemilik.'; R and scores are elsewhere."""
        ep = self.eps('TKRS 1')['a']
        self.assertEqual(
            ep['description'],
            'Representasi pemilik/Dewan Pengawas dipilih dan ditetapkan oleh Pemilik.')
        self.assertEqual(ep['evidence_types'], ['R'])

    def test_multiple_evidence_types_in_one_row(self):
        """A band's marker column may hold several RDWOS letters."""
        ep = self.eps('PPI 7')['a']
        self.assertEqual(sorted(ep['evidence_types']), ['D', 'O', 'W'])

    def test_marker_inside_prose_is_not_an_ep_boundary(self):
        """'... meliputi poin a) sampai i) ...' must not split the EP."""
        eps = self.eps('TKRS 1')
        self.assertIn('poin a)', eps['b']['description'])
        # The prose mentions a)..i) but TKRS 1 really has four EPs (a-d), so
        # no phantom e)..i) rows may appear.
        self.assertEqual(sorted(eps), ['a', 'b', 'c', 'd'])

    def test_numeric_row_markers_are_supported(self):
        """SKP and PROGNAS number their EPs 1) 2) 3) instead of a) b) c)."""
        eps = self.eps('SKP 1')
        self.assertEqual(sorted(eps), ['1', '2', '3', '4'])

    def test_row_continuing_across_a_page_break_is_merged(self):
        """MRMIK 7 starts on p171 (EP a) and continues on p172 (EP b)."""
        eps = self.eps('MRMIK 7')
        self.assertEqual(sorted(eps), ['a', 'b'])
        self.assertIn('memadai', eps['b']['description'])
        # EP a must keep only its own sentence, not the continuation's text.
        self.assertNotIn('memadai', eps['a']['description'])

    def test_prognas_chapter_is_parsed(self):
        self.assertEqual(len(self.eps('PROGNAS 1')), 5)

    def test_typographic_variants_do_not_lose_a_table(self):
        """p385 typesets 'Eleman Penilaian' and p84 'Elemen Penelitian'."""
        self.assertIn('3', self.eps('SKP 3'))
        self.assertEqual(len(self.eps('KPS 13')), 3)


class ImportCommandTests(TestCase):
    """The command is idempotent, transactional, and refuses bad input.

    The test database is already seeded by the project's data migrations
    (16 canonical chapters plus a legacy ``IPKP``), so every assertion here is
    relative to the pre-import state rather than to absolute counts.
    """

    def run_import(self, *args):
        call_command('import_instrumen_2024', *args, verbosity=0)

    def test_dry_run_writes_nothing(self):
        before = (Category.objects.count(), StandardItem.objects.count(),
                  EvidenceReq.objects.count())
        call_command('import_instrumen_2024', '--dry-run', verbosity=0)
        after = (Category.objects.count(), StandardItem.objects.count(),
                 EvidenceReq.objects.count())
        self.assertEqual(before, after)

    def test_import_creates_every_standard_in_the_fixture(self):
        call_command('import_instrumen_2024', verbosity=0)
        records = load_raw()
        expected = {f"{r['standard_code']} EP {ep['letter']}"
                    for r in records for ep in r['eps']}
        present = set(StandardItem.objects.values_list('code', flat=True))
        self.assertEqual(expected - present, set())
        for bab in {r['bab_code'] for r in records}:
            self.assertTrue(Category.objects.filter(code=bab).exists(), bab)

    def test_import_is_idempotent(self):
        call_command('import_instrumen_2024', verbosity=0)
        first = (Category.objects.count(), StandardItem.objects.count(),
                 EvidenceReq.objects.count())
        call_command('import_instrumen_2024', verbosity=0)
        second = (Category.objects.count(), StandardItem.objects.count(),
                  EvidenceReq.objects.count())
        self.assertEqual(first, second)

    def test_import_creates_evidence_requirements(self):
        call_command('import_instrumen_2024', verbosity=0)
        item = StandardItem.objects.get(code='PPI 7 EP a')
        types = sorted(item.evidence_reqs.values_list('category_type', flat=True))
        self.assertEqual(types, ['D', 'O', 'W'])

    def test_import_links_each_ep_to_its_chapter(self):
        call_command('import_instrumen_2024', verbosity=0)
        item = StandardItem.objects.get(code='TKRS 1 EP a')
        self.assertEqual(item.category.code, 'TKRS')
        self.assertEqual(item.sub_standard, 'TKRS 1')

    def test_category_filter_limits_scope(self):
        before = set(StandardItem.objects.exclude(
            category__code='TKRS').values_list('code', flat=True))
        call_command('import_instrumen_2024', '--category', 'TKRS', verbosity=0)
        self.assertTrue(StandardItem.objects.filter(category__code='TKRS').exists())
        # Nothing outside TKRS may be touched by a filtered import.
        after = set(StandardItem.objects.exclude(
            category__code='TKRS').values_list('code', flat=True))
        self.assertEqual(before, after)

    def test_category_filter_rejects_unknown_chapter(self):
        with self.assertRaises(CommandError):
            call_command('import_instrumen_2024', '--category', 'NOPE', verbosity=0)

    def test_import_uses_the_2024_framework(self):
        call_command('import_instrumen_2024', verbosity=0)
        fw = Framework.objects.get(name='STARKES Edisi 2024 / Kemenkes RI')
        self.assertEqual(fw.version, '2024')

    def test_missing_fixture_fails_loudly(self):
        with self.assertRaises(CommandError):
            call_command('import_instrumen_2024', '--fixture', 'nope.json', verbosity=0)

    def test_corrupt_fixture_is_rejected(self):
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                         encoding='utf-8') as fh:
            json.dump([{'bab_code': 'TKRS', 'standard_code': 'TKRS 1',
                        'standard_num': '1', 'ep_count': 2, 'eps': []}], fh)
            path = fh.name
        try:
            with self.assertRaises(CommandError):
                call_command('import_instrumen_2024', '--fixture', path, verbosity=0)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_prune_removes_stale_eps(self):
        call_command('import_instrumen_2024', '--category', 'TKRS', verbosity=0)
        StandardItem.objects.create(
            category=Category.objects.get(code='TKRS'), code='TKRS 99 EP z',
            sub_standard='TKRS 99', description='stale', order=999)
        call_command('import_instrumen_2024', '--category', 'TKRS', '--prune', verbosity=0)
        self.assertFalse(StandardItem.objects.filter(code='TKRS 99 EP z').exists())
