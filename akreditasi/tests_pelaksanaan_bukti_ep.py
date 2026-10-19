"""Pelaksanaan Risiko wajib punya bukti dokumen dan tautan standar + EP.

Spec: "Dibagian pelaksanaan; setiap pelaksanaan ada bukti dokumen dan link ke
standar akreditasi, EP."

Standar akreditasi = Category (Pokja/Standar). EP = StandardItem (Elemen
Penilaian), yang selalu milik satu Category — jadi memilih EP otomatis
menentukan standarnya, tetapi aksi boleh terikat standar saja tanpa EP
spesifik. Keduanya disimpan terpisah supaya tidak ada drift.

Fixture memakai prefix unik karena migrasi menanam data demo (IRIN,
BANGSAL-ANAK, dll) ke SQLite test.
"""
from itertools import count

from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from akreditasi.models import Category, Framework, StandardItem, UnitKerja
from akreditasi.risiko_models import RisikoUnit, TindakLanjutRisiko
from akreditasi.models import IndikatorMutu

_seq = count(1)


def _mk_framework():
    n = next(_seq)
    return Framework.objects.create(name=f'STARKES T{n}', cycle_type='PDCA')


def _mk_category():
    n = next(_seq)
    return Category.objects.create(
        framework=_mk_framework(),
        code=f'TK{n}',
        name=f'Pokja Tk {n}',
        kelompok='MANAJEMEN',
    )


def _mk_ep(category, n=None):
    n = n or next(_seq)
    return StandardItem.objects.create(
        category=category,
        sub_standard=str(n),
        sub_title='Judul EP',
        code=f'TK{n}-{next(_seq)} EP 1',
        description='Bunyi Standar / Elemen Penilaian',
    )


def _mk_risiko():
    n = next(_seq)
    unit = UnitKerja.objects.create(code=f'TLU{n}', name=f'Unit Tk {n}', level=3)
    # RisikoUnit punya 10 field wajib (tanpa null/blank/default); lengkapi
    # semuanya supaya fixture lolos validasi kolom, bukan lolos karena kosong.
    return RisikoUnit.objects.create(
        unit=unit, tahun=2026, periode='TAHUNAN',
        kategori_risiko='OPERASIONAL', jenis_risiko=f'Risiko Tk {n}',
        deskripsi_risiko=f'Deskripsi Tk {n}',
        dampak=3, probabilitas=3, strategi_mitigasi='KURANGI',
        rencana_aksi=f'Rencana Tk {n}', pj_mitigasi=f'PJ Tk {n}',
    )


class PelaksanaanLinkTest(TestCase):
    """Aksi pelaksanaan membawa tautan standar dan EP, keduanya terbaca balik."""

    def test_action_carries_standar_and_ep(self):
        cat = _mk_category()
        ep = _mk_ep(cat)
        risiko = _mk_risiko()

        tl = TindakLanjutRisiko.objects.create(
            risiko=risiko, urutan=1, aksi='Aksi', status_aksi='SEDANG',
            standar_terkait=cat, ep_terkait=ep)
        tl.refresh_from_db()

        self.assertEqual(tl.standar_terkait_id, cat.pk)
        self.assertEqual(tl.ep_terkait_id, ep.pk)
        # reverse relations resolve, karena template membaca dari keduanya
        self.assertIn(tl, cat.tindak_lanjut_set.all())
        self.assertIn(tl, ep.tindak_lanjut_set.all())

    def test_ep_must_belong_to_the_declared_standar(self):
        """View selalu menurunkan standar dari EP; model tidak boleh menerima drift."""
        cat_a = _mk_category()
        cat_b = _mk_category()
        ep_of_b = _mk_ep(cat_b)
        risiko = _mk_risiko()

        tl = TindakLanjutRisiko(
            risiko=risiko, urutan=1, aksi='Aksi',
            standar_terkait=cat_a, ep_terkait=ep_of_b)

        with self.assertRaises(ValidationError):
            tl.full_clean()


class PelaksanaanStandarSajaTest(TestCase):
    """Aksi boleh terikat standar tanpa EP spesifik."""

    def test_standar_without_ep_is_valid(self):
        cat = _mk_category()
        risiko = _mk_risiko()

        tl = TindakLanjutRisiko(
            risiko=risiko, urutan=1, aksi='Aksi', standar_terkait=cat)
        tl.full_clean()  # must not raise

    def test_ep_alone_also_validates(self):
        """EP menentukan standarnya sendiri; tidak perlu diisi manual."""
        cat = _mk_category()
        ep = _mk_ep(cat)
        risiko = _mk_risiko()

        tl = TindakLanjutRisiko(
            risiko=risiko, urutan=1, aksi='Aksi', ep_terkait=ep)
        tl.full_clean()  # must not raise


# ── Task 2: form Standar + EP di halaman detail risiko ────────────────────

class RisikoDetailFormTest(TestCase):
    """Form Do menawarkan picker Standar & EP (difilter klien per Standar)."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('pel-f', 'p@x.id', 'x')
        self.client = Client()
        self.client.force_login(self.user)
        self.cat1 = _mk_category()
        self.cat2 = _mk_category()
        self.ep1 = _mk_ep(self.cat1)
        self.ep2 = _mk_ep(self.cat2)
        self.risiko = _mk_risiko()
        self.url = reverse('akreditasi:risiko_detail', args=[self.risiko.pk])

    def test_form_offers_standar_and_ep(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'name="standar_terkait"')
        self.assertContains(res, 'name="ep_terkait"')

    def test_posting_an_action_saves_both_links(self):
        res = self.client.post(self.url, {
            'aksi': 'Aksi uji tautan',
            'status_aksi': 'SEDANG',
            'standar_terkait': str(self.cat1.pk),
            'ep_terkait': str(self.ep1.pk),
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        tl = TindakLanjutRisiko.objects.latest('id')
        self.assertEqual(tl.aksi, 'Aksi uji tautan')
        self.assertEqual(tl.standar_terkait_id, self.cat1.pk)
        self.assertEqual(tl.ep_terkait_id, self.ep1.pk)

    def test_ep_dropdown_carries_its_standar_for_client_side_filter(self):
        """Tiap opsi EP membawa data-standar supaya filter klien punya bahan."""
        res = self.client.get(self.url)
        html = res.content.decode()
        self.assertIn(f'data-standar="{self.cat1.pk}"', html)
        self.assertIn(f'data-standar="{self.cat2.pk}"', html)

    def test_ep_wins_when_it_disagrees_with_the_posted_standar(self):
        """Halaman usang: standar disimpan dari EP yang benar, bukan yang dikirim."""
        res = self.client.post(self.url, {
            'aksi': 'Aksi drift',
            'status_aksi': 'SEDANG',
            'standar_terkait': str(self.cat1.pk),
            'ep_terkait': str(self.ep2.pk),
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        tl = TindakLanjutRisiko.objects.latest('id')
        self.assertEqual(tl.ep_terkait_id, self.ep2.pk)
        self.assertEqual(tl.standar_terkait_id, self.cat2.pk)

    def test_table_shows_standar_and_ep_columns(self):
        TindakLanjutRisiko.objects.create(
            risiko=self.risiko, urutan=1, aksi='Aksi tabel',
            status_aksi='SEDANG', standar_terkait=self.cat1, ep_terkait=self.ep1)
        res = self.client.get(self.url)
        html = res.content.decode()
        self.assertIn(self.cat1.code, html)
        self.assertIn(self.ep1.code, html)
        self.assertIn(self.ep1.description, html)   # bunyi EP di tooltip

    def test_post_selesai_tanpa_bukti_ditolak_dengan_pesan_rapi(self):
        res = self.client.post(self.url, {
            'aksi': 'Tutup aksi', 'status_aksi': 'SELESAI'})
        self.assertEqual(res.status_code, 200)       # re-render, bukan 500
        self.assertContains(res, 'wajib punya bukti dokumen')
        self.assertFalse(
            TindakLanjutRisiko.objects.filter(status_aksi='SELESAI').exists())

    def test_post_selesai_dengan_bukti_lolos(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        res = self.client.post(self.url, {
            'aksi': 'Tutup aksi dengan bukti', 'status_aksi': 'SELESAI',
            'bukti_upload': SimpleUploadedFile('bukti.pdf', b'%PDF-1.4 uji')},
            follow=True)
        self.assertEqual(res.status_code, 200)
        tl = TindakLanjutRisiko.objects.latest('id')
        self.assertEqual(tl.status_aksi, 'SELESAI')
        self.assertTrue(tl.bukti_upload.name)


# ── Task 3: kolom EP di daftar risiko (register) ──────────────────────────

class RisikoDaftarEPTest(TestCase):
    """Daftar risiko ikut menampilkan EP yang dilayani pelaksanaannya."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('pel-h', 'h@x.id', 'x')
        self.client = Client()
        self.client.force_login(self.user)
        self.cat = _mk_category()
        self.ep = _mk_ep(self.cat)
        self.risiko = _mk_risiko()
        self.url = reverse('akreditasi:risiko_daftar')

    def test_register_has_ep_column(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'EP (Pelaksanaan)')

    def test_register_shows_ep_code_for_each_risk(self):
        TindakLanjutRisiko.objects.create(
            risiko=self.risiko, urutan=1, aksi='Aksi register',
            status_aksi='SEDANG', standar_terkait=self.cat, ep_terkait=self.ep)
        res = self.client.get(self.url)
        self.assertContains(res, self.ep.code)

    def test_register_without_action_shows_dash(self):
        res = self.client.get(self.url)
        # baris risiko tanpa pelaksanaan tetap dirender, EP kosong
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, self.risiko.masalah)


# ── Task 4: materialisasi rencana_aksi membawa tautan EP/standar ──────────

class StepMaterializationLinkTest(TestCase):
    """Tahap rencana yang dijadikan pelaksanaan tidak boleh yatim tautannya."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('pel-i', 'i@x.id', 'x')
        self.client = Client()
        self.client.force_login(self.user)
        self.cat = _mk_category()
        self.ep = _mk_ep(self.cat)
        ind = IndikatorMutu.objects.create(
            kode_indikator='IM-404', nama_indikator='Kepatuhan EP',
            jenis='INM', dimensi_mutu='AMAN',
            numerator='Barang sesuai', denominator='Total barang',
            target_nilai=90, ep_terkait=self.ep)
        self.risiko = _mk_risiko()
        self.risiko.rencana_aksi = '1. Langkah satu\n2. Langkah dua'
        self.risiko.indikator_mutu_terkait = ind
        self.risiko.save()
        self.url = reverse('akreditasi:risiko_evaluasi', args=[self.risiko.pk])

    def test_materialized_steps_inherit_ep_and_standar(self):
        res = self.client.post(self.url, {
            'dampak_residual': '3', 'probabilitas_residual': '3',
            'step_status_1': 'SELESAI',
            'step_status_2': 'SEDANG',
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.risiko.tindak_lanjut.count(), 2)
        for tl in self.risiko.tindak_lanjut.all():
            self.assertEqual(tl.ep_terkait_id, self.ep.pk)
            self.assertEqual(tl.standar_terkait_id, self.cat.pk)

    def test_ep_yang_tanpa_konflik_tetap_lolos_validasi(self):
        res = self.client.post(self.url, {
            'dampak_residual': '3', 'probabilitas_residual': '3',
            'step_status_1': 'SEDANG'}, follow=True)
        self.assertEqual(res.status_code, 200)
        from django.contrib.messages import get_messages
        msgs = [m for m in get_messages(res.wsgi_request)]
        self.assertFalse([m for m in msgs if m.level_tag == 'error'],
                         'materialisasi tahap tidak boleh memunculkan pesan error')
        self.assertEqual(self.risiko.tindak_lanjut.count(), 1)


class BuktiWajibTidakMengubahBarisLama(TestCase):
    """Penolakan SELESAI tanpa bukti tidak boleh menyentuh baris yang sudah ada."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('pel-j', 'j@x.id', 'x')
        self.client = Client()
        self.client.force_login(self.user)
        self.cat = _mk_category()
        self.ep = _mk_ep(self.cat)
        self.risiko = _mk_risiko()
        self.url = reverse('akreditasi:risiko_detail', args=[self.risiko.pk])
        self.existing = TindakLanjutRisiko.objects.create(
            risiko=self.risiko, urutan=1, aksi='Aksi lama',
            status_aksi='SEDANG', standar_terkait=self.cat, ep_terkait=self.ep)

    def test_baris_lama_tetap_utuh_setelah_posting_gagal(self):
        before = {tl.pk: (tl.aksi, tl.status_aksi, tl.standar_terkait_id,
                          tl.ep_terkait_id)
                  for tl in self.risiko.tindak_lanjut.all()}
        self.client.post(self.url, {'aksi': 'Aksi baru', 'status_aksi': 'SELESAI'})
        after = {tl.pk: (tl.aksi, tl.status_aksi, tl.standar_terkait_id,
                         tl.ep_terkait_id)
                 for tl in self.risiko.tindak_lanjut.all()}
        self.assertEqual(before, after)
        # hanya baris lama, tidak ada duplikat terselundup
        self.assertEqual(self.risiko.tindak_lanjut.count(), 1)

    def test_posting_gagal_tidak_menambah_urutan_kotor(self):
        self.client.post(self.url, {'aksi': 'Aksi gagal', 'status_aksi': 'SELESAI'})
        # urutan berikutnya tetap 2, bukan 3 (gagal sebelum save)
        res = self.client.post(self.url, {
            'aksi': 'Aksi valid', 'status_aksi': 'SEDANG'}, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.risiko.tindak_lanjut.order_by('-urutan').first().urutan, 2)


# ── Task 3: kolom Standar/EP di semua permukaan lain yang me-loop pelaksanaan ──

class SurfaceLinkPropagationTest(TestCase):
    """Setiap halaman yang mencetak pelaksanaan ikut menyebut standar & EP."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('pel-k', 'k@x.id', 'x')
        self.client = Client()
        self.client.force_login(self.user)
        self.cat = _mk_category()
        self.ep = _mk_ep(self.cat)
        self.risiko = _mk_risiko()
        # Indikator menentukan EP pada permukaan perencanaan yang tidak
        # me-loop pelaksanaan -- kolom EP-nya diturunkan dari indikator.
        self.ind = IndikatorMutu.objects.create(
            kode_indikator='SURF-EP', nama_indikator='Indikator Permukaan',
            jenis='INM', dimensi_mutu='AMAN',
            target_nilai='90', ep_terkait=self.ep)
        self.risiko.indikator_mutu_terkait = self.ind
        self.risiko.save(update_fields=['indikator_mutu_terkait'])
        self.tl = TindakLanjutRisiko.objects.create(
            risiko=self.risiko, urutan=1, aksi='Aksi permukaan',
            status_aksi='SEDANG', standar_terkait=self.cat, ep_terkait=self.ep)
        self.unit_id = self.risiko.unit_id
        self.tahun = str(self.risiko.tahun)

    def _assert_links(self, html):
        self.assertIn(self.ep.code, html, 'kode EP tidak muncul')
        self.assertIn(self.cat.code, html, 'kode standar tidak muncul')

    def test_per_unit_do_page(self):
        res = self.client.get(reverse(
            'akreditasi:risiko_pelaksanaan_unit', args=[self.unit_id]))
        self.assertEqual(res.status_code, 200)
        self._assert_links(res.content.decode())

    def test_print_do_sheet(self):
        res = self.client.get(reverse(
            'akreditasi:risiko_pelaksanaan_dokumen', args=[self.risiko.pk]))
        self.assertEqual(res.status_code, 200)
        self._assert_links(res.content.decode())

    def test_csv_export_appends_new_columns(self):
        res = self.client.get(reverse('akreditasi:risiko_pelaksanaan_export_csv'))
        self.assertEqual(res.status_code, 200)
        lines = res.content.decode('utf-8-sig').splitlines()
        # baris 0 adalah judul dokumen; header kolom adalah baris ber-Deskripsi
        header = next(ln for ln in lines if 'Deskripsi Pelaksanaan' in ln)
        cols = [c.strip() for c in header.split(',')]
        # urutan kolom lama tidak boleh bergeser, kolom baru menempel di belakang
        self.assertEqual(cols[:11], [
            'No', 'Jenis Risiko', 'Rencana Aksi Mitigasi', 'No. Aksi',
            'Deskripsi Pelaksanaan', 'Status', 'Tgl Mulai', 'Tgl Selesai',
            'Catatan', 'Bukti Dokumen', 'PJ Mitigasi'], f'header berubah: {cols}')
        for col in ('standar', 'kode_ep', 'judul_ep', 'ada_bukti'):
            self.assertIn(col, cols, f'kolom {col} hilang dari header CSV')
        self.assertEqual(cols[11:], ['standar', 'kode_ep', 'judul_ep', 'ada_bukti'])

    def test_csv_row_carry_values(self):
        # export tanpa param memakai UnitKerja.objects.first(); sebutkan unitnya
        text = self.client.get(reverse('akreditasi:risiko_pelaksanaan_export_csv') +
                               f'?unit={self.unit_id}&tahun={self.tahun}'
        ).content.decode('utf-8-sig')
        row = [ln for ln in text.splitlines() if 'Aksi permukaan' in ln][0]
        self.assertIn(self.ep.code, row)
        self.assertIn(self.cat.code, row)

    def test_laporan_lengkap(self):
        res = self.client.get(reverse('akreditasi:risiko_laporan_lengkap_single',
                                      args=[self.risiko.pk]))
        self.assertEqual(res.status_code, 200)
        self._assert_links(res.content.decode())

    def test_monitoring_evaluasi(self):
        res = self.client.get(reverse('akreditasi:risiko_monev_unit',
                                      args=[self.unit_id]))
        self.assertEqual(res.status_code, 200)
        self._assert_links(res.content.decode())

    def test_perencanaan_preview(self):
        # Perencanaan tidak me-loop pelaksanaan, jadi kolomnya cukup EP --
        # standarnya tersirat dari EP, mengikuti aturan kategori.
        res = self.client.get(reverse('akreditasi:risiko_perencanaan_unit',
                                      args=[self.unit_id]))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn(self.ep.code, html, 'kode EP tidak muncul')
        self.assertIn('EP (Pelaksanaan)', html, 'kolom EP hilang')
