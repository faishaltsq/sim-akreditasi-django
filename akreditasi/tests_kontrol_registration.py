"""Kontrak pintu masuk pendaftaran pasien di Integrated Control.

Builder murni diuji tanpa DB; integrasi memakai fixture sintetis di database
test terisolasi. Tidak ada perluasan RBAC: yang berhak tetap yang sudah
memegang modul ``pendaftaran``.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from akreditasi.models import UnitKerja


class RegistrationActionTest(SimpleTestCase):
    def test_entitled_emr_action_has_exact_hospital_wide_destination(self):
        from akreditasi.kontrol_navigation import registration_action

        action = registration_action(
            active_portal='emr', allowed_patient_modules={'pendaftaran'})
        self.assertEqual(action['key'], 'pendaftaran')
        self.assertEqual(action['label'], 'Pendaftaran pasien')
        self.assertEqual(action['href'], reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(action['scope'], 'Seluruh rumah sakit')
        self.assertIn('pasien baru atau lama', action['description'])

    def test_other_portals_never_advertise_registration(self):
        from akreditasi.kontrol_navigation import registration_action

        for portal in ('hub', 'risiko', 'dokumen', 'layanan'):
            with self.subTest(portal=portal):
                self.assertIsNone(registration_action(
                    active_portal=portal,
                    allowed_patient_modules={'pendaftaran'}))

    def test_missing_or_insufficient_entitlement_returns_none(self):
        from akreditasi.kontrol_navigation import registration_action

        for allowed in (None, set(), {'rajal'}, {'ranap'}, {'laboratorium'}):
            with self.subTest(allowed=allowed):
                self.assertIsNone(registration_action(
                    active_portal='emr', allowed_patient_modules=allowed))


class RegistrationEntryTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def login(self, *, code, role='STAF', superuser=False):
        unit, _ = UnitKerja.objects.get_or_create(
            code=code,
            defaults={'name': 'Fixture ' + code, 'level': 3, 'is_active': True},
        )
        User = get_user_model()
        user = User.objects.create_user(
            username='entry-' + role.lower() + '-' + code.lower(),
            is_superuser=superuser, is_staff=superuser,
        )
        UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
        self.client.force_login(user)
        cache.clear()
        return unit

    def emr(self, unit):
        return self.client.get(reverse('akreditasi:kontrol_emr'), {'unit': unit.pk})

    def test_entitled_roles_and_units_see_registration(self):
        cases = (
            ('IGD', 'STAF', False),
            ('ADMISI', 'STAF', False),
            ('PENDAFTARAN', 'STAF', False),
            ('REKAM-MEDIS', 'STAF', False),
            ('KOMITE-MUTU', 'SUPER_ADMIN', False),
            ('KOMITE-MUTU', 'ADMIN_RS', False),
            ('KOMITE-MUTU', 'DIREKTUR', False),
            ('KOMITE-MUTU', 'STAF', True),
        )
        for code, role, superuser in cases:
            with self.subTest(code=code, role=role, superuser=superuser):
                unit = self.login(code=code, role=role, superuser=superuser)
                response = self.emr(unit)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-service-action="pendaftaran"', count=1)
                self.assertContains(response, 'Pendaftaran pasien')
                action = response.context['registration_action']
                self.assertEqual(action['href'], reverse('pasien:pendaftaran_dashboard'))
                target = self.client.get(action['href'])
                self.assertEqual(target.status_code, 200)

    def test_unmapped_admission_still_has_registration(self):
        unit = self.login(code='ADMISI')
        response = self.emr(unit)
        self.assertFalse(response.context['snapshot']['layanan']['mapped'])
        self.assertContains(response, 'data-service-action="pendaftaran"')
        self.assertContains(response, 'belum memiliki pemetaan layanan klinis untuk daftar kunjungan harian')
        self.assertNotContains(response, 'tidak memiliki layanan pendaftaran pasien')

    def test_non_entitled_users_get_neither_menu_nor_destination_access(self):
        for code in ('POLI-PD', 'LAB-BDRS', 'FARM', 'BANGSAL-DEWASA', 'DIREKSI'):
            with self.subTest(code=code):
                unit = self.login(code=code)
                response = self.emr(unit)
                self.assertNotContains(response, 'data-service-action="pendaftaran"')
                self.assertIsNone(response.context['registration_action'])
                self.assertEqual(self.client.get(
                    reverse('pasien:pendaftaran_dashboard')).status_code, 403)

    def test_shared_partial_does_not_add_registration_to_other_portals(self):
        unit = self.login(code='IGD')
        for name in ('kontrol_risiko', 'kontrol_dokumen', 'kontrol_layanan', 'kontrol_hub'):
            with self.subTest(name=name):
                response = self.client.get(reverse('akreditasi:' + name), {'unit': unit.pk})
                self.assertNotContains(response, 'data-service-action="pendaftaran"')
                self.assertIsNone(response.context['registration_action'])

    def test_registration_belongs_to_services_and_services_precede_kpis(self):
        unit = self.login(code='IGD')
        body = self.emr(unit).content.decode()
        start = body.index('<section class="kontrol-layanan"')
        end = body.index('</section>', start)
        marker = body.index('data-service-action="pendaftaran"')
        self.assertLess(start, marker)
        self.assertLess(marker, end)
        self.assertLess(end, body.index('class="kontrol-kpis"'))
        self.assertLess(end, body.index('class="kontrol-ai"'))

    def test_registration_scope_does_not_follow_requested_unit(self):
        unit = self.login(code='IGD')
        other = UnitKerja.objects.create(code='ENTRY-OTHER', name='Other', level=3)
        response = self.client.get(reverse('akreditasi:kontrol_emr'), {'unit': other.pk})
        self.assertEqual(response.context['unit'].pk, unit.pk)
        self.assertEqual(response.context['registration_action']['href'],
                         reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(response, 'Cakupan seluruh rumah sakit sesuai hak akses.')

    def test_anonymous_emr_still_redirects_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(
            reverse('akreditasi:kontrol_emr')).status_code, 302)

    def test_dashboard_explanations_are_visible_and_specific(self):
        unit = self.login(code='IGD')
        checks = {
            'kontrol_hub': ('Pilih unit aktif', 'Elemen Penilaian'),
            'kontrol_emr': ('Catatan Perkembangan Pasien Terintegrasi',
                            'Profesional Pemberi Asuhan', 'Seluruh RS'),
            'kontrol_risiko': ('Rencana Tindak Lanjut',),
            'kontrol_dokumen': ('Elemen Penilaian', 'Catatan mutu unit dengan skor di atas 0'),
        }
        for name, phrases in checks.items():
            with self.subTest(name=name):
                response = self.client.get(reverse('akreditasi:' + name), {'unit': unit.pk})
                for phrase in phrases:
                    self.assertContains(response, phrase)
