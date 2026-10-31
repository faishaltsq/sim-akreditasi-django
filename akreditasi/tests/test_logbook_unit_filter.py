from django.core.management import call_command
from django.test import TestCase
from pasien.models import Ruangan
from akreditasi.models import UnitKerja
from akreditasi.layanan_unit import RUANGAN_UNIT_CODE


class RuanganUnitKerjaLinkageTest(TestCase):
    def test_ruangan_linked_to_unit_kerja(self):
        """Every seeded Ruangan in RUANGAN_UNIT_CODE must have unit_kerja populated."""
        call_command('seed_pasien_data')
        for kode, unit_code in RUANGAN_UNIT_CODE.items():
            unit = UnitKerja.objects.filter(code=unit_code).first()
            self.assertIsNotNone(unit, f"UnitKerja with code {unit_code} must exist")
            r = Ruangan.objects.filter(kode=kode).first()
            self.assertIsNotNone(r, f"Ruangan with code {kode} must exist")
            self.assertIsNotNone(r.unit_kerja, f"Ruangan {kode} unit_kerja must not be None")
            self.assertEqual(r.unit_kerja.code, unit_code)
