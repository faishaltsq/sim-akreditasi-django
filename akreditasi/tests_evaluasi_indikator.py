import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import (
    RisikoUnit, IndikatorMutu, TindakLanjutRisiko
)
from akreditasi.ai_service import generate_evaluasi_risiko


class EvaluasiIndikatorMutuTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='evaladmin',
            password='password123',
            email='evaladmin@test.com'
        )
        self.client = Client()
        self.client.force_login(self.user)

        self.unit = UnitKerja.objects.create(name='Unit Gawat Darurat', code='UGD-01', level=3)
        self.indikator = IndikatorMutu.objects.create(
            kode_indikator='INM-UGD-01',
            nama_indikator='Waktu Tanggap Pelayanan Gawat Darurat (Emergency Response Time)',
            jenis='NASIONAL',
            dimensi_mutu='KESELAMATAN',
            target_nilai=90.0,
            arah_target='MIN',
            satuan='%',
            unit=self.unit
        )
        self.risiko = RisikoUnit.objects.create(
            unit=self.unit,
            periode='TAHUNAN',
            tahun=2026,
            jenis_risiko='Keterlambatan Respon Triase Pasien Kritis',
            kategori_risiko='KLINIS',
            dampak=4,
            probabilitas=4,
            deskripsi_risiko='Antrean pasien menumpuk di triase gawat darurat',
            strategi_mitigasi='KURANGI',
            indikator_mutu_terkait=self.indikator,
            target_capaian_indikator=90.0,
            rencana_aksi="1. Penyiapan form triase digital ATS\n2. Pelatihan triage ESI perawat UGD\n3. Pengadaan tombol code red",
            pj_mitigasi='Ka. Tim Triase UGD',
            status='DO',
            created_by=self.user
        )

    def test_rencana_aksi_list_parsing(self):
        """Test RisikoUnit.rencana_aksi_list property parses numbered, bullet, and plain text."""
        # Numbered list
        items = self.risiko.rencana_aksi_list
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]['urutan'], 1)
        self.assertEqual(items[0]['text'], 'Penyiapan form triase digital ATS')
        self.assertEqual(items[1]['urutan'], 2)
        self.assertEqual(items[1]['text'], 'Pelatihan triage ESI perawat UGD')
        self.assertEqual(items[2]['urutan'], 3)
        self.assertEqual(items[2]['text'], 'Pengadaan tombol code red')

        # Bullet list
        self.risiko.rencana_aksi = "- SPO Revisi Triase\n* Briefing Pagi\n• Supervisi Ka. Ruang"
        bullet_items = self.risiko.rencana_aksi_list
        self.assertEqual(len(bullet_items), 3)
        self.assertEqual(bullet_items[0]['text'], 'SPO Revisi Triase')
        self.assertEqual(bullet_items[1]['text'], 'Briefing Pagi')
        self.assertEqual(bullet_items[2]['text'], 'Supervisi Ka. Ruang')

        # Empty
        self.risiko.rencana_aksi = ""
        self.assertEqual(self.risiko.rencana_aksi_list, [])

    def test_jenis_dokumen_bukti_choices(self):
        """Test choices field jenis_dokumen_capaian."""
        codes = [c[0] for c in RisikoUnit.JENIS_DOKUMEN_BUKTI_CHOICES]
        self.assertIn('LAPORAN_BULANAN', codes)
        self.assertIn('LAPORAN_INSIDEN', codes)
        self.assertIn('FORM_AUDIT', codes)
        self.assertIn('FOTO_BUKTI', codes)
        self.assertIn('SOP_KEBIJAKAN', codes)
        self.assertIn('LAINNYA', codes)

        self.risiko.jenis_dokumen_capaian = 'FORM_AUDIT'
        self.risiko.save()
        self.risiko.refresh_from_db()
        self.assertEqual(self.risiko.jenis_dokumen_capaian, 'FORM_AUDIT')
        self.assertEqual(self.risiko.get_jenis_dokumen_capaian_display(), 'Form Audit / Monitoring Kepatuhan')

    def test_view_risiko_evaluasi_get(self):
        """Test GET risiko_evaluasi renders new G.1, G.2, G.3 elements."""
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Context checks
        self.assertIn('jenis_dokumen_choices', resp.context)
        self.assertIn('rencana_aksi_items', resp.context)

        # G.1 Indikator Mutu Callout, gap calculation & AI buttons
        self.assertContains(resp, 'G.1 Capaian Indikator Mutu &amp; Bukti Pendukung')
        self.assertContains(resp, 'Waktu Tanggap Pelayanan Gawat Darurat')
        self.assertContains(resp, 'btn-insert-template')
        self.assertContains(resp, 'btn-ai-evaluasi')
        self.assertContains(resp, 'jenis_dokumen_capaian')

        # G.2 Monitoring Per-Item
        self.assertContains(resp, 'G.2 Status Pelaksanaan Tindakan Setiap Rencana')
        self.assertContains(resp, 'Penyiapan form triase digital ATS')

        # G.3 Residual & Matrix
        self.assertContains(resp, 'G.3 Penilaian Risiko Sisa')
        self.assertContains(resp, 'mini-matrix')
        self.assertContains(resp, 'calc-reduction-pill')

    def test_view_risiko_evaluasi_post_with_tindak_lanjut(self):
        """Test POST risiko_evaluasi saves individual action statuses, recalculates aggregate and residual score."""
        tl1 = TindakLanjutRisiko.objects.create(
            risiko=self.risiko,
            urutan=1,
            aksi='Penyiapan form triase digital ATS',
            status_aksi='BELUM'
        )
        tl2 = TindakLanjutRisiko.objects.create(
            risiko=self.risiko,
            urutan=2,
            aksi='Pelatihan triage ESI perawat UGD',
            status_aksi='BELUM'
        )

        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        post_data = {
            'capaian_nilai': '92.5',
            'jenis_dokumen_capaian': 'LAPORAN_BULANAN',
            'evaluasi_capaian': '1. Analisis Capaian: Target 90% terlampaui 92.5%\n2. Evaluasi Barrier: Efektif\n3. Kendala: Tidak ada',
            f'tl_status_{tl1.pk}': 'SELESAI',
            f'tl_status_{tl2.pk}': 'SELESAI',
            'dampak_residual': '2',
            'probabilitas_residual': '1',
            'status_rtl': 'SELESAI',
            'pj_rtl': 'Ka. UGD',
        }

        resp = self.client.post(url, data=post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.risiko.refresh_from_db()
        tl1.refresh_from_db()
        tl2.refresh_from_db()

        # Check action statuses
        self.assertEqual(tl1.status_aksi, 'SELESAI')
        self.assertEqual(tl2.status_aksi, 'SELESAI')

        # Check auto-synced aggregate status
        self.assertEqual(self.risiko.status_pelaksanaan, 'DILAKUKAN')

        # Check residual calculation (2 * 1 = 2)
        self.assertEqual(self.risiko.dampak_residual, 2)
        self.assertEqual(self.risiko.probabilitas_residual, 1)
        self.assertEqual(self.risiko.skor_residual, 2)
        self.assertEqual(self.risiko.status, 'EVALUASI')
        self.assertEqual(float(self.risiko.capaian_nilai), 92.5)
        self.assertEqual(self.risiko.jenis_dokumen_capaian, 'LAPORAN_BULANAN')

    def test_ai_service_evaluasi_risiko_fallback(self):
        """Test generate_evaluasi_risiko produces structured PDCA text when offline."""
        result = generate_evaluasi_risiko(
            user=self.user,
            unit_name='Unit Gawat Darurat',
            jenis_risiko='Keterlambatan Respon Triase',
            deskripsi_risiko='Antrean pasien menumpuk di triase',
            skor_awal=16,
            dampak_awal=4,
            prob_awal=4,
            mitigasi_terlaksana='Digitalisasi form triase',
            dampak_residual=2,
            prob_residual=1,
            status='EVALUASI',
            nama_indikator='Waktu Tanggap Pelayanan Gawat Darurat',
            target_capaian='90%',
            capaian_nilai='92.5%',
            gap_persen='+2.5%'
        )
        self.assertTrue(result['success'])
        self.assertIn('draf_evaluasi', result['data'])
        draft = result['data']['draf_evaluasi']
        self.assertIn('1. Analisis Capaian:', draft)
        self.assertIn('2. Evaluasi Barrier/Mitigasi:', draft)
        self.assertIn('3. Kendala di Lapangan:', draft)

    def test_api_ai_evaluasi_risiko_endpoint(self):
        """Test API endpoint api_ai_evaluasi_risiko with mutu payload."""
        url = reverse('akreditasi:ai_evaluasi_risiko')
        payload = {
            'unit_name': 'Unit Gawat Darurat',
            'jenis_risiko': 'Keterlambatan Respon Triase',
            'deskripsi_risiko': 'Antrean pasien menumpuk di triase',
            'skor_awal': 16,
            'dampak_awal': 4,
            'prob_awal': 4,
            'mitigasi_terlaksana': 'Digitalisasi form triase',
            'dampak_residual': 2,
            'prob_residual': 1,
            'nama_indikator': 'Waktu Tanggap Pelayanan Gawat Darurat',
            'target_capaian': '90%',
            'capaian_nilai': '92.5%',
            'gap_persen': '+2.5%'
        }
        resp = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('draf_evaluasi', data['data'])
