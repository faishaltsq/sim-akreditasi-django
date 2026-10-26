"""Source preparation rehearsal; intentionally does not exercise catalogue activation."""
import json
from pathlib import Path

from django.test import TestCase

from akreditasi.models import Category, EvidenceFile, EvidenceReq, Framework, QualityRecord, StandardItem, UnitKerja
from akreditasi.starkes_source_fixture import reconcile_sources


class SourcePreparationDatabaseIsolationTests(TestCase):
    def test_preparation_preserves_edition_ids_scores_evidence_and_history(self):
        current = Framework.objects.create(name='Source rehearsal active', version='2024', edition='2024',
                                           source_type='STANDARD_DECREE', lifecycle='ACTIVE', is_active=True)
        archived = Framework.objects.create(name='Source rehearsal archive', version='2022', edition='2022',
                                            source_type='ARCHIVE', lifecycle='ARCHIVED', is_active=False)
        unit = UnitKerja.objects.create(name='Source rehearsal unit', code='SOURCE-TEST')
        for framework in (current, archived):
            category = Category.objects.create(framework=framework, code='TKRS', name='Tata Kelola', order=1)
            item = StandardItem.objects.create(category=category, code='TKRS 1 EP a', sub_standard='TKRS 1',
                                               sub_title='', description='Existing assessed requirement.', order=1)
            QualityRecord.objects.create(standard_item=item, unit=unit, score=5, baseline_data='Preserved baseline',
                                         eval_notes='Preserved reviewer note', action_plan='Preserved action plan')
            requirement = EvidenceReq.objects.create(standard_item=item, category_type='D', title='Existing evidence', is_mandatory=True)
            EvidenceFile.objects.create(requirement=requirement, file_name='existing-evidence.pdf',
                                        file_url='https://example.test/existing-evidence.pdf', version=3, status='VALID')
        models = (Framework, Category, StandardItem, QualityRecord, EvidenceReq, EvidenceFile)
        before = {model.__name__: list(model.objects.order_by('pk').values()) for model in models}
        path = Path(__file__).resolve().parent.parent / 'fixtures/standar_akreditasi_2024.sources.json'
        artifact = json.loads(path.read_text(encoding='utf-8'))
        decree = {'items': artifact['decree_items'], 'anomalies': artifact['parser_anomalies']['decree']}
        survey = {'items': artifact['survey_items'], 'anomalies': artifact['parser_anomalies']['survey']}
        with self.assertNumQueries(0):
            first = reconcile_sources(decree, survey)
            second = reconcile_sources(decree, survey)
        self.assertEqual(first, second)
        self.assertFalse(first['production_ready'])
        after = {model.__name__: list(model.objects.order_by('pk').values()) for model in models}
        self.assertEqual(before, after)
        self.assertEqual(StandardItem.objects.filter(code='TKRS 1 EP a').count(), 2)
        self.assertEqual(QualityRecord.objects.filter(score=5).count(), 2)
        self.assertEqual(EvidenceFile.objects.filter(version=3, status='VALID').count(), 2)
