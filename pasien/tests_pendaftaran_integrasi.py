from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from pasien.models import (
    DPJP_CHOICES, DPJP_POLI_MAP, POLIKLINIK_CHOICES,
    JadwalDinusAdmission, LogbookHarianAdmission,
)


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


class AdmissionShiftLogbookModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas_loket', password='password123')

    def test_create_jadwal_dinus_defaults(self):
        j = JadwalDinusAdmission.objects.create(petugas=self.user, tanggal=date(2026, 11, 4), shift='PAGI')
        self.assertEqual(j.status_kehadiran, 'HADIR')
        self.assertEqual(str(j), f'{self.user.username} — 2026-11-04 Pagi (07:00 - 14:00)')

    def test_create_logbook_defaults(self):
        log = LogbookHarianAdmission.objects.create(
            petugas=self.user, kegiatan='Verifikasi berkas 12 pasien BPJS')
        self.assertEqual(log.tanggal, timezone.localdate())
        self.assertIsNotNone(log.jam_aktivitas)
        self.assertIn('Verifikasi berkas', str(log))
