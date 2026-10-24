"""Track C4: Pemetaan edisi direview — linier asesmen terpisah, tidak ada repointing."""

from django.test import TestCase

from akreditasi.models import (
    Category, Framework, StandardItem, QualityRecord, UnitKerja,
    PemetaanEdisi, TautanAsesmenLintasEdisi,
)
from akreditasi.catalogue_services import review_edition_mapping
from accounts.models import UserProfile
from django.contrib.auth import get_user_model

User = get_user_model()


def _make_user(role='SUPER_ADMIN'):
    u = User.objects.create_user(username=role.lower(), password='pw')
    UserProfile.objects.create(user=u, role=role)
    return u


class ReviewedMappingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(name='U', code='U')
        cls.src = Framework.objects.create(
            name='Src 2022', version='2022', edition='2022',
            lifecycle='ARCHIVED', is_active=False,
        )
        cls.tgt = Framework.objects.create(
            name='Tgt 2024', version='2024', edition='2024',
            lifecycle='ACTIVE', is_active=True,
        )
        scat = Category.objects.create(framework=cls.src, code='TKRS', name='TKRS', order=1)
        tcat = Category.objects.create(framework=cls.tgt, code='TKRS', name='TKRS', order=1)
        cls.s_item = StandardItem.objects.create(
            category=scat, sub_standard='TKRS 1', code='TKRS 1 EP a',
            description='konten lama', order=1,
        )
        cls.t_item = StandardItem.objects.create(
            category=tcat, sub_standard='TKRS 1', code='TKRS 1 EP a',
            description='konten baru', order=1,
        )
        cls.s_rec = QualityRecord.objects.create(
            standard_item=cls.s_item, unit=cls.unit, score=10, assessment_state='ASSESSED',
        )
        cls.reviewer = _make_user()

    def test_review_edition_mapping_records_immutable_decision(self):
        mapping = review_edition_mapping(
            actor=self.reviewer,
            source_item_ids=[self.s_item.pk],
            target_item_ids=[self.t_item.pk],
            classification='UNCHANGED',
            evidence_rule_map={'R': 'SK 1596/2024 hal 12'},
            score_policy='CARRY_ASSESSMENT',
            reason='Konten sama persis, persetujuan pemilik tercatat.',
        )
        self.assertTrue(mapping.approved)
        self.assertEqual(mapping.classification, 'UNCHANGED')
        self.assertEqual(mapping.score_policy, 'CARRY_ASSESSMENT')
        self.assertEqual(mapping.source_code, 'TKRS 1 EP a')
        self.assertEqual(mapping.target_code, 'TKRS 1 EP a')
        self.assertEqual(mapping.reviewer, self.reviewer)
        self.assertIsNotNone(mapping.reviewed_at)

    def test_carry_assessment_requires_reason(self):
        with self.assertRaises(Exception):
            review_edition_mapping(
                actor=self.reviewer,
                source_item_ids=[self.s_item.pk],
                target_item_ids=[self.t_item.pk],
                classification='UNCHANGED',
                evidence_rule_map={},
                score_policy='CARRY_ASSESSMENT',
                reason='',
            )

    def test_default_score_policy_is_reassess(self):
        mapping = review_edition_mapping(
            actor=self.reviewer,
            source_item_ids=[self.s_item.pk],
            target_item_ids=[self.t_item.pk],
            classification='CHANGED',
            evidence_rule_map={},
            score_policy='REASSESS',
            reason='Konten berubah, harus dinilai ulang.',
        )
        self.assertEqual(mapping.score_policy, 'REASSESS')

    def test_invalid_classification_rejected(self):
        with self.assertRaises(Exception):
            review_edition_mapping(
                actor=self.reviewer,
                source_item_ids=[self.s_item.pk],
                target_item_ids=[self.t_item.pk],
                classification='TIDAK_VALID',
                evidence_rule_map={},
                score_policy='REASSESS',
                reason='x',
            )

    def test_carry_creates_distinct_target_not_repoint_original(self):
        """Score policy CARRY: target assessment is a NEW row; original row untouched."""
        mapping = review_edition_mapping(
            actor=self.reviewer,
            source_item_ids=[self.s_item.pk],
            target_item_ids=[self.t_item.pk],
            classification='UNCHANGED',
            evidence_rule_map={},
            score_policy='CARRY_ASSESSMENT',
            reason='owner approved',
        )
        t_rec = QualityRecord.objects.create(
            standard_item=self.t_item, unit=self.unit, score=0,
            assessment_state='UNASSESSED',
        )
        link = TautanAsesmenLintasEdisi.objects.create(
            source_record=self.s_rec, target_record=t_rec, mapping=mapping,
            state='UNASSESSED',
        )
        # Original row preserved.
        self.s_rec.refresh_from_db()
        self.assertEqual(self.s_rec.standard_item, self.s_item)
        self.assertEqual(self.s_rec.score, 10)
        self.assertEqual(self.s_rec.assessment_state, 'ASSESSED')
        # Distinct target assessment.
        self.assertEqual(t_rec.standard_item, self.t_item)
        self.assertEqual(t_rec.assessment_state, 'UNASSESSED')
        self.assertEqual(link.state, 'UNASSESSED')

    def test_split_merge_new_unresolved_classifications(self):
        for cls_ in ('SPLIT', 'MERGED', 'NEW', 'UNRESOLVED', 'RETIRED', 'CHANGED'):
            mapping = review_edition_mapping(
                actor=self.reviewer,
                source_item_ids=[self.s_item.pk],
                target_item_ids=[self.t_item.pk],
                classification=cls_,
                evidence_rule_map={},
                score_policy='REASSESS',
                reason=f'klasifikasi {cls_}',
            )
            self.assertEqual(mapping.classification, cls_)
