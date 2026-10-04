"""
Unit-scoped RBAC test suite for Patient Management module access.
Tests that get_allowed_patient_modules() returns correct module set
based on user's role, unit_kerja, and profesi.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja

from accounts.models import UserProfile

User = get_user_model()


class UnitPatientModuleRBACTest(TestCase):
    def setUp(self):
        self.unit_lab, _ = UnitKerja.objects.get_or_create(code='LAB-BDRS', defaults={'name': 'Instalasi Laboratorium', 'level': 3})
        self.unit_farm, _ = UnitKerja.objects.get_or_create(code='FARM', defaults={'name': 'Instalasi Farmasi', 'level': 3})
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        self.unit_irj, _ = UnitKerja.objects.get_or_create(code='IRJ', defaults={'name': 'Instalasi Rawat Jalan', 'level': 2})
        self.unit_irin, _ = UnitKerja.objects.get_or_create(code='IRIN', defaults={'name': 'Instalasi Rawat Inap', 'level': 2})
        self.unit_admisi, _ = UnitKerja.objects.get_or_create(code='ADMISI', defaults={'name': 'Pendaftaran & Admisi', 'level': 4})
        self.unit_poli, _ = UnitKerja.objects.get_or_create(code='POLI-PD', defaults={'name': 'Poliklinik Penyakit Dalam', 'level': 3, 'parent': self.unit_irj})
        self.unit_depo, _ = UnitKerja.objects.get_or_create(code='DEPO-RAJAL', defaults={'name': 'Depo Farmasi Rajal', 'level': 4})

    def _make_user(self, username, role, profesi='', unit=None):
        user = User.objects.create_user(username, f'{username}@rs.id', 'pass123')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.profesi = profesi
        profile.unit_kerja = unit
        profile.save()
        return user

    def test_lab_user_sees_lab_only(self):
        user = self._make_user('analis1', 'STAF_NAKES', 'ANALIS_LAB', self.unit_lab)
        allowed = user.profile.get_allowed_patient_modules()
        self.assertIn('laboratorium', allowed)
        self.assertIn('master_pasien', allowed)
        self.assertIn('riwayat', allowed)
        self.assertNotIn('igd', allowed)
        self.assertNotIn('rajal', allowed)
        self.assertNotIn('pendaftaran', allowed)
        self.assertNotIn('ranap', allowed)
        self.assertNotIn('farmasi', allowed)

    def test_farmasi_user_sees_farmasi_only(self):
        user = self._make_user('apoteker1', 'STAF_NAKES', 'APOTEKER', self.unit_farm)
        allowed = user.profile.get_allowed_patient_modules()
        self.assertIn('farmasi', allowed)
        self.assertIn('master_pasien', allowed)
        self.assertNotIn('igd', allowed)
        self.assertNotIn('rajal', allowed)
        self.assertNotIn('laboratorium', allowed)

    def test_depo_rajal_user_sees_farmasi(self):
        user = self._make_user('depo1', 'STAF_NAKES', '', self.unit_depo)
        allowed = user.profile.get_allowed_patient_modules()
        self.assertIn('farmasi', allowed)
        self.assertNotIn('igd', allowed)

    def test_igd_user_sees_igd_pendaftaran_ranap(self):
        user = self._make_user('perawat_igd', 'STAF_NAKES', 'PERAWAT', self.unit_igd)
        allowed = user.profile.get_allowed_patient_modules()
        self.assertIn('igd', allowed)
        self.assertIn('pendaftaran', allowed)
        self.assertIn('ranap', allowed)
        self.assertNotIn('rajal', allowed)
        self.assertNotIn('farmasi', allowed)
        self.assertNotIn('laboratorium', allowed)

    def test_poli_user_sees_rajal_ranap(self):
        user = self._make_user('dokter_poli', 'STAF_NAKES', 'DOKTER_SPESIALIS', self.unit_poli)
        allowed = user.profile.get_allowed_patient_modules()
        self.assertIn('rajal', allowed)
        self.assertIn('ranap', allowed)
        self.assertNotIn('igd', allowed)
        self.assertNotIn('farmasi', allowed)

    def test_admisi_user_sees_pendaftaran_ranap(self):
        user = self._make_user('staf_admisi', 'STAF_NAKES', '', self.unit_admisi)
        allowed = user.profile.get_allowed_patient_modules()
        self.assertIn('pendaftaran', allowed)
        self.assertIn('ranap', allowed)
        self.assertNotIn('igd', allowed)
        self.assertNotIn('rajal', allowed)

    def test_superuser_sees_all(self):
        admin = User.objects.create_superuser('superadmin', 'admin@rs.id', 'pass123')
        profile, _ = UserProfile.objects.get_or_create(user=admin)
        allowed = profile.get_allowed_patient_modules()
        for mod in ['pendaftaran', 'igd', 'rajal', 'ranap', 'farmasi', 'laboratorium', 'master_pasien', 'riwayat']:
            self.assertIn(mod, allowed)

    def test_admin_rs_sees_all(self):
        user = self._make_user('admin_rs', 'ADMIN_RS')
        allowed = user.profile.get_allowed_patient_modules()
        for mod in ['pendaftaran', 'igd', 'rajal', 'ranap', 'farmasi', 'laboratorium', 'master_pasien', 'riwayat']:
            self.assertIn(mod, allowed)

    def test_user_without_unit_sees_minimal(self):
        user = self._make_user('orphan', 'ASESOR')
        allowed = user.profile.get_allowed_patient_modules()
        self.assertEqual(allowed, {'master_pasien', 'riwayat'})

    def test_ranap_user_sees_ranap_only(self):
        user = self._make_user('perawat_ranap', 'STAF_NAKES', 'PERAWAT', self.unit_irin)
        allowed = user.profile.get_allowed_patient_modules()
        self.assertIn('ranap', allowed)
        self.assertNotIn('igd', allowed)
        self.assertNotIn('rajal', allowed)
