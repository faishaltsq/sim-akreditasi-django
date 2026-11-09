from decimal import Decimal
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja, StandardItem
from klinis.models import AturanEpAsesmen
from pasien.models import Pasien, KunjunganPasien, BillingItem, KorelasiEpAsesmen, LampiranAsesmen


class AsesmenSaveEpTarifTest(TestCase):
    def setUp(self):
        call_command('seed_katalog_klinis')
        self.user = User.objects.create_user(username='dokter.igd', password='password123')
        self.unit_igd = UnitKerja.objects.filter(code='IGD').first()
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Save Test',
            no_rm='RM-SAVE-001',
            tanggal_lahir='1992-02-02',
            jenis_kelamin='L',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-SAVE-001',
            jenis_kunjungan='IGD',
            unit_kerja=self.unit_igd,
            penjamin='UMUM',
            tanggal_masuk=timezone.now(),
            status='AKTIF',
        )
        self.client.force_login(self.user)

    def test_save_syncs_billing_and_ep_and_morse(self):
        url = reverse('pasien:igd_asesmen_awal_save', kwargs={'pk': self.kunjungan.pk})
        rule = AturanEpAsesmen.objects.first()

        data = {
            'anamnesis_rps': 'Pasien mengeluh nyeri dada tiba-tiba',
            'skrining_jatuh_skor': '45',
            'skrining_jatuh_grade': 'RISIKO_TINGGI',
            'jatuh_riwayat': '25',
            'jatuh_diagnosis': '15',
            'jatuh_alat': '0',
            'jatuh_infus': '20',
            'jatuh_jalan': '10',
            'jatuh_mental': '0',
            'asesmen_catatan_waktu': 'Dokter tiba dalam 5 menit setelah triase',
            'icd9_kode': ['89.52', '99.18'],
            f'ep_status_{rule.pk}': 'TERPENUHI',
            f'ep_catatan_{rule.pk}': 'Asesmen awal selesai < 24 jam',
        }

        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)

        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.skrining_jatuh_skor, 45)
        self.assertEqual(self.kunjungan.skrining_jatuh_grade, 'RISIKO_TINGGI')
        self.assertEqual(self.kunjungan.skrining_jatuh_detail.get('jatuh_riwayat'), 25)
        self.assertEqual(self.kunjungan.skrining_jatuh_detail.get('jatuh_infus'), 20)
        self.assertEqual(self.kunjungan.asesmen_catatan_waktu, 'Dokter tiba dalam 5 menit setelah triase')

        # Billing items synced (sumber='ASESMEN')
        billing_items = BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN')
        self.assertEqual(billing_items.count(), 2)
        kodes = set(billing_items.values_list('kode_icd', flat=True))
        self.assertEqual(kodes, {'89.52', '99.18'})

        # Korelasi EP persisted
        korelasi = KorelasiEpAsesmen.objects.filter(kunjungan=self.kunjungan)
        self.assertTrue(korelasi.filter(standard_item__sub_standard=rule.sub_standard, status='TERPENUHI').exists())

    def test_tarif_preview_endpoint_returns_items(self):
        url = reverse('pasien:api_tarif_preview')
        resp = self.client.get(url, {'kunjungan': self.kunjungan.pk, 'icd9': '89.52,99.9999'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data['total'])          # ada kode tak dikenal
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(data['items'][0]['kode'], '89.52')
        self.assertIsNotNone(data['items'][0]['nominal'])
        self.assertTrue(data['items'][0]['nama'])
        self.assertFalse(data['items'][1]['found'])

    def test_medis_save_accepts_attachment_and_rujukan(self):
        url = reverse('pasien:igd_asesmen_medis_save', kwargs={'pk': self.kunjungan.pk})
        f = SimpleUploadedFile('rujukan.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        resp = self.client.post(url, {
            'diagnosa_masuk': 'A09', 'icd9_tindakan': '89.52',
            'lampiran_files': f, 'lampiran_kategori': 'RUJUKAN',
        })
        self.assertEqual(resp.status_code, 302)
        lap = LampiranAsesmen.objects.get(kunjungan=self.kunjungan)
        self.assertEqual(lap.ukuran, f.size)
        self.assertEqual(lap.jenis, 'RUJUKAN')

    def test_upload_and_download_and_delete_lampiran(self):
        upload_url = reverse('pasien:asesmen_lampiran_upload', kwargs={'pk': self.kunjungan.pk})

        # Test invalid extension
        bad_file = SimpleUploadedFile("malware.exe", b"binarycontent", content_type="application/octet-stream")
        resp = self.client.post(upload_url, {'file': bad_file, 'jenis': 'ASESMEN'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(LampiranAsesmen.objects.filter(kunjungan=self.kunjungan).count(), 0)

        # Test valid PDF upload
        good_file = SimpleUploadedFile("ekg_pasien.pdf", b"%PDF-1.4 test content", content_type="application/pdf")
        resp = self.client.post(upload_url, {'file': good_file, 'jenis': 'PENUNJANG'})
        self.assertEqual(resp.status_code, 302)

        lap = LampiranAsesmen.objects.filter(kunjungan=self.kunjungan).first()
        self.assertIsNotNone(lap)
        self.assertEqual(lap.nama_asli, 'ekg_pasien.pdf')
        self.assertEqual(lap.jenis, 'PENUNJANG')

        # Test download
        dl_url = reverse('pasien:asesmen_lampiran_download', kwargs={'pk': self.kunjungan.pk, 'lampiran_id': lap.pk})
        resp_dl = self.client.get(dl_url)
        self.assertEqual(resp_dl.status_code, 200)
        self.assertIn('ekg_pasien.pdf', resp_dl['Content-Disposition'])

        # Test delete
        del_url = reverse('pasien:asesmen_lampiran_hapus', kwargs={'pk': self.kunjungan.pk, 'lampiran_id': lap.pk})
        resp_del = self.client.post(del_url)
        self.assertEqual(resp_del.status_code, 302)
        self.assertFalse(LampiranAsesmen.objects.filter(pk=lap.pk).exists())
