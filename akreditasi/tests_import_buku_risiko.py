import os
import django
from django.test import TestCase
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import RisikoUnit

class UnitResolverAndNormalizationTest(TestCase):
    def test_normalize_row_maps_fields_and_defaults(self):
        from akreditasi.management.commands.import_buku_risiko_bab3 import normalize_row
        raw = {
            "No": "1",
            "Kategori Risiko": "Klinis",
            "Jenis Risiko": "Medication Error",
            "Deskripsi Risiko": "Salah pembacaan resep manual yang berakibat fatal.",
            "Indikator Mutu": "INM: Kepatuhan Identifikasi Pasien",
            "Strategi Mitigasi": "Risk Reduction",
            "Rencana Aksi": "E-Prescribing ARIMA terintegrasi peringatan dosis otomatis."
        }
        res = normalize_row(raw)
        self.assertEqual(res['kategori_risiko'], 'KLINIS')
        self.assertEqual(res['jenis_risiko'], 'Medication Error')
        self.assertEqual(res['deskripsi_risiko'], 'Salah pembacaan resep manual yang berakibat fatal.')
        self.assertGreaterEqual(res['dampak'], 1)
        self.assertGreaterEqual(res['probabilitas'], 1)
        self.assertEqual(res['status'], 'IDENTIFIKASI')

    def test_resolve_unit_matches_poliklinik(self):
        from akreditasi.management.commands.import_buku_risiko_bab3 import resolve_unit, _unit_cache
        _unit_cache.clear()
        unit_existing = UnitKerja.objects.create(name="Poliklinik Penyakit Dalam", tipe_unit="POLIKLINIK")
        unit = resolve_unit("4.1.1 Poliklinik Penyakit Dalam", "BAB IV  INSTALASI RAWAT JALAN (IRJ)")
        self.assertIsNotNone(unit)
        self.assertEqual(unit.id, unit_existing.id)
        _unit_cache.clear()

    def test_resolve_unit_creates_new_when_not_found(self):
        from akreditasi.management.commands.import_buku_risiko_bab3 import resolve_unit, _unit_cache
        _unit_cache.clear()
        before = UnitKerja.objects.count()
        unit = resolve_unit("9.9.9 Unit Tidak Ada Sama Sekali", "BAB IX")
        after = UnitKerja.objects.count()
        self.assertIsNotNone(unit)
        self.assertEqual(after, before + 1)
        _unit_cache.clear()


class ImportBukuRisikoCommandTest(TestCase):
    def setUp(self):
        from akreditasi.management.commands.import_buku_risiko_bab3 import _unit_cache
        _unit_cache.clear()

    def test_dry_run_does_not_persist_records(self):
        from django.core.management import call_command
        before = RisikoUnit.objects.count()
        call_command('import_buku_risiko_bab3', dry_run=True)
        after = RisikoUnit.objects.count()
        self.assertEqual(before, after)

    def test_execution_creates_records_and_is_idempotent(self):
        from django.core.management import call_command
        from akreditasi.management.commands.import_buku_risiko_bab3 import _unit_cache
        call_command('import_buku_risiko_bab3', verbosity=0)
        first_count = RisikoUnit.objects.count()
        self.assertGreater(first_count, 100)
        _unit_cache.clear()
        call_command('import_buku_risiko_bab3', verbosity=0)
        second_count = RisikoUnit.objects.count()
        self.assertEqual(first_count, second_count)
