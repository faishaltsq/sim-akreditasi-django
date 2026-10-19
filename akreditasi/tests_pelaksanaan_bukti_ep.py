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
