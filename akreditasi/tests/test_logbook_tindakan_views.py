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

    def test_simpan_tindakan_dengan_master_pasien(self):
        from pasien.models import Pasien
        p_master = Pasien.objects.create(
            no_rm='RM-MST-001', nama_lengkap='Pasien Master Uji',
            tanggal_lahir=date(1995, 5, 5), jenis_kelamin='L'
        )
        url = reverse('akreditasi:logbook_simpan_tindakan', args=[self.lb.pk])
        resp = self.client.post(url, {
            'pasien_id': f'master_{p_master.pk}',
            'katalog_id': str(self.katalog.pk),
            'kategori': 'M',
        })
        self.assertEqual(resp.status_code, 302)
        entri = EntriLogbookKlinis.objects.filter(logbook_harian=self.lb, pasien_ref='RM-MST-001').first()
        self.assertIsNotNone(entri)
        self.assertEqual(entri.pasien_ref, 'RM-MST-001')
        # Pasien otomatis terdaftar di shift (LogbookPasien)
        self.assertTrue(self.lb.pasien.filter(no_rm='RM-MST-001').exists())
        self.assertEqual(entri.logbook_pasien.no_rm, 'RM-MST-001')

    def test_simpan_tindakan_dengan_no_rm_manual(self):
        url = reverse('akreditasi:logbook_simpan_tindakan', args=[self.lb.pk])
        resp = self.client.post(url, {
            'pasien_id': 'manual',
            'no_rm_manual': 'RM-MANUAL-999',
            'katalog_id': str(self.katalog.pk),
            'kategori': 'M',
        })
        self.assertEqual(resp.status_code, 302)
        entri = EntriLogbookKlinis.objects.filter(logbook_harian=self.lb, pasien_ref='RM-MANUAL-999').first()
        self.assertIsNotNone(entri)
        self.assertEqual(entri.pasien_ref, 'RM-MANUAL-999')
        self.assertTrue(self.lb.pasien.filter(no_rm='RM-MANUAL-999').exists())

    def test_tambah_dan_hapus_pasien_manual_ke_shift(self):
        url_tambah = reverse('akreditasi:logbook_tambah_pasien', args=[self.lb.pk])
        resp = self.client.post(url_tambah, {
            'no_rm': 'RM-BARU-01',
            'nama_pasien': 'Pasien Tambah Manual',
            'jenis_kelamin': 'P',
            'umur': '28',
            'no_bed': 'Bed-1A',
            'triage': 'KUNING',
            'diagnosa': 'Obs Febris',
        })
        self.assertEqual(resp.status_code, 302)
        b = self.lb.pasien.filter(no_rm='RM-BARU-01').first()
        self.assertIsNotNone(b)
        self.assertEqual(b.nama_pasien, 'Pasien Tambah Manual')
        self.assertEqual(b.no_bed, 'Bed-1A')
        self.assertEqual(b.triage, 'KUNING')

        # Test hapus
        url_hapus = reverse('akreditasi:logbook_hapus_pasien', args=[self.lb.pk, b.pk])
        resp_del = self.client.post(url_hapus)
        self.assertEqual(resp_del.status_code, 302)
        self.assertFalse(self.lb.pasien.filter(no_rm='RM-BARU-01').exists())
