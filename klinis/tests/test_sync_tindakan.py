from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from akreditasi.models import UnitKerja
from klinis.models import MasterIcd9
from klinis.services.tarif import refresh_acuan, resolve, sync_billing_tindakan
from pasien.models import BillingItem, KunjunganPasien, Pasien, TindakanAsesmen


class SyncBillingTindakanTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 3})
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user(username='dokter.sync', password='password123')
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Sync', no_rm='RM-SYNC-001',
            tanggal_lahir='1990-01-01', jenis_kelamin='L',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-SYNC-001', jenis_kunjungan='IGD',
            unit_kerja=UnitKerja.objects.filter(code='IGD').first(),
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='AKTIF',
        )
        self.acuan = resolve(self.kunjungan, '99.18')
        self.assertIsNotNone(self.acuan)
        self.icd9 = MasterIcd9.objects.get(kode='99.18')

    def _line(self, **kwargs):
        defaults = dict(
            kunjungan=self.kunjungan, urutan=1, jenis='ICD9', icd9=self.icd9,
            kode='99.18', nama='Pemasangan Infus', sumber_data='MASTER',
        )
        defaults.update(kwargs)
        return TindakanAsesmen.objects.create(**defaults)

    def test_override_survives_resync(self):
        line = self._line(tarif=Decimal('175000'))
        for _ in range(2):
            refresh_acuan(self.kunjungan, [line])
            line.save()
            sync_billing_tindakan(self.kunjungan, [line], user=self.user)
            item = BillingItem.objects.get(kunjungan=self.kunjungan, sumber='ASESMEN', kode_icd='99.18')
            self.assertEqual(item.harga_satuan, Decimal('175000'))
        line.refresh_from_db()
        self.assertEqual(line.tarif_acuan, self.acuan)
        self.assertEqual(line.tarif, Decimal('175000'))

    def test_null_override_uses_acuan(self):
        line = self._line(tarif=None)
        refresh_acuan(self.kunjungan, [line])
        line.save()
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        item = BillingItem.objects.get(kunjungan=self.kunjungan, sumber='ASESMEN', kode_icd='99.18')
        self.assertEqual(item.harga_satuan, self.acuan)
        self.assertEqual(item.nama_item, 'Pemasangan Infus')
        self.assertEqual(item.kuantitas, Decimal('1'))

    def test_line_without_tariff_writes_nothing(self):
        line = self._line(kode='99.9999', icd9=None, tarif=None)
        refresh_acuan(self.kunjungan, [line])
        line.save()
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        self.assertFalse(BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN').exists())

    def test_removing_line_deletes_only_its_billing(self):
        keep = self._line(tarif=None)
        drop = self._line(urutan=2, kode='89.52', icd9=MasterIcd9.objects.get(kode='89.52'),
                          nama='EKG', tarif=None)
        for line in (keep, drop):
            refresh_acuan(self.kunjungan, [line])
            line.save()
        sync_billing_tindakan(self.kunjungan, [keep, drop], user=self.user)
        self.assertEqual(BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN').count(), 2)

        sync_billing_tindakan(self.kunjungan, [keep], user=self.user)
        kodes = set(BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN')
                    .values_list('kode_icd', flat=True))
        self.assertEqual(kodes, {'99.18'})

    def test_manual_billing_untouched(self):
        manual = BillingItem.objects.create(
            kunjungan=self.kunjungan, kategori='OBAT', nama_item='Paracetamol',
            harga_satuan=Decimal('50000'), kuantitas=Decimal('1'), sumber='MANUAL',
        )
        line = self._line(tarif=None)
        refresh_acuan(self.kunjungan, [line])
        line.save()
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        self.assertTrue(BillingItem.objects.filter(pk=manual.pk).exists())

    def test_updating_tarif_updates_existing_row(self):
        line = self._line(tarif=None)
        refresh_acuan(self.kunjungan, [line])
        line.save()
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        line.tarif = Decimal('200000')
        line.save()
        sync_billing_tindakan(self.kunjungan, [line], user=self.user)
        self.assertEqual(
            BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN').count(), 1)
        self.assertEqual(
            BillingItem.objects.get(kunjungan=self.kunjungan, sumber='ASESMEN').harga_satuan,
            Decimal('200000'))
