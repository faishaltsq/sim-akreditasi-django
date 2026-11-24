"""F0.7 — impor katalog obat wajib idempoten.

``import_medication_catalogue --apply`` mengisi tiga tabel staging
(``KelasTerapiObat``, ``GenerikObat``, ``ProdukFarmasi``) dari
``klinis/data/medication_catalogue.json``. Sebelum F0.7 ketiganya 0 baris di
DB dev. Modul ini menjalankan impor dua kali dan memastikan run kedua tidak
membuat baris baru maupun mengubah jumlah baris — syarat rollback A2
("revert + seed idempoten").
"""
from pathlib import Path

from django.test import TestCase

from klinis.models import KelasTerapiObat, GenerikObat, ProdukFarmasi
from klinis.services.catalogue_import import import_catalogue

DATA = Path(__file__).resolve().parents[1] / 'data' / 'medication_catalogue.json'

class MedicationCatalogueImportTest(TestCase):
    def _counts(self):
        return (
            KelasTerapiObat.objects.count(),
            GenerikObat.objects.count(),
            ProdukFarmasi.objects.count(),
        )

    def test_impor_dua_kali_idempoten(self):
        pertama = import_catalogue('medication', str(DATA), apply=True)
        setelah_pertama = self._counts()

        kedua = import_catalogue('medication', str(DATA), apply=True)
        setelah_kedua = self._counts()

        self.assertGreater(setelah_pertama[0], 0)
        self.assertGreater(setelah_pertama[1], 0)
        self.assertGreater(setelah_pertama[2], 0)
        self.assertEqual(pertama['created'], sum(setelah_pertama))
        self.assertEqual(kedua['created'], 0)
        self.assertEqual(setelah_kedua, setelah_pertama)

    def test_tanpa_apply_tidak_menulis(self):
        hasil = import_catalogue('medication', str(DATA), apply=False)
        self.assertFalse(hasil['applied'])
        self.assertEqual(self._counts(), (0, 0, 0))
