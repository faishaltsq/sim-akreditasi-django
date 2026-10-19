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
from django.test import TestCase

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
