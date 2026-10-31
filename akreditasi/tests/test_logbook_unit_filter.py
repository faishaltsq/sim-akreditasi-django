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


class LogbookFormTemplateRenderTest(TestCase):
    def setUp(self):
        self.bangsal = UnitKerja.objects.create(code='BANGSAL-D-TMPL', name='Bangsal Dewasa Tmpl', level=3)
        self.r1 = Ruangan.objects.create(kode='R-K1-TMPL', nama='Bangsal Mawar Tmpl', kelas='1', jenis='RANAP', unit_kerja=self.bangsal)
        self.user = User.objects.create_user('ka.bangsal.tmpl', password='x')
        UserProfile.objects.update_or_create(user=self.user, defaults={'role': 'KEPALA_UNIT', 'unit_kerja': self.bangsal})

    def test_rendered_form_has_preselected_unit_and_data_unit_attributes(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('akreditasi:logbook_buat'))
        self.assertEqual(r.status_code, 200)
        content = r.content.decode('utf-8')
        # Check pre-selected unit
        self.assertIn(f'value="{self.bangsal.pk}" selected', content)
        # Check data-unit on room option
        self.assertIn(f'data-unit="{self.bangsal.pk}"', content)
        # Check presence of client-side sync script
        self.assertIn('filterRuanganByUnit', content)


class LogbookPostValidationTest(TestCase):
    def setUp(self):
        self.bangsal = UnitKerja.objects.create(code='BANGSAL-D-VAL', name='Bangsal Dewasa Val', level=3)
        self.igd = UnitKerja.objects.create(code='IGD-VAL', name='IGD Val', level=2)

        self.r_bangsal = Ruangan.objects.create(kode='R-K1-VAL', nama='Bangsal Mawar Val', kelas='1', jenis='RANAP', unit_kerja=self.bangsal)
        self.r_igd = Ruangan.objects.create(kode='IGD-01-VAL', nama='Triase IGD Val', kelas='IGD', jenis='IGD', unit_kerja=self.igd)

        self.user = User.objects.create_user('ka.bangsal.val', password='x')
        UserProfile.objects.update_or_create(user=self.user, defaults={'role': 'KEPALA_UNIT', 'unit_kerja': self.bangsal})

    def test_forged_room_from_different_unit_is_sanitized_or_rejected(self):
        """If user submits Bangsal Dewasa unit but injects IGD ruangan, room must not be linked."""
        self.client.force_login(self.user)
        r = self.client.post(reverse('akreditasi:logbook_buat'), {
            'jenis': 'RANAP',
            'shift': 'PAGI',
            'unit': self.bangsal.pk,
            'ruangan': self.r_igd.pk,  # Tampered room
            'tanggal': '2026-10-31',
        })
        self.assertEqual(r.status_code, 302)
        from akreditasi.logbook_models import LogbookHarian
        lb = LogbookHarian.objects.get(unit=self.bangsal, shift='PAGI', tanggal='2026-10-31')
        # Room must be sanitized to None because r_igd does not belong to self.bangsal
        self.assertIsNone(lb.ruangan, "Mismatched ruangan must be sanitized to None")
