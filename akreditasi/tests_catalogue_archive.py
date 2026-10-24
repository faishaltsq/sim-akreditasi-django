"""Track C3: Arsip baca-satu — write guard menolak semua mutasi pada katalog ARCHIVED."""

from django.test import TestCase
from django.contrib.auth import get_user_model

from akreditasi.catalogue import require_catalogue_write
from akreditasi.models import (
    Category, Framework, StandardItem, QualityRecord, EvidenceFile, EvidenceReq,
    UnitKerja,
)
from accounts.models import UserProfile

User = get_user_model()


def _make_user(role):
    u = User.objects.create_user(username=role.lower(), password='pw')
    UserProfile.objects.create(user=u, role=role)
    return u


class ArchiveWriteGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fw = Framework.objects.create(
            name='STARKES 2022 Arsip', version='2022', edition='2022',
            lifecycle='ARCHIVED', is_active=False,
        )
        cls.active = Framework.objects.create(
            name='STARKES 2024 Aktif', version='2024', edition='2024',
            lifecycle='ACTIVE', is_active=True,
        )
        cls.arch_cat = Category.objects.create(
            framework=cls.fw, code='TKRS', name='TKRS', order=1
        )
        cls.arch_item = StandardItem.objects.create(
            category=cls.arch_cat, sub_standard='TKRS 1', code='TKRS 1 EP a',
            description='arsip', order=1,
        )
        cls.arch_rec = QualityRecord.objects.create(
            standard_item=cls.arch_item, unit=UnitKerja.objects.create(name='U', code='U'),
            score=10, assessment_state='ASSESSED',
        )
        cls.req = EvidenceReq.objects.create(
            standard_item=cls.arch_item, category_type='R', title='Bukti R',
        )
        cls.file = EvidenceFile.objects.create(
            requirement=cls.req, file_name='arsip.pdf', status='VALID',
        )
        cls.superuser = _make_user('SUPER_ADMIN')
        cls.adminrs = _make_user('ADMIN_RS')
        cls.koordinator = _make_user('KOORDINATOR_POKJA')
        cls.kepala = _make_user('KEPALA_UNIT')
        cls.staf = _make_user('STAF_NAKES')
        cls.asesor = _make_user('ASESOR')

    def test_require_catalogue_write_rejects_every_role_on_archived(self):
        for u in (self.superuser, self.adminrs, self.koordinator, self.kepala,
                  self.staf, self.asesor):
            with self.assertRaises(Exception):
                require_catalogue_write(u, item=self.arch_rec, operation='score')
            with self.assertRaises(Exception):
                require_catalogue_write(u, item=self.file, operation='upload')
            with self.assertRaises(Exception):
                require_catalogue_write(u, item=self.file, operation='unlink')
            with self.assertRaises(Exception):
                require_catalogue_write(u, item=self.arch_rec, operation='edit')
            with self.assertRaises(Exception):
                require_catalogue_write(u, item=self.arch_rec, operation='delete')
            with self.assertRaises(Exception):
                require_catalogue_write(u, item=self.arch_rec, operation='auto_score')
            with self.assertRaises(Exception):
                require_catalogue_write(u, item=self.file, operation='link')

    def test_require_catalogue_write_allows_active_for_admin(self):
        act_cat = Category.objects.create(framework=self.active, code='TKRS', name='TKRS', order=2)
        act_item = StandardItem.objects.create(
            category=act_cat, sub_standard='TKRS 1', code='TKRS 1 EP b', description='aktif', order=1,
        )
        act_rec = QualityRecord.objects.create(
            standard_item=act_item, unit=self.arch_rec.unit, score=5,
        )
        require_catalogue_write(self.superuser, item=act_rec, operation='score')
