"""Track C5: Aktivasi katalog — lock, revalidasi, switch once, rotasi cache."""

from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model

from akreditasi.models import (
    Framework, Category, StandardItem, QualityRecord, UnitKerja,
    SumberKatalog, AktivasiKatalog, PemetaanEdisi,
)
from akreditasi.catalogue import resolve_catalogue
from akreditasi.catalogue_services import stage_catalogue, activate_catalogue
from accounts.models import UserProfile

User = get_user_model()
_user_counter = {'n': 0}


def _make_user(role='SUPER_ADMIN'):
    _user_counter['n'] += 1
    u = User.objects.create_user(
        username=f'u{_user_counter["n"]}_{role.lower()}', password='pw'
    )
    UserProfile.objects.create(user=u, role=role)
    return u


def _make_prev_active(name='STARKES 2022', edition='2022'):
    fw = Framework.objects.create(
        name=name, version=edition, edition=edition,
        lifecycle='ACTIVE', is_active=True, source_hash='prev' * 32,
    )
    cat = Category.objects.create(framework=fw, code='TKRS', name='TKRS', order=1)
    item = StandardItem.objects.create(
        category=cat, sub_standard='TKRS 1', code='TKRS 1 EP a',
        description='lama', order=1,
    )
    unit = UnitKerja.objects.create(name='U', code='U')
    rec = QualityRecord.objects.create(
        standard_item=item, unit=unit, score=10, assessment_state='ASSESSED',
    )
    return fw, item, rec


def _make_validated_candidate(name='Kandidat', edition='2024', source_hash='cand' * 32):
    fw = Framework.objects.create(
        name=name, version=edition, edition=edition,
        lifecycle='VALIDATED', is_active=False, source_hash=source_hash,
    )
    SumberKatalog.objects.create(
        framework=fw, source_path='x.pdf', sha256=source_hash,
        document_type='STANDARD_DECREE', pages=1,
    )
    return fw


class ActivationTests(TestCase):
    def setUp(self):
        cache.clear()
        Framework.objects.filter(lifecycle='ACTIVE').update(
            lifecycle='ARCHIVED', is_active=False)

    def test_stage_catalogue_creates_inactive_draft(self):
        fw = stage_catalogue(
            actor=_make_user(),
            source_manifest={
                'framework_name': 'STARKES 2024 Staging', 'edition': '2024',
                'document_type': 'STANDARD_DECREE',
                'decree_number': 'HK.01.07/MENKES/1596/2024',
                'instrument_type': 'Standar Akreditasi RS',
                'sha256': 'a' * 64, 'pages': 10,
            },
            reviewed_artifact={
                'path': 'fixtures/standar_akreditasi_2024.json', 'digest': 'd' * 64,
            },
        )
        self.assertEqual(fw.lifecycle, 'DRAFT')
        self.assertFalse(fw.is_active)
        self.assertEqual(fw.edition, '2024')

    def test_stage_catalogue_idempotent(self):
        sm = {'edition': '2024', 'document_type': 'STANDARD_DECREE',
              'sha256': 's' * 64, 'pages': 1}
        ra = {'path': 'fixtures/standar_akreditasi_2024.json', 'digest': 'i' * 64}
        fw1 = stage_catalogue(actor=_make_user(), source_manifest=sm, reviewed_artifact=ra)
        fw2 = stage_catalogue(actor=_make_user(), source_manifest=sm, reviewed_artifact=ra)
        self.assertEqual(fw1.pk, fw2.pk)

    def test_stage_catalogue_never_reparents_old_rows(self):
        prev, _, prev_rec = _make_prev_active()
        before = QualityRecord.objects.filter(
            standard_item__category__framework=prev
        ).count()
        stage_catalogue(
            actor=_make_user(),
            source_manifest={'edition': '2024', 'document_type': 'STANDARD_DECREE',
                             'sha256': 'r' * 64, 'pages': 1},
            reviewed_artifact={'path': 'fixtures/standar_akreditasi_2024.json', 'digest': 'r2' * 32},
        )
        after = QualityRecord.objects.filter(
            standard_item__category__framework=prev
        ).count()
        self.assertEqual(before, after)
        prev_rec.refresh_from_db()
        self.assertEqual(prev_rec.score, 10)

    def test_activate_catalogue_switches_once_and_archives_previous(self):
        prev, _, _ = _make_prev_active()
        cand = _make_validated_candidate(source_hash='h' * 64)
        receipt = activate_catalogue(
            actor=_make_user(), framework=cand,
            reviewed_plan_hash='plan' * 16,
            backup_reference='var/backup/backup.sql',
            expected_previous_id=prev.pk,
        )
        self.assertEqual(receipt.status, 'ACTIVE')
        self.assertEqual(receipt.previous_framework, prev)
        prev.refresh_from_db()
        self.assertEqual(prev.lifecycle, 'ARCHIVED')
        self.assertFalse(prev.is_active)
        cand.refresh_from_db()
        self.assertEqual(cand.lifecycle, 'ACTIVE')
        self.assertTrue(cand.is_active)
        self.assertEqual(resolve_catalogue(None), cand)

    def test_activate_catalogue_rejects_wrong_previous_id(self):
        prev, _, _ = _make_prev_active()
        cand = _make_validated_candidate(source_hash='h2' * 32)
        with self.assertRaises(Exception):
            activate_catalogue(
                actor=_make_user(), framework=cand,
                reviewed_plan_hash='p', backup_reference='b',
                expected_previous_id=999999,
            )
        prev.refresh_from_db()
        self.assertTrue(prev.is_active)
        cand.refresh_from_db()
        self.assertEqual(cand.lifecycle, 'VALIDATED')

    def test_activation_receipt_immutable_metadata(self):
        prev, _, _ = _make_prev_active()
        cand = _make_validated_candidate(source_hash='h3' * 32)
        receipt = activate_catalogue(
            actor=_make_user(), framework=cand,
            reviewed_plan_hash='plan-hash',
            backup_reference='var/backup/backup.sql',
            expected_previous_id=prev.pk,
        )
        self.assertEqual(receipt.plan_hash, 'plan-hash')
        self.assertEqual(receipt.backup_reference, 'var/backup/backup.sql')
        self.assertIsNotNone(receipt.run_metadata)
        self.assertEqual(receipt.run_metadata['previous_framework_id'], prev.pk)
        prev.refresh_from_db()
        self.assertEqual(prev.lifecycle, 'ARCHIVED')

    def test_previous_active_remains_usable_after_failed_activation(self):
        prev, _, _ = _make_prev_active()
        cand = _make_validated_candidate(source_hash='h4' * 32)
        with self.assertRaises(Exception):
            activate_catalogue(
                actor=_make_user(), framework=cand,
                reviewed_plan_hash='p', backup_reference='b',
                expected_previous_id=999999,
            )
        prev.refresh_from_db()
        self.assertEqual(prev.lifecycle, 'ACTIVE')
        self.assertTrue(prev.is_active)
        self.assertEqual(resolve_catalogue(None), prev)

    def test_unresolved_mapping_blocks_activation(self):
        prev, _, _ = _make_prev_active()
        cand = _make_validated_candidate(source_hash='h5' * 32)
        src_item = StandardItem.objects.filter(category__framework=prev).first()
        tgt_item = StandardItem.objects.create(
            category=Category.objects.create(framework=cand, code='TKRS', name='TKRS', order=1),
            sub_standard='TKRS 1', code='TKRS 1 EP a', description='x', order=1,
        )
        PemetaanEdisi.objects.create(
            source_framework=prev, source_item_id=src_item.pk, source_code='TKRS 1 EP a',
            source_text_hash='a', target_framework=cand, target_item_id=tgt_item.pk,
            target_code='TKRS 1 EP a', target_text_hash='b',
            classification='UNRESOLVED', score_policy='REASSESS',
            reason='belum direview', approved=True,
        )
        with self.assertRaises(Exception):
            activate_catalogue(
                actor=_make_user(), framework=cand,
                reviewed_plan_hash='p', backup_reference='b',
                expected_previous_id=prev.pk,
            )
        prev.refresh_from_db()
        self.assertEqual(prev.lifecycle, 'ACTIVE')
