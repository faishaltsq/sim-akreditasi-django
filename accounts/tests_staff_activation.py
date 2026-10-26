"""Staff activation HTTP surface (Task 9)."""

import hashlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai, PenempatanPegawai, UndanganAkunPegawai


class StaffActivationViewTests(TestCase):
    def setUp(self):
        # Demo seed migrations create accounts at DB setup; assertions below are
        # about the delta this test causes, never the absolute user count.
        self.users_before = get_user_model().objects.count()
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='ACT-HC')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Aktivasi', kategori='NON_PPA', status='AKTIF',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.root,
            tanggal_mulai=timezone.localdate(), alokasi_fte=1.00,
        )

    def _invitation(self, raw='raw-token', **kwargs):
        defaults = {
            'employee': self.employee,
            'email': 'aktivasi@example.com',
            'token_digest': hashlib.sha256(raw.encode()).hexdigest(),
            'expiry': timezone.now() + timedelta(hours=1),
            'state': 'SENT',
            'intended_role': 'STAF_NAKES',
        }
        defaults.update(kwargs)
        return UndanganAkunPegawai.objects.create(**defaults)

    def test_get_does_not_mutate(self):
        invitation = self._invitation()
        response = self.client.get(
            reverse('accounts:staff_activate', kwargs={'token': 'raw-token'})
        )
        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.state, 'SENT')
        self.assertEqual(get_user_model().objects.count(), self.users_before)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')

    def test_post_creates_exactly_one_account_and_links_it(self):
        invitation = self._invitation()
        response = self.client.post(
            reverse('accounts:staff_activate', kwargs={'token': 'raw-token'}),
            {'new_password1': 'StrongPass123!', 'new_password2': 'StrongPass123!'},
        )
        self.assertEqual(response.status_code, 302)
        invitation.refresh_from_db()
        self.assertEqual(invitation.state, 'ACCEPTED')
        self.employee.refresh_from_db()
        self.assertIsNotNone(self.employee.akun_id)
        self.assertEqual(get_user_model().objects.count(), self.users_before + 1)

    def test_replay_does_not_create_a_second_account(self):
        self._invitation()
        payload = {'new_password1': 'StrongPass123!', 'new_password2': 'StrongPass123!'}
        self.client.post(
            reverse('accounts:staff_activate', kwargs={'token': 'raw-token'}), payload
        )
        response = self.client.post(
            reverse('accounts:staff_activate', kwargs={'token': 'raw-token'}), payload
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.count(), self.users_before + 1)

    def test_unknown_token_is_a_generic_failure(self):
        response = self.client.get(
            reverse('accounts:staff_activate', kwargs={'token': 'not-a-token'})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tidak valid atau sudah digunakan')

    def test_mismatched_passwords_are_refused(self):
        self._invitation()
        response = self.client.post(
            reverse('accounts:staff_activate', kwargs={'token': 'raw-token'}),
            {'new_password1': 'StrongPass123!', 'new_password2': 'Different123!'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.count(), self.users_before)

    def test_intentionally_inactive_account_does_not_get_login_promise(self):
        self._invitation(intended_is_active=False)
        response = self.client.post(
            reverse('accounts:staff_activate', kwargs={'token': 'raw-token'}),
            {'new_password1': 'StrongPass123!', 'new_password2': 'StrongPass123!'},
            follow=True,
        )
        user = get_user_model().objects.get(email='aktivasi@example.com')
        self.assertFalse(user.is_active)
        self.assertContains(response, 'menunggu aktivasi administrator')
        self.assertNotContains(response, 'Silakan masuk')

    def test_employee_with_linked_account_is_not_relinked(self):
        existing = get_user_model().objects.create_user(username='existing-account')
        self.employee.akun = existing
        self.employee.save(update_fields=['akun', 'updated_at'])
        self._invitation()
        response = self.client.post(
            reverse('accounts:staff_activate', kwargs={'token': 'raw-token'}),
            {'new_password1': 'StrongPass123!', 'new_password2': 'StrongPass123!'},
        )
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.akun_id, existing.pk)
        self.assertEqual(get_user_model().objects.count(), self.users_before + 1)

    def test_case_insensitive_email_collision_is_refused(self):
        get_user_model().objects.create_user(
            username='different-username', email='AKTIVASI@example.com'
        )
        self._invitation()
        response = self.client.post(
            reverse('accounts:staff_activate', kwargs={'token': 'raw-token'}),
            {'new_password1': 'StrongPass123!', 'new_password2': 'StrongPass123!'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.count(), self.users_before + 1)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.akun_id)

    @override_settings(PUBLIC_BASE_URL='https://arima.example.org')
    def test_invitation_email_carries_a_real_activation_url(self):
        from django.core import mail
        from sdm.services.undangan import invite_staff_account

        manager = get_user_model().objects.create_user(username='act-manager')
        UserProfile.objects.create(user=manager, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.save(update_fields=[
            'can_view_hc', 'can_manage_hc_employees', 'updated_at',
        ])
        HcGrant.objects.create(user=manager, capability='can_view_hc', unit_kerja=self.root)
        HcGrant.objects.create(
            user=manager, capability='can_manage_hc_employees', unit_kerja=self.root
        )
        with self.captureOnCommitCallbacks(execute=True):
            invite_staff_account(
                actor=manager, employee=self.employee,
                email='aktivasi@example.com', role='STAF_NAKES',
                idempotency_key='act-1',
            )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('https://arima.example.org', mail.outbox[0].body)
        self.assertNotIn('example.com/aktivasi', mail.outbox[0].body)
        self.assertNotIn('password', mail.outbox[0].body.lower())
