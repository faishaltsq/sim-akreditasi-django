from django.core.management import call_command
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import TestCase
from accounts.models import UserProfile
from pasien.models import Ruangan
from akreditasi.models import UnitKerja
from akreditasi.layanan_unit import RUANGAN_UNIT_CODE
from akreditasi.logbook import _unit_pilihan


class RuanganUnitKerjaLinkageTest(TestCase):
    def test_ruangan_linked_to_unit_kerja(self):
        """Every seeded Ruangan in RUANGAN_UNIT_CODE must have unit_kerja populated."""
        call_command('seed_pasien_data')
        for kode, unit_code in RUANGAN_UNIT_CODE.items():
            unit = UnitKerja.objects.filter(code=unit_code).first()
            self.assertIsNotNone(unit, f"UnitKerja with code {unit_code} must exist")
            r = Ruangan.objects.filter(kode=kode).first()
            self.assertIsNotNone(r, f"Ruangan with code {kode} must exist")
            self.assertIsNotNone(r.unit_kerja, f"Ruangan {kode} unit_kerja must not be None")
            self.assertEqual(r.unit_kerja.code, unit_code)


class UnitPilihanScopingTest(TestCase):
    def setUp(self):
        self.pelaksana = UnitKerja.objects.create(code='DIR-OPS-T', name='Direktorat Ops Test', level=1)
        self.irin = UnitKerja.objects.create(code='IRIN-T', name='Instalasi Rawat Inap Test', level=2, parent=self.pelaksana)
        self.bangsal = UnitKerja.objects.create(code='BANGSAL-D-T', name='Bangsal Dewasa Test', level=3, parent=self.irin)
        self.ruang_pria = UnitKerja.objects.create(code='R-PRIA-T', name='Ruang Pria Test', level=4, parent=self.bangsal)

        self.user_bangsal = User.objects.create_user('ka.bangsal.test', password='x')
        UserProfile.objects.update_or_create(user=self.user_bangsal, defaults={'role': 'KEPALA_UNIT', 'unit_kerja': self.bangsal})

        self.user_admin = User.objects.create_user('admin.test', password='x')
        UserProfile.objects.update_or_create(user=self.user_admin, defaults={'role': 'ADMIN_RS'})

    def test_unit_scoped_user_only_sees_subtree_no_ancestors(self):
        """User at Bangsal must see Bangsal and Ruang Pria, but NOT IRIN or Pelaksana Teknis."""
        units = _unit_pilihan(self.user_bangsal)
        unit_pks = set(units.values_list('pk', flat=True))

        self.assertIn(self.bangsal.pk, unit_pks)
        self.assertIn(self.ruang_pria.pk, unit_pks)
        self.assertNotIn(self.irin.pk, unit_pks, "Ancestor IRIN must not appear in unit_pilihan")
        self.assertNotIn(self.pelaksana.pk, unit_pks, "Ancestor Direktorat must not appear in unit_pilihan")

    def test_admin_sees_all_units(self):
        """Admin RS must see all active units including top level."""
        units = _unit_pilihan(self.user_admin)
        unit_pks = set(units.values_list('pk', flat=True))
        self.assertIn(self.pelaksana.pk, unit_pks)
        self.assertIn(self.irin.pk, unit_pks)
        self.assertIn(self.bangsal.pk, unit_pks)

    def test_logbook_buat_context_prefills_default_unit(self):
        """GET /logbook/buat/ passes default_unit_id equal to user's assigned unit."""
        self.client.force_login(self.user_bangsal)
        r = self.client.get(reverse('akreditasi:logbook_buat'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['default_unit_id'], self.bangsal.pk)
