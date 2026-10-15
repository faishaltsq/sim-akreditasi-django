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
        self.assertContains(resp, 'Total Estimasi Biaya Mitigasi')
        self.assertContains(resp, 'Rp 5.000.000')

    def test_perencanaan_unit_aggregate_view(self):
        """Test unit aggregate planning view (HTTP 200 and tables)."""
        url = reverse('akreditasi:risiko_perencanaan_unit', kwargs={'unit_id': self.unit.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'PERENCANAAN RESIKO RS MONSISKAMI ARIMA')
        self.assertContains(resp, 'TABEL 1: INDIKATOR MUTU TERKAIT RISIKO' if False else 'Indikator Mutu Terkait Risiko')
        self.assertContains(resp, 'Rencana Aksi (Mitigasi) Risiko')
        self.assertContains(resp, 'Antrean resep racikan melebihi standar waktu 60 menit')
        self.assertContains(resp, 'Total Estimasi Biaya Mitigasi')
        self.assertContains(resp, 'Rp 5.000.000')

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
        self.assertIn('TOTAL BIAYA MITIGASI', content)
        self.assertIn('Rp 5.000.000', content)

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

    def test_pelaksanaan_dokumen_single_view(self):
        """Test single risk execution view (HTTP 200)."""
        url = reverse('akreditasi:risiko_pelaksanaan_dokumen', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'PELAKSANAAN TINDAKAN RESIKO RS MONSISKAMI ARIMA')
        self.assertContains(resp, 'Siklus Do')

    def test_pelaksanaan_unit_view(self):
        """Test unit execution view (HTTP 200)."""
        url = reverse('akreditasi:risiko_pelaksanaan_unit', kwargs={'unit_id': self.unit.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'PELAKSANAAN TINDAKAN RESIKO RS MONSISKAMI ARIMA')

    def test_pelaksanaan_export_csv(self):
        """Test execution CSV export."""
        url = reverse('akreditasi:risiko_pelaksanaan_export_csv') + f'?unit={self.unit.pk}&tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        content = resp.content.decode('utf-8')
        self.assertIn('PELAKSANAAN RESIKO RS MONSISKAMI ARIMA', content)

    def test_risiko_edit_view_get(self):
        """Test edit view loads properly with pre-filled risk data."""
        url = reverse('akreditasi:risiko_edit', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'Edit Risiko #{self.risiko.pk}')

    def test_risiko_hapus_view(self):
        """Test risk delete view confirmation and post-delete."""
        url = reverse('akreditasi:risiko_hapus', kwargs={'risiko_id': self.risiko.pk})
        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, 'Konfirmasi Hapus Risiko')

        resp_post = self.client.post(url)
        self.assertEqual(resp_post.status_code, 302)
        self.assertFalse(RisikoUnit.objects.filter(pk=self.risiko.pk).exists())

    def test_laporan_lengkap_single_view(self):
        """Test Laporan Lengkap PDCA single risk view renders 4 phases and total cost."""
        url = reverse('akreditasi:risiko_laporan_lengkap_single', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('LAPORAN LENGKAP MANAJEMEN RISIKO', content)
        self.assertIn('FASE 1: PERENCANAAN RISIKO (PLAN)', content)
        self.assertIn('FASE 2: PELAKSANAAN TINDAKAN RISIKO (DO)', content)
        self.assertIn('FASE 3: MONITORING &amp; EVALUASI (CHECK)', content)
        self.assertIn('FASE 4: RENCANA TINDAK LANJUT (ACTION / RTL)', content)
        self.assertIn('Estimasi Biaya Mitigasi', content)
        self.assertIn('Rp 5.000.000', content)

    def test_laporan_lengkap_unit_view(self):
        """Test Laporan Lengkap PDCA aggregate unit view renders vertically stacked 9 sections and total costs."""
        url = reverse('akreditasi:risiko_laporan_lengkap_unit', kwargs={'unit_id': self.unit.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('LAPORAN LENGKAP MANAJEMEN RISIKO', content)
        self.assertIn('Unit Kamar Operasi', content)
        # Verify 9 sections stacked vertically
        self.assertIn('1. Identifikasi Masalah Risiko', content)
        self.assertIn('2. Tujuan', content)
        self.assertIn('3. Penilaian Risiko Awal', content)
        self.assertIn('4. Pemilihan Metode Evaluasi', content)
        self.assertIn('5. Indikator Mutu Terkait Risiko', content)
        self.assertIn('6. Rencana Aksi (Mitigasi) Risiko', content)
        self.assertIn('7. Pelaksanaan (Do)', content)
        self.assertIn('8. Monitoring dan evaluasi', content)
        self.assertIn('9. Kesimpulan Akhir', content)
        # Verify total cost calculation in aggregate summary & table footers
        self.assertIn('Total Alokasi Biaya Mitigasi', content)
        self.assertIn('Total Estimasi Biaya Mitigasi', content)
        self.assertIn('Total Biaya Pelaksanaan', content)
        self.assertIn('Rp 5.000.000', content)
        # Verify clean layout formatting & right-aligned financial styling
        self.assertIn('col-biaya-val', content)
        self.assertIn('col-pic-val', content)
        self.assertIn('table-sticky-wrapper', content)

    def test_document_views_contain_edit_and_delete_actions(self):
        """Verify that Perencanaan, Pelaksanaan, and Laporan Lengkap have Edit & Delete buttons."""
        # 1. Perencanaan unit
        url_plan = reverse('akreditasi:risiko_perencanaan_unit', kwargs={'unit_id': self.unit.pk})
        resp_plan = self.client.get(url_plan)
        self.assertEqual(resp_plan.status_code, 200)
        self.assertContains(resp_plan, f'/risiko/{self.risiko.pk}/edit/')
        self.assertContains(resp_plan, f'/risiko/{self.risiko.pk}/hapus/')

        # 2. Pelaksanaan unit
        url_do = reverse('akreditasi:risiko_pelaksanaan_unit', kwargs={'unit_id': self.unit.pk})
        resp_do = self.client.get(url_do)
        self.assertEqual(resp_do.status_code, 200)
        self.assertContains(resp_do, f'/risiko/{self.risiko.pk}/evaluasi/')
        self.assertContains(resp_do, f'/risiko/{self.risiko.pk}/hapus/')

        # 3. Laporan Lengkap Single
        url_single = reverse('akreditasi:risiko_laporan_lengkap_single', kwargs={'risiko_id': self.risiko.pk})
        resp_single = self.client.get(url_single)
        self.assertEqual(resp_single.status_code, 200)
        self.assertContains(resp_single, f'/risiko/{self.risiko.pk}/edit/')
        self.assertContains(resp_single, f'/risiko/{self.risiko.pk}/hapus/')

        # 4. Laporan Lengkap Unit
        url_unit = reverse('akreditasi:risiko_laporan_lengkap_unit', kwargs={'unit_id': self.unit.pk})
        resp_unit = self.client.get(url_unit)
        self.assertEqual(resp_unit.status_code, 200)
        self.assertContains(resp_unit, f'/risiko/{self.risiko.pk}/edit/')
        self.assertContains(resp_unit, f'/risiko/{self.risiko.pk}/hapus/')

    def test_risiko_monitoring_evaluasi_view_regression(self):
        """Pastikan view monitoring & evaluasi risiko merender HTTP 200 tanpa AttributeError pada skor_awal."""
        url = reverse('akreditasi:risiko_monev')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Monitoring')
        self.assertContains(resp, 'Awal:')

    def test_render_structured_plan_numbered(self):
        """Ensure render_structured_plan parses '1. Step one 2. Step two' into structured items."""
        from akreditasi.templatetags.akreditasi_tags import render_structured_plan
        raw_text = "1. Lakukan audit cepat alur triase 2. Revisi dan perbarui SOP Triase IGD"
        html = render_structured_plan(raw_text)
        self.assertIn('step-badge', html)
        self.assertIn('1', html)
        self.assertIn('2', html)
        self.assertIn('Lakukan audit cepat', html)
        self.assertIn('Revisi dan perbarui', html)

    def test_render_structured_plan_bullets(self):
        """Ensure render_structured_plan parses bulleted multiline text."""
        from akreditasi.templatetags.akreditasi_tags import render_structured_plan
        raw_text = "• Penempelan alur Door-to-ECG\n• Penyediaan EKG mobile"
        html = render_structured_plan(raw_text)
        self.assertIn('<ul', html)
        self.assertIn('Door-to-ECG', html)






