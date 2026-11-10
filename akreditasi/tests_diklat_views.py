import datetime
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from akreditasi.logbook_nonmedis_models import (
    AktivitasNonMedis,
    LogbookNonMedis,
    MasterAktivitasNonMedis,
)
from akreditasi.models import UnitKerja

User = get_user_model()


class TestDiklatViews(TestCase):
    def setUp(self):
        call_command('seed_master_aktivitas_diklat')

        self.unit_diklat, _ = UnitKerja.objects.get_or_create(
            code='BAG-DIKLIT',
            defaults={'name': 'Bagian Pendidikan & Penelitian', 'level': 2, 'order': 10}
        )

        self.staf_diklat = User.objects.create_user(
            username='staf.diklat',
            password='password123',
            first_name='Budi',
            last_name='Diklat'
        )
        UserProfile.objects.create(
            user=self.staf_diklat,
            role='STAF_NAKES',
            unit_kerja=self.unit_diklat,
        )

        self.ka_diklat = User.objects.create_user(
            username='ka.diklat',
            password='password123',
            first_name='Siti',
            last_name='Kepala Diklat'
        )
        UserProfile.objects.create(
            user=self.ka_diklat,
            role='KEPALA_UNIT',
            unit_kerja=self.unit_diklat,
        )

        self.client_staf = Client()
        self.client_staf.login(username='staf.diklat', password='password123')

        self.client_ka = Client()
        self.client_ka.login(username='ka.diklat', password='password123')

    def test_api_master_aktivitas_returns_13_items_for_diklat(self):
        url = reverse('akreditasi:logbook_nonmedis_api_master_aktivitas') + '?kategori=DIKLAT'
        resp = self.client_staf.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['items']), 13)
        self.assertEqual(data['items'][0]['kode'], 'DIKLAT-01')
        self.assertIn('KPS 8', data['items'][0]['ep_rekomendasi'])

    def test_buat_logbook_diklat_with_jam_dinas_and_delegated_pelaksana(self):
        url = reverse('akreditasi:logbook_nonmedis_buat')
        post_data = {
            'unit': self.unit_diklat.pk,
            'tanggal': '2026-11-10',
            'jam_mulai': '07:30',
            'jam_selesai': '15:30',
            'shift': 'PAGI',
            'pelaksana_nama': 'Staf Pengganti / Delegasi',
        }
        # Client kepala can delegate pelaksana_nama
        resp = self.client_ka.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        entry = LogbookNonMedis.objects.get(unit=self.unit_diklat, tanggal='2026-11-10')
        self.assertEqual(entry.jam_mulai, datetime.time(7, 30))
        self.assertEqual(entry.jam_selesai, datetime.time(15, 30))
        self.assertEqual(entry.pelaksana_nama, 'Staf Pengganti / Delegasi')

    def test_tambah_aktivitas_row_with_ep_autolink_and_file_proof(self):
        entry = LogbookNonMedis.objects.create(
            unit=self.unit_diklat,
            tanggal=datetime.date(2026, 11, 10),
            pelaksana_nama='Budi Diklat',
            dibuat_oleh=self.staf_diklat,
            status='DRAF',
        )

        master_d1 = MasterAktivitasNonMedis.objects.get(kode='DIKLAT-01')
        dummy_file = SimpleUploadedFile(
            'notulen_orientasi.pdf',
            b'%PDF-1.4 dummy orientasi content',
            content_type='application/pdf'
        )

        url = reverse('akreditasi:logbook_nonmedis_tambah_aktivitas', kwargs={'pk': entry.pk})
        post_data = {
            'master_id': master_d1.pk,
            'nama_aktivitas': master_d1.nama,
            'jam_mulai': '08:00',
            'jam_selesai': '10:00',
            'detail_uraian': 'Pelaksanaan orientasi staf baru di aula lt. 3',
            'ep_starkes': '',  # empty to trigger autolink
            'pelaksana_nama': 'Budi Diklat',
            'nama_bukti': 'Notulen Orientasi Staf Baru',
            'dokumen_bukti': dummy_file,
        }

        resp = self.client_staf.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        row = AktivitasNonMedis.objects.get(logbook=entry)
        self.assertEqual(row.nama_aktivitas, master_d1.nama)
        self.assertEqual(row.ep_starkes, master_d1.ep_rekomendasi)
        self.assertEqual(row.durasi_jam, 2.0)
        self.assertTrue(bool(row.dokumen_bukti))
        self.assertEqual(row.nama_bukti, 'Notulen Orientasi Staf Baru')

    def test_hapus_aktivitas_row_by_owner(self):
        entry = LogbookNonMedis.objects.create(
            unit=self.unit_diklat,
            tanggal=datetime.date(2026, 11, 10),
            pelaksana_nama='Budi Diklat',
            dibuat_oleh=self.staf_diklat,
            status='DRAF',
        )
        row = AktivitasNonMedis.objects.create(
            logbook=entry,
            nama_aktivitas='Aktivitas Uji Hapus',
            urutan=1,
        )

        url = reverse('akreditasi:logbook_nonmedis_hapus_aktivitas',
                       kwargs={'pk': entry.pk, 'aktivitas_id': row.pk})
        resp = self.client_staf.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(AktivitasNonMedis.objects.filter(pk=row.pk).exists())
