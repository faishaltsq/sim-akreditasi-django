from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.logbook_models import LogbookHarian, LogbookPasien
from sdm.models import Pegawai, EntriLogbookKlinis, KatalogTindakan, MasterProfesiPegawai, MasterJenjangProfesi

class LogbookHarianIntegrationTest(TestCase):
    def test_entri_logbook_links_to_logbook_harian_and_pasien(self):
        unit = UnitKerja.objects.create(code='IGD-TEST', name='IGD Test', level=1)
        user = User.objects.create_user('nurse1', password='x')
        emp = Pegawai.objects.create(nama_lengkap='Nurse 1', akun=user, kategori='PPA', profesi='Perawat')
        lb = LogbookHarian.objects.create(unit=unit, tanggal=date(2026, 11, 1), shift='PAGI')
        pasien = LogbookPasien.objects.create(logbook=lb, nama_pasien='Tn. Ahmad', no_rm='RM001')
        profesi = MasterProfesiPegawai.objects.create(
            code='P-PRW', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        jenjang = MasterJenjangProfesi.objects.create(
            profesi=profesi, kode='PK-I', nama='Perawat I', urutan=1,
        )
        katalog = KatalogTindakan.objects.create(
            kode='TIND-TEST-01', nama='Pemasangan Infus', jenjang=jenjang, tingkat_supervisi='M',
        )
        
        entry = EntriLogbookKlinis.objects.create(
            employee=emp,
            tanggal=lb.tanggal,
            unit_kerja=unit,
            logbook_harian=lb,
            logbook_pasien=pasien,
            katalog_tindakan=katalog,
            kategori='M',
            jumlah_mandiri=1,
            created_by=user,
        )
        self.assertEqual(entry.logbook_harian, lb)
        self.assertEqual(entry.logbook_pasien, pasien)
        self.assertIn(entry, lb.tindakan_klinis.all())
