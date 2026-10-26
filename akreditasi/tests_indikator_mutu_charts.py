"""
Unit Tests for Monthly Quality Indicator Trends, Evidence Upload & Renstra Multi-Year Charts
Targeting: STARKES PMKP 12 & Renstra 2026-2030 Dashboard Integration
"""
import re
import json
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

    # ── Task 1: single indicator selection, target-aware colors ─────────────

    def test_dashboard_single_indicator_selection_and_colors(self):
        """Selecting one indicator charts its own monthly trend, target line and per-bar colours."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('90'), nilai_denominator=Decimal('100'))
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=2, tahun=2026,
            nilai_numerator=Decimal('70'), nilai_denominator=Decimal('100'))

        url = reverse('akreditasi:dashboard') + f'?mutu_indikator={self.indikator.pk}&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()

        # Data of the single indicator: Jan=90.0, Feb=70.0 (target 85.00)
        self.assertIn('[90.0, 70.0', content)
        # Target line uses the indicator's own target, not the average of all
        self.assertIn('85.0', content)
        # Jan green, Feb red, remaining months grey
        self.assertIn('["#198754", "#dc3545"', content)

    def test_dashboard_arah_target_max_flips_bar_colors(self):
        """MAX indicators (lower is better) turn green when capaian <= target."""
        ind_max = IndikatorMutu.objects.create(
            nama_indikator='Waktu Tanggap Pelayanan IGD', kode_indikator='IMRS-99',
            unit=self.unit, jenis='IMRS', dimensi_mutu='EFISIEN',
            numerator='Jumlah kasus <= 5 menit', denominator='Total kasus',
            target_nilai=Decimal('5.00'), satuan='Menit', arah_target='MAX', aktif=True)
        CatatanIndikator.objects.create(
            indikator=ind_max, bulan=1, tahun=2026,
            nilai_numerator=Decimal('4'), nilai_denominator=Decimal('100'))  # 4% <= 5% -> green

        url = reverse('akreditasi:dashboard') + f'?mutu_indikator={ind_max.pk}&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('["#198754"', resp.content.decode())

        CatatanIndikator.objects.filter(indikator=ind_max, bulan=1, tahun=2026).update(
            nilai_numerator=Decimal('8'))  # 8% > 5% -> red
        resp = self.client.get(url)
        self.assertIn('["#dc3545"', resp.content.decode())

    def test_dashboard_multi_year_trend_and_matrix_tab(self):
        """Yearly trend JSON spans current year - 4, and matrix table renders."""
        for yr in (2024, 2025, 2026):
            CatatanIndikator.objects.create(
                indikator=self.indikator, bulan=1, tahun=yr,
                nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'))

        url = reverse('akreditasi:dashboard') + f'?mutu_indikator={self.indikator.pk}&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()

        self.assertContains(resp, 'pills-tahunan-tab')
        self.assertContains(resp, 'pills-matriks-tab')
        self.assertContains(resp, 'chartTahunanMulti')
        self.assertContains(resp, 'tabelMatriksRekap')
        self.assertIn('[2022, 2023, 2024, 2025, 2026]', content)

    def test_dashboard_unknown_indikator_param_falls_back(self):
        """A bogus mutu_indikator id must not crash and must fall back to aggregate mode."""
        url = reverse('akreditasi:dashboard') + '?mutu_indikator=999999&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'chartMutuBulanan')

    def test_dashboard_chart_datalabels_and_drilldown_modal_markup(self):
        """Value-label plugin and the drill-down modal are rendered."""
        resp = self.client.get(reverse('akreditasi:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'modalDrilldownMutu')
        self.assertContains(resp, 'afterDatasetsDraw')
        self.assertContains(resp, 'dd-btn-pdca')

    # ── Task 4: risk form prefill from drill-down ──────────────────────────

    def test_risiko_input_prefill_from_chart_drilldown(self):
        """Drill-down link params pre-fill the risk form (indicator, unit, problem text)."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=8, tahun=2026,
            nilai_numerator=Decimal('60'), nilai_denominator=Decimal('100'))

        url = reverse('akreditasi:risiko_input') + f'?indikator={self.indikator.pk}&bulan=8&tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('prefill_indikator_id', content)
        self.assertIn('60.0', content)
        self.assertIn('Capaian', content)

        # Bogus params must not crash
        bad = reverse('akreditasi:risiko_input') + '?indikator=999999&bulan=99&tahun=abc'
        self.assertEqual(self.client.get(bad).status_code, 200)


    # ── Per-indicator charts on /indikator-mutu/ ───────────────────────────

    def test_mutu_dashboard_dropdown_lists_all_indicators_and_flags_empty(self):
        """Every indicator in the tier is listed; the unmeasured ones carry a marker."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'))

        empty = IndikatorMutu.objects.create(
            nama_indikator='Belum Ada Data', kode_indikator='INM-99',
            unit=self.unit, jenis='NASIONAL', dimensi_mutu='AMAN',
            numerator='a', denominator='b', target_nilai=Decimal('80.00'), aktif=True)

        resp = self.client.get('/indikator-mutu/?jenis=INM&tahun=2026')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        m = re.search(r'<select name="indikator".*?</select>', html, re.S)
        self.assertIsNotNone(m, 'dropdown indikator tidak dirender')
        opts = re.findall(r'<option value="(\d+)"', m.group(0))
        # Kontrak baru: indikator tanpa data tetap muncul, hanya ditandai.
        self.assertIn(str(self.indikator.pk), opts)
        self.assertIn(str(empty.pk), opts)
        self.assertIn('belum ada data', m.group(0))

    def test_mutu_dashboard_empty_tier_falls_back_to_all_indicators(self):
        """A tier with zero catatan still lists its active indicators."""
        IndikatorMutu.objects.create(
            nama_indikator='Unit Tanpa Data', kode_indikator='IMU-99',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='a', denominator='b', target_nilai=Decimal('80.00'), aktif=True)

        resp = self.client.get('/indikator-mutu/?jenis=IMU&tahun=2026')
        self.assertEqual(resp.status_code, 200)
        m = re.search(r'<select name="indikator".*?</select>', resp.content.decode(), re.S)
        self.assertIsNotNone(m)
        self.assertIn('IMU-99', m.group(0))

    def test_mutu_dashboard_single_indicator_series_and_colors(self):
        """Selecting one indicator charts its own monthly capaian, not the average."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('90'), nilai_denominator=Decimal('100'))
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=2, tahun=2026,
            nilai_numerator=Decimal('70'), nilai_denominator=Decimal('100'))

        url = f'/indikator-mutu/?jenis=INM&tahun=2026&indikator={self.indikator.pk}'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        self.assertRegex(html, r'const indData\s*=\s*\[90\.0, 70\.0, null')
        self.assertRegex(html, r'const indTarget\s*=\s*85\.0;')
        self.assertRegex(html, r'const indColors\s*=\s*\["#198754", "#dc3545"')

    def test_mutu_dashboard_max_indicator_flips_colors(self):
        """arah_target='MAX' (lower is better) is green when capaian <= target."""
        ind_max = IndikatorMutu.objects.create(
            nama_indikator='Waktu Tunggu IGD', kode_indikator='IMRS-98',
            unit=self.unit, jenis='IMP_RS', dimensi_mutu='EFISIEN',
            numerator='jumlah kasus', denominator='total kasus',
            target_nilai=Decimal('5.00'), satuan='Menit', arah_target='MAX', aktif=True)
        CatatanIndikator.objects.create(
            indikator=ind_max, bulan=1, tahun=2026,
            nilai_numerator=Decimal('4'), nilai_denominator=Decimal('100'))

        url = f'/indikator-mutu/?jenis=IMRS&tahun=2026&indikator={ind_max.pk}'
        self.assertRegex(self.client.get(url).content.decode(), r'const indColors\s*=\s*\["#198754"')

        CatatanIndikator.objects.filter(indikator=ind_max, bulan=1, tahun=2026).update(
            nilai_numerator=Decimal('8'))
        self.assertRegex(self.client.get(url).content.decode(), r'const indColors\s*=\s*\["#dc3545"')

    def test_mutu_dashboard_unknown_indicator_falls_back(self):
        """A bogus or foreign indikator pk must render 200 in aggregate mode."""
        resp = self.client.get('/indikator-mutu/?jenis=INM&tahun=2026&indikator=999999')
        self.assertEqual(resp.status_code, 200)
        self.assertRegex(resp.content.decode(), r'const hasInd\s*=\s*false;')

    def test_dashboard_jenis_canonical_lists_all_tier_indicators(self):
        """Category INM must resolve to the legacy NASIONAL rows, data or no data."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'))
        empty = IndikatorMutu.objects.create(
            nama_indikator='Belum Ada Data', kode_indikator='INM-98',
            unit=self.unit, jenis='NASIONAL', dimensi_mutu='AMAN',
            numerator='a', denominator='b', target_nilai=Decimal('80.00'), aktif=True)

        resp = self.client.get(reverse('akreditasi:dashboard') + '?mutu_jenis=INM&mutu_tahun=2026')
        self.assertEqual(resp.status_code, 200)
        m = re.search(r'<select name="mutu_indikator".*?</select>', resp.content.decode(), re.S)
        self.assertIsNotNone(m)
        opts = re.findall(r'<option value="(\d+)"', m.group(0))
        # Kontrak baru: tier lengkap ditampilkan; yang belum diukur ditandai.
        self.assertIn(str(self.indikator.pk), opts)
        self.assertIn(str(empty.pk), opts)
        self.assertIn('belum ada data', m.group(0))

    def _mk(self, bulan, num, den, catatan):
        return CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=bulan, tahun=2026,
            nilai_numerator=Decimal(str(num)), nilai_denominator=Decimal(str(den)),
            catatan=catatan,
        )

    def test_tooltip_meta_json_carries_numerator_denominator_and_note(self):
        """Tooltip panjang butuh num/den/catatan per bulan, bukan hanya capaian."""
        self._mk(1, '95.11', '135.00', 'Data evaluasi bulan 1/2026 - INM-01')
        self._mk(2, '70.00', '100.00', 'Ada kekurangan sarana handrub')
        url = f'/indikator-mutu/?jenis=INM&tahun=2026&indikator={self.indikator.pk}'
        html = self.client.get(url).content.decode()
        m = re.search(r'const indMeta\s*=\s*(\[.*?\]);', html, re.S)
        self.assertIsNotNone(m, 'const indMeta tidak dirender')
        meta = json.loads(m.group(1))
        self.assertEqual(len(meta), 12)
        jan = meta[0]
        self.assertIsNotNone(jan, 'Bulan 1 harus punya data')
        for key in ('capaian', 'num', 'den', 'catatan', 'tercapai'):
            self.assertIn(key, jan)
        self.assertEqual(jan['num'], 95.11)
        self.assertEqual(jan['den'], 135.0)
        self.assertIn('INM-01', jan['catatan'])
        self.assertIsNone(meta[5], 'Bulan tanpa data harus None')
        self.assertFalse(jan['tercapai'], '70.45% < target 85 -> tidak tercapai')

    def test_tooltip_indicator_labels_present(self):
        """Label rumus/PJ/dimensi untuk footer tooltip per-indikator."""
        self._mk(1, '95.11', '135.00', 'catatan')
        url = f'/indikator-mutu/?jenis=INM&tahun=2026&indikator={self.indikator.pk}'
        html = self.client.get(url).content.decode()
        self.assertRegex(html, r'const indNama\s*=\s*"[^"]+";')
        self.assertRegex(html, r'const indNumLabel\s*=\s*"[^"]+";')
        self.assertRegex(html, r'const indDenLabel\s*=\s*"[^"]+";')
        self.assertRegex(html, r'const indDimensi\s*=\s*"Aman";')
        self.assertIn('indTooltipLines', html)
        self.assertIn('Panel teks panjang', html)

    def test_dashboard_tooltip_meta_lists_missed_indicators(self):
        """Agregat: meta per bulan menyebut indikator yang di bawah target."""
        self._mk(1, '95.11', '135.00', 'catatan')
        url = f'/?mutu_jenis=INM&mutu_tahun=2026&mutu_indikator={self.indikator.pk}'
        html = self.client.get(url).content.decode()
        m = re.search(r'const mutuMeta\s*=\s*(\[.*?\]);', html, re.S)
        self.assertIsNotNone(m, 'const mutuMeta tidak dirender')
        meta = json.loads(m.group(1))
        self.assertEqual(len(meta), 12)
        jan = meta[0]
        self.assertIsNotNone(jan)
        self.assertEqual(jan['n'], 1)
        self.assertEqual(jan['ok'], 0)
        # Setiap baris mencantumkan indikator penyumbang beserta capaian dan
        # targetnya sendiri, jadi angka rata-rata bisa dilacak ke pengukurannya.
        row = jan['rows'][0]
        self.assertEqual(row['kode'], 'INM-01')
        self.assertFalse(row['ok'])
        self.assertAlmostEqual(row['capaian'], round(95.11 / 135.00 * 100, 1), places=1)
        self.assertAlmostEqual(row['target'], float(self.indikator.target_nilai), places=1)

    def test_dashboard_tooltip_has_formula_and_name(self):
        self._mk(1, '95.11', '135.00', 'catatan')
        url = f'/?mutu_jenis=INM&mutu_tahun=2026&mutu_indikator={self.indikator.pk}'
        html = self.client.get(url).content.decode()
        self.assertRegex(html, r'const mutuNama\s*=\s*"[^"]*INM-01[^"]*";')
        m = re.search(r'const mutuRumus\s*=\s*"(.*?)";', html)
        self.assertIsNotNone(m)
        self.assertIn('u00f7', m.group(1))  # ÷ ter-escapejs sebagai \u00f7
        self.assertIn('Di bawah target', html)

    def test_dropdown_options_show_full_name_and_title_attr(self):
        """Nama panjang tidak dipotong; title memuat detail indikator."""
        self._mk(1, '95.11', '135.00', 'catatan')
        url = '/indikator-mutu/?jenis=INM&tahun=2026'
        html = self.client.get(url).content.decode()
        self.assertRegex(html, r'<option value="\d+" title="\[INM-01\][^"]*Target 85[^"]*"')
        self.assertIn(self.indikator.nama_indikator, html)


class IndikatorDropdownTanpaDataTest(TestCase):
    """Indikator tanpa pengukuran tetap muncul di dropdown, dengan penanda."""

    def setUp(self):
        self.user = User.objects.create_superuser('admin_dd', 'dd@rs.id', 'secret123')
        self.unit = UnitKerja.objects.create(name='Bangsal Dropdown', code='DD-01', tipe_unit='RUANGAN')
        self.ind_kosong = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Identifikasi Pasien', kode_indikator='DD-IMU-01',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=Decimal('100.00'), satuan='%',
        )
        self.ind_berisi = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Kebersihan Tangan', kode_indikator='DD-INM-01',
            unit=None, jenis='NASIONAL', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=Decimal('85.00'), satuan='%',
        )
        CatatanIndikator.objects.create(
            indikator=self.ind_berisi, tahun=2026, bulan=1,
            nilai_numerator=Decimal('90'), nilai_denominator=Decimal('100'),
        )
        self.client.force_login(self.user)

    def test_indikator_tanpa_data_tetap_ada_di_dropdown(self):
        html = self.client.get('/?mutu_jenis=IMU&mutu_tahun=2026').content.decode()
        self.assertIn('DD-IMU-01', html)
        self.assertIn('belum ada data', html)

    def test_kategori_legacy_tidak_ditawarkan(self):
        html = self.client.get('/?mutu_tahun=2026').content.decode()
        self.assertNotIn('IMP Unit (Legacy)', html)
        self.assertNotIn('IMP Rumah Sakit (Legacy)', html)

    def test_api_mutu_indikator_menghormati_jenis(self):
        r = self.client.get('/api/mutu-indikator/?jenis=IMU&tahun=2026')
        kode = [i['kode'] for i in r.json()['indikator']]
        self.assertIn('DD-IMU-01', kode)
        self.assertNotIn('DD-INM-01', kode)

    def test_arah_target_dirender_sebagai_simbol(self):
        self.ind_berisi.arah_target = 'MAX'
        self.ind_berisi.save(update_fields=['arah_target'])
        html = self.client.get(f'/?mutu_indikator={self.ind_berisi.pk}&mutu_tahun=2026').content.decode()
        # Simbol perbandingan, bukan kode arah mentah; angkanya tetap ter-lokalisasi.
        self.assertNotRegex(html, r'MIN[\d,\.]')
        self.assertIn('&le;', html)


class DashboardCategoryIndicatorConsistencyTest(TestCase):
    """A category change must not leave the dashboard acting on a foreign indicator."""

    def setUp(self):
        self.user = User.objects.create_superuser('admin_filter', 'admin_filter@rs.id', 'secret123')
        self.client = Client()
        self.client.force_login(self.user)
        self.unit = UnitKerja.objects.create(name='IGD Filter', code='IGD-F', tipe_unit='RUANGAN')

        self.inm = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Hand Hygiene', kode_indikator='INM-F1',
            unit=self.unit, jenis='NASIONAL', dimensi_mutu='AMAN',
            numerator='Patuh', denominator='Total peluang',
            target_nilai=Decimal('85.00'), satuan='%', aktif=True,
        )
        self.imrs = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Identifikasi Pasien', kode_indikator='IMRS-F1',
            unit=self.unit, jenis='IMRS', dimensi_mutu='AMAN',
            numerator='Patuh', denominator='Total kunjungan',
            target_nilai=Decimal('100.00'), satuan='%', aktif=True,
        )
        for ind in (self.inm, self.imrs):
            CatatanIndikator.objects.create(
                indikator=ind, bulan=1, tahun=2026,
                nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'),
            )

    def _indikator_select(self, html):
        m = re.search(r'<select name="mutu_indikator".*?</select>', html, re.S)
        self.assertIsNotNone(m, 'select mutu_indikator tidak dirender')
        return m.group(0)

    def _mutu_ind_id(self, html):
        m = re.search(r'MUTU_IND_ID\s*=\s*"([^"]*)"', html)
        self.assertIsNotNone(m, 'const MUTU_IND_ID tidak dirender')
        return m.group(1)

    def test_stale_indicator_id_is_cleared_from_client_context(self):
        """An INM id carried into an IMRS view must not reach the drill-down/PDCA link."""
        url = (reverse('akreditasi:dashboard')
               + f'?mutu_jenis=IMRS&mutu_tahun=2026&mutu_indikator={self.inm.pk}')
        html = self.client.get(url).content.decode()
        self.assertEqual(self._mutu_ind_id(html), '',
                         'MUTU_IND_ID masih memuat indikator dari kategori lain')
        self.assertNotIn(f'value="{self.inm.pk}"', self._indikator_select(html),
                         'indikator INM masih ditawarkan di bawah filter IMRS')

    def test_valid_indicator_in_same_category_stays_selected(self):
        """The fix must not throw away a legitimate selection."""
        url = (reverse('akreditasi:dashboard')
               + f'?mutu_jenis=IMRS&mutu_tahun=2026&mutu_indikator={self.imrs.pk}')
        html = self.client.get(url).content.decode()
        self.assertEqual(self._mutu_ind_id(html), str(self.imrs.pk))
        self.assertRegex(self._indikator_select(html),
                         rf'<option value="{self.imrs.pk}"[^>]*\bselected\b')

    def test_category_select_clears_indicator_before_submit(self):
        """The category/unit/year selects must reset the indicator selection explicitly."""
        html = self.client.get(reverse('akreditasi:dashboard')).content.decode()
        self.assertRegex(html, r'name="mutu_jenis"[^>]*onchange="arimaMutuFilterChange\(this\)"')
        self.assertRegex(html, r'name="mutu_tahun"[^>]*onchange="arimaMutuFilterChange\(this\)"')
        self.assertIn('window.arimaMutuFilterChange', html)
