from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.logbook_models import LogbookHarian, LogbookPasien
from sdm.models import Pegawai, KatalogTindakan, MasterProfesiPegawai, MasterJenjangProfesi, EntriLogbookKlinis

class LogbookTindakanViewTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(code='IGD-01', name='IGD', level=1)
        self.user = User.objects.create_user('perawat1', password='x')
        UserProfile.objects.create(user=self.user, role='STAF_NAKES', unit_kerja=self.unit)
        self.emp = Pegawai.objects.create(nama_lengkap='Perawat 1', akun=self.user, kategori='PPA', profesi='Perawat')
        
        profesi = MasterProfesiPegawai.objects.create(
            code='P-PRW-TEST', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        jenjang = MasterJenjangProfesi.objects.create(
            profesi=profesi, kode='PK-I-TEST', nama='Perawat I', urutan=1,
        )
        self.katalog = KatalogTindakan.objects.create(
            kode='TIND-TEST-01', nama='Pemasangan Infus', jenjang=jenjang, tingkat_supervisi='M',
        )
        
        self.lb = LogbookHarian.objects.create(
            unit=self.unit, tanggal=date(2026, 11, 1), shift='PAGI', dibuat_oleh=self.user,
        )
        self.pasien = LogbookPasien.objects.create(logbook=self.lb, nama_pasien='Tn. Anton', no_rm='RM101')
        self.client.force_login(self.user)

    def test_simpan_tindakan_mandiri_creates_entri_klinis(self):
        url = reverse('akreditasi:logbook_simpan_tindakan', args=[self.lb.pk])
        resp = self.client.post(url, {
            'pasien_id': self.pasien.pk,
            'katalog_id': str(self.katalog.pk),
            'kategori': 'M',
            'catatan': 'Jalur perifer lancar',
        })
        self.assertEqual(resp.status_code, 302)
        entri = EntriLogbookKlinis.objects.get(logbook_harian=self.lb)
        self.assertEqual(entri.employee, self.emp)
        self.assertEqual(entri.kategori, 'M')
        self.assertEqual(entri.jumlah_mandiri, 1)
        self.assertEqual(entri.jumlah_kolaborasi, 0)
        self.assertEqual(entri.jumlah_supervisi, 0)
        self.assertEqual(entri.pasien_ref, 'RM101')
        self.assertNotIn('Tn. Anton', entri.pasien_ref)
        self.assertEqual(entri.katalog_tindakan, self.katalog)

    def test_simpan_tindakan_tanpa_katalog_ditolak(self):
        url = reverse('akreditasi:logbook_simpan_tindakan', args=[self.lb.pk])
        resp = self.client.post(url, {
            'pasien_id': self.pasien.pk,
            'katalog_id': '',
            'kategori': 'M',
        })
        self.assertEqual(resp.status_code, 302)
        # Tidak membuat entri karena tindakan wajib dari master
        self.assertFalse(EntriLogbookKlinis.objects.filter(logbook_harian=self.lb).exists())

    def test_simpan_tindakan_kolaborasi_and_supervisi_sets_correct_counts(self):
        url = reverse('akreditasi:logbook_simpan_tindakan', args=[self.lb.pk])
        self.client.post(url, {
            'pasien_id': self.pasien.pk,
            'katalog_id': str(self.katalog.pk),
            'kategori': 'K',
        })
        entri_k = EntriLogbookKlinis.objects.filter(logbook_harian=self.lb, kategori='K').first()
        self.assertIsNotNone(entri_k)
        self.assertEqual(entri_k.jumlah_kolaborasi, 1)
        self.assertEqual(entri_k.jumlah_mandiri, 0)

    def test_hapus_tindakan_removes_entry(self):
        entri = EntriLogbookKlinis.objects.create(
            employee=self.emp,
            tanggal=self.lb.tanggal,
            unit_kerja=self.unit,
            logbook_harian=self.lb,
            logbook_pasien=self.pasien,
            katalog_tindakan=self.katalog,
            kategori='M',
            jumlah_mandiri=1,
            created_by=self.user,
        )
        url = reverse('akreditasi:logbook_hapus_tindakan', args=[self.lb.pk, entri.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(EntriLogbookKlinis.objects.filter(pk=entri.pk).exists())
