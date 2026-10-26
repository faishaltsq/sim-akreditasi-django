import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from akreditasi.starkes_source_fixture import assemble_survey_rows, reconcile_sources


class SurveyAssemblyTests(unittest.TestCase):
    def test_continuation_keeps_the_previous_evidence_type_and_page(self):
        pages = [
            {'page': 10, 'headings': [{'top': 600, 'standard_code': 'TKRS 1', 'kind': 'ep'}], 'rows': [
                {'top': 500, 'letter': 'a', 'description': 'Rumah sakit', 'evidence': [
                    {'category_type': 'D', 'instruction': 'Bukti evaluasi', 'source_pages': [10]},
                ]},
            ]},
            {'page': 11, 'headings': [], 'rows': [
                {'top': 700, 'letter': None, 'description': 'melakukan evaluasi.', 'evidence': [
                    {'category_type': None, 'instruction': 'setiap tahun.', 'source_pages': [11]},
                    {'category_type': 'W', 'instruction': 'Direktur.', 'source_pages': [11]},
                ]},
            ]},
        ]
        result = assemble_survey_rows(pages)
        self.assertEqual(len(result['items']), 1)
        item = result['items'][0]
        self.assertEqual(item['code'], 'TKRS 1 EP a')
        self.assertEqual(item['description'], 'Rumah sakit melakukan evaluasi.')
        self.assertEqual(item['evidence'][0]['instruction'], 'Bukti evaluasi setiap tahun.')
        self.assertEqual(item['evidence'][0]['source_pages'], [10, 11])
        self.assertEqual(item['source_pages'], [10, 11])
        self.assertEqual(item['evidence_types'], ['D', 'W'])

    def test_orphan_continuation_is_reported_not_attached_to_an_invented_ep(self):
        result = assemble_survey_rows([{'page': 2, 'rows': [
            {'top': 600, 'letter': None, 'description': 'lanjutan tanpa induk', 'evidence': []},
        ]}])
        self.assertEqual(result['items'], [])
        self.assertEqual(result['anomalies'][0]['kind'], 'orphan_survey_continuation')

    def test_new_standard_cannot_inherit_a_continuation_from_previous_standard(self):
        result = assemble_survey_rows([
            {'page': 1, 'headings': [{'top': 700, 'standard_code': 'TKRS 1', 'kind': 'ep'}], 'rows': [
                {'top': 600, 'letter': 'a', 'description': 'Ketentuan lama.', 'evidence': []},
            ]},
            {'page': 2, 'headings': [{'top': 700, 'standard_code': 'KPS 1', 'kind': 'standard'}], 'rows': [
                {'top': 600, 'letter': None, 'description': 'Fragmen tidak berlabel.', 'evidence': []},
            ]},
        ])
        self.assertEqual(result['items'][0]['description'], 'Ketentuan lama.')
        self.assertTrue(result['anomalies'])


class SourceReconciliationTests(unittest.TestCase):
    def test_numeric_threshold_punctuation_is_not_discarded_during_alignment(self):
        self.decree['items'][0]['description'] = 'Batas risiko 1.5%.'
        self.survey['items'][0]['description'] = 'Batas risiko 15%.'
        self.assertEqual(reconcile_sources(self.decree, self.survey)['links'], [])

    def setUp(self):
        self.decree = {'items': [{'code': 'TKRS 1 EP a', 'standard_code': 'TKRS 1', 'letter': 'a',
            'description': 'Rumah sakit melakukan evaluasi setiap tahun.', 'source_pages': [19]}], 'anomalies': []}
        self.survey = {'items': [{'survey_key': 'survey:10:1', 'code': 'TKRS 1 EP a', 'standard_code': 'TKRS 1',
            'letter': 'a', 'description': 'Rumah sakit melakukan evaluasi setiap tahun.', 'source_pages': [10],
            'evidence': [{'category_type': 'D', 'instruction': 'Bukti evaluasi tahunan.', 'source_pages': [10]}]}], 'anomalies': []}

    def test_exact_text_links_preserve_both_sources_without_approving_publication(self):
        before = copy.deepcopy((self.decree, self.survey))
        result = reconcile_sources(self.decree, self.survey)
        self.assertEqual(result['links'][0]['decree_code'], 'TKRS 1 EP a')
        self.assertEqual(result['links'][0]['match_method'], 'EXACT_NORMALIZED_TEXT')
        self.assertEqual(result['review_status'], 'PENDING_OWNER_REVIEW')
        self.assertFalse(result['production_ready'])
        self.assertEqual((self.decree, self.survey), before)

    def test_matching_code_with_different_substance_is_not_auto_linked(self):
        self.survey['items'][0]['description'] = 'Rumah sakit melakukan evaluasi setiap bulan.'
        result = reconcile_sources(self.decree, self.survey)
        self.assertEqual(result['links'], [])
        self.assertEqual(result['review_queue'][0]['kind'], 'source_text_diff')
        self.assertEqual(result['review_queue'][0]['suggested_decree_code'], 'TKRS 1 EP a')

    def test_identical_text_under_multiple_codes_requires_identity_disambiguation(self):
        second = copy.deepcopy(self.decree['items'][0])
        second['code'] = 'KPS 1 EP a'
        second['standard_code'] = 'KPS 1'
        self.decree['items'].append(second)
        self.survey['items'][0]['code'] = None
        result = reconcile_sources(self.decree, self.survey)
        self.assertEqual(result['links'], [])
        self.assertEqual(result['review_queue'][0]['kind'], 'ambiguous_exact_text')


class SourceArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parent.parent / 'fixtures/standar_akreditasi_2024.sources.json'
        cls.artifact = json.loads(cls.path.read_text(encoding='utf-8'))
        cls.manifest = json.loads(cls.path.with_suffix('.manifest.json').read_text(encoding='utf-8'))

    def test_manifest_digest_and_inventory_match_the_physical_artifact(self):
        from akreditasi.starkes_source_fixture import artifact_manifest

        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.manifest['artifact_sha256'])
        review_path = self.path.with_suffix('.review.csv')
        self.assertEqual(hashlib.sha256(review_path.read_bytes()).hexdigest(), self.manifest['review_csv_sha256'])
        self.assertEqual(artifact_manifest(self.artifact)['inventory'], self.manifest['inventory'])
        self.assertEqual(len(self.manifest['inventory']['chapters']), 16)
        self.assertGreater(self.manifest['inventory']['evidence_instructions'], 0)
        self.assertFalse(self.artifact['production_ready'])

    def test_links_never_map_different_text_on_code_alone(self):
        from akreditasi.starkes_source_fixture import _fingerprint

        decree = {i['code']: i for i in self.artifact['decree_items']}
        survey = {i['survey_key']: i for i in self.artifact['survey_items']}
        self.assertEqual(len(decree), len(self.artifact['decree_items']))
        self.assertEqual(len(survey), len(self.artifact['survey_items']))
        for link in self.artifact['links']:
            self.assertEqual(_fingerprint(decree[link['decree_code']]['description']),
                             _fingerprint(survey[link['survey_key']]['description']))

    def test_real_full_text_and_chapter_boundaries_are_preserved(self):
        decree = {i['code']: i for i in self.artifact['decree_items']}
        self.assertGreater(len(decree['KPS 10 EP c']['description']), 300)
        self.assertIn('EMG', decree['KPS 10 EP c']['description'])
        self.assertNotIn('Hak Pasien', decree['AKP 6 EP d']['description'])
        self.assertFalse('PMKP 8 EP o' in decree)
        self.assertFalse('KPS 2 EP d' in decree)
        self.assertNotIn('Kelompok Sasaran', decree['KE 7 EP b']['description'])
        self.assertNotIn('Program Nasional', decree['SKP 6.1 EP 3']['description'])
        self.assertNotIn('PENUTUP', decree['PROGNAS 6.1 EP 4']['description'])
        self.assertIn('PPK 6 EP f', decree)

    def test_text_hashes_and_page_provenance_are_valid(self):
        for kind in ('decree', 'survey'):
            count = self.artifact['sources'][kind]['pages']
            for item in self.artifact[kind + '_items']:
                self.assertEqual(hashlib.sha256(item['description'].encode()).hexdigest(), item['description_sha256'])
                self.assertTrue(item['source_pages'])
                self.assertTrue(all(1 <= p <= count for p in item['source_pages']))
                for evidence in item.get('evidence', []):
                    self.assertIn(evidence['category_type'], [None, 'R', 'D', 'W', 'O', 'S'])
                    self.assertTrue(evidence['instruction'])
                    self.assertTrue(all(1 <= p <= count for p in evidence['source_pages']))


class SourceFileTests(unittest.TestCase):
    def test_unrelated_pdf_is_rejected_instead_of_getting_starkes_provenance(self):
        from pypdf import PdfWriter
        from akreditasi.starkes_source_fixture import read_source_pdf

        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            path = Path(temporary) / 'not-starkes.pdf'
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            writer.write(path)
            with self.assertRaisesRegex(ValueError, 'HK.01.07/MENKES/1596/2024'):
                read_source_pdf(path)

    def test_review_csv_has_full_source_text_not_only_codes(self):
        import csv
        import io
        from akreditasi.starkes_source_fixture import render_review_csv

        artifact = json.loads(
            (Path(__file__).resolve().parent.parent / 'fixtures/standar_akreditasi_2024.sources.json').read_text(encoding='utf-8'))
        rows = list(csv.DictReader(io.StringIO(render_review_csv(artifact))))
        self.assertEqual(len(rows), len(artifact['review_queue']) + sum(len(v) for v in artifact['parser_anomalies'].values()))
        self.assertTrue(any(row['decree_text'] and row['survey_text'] for row in rows))
        self.assertTrue(all(row['status'] == 'PENDING_OWNER_REVIEW' for row in rows))


if __name__ == '__main__':
    unittest.main()
