"""
Unit Tests for Monthly Quality Indicator Trends, Evidence Upload & Renstra Multi-Year Charts
Targeting: STARKES PMKP 12 & Renstra 2026-2030 Dashboard Integration
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu, CatatanIndikator, RenstraRoadmap

User = get_user_model()


class IndikatorMutuChartsAndUploadTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_mutu_chart', 'admin_mutu@rs.id', 'secret123')
        self.client = Client()
        self.client.force_login(self.user)

        self.unit = UnitKerja.objects.create(
            name='Instalasi Rawat Inap',
            code='RANAP-01',
            tipe_unit='RUANGAN'
        )

        self.indikator = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Kebersihan Tangan',
            kode_indikator='INM-01',
            unit=self.unit,
            jenis='NASIONAL',
            dimensi_mutu='AMAN',
            numerator='Peluang kebersihan tangan yang dilakukan',
            denominator='Total seluruh peluang kebersihan tangan',
            target_nilai=Decimal('85.00'),
            satuan='%',
            aktif=True,
        )

        self.roadmap_2026 = RenstraRoadmap.objects.create(
            tahun=2026,
            isu_strategis='Digital Foundation',
            target_persen=Decimal('75.00'),
            urutan=1,
            aktif=True
        )

    def test_input_capaian_with_file_upload(self):
        """Test submitting monthly indicator record with an attached proof file."""
        url = reverse('akreditasi:indikator_input_capaian', kwargs={'indikator_id': self.indikator.pk})

        test_file = SimpleUploadedFile(
            "laporan_mutu_januari.pdf",
            b"%PDF-1.4 test document content",
            content_type="application/pdf"
        )

        payload = {
            'bulan': 1,
            'tahun': 2026,
            'nilai_numerator': '90.00',
            'nilai_denominator': '100.00',
            'catatan': 'Rekapitulasi sampling triwulan 1',
            'bukti_dokumen': test_file,
        }

        resp = self.client.post(url, payload, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Verify saved in database
        catatan = CatatanIndikator.objects.get(indikator=self.indikator, bulan=1, tahun=2026)
        self.assertEqual(catatan.nilai_numerator, Decimal('90.00'))
        self.assertEqual(catatan.nilai_denominator, Decimal('100.00'))
        self.assertEqual(catatan.nilai_capaian, Decimal('90.00'))
        self.assertTrue(catatan.tercapai)
        self.assertTrue(bool(catatan.bukti_dokumen))
        self.assertTrue(catatan.bukti_dokumen.name.endswith('.pdf'))
        self.assertIn('laporan_mutu_januari', catatan.bukti_dokumen.name)

    def test_indikator_detail_displays_attachment_link(self):
        """Test detail page renders download link for uploaded evidence file."""
        test_file = SimpleUploadedFile(
            "bukti_audit.docx",
            b"test word document content",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        catatan = CatatanIndikator.objects.create(
            indikator=self.indikator,
            bulan=2,
            tahun=2026,
            nilai_numerator=Decimal('70.00'),
            nilai_denominator=Decimal('100.00'),
            catatan='Ada kekurangan sarana handrub',
            bukti_dokumen=test_file,
        )

        url = reverse('akreditasi:indikator_detail', kwargs={'indikator_id': self.indikator.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Unduh')
        self.assertContains(resp, 'bukti_audit')

    def test_dashboard_renders_quality_and_renstra_charts(self):
        """Test main dashboard renders both monthly trend and Renstra multi-year charts."""
        # Create monthly records
        CatatanIndikator.objects.create(
            indikator=self.indikator,
            bulan=1,
            tahun=2026,
            nilai_numerator=Decimal('90.00'),
            nilai_denominator=Decimal('100.00'),
        )
        CatatanIndikator.objects.create(
            indikator=self.indikator,
            bulan=2,
            tahun=2026,
            nilai_numerator=Decimal('75.00'),
            nilai_denominator=Decimal('100.00'),
        )

        url = reverse('akreditasi:dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Check HTML structure
        self.assertContains(resp, 'Grafik Capaian Indikator Mutu &amp; Roadmap Renstra')
        self.assertContains(resp, 'STARKES PMKP 12 &amp; RENSTRA')
        self.assertContains(resp, 'chartMutuBulanan')
        self.assertContains(resp, 'chartRenstraTahunan')
        self.assertContains(resp, 'pills-bulanan-tab')
        self.assertContains(resp, 'pills-renstra-tab')

        # Check chart dataset contexts in HTML
        content = resp.content.decode('utf-8')
        self.assertIn('chartMutuBulanan', content)
        self.assertIn('chartRenstraTahunan', content)
        self.assertIn('Batas Target', content)
        self.assertIn('Realisasi Capaian (%)', content)
        self.assertIn('Target Renstra (%)', content)

    def test_dashboard_filtered_by_category_and_unit(self):
        """Test dashboard query params filter charts without crashing."""
        url = reverse('akreditasi:dashboard') + f'?mutu_jenis=NASIONAL&mutu_unit={self.unit.pk}&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'chartMutuBulanan')
