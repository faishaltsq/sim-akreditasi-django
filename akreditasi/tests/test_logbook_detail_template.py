from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.logbook_models import LogbookHarian, LogbookPasien
from sdm.models import Pegawai, MasterProfesiPegawai, MasterJenjangProfesi, KatalogTindakan

class LogbookDetailTemplateTest(TestCase):
    def test_logbook_detail_renders_tindakan_klinis_section_and_categories(self):
        unit = UnitKerja.objects.create(code='IGD-01', name='IGD', level=1)
        user = User.objects.create_user('perawat1', password='x')
        UserProfile.objects.create(user=user, role='STAF_NAKES', unit_kerja=unit)
        emp = Pegawai.objects.create(nama_lengkap='Perawat 1', akun=user, kategori='PPA', profesi='Perawat')
        
        profesi = MasterProfesiPegawai.objects.create(
            code='P-PRW-TEST', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        jenjang = MasterJenjangProfesi.objects.create(
            profesi=profesi, kode='PK-I-TEST', nama='Perawat I', urutan=1,
        )
        KatalogTindakan.objects.create(
            kode='TIND-TEST-01', nama='Pemasangan Infus', jenjang=jenjang, tingkat_supervisi='M',
        )
        
        lb = LogbookHarian.objects.create(unit=unit, tanggal=date(2026, 11, 1), shift='PAGI', dibuat_oleh=user)
        LogbookPasien.objects.create(logbook=lb, nama_pasien='Tn. Anton', no_rm='RM101')
        self.client.force_login(user)
        
        resp = self.client.get(reverse('akreditasi:logbook_detail', args=[lb.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Tindakan Klinis Shift', content)
        self.assertIn('Mandiri', content)
        self.assertIn('Kolaborasi', content)
        self.assertIn('Supervisi', content)
        self.assertIn('Pilih Pasien (No. RM)', content)
        self.assertIn('No. RM: RM101', content)
        self.assertIn('Pilih Tindakan Klinis (Master Database)', content)
        self.assertIn('Pemasangan Infus', content)
        # Ensure the select option for patient has NO patient name
        self.assertNotIn('Tn. Anton (RM: RM101)', content)
