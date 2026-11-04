from django.test import TestCase
from pasien.models import DPJP_CHOICES, DPJP_POLI_MAP, POLIKLINIK_CHOICES


class DPJPPoliMapTest(TestCase):
    def test_every_dpjp_mapped_to_at_least_one_poli(self):
        mapped = {dpjp for dpjps in DPJP_POLI_MAP.values() for dpjp in dpjps}
        for val, _label in DPJP_CHOICES:
            self.assertIn(val, mapped, f'{val} tidak ter-map ke poliklinik manapun')

    def test_map_contains_only_known_dpjp_and_poli(self):
        dpjp_vals = {val for val, _ in DPJP_CHOICES}
        poli_vals = {val for val, _ in POLIKLINIK_CHOICES}
        for poli, dpjps in DPJP_POLI_MAP.items():
            self.assertIn(poli, poli_vals)
            for dpjp in dpjps:
                self.assertIn(dpjp, dpjp_vals)

    def test_every_poli_has_at_least_one_dpjp(self):
        for poli, _label in POLIKLINIK_CHOICES:
            self.assertIn(poli, DPJP_POLI_MAP, f'{poli} tidak punya DPJP')
            self.assertTrue(DPJP_POLI_MAP[poli])
