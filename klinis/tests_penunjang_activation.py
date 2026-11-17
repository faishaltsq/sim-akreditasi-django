import json
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from akreditasi.models import UnitKerja
from klinis.models import ItemPenunjang, KategoriPenunjang
from klinis.services.penunjang_catalogue import list_choices


class ActivatePenunjangCatalogueTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewer = User.objects.create_superuser('katalog_reviewer', password='fixture-only')
        cls.lab = UnitKerja.objects.get_or_create(code='LAB-BDRS', defaults={'name': 'Laboratorium', 'level': 2})[0]
        cls.rad = UnitKerja.objects.get_or_create(code='RAD', defaults={'name': 'Radiologi', 'level': 2})[0]
        cls.igd = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 2})[0]
        cls.l1 = KategoriPenunjang.objects.create(kode='laboratorium', nama='Laboratorium', level=1)
        cls.lab_klinik = KategoriPenunjang.objects.create(kode='laboratorium-laboratorium-klinik', nama='Laboratorium Klinik', level=2, parent=cls.l1)
        cls.rujukan = KategoriPenunjang.objects.create(kode='laboratorium-rujukan-luar', nama='Rujukan Luar', level=2, parent=cls.l1)
        cls.hematologi = KategoriPenunjang.objects.create(kode='laboratorium-laboratorium-klinik-hematologi', nama='Hematologi', level=3, parent=cls.lab_klinik)
        cls.rujukan_l3 = KategoriPenunjang.objects.create(kode='laboratorium-rujukan-luar-luar', nama='Rujukan', level=3, parent=cls.rujukan)
        cls.d1 = KategoriPenunjang.objects.create(kode='penunjang-diagnostik', nama='Penunjang Diagnostik', level=1)
        cls.radiologi = KategoriPenunjang.objects.create(kode='penunjang-diagnostik-radiologi-pencitraan', nama='Radiologi & Pencitraan', level=2, parent=cls.d1)
        cls.ct = KategoriPenunjang.objects.create(kode='penunjang-diagnostik-radiologi-pencitraan-ct-scan', nama='CT Scan', level=3, parent=cls.radiologi)
        cls.ekg = KategoriPenunjang.objects.create(kode='penunjang-diagnostik-elektrofisiologi-ekg', nama='EKG', level=3,
                                                  parent=KategoriPenunjang.objects.create(kode='penunjang-diagnostik-elektrofisiologi', nama='Elektrofisiologi', level=2, parent=cls.d1))
        cls.item_lab = cls.make_item('lab-darah-lengkap', cls.hematologi, 'LAB')
        cls.item_rujukan = cls.make_item('lab-rujukan-pcr', cls.rujukan_l3, 'LAB')
        cls.item_ct = cls.make_item('rad-ct-kepala', cls.ct, 'RADIOLOGI')
        cls.item_ekg = cls.make_item('ekg-12-lead', cls.ekg, 'EKG')

    @classmethod
    def make_item(cls, kode, group, jenis):
        return ItemPenunjang.objects.create(kode=kode, nama=kode.replace('-', ' ').title(), group=group,
                                            jenis_order=jenis, active=False, source_version='DOCX-2026-11-13')

    def sidecar(self, rules=None, units=None):
        data = {'destination_units': units or {'LAB': 'LAB-BDRS', 'RAD': 'RAD', 'EKG': 'IGD'},
                'rules': rules or [
                    {'prefix': 'laboratorium-rujukan-luar-', 'unit': 'LAB', 'required': ['specimen', 'external_destination']},
                    {'prefix': 'laboratorium-', 'unit': 'LAB', 'required': ['specimen']},
                    {'prefix': 'penunjang-diagnostik-radiologi-pencitraan-ct-scan', 'unit': 'RAD', 'required': ['contrast', 'pregnancy']},
                    {'prefix': 'penunjang-diagnostik-elektrofisiologi-', 'unit': 'EKG', 'required': []},
                ]}
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(data, handle)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return handle.name

    def activate(self, *extra):
        call_command('activate_penunjang_catalogue', reviewer='katalog_reviewer',
                     sidecar=self.sidecar(), *extra, stdout=StringIO())

    def test_activation_makes_items_orderable_with_longest_prefix_rule(self):
        self.activate()
        self.item_lab.refresh_from_db()
        self.item_rujukan.refresh_from_db()
        self.item_ct.refresh_from_db()
        self.item_ekg.refresh_from_db()
        self.assertTrue(self.item_lab.active)
        self.assertEqual(self.item_lab.destination, self.lab)
        self.assertEqual(self.item_lab.reviewed_by, self.reviewer)
        self.assertEqual(self.item_lab.preparation_schema, {'required': ['specimen']})
        self.assertEqual(self.item_rujukan.preparation_schema, {'required': ['specimen', 'external_destination']})
        self.assertEqual(self.item_ct.destination, self.rad)
        self.assertEqual(self.item_ct.preparation_schema, {'required': ['contrast', 'pregnancy']})
        self.assertEqual(self.item_ekg.destination, self.igd)
        self.assertEqual(self.item_ekg.preparation_schema, {'required': []})
        rows = list_choices(self.reviewer, parent_id=self.hematologi.pk)['results']
        self.assertEqual([row['kode'] for row in rows], ['lab-darah-lengkap'])
        self.assertEqual(rows[0]['destination_id'], self.lab.pk)

    def test_dry_run_writes_nothing(self):
        self.activate('--dry-run')
        self.item_lab.refresh_from_db()
        self.assertFalse(self.item_lab.active)
        self.assertIsNone(self.item_lab.destination)

    def test_missing_unit_blocks_activation(self):
        with self.assertRaises(CommandError):
            call_command('activate_penunjang_catalogue', reviewer='katalog_reviewer',
                         sidecar=self.sidecar(units={'LAB': 'UNIT-TIDAK-ADA', 'RAD': 'RAD', 'EKG': 'IGD'}, rules=[
                             {'prefix': 'laboratorium-', 'unit': 'LAB', 'required': []},
                             {'prefix': 'penunjang-diagnostik-', 'unit': 'RAD', 'required': []},
                         ]), stdout=StringIO())
        self.item_lab.refresh_from_db()
        self.assertFalse(self.item_lab.active)

    def test_unmatched_item_blocks_activation(self):
        with self.assertRaises(CommandError):
            call_command('activate_penunjang_catalogue', reviewer='katalog_reviewer',
                         sidecar=self.sidecar(rules=[{'prefix': 'laboratorium-', 'unit': 'LAB', 'required': []}]),
                         stdout=StringIO())
        self.item_lab.refresh_from_db()
        self.assertFalse(self.item_lab.active)

    def test_reviewer_is_mandatory(self):
        with self.assertRaises(CommandError):
            call_command('activate_penunjang_catalogue', sidecar=self.sidecar(), stdout=StringIO())

    def test_unknown_preparation_key_is_rejected(self):
        with self.assertRaisesMessage(CommandError, 'tak dikenal'):
            call_command('activate_penunjang_catalogue', reviewer='katalog_reviewer',
                         sidecar=self.sidecar(rules=[{'prefix': 'laboratorium-', 'unit': 'LAB', 'required': ['bogus']}],
                                              units={'LAB': 'LAB-BDRS'}), stdout=StringIO())

    def test_item_without_source_version_is_refused_atomically(self):
        ItemPenunjang.objects.filter(pk=self.item_lab.pk).update(source_version='')
        with self.assertRaises(CommandError):
            call_command('activate_penunjang_catalogue', reviewer='katalog_reviewer',
                         sidecar=self.sidecar(), stdout=StringIO())
        self.item_ct.refresh_from_db()
        self.assertFalse(self.item_ct.active)
