"""A2 (AMBIGU-17a): peringatan kehamilan menyala dari kolom master, bukan kode.

Bukti yang ditegaskan di sini: ``ProdukFarmasi.pregnancy_class`` (diisi perintah
``seed_pregnancy_contra``) yang menentukan finding ``PREGNANCY_CONTRA``. Setiap
produk di bawah sengaja memakai ``class_code`` kasar
``kardiovaskular-antihipertensi`` — kelas yang **tidak** cocok dengan pencocokan
lama — dan snapshot resepnya sengaja tidak memuat ``pregnancy_class``, sehingga
satu-satunya jalan peringatan menyala adalah kolom master yang baru.
"""
import json
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import override_settings

from klinis.models import (
    GenerikObat, KelasTerapiObat, KomposisiProdukFarmasi, ProdukFarmasi,
)
from pasien.models import ResepDetail, ResepElektronik
from pasien.services.igd_assessment_workflow import save_step
from pasien.services.medication_safety import evaluate_prescription
from pasien.services.pregnancy_safety import contra_groups

from .tests_poli_workflow import TEST_STORAGES, PoliFixture

COARSE_CLASS = 'kardiovaskular-antihipertensi'


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class PregnancyContraMasterTest(PoliFixture):
    """Kolom master menentukan finding; kelas kasar tidak lagi menentukan."""

    def save(self, step, fields, version=0):
        return save_step(self.visit.pk, self.nurse, step, fields, version,
                         service_line='RAJAL_JANTUNG')

    def make_product(self, *, generic_name, kode, ingredient):
        cls, _ = KelasTerapiObat.objects.get_or_create(
            kode=COARSE_CLASS, defaults={'nama': 'Kardiovaskular & Antihipertensi'},
        )
        generic = GenerikObat.objects.create(
            kode=f'g-{kode}', nama=generic_name, kelas=cls,
            bentuk='TABLET', dispense_unit='tablet',
        )
        product = ProdukFarmasi.objects.create(
            kode=f'p-{kode}', nama=generic_name, generik=generic, kind='OBAT',
            active=True, source_version='fixture', reviewed_by=self.nurse,
            price=Decimal('1000'), allowed_routes=['PO'],
        )
        KomposisiProdukFarmasi.objects.create(
            produk=product, ingredient_code=ingredient, nama=ingredient,
            strength=Decimal('5'), unit='mg',
        )
        return product

    def prescribe(self, product, *, no_resep):
        """Snapshot tanpa ``pregnancy_class``: meniru resep pra-migrasi."""
        self.visit.skrining_alergi_status = 'TIDAK_ADA'
        self.visit.save(update_fields=['skrining_alergi_status'])
        rx = ResepElektronik.objects.create(
            no_resep=no_resep, kunjungan=self.visit, dokter_peresep=self.dpjp_user,
            jenis_resep='RAWAT_JALAN', status='DRAFT', serving_unit=self.unit,
        )
        ResepDetail.objects.create(
            resep=rx, product=product, nama_obat=product.nama, dosis='5 mg',
            aturan_pakai='1x1', jumlah=30, harga_satuan=Decimal('1000'), kind='OBAT',
            quantity_decimal=Decimal('30'), reference_price=Decimal('1000'),
            product_snapshot={
                'id': product.pk, 'kode': product.kode, 'class_code': COARSE_CLASS,
                'flags': [],
                'ingredients': [{'ingredient_code': 'x', 'strength': '5', 'unit': 'mg'}],
            },
        )
        return rx

    def seed(self, *args):
        out = StringIO()
        call_command('seed_pregnancy_contra', *args, stdout=out)
        return json.loads(out.getvalue())

    def codes(self, rx):
        return [finding['code'] for finding in evaluate_prescription(rx)]

    def test_captopril_triggers_for_pregnant_patient(self):
        self.save(3, {'status_kehamilan_menyusui': 'HAMIL'})
        product = self.make_product(
            generic_name='Captopril 12,5 mg / 25 mg', kode='captopril',
            ingredient='captopril')
        self.seed('--apply')
        product.refresh_from_db()
        self.assertEqual(product.pregnancy_class, 'ACEI')
        self.assertTrue(product.pregnancy_contra)

        rx = self.prescribe(product, no_resep='RX-CAPTOPRIL')
        findings = evaluate_prescription(rx)
        self.assertIn('PREGNANCY_CONTRA', [f['code'] for f in findings])
        finding = next(f for f in findings if f['code'] == 'PREGNANCY_CONTRA')
        self.assertTrue(finding['blocking'])
        self.assertIn('ACEI', finding['message'])

    def test_candesartan_triggers_for_pregnant_patient(self):
        self.save(3, {'status_kehamilan_menyusui': 'HAMIL'})
        product = self.make_product(
            generic_name='Candesartan 8 mg / 16 mg', kode='candesartan',
            ingredient='candesartan')
        self.seed('--apply')
        product.refresh_from_db()
        self.assertEqual(product.pregnancy_class, 'ARB')

        rx = self.prescribe(product, no_resep='RX-CANDESARTAN')
        findings = evaluate_prescription(rx)
        finding = next(f for f in findings if f['code'] == 'PREGNANCY_CONTRA')
        self.assertIn('ARB', finding['message'])

    def test_unmapped_drug_never_triggers(self):
        self.save(3, {'status_kehamilan_menyusui': 'HAMIL'})
        product = self.make_product(
            generic_name='Paracetamol 500 mg', kode='paracetamol',
            ingredient='paracetamol')
        self.seed('--apply')
        product.refresh_from_db()
        self.assertEqual(product.pregnancy_class, '')

        rx = self.prescribe(product, no_resep='RX-PARACETAMOL')
        self.assertNotIn('PREGNANCY_CONTRA', self.codes(rx))

    def test_non_pregnant_patient_never_triggers(self):
        self.save(3, {'status_kehamilan_menyusui': 'TIDAK_HAMIL_TIDAK_MENYUSUI'})
        product = self.make_product(
            generic_name='Captopril 12,5 mg / 25 mg', kode='captopril2',
            ingredient='captopril')
        self.seed('--apply')
        rx = self.prescribe(product, no_resep='RX-NOT-PREGNANT')
        self.assertNotIn('PREGNANCY_CONTRA', self.codes(rx))

    def test_master_column_beats_the_coarse_class_code(self):
        """Kolom menang: ``class_code`` ACEI tidak menyalakan apa pun bila kosong."""
        product = self.make_product(
            generic_name='Paracetamol 500 mg', kode='para2', ingredient='paracetamol')
        self.assertEqual(
            contra_groups({'class_code': COARSE_CLASS, 'pregnancy_class': ''}), set())
        self.assertEqual(contra_groups({'pregnancy_class': 'STatin'.upper()}), {'STATIN'})
        self.assertEqual(contra_groups({'pregnancy_class': 'TIDAK_DIKENAL'}), set())

    def test_command_is_idempotent_and_reports_what_it_could_not_map(self):
        self.make_product(generic_name='Captopril 12,5 mg / 25 mg', kode='cap3',
                          ingredient='captopril')
        self.make_product(generic_name='Paracetamol 500 mg', kode='para3',
                          ingredient='paracetamol')
        first = self.seed('--apply')
        second = self.seed('--apply')

        self.assertEqual(first['counts']['ACEI'], 1)
        self.assertEqual(second['counts']['ACEI'], 0)
        self.assertEqual(second['skipped_already_classified'], ['p-cap3'])
        self.assertEqual(ProdukFarmasi.objects.filter(pregnancy_class='ACEI').count(), 1)
        # Tidak menebak: paracetamol tetap tanpa kelas dan dilaporkan.
        self.assertIn('p-para3', second['unmapped'])
        # Celah katalog dilaporkan, bukan ditambal.
        self.assertIn('Warfarin', second['zat_tanpa_generik'])
        self.assertIn('ARNI', second['kelompok_tanpa_baris'])

    def test_dry_run_writes_nothing(self):
        product = self.make_product(generic_name='Valsartan 80 mg / 160 mg',
                                    kode='valsartan', ingredient='valsartan')
        report = self.seed()
        product.refresh_from_db()
        self.assertEqual(report['mode'], 'dry-run')
        self.assertEqual(report['counts']['ARB'], 1)
        self.assertEqual(product.pregnancy_class, '')
        self.assertFalse(product.pregnancy_contra)

    def test_source_is_recorded_on_every_mapped_row(self):
        product = self.make_product(generic_name='Valsartan 80 mg / 160 mg',
                                    kode='valsartan2', ingredient='valsartan')
        self.seed('--apply')
        product.refresh_from_db()
        self.assertIn('ADR-15', product.pregnancy_class_source)
        self.assertIn('Valsartan', product.pregnancy_class_source)

    def test_model_rejects_a_class_without_the_boolean(self):
        product = self.make_product(generic_name='Paracetamol 500 mg',
                                    kode='para4', ingredient='paracetamol')
        product.pregnancy_class = 'ACEI'
        with self.assertRaises(Exception):
            product.full_clean()
