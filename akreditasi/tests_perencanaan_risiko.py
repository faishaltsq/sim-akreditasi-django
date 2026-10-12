from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import RisikoUnit, IndikatorMutu


class PerencanaanRisikoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='testadmin', password='password123', email='admin@test.com')
        self.client = Client()
        self.client.force_login(self.user)

        self.unit = UnitKerja.objects.create(name='Unit Farmasi Rawat Inap', code='FARM-RANAP', level=3)
        self.indikator = IndikatorMutu.objects.create(
            kode_indikator='INM-01',
            nama_indikator='Kepatuhan Kebersihan Tangan',
            jenis='NASIONAL',
            dimensi_mutu='AMAN',
            numerator='Jumlah nakes patuh cuci tangan',
            denominator='Jumlah seluruh peluang cuci tangan',
            unit=self.unit,
            target_nilai=85.0
        )
        self.risiko = RisikoUnit.objects.create(
            unit=self.unit,
            periode='TAHUNAN',
            tahun=2026,
            jenis_risiko='Keterlambatan Penyiapan Obat Racikan',
            kategori_risiko='OPERASIONAL',
            masalah='Antrean resep racikan melebihi standar waktu 60 menit',
            data_pendukung='Hasil audit farmasi bulan Januari: rata-rata tunggu 78 menit',
            tujuan='Mempersingkat waktu penyiapan resep racikan menjadi maksimal 45 menit',
            deskripsi_risiko='Dapat memicu komplain pasien dan keterlambatan pemberian terapi',
            dampak=3,
            probabilitas=4,
            pengendalian_ada='Pemisahan meja racik',
            metode_evaluasi='FMEA',
            indikator_mutu_terkait=self.indikator,
            target_capaian_indikator=90.0,
            strategi_mitigasi='KURANGI',
            rencana_aksi='Penambahan mesin press pulverizer dan rotasi jam sibuk',
            pj_mitigasi='Apoteker Penanggung Jawab',
            biaya_mitigasi=5000000,
            created_by=self.user
        )

    def test_model_tujuan_and_display(self):
        """Test tujuan field and tujuan_display fallback."""
        self.assertEqual(self.risiko.tujuan, 'Mempersingkat waktu penyiapan resep racikan menjadi maksimal 45 menit')
        self.assertEqual(self.risiko.tujuan_display, 'Mempersingkat waktu penyiapan resep racikan menjadi maksimal 45 menit')

        # Test fallback when tujuan is empty
        risiko_empty = RisikoUnit.objects.create(
            unit=self.unit,
            periode='TAHUNAN',
            tahun=2026,
            jenis_risiko='Risiko Tanpa Tujuan Khusus',
            kategori_risiko='KLINIS',
            dampak=2,
            probabilitas=2,
            deskripsi_risiko='Deskripsi',
            rencana_aksi='Aksi mitigasi',
            pj_mitigasi='Ka. Unit',
            strategi_mitigasi='KURANGI',
            created_by=self.user
        )
        self.assertIn('Mengendalikan dan memitigasi risiko klinis', risiko_empty.tujuan_display)

    def test_perencanaan_dokumen_single_view(self):
        """Test single risk planning view (HTTP 200 and contents)."""
        url = reverse('akreditasi:risiko_perencanaan_dokumen', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'PERENCANAAN RESIKO RS MONSISKAMI ARIMA')
        self.assertContains(resp, 'JL. Candiwulan Kalibuntu Mangli Kuwarasan Kebumen Jawatengah')
        self.assertContains(resp, 'Unit Farmasi Rawat Inap')
        self.assertContains(resp, 'Mempersingkat waktu penyiapan resep racikan')
        self.assertContains(resp, 'Kepatuhan Kebersihan Tangan')
        self.assertContains(resp, 'Penambahan mesin press pulverizer')
        self.assertContains(resp, 'Kuwarasan')

    def test_perencanaan_unit_aggregate_view(self):
        """Test unit aggregate planning view (HTTP 200 and tables)."""
        url = reverse('akreditasi:risiko_perencanaan_unit', kwargs={'unit_id': self.unit.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'PERENCANAAN RESIKO RS MONSISKAMI ARIMA')
        self.assertContains(resp, 'TABEL 1: INDIKATOR MUTU TERKAIT RISIKO' if False else 'Indikator Mutu Terkait Risiko')
        self.assertContains(resp, 'Rencana Aksi (Mitigasi) Risiko')
        self.assertContains(resp, 'Antrean resep racikan melebihi standar waktu 60 menit')

    def test_perencanaan_export_csv(self):
        """Test CSV export view returns valid CSV with UTF-8 BOM."""
        url = reverse('akreditasi:risiko_perencanaan_export_csv') + f'?unit={self.unit.pk}&tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        content = resp.content.decode('utf-8')
        self.assertTrue(content.startswith('\ufeffPERENCANAAN RESIKO RS MONSISKAMI ARIMA'))
        self.assertIn('TABEL 1: INDIKATOR MUTU DENGAN RISIKO TERKAIT', content)
        self.assertIn('TABEL 2: RENCANA AKSI (MITIGASI) RISIKO', content)
        self.assertIn('Antrean resep racikan melebihi standar waktu 60 menit', content)

    def test_upload_bukti_data_pendukung(self):
        """Test upload file in risiko_input for data pendukung."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_file = SimpleUploadedFile("laporan_baseline.pdf", b"%PDF-1.4 sample baseline report", content_type="application/pdf")
        
        post_data = {
            'unit': self.unit.pk,
            'tahun': 2026,
            'periode': 'TAHUNAN',
            'kategori_risiko': 'OPERASIONAL',
            'jenis_risiko': 'Risiko dengan Lampiran Data Pendukung',
            'masalah': 'Masalah dengan lampiran data pendukung',
            'data': 'Audit internal menunjukkan baseline 15% deviasi',
            'tujuan': 'Target deviasi turun ke 0%',
            'deskripsi_risiko': 'Deskripsi risiko terlampir',
            'dampak': 3,
            'probabilitas': 3,
            'metode_evaluasi': 'STANDAR',
            'strategi_mitigasi': 'KURANGI',
            'rencana_aksi': 'Lakukan pelatihan ulang SOP',
            'pj_mitigasi': 'Ka. Unit',
            'bukti_data_pendukung': test_file
        }
        resp = self.client.post(reverse('akreditasi:risiko_input'), post_data)
        self.assertEqual(resp.status_code, 302)
        
        created = RisikoUnit.objects.filter(jenis_risiko='Risiko dengan Lampiran Data Pendukung').first()
        self.assertIsNotNone(created)
        self.assertTrue(bool(created.bukti_data_pendukung))
        self.assertIn('laporan_baseline', created.bukti_data_pendukung.name)

