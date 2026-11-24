"""F4.0: dua penulis billing otomatis tidak boleh saling menyapu (money bug).

``klinis/services/tarif.py`` punya dua fungsi yang menulis baris
``BillingItem(kategori='JASA_MEDIS', sumber='ASESMEN')``:

``sync_billing``
    dari daftar kode ICD-9 form teks bebas lama; dipanggil
    ``pasien/views.py`` saat POST tidak membawa payload tindakan **dan**
    kunjungan belum punya baris ``TindakanAsesmen``.

``sync_billing_tindakan``
    dari baris ``TindakanAsesmen``; dipanggil ``simpan_tindakan``
    (``pasien/asesmen_tindakan.py``) saat POST membawa payload tindakan.

Keduanya dulu menutup dengan sapuan tanpa batas
``filter(kunjungan, sumber='ASESMEN').exclude(pk__in=keep).delete()``. Dua
akibatnya diuji di sini:

1. **Sapuan tanpa kategori.** Baris penunjang ber-``sumber='ASESMEN'`` dengan
   kategori LAB/RADIOLOGI/EKG ikut terhapus oleh penyimpanan tindakan.
2. **Kepemilikan bertumpuk.** Baris ICD-9 milik ``sync_billing`` terhapus oleh
   ``sync_billing_tindakan`` pada kunjungan yang sama, dan sebaliknya — jadi
   tagihan yang sah hilang tanpa jejak, bukan sekadar tertunda.

Kontrak yang ditegaskan: setiap fungsi hanya menyapu baris yang ia miliki.
"""
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from akreditasi.models import UnitKerja
from klinis.models import MasterIcd9
from klinis.services.tarif import refresh_acuan, sync_billing, sync_billing_tindakan
from pasien.models import BillingItem, KunjunganPasien, Pasien, TindakanAsesmen


class BillingOwnershipTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 3})
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user(username='dokter.owner', password='password123')
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Kepemilikan', no_rm='RM-OWN-001',
            tanggal_lahir='1990-01-01', jenis_kelamin='L',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-OWN-001', jenis_kunjungan='IGD',
            unit_kerja=UnitKerja.objects.filter(code='IGD').first(),
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='AKTIF',
        )

    def make_line(self, kode, urutan=1):
        line = TindakanAsesmen.objects.create(
            kunjungan=self.kunjungan, urutan=urutan, jenis='ICD9',
            icd9=MasterIcd9.objects.get(kode=kode), kode=kode,
            nama='Tindakan ' + kode, sumber_data='MASTER',
        )
        refresh_acuan(self.kunjungan, [line])
        line.save()
        return line

    def penunjang_row(self, kategori='LAB'):
        """Baris penunjang yang akan ditulis F4.6 (kategori bukan JASA_MEDIS)."""
        return BillingItem.objects.create(
            kunjungan=self.kunjungan, kategori=kategori, nama_item='Darah Rutin',
            harga_satuan=Decimal('85000'), kuantitas=Decimal('1'),
            kode_icd='', sumber='ASESMEN',
        )

    # ── Problem 1: sapuan tanpa kategori ────────────────────────────────────
    def test_tindakan_sync_keeps_penunjang_rows(self):
        lab = self.penunjang_row('LAB')
        rad = self.penunjang_row('RADIOLOGI')
        line = self.make_line('99.18')
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)

        self.assertTrue(BillingItem.objects.filter(pk=lab.pk).exists(),
                        'Baris penunjang LAB tersapu sync_billing_tindakan.')
        self.assertTrue(BillingItem.objects.filter(pk=rad.pk).exists(),
                        'Baris penunjang RADIOLOGI tersapu sync_billing_tindakan.')

    def test_icd9_sync_keeps_penunjang_rows(self):
        lab = self.penunjang_row('LAB')
        sync_billing(self.kunjungan, ['89.52'], user=self.user)
        self.assertTrue(BillingItem.objects.filter(pk=lab.pk).exists(),
                        'Baris penunjang LAB tersapu sync_billing.')

    # ── Problem 2: kepemilikan bertumpuk ────────────────────────────────────
    def test_tindakan_sync_does_not_delete_the_icd9_row(self):
        sync_billing(self.kunjungan, ['89.52'], user=self.user)
        legacy = BillingItem.objects.get(
            kunjungan=self.kunjungan, kategori='JASA_MEDIS', kode_icd='89.52')

        line = self.make_line('99.18')
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)

        self.assertTrue(
            BillingItem.objects.filter(pk=legacy.pk).exists(),
            'Baris ICD-9 milik sync_billing terhapus oleh sync_billing_tindakan.')

    def test_icd9_sync_does_not_delete_the_tindakan_row(self):
        line = self.make_line('99.18')
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        derived = BillingItem.objects.get(
            kunjungan=self.kunjungan, kategori='JASA_MEDIS', kode_icd='99.18')

        sync_billing(self.kunjungan, ['89.52'], user=self.user)

        self.assertTrue(
            BillingItem.objects.filter(pk=derived.pk).exists(),
            'Baris turunan TindakanAsesmen terhapus oleh sync_billing.')

    def test_both_origins_coexist_on_one_visit(self):
        """Kunjungan dengan dua asal tagihan: keduanya bertahan, tidak bergantian."""
        line = self.make_line('99.18')
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        sync_billing(self.kunjungan, ['89.52'], user=self.user)
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)

        kodes = set(BillingItem.objects.filter(
            kunjungan=self.kunjungan, kategori='JASA_MEDIS',
        ).exclude(sumber='MANUAL').values_list('kode_icd', flat=True))
        self.assertEqual(kodes, {'99.18', '89.52'})

    # ── Perilaku lama yang tidak boleh bergeser ─────────────────────────────
    def test_removing_the_line_still_removes_its_charge(self):
        line = self.make_line('99.18')
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        other = self.make_line('89.52', urutan=2)
        sync_billing_tindakan(self.kunjungan, [line, other], user=self.user)

        sync_billing_tindakan(self.kunjungan, [line], user=self.user)

        kodes = set(BillingItem.objects.filter(
            kunjungan=self.kunjungan, kategori='JASA_MEDIS',
        ).exclude(sumber='MANUAL').values_list('kode_icd', flat=True))
        self.assertEqual(kodes, {'99.18'})

    def test_manual_rows_are_never_touched(self):
        manual = BillingItem.objects.create(
            kunjungan=self.kunjungan, kategori='OBAT', nama_item='Paracetamol',
            harga_satuan=Decimal('50000'), kuantitas=Decimal('1'), sumber='MANUAL',
        )
        line = self.make_line('99.18')
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        sync_billing(self.kunjungan, ['89.52'], user=self.user)
        self.assertTrue(BillingItem.objects.filter(pk=manual.pk).exists())
