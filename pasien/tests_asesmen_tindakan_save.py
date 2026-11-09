from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from klinis.services.tarif import resolve
from pasien.models import BillingItem, KunjunganPasien, Pasien, TindakanAsesmen


class SimpanTindakanTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 3})
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user(username='dokter.baris', password='password123')
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Baris', no_rm='RM-BARIS-001',
            tanggal_lahir='1992-04-04', jenis_kelamin='L',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-BARIS-001', jenis_kunjungan='IGD',
            unit_kerja=UnitKerja.objects.filter(code='IGD').first(),
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='AKTIF',
        )
        self.client.force_login(self.user)
        self.url = reverse('pasien:igd_asesmen_medis_save', kwargs={'pk': self.kunjungan.pk})
        self.acuan = resolve(self.kunjungan, '99.18')

    def _post(self, extra):
        data = {'diagnosa_masuk': 'A09'}
        data.update(extra)
        return self.client.post(self.url, data)

    def _row(self, i, kode='99.18', nama='Pemasangan Infus', **kw):
        base = {
            f'tindakan_{i}_id': '',
            f'tindakan_{i}_jenis': 'ICD9',
            f'tindakan_{i}_kode': kode,
            f'tindakan_{i}_nama': nama,
            f'tindakan_{i}_sumber': 'MASTER',
            f'tindakan_{i}_tarif': '',
            f'tindakan_{i}_catatan_tarif': '',
            f'tindakan_{i}_ep_sub': '',
            f'tindakan_{i}_ep_status': 'BELUM',
            f'tindakan_{i}_ep_catatan': '',
        }
        base.update(kw)
        return base

    def test_saves_line_and_billing_from_acuan(self):
        resp = self._post(self._row(0))
        self.assertEqual(resp.status_code, 302)
        line = TindakanAsesmen.objects.get(kunjungan=self.kunjungan)
        self.assertEqual(line.kode, '99.18')
        self.assertEqual(line.tarif_acuan, self.acuan)
        self.assertIsNone(line.tarif)
        item = BillingItem.objects.get(kunjungan=self.kunjungan, sumber='ASESMEN')
        self.assertEqual(item.harga_satuan, self.acuan)
        self.assertEqual(line.billing_item_id, item.pk)

    def test_override_with_note_is_saved(self):
        self._post(self._row(0, **{
            'tindakan_0_tarif': '175000',
            'tindakan_0_catatan_tarif': 'Tambahan BHP spuit 5cc',
        }))
        line = TindakanAsesmen.objects.get(kunjungan=self.kunjungan)
        self.assertEqual(line.tarif, Decimal('175000'))
        self.assertEqual(line.tarif_acuan, self.acuan)
        self.assertEqual(
            BillingItem.objects.get(kunjungan=self.kunjungan, sumber='ASESMEN').harga_satuan,
            Decimal('175000'))

    def test_override_without_note_is_rejected_atomically(self):
        resp = self._post(self._row(0, **{'tindakan_0_tarif': '175000'}))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(TindakanAsesmen.objects.filter(kunjungan=self.kunjungan).exists())
        self.assertFalse(BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN').exists())

    def test_duplicate_code_keeps_one_line(self):
        self._post({
            **self._row(0),
            **self._row(1, nama='Infus duplikat'),
        })
        self.assertEqual(TindakanAsesmen.objects.filter(kunjungan=self.kunjungan).count(), 1)
        self.assertEqual(BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN').count(), 1)

    def test_resave_is_idempotent(self):
        self._post(self._row(0))
        line = TindakanAsesmen.objects.get(kunjungan=self.kunjungan)
        self._post(self._row(0, **{'tindakan_0_id': str(line.pk), 'tindakan_0_nama': 'Infus RL 20 tpm'}))
        self.assertEqual(TindakanAsesmen.objects.filter(kunjungan=self.kunjungan).count(), 1)
        self.assertEqual(BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN').count(), 1)
        line.refresh_from_db()
        self.assertEqual(line.nama, 'Infus RL 20 tpm')

    def test_removed_line_deletes_its_billing(self):
        self._post({
            **self._row(0),
            **self._row(1, kode='89.52', nama='EKG 12 Lead'),
        })
        self.assertEqual(BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN').count(), 2)

        kept = TindakanAsesmen.objects.get(kunjungan=self.kunjungan, kode='99.18')
        self._post({
            **self._row(0, **{'tindakan_0_id': str(kept.pk)}),
            **self._row(1, **{'tindakan_1_hapus': '1'}),
        })
        self.assertEqual(TindakanAsesmen.objects.filter(kunjungan=self.kunjungan).count(), 1)
        kodes = set(BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN')
                    .values_list('kode_icd', flat=True))
        self.assertEqual(kodes, {'99.18'})

    def test_ep_status_persisted_and_auto_primary_when_empty(self):
        self._post(self._row(0, **{'tindakan_0_ep_status': 'TERPENUHI'}))
        line = TindakanAsesmen.objects.get(kunjungan=self.kunjungan)
        self.assertEqual(line.ep_status, 'TERPENUHI')
        self.assertIsNotNone(line.standard_item)
        self.assertEqual(line.standard_item.sub_standard, 'PAP 3')
        self.assertTrue(line.ep_lengkap)

    def test_unknown_ep_sub_standard_is_skipped(self):
        self._post(self._row(0, **{'tindakan_0_ep_sub': 'KPR 3'}))
        line = TindakanAsesmen.objects.get(kunjungan=self.kunjungan)
        self.assertIsNone(line.standard_item)

    def test_unknown_icd9_code_is_not_saved(self):
        self._post(self._row(0, kode='99.9999'))
        self.assertFalse(TindakanAsesmen.objects.filter(kunjungan=self.kunjungan).exists())

    def test_manual_billing_survives_line_save(self):
        manual = BillingItem.objects.create(
            kunjungan=self.kunjungan, kategori='OBAT', nama_item='Paracetamol',
            harga_satuan=Decimal('50000'), kuantitas=Decimal('1'), sumber='MANUAL',
        )
        self._post(self._row(0))
        self.assertTrue(BillingItem.objects.filter(pk=manual.pk).exists())

    def test_legacy_text_path_still_syncs(self):
        self._post({'icd9_tindakan': '89.52 - EKG 12 Lead'})
        self.assertTrue(BillingItem.objects.filter(
            kunjungan=self.kunjungan, sumber='ASESMEN', kode_icd='89.52').exists())
        self.assertFalse(TindakanAsesmen.objects.filter(kunjungan=self.kunjungan).exists())

    def test_summary_text_reflects_lines(self):
        self._post(self._row(0, nama='Infus RL 20 tpm'))
        self.kunjungan.refresh_from_db()
        self.assertIn('Infus RL 20 tpm', self.kunjungan.icd9_tindakan)
