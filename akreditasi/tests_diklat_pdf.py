from datetime import date, time
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.logbook_nonmedis_models import (
    AktivitasNonMedis,
    LogbookNonMedis,
    MasterAktivitasNonMedis,
)
from sdm.models import Pegawai

User = get_user_model()


class LogbookNonMedisPdfTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='staf.diklat.pdf',
            password='password123',
            first_name='Staf',
            last_name='Diklat'
        )
        self.unit = UnitKerja.objects.create(
            name='Bagian Pendidikan dan Penelitian',
            code='BAG-DIKLIT-PDF'
        )
        UserProfile.objects.create(
            user=self.user,
            role='ADMIN_RS',
            unit_kerja=self.unit
        )

        self.logbook = LogbookNonMedis.objects.create(
            unit=self.unit,
            dibuat_oleh=self.user,
            tanggal=date(2026, 11, 10),
            shift='PAGI',
            jam_mulai=time(7, 30),
            jam_selesai=time(15, 30),
            pelaksana_nama='Staf Diklat'
        )

        self.master = MasterAktivitasNonMedis.objects.create(
            kode='DIKLAT-01',
            nama='Pelaksanaan Orientasi Pegawai Baru',
            ep_rekomendasi='KPS 8 / TKRS 9'
        )

        self.aktivitas = AktivitasNonMedis.objects.create(
            logbook=self.logbook,
            master=self.master,
            nama_aktivitas='Orientasi 15 Nakes Baru',
            detail_uraian='Penyampaian materi KPS dan PPI',
            jam_mulai=time(8, 0),
            jam_selesai=time(11, 0),
            ep_starkes='KPS 8',
            nama_bukti='Daftar Hadir & Notulen.pdf',
            pelaksana_nama='Staf Diklat'
        )

        self.client.login(username='staf.diklat.pdf', password='password123')

    def test_logbook_single_pdf_contains_activity_table(self):
        url = reverse('akreditasi:logbook_nonmedis_pdf', kwargs={'pk': self.logbook.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        # Response should be a valid PDF buffer (> 1000 bytes)
        self.assertGreater(len(response.content), 1000)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_logbook_rekap_pdf_bulanan(self):
        url = reverse('akreditasi:logbook_nonmedis_rekap_pdf') + f'?unit={self.unit.pk}&periode=BULANAN&tahun=2026&bulan=11'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_logbook_rekap_pdf_tahunan(self):
        url = reverse('akreditasi:logbook_nonmedis_rekap_pdf') + f'?unit={self.unit.pk}&periode=TAHUNAN&tahun=2026'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_logbook_rekap_pdf_5tahunan(self):
        url = reverse('akreditasi:logbook_nonmedis_rekap_pdf') + f'?unit={self.unit.pk}&periode=5TAHUNAN&tahun=2026'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
