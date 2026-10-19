"""Uji sinkronisasi Indikator Mutu <-> EP <-> Dokumen Bukti.

Menguji kaskade tiga tingkat: rule boost (Tier A), prefilter lexical (Tier B),
dan rekomendasi DeepSeek (Tier C) — termasuk validasi anti-halusinasi, jalur
degradasi saat AI mati, serta panel dokumen bukti di halaman detail.

Panggilan jaringan ke DeepSeek SELALU di-mock; tidak ada tes yang menembak API.
"""
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from akreditasi import ai_service, ep_sync
from akreditasi.models import (Category, EvidenceReq, Framework, StandardItem,
                               UnitKerja)
from akreditasi.risiko_models import IndikatorMutu
from akreditasi.system_models import SystemConfig
from akreditasi.tests_utils import reset_rate_limit
from accounts.models import UserProfile


class _EPFixture:
    """Katalog EP kecil yang deterministik untuk seluruh kelas uji."""

    @classmethod
    def setUpTestData(cls):
        # Framework hanya punya name/cycle_type/version — bukan code/year.
        cls.fw = Framework.objects.create(name='Standar Akreditasi RS',
                                          cycle_type='3 Tahun', version='2022')
        cls.pokja = Category.objects.create(
            framework=cls.fw, code='SKP', name='Sasaran Keselamatan Pasien',
            kelompok='SASARAN_KP', order=1)
        cls.pokja2 = Category.objects.create(
            framework=cls.fw, code='TKRS', name='Tata Kelola Rumah Sakit',
            kelompok='MANAJEMEN', order=2)
        cls.ep = StandardItem.objects.create(
            category=cls.pokja, sub_standard='SKP 5',
            sub_title='Kepatuhan Hand Hygiene', code='SKP 5 EP 901',
            description='Rumah sakit menetapkan indikator mutu keselamatan pasien '
                        'dan memantau kepatuhan pelaksanaan hand hygiene.',
            order=1)
        cls.ep2 = StandardItem.objects.create(
            category=cls.pokja2, sub_standard='TKRS 1',
            sub_title='Representasi Pemilik', code='TKRS 1 EP 901',
            description='Pemilik rumah sakit menetapkan struktur organisasi dan '
                        'rencana strategis rumah sakit.',
            order=2)
        # Kode unik — DB test sudah terisi unit hasil seed (mis. 'IGD').
        cls.unit = UnitKerja.objects.create(
            code='ZUNIT-UTS', name='Unit Uji Sinkronisasi EP', is_active=True,
            standar_terkait={'SKP': ['SKP 5']})

    def _indikator(self, **kw):
        data = dict(
            kode_indikator='TEST-01',
            nama_indikator='Kepatuhan Hand Hygiene Perawat IGD',
            numerator='Jumlah kepatuhan hand hygiene',
            denominator='Jumlah observasi',
            jenis='IMU', dimensi_mutu='AMAN',
            satuan='%', target_nilai=85, unit=self.unit, aktif=True,
        )
        data.update(kw)
        return IndikatorMutu.objects.create(**data)

    def _set_ai(self, **flags):
        """Tulis ulang konfigurasi AI dan validasi cache-nya.

        ``SystemConfig.get_solo()`` meng-cache objek selama 10 detik di level
        kelas; rollback transaksi test TIDAK mengosongkan cache itu. Karena itu
        flag yang relevan ditulis eksplisit di setiap setUp, lalu ``save()``
        (yang meng-invalidasi cache) supaya service membaca nilai yang sama.
        """
        cfg = SystemConfig.get_solo()
        cfg.ai_enabled = flags.get('ai_enabled', True)
        cfg.ai_enable_ep_sync = flags.get('ai_enable_ep_sync', True)
        cfg.save()
        return cfg

    def _manager(self, username='mgr', role='ADMIN_RS'):
        u = User.objects.create_user(username, f'{username}@x.io', 'x')
        UserProfile.objects.create(user=u, role=role)
        return u


class EPKatalogTest(_EPFixture, TestCase):
    """Tier B: katalog, index, dan penyaring lexical."""

    def test_katalog_memuat_semua_ep_dengan_kode_unik(self):
        lines, codes, n = ep_sync.build_ep_catalog()
        self.assertEqual(n, StandardItem.objects.count())
        self.assertEqual(len(codes), n)
        self.assertIn('SKP 5 EP 901', codes)

    def test_katalog_menghormati_batas_karakter(self):
        lines, _, _ = ep_sync.build_ep_catalog(max_chars=30)
        for line in lines:
            teks = line.split(' | ', 2)[2]
            self.assertLessEqual(len(teks), 30)

    def test_prefilter_mengembalikan_kandidat_relevan(self):
        ind = self._indikator()
        top = ep_sync.prefilter_candidates(ind, top_k=10)
        self.assertTrue(top, 'harus ada kandidat untuk indikator hand hygiene')
        self.assertIn('SKP 5 EP 901', [k['code'] for k in top],
                      'EP fixture harus masuk kandidat')
        self.assertTrue(any(k['dari_unit'] for k in top),
                        'EP fixture ada di pemetaan unit IGD')

    def test_prefilter_menandai_kandidat_dari_pemetaan_unit(self):
        ind = self._indikator(unit=None)
        top = ep_sync.prefilter_candidates(ind, top_k=5)
        self.assertTrue(top)
        self.assertFalse(any(c['dari_unit'] for c in top),
                         'tanpa unit tidak boleh ada penanda dari unit')

    def test_resolve_ep_by_code(self):
        self.assertEqual(ep_sync.resolve_ep_by_code('SKP 5 EP 901').pk, self.ep.pk)
        self.assertIsNone(ep_sync.resolve_ep_by_code('TIDAK ADA EP 9'))
        self.assertIsNone(ep_sync.resolve_ep_by_code(''))

    def test_index_cache_dibuang_setelah_ep_baru(self):
        sebelum = len(ep_sync.get_ep_index())
        StandardItem.objects.create(
            category=self.pokja, sub_standard='SKP 9', code='SKP 9 EP 9',
            description='EP baru untuk menguji pembuangan cache.', order=99)
        self.assertEqual(len(ep_sync.get_ep_index()), sebelum + 1)


class EPRekomendasiServiceTest(_EPFixture, TestCase):
    """Tier C: validasi balasan AI dan jalur degradasi."""

    def setUp(self):
        self.ind = self._indikator()
        self.cfg = self._set_ai()

    def _reply(self, items):
        return {'success': True, 'data': {'rekomendasi': items}, 'error': None}

    def test_membuang_kode_halusinasi_dan_menjepit_confidence(self):
        fake = self._reply([
            {'ep_code': 'SKP 5 EP 901', 'confidence': 1.9, 'alasan': 'relevan'},
            {'ep_code': 'KARANGAN 99 EP 9', 'confidence': 0.99, 'alasan': 'palsu'},
            {'ep_code': 'TKRS 1 EP 901', 'confidence': 0.5, 'alasan': 'mirip'},
        ])
        with patch.object(ai_service, '_call_deepseek', return_value=fake):
            res = ai_service.generate_ep_rekomendasi(None, self.ind)
        kode = [r['ep_code'] for r in res['data']['rekomendasi']]
        self.assertEqual(kode, ['SKP 5 EP 901', 'TKRS 1 EP 901'])
        self.assertNotIn('KARANGAN 99 EP 9', kode)
        self.assertEqual(res['data']['rekomendasi'][0]['confidence'], 1.0)  # dijepit
        self.assertEqual(res['ditolak'], 1)
        self.assertTrue(res['ai_terpakai'])

    def test_katalog_ikut_dikirim_ke_model(self):
        ditangkap = {}

        def fake(prompt, **kw):
            ditangkap['prompt'] = prompt
            ditangkap['kw'] = kw
            return self._reply([])

        with patch.object(ai_service, '_call_deepseek', side_effect=fake):
            ai_service.generate_ep_rekomendasi(None, self.ind)
        self.assertIn('SKP 5 EP 901', ditangkap['prompt'])
        self.assertIn('Katalog EP', ditangkap['prompt'])
        self.assertGreaterEqual(ditangkap['kw'].get('timeout', 0), 60,
                                'prompt besar perlu timeout lebih longgar')

    def test_balasan_bukan_list_jatuh_ke_lexical(self):
        with patch.object(ai_service, '_call_deepseek',
                          return_value=self._reply('bukan list')):
            res = ai_service.generate_ep_rekomendasi(None, self.ind)
        self.assertTrue(res['success'])
        self.assertFalse(res['ai_terpakai'])
        self.assertEqual(res['data']['sumber'], 'LEXICAL')
        self.assertTrue(res['data']['rekomendasi'])

    def test_semua_kode_ditolak_jatuh_ke_lexical(self):
        with patch.object(ai_service, '_call_deepseek',
                          return_value=self._reply([{'ep_code': 'X 1 EP 1',
                                                     'confidence': 0.9}])):
            res = ai_service.generate_ep_rekomendasi(None, self.ind)
        self.assertFalse(res['ai_terpakai'])
        self.assertEqual(res['data']['sumber'], 'LEXICAL')

    def test_transport_gagal_jatuh_ke_lexical(self):
        with patch.object(ai_service, '_call_deepseek',
                          return_value={'success': False, 'error': 'timeout'}):
            res = ai_service.generate_ep_rekomendasi(None, self.ind)
        self.assertTrue(res['success'], 'fallback tidak boleh membuat pemanggil pecah')
        self.assertFalse(res['ai_terpakai'])
        self.assertEqual(res['data']['sumber'], 'LEXICAL')

    def test_flag_off_tidak_memanggil_ai(self):
        self.cfg = self._set_ai(ai_enable_ep_sync=False)
        with patch.object(ai_service, '_call_deepseek') as m:
            res = ai_service.generate_ep_rekomendasi(None, self.ind)
        m.assert_not_called()
        self.assertFalse(res['ai_terpakai'])

    def test_ai_nonaktif_tidak_memanggil_ai(self):
        self.cfg = self._set_ai(ai_enabled=False)
        with patch.object(ai_service, '_call_deepseek') as m:
            res = ai_service.generate_ep_rekomendasi(None, self.ind)
        m.assert_not_called()
        self.assertFalse(res['ai_terpakai'])


class EndpointEPRekomendasiTest(_EPFixture, TestCase):
    """Endpoint /ai/ep-rekomendasi/ dan kontrol aksesnya."""

    def setUp(self):
        self.ind = self._indikator()
        self.url = reverse('akreditasi:api_ai_ep_rekomendasi')
        self.cfg = self._set_ai()

    def _post(self, user, payload):
        reset_rate_limit()
        c = Client()
        c.force_login(user)
        return c.post(self.url, data=json.dumps(payload),
                      content_type='application/json')

    def test_anonim_diarahkan_ke_login(self):
        reset_rate_limit()
        r = Client().post(self.url, data=json.dumps({'indikator_id': self.ind.pk}),
                          content_type='application/json')
        self.assertEqual(r.status_code, 302)

    def test_get_ditolak(self):
        c = Client()
        c.force_login(self._manager())
        reset_rate_limit()
        self.assertEqual(c.get(self.url).status_code, 405)

    def test_staf_tidak_punya_akses(self):
        for role in ('STAF_NAKES', 'ASESOR'):
            r = self._post(self._manager(f'n_{role}', role),
                           {'indikator_id': self.ind.pk})
            self.assertEqual(r.status_code, 403, role)

    def test_koordinator_pokja_dianggap_manager(self):
        """Regresi: nilai role sebenarnya 'KOORDINATOR_POKJA', bukan 'KOORDINATOR'."""
        fake = {'success': True, 'data': {'rekomendasi': []}, 'error': None}
        with patch.object(ai_service, '_call_deepseek', return_value=fake):
            r = self._post(self._manager('koor', 'KOORDINATOR_POKJA'),
                           {'indikator_id': self.ind.pk})
        self.assertEqual(r.status_code, 200)

    def test_payload_tidak_valid_ditolak(self):
        mgr = self._manager('m_bad')
        for bad in ({'indikator_id': 'xx'}, {}):
            self.assertEqual(self._post(mgr, bad).status_code, 400, bad)

    def test_indikator_tidak_ada_404(self):
        self.assertEqual(
            self._post(self._manager('m_404'), {'indikator_id': 999999}).status_code,
            404)

    def test_link_manual_tidak_boleh_ditimpa(self):
        ind = self._indikator(kode_indikator='TEST-MANUAL', ep_terkait=self.ep,
                              ep_sumber='MANUAL')
        r = self._post(self._manager('m_manual'), {'indikator_id': ind.pk})
        self.assertEqual(r.status_code, 400)
        self.assertIn('manual', r.json()['error'])

    def test_sukses_mengembalikan_kandidat_dan_rekomendasi(self):
        fake = {'success': True, 'error': None,
                'data': {'rekomendasi': [{'ep_code': 'SKP 5 EP 901',
                                          'confidence': 0.91,
                                          'alasan': 'mengukur kepatuhan'}]}}
        with patch.object(ai_service, '_call_deepseek', return_value=fake):
            r = self._post(self._manager('m_ok'), {'indikator_id': self.ind.pk})
        self.assertEqual(r.status_code, 200)
        b = r.json()
        self.assertTrue(b['success'])
        self.assertTrue(b['ai_terpakai'])
        self.assertEqual(b['sumber'], 'AI')
        self.assertEqual(b['rekomendasi'][0]['ep_code'], 'SKP 5 EP 901')
        self.assertTrue(b['kandidat'])
        self.assertIsNone(b['ep_terkait'])

    def test_notice_diisi_saat_ai_mati(self):
        with patch.object(ai_service, '_call_deepseek',
                          return_value={'success': False, 'error': 'timeout'}):
            r = self._post(self._manager('m_notice'), {'indikator_id': self.ind.pk})
        b = r.json()
        self.assertTrue(b['success'])
        self.assertFalse(b['ai_terpakai'])
        self.assertEqual(b['sumber'], 'LEXICAL')
        self.assertIn('timeout', b['notice'])


class IndikatorFormTest(_EPFixture, TestCase):
    """Cap dropdown EP dihapus + kartu sinkronisasi ada di form."""

    def setUp(self):
        self.mgr = self._manager('mgr_form')

    def test_dropdown_memuat_semua_ep_tanpa_cap(self):
        # 201 EP: di bawah cap lama [:200] sebagian EP tidak akan pernah muncul.
        StandardItem.objects.bulk_create([
        StandardItem(category=self.pokja, sub_standard='SKP 9',
                     sub_title=f'EP uji {i}',
                     code=f'ZTEST {i:03d} EP 1',   # kode tak mungkin tabrakan dengan seed
                     description=f'EP uji nomor {i} untuk memastikan tidak ada cap.',
                     order=i) for i in range(1, 202)])
        ind = self._indikator()
        reset_rate_limit()
        c = Client()
        c.force_login(self.mgr)
        r = c.get(reverse('akreditasi:indikator_edit', args=[ind.pk]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertEqual(html.count('data-code='), StandardItem.objects.count())
        self.assertIn('ZTEST 201 EP 1', html)      # EP ke-201: tidak ada lagi cap 200
        self.assertIn('btn-ep-sync', html)

    def test_kartu_sync_dan_unlocalize_di_form(self):
        ind = self._indikator()
        reset_rate_limit()
        c = Client()
        c.force_login(self.mgr)
        html = c.get(reverse('akreditasi:indikator_edit', args=[ind.pk])).content.decode()
        self.assertIn('Sinkronisasi EP', html)
        self.assertNotIn('{{ ind.pk }}', html)   # nilai mentah tak boleh lolos

    def test_halaman_tambah_tetap_200_dan_ada_petunjuk(self):
        reset_rate_limit()
        c = Client()
        c.force_login(self.mgr)
        r = c.get(reverse('akreditasi:indikator_tambah'))
        self.assertEqual(r.status_code, 200)


class BuktiPanelTest(_EPFixture, TestCase):
    """Panel dokumen bukti di halaman detail indikator."""

    def setUp(self):
        self.mgr = self._manager('mgr_bukti')

    def _get(self, ind):
        reset_rate_limit()
        c = Client()
        c.force_login(self.mgr)
        return c.get(reverse('akreditasi:indikator_detail', args=[ind.pk]),
                     {'tahun': 2026}).content.decode()

    def test_ep_dengan_kebutuhan_bukti_menampilkan_daftar(self):
        EvidenceReq.objects.create(standard_item=self.ep, category_type='D',
                                   title='Laporan audit kepatuhan hand hygiene')
        ind = self._indikator(ep_terkait=self.ep, ep_sumber='MANUAL')
        html = self._get(ind)
        self.assertIn('Laporan audit kepatuhan hand hygiene', html)
        self.assertIn('Belum ada berkas', html)
        self.assertIn(f'/ep/{self.ep.pk}/bukti-data/', html)

    def test_berkas_terunggah_dihitung(self):
        from akreditasi.models import EvidenceFile
        req = EvidenceReq.objects.create(standard_item=self.ep, category_type='D',
                                         title='Laporan audit')
        EvidenceFile.objects.create(requirement=req, file_name='audit.pdf', version=2)
        ind = self._indikator(ep_terkait=self.ep, ep_sumber='MANUAL')
        html = self._get(ind)
        self.assertIn('audit.pdf', html)
        self.assertIn('1/1 kebutuhan punya berkas', html)
        self.assertNotIn('Belum ada berkas', html)

    def test_indikator_tanpa_ep_menampilkan_ajakan_taut(self):
        html = self._get(self._indikator(kode_indikator='TEST-NOEP'))
        self.assertIn('belum tertaut ke Elemen Penilaian', html)
        self.assertIn('Tautkan ke EP', html)

    def test_ep_tanpa_kebutuhan_bukti_tidak_menampilkan_progres_merah(self):
        ind = self._indikator(kode_indikator='TEST-NOREQ', ep_terkait=self.ep2,
                              ep_sumber='MANUAL')
        html = self._get(ind)
        self.assertIn('tidak memiliki daftar kebutuhan', html)
        self.assertNotIn('kebutuhan punya berkas', html)


class SyncCommandTest(_EPFixture, TestCase):
    """Command bulk sync_ep_indikator — keselamatan penulisan."""

    def setUp(self):
        self.cfg = self._set_ai()

    def _out(self, *args):
        """Jalankan command; selalu batasi ke indikator fixture sendiri.

        DB test berisi indikator hasil seed, jadi tanpa ``--kode`` perintah massal
        akan menimpa data yang bukan milik tes ini.
        """
        from io import StringIO
        if '--kode' not in args:
            args = tuple(args) + ('--kode', 'TEST-')
        buf = StringIO()
        call_command('sync_ep_indikator', *args, stdout=buf)
        return buf.getvalue()

    def test_dry_run_tidak_menulis(self):
        ind = self._indikator()
        self._out('--limit', 1)
        ind.refresh_from_db()
        self.assertIsNone(ind.ep_terkait_id)

    def test_saran_kata_tidak_pernah_diterapkan_otomatis(self):
        """Presisi@1 saran kata hanya 10%: tidak boleh menulis tanpa AI."""
        ind = self._indikator()
        self._out('--limit', 1, '--apply')
        ind.refresh_from_db()
        self.assertIsNone(ind.ep_terkait_id)
        self.assertEqual(ind.ep_sumber, 'MANUAL')

    def test_apply_dengan_ai_menulis_provenance(self):
        ind = self._indikator()
        fake = {'success': True, 'error': None,
                'data': {'rekomendasi': [{'ep_code': 'SKP 5 EP 901', 'confidence': 0.93,
                                          'alasan': 'mengukur kepatuhan'}]}}
        with patch.object(ai_service, '_call_deepseek', return_value=fake):
            self._out('--limit', 1, '--apply', '--ai', '--throttle', '0')
        ind.refresh_from_db()
        self.assertEqual(ind.ep_terkait_id, self.ep.pk)
        self.assertEqual(ind.ep_sumber, 'AI')
        self.assertEqual(float(ind.ep_skor), 0.93)

    def test_confidence_di_bawah_ambang_tidak_diterapkan(self):
        ind = self._indikator()
        fake = {'success': True, 'error': None,
                'data': {'rekomendasi': [{'ep_code': 'SKP 5 EP 901', 'confidence': 0.4,
                                          'alasan': 'ragu'}]}}
        with patch.object(ai_service, '_call_deepseek', return_value=fake):
            self._out('--limit', 1, '--apply', '--ai', '--throttle', '0')
        ind.refresh_from_db()
        self.assertIsNone(ind.ep_terkait_id, 'confidence rendah harus dilewati')

    def test_link_manual_tidak_disentuh_termasuk_dengan_ulang(self):
        ind = self._indikator(kode_indikator='TEST-MAN', ep_terkait=self.ep,
                              ep_sumber='MANUAL')
        fake = {'success': True, 'error': None,
                'data': {'rekomendasi': [{'ep_code': 'TKRS 1 EP 901',
                                          'confidence': 0.99, 'alasan': 'x'}]}}
        with patch.object(ai_service, '_call_deepseek', return_value=fake):
            self._out('--apply', '--ai', '--ulang', '--throttle', '0')
        ind.refresh_from_db()
        self.assertEqual(ind.ep_terkait_id, self.ep.pk, 'link manual tidak boleh berubah')
        self.assertEqual(ind.ep_sumber, 'MANUAL')

    def test_ulang_menilai_ulang_tautan_otomatis(self):
        ind = self._indikator(kode_indikator='TEST-AUTO', ep_terkait=self.ep2,
                              ep_sumber='AI', ep_skor='0.8000')
        fake = {'success': True, 'error': None,
                'data': {'rekomendasi': [{'ep_code': 'SKP 5 EP 901',
                                          'confidence': 0.95, 'alasan': 'lebih tepat'}]}}
        with patch.object(ai_service, '_call_deepseek', return_value=fake):
            self._out('--apply', '--ai', '--ulang', '--throttle', '0')
        ind.refresh_from_db()
        self.assertEqual(ind.ep_terkait_id, self.ep.pk)
        self.assertEqual(ind.ep_sumber, 'AI')

    def test_tanpa_ulang_hanya_memproses_yang_belum_tertaut(self):
        ind = self._indikator(kode_indikator='TEST-LAMA', ep_terkait=self.ep2,
                              ep_sumber='AI')
        out = self._out('--apply', '--ai', '--throttle', '0')
        self.assertIn('Indikator belum tertaut: 0', out)
        ind.refresh_from_db()
        self.assertEqual(ind.ep_terkait_id, self.ep2.pk)

    def test_filter_kode_membatasi_pemrosesan(self):
        self._indikator(kode_indikator='AAA-01')
        self._indikator(kode_indikator='BBB-01')
        out = self._out('--kode', 'AAA')
        self.assertIn('Indikator belum tertaut: 1', out)


class ProvenanceSaveTest(_EPFixture, TestCase):
    """Pilihan operator di form menulis ulang provenance link (Task 5)."""

    def setUp(self):
        self.mgr = self._manager('mgr_prov')

    def _post_edit(self, ind, ep_value):
        reset_rate_limit()
        c = Client()
        c.force_login(self.mgr)
        return c.post(reverse('akreditasi:indikator_edit', args=[ind.pk]), {
            'kode_indikator': ind.kode_indikator,
            'nama_indikator': ind.nama_indikator,
            'unit': ind.unit_id or '',
            'jenis': ind.jenis,
            'dimensi_mutu': ind.dimensi_mutu,
            'numerator': ind.numerator,
            'denominator': ind.denominator,
            'target_nilai': str(ind.target_nilai),
            'satuan': ind.satuan,
            'ep_terkait': '' if ep_value is None else str(ep_value),
        })

    def test_mengganti_ep_menjadi_pilihan_manual(self):
        ind = self._indikator(ep_terkait=self.ep, ep_sumber='AI', ep_skor='0.8000')
        r = self._post_edit(ind, self.ep2.pk)
        self.assertEqual(r.status_code, 302)
        ind.refresh_from_db()
        self.assertEqual(ind.ep_terkait_id, self.ep2.pk)
        self.assertEqual(ind.ep_sumber, 'MANUAL')
        self.assertIsNone(ind.ep_skor, 'skor AI tidak boleh bertahan di link manual')

    def test_simpan_tanpa_mengubah_ep_mempertahankan_provenance(self):
        ind = self._indikator(ep_terkait=self.ep, ep_sumber='AI', ep_skor='0.8000')
        r = self._post_edit(ind, self.ep.pk)
        self.assertEqual(r.status_code, 302)
        ind.refresh_from_db()
        self.assertEqual(ind.ep_terkait_id, self.ep.pk)
        self.assertEqual(ind.ep_sumber, 'AI', 'edit bidang lain tidak boleh merusak riwayat AI')

    def test_mengosongkan_ep_mereset_provenance(self):
        ind = self._indikator(ep_terkait=self.ep, ep_sumber='AI', ep_skor='0.8000')
        r = self._post_edit(ind, None)
        self.assertEqual(r.status_code, 302)
        ind.refresh_from_db()
        self.assertIsNone(ind.ep_terkait_id)
        self.assertEqual(ind.ep_sumber, 'MANUAL')
        self.assertIsNone(ind.ep_skor)

    def test_dashboard_menampilkan_ringkasan_bukti_ep(self):
        EvidenceReq.objects.create(standard_item=self.ep, category_type='D',
                                   title='Laporan audit')
        EvidenceReq.objects.create(standard_item=self.ep, category_type='D',
                                   title='Rekap kedua')
        ind = self._indikator(ep_terkait=self.ep, ep_sumber='MANUAL')
        reset_rate_limit()
        c = Client()
        c.force_login(self.mgr)
        resp = c.get(reverse('akreditasi:indikator_dashboard'),
                     {'indikator': ind.pk, 'tahun': 2026})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('EP Terkait:', html)
        self.assertIn('2 kebutuhan bukti, 0 terunggah', html)
