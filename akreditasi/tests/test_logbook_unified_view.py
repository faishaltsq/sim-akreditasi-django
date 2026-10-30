from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.logbook_models import LogbookHarian
from sdm.models import Pegawai, EntriLogbookKlinis

class LogbookUnifiedViewTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(code='IGD-01', name='IGD', level=1)
        self.user = User.objects.create_user('perawat1', password='x')
        UserProfile.objects.create(user=self.user, role='STAF_NAKES', unit_kerja=self.unit)
        self.emp = Pegawai.objects.create(nama_lengkap='Perawat 1', akun=self.user, kategori='PPA', profesi='Perawat')
        self.lb = LogbookHarian.objects.create(unit=self.unit, tanggal=date(2026, 11, 1), shift='PAGI', dibuat_oleh=self.user)
        self.entri = EntriLogbookKlinis.objects.create(
            employee=self.emp,
            tanggal=self.lb.tanggal,
            unit_kerja=self.unit,
            logbook_harian=self.lb,
            tindakan='Resusitasi Jantung Paru',
            kategori='M',
            jumlah_mandiri=1,
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def test_unified_logbook_page_renders_tabs_and_both_contexts(self):
        # Default tab: harian
        resp = self.client.get(reverse('akreditasi:logbook_daftar'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Logbook Harian Shift', content)
        self.assertIn('Logbook Saya', content)
        self.assertIn('IGD', content)

        # Tab: saya
        resp_saya = self.client.get(reverse('akreditasi:logbook_daftar') + '?tab=saya')
        self.assertEqual(resp_saya.status_code, 200)
        content_saya = resp_saya.content.decode('utf-8')
        self.assertIn('Resusitasi Jantung Paru', content_saya)
        self.assertIn('Mandiri', content_saya)
