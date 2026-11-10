from django.test import TestCase

from akreditasi.logbook_nonmedis_models import (
    MasterAktivitasNonMedis,
    resolve_ep_aktivitas,
)


class TestDiklatEpEngine(TestCase):
    def setUp(self):
        self.master_orientasi = MasterAktivitasNonMedis.objects.create(
            kode='DIKLAT-01',
            kategori_unit='DIKLAT',
            nama='Pelaksanaan Orientasi Pegawai Baru & Peserta Didik',
            ep_rekomendasi='KPS 8 / TKRS 9',
            standar_terkait=['KPS 8', 'TKRS 9'],
            urutan=1,
        )

    def test_resolve_from_master_returns_configured_ep(self):
        ep_rec = resolve_ep_aktivitas(master=self.master_orientasi)
        self.assertEqual(ep_rec, 'KPS 8 / TKRS 9')

    def test_resolve_from_text_keywords_mahasiswa_magang(self):
        ep_rec = resolve_ep_aktivitas(nama='Monitoring mahasiswa magang keperawatan di ruang rawat')
        self.assertIn('IPKP 1', ep_rec)
        self.assertIn('KPS 8', ep_rec)

    def test_resolve_from_text_keywords_penelitian_ethical_clearance(self):
        ep_rec = resolve_ep_aktivitas(uraian='Penerbitan surat izin ethical clearance dan pengumpulan responden')
        self.assertIn('IPKP 3', ep_rec)
        self.assertIn('TKRS 9', ep_rec)

    def test_resolve_from_text_keywords_mandatory_bhd(self):
        ep_rec = resolve_ep_aktivitas(nama='Pelatihan wajib internal', uraian='Praktek BHD dan simulasi APAR K3RS')
        self.assertIn('KPS 8', ep_rec)
        self.assertIn('PPI', ep_rec)
        self.assertIn('MFK', ep_rec)

    def test_resolve_fallback_empty(self):
        ep_rec = resolve_ep_aktivitas(nama='Aktivitas lain non-spesifik', uraian='Merapikan meja kerja')
        self.assertEqual(ep_rec, '')
