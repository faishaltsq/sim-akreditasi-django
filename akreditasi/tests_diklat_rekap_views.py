from datetime import date, time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from akreditasi.models import UnitKerja
from akreditasi.logbook_nonmedis_models import (
    LogbookNonMedis,
    MasterAktivitasNonMedis,
    AktivitasNonMedis,
)
from accounts.models import UserProfile

User = get_user_model()


class LogbookNonMedisRekapViewTests(TestCase):
    def setUp(self):
        self.unit_diklit = UnitKerja.objects.filter(code='BAG-DIKLIT').first()
        if not self.unit_diklit:
            self.unit_diklit = UnitKerja.objects.create(
                code='BAG-DIKLIT',
                name='Bagian Diklit & Pelatihan',
                tipe_unit='PENUNJANG_NON_KLINIS'
            )

        self.user = User.objects.create_user(
            username='ka.diklit',
            password='password123',
            first_name='Kepala',
            last_name='Diklit'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='KEPALA_UNIT',
            unit_kerja=self.unit_diklit
        )
        self.client.login(username='ka.diklit', password='password123')

        self.master1 = MasterAktivitasNonMedis.objects.create(
            kode='DIKLAT-01',
            nama='Pelaksanaan Orientasi Pegawai Baru',
            ep_rekomendasi='KPS 8, TKRS 9',
            kategori_unit='DIKLAT'
        )
        self.master6 = MasterAktivitasNonMedis.objects.create(
            kode='DIKLAT-06',
            nama='Koordinasi Mandatory Training BHD & PPI',
            ep_rekomendasi='KPS 8, SKP, PPI, MFK',
            kategori_unit='DIKLAT'
        )

        self.lb = LogbookNonMedis.objects.create(
            unit=self.unit_diklit,
            tanggal=date.today(),
            shift='PAGI',
            jam_mulai=time(8, 0),
            jam_selesai=time(16, 0),
            pelaksana_nama='Staf Diklat 1',
            dibuat_oleh=self.user,
            status='DISETUJUI'
        )

        self.akt1 = AktivitasNonMedis.objects.create(
            logbook=self.lb,
            master=self.master1,
            nama_aktivitas='Orientasi 10 Dokter Baru',
            jam_mulai=time(8, 30),
            jam_selesai=time(11, 30),
            ep_starkes='KPS 8, TKRS 9',
            nama_bukti='Absensi Orientasi.pdf'
        )
        self.akt2 = AktivitasNonMedis.objects.create(
            logbook=self.lb,
            master=self.master6,
            nama_aktivitas='Pelatihan BHD Batch 1',
            jam_mulai=time(13, 0),
            jam_selesai=time(15, 0),
            ep_starkes='KPS 8, SKP, PPI',
            nama_bukti='Sertifikat BHD.pdf'
        )

    def test_rekap_dashboard_loads_200(self):
        url = reverse('akreditasi:logbook_nonmedis_rekap')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'akreditasi/logbook_nonmedis_rekap.html')

    def test_rekap_dashboard_contains_all_tabs(self):
        url = reverse('akreditasi:logbook_nonmedis_rekap')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('Bulanan', content)
        self.assertIn('Tahunan', content)
        self.assertIn('5 Tahunan', content)
        self.assertIn('Kontrol', content)

    def test_rekap_dashboard_filters(self):
        url = reverse('akreditasi:logbook_nonmedis_rekap')
        res = self.client.get(url, {
            'unit': self.unit_diklit.pk,
            'tahun': date.today().year,
            'bulan': date.today().month,
            'periode': 'BULANAN'
        })
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('Orientasi 10 Dokter Baru', content)
        self.assertIn('DIKLAT-01', content)
        self.assertIn('KPS 8', content)

    def test_rekap_dashboard_annual_metrics(self):
        url = reverse('akreditasi:logbook_nonmedis_rekap')
        res = self.client.get(url, {
            'unit': self.unit_diklit.pk,
            'tahun': date.today().year,
            'periode': 'TAHUNAN'
        })
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('Mandatory Training', content)
        self.assertIn('20 JPL', content)

    def test_rekap_dashboard_5year_metrics(self):
        url = reverse('akreditasi:logbook_nonmedis_rekap')
        res = self.client.get(url, {
            'unit': self.unit_diklit.pk,
            'tahun': date.today().year,
            'periode': '5TAHUNAN'
        })
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('Siklus STARKES', content)
