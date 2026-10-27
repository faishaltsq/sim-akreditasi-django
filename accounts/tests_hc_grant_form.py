from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai
from sdm.services.akses_hc import sinkronkan_grant

KREDENSIAL = ['can_review_hc_credentials', 'hc_review_subkomite', 'hc_approve_credentials']


class GrantFormTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='hc-admin-form', password='RahasiaKuat-2026'
        )
        self.unit = UnitKerja.objects.create(name='Unit Form HC', code='HC-FORM')
        self.client.force_login(self.admin)

    def _payload(self, **overrides):
        data = {
            'username': 'hc.penerima',
            'password1': 'RahasiaKuat-2026',
            'password2': 'RahasiaKuat-2026',
            'first_name': 'Penerima',
            'last_name': 'Hak',
            'email': 'hc.penerima@arima.local',
            'role': 'ADMIN_RS',
            'full_name': 'Penerima Hak',
            'jabatan': 'Tester',
            'profesi': '',
            'telepon': '',
            'unit_kerja': '',
            'is_active_member': 'on',
            'hc_akses_diisi': '1',
            'hc_lingkup': 'RS',
            'hc_unit': '',
            'hc_include_descendants': 'on',
            'hc_capability': list(KREDENSIAL),
        }
        data.update(overrides)
        return data

    def _create(self, **overrides):
        return self.client.post(reverse('accounts:user_create'), self._payload(**overrides))

    def test_form_renders_capability_grid(self):
        response = self.client.get(reverse('accounts:user_create'))
        body = response.content.decode()
        self.assertIn('name="hc_capability"', body)
        self.assertIn('name="hc_lingkup"', body)

    def test_create_makes_grants_and_enables_role(self):
        response = self._create()
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username='hc.penerima')

        grant = HcGrant.objects.get(user=user, is_active=True, capability='hc_review_subkomite')
        self.assertIsNone(grant.unit_kerja_id)
        self.assertTrue(grant.include_descendants)
        self.assertEqual(
            set(HcGrant.objects.filter(user=user, is_active=True).values_list('capability', flat=True)),
            set(KREDENSIAL),
        )

        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        for capability in KREDENSIAL:
            self.assertTrue(getattr(config, capability), capability)

    def test_create_keeps_grants_in_other_scope(self):
        user = get_user_model().objects.create_user(username='hc.lama')
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        sinkronkan_grant(user, capabilities={'can_view_hc'}, unit=self.unit)

        self._create(username='hc.lama2', email='hc.lama2@arima.local')
        self.assertTrue(
            HcGrant.objects.filter(user=user, unit_kerja=self.unit, is_active=True).exists()
        )

    def test_unit_scope_grants_target_unit(self):
        self._create(hc_lingkup='UNIT', hc_unit=str(self.unit.pk))
        user = get_user_model().objects.get(username='hc.penerima')
        self.assertEqual(
            set(HcGrant.objects.filter(user=user, is_active=True).values_list('unit_kerja_id', flat=True)),
            {self.unit.pk},
        )

    def test_invalid_unit_reports_error_and_touches_nothing(self):
        response = self._create(hc_lingkup='UNIT', hc_unit='')
        user = get_user_model().objects.get(username='hc.penerima')

        self.assertEqual(HcGrant.objects.filter(user=user).count(), 0)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('tidak valid' in m for m in messages), messages)

    def test_edit_without_capabilities_deactivates_scope(self):
        self._create()
        user = get_user_model().objects.get(username='hc.penerima')
        total = HcGrant.objects.filter(user=user).count()

        data = self._payload()
        data.pop('hc_capability')
        response = self.client.post(reverse('accounts:user_edit', args=[user.pk]), data)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(HcGrant.objects.filter(user=user, is_active=True).count(), 0)
        self.assertEqual(HcGrant.objects.filter(user=user).count(), total)

    def test_edit_restores_selected_capabilities(self):
        self._create()
        user = get_user_model().objects.get(username='hc.penerima')
        data = self._payload(hc_capability=['hc_review_subkomite'])
        self.client.post(reverse('accounts:user_edit', args=[user.pk]), data)

        self.assertEqual(
            set(HcGrant.objects.filter(user=user, is_active=True).values_list('capability', flat=True)),
            {'hc_review_subkomite'},
        )


class GrantCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='cmd.penerima')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=None)
        Pegawai.objects.create(nama_lengkap='Pegawai Cmd', kategori='PPA', profesi='Perawat')

    def test_command_is_idempotent(self):
        call_command('grant_hc_akses', 'cmd.penerima')
        after_first = HcGrant.objects.filter(user=self.user, is_active=True).count()
        self.assertGreater(after_first, 0)

        call_command('grant_hc_akses', 'cmd.penerima')
        self.assertEqual(
            HcGrant.objects.filter(user=self.user, is_active=True).count(), after_first
        )

    def test_command_all_creates_every_capability(self):
        call_command('grant_hc_akses', 'cmd.penerima', '--all')
        self.assertEqual(
            HcGrant.objects.filter(user=self.user, is_active=True).count(),
            len(HcGrant.CAPABILITY_CHOICES),
        )
