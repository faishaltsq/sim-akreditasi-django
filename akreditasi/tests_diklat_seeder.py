from django.core.management import call_command
from django.test import TestCase

from akreditasi.logbook_nonmedis_models import MasterAktivitasNonMedis


class TestDiklatSeeder(TestCase):
    def test_seed_master_aktivitas_diklat_creates_13_items_and_is_idempotent(self):
        call_command('seed_master_aktivitas_diklat')

        qs = MasterAktivitasNonMedis.objects.filter(kategori_unit='DIKLAT')
        self.assertEqual(qs.count(), 13)

        d1 = qs.get(kode='DIKLAT-01')
        self.assertEqual(d1.nama, 'Pelaksanaan Orientasi Pegawai Baru & Peserta Didik')
        self.assertIn('orientasi umum rumah sakit', d1.deskripsi)
        self.assertEqual(d1.ep_rekomendasi, 'KPS 8 / TKRS 9')

        d7 = qs.get(kode='DIKLAT-07')
        self.assertEqual(d7.nama, 'Pengelolaan Praktik Mahasiswa & Peserta Magang')
        self.assertIn('IPKP 1', d7.ep_rekomendasi)

        d13 = qs.get(kode='DIKLAT-13')
        self.assertEqual(d13.nama, 'Pengelolaan Arsip & Dokumen Akreditasi Diklat')
        self.assertIn('repository sistem ARIMA', d13.deskripsi)

        # Idempotency check: run again without duplication
        call_command('seed_master_aktivitas_diklat')
        self.assertEqual(MasterAktivitasNonMedis.objects.filter(kategori_unit='DIKLAT').count(), 13)
