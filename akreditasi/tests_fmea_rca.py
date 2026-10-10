"""
Test suite untuk Section E — Hiliran Metode Evaluasi Mendalam (FMEA & RCA).

Mencakup:
1. Model RisikoUnit: field FMEA/RCA, property rpn_calc, is_fmea, is_rca.
2. Migration 0031: field baru terpasang.
3. Form risiko_input: POST dengan metode FMEA & RCA tersimpan benar.
4. View risiko_fmea_rca: hub menampilkan data, filter, KPI.
5. Detail & Laporan: card FMEA/RCA ter-render.
6. AI endpoints: validasi payload & permission.
7. Seed command: 45 indikator + 45 risiko untuk 9 unit.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from akreditasi.models import UnitKerja
from akreditasi.risiko_models import RisikoUnit, IndikatorMutu


class FmeaRcaModelTest(TestCase):
    """Test model fields, properties, dan migration."""

    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(code='TEST-IGD', name='Test IGD')
        cls.user = User.objects.create_user('tester_model', password='x')

    def _mk(self, **kw):
        base = dict(
            unit=self.unit, tahun=2026, periode='TAHUNAN',
            kategori_risiko='KLINIS',
            jenis_risiko='Risiko uji',
            deskripsi_risiko='Deskripsi uji',
            dampak=4, probabilitas=3,
            strategi_mitigasi='KURANGI',
            rencana_aksi='Rencana uji',
            pj_mitigasi='Tester',
        )
        base.update(kw)
        return RisikoUnit.objects.create(**base)

    def test_new_fields_exist(self):
        """Semua field Section E terpasang di model."""
        for f in ['metode_evaluasi', 'tim_evaluasi', 'failure_mode_fmea',
                  'akar_masalah_rca', 'tindakan_korektif_rca',
                  'rpn_fmea', 'tanggal_evaluasi']:
            self.assertTrue(
                hasattr(RisikoUnit, f) or f in [x.name for x in RisikoUnit._meta.fields],
                f'Field {f} tidak ada di model RisikoUnit'
            )

    def test_default_metode_evaluasi_is_standar(self):
        r = self._mk()
        self.assertEqual(r.metode_evaluasi, 'STANDAR')
        self.assertFalse(r.is_fmea)
        self.assertFalse(r.is_rca)
        self.assertIsNone(r.rpn_calc)

    def test_rpn_calc_auto_for_fmea(self):
        """RPN otomatis = dampak × probabilitas × 5 bila tidak diisi manual."""
        r = self._mk(metode_evaluasi='FMEA', dampak=5, probabilitas=4)
        self.assertEqual(r.rpn_calc, 5 * 4 * 5)
        self.assertTrue(r.is_fmea)

    def test_rpn_calc_uses_manual_value(self):
        """RPN manual (rpn_fmea) menang atas kalkulasi otomatis."""
        r = self._mk(metode_evaluasi='FMEA', rpn_fmea=125)
        self.assertEqual(r.rpn_calc, 125)

    def test_rca_has_no_rpn(self):
        r = self._mk(metode_evaluasi='RCA', akar_masalah_rca='Mengapa 1: x')
        self.assertIsNone(r.rpn_calc)
        self.assertTrue(r.is_rca)

    def test_metode_evaluasi_badge(self):
        self.assertEqual(self._mk(metode_evaluasi='FMEA').metode_evaluasi_badge[2], 'FMEA Proaktif')
        self.assertEqual(self._mk(metode_evaluasi='RCA').metode_evaluasi_badge[2], 'RCA Reaktif')
        self.assertEqual(self._mk().metode_evaluasi_badge[2], 'Standar PDCA')


class FmeaRcaFormPostTest(TestCase):
    """Test POST form risiko dengan metode FMEA & RCA."""

    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(code='TEST-IGD2', name='Test IGD 2')
        cls.user = User.objects.create_user('tester_form', password='x')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        self.base = {
            'unit': str(self.unit.id), 'tahun': '2026', 'periode': 'TAHUNAN',
            'kategori_risiko': 'KLINIS',
            'masalah': 'Masalah uji', 'data': 'Data uji',
            'deskripsi_risiko': 'Deskripsi uji',
            'dampak': '5', 'probabilitas': '4',
            'strategi_mitigasi': 'KURANGI',
            'rencana_aksi': 'Rencana uji', 'pj_mitigasi': 'Tester',
            'biaya_mitigasi': '0',
        }

    def test_post_fmea_saves_all_fields(self):
        payload = dict(self.base)
        payload.update({
            'jenis_risiko': 'UJI FMEA',
            'metode_evaluasi': 'FMEA',
            'tim_evaluasi_fmea': 'Ka. IGD, IPCN',
            'rpn_fmea': '100',
            'failure_mode_fmea': 'Mode: salah dosis\nEfek: overdosis',
            'tanggal_evaluasi': '2026-10-10',
        })
        resp = self.client.post(reverse('akreditasi:risiko_input'), payload)
        self.assertEqual(resp.status_code, 302)

        r = RisikoUnit.objects.get(jenis_risiko='UJI FMEA')
        self.assertEqual(r.metode_evaluasi, 'FMEA')
        self.assertEqual(r.tim_evaluasi, 'Ka. IGD, IPCN')
        self.assertEqual(r.rpn_fmea, 100)
        self.assertEqual(r.rpn_calc, 100)
        self.assertIn('salah dosis', r.failure_mode_fmea)
        self.assertEqual(r.tanggal_evaluasi, date(2026, 10, 10))

    def test_post_rca_saves_all_fields(self):
        payload = dict(self.base)
        payload.update({
            'jenis_risiko': 'UJI RCA',
            'metode_evaluasi': 'RCA',
            'tim_evaluasi_rca': 'Ketua Komite Mutu',
            'akar_masalah_rca': 'Mengapa 1: x\nMengapa 5: akar sistemik',
            'tindakan_korektif_rca': '1) Revisi SPO',
        })
        resp = self.client.post(reverse('akreditasi:risiko_input'), payload)
        self.assertEqual(resp.status_code, 302)

        r = RisikoUnit.objects.get(jenis_risiko='UJI RCA')
        self.assertEqual(r.metode_evaluasi, 'RCA')
        self.assertEqual(r.tim_evaluasi, 'Ketua Komite Mutu')
        self.assertIn('akar sistemik', r.akar_masalah_rca)
        self.assertIn('Revisi SPO', r.tindakan_korektif_rca)
        # RCA tidak boleh menyimpan RPN / failure mode
        self.assertIsNone(r.rpn_fmea)
        self.assertEqual(r.failure_mode_fmea, '')

    def test_invalid_metode_falls_back_to_standar(self):
        payload = dict(self.base)
        payload.update({'jenis_risiko': 'UJI INVALID', 'metode_evaluasi': 'HACKED'})
        self.client.post(reverse('akreditasi:risiko_input'), payload)
        r = RisikoUnit.objects.get(jenis_risiko='UJI INVALID')
        self.assertEqual(r.metode_evaluasi, 'STANDAR')

    def test_standar_mode_ignores_fmea_fields(self):
        """Bila metode STANDAR, field FMEA/RCA tidak tersimpan."""
        payload = dict(self.base)
        payload.update({
            'jenis_risiko': 'UJI STANDAR',
            'metode_evaluasi': 'STANDAR',
            'failure_mode_fmea': 'harus diabaikan',
            'akar_masalah_rca': 'harus diabaikan juga',
        })
        self.client.post(reverse('akreditasi:risiko_input'), payload)
        r = RisikoUnit.objects.get(jenis_risiko='UJI STANDAR')
        self.assertEqual(r.metode_evaluasi, 'STANDAR')
        self.assertEqual(r.failure_mode_fmea, '')
        self.assertEqual(r.akar_masalah_rca, '')


class FmeaRcaViewTest(TestCase):
    """Test hub, detail, dan laporan menampilkan data FMEA/RCA."""

    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(code='TEST-IGD3', name='Test IGD 3')
        cls.user = User.objects.create_user('tester_view', password='x')
        cls.fmea = RisikoUnit.objects.create(
            unit=cls.unit, tahun=2026, periode='TAHUNAN',
            kategori_risiko='KLINIS', jenis_risiko='Risiko FMEA UJI',
            deskripsi_risiko='d', dampak=5, probabilitas=4,
            strategi_mitigasi='KURANGI', rencana_aksi='ra', pj_mitigasi='pj',
            metode_evaluasi='FMEA', tim_evaluasi='Tim FMEA UJI',
            failure_mode_fmea='Mode kegagalan uji', rpn_fmea=100,
        )
        cls.rca = RisikoUnit.objects.create(
            unit=cls.unit, tahun=2026, periode='TAHUNAN',
            kategori_risiko='KLINIS', jenis_risiko='Risiko RCA UJI',
            deskripsi_risiko='d', dampak=5, probabilitas=3,
            strategi_mitigasi='KURANGI', rencana_aksi='ra', pj_mitigasi='pj',
            metode_evaluasi='RCA', tim_evaluasi='Tim RCA UJI',
            akar_masalah_rca='Akar masalah uji', tindakan_korektif_rca='Korektif uji',
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_hub_returns_200_and_shows_both_tabs(self):
        resp = self.client.get(reverse('akreditasi:risiko_fmea_rca'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for s in ['Kajian FMEA Proaktif', 'Investigasi RCA Reaktif',
                  'Pusat Evaluasi Mendalam', 'Panduan Pemilihan Metode']:
            self.assertIn(s, html)

    def test_hub_shows_fmea_and_rca_records(self):
        html = self.client.get(reverse('akreditasi:risiko_fmea_rca')).content.decode()
        self.assertIn('Risiko FMEA UJI', html)
        self.assertIn('Risiko RCA UJI', html)
        self.assertIn('Tim FMEA UJI', html)
        self.assertIn('Tim RCA UJI', html)

    def test_hub_kpi_counts(self):
        resp = self.client.get(reverse('akreditasi:risiko_fmea_rca'))
        self.assertEqual(resp.context['kpi']['total_fmea'], 1)
        self.assertEqual(resp.context['kpi']['total_rca'], 1)
        self.assertEqual(resp.context['kpi']['rpn_max'], 100)

    def test_hub_filter_by_unit(self):
        resp = self.client.get(reverse('akreditasi:risiko_fmea_rca'), {'unit': self.unit.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['kpi']['total_fmea'], 1)

    def test_detail_shows_fmea_card(self):
        resp = self.client.get(reverse('akreditasi:risiko_detail', kwargs={'risiko_id': self.fmea.pk}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('E. Evaluasi Mendalam — FMEA', html)
        self.assertIn('Mode kegagalan uji', html)

    def test_detail_shows_rca_card(self):
        resp = self.client.get(reverse('akreditasi:risiko_detail', kwargs={'risiko_id': self.rca.pk}))
        html = resp.content.decode()
        self.assertIn('E. Evaluasi Mendalam — RCA', html)
        self.assertIn('Akar masalah uji', html)
        self.assertIn('Korektif uji', html)

    def test_detail_hides_section_e_for_standar(self):
        r = RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TAHUNAN',
            kategori_risiko='KLINIS', jenis_risiko='Risiko Standar UJI',
            deskripsi_risiko='d', dampak=2, probabilitas=2,
            strategi_mitigasi='TERIMA', rencana_aksi='ra', pj_mitigasi='pj',
        )
        html = self.client.get(reverse('akreditasi:risiko_detail', kwargs={'risiko_id': r.pk})).content.decode()
        self.assertNotIn('E. Evaluasi Mendalam', html)

    def test_form_has_section_e_markup(self):
        html = self.client.get(reverse('akreditasi:risiko_input')).content.decode()
        for s in ['E. Hiliran Metode Evaluasi Mendalam', 'panel-metode-fmea',
                  'panel-metode-rca', 'btn-ai-fmea', 'btn-ai-rca',
                  'input_metode_evaluasi']:
            self.assertIn(s, html)

    def test_laporan_shows_rekap_when_fmea_exists(self):
        html = self.client.get(reverse('akreditasi:risiko_laporan')).content.decode()
        self.assertIn('Rekapitulasi Evaluasi Mendalam', html)

    def test_sidebar_has_fmea_rca_link(self):
        html = self.client.get(reverse('akreditasi:risiko_fmea_rca')).content.decode()
        self.assertIn('Metode FMEA', html)


class FmeaRcaAiEndpointTest(TestCase):
    """Test validasi payload endpoint AI FMEA & RCA."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('tester_ai', password='x')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_fmea_endpoint_requires_payload(self):
        resp = self.client.post(reverse('akreditasi:ai_fmea_saran'), data='not json',
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])

    def test_fmea_endpoint_requires_jenis_or_masalah(self):
        resp = self.client.post(reverse('akreditasi:ai_fmea_saran'),
                                data='{"jenis_risiko": "", "masalah": ""}',
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Jenis Risiko atau Masalah', resp.json()['error'])

    def test_rca_endpoint_requires_payload(self):
        resp = self.client.post(reverse('akreditasi:ai_rca_saran'), data='not json',
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_rca_endpoint_requires_jenis_or_masalah(self):
        resp = self.client.post(reverse('akreditasi:ai_rca_saran'),
                                data='{"jenis_risiko": "", "masalah": ""}',
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Jenis Risiko atau Masalah', resp.json()['error'])

    def test_endpoints_require_login(self):
        anon = Client()
        for name in ['akreditasi:ai_fmea_saran', 'akreditasi:ai_rca_saran']:
            resp = anon.post(reverse(name), data='{}', content_type='application/json')
            self.assertIn(resp.status_code, (302, 403), f'{name} tidak dilindungi login')


class FmeaRcaSeedTest(TestCase):
    """Test bahwa seed command membuat data yang benar."""

    # Kode unit yang dibutuhkan seed command (kandidat pertama tiap logical unit).
    # Seed command punya fallback otomatis untuk HD bila belum ada.
    REQUIRED_UNITS = ['IGD', 'ICU', 'ICCU', 'IRJ', 'IRIN', 'LAB-BDRS',
                      'RUANG-BERSALIN-VK', 'IBS']

    def setUp(self):
        # Test DB kosong — buat unit yang dibutuhkan seed command
        for code in self.REQUIRED_UNITS:
            UnitKerja.objects.get_or_create(code=code, defaults={'name': f'Unit {code} Uji'})

    def test_seed_command_creates_data(self):
        from django.core.management import call_command
        from io import StringIO

        # Hapus data agar test bersih (unit tetap ada)
        RisikoUnit.objects.all().delete()
        IndikatorMutu.objects.all().delete()

        out = StringIO()
        call_command('seed_clinical_risk_indicators', stdout=out)
        output = out.getvalue()

        # 9 unit × 5 risiko = 45
        klinis = RisikoUnit.objects.filter(kategori_risiko='KLINIS')
        self.assertEqual(klinis.count(), 45, f'Expected 45 risiko klinis, got {klinis.count()}')

        # Semua risiko harus terhubung ke indikator mutu
        with_ind = klinis.exclude(indikator_mutu_terkait__isnull=True)
        self.assertEqual(with_ind.count(), 45, 'Semua risiko harus terhubung indikator')

        # Setiap risiko punya masalah & data pendukung
        for r in klinis:
            self.assertTrue(r.masalah, f'{r.jenis_risiko} tidak punya masalah')
            self.assertTrue(r.data_pendukung, f'{r.jenis_risiko} tidak punya data pendukung')
            self.assertTrue(r.rencana_aksi, f'{r.jenis_risiko} tidak punya rencana aksi')

        # Idempoten: jalankan dua kali tidak menduplikasi
        call_command('seed_clinical_risk_indicators', stdout=StringIO())
        self.assertEqual(RisikoUnit.objects.filter(kategori_risiko='KLINIS').count(), 45)

        # 9 unit terwakili (via UNIT_CODE_MAP: kode bisa berbeda antar environment)
        from akreditasi.management.commands.seed_clinical_risk_indicators import UNIT_CODE_MAP
        unit_codes = set(klinis.values_list('unit__code', flat=True))
        for logical, candidates in UNIT_CODE_MAP.items():
            matched = [c for c in candidates if c in unit_codes]
            self.assertTrue(matched, f'Unit {logical} tidak ter-seed (kandidat: {candidates})')

    def test_seed_creates_indicators_with_categories(self):
        from django.core.management import call_command
        from io import StringIO

        IndikatorMutu.objects.all().delete()
        call_command('seed_clinical_risk_indicators', stdout=StringIO())

        # Minimal 3 kategori indikator ada
        jenis_set = set(IndikatorMutu.objects.values_list('jenis', flat=True))
        self.assertIn('NASIONAL', jenis_set)
        self.assertIn('IMP_RS', jenis_set)
        self.assertIn('IMP_UNIT', jenis_set)
