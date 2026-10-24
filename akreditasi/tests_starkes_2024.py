"""STARKES 2024 catalogue: parser correctness and safe replacement."""
from django.test import SimpleTestCase, TestCase

from akreditasi.management.commands.import_instrumen_2024 import (
    _extract_ep_items,
    BAB_META,
    FRAMEWORK_NAME_2024,
)
from akreditasi.models import (
    Category,
    Framework,
    QualityRecord,
    StandardItem,
    UnitKerja,
)


class EpExtractionTests(SimpleTestCase):
    def test_lettered_items_are_extracted(self):
        block = (
            'Elemen Penilaian TKRS 1\n'
            'a) Representasi pemilik dipilih oleh pemilik.\n'
            'b) Tanggung jawab dan wewenang dijelaskan.\n'
        )

        items = _extract_ep_items(block)

        self.assertEqual([i['letter'] for i in items], ['a', 'b'])

    def test_repeated_letter_stops_the_block(self):
        """The next standard's EP list must not be absorbed (MFK 3 → MFK 4)."""
        block = (
            'Elemen Penilaian MFK 3\n'
            'a) Keselamatan rumah sakit diterapkan.\n'
            'b) K3 staf diintegrasikan.\n'
            'a) Keamanan lingkungan diterapkan.\n'
            'b) Pemantauan keamanan berkala.\n'
        )

        items = _extract_ep_items(block)

        self.assertEqual([i['letter'] for i in items], ['a', 'b'])
        self.assertIn('Keselamatan', items[0]['description'])

    def test_prose_enumeration_is_not_an_ep(self):
        block = (
            'Elemen Penilaian MFK 4\n'
            'a) Rumah sakit menerapkan proses pengelolaan keamanan.\n'
            'e) pada maksud dan tujuan.\n'
            'b) Pengkajian risiko keamanan tahunan.\n'
        )

        items = _extract_ep_items(block)

        self.assertEqual([i['letter'] for i in items], ['a', 'b'])

    def test_dotted_numbering_is_supported(self):
        block = (
            'Elemen Penilaian Prognas 6\n'
            '1. Regulasi pengendalian resistansi antimikroba ditetapkan.\n'
            '2. Komite/tim PRA dibentuk.\n'
        )

        items = _extract_ep_items(block)

        self.assertEqual([i['letter'] for i in items], ['1', '2'])

    def test_all_2024_codes_have_metadata(self):
        self.assertIn('PROGNAS', BAB_META)
        self.assertIn('SKP', BAB_META)
        self.assertEqual(len(BAB_META), 16)


class ReplaceCatalogueTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Ganti', code='HC-GANTI')
        self.old = Framework.objects.create(
            name='STARKES Edisi 2022 / Kemenkes RI', version='2022', edition='2022',
            lifecycle='ARCHIVED', is_active=False,
        )
        old_cat = Category.objects.create(
            framework=self.old, code='TKRS', name='Tata Kelola', order=1
        )
        self.old_item = StandardItem.objects.create(
            category=old_cat, sub_standard='TKRS 1', sub_title='Lama',
            code='TKRS 1 EP a', description='Butir lama', order=1,
        )
        self.record = QualityRecord.objects.create(
            standard_item=self.old_item, unit=self.unit, score=10,
            assessment_state='ASSESSED',
        )

    def test_active_returns_the_flagged_framework(self):
        new = Framework.objects.create(
            name=FRAMEWORK_NAME_2024, version='2024', edition='2024',
            lifecycle='ACTIVE', is_active=True,
        )
        self.assertEqual(Framework.active(), new)

    def test_old_assessment_row_preserved_not_repointed(self):
        """Archive-preservation contract: original QualityRecord PK/FK/payload
        unchanged; a 2024 successor assessment is a DISTINCT row with lineage."""
        self.old_item.code = 'TKRS 1 EP a [2022]'
        self.old_item.save(update_fields=['code'])
        new = Framework.objects.create(
            name=FRAMEWORK_NAME_2024, version='2024', edition='2024',
            lifecycle='ACTIVE', is_active=True,
        )
        new_cat = Category.objects.create(
            framework=new, code='TKRS', name='Tata Kelola 2024', order=1
        )
        new_item = StandardItem.objects.create(
            category=new_cat, sub_standard='TKRS 1', sub_title='',
            code='TKRS 1 EP a', description='Butir baru', order=1,
        )
        target_record = QualityRecord.objects.create(
            standard_item=new_item, unit=self.unit, score=0,
            assessment_state='UNASSESSED',
        )
        from akreditasi.models import TautanAsesmenLintasEdisi, PemetaanEdisi
        mapping = PemetaanEdisi.objects.create(
            source_framework=self.old, source_item_id=self.old_item.pk,
            source_code='TKRS 1 EP a', source_text_hash='x',
            target_framework=new, target_item_id=new_item.pk,
            target_code='TKRS 1 EP a', target_text_hash='y',
            classification='UNCHANGED', score_policy='CARRY_ASSESSMENT',
            reason='owner approved unchanged content',
            approved=True,
        )
        TautanAsesmenLintasEdisi.objects.create(
            source_record=self.record, target_record=target_record,
            mapping=mapping, state='UNASSESSED',
        )
        # Original row preserved, never repointed.
        self.record.refresh_from_db()
        self.assertEqual(self.record.standard_item, self.old_item)
        self.assertEqual(self.record.score, 10)
        self.assertEqual(self.record.assessment_state, 'ASSESSED')
        # Distinct target assessment exists with lineage.
        self.assertEqual(target_record.standard_item, new_item)
        self.assertEqual(target_record.assessment_state, 'UNASSESSED')
        self.assertEqual(
            TautanAsesmenLintasEdisi.objects.filter(
                source_record=self.record, target_record=target_record
            ).count(), 1
        )
        self.old.refresh_from_db()
        self.assertEqual(self.old.lifecycle, 'ARCHIVED')
        self.assertFalse(self.old.is_active)
