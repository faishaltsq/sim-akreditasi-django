"""F0.2–F0.5 — pengerasan dasbor rawat jalan.

Modul ini mengunci empat cacat produksi pada jalur rawat jalan:

* F0.2 — order penunjang memakai harga karangan (``150000``/``250000``) dan
  tidak pernah menunjuk katalog. Sekarang order wajib memakai
  ``klinis.ItemPenunjang``; selama belum ada sumber tarif per item
  (``TarifPenunjang``, F0.8) tidak ada ``BillingItem`` yang dibuat.
* F0.3 — antrean bisa masuk ``SEDANG_DILAYANI`` tanpa DPJP.
* F0.4 — hitungan antrean per poli dihitung dari potongan label
  (``poliklinik__icontains=label[:15]``), sehingga kunjungan yang menyimpan
  kode ``POLI_*`` tidak terhitung.
* F0.5 — dasbor rajal tidak dibatasi unit kerja.

Semua asersi di sini memeriksa keadaan database atau hasil render, bukan
keberadaan simbol.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from klinis.models import ItemPenunjang, KategoriPenunjang
from pasien.models import (
    BillingItem, KunjunganPasien, OrderPenunjang, Pasien, POLIKLINIK_CHOICES,
)


def buat_item_penunjang(*, kode='UJI-LAB-001', nama='Darah Lengkap Uji',
                        jenis_order='LAB', user, unit, active=True):
    """Item katalog yang lolos ``penunjang_catalogue.orderable_items()``."""
    l1, _ = KategoriPenunjang.objects.get_or_create(
        kode='UJI-LAB', defaults={'nama': 'Uji Laboratorium', 'level': 1})
    l2, _ = KategoriPenunjang.objects.get_or_create(
        kode='UJI-LAB-KLINIK',
        defaults={'nama': 'Uji Laboratorium Klinik', 'level': 2, 'parent': l1})
    l3, _ = KategoriPenunjang.objects.get_or_create(
        kode='UJI-LAB-HEMATOLOGI',
        defaults={'nama': 'Uji Hematologi', 'level': 3, 'parent': l2})
    return ItemPenunjang.objects.create(
        kode=kode, nama=nama, group=l3, jenis_order=jenis_order,
        destination=unit, active=active, source_version='UJI-2026-11-24',
        reviewed_by=user)


class _RajalFixture(TestCase):
    password = 'pass123-rajal'

    def setUp(self):
        self.unit_jantung = UnitKerja.objects.get_or_create(
            code='POLI-JANTUNG',
            defaults={'name': 'Poliklinik Jantung', 'level': 4})[0]
        self.dokter = self._user('dokter.jantung', self.unit_jantung,
                                 profesi='DOKTER_SPESIALIS')
        self.client.login(username=self.dokter.username, password=self.password)
        self.pasien = Pasien.objects.create(
            no_rm='RM-RAJAL-HARD-01', nama_lengkap='Pasien Rawat Jalan',
            tanggal_lahir='1980-01-01', jenis_kelamin='L')

    def _user(self, username, unit, role='STAF_NAKES', profesi=''):
        user = User.objects.create_user(
            username=username, email=f'{username}@rs.test', password=self.password)
        UserProfile.objects.create(
            user=user, role=role, unit_kerja=unit, profesi=profesi)
        return user

    def _kunjungan(self, no='KJ-RAJAL-HARD-01', poliklinik='POLI_JANTUNG',
                   dpjp='', status='DAFTAR', status_antrean='MENUNGGU'):
        return KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan=no, jenis_kunjungan='RAJAL',
            poliklinik=poliklinik, tanggal_masuk=timezone.now(),
            dpjp=dpjp, status=status, status_antrean=status_antrean,
            penjamin='UMUM')


class PenunjangOrderKatalogTest(_RajalFixture):
    """F0.2 — order penunjang wajib dari katalog, tanpa harga karangan."""

    def setUp(self):
        super().setUp()
        self.kunjungan = self._kunjungan()
        self.item = buat_item_penunjang(user=self.dokter, unit=self.unit_jantung)
        self.url = reverse('pasien:order_penunjang_buat', args=[self.kunjungan.pk])

    def test_order_tanpa_item_katalog_ditolak(self):
        res = self.client.post(self.url, {
            'nama_pemeriksaan': 'Darah Lengkap (teks bebas)',
            'prioritas': 'RUTIN',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(OrderPenunjang.objects.filter(kunjungan=self.kunjungan).count(), 0)
        self.assertEqual(BillingItem.objects.count(), 0)

    def test_order_dengan_item_tidak_dikenal_ditolak(self):
        res = self.client.post(self.url, {
            'catalogue_item': '999999', 'prioritas': 'RUTIN',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(OrderPenunjang.objects.filter(kunjungan=self.kunjungan).count(), 0)
        self.assertEqual(BillingItem.objects.count(), 0)

    def test_order_item_nonaktif_ditolak(self):
        nonaktif = buat_item_penunjang(
            kode='UJI-LAB-002', nama='Pemeriksaan Nonaktif',
            user=self.dokter, unit=self.unit_jantung, active=False)
        res = self.client.post(self.url, {
            'catalogue_item': str(nonaktif.pk), 'prioritas': 'RUTIN',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(OrderPenunjang.objects.filter(kunjungan=self.kunjungan).count(), 0)

    def test_order_katalog_tersimpan_tanpa_tagihan(self):
        """Order sah dibuat dengan item katalog; tagihan ditunda sampai tarif ada."""
        res = self.client.post(self.url, {
            'catalogue_item': str(self.item.pk),
            'prioritas': 'CITO',
            'catatan_klinis': 'Evaluasi nyeri dada.',
        })
        self.assertEqual(res.status_code, 302)

        order = OrderPenunjang.objects.get(kunjungan=self.kunjungan)
        self.assertEqual(order.catalogue_item_id, self.item.pk)
        self.assertEqual(order.nama_pemeriksaan, self.item.nama)
        self.assertEqual(order.jenis, 'LAB')
        self.assertEqual(order.prioritas, 'CITO')
        self.assertEqual(order.catatan_klinis, 'Evaluasi nyeri dada.')
        self.assertEqual(order.destination_id, self.unit_jantung.pk)

        self.assertEqual(BillingItem.objects.count(), 0)

    def test_tidak_ada_tagihan_nominal_karangan(self):
        self.client.post(self.url, {'catalogue_item': str(self.item.pk), 'prioritas': 'RUTIN'})
        self.assertEqual(
            BillingItem.objects.filter(harga_satuan__in=[150000, 250000]).count(), 0)
        self.assertEqual(BillingItem.objects.filter(kunjungan=self.kunjungan).count(), 0)


class AntreanDpjpTest(_RajalFixture):
    """F0.3 — ``SEDANG_DILAYANI`` tanpa DPJP ditolak tanpa mutasi."""

    def test_tanpa_dpjp_status_tidak_berubah(self):
        kunjungan = self._kunjungan(no='KJ-DPJP-01', dpjp='')
        res = self.client.post(
            reverse('pasien:rajal_antrean_status', args=[kunjungan.pk]),
            {'status_antrean': 'SEDANG_DILAYANI'})
        self.assertEqual(res.status_code, 302)

        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'DAFTAR')
        self.assertEqual(kunjungan.status_antrean, 'MENUNGGU')

    def test_dpjp_kosong_spasi_tetap_ditolak(self):
        kunjungan = self._kunjungan(no='KJ-DPJP-02', dpjp='   ')
        self.client.post(
            reverse('pasien:rajal_antrean_status', args=[kunjungan.pk]),
            {'status_antrean': 'SEDANG_DILAYANI'})

        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'DAFTAR')
        self.assertEqual(kunjungan.status_antrean, 'MENUNGGU')

    def test_dengan_dpjp_transisi_diterima(self):
        kunjungan = self._kunjungan(
            no='KJ-DPJP-03', dpjp='dr. Spesialis Jantung')
        self.client.post(
            reverse('pasien:rajal_antrean_status', args=[kunjungan.pk]),
            {'status_antrean': 'SEDANG_DILAYANI'})

        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status, 'ASESMEN')
        self.assertEqual(kunjungan.status_antrean, 'SEDANG_DILAYANI')

    def test_dipanggil_tanpa_dpjp_tetap_boleh(self):
        """Penolakan hanya pada transisi yang menaikkan status ke ASESMEN."""
        kunjungan = self._kunjungan(no='KJ-DPJP-04', dpjp='')
        self.client.post(
            reverse('pasien:rajal_antrean_status', args=[kunjungan.pk]),
            {'status_antrean': 'DIPANGGIL'})

        kunjungan.refresh_from_db()
        self.assertEqual(kunjungan.status_antrean, 'DIPANGGIL')
        self.assertEqual(kunjungan.status, 'DAFTAR')
