import datetime
from django.contrib.auth import get_user_model
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


class TestDiklatUITemplate(TestCase):
    def setUp(self):
        call_command('seed_master_aktivitas_diklat')
        self.unit_diklat, _ = UnitKerja.objects.get_or_create(
            code='BAG-DIKLIT',
            defaults={'name': 'Bagian Pendidikan & Penelitian', 'level': 2, 'order': 10}
        )
        self.staf = User.objects.create_user(
            username='staf.diklat.ui',
            password='password123',
            first_name='Ahmad',
            last_name='Diklat'
        )
        UserProfile.objects.create(
            user=self.staf,
            role='STAF_NAKES',
            unit_kerja=self.unit_diklat,
        )
        self.client = Client()
        self.client.login(username='staf.diklat.ui', password='password123')

        self.entry = LogbookNonMedis.objects.create(
            unit=self.unit_diklat,
            tanggal=datetime.date(2026, 11, 10),
            jam_mulai=datetime.time(7, 30),
            jam_selesai=datetime.time(15, 30),
            pelaksana_nama='Ahmad Diklat',
            dibuat_oleh=self.staf,
            status='DRAF',
        )

        self.master_orientasi = MasterAktivitasNonMedis.objects.get(kode='DIKLAT-01')
        self.aktivitas = AktivitasNonMedis.objects.create(
            logbook=self.entry,
            master=self.master_orientasi,
            urutan=1,
            jam_mulai=datetime.time(8, 0),
            jam_selesai=datetime.time(10, 0),
            nama_aktivitas=self.master_orientasi.nama,
            detail_uraian='Orientasi 15 perawat baru di ruang diklat',
            ep_starkes='KPS 8 / TKRS 9',
            pelaksana_nama='Ahmad Diklat',
            nama_bukti='Absensi Orientasi.pdf',
        )

    def test_form_renders_jam_dinas_inputs(self):
        url = reverse('akreditasi:logbook_nonmedis_buat')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'jam_mulai')
        self.assertContains(resp, 'jam_selesai')

    def test_detail_renders_aktivitas_table_and_hours(self):
        url = reverse('akreditasi:logbook_nonmedis_detail', kwargs={'pk': self.entry.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Check activity row content
        self.assertContains(resp, 'Orientasi 15 perawat baru')
        self.assertContains(resp, 'KPS 8 / TKRS 9')
        self.assertContains(resp, '08.00 - 10.00')
        # Check master dropdown or master catalog
        self.assertContains(resp, 'DIKLAT-01')
        self.assertContains(resp, 'Absensi Orientasi.pdf')
