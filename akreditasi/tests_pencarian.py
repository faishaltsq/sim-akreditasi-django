"""Uji endpoint pencarian terpadu (akreditasi:pencarian).

Mengunci tiga kontrak:
1. Autentikasi — anonim tidak bisa mencari (302 ke login; 401 JSON hanya
   untuk jalur /ai/, bukan di sini, lihat tests_security).
2. Data nyata — hasil datang dari query ORM: buat EP, dokumen, risiko,
   unit, insiden, lalu yakinikan semuanya muncul; kata kunci yang tak
   cocok mengembalikan kosong.
3. Lingkup risiko mengikuti unit scope (risiko unit lain tidak bocor ke
   pengguna unit-scoped), atau kata kunci untuk sumber lain ikut pola
   halaman sumbernya (ep_list, dokumen_hub, unit_tree, insiden_daftar
   ber-turnstile login_required tanpa cukuran unit).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from akreditasi.models import (
    Category, EvidenceFile, EvidenceReq, Framework, StandardItem, UnitKerja
)
from akreditasi.risiko_models import InsidenKeselamatan, RisikoUnit
from accounts.models import UserProfile

User = get_user_model()


def _profile_with(user, **kw):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    for field, value in kw.items():
        setattr(profile, field, value)
    profile.save()
    return profile


class PencarianBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Password@123'
        cls.user = User.objects.create_user(username='admin_test', password=cls.password)
        _profile_with(cls.user)

        # DB uji sudah terisi data hasil migrasi seed (unit, framework, kategori
        # standar), jadi semua kode di sini pakai prefix QRY- agar tidak bentrok
        # UNIQUE dengan baris seed.
        cls.unit, _ = UnitKerja.objects.get_or_create(
            code='QRY-IGD', defaults=dict(name='Instalasi Gawat Darurat Uji', level=2),
        )
        cls.unit_lain, _ = UnitKerja.objects.get_or_create(
            code='QRY-FARM', defaults=dict(name='Farmasi Uji', level=2),
        )

        cls.framework, _ = Framework.objects.get_or_create(
            name='Standar Uji Pencarian', defaults=dict(cycle_type='PDCA', version='2026'),
        )
        cls.cat, _ = Category.objects.get_or_create(
            framework=cls.framework, code='QRY-PMKP',
            defaults=dict(name='PMKP Uji', kelompok='MANAJEMEN', order=99),
        )
        cls.item, _ = StandardItem.objects.get_or_create(
            code='QRY PMKP 1 EP 1',
            defaults=dict(
                category=cls.cat, sub_standard='PMKP 1',
                sub_title='Tata Laksana Risiko Uji',
                description='Pelaksanaan manajemen risiko di IGD', order=1,
            ),
        )
        cls.req, _ = EvidenceReq.objects.get_or_create(
            standard_item=cls.item, category_type='D',
            defaults=dict(title='Laporan Riset Keselamatan Pasien'),
        )
        cls.doc = EvidenceFile.objects.create(
            requirement=cls.req, file_name='laporan-riset-ksp.pdf', version=3, status='VALID',
        )

        cls.risiko = RisikoUnit.objects.create(
            unit=cls.unit, tahun=2026, periode='TRIWULAN_1', kategori_risiko='KLINIS',
            jenis_risiko='Klinis', masalah='Nyala cair oksigen medis habis',
            deskripsi_risiko='Cadangan oksigen medis di IGD tidak terpantau',
            dampak=3, probabilitas=2, strategi_mitigasi='KURANGI',
            rencana_aksi='Cek stok oksigen tiap shift', pj_mitigasi='Kepala IGD',
            status='PLAN',
        )
        cls.risiko_lain = RisikoUnit.objects.create(
            unit=cls.unit_lain, tahun=2026, periode='TAHUNAN', kategori_risiko='FINANSIAL',
            jenis_risiko='Finansial', masalah='Kurangnya stok obat mahal di gudang farmasi',
            deskripsi_risiko='Anggaran pengadaan obat kategori mahal tidak mencukupi',
            dampak=2, probabilitas=2, strategi_mitigasi='TRANSFER',
            rencana_aksi='Revisi RKA pengadaan obat', pj_mitigasi='Kepala Farmasi',
            status='PLAN',
        )
        cls.insiden = InsidenKeselamatan.objects.create(
            unit=cls.unit, tanggal_kejadian=datetime.date(2026, 10, 1),
            jenis_insiden='KTD', tingkat_keparahan='MODERAT',
            lokasi_kejadian='Ruang Resusitasi IGD',
            deskripsi_kejadian='Pemberian dosis obat salah',
        )


class PencarianAkses(PencarianBase):
    def test_anonim_ditolak(self):
        """A non-authenticated user cannot use search."""
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': 'IGD'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp['Location'])

    def test_otentikasi_dilayani(self):
        self.client.login(username='admin_test', password=self.password)
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': 'IGD'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('groups', resp.context)


class PencarianKonten(PencarianBase):
    def setUp(self):
        self.client.login(username='admin_test', password=self.password)

    def test_semua_sumber_menemukan_data_nyata(self):
        """Setiap sumber punya jalur query sendiri — uji satu per satu dengan
        kata kunci yang memang ada di data, bukan satu kata ajaib."""
        kasus = {
            'Tata Laksana': 'Elemen Penilaian (EP)',
            'riset': 'Dokumen Bukti (RDWOS)',
            'oksigen': 'Risiko PDCA',
            'Farmasi': 'Unit Kerja',
            'Resusitasi': 'Temuan & Insiden',
        }
        for kata, label in kasus.items():
            with self.subTest(kata=kata):
                resp = self.client.get(reverse('akreditasi:pencarian'), {'q': kata})
                labels = {g['label'] for g in resp.context['groups']}
                self.assertIn(label, labels)

    def test_detail_url_tidak_dead_link(self):
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': 'risiko'})
        urls = [item['url'] for g in resp.context['groups'] for item in g['items']]
        for url in urls:
            follow = self.client.get(url)
            self.assertEqual(follow.status_code, 200, 'unsafe URL: %s' % url)

    def test_kata_kunci_kosong_atau_terlalu_pendek(self):
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': ''})
        self.assertEqual(resp.context['groups'], [])
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': 'a'})
        self.assertEqual(resp.context['groups'], [])
        self.assertEqual(resp.context['total_results'], 0)

    def test_tidak_ada_hit_kembalikan_kosong_bukan_error(self):
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': 'zzzz-null-martian'})
        self.assertEqual(resp.context['groups'], [])
        self.assertContains(resp, 'Tidak ada hasil')


class PencarianLingkupUnit(PencarianBase):
    """Risiko harus mengikuti unit scope, perilaku yang sama dengan risiko_daftar."""

    def setUp(self):
        self.scoped_user = User.objects.create_user(username='igd_scoped', password=self.password)
        # is_unit_scoped adalah @property: dihitung dari role + unit_kerja,
        # jadi tidak bisa di-set langsung. KEPALA_UNIT + unit = scoped.
        _profile_with(self.scoped_user, role='KEPALA_UNIT', unit_kerja=self.unit)
        self.client.login(username='igd_scoped', password=self.password)

    def test_unit_scoped_melihat_risiko_unitnya(self):
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': 'nyala'})
        risiko_urls = [
            item['judul'] for g in resp.context['groups']
            if g['label'] == 'Risiko PDCA' for item in g['items']
        ]
        self.assertIn(self.risiko.masalah, risiko_urls)
        self.assertNotIn(self.risiko_lain.masalah, risiko_urls)

    def test_unit_scoped_tetap_lihat_lingkungan_global_sesuai_sumbernya(self):
        """ep_list/dokumen_hub/unit_tree/insiden_daftar tidak dicukur unit,
        jadi pencariannya juga tidak dicukur — unit farmasi tetap muncul."""
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': 'farmasi'})
        labels = {g['label'] for g in resp.context['groups']}
        self.assertIn('Unit Kerja', labels)
        self.assertIn('Elemen Penilaian (EP)', labels)


class PencarianBatasHalaman(PencarianBase):
    def test_limit_per_grup_dihormati(self):
        from akreditasi import search_views
        self.assertEqual(search_views.MAX_PER_GROUP, 8)
        for _ in range(12):
            EvidenceFile.objects.create(
                requirement=self.req,
                file_name='berkas-igd-%02d.pdf' % _,
            )
        self.client.login(username='admin_test', password=self.password)
        resp = self.client.get(reverse('akreditasi:pencarian'), {'q': 'berkas-igd'})
        dokumen = [g for g in resp.context['groups'] if g['label'] == 'Dokumen Bukti (RDWOS)']
        self.assertEqual(len(dokumen), 1)
        self.assertEqual(dokumen[0]['jumlah'], 8)
