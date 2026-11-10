from datetime import date, time
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from akreditasi.models import UnitKerja
from akreditasi.logbook_nonmedis_models import (
    LogbookNonMedis,
    MasterAktivitasNonMedis,
    AktivitasNonMedis,
)

User = get_user_model()


class TestDiklatModels(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staf.diklat',
            first_name='Basirun',
            last_name='Al Ummah',
            password='password123',
        )
        self.unit = UnitKerja.objects.create(
            name='Bagian Pendidikan & Pelatihan (Diklat)',
            code='BAG-DIKLAT-TEST',
            level=2,
            is_active=True,
        )
        self.logbook = LogbookNonMedis.objects.create(
            unit=self.unit,
            pelaksana_nama='Dr. Muh. Basirun Al Ummah, MKes',
            tanggal=date(2026, 11, 10),
            jam_mulai=time(8, 0),
            jam_selesai=time(16, 0),
            shift='PAGI',
            dibuat_oleh=self.user,
        )

    def test_master_aktivitas_creation_and_ordering(self):
        m1 = MasterAktivitasNonMedis.objects.create(
            kode='DIKLAT-01',
            kategori_unit='DIKLAT',
            nama='Pelaksanaan Orientasi Pegawai Baru & Peserta Didik',
            deskripsi='Menyusun jadwal, materi, dan lembar evaluasi untuk orientasi umum dan khusus.',
            ep_rekomendasi='KPS 8 / TKRS 9',
            standar_terkait=['KPS 8', 'TKRS 9'],
            urutan=1,
        )
        m2 = MasterAktivitasNonMedis.objects.create(
            kode='DIKLAT-02',
            kategori_unit='DIKLAT',
            nama='Penyusunan Program & KAK/TOR Pelatihan (IHT)',
            deskripsi='Merancang Kerangka Acuan Kerja (KAK) dan proposal kegiatan IHT.',
            ep_rekomendasi='KPS 8 / TKRS 9',
            standar_terkait=['KPS 8', 'TKRS 9'],
            urutan=2,
        )
        self.assertEqual(str(m1), 'DIKLAT-01 — Pelaksanaan Orientasi Pegawai Baru & Peserta Didik')
        items = list(MasterAktivitasNonMedis.objects.filter(kategori_unit='DIKLAT'))
        self.assertEqual(items[0], m1)
        self.assertEqual(items[1], m2)

    def test_aktivitas_nonmedis_child_model(self):
        master = MasterAktivitasNonMedis.objects.create(
            kode='DIKLAT-01',
            kategori_unit='DIKLAT',
            nama='Pelaksanaan Orientasi Pegawai Baru & Peserta Didik',
            ep_rekomendasi='KPS 8 / TKRS 9',
            urutan=1,
        )
        dummy_file = SimpleUploadedFile("absen_materi.pdf", b"dummy pdf content", content_type="application/pdf")

        aktivitas = AktivitasNonMedis.objects.create(
            logbook=self.logbook,
            master=master,
            urutan=1,
            jam_mulai=time(8, 0),
            jam_selesai=time(10, 0),
            nama_aktivitas=master.nama,
            detail_uraian='Melakukan orientasi keselamatan pasien bagi 5 perawat baru di ruang pertemuan.',
            ep_starkes='KPS 8 / TKRS 9',
            pelaksana_nama=self.logbook.pelaksana_nama,
            nama_bukti='Absen & Materi',
            dokumen_bukti=dummy_file,
        )

        self.assertEqual(self.logbook.aktivitas_list.count(), 1)
        self.assertEqual(aktivitas.waktu_display, '08.00 - 10.00')
        self.assertAlmostEqual(aktivitas.durasi_jam, 2.0)
        self.assertTrue(aktivitas.dokumen_bukti.name.endswith('.pdf'))
        self.assertEqual(aktivitas.ep_starkes, 'KPS 8 / TKRS 9')
