import json
from decimal import Decimal

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

    def test_evaluasi_offers_link_when_indikator_missing(self):
        """Risiko tanpa indikator harus punya UI penautan di G.1, bukan banner read-only."""
        self.risiko.indikator_mutu_terkait = None
        self.risiko.target_capaian_indikator = None
        self.risiko.save()
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Belum ditautkan ke Indikator Mutu formal')
        self.assertContains(resp, 'name="indikator_mutu_terkait"')
        self.assertContains(resp, 'id="link-indikator-select"')
        self.assertContains(resp, self.indikator.nama_indikator)

    def test_evaluasi_hides_link_ui_when_already_linked(self):
        """Sudah tertaut -> select penautan tidak dirender (tampilan lama tak berubah)."""
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertNotContains(resp, 'id="link-indikator-select"')

    def test_evaluasi_post_links_indikator(self):
        """POST menyimpan tautan indikator + target dari halaman evaluasi."""
        self.risiko.indikator_mutu_terkait = None
        self.risiko.target_capaian_indikator = None
        self.risiko.save()
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.post(url, data={
            'indikator_mutu_terkait': str(self.indikator.pk),
            'target_capaian_indikator': '90',
            'dampak_residual': '2',
            'probabilitas_residual': '1',
            'status_rtl': 'BELUM',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.risiko.refresh_from_db()
        self.assertEqual(self.risiko.indikator_mutu_terkait_id, self.indikator.pk)
        self.assertEqual(float(self.risiko.target_capaian_indikator), 90.0)

    def test_evaluasi_post_without_link_field_keeps_existing_link(self):
        """POST lama (tanpa field indikator) tidak boleh menghapus tautan."""
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        self.client.post(url, data={
            'capaian_nilai': '92.5',
            'dampak_residual': '2',
            'probabilitas_residual': '1',
            'status_rtl': 'BELUM',
        }, follow=True)
        self.risiko.refresh_from_db()
        self.assertEqual(self.risiko.indikator_mutu_terkait_id, self.indikator.pk)

    def test_evaluasi_candidates_include_parent_unit_indicators(self):
        """Indikator milik unit INDUK harus muncul sebagai kandidat (kasus Bangsal->IRIN)."""
        parent = UnitKerja.objects.create(name='Instalasi Rawat Inap', code='IRIN-01', level=2)
        child = UnitKerja.objects.create(name='Bangsal Anak', code='BANAK-01', level=3, parent=parent)
        ind_parent = IndikatorMutu.objects.create(
            kode_indikator='IMP-UNIT-RANAP-02',
            nama_indikator='Angka Kejadian Phlebitis',
            jenis='IMP_UNIT', dimensi_mutu='KESELAMATAN',
            target_nilai=1.5, arah_target='MAX', satuan='%o', unit=parent,
        )
        r = RisikoUnit.objects.create(
            unit=child, periode='TAHUNAN', tahun=2026,
            jenis_risiko='Phlebitis', kategori_risiko='KLINIS',
            dampak=3, probabilitas=3, deskripsi_risiko='x',
            strategi_mitigasi='KURANGI', rencana_aksi='1. a', pj_mitigasi='Ka',
            status='DO', created_by=self.user,
        )
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': r.pk})
        resp = self.client.get(url)
        self.assertContains(resp, 'Angka Kejadian Phlebitis')
        self.assertContains(resp, 'IMP-UNIT-RANAP-02')

    def test_evaluasi_candidates_fallback_inm_when_no_local(self):
        """Unit tanpa indikator lokal & tanpa induk berindikator -> fallback INM."""
        lone = UnitKerja.objects.create(name='Unit Tanpa Indikator', code='NOL-01', level=3)
        r = RisikoUnit.objects.create(
            unit=lone, periode='TAHUNAN', tahun=2026,
            jenis_risiko='X', kategori_risiko='MANAJERIAL',
            dampak=2, probabilitas=2, deskripsi_risiko='x',
            strategi_mitigasi='KURANGI', rencana_aksi='1. a', pj_mitigasi='Ka',
            status='DO', created_by=self.user,
        )
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': r.pk})
        resp = self.client.get(url)
        self.assertContains(resp, 'INM-UGD-01')

    # ── Filter kandidat: hanya indikator yang berkaitan dengan rencana ──

    def test_candidates_only_include_planned_indicators(self):
        """Indikator yang tak pernah direncanakan unit ini tidak muncul di dropdown."""
        unplanned = IndikatorMutu.objects.create(
            kode_indikator='INM-UGD-02',
            nama_indikator='Kepatuhan Identifikasi Pasien UGD',
            jenis='NASIONAL', dimensi_mutu='KESELAMATAN',
            target_nilai=100.0, arah_target='MIN', satuan='%', unit=self.unit,
        )
        # Risiko lain di unit yang sama tetap tertaut -> set rencana tidak kosong.
        RisikoUnit.objects.create(
            unit=self.unit, periode='TAHUNAN', tahun=2026,
            jenis_risiko='Risiko lain UGD', kategori_risiko='KLINIS',
            dampak=3, probabilitas=3, deskripsi_risiko='y',
            strategi_mitigasi='KURANGI', rencana_aksi='1. a', pj_mitigasi='Ka',
            status='DO', created_by=self.user,
            indikator_mutu_terkait=self.indikator,
            target_capaian_indikator=90.0,
        )
        self.risiko.indikator_mutu_terkait = None
        self.risiko.target_capaian_indikator = None
        self.risiko.save()

        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertContains(resp, self.indikator.nama_indikator)
        self.assertNotContains(resp, unplanned.nama_indikator)
        self.assertContains(resp, 'Hanya indikator yang sudah direncanakan')
        self.assertContains(resp, 'data-target-rencana="90')

    def test_candidates_fall_back_when_unit_has_no_plan(self):
        """Unit tanpa rencana -> dropdown tetap terisi (perilaku lama), bukan kosong."""
        self.risiko.indikator_mutu_terkait = None
        self.risiko.target_capaian_indikator = None
        self.risiko.save()

        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="link-indikator-select"')
        self.assertContains(resp, 'data-target=')
        self.assertContains(resp, 'belum memiliki indikator pada tahap perencanaan')
        self.assertContains(resp, self.indikator.nama_indikator)

    def test_candidates_include_ancestor_unit_plan(self):
        """Rencana di unit INDUK harus ikut jadi kandidat (kasus Bangsal Anak -> IRIN)."""
        parent = UnitKerja.objects.create(name='Instalasi Rawat Inap', code='IRIN-T', level=2)
        ind_parent = IndikatorMutu.objects.create(
            kode_indikator='IMP-PARENT-01',
            nama_indikator='Kepatuhan Double Check Obat High Alert',
            jenis='IMP_UNIT', dimensi_mutu='KESELAMATAN',
            target_nilai=100.0, arah_target='MIN', satuan='%', unit=parent,
        )
        # Rencana dibuat oleh risiko di unit induk.
        RisikoUnit.objects.create(
            unit=parent, periode='TAHUNAN', tahun=2026,
            jenis_risiko='High alert', kategori_risiko='KLINIS',
            dampak=3, probabilitas=3, deskripsi_risiko='z',
            strategi_mitigasi='KURANGI', rencana_aksi='1. a', pj_mitigasi='Ka',
            status='DO', created_by=self.user,
            indikator_mutu_terkait=ind_parent,
            target_capaian_indikator=100.0,
        )
        child = UnitKerja.objects.create(name='Bangsal Anak', code='BANAK-T', level=3, parent=parent)
        rc = RisikoUnit.objects.create(
            unit=child, periode='TAHUNAN', tahun=2026,
            jenis_risiko='Obat high alert', kategori_risiko='KLINIS',
            dampak=3, probabilitas=3, deskripsi_risiko='w',
            strategi_mitigasi='KURANGI', rencana_aksi='1. a', pj_mitigasi='Ka',
            status='DO', created_by=self.user,
        )
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': rc.pk})
        resp = self.client.get(url)
        self.assertContains(resp, 'IMP-PARENT-01')
        self.assertContains(resp, 'Hanya indikator yang sudah direncanakan')

    def test_manual_marker_renders_as_hint(self):
        """Nama indikator yang dulu diketik manual muncul sebagai hint, bukan hilang."""
        self.risiko.indikator_mutu_terkait = None
        self.risiko.target_capaian_indikator = None
        self.risiko.deskripsi_risiko += (
            "\n\n[Indikator Mutu Manual: kepatuhan double-check obat high alert]"
        )
        self.risiko.save()

        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertContains(resp, 'kepatuhan double-check obat high alert')
        self.assertContains(resp, 'Indikator yang Anda tulis manual')

class EvaluasiCapaianPolaritasTest(TestCase):
    """Polaritas + gap harus benar untuk kedua arah, dengan dan tanpa master."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin_pol', password='secret123', email='admin_pol@test.com'
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.unit = UnitKerja.objects.create(
            name='Bangsal Pol', code='POL-01', level=3
        )
        self.ind_max = IndikatorMutu.objects.create(
            nama_indikator='Angka Kejadian Phlebitis', kode_indikator='POL-MAX',
            jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='Jumlah kejadian', denominator='Jumlah pasien',
            target_nilai=Decimal('1.50'), satuan='permil', arah_target='MAX',
            unit=self.unit,
        )

    def _mk(self, **kw):
        base = dict(unit=self.unit, periode='TAHUNAN', tahun=2026,
                    jenis_risiko='Angka kejadian phlebitis bangsal pol',
                    kategori_risiko='KLINIS', dampak=3, probabilitas=3,
                    deskripsi_risiko='x', strategi_mitigasi='KURANGI',
                    rencana_aksi='1. a', pj_mitigasi='Ka', status='DO',
                    created_by=self.user)
        base.update(kw)
        return RisikoUnit.objects.create(**base)

    def test_lower_is_better_di_bawah_target_tercapai(self):
        """Phlebitis 1.00 dengan target <= 1.50 dianggap tercapai (gap positif)."""
        r = self._mk(indikator_mutu_terkait=self.ind_max, capaian_nilai=Decimal('1.00'))
        ev = r.capaian_evaluasi
        self.assertEqual(ev['arah'], 'MAX')
        self.assertTrue(ev['tercapai'])
        self.assertAlmostEqual(ev['gap'], 0.5)

    def test_lower_is_better_di_atas_target_tidak_tercapai(self):
        """Phlebitis 2.50 melebihi target <= 1.50 (gap negatif)."""
        r = self._mk(indikator_mutu_terkait=self.ind_max, capaian_nilai=Decimal('2.50'))
        ev = r.capaian_evaluasi
        self.assertFalse(ev['tercapai'])
        self.assertAlmostEqual(ev['gap'], -1.0)

    def test_arah_manual_menimpa_master_saat_belum_tertaut(self):
        """Risiko belum tertaut: arah_capaian manual dipakai, bukan fallback 'MIN'."""
        r = self._mk(arah_capaian='MAX', target_capaian_indikator=Decimal('1.50'),
                     capaian_nilai=Decimal('0.80'))
        ev = r.capaian_evaluasi
        self.assertEqual(ev['arah'], 'MAX')
        self.assertTrue(ev['tercapai'])
        self.assertEqual(ev['sumber'], 'rencana')

    def test_tanpa_target_tidak_dianggap_gagal(self):
        """Tanpa target, status None — bukan diam-diam dianggap tidak tercapai."""
        r = self._mk(capaian_nilai=Decimal('90'))
        ev = r.capaian_evaluasi
        self.assertIsNone(ev['tercapai'])
        self.assertIsNone(ev['target'])
        self.assertIsNone(r.capaian_status_label)

    def test_target_rencana_menang_atas_master(self):
        """Target yang diisi di tahap Plan menimpa target master indikator."""
        r = self._mk(indikator_mutu_terkait=self.ind_max,
                     target_capaian_indikator=Decimal('0.50'),
                     capaian_nilai=Decimal('1.00'))
        ev = r.capaian_evaluasi
        self.assertEqual(ev['sumber'], 'rencana')
        self.assertFalse(ev['tercapai'])

    def test_monev_menampilkan_le_bukan_ge_untuk_indikator_max(self):
        """Tabel MONEV harus menulis simbol arah dari resolver, bukan hardcode '>='."""
        self._mk(indikator_mutu_terkait=self.ind_max, capaian_nilai=Decimal('1.00'))
        resp = self.client.get(reverse('akreditasi:risiko_monev') + '?tahun=2026')
        html = resp.content.decode()
        self.assertIn('Target: &le;1.5permil', html)
        self.assertIn('Tercapai', html)
        self.assertNotIn('Target: &ge;1.5permil', html)

