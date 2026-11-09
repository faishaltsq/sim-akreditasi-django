from decimal import Decimal
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from akreditasi.models import UnitKerja
from klinis.models import KelompokLayanan, MasterIcd9, KasusTindakan
from klinis.services.tarif import resolve, sync_billing
from pasien.models import Pasien, KunjunganPasien, BillingItem


class TarifServiceTest(TestCase):
    def setUp(self):
        call_command('seed_katalog_klinis')
        self.user = User.objects.create_user(username='dokter.uji', password='password123')
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Uji',
            no_rm='RM-TEST-001',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='L',
        )
        self.unit_igd = UnitKerja.objects.filter(code='IGD').first()
        self.unit_jantung = UnitKerja.objects.filter(code='ICCU').first()

        self.kunjungan_igd_umum = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-IGD-001',
            jenis_kunjungan='IGD',
            unit_kerja=self.unit_igd,
            penjamin='UMUM',
            tanggal_masuk=timezone.now(),
            status='AKTIF',
        )
        self.kunjungan_igd_bpjs = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-IGD-002',
            jenis_kunjungan='IGD',
            unit_kerja=self.unit_igd,
            penjamin='BPJS',
            tanggal_masuk=timezone.now(),
            status='AKTIF',
        )
        self.kunjungan_jantung = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-JNT-001',
            jenis_kunjungan='RANAP',
            unit_kerja=self.unit_jantung,
            penjamin='UMUM',
            tanggal_masuk=timezone.now(),
            status='AKTIF',
        )

    def test_bpjs_uses_bpjs_tariff(self):
        # 89.52 (EKG) on IGD
        tariff = resolve(self.kunjungan_igd_bpjs, '89.52')
        self.assertEqual(tariff, Decimal('120000.00'))

    def test_umum_uses_umum_tariff(self):
        # 89.52 (EKG) on IGD
        tariff = resolve(self.kunjungan_igd_umum, '89.52')
        self.assertEqual(tariff, Decimal('150000.00'))

    def test_returns_none_when_not_found(self):
        # unknown code
        tariff = resolve(self.kunjungan_igd_umum, '99.9999')
        self.assertIsNone(tariff)

    def test_same_code_differs_per_kelompok(self):
        # 99.29 differs: IGD Umum = 350.000 vs JANTUNG Umum = 1.200.000
        tariff_igd = resolve(self.kunjungan_igd_umum, '99.29')
        tariff_jnt = resolve(self.kunjungan_jantung, '99.29')
        self.assertEqual(tariff_igd, Decimal('350000.00'))
        self.assertEqual(tariff_jnt, Decimal('1200000.00'))
        self.assertNotEqual(tariff_igd, tariff_jnt)

    def test_sync_billing_idempotency_and_reconciliation(self):
        # Initial sync: 2 items
        items = sync_billing(self.kunjungan_igd_umum, ['89.52', '99.18'], user=self.user)
        self.assertEqual(len(items), 2)
        self.assertEqual(BillingItem.objects.filter(kunjungan=self.kunjungan_igd_umum, sumber='ASESMEN').count(), 2)

        # Existing manual item should not be affected
        manual_item = BillingItem.objects.create(
            kunjungan=self.kunjungan_igd_umum,
            kategori='OBAT',
            nama_item='Paracetamol Infus',
            harga_satuan=Decimal('50000.00'),
            kuantitas=Decimal('1'),
            sumber='MANUAL',
        )

        # Re-sync with only '89.52' (removing '99.18')
        updated_items = sync_billing(self.kunjungan_igd_umum, ['89.52'], user=self.user)
        self.assertEqual(len(updated_items), 1)

        asesmen_billing = BillingItem.objects.filter(kunjungan=self.kunjungan_igd_umum, sumber='ASESMEN')
        self.assertEqual(asesmen_billing.count(), 1)
        self.assertEqual(asesmen_billing.first().kode_icd, '89.52')

        # Manual item is preserved
        self.assertTrue(BillingItem.objects.filter(pk=manual_item.pk).exists())
