import unittest

from akreditasi.starkes_sources import extract_ep_items, parse_decree_pages, extract_survey_cells


class FullTextExtractionTests(unittest.TestCase):
    def test_preserves_the_full_description_beyond_preview_limits(self):
        description = 'Rumah sakit memastikan ' + ('pelayanan aman dan bermutu ' * 30) + 'terdokumentasi.'
        items = extract_ep_items('Elemen Penilaian KPS 10\na) ' + description)
        self.assertEqual(items[0]['description'], description)

    def test_chapter_introduction_is_not_part_of_last_ep(self):
        block = (
            'Elemen Penilaian AKP 6\n'
            'a) Kriteria transportasi memenuhi keselamatan pasien.\n'
            '2. Hak Pasien dan Keterlibatan Keluarga (HPK)\n'
            'Gambaran Umum\nHak pasien dilindungi oleh undang-undang.\n'
        )
        items = extract_ep_items(block)
        self.assertEqual(items[0]['description'], 'Kriteria transportasi memenuhi keselamatan pasien.')

    def test_removes_page_furniture_but_keeps_continuation(self):
        block = (
            'Elemen Penilaian KPS 10\n'
            'a) Pemeriksaan elektrokardiogram\n'
            'KEMENTERIAN KESEHATAN\njdih.kemkes.go.id\n- 68 -\n'
            '(EKG), elektroensefalogram (EEG), dan elektromiogram (EMG).\n'
        )
        items = extract_ep_items(block)
        self.assertEqual(
            items[0]['description'],
            'Pemeriksaan elektrokardiogram (EKG), elektroensefalogram (EEG), dan elektromiogram (EMG).',
        )

    def test_does_not_guess_rdwos_from_letters_in_decree_prose(self):
        items = extract_ep_items('Elemen Penilaian PMKP 11\na) Analisis menggunakan R dan skala D.')
        self.assertEqual(items[0]['evidence_types'], [])

    def test_stops_before_next_standard_without_truncating(self):
        items = extract_ep_items(
            'Elemen Penilaian TKRS 1\na) Pemilik menetapkan kebijakan.\n'
            'b. Akuntabilitas Direktur Rumah Sakit\n'
            '1) Standar TKRS 2\nDirektur bertanggung jawab.\n'
        )
        self.assertEqual(items[0]['description'], 'Pemilik menetapkan kebijakan.')


class DecreePageTests(unittest.TestCase):
    def test_group_and_closing_chapters_are_not_ep_continuations(self):
        for heading in ['C. Kelompok Sasaran Keselamatan Pasien', 'D. Program Nasional', 'BAB IV\nPENUTUP']:
            with self.subTest(heading=heading):
                result = parse_decree_pages([{'page': 355, 'text': (
                    'Elemen Penilaian PROGNAS 6.1\n1) Rumah sakit melakukan evaluasi.\n'
                    + heading + '\nNaskah pengantar bukan persyaratan EP.'
                )}])
                self.assertEqual(result['items'][0]['description'], 'Rumah sakit melakukan evaluasi.')

    def test_nonsequential_source_labels_are_flagged_never_renumbered(self):
        result = parse_decree_pages([{'page': 21, 'text': (
            'Elemen Penilaian TKRS 2\na) Ketentuan pertama.\nb) Ketentuan kedua.\ne) Ketentuan sesuai label sumber.'
        )}])
        self.assertEqual([i['letter'] for i in result['items']], ['a', 'b', 'e'])
        self.assertEqual(result['anomalies'][0]['kind'], 'nonsequential_ep_labels')

    def test_range_with_hingga_does_not_split_a_requirement(self):
        result = parse_decree_pages([{'page': 53, 'text': (
            'Elemen Penilaian KPS 2\na) Setiap staf memiliki uraian tugas.\n'
            'b) Tenaga kesehatan dalam poin a) hingga\nd) dalam maksud dan tujuan memiliki uraian tugas yang sesuai.'
        )}])
        self.assertEqual([item['letter'] for item in result['items']], ['a', 'b'])
        self.assertIn('hingga d)', result['items'][1]['description'])

    def test_range_endpoint_on_next_line_is_not_a_new_ep(self):
        result = parse_decree_pages([{'page': 143, 'text': (
            'Elemen Penilaian PMKP 8\na) Kejadian sentinel meliputi poin a –\n'
            'o) dalam bagian maksud dan tujuan.\nb) Tim melakukan investigasi.'
        )}])
        self.assertEqual([item['letter'] for item in result['items']], ['a', 'b'])
        self.assertIn('a – o)', result['items'][0]['description'])

    def test_letter_range_wrapped_on_its_own_line_is_not_a_new_ep(self):
        result = parse_decree_pages([{'page': 73, 'text': (
            'Elemen Penilaian KPS 11\na) Direktur mempertimbangkan poin\n'
            'a) – j) dalam maksud dan tujuan.\nb) Ada bukti penetapan.'
        )}])
        self.assertEqual([item['letter'] for item in result['items']], ['a', 'b'])
        self.assertIn('a) – j)', result['items'][0]['description'])

    def test_lettered_dotted_eps_are_not_mistaken_for_section_headings(self):
        result = parse_decree_pages([{'page': 274, 'text': (
            'Elemen Penialaian PAP 2.4\na. Rumah sakit menetapkan regulasi.\n'
            'b. Rumah sakit melaksanakan skrining.\nc. Rumah sakit melatih staf.'
        )}])
        self.assertEqual([item['letter'] for item in result['items']], ['a', 'b', 'c'])

    def test_page_layout_indentation_does_not_drop_continuing_eps(self):
        result = parse_decree_pages([
            {'page': 1, 'text': 'Elemen Penilaian AKP 6\na) Kriteria transportasi.', 'layout': 'Elemen Penilaian AKP 6\n    a) Kriteria transportasi.'},
            {'page': 2, 'text': 'b) Kendaraan dipelihara.\nc) Kerja sama dievaluasi.', 'layout': '                b) Kendaraan dipelihara.\n                c) Kerja sama dievaluasi.'},
        ])
        self.assertEqual([item['letter'] for item in result['items']], ['a', 'b', 'c'])

    def test_wrapped_reference_to_maksud_dan_tujuan_does_not_end_an_ep(self):
        result = parse_decree_pages([{'page': 98, 'text': (
            'Elemen Penilaian MFK 3\na) Program meliputi poin a) - c) pada\n'
            'maksud dan tujuan.\nb) Rumah sakit mengintegrasikan program.'
        )}])
        self.assertEqual([item['letter'] for item in result['items']], ['a', 'b'])
        self.assertTrue(result['items'][0]['description'].endswith('maksud dan tujuan.'))

    def test_dotted_topic_before_next_standard_is_not_an_extra_ep(self):
        result = parse_decree_pages([{'page': 275, 'text': (
            'Elemen Penialaian PAP 2.4\na. Rumah sakit menetapkan regulasi.\n'
            'b. Rumah sakit melaksanakan skrining.\nf. Pelayanan Darah\n'
            '1) Standar PAP 3\nRumah sakit melaksanakan pelayanan darah.'
        )}])
        self.assertEqual([item['letter'] for item in result['items']], ['a', 'b'])

    def test_recognizes_source_heading_spelling_and_punctuation_variants(self):
        variants = [
            ('Elemen Penialian PPI 1.1', 'PPI 1.1'),
            ('Elemen Penialaian PAP 2.4', 'PAP 2.4'),
            ('Elemen Penilaian dari PP 3.8', 'PP 3.8'),
            ('Elemen Penilaian PPI .4.1', 'PPI 4.1'),
        ]
        for heading, expected in variants:
            with self.subTest(heading=heading):
                result = parse_decree_pages([{'page': 10, 'text': heading + '\na) Ketentuan wajib dilaksanakan.'}])
                self.assertEqual(result['items'][0]['standard_code'], expected)
                self.assertEqual(result['items'][0]['source_pages'], [10])

    def test_preserves_numeric_ep_with_nested_lettered_requirements(self):
        result = parse_decree_pages([{
            'page': 326,
            'text': 'Elemen Penilaian SKP 1\n1) Ketentuan mencakup:\n    a) identitas;\n    b) pelayanan.\n2) Pasien diidentifikasi.',
        }])
        self.assertEqual([item['letter'] for item in result['items']], ['1', '2'])
        self.assertIn('a) identitas;', result['items'][0]['description'])

    def test_empty_heading_is_an_anomaly_not_a_fabricated_ep(self):
        result = parse_decree_pages([{'page': 10, 'text': 'Elemen Penilaian KPS 1\n1) Standar KPS 2\nUraian standar.'}])
        self.assertEqual(result['items'], [])
        self.assertTrue(result['anomalies'])

    def test_keeps_page_provenance_across_continuation_and_stops_at_chapter(self):
        result = parse_decree_pages([
            {'page': 1, 'text': 'Elemen Penilaian AKP 6\na) Ketentuan transportasi'},
            {'page': 2, 'text': 'harus diterapkan.\n2. Meningkatkan Komunikasi yang Efektif\na. Standar SKP 2'},
        ])
        self.assertEqual(result['items'][0]['description'], 'Ketentuan transportasi harus diterapkan.')
        self.assertEqual(result['items'][0]['source_pages'], [1, 2])


class SurveyCellTests(unittest.TestCase):
    def test_vertically_centered_marker_owns_the_entire_separate_type_cell(self):
        self.rectangles[4] = (300, 460, 20, 40)
        self.rectangles.append((300, 400, 20, 60))
        self.fragments[4]['y'] = 465
        self.fragments[5]['y'] = 465
        self.fragments.append({'x': 325, 'y': 485, 'text': 'Dokumen penetapan.'})
        result = extract_survey_cells(113, self.rectangles, self.fragments)
        evidence = result['rows'][0]['evidence']
        self.assertEqual([e['category_type'] for e in evidence], ['R', 'W'])
        self.assertTrue(evidence[0]['instruction'].startswith('Dokumen penetapan.'))

    def test_inset_body_clipping_keeps_hanging_ep_label(self):
        self.rectangles[3] = (120, 400, 180, 100)
        result = extract_survey_cells(214, self.rectangles, self.fragments)
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(result['rows'][0]['letter'], 'a')
        self.assertEqual(result['rows'][0]['evidence'][0]['category_type'], 'R')

    def setUp(self):
        self.rectangles = [
            (100, 500, 200, 20), (300, 500, 180, 20), (480, 500, 80, 20),
            (100, 400, 200, 100), (300, 400, 20, 100),
            (320, 400, 160, 100), (480, 400, 80, 100),
        ]
        self.fragments = [
            {'x': 150, 'y': 510, 'text': 'Elemen Penilaian'},
            {'x': 350, 'y': 510, 'text': 'Kelengkapan Bukti'},
            {'x': 500, 'y': 510, 'text': 'Skoring'},
            {'x': 105, 'y': 480, 'text': 'a) Rumah sakit menetapkan regulasi.'},
            {'x': 305, 'y': 480, 'text': 'R'},
            {'x': 325, 'y': 480, 'text': 'Penetapan peraturan rumah sakit.'},
            {'x': 305, 'y': 450, 'text': 'W'},
            {'x': 325, 'y': 450, 'text': 'Direktur dan staf rumah sakit.'},
            {'x': 500, 'y': 480, 'text': '10'},
            {'x': 500, 'y': 450, 'text': '0'},
        ]

    def test_uses_table_geometry_to_separate_ep_evidence_and_scoring(self):
        result = extract_survey_cells(10, self.rectangles, self.fragments)
        self.assertEqual(len(result['rows']), 1)
        row = result['rows'][0]
        self.assertEqual(row['description'], 'Rumah sakit menetapkan regulasi.')
        self.assertEqual(row['letter'], 'a')
        self.assertEqual([entry['category_type'] for entry in row['evidence']], ['R', 'W'])
        self.assertEqual(row['evidence'][0]['instruction'], 'Penetapan peraturan rumah sakit.')
        self.assertEqual(row['source_pages'], [10])
        self.assertNotIn('10', row['description'])

    def test_letters_inside_evidence_column_are_not_new_eps(self):
        self.fragments.append({'x': 325, 'y': 465, 'text': 'b) Dokumen pendukung dan hasil evaluasi.'})
        result = extract_survey_cells(10, self.rectangles, self.fragments)
        self.assertEqual(len(result['rows']), 1)
        self.assertIn('b) Dokumen pendukung', result['rows'][0]['evidence'][0]['instruction'])

    def test_page_continuation_is_retained_without_inventing_a_label(self):
        self.fragments[3]['text'] = 'lanjutan uraian EP sebelumnya.'
        result = extract_survey_cells(11, self.rectangles, self.fragments)
        self.assertIsNone(result['rows'][0]['letter'])
        self.assertEqual(result['rows'][0]['description'], 'lanjutan uraian EP sebelumnya.')

    def test_separate_blank_type_header_does_not_hide_rdwos_markers(self):
        self.rectangles[1] = (320, 500, 160, 20)
        self.rectangles.append((300, 500, 20, 20))
        result = extract_survey_cells(10, self.rectangles, self.fragments)
        self.assertEqual([entry['category_type'] for entry in result['rows'][0]['evidence']], ['R', 'W'])

    def test_leading_continued_evidence_is_not_attributed_to_a_new_marker(self):
        self.fragments[4]['y'] = 465
        self.fragments[5]['y'] = 465
        self.fragments.append({'x': 325, 'y': 485, 'text': 'lanjutan bukti pada halaman sebelumnya.'})
        result = extract_survey_cells(10, self.rectangles, self.fragments)
        evidence = result['rows'][0]['evidence']
        self.assertIsNone(evidence[0]['category_type'])
        self.assertEqual(evidence[0]['instruction'], 'lanjutan bukti pada halaman sebelumnya.')
        self.assertNotIn('lanjutan', evidence[1]['instruction'])

    def test_adjacent_font_runs_do_not_insert_spaces_inside_words(self):
        self.fragments[5]['text'] = 'Penetapan oleh pemili'
        self.fragments.append({'x': 450, 'y': 480, 'text': 'k.'})
        result = extract_survey_cells(10, self.rectangles, self.fragments)
        self.assertEqual(result['rows'][0]['evidence'][0]['instruction'], 'Penetapan oleh pemilik.')

    def test_missing_table_structure_is_reported_instead_of_guessing(self):
        result = extract_survey_cells(10, [], self.fragments)
        self.assertEqual(result['rows'], [])
        self.assertTrue(result['anomalies'])


if __name__ == '__main__':
    unittest.main()
