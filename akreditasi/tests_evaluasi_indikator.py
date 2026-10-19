import json
from unittest import mock
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import (
    RisikoUnit, IndikatorMutu, TindakLanjutRisiko, CatatanIndikator,
)
from akreditasi.ai_service import generate_evaluasi_risiko
from akreditasi.tests_utils import reset_rate_limit


class EvaluasiIndikatorMutuTest(TestCase):
    def setUp(self):
        reset_rate_limit()
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
        self.assertIn('rencana_aksi_items', resp.context)
        # Ringkasan agregat Input Capaian disiapkan view (belum ada catatan)
        self.assertIn('agregat', resp.context)
        self.assertEqual(resp.context['agregat']['bulan_terisi'], 0)
        self.assertIsNone(resp.context['agregat']['capaian'])
        # Pilihan jenis dokumen tidak lagi dikirim: input inline G.1 dihapus
        self.assertNotIn('jenis_dokumen_choices', resp.context)

        # G.1 Indikator Mutu Callout, gap calculation & AI buttons
        self.assertContains(resp, 'G.1 Capaian Indikator Mutu &amp; Bukti Pendukung')
        self.assertContains(resp, 'Waktu Tanggap Pelayanan Gawat Darurat')
        self.assertContains(resp, 'Input Capaian Bulanan')
        self.assertContains(resp, 'btn-insert-template')
        self.assertContains(resp, 'btn-ai-evaluasi')
        # Form penautan & input capaian/bukti inline sudah tidak dirender
        self.assertNotContains(resp, 'link-indikator-select')
        self.assertNotContains(resp, 'name="capaian_nilai"')
        self.assertNotContains(resp, 'name="jenis_dokumen_capaian"')

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
            # capaian_nilai & jenis_dokumen_capaian tidak dikirim lagi: input
            # inline G.1 dihapus, sumbernya halaman Input Capaian.
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
        # Kedua field itu tidak dikirim form dan tidak diubah oleh POST
        self.assertIsNone(self.risiko.capaian_nilai)
        self.assertEqual(self.risiko.jenis_dokumen_capaian, '')

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

    def test_evaluasi_hints_perencanaan_when_indikator_missing(self):
        """Risiko tanpa indikator -> diarahkan ke form perencanaan, tanpa select."""
        self.risiko.indikator_mutu_terkait = None
        self.risiko.target_capaian_indikator = None
        self.risiko.save()
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Belum ditautkan ke Indikator Mutu formal')
        self.assertContains(resp, 'Tautkan di Perencanaan Risiko')
        self.assertContains(
            resp, reverse('akreditasi:risiko_edit', kwargs={'risiko_id': self.risiko.pk}))
        # G.1 kini read-only: select penautan tidak pernah dirender
        self.assertNotContains(resp, 'name="indikator_mutu_terkait"')
        self.assertNotContains(resp, 'id="link-indikator-select"')

    def test_evaluasi_hides_link_ui_when_already_linked(self):
        """Sudah tertaut -> G.1 hanya membaca, tanpa select/input penautan."""
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertNotContains(resp, 'id="link-indikator-select"')
        self.assertNotContains(resp, 'name="indikator_mutu_terkait"')

    def test_evaluasi_post_links_indikator(self):
        """Payload lama yang memuat indikator_mutu_terkait tetap menyimpan tautan."""
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
        # payload lama yang masih memuat capaian_nilai tetap diterima
        self.assertEqual(float(self.risiko.capaian_nilai), 92.5)

    # ── G.1 membaca agregat Input Capaian (input inline sudah dihapus) ──

    def test_evaluasi_menampilkan_agregat_capaian_tahunan(self):
        """8 bulan catatan (10/100) -> agregat 80/800 = 10.0% tampil di panel."""
        for b in range(1, 9):
            CatatanIndikator.objects.create(
                indikator=self.indikator, bulan=b, tahun=2026,
                nilai_numerator=Decimal('10.00'), nilai_denominator=Decimal('100.00'),
            )
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertContains(resp, '>8</strong>/12 bulan tercatat (2026)')
        self.assertContains(resp, 'Σ Numerator <strong>80,00</strong>')
        self.assertContains(resp, '/ Denominator <strong>800,00</strong>')
        self.assertContains(resp, 'dari Input Capaian')
        # capaian 10 < target 90 (arah MIN = wajib >=) -> belum tercapai
        self.assertContains(resp, 'bg-danger')
        self.assertContains(resp, '10,0%')
        self.assertContains(resp, 'selisih -80,0')
        # input inline capaian/bukti dan form penautan sudah tidak dirender
        self.assertNotContains(resp, 'name="capaian_nilai"')
        self.assertNotContains(resp, 'name="jenis_dokumen_capaian"')
        self.assertNotContains(resp, 'id="link-indikator-select"')
        self.assertNotContains(resp, 'name="indikator_mutu_terkait"')

    def test_capaian_sumber_dan_faktor_rate_absolut(self):
        """capaian_sumber menandai asal angka; tipe rate_absolut pakai faktor_pengali."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=2, tahun=2026,
            nilai_numerator=Decimal('30.00'), nilai_denominator=Decimal('100.00'),
        )
        ev = self.risiko.capaian_evaluasi
        self.assertEqual(ev['capaian_sumber'], 'catatan')
        self.assertEqual(float(ev['capaian']), 30.0)

        # capaian manual menang dan menandai sumber 'manual'
        self.risiko.capaian_nilai = Decimal('77.77')
        self.risiko.save()
        self.assertEqual(self.risiko.capaian_evaluasi['capaian_sumber'], 'manual')
        self.assertEqual(float(self.risiko.capaian_evaluasi['capaian']), 77.77)

        # tipe rate_absolut -> (Σnum/Σden) x faktor_pengali, bukan x100
        ind = IndikatorMutu.objects.create(
            unit=self.unit, kode_indikator='INM-UGD-02',
            nama_indikator='Tambahan Indikator Rate Absolut', jenis='NASIONAL',
            dimensi_mutu='EFISIENSI', numerator='n', denominator='d',
            target_nilai=40.0, satuan='x', tipe_pengukuran='rate_absolut',
            faktor_pengali=10,
        )
        CatatanIndikator.objects.create(
            indikator=ind, bulan=3, tahun=2026,
            nilai_numerator=Decimal('5.00'), nilai_denominator=Decimal('10.00'),
        )
        self.assertEqual(float(ind.agregat_capaian(2026)['capaian']), 5.0)

    def test_evaluasi_tanpa_catatan_pakai_capaian_manual(self):
        """Tanpa catatan bulanan: capaian manual lama tetap tampil (fallback)."""
        self.risiko.capaian_nilai = Decimal('92.50')
        self.risiko.save()
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertContains(resp, '92,5%')
        # arah MIN = capaian wajib >= target 90 -> tercapai, selisih 2,5
        self.assertContains(resp, 'bg-success')
        self.assertContains(resp, 'Tercapai (selisih 2,5)')
        self.assertNotContains(resp, 'dari Input Capaian')
        self.assertContains(resp, '>0</strong>/12 bulan tercatat (2026)')

    def test_evaluasi_denominator_nol_tidak_render_garpu(self):
        """Baris ber-denominator 0 diabaikan agregat (nilai_numerator__gt=0) -> panel aman."""
        for b in range(1, 4):
            CatatanIndikator.objects.create(
                indikator=self.indikator, bulan=b, tahun=2026,
                nilai_numerator=Decimal('5.00'), nilai_denominator=Decimal('0.00'),
            )
        url = reverse('akreditasi:risiko_evaluasi', kwargs={'risiko_id': self.risiko.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '>0</strong>/12 bulan tercatat (2026)')
        self.assertContains(resp, 'Belum ada data Input Capaian untuk 2026')
        self.assertNotContains(resp, 'Belum Tercapai')

    def test_ai_evaluasi_risiko_konteks_dari_model(self):
        """Payload kini berisi risiko_id: seluruh konteks AI diambil dari model."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('45.00'), nilai_denominator=Decimal('100.00'),
        )
        url = reverse('akreditasi:ai_evaluasi_risiko')
        with mock.patch('akreditasi.ai_views.generate_evaluasi_risiko') as gen:
            gen.return_value = {'success': True, 'data': {'draf_evaluasi': 'Draf uji'}}
            resp = self.client.post(
                url,
                data=json.dumps({'risiko_id': self.risiko.pk,
                                 'dampak_residual': 2, 'prob_residual': 1}),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 200)
        kwargs = gen.call_args.kwargs
        self.assertEqual(kwargs['unit_name'], 'Unit Gawat Darurat')
        self.assertIn('Emergency Response Time', kwargs['nama_indikator'])
        self.assertEqual(kwargs['target_capaian'], '90.0%')
        self.assertEqual(kwargs['capaian_nilai'], '45.0%')     # 45/100
        self.assertEqual(kwargs['gap_persen'], '-45.0%')       # capaian - target
        self.assertEqual(kwargs['dampak_residual'], 2)
        self.assertEqual(kwargs['prob_residual'], 1)

    def test_ai_evaluasi_risiko_id_tak_valid_400(self):
        """risiko_id tidak ada -> 400 tanpa memanggil layanan AI."""
        url = reverse('akreditasi:ai_evaluasi_risiko')
        with mock.patch('akreditasi.ai_views.generate_evaluasi_risiko') as gen:
            resp = self.client.post(url, data=json.dumps({'risiko_id': 999999}),
                                    content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        gen.assert_not_called()


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

