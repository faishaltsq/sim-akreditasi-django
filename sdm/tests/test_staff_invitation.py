"""RED tests for Task B6: staff account invitation and activation."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai, PenempatanPegawai, UndanganAkunPegawai
from sdm.services.undangan import accept_staff_invitation, invite_staff_account


class StaffInvitationTests(TestCase):
    def setUp(self):
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='DIR-HC')
        self.manager = self._user('impor-manager')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Baru',
            kategori='NON_PPA',
            profesi='Administrasi',
            status='AKTIF',
            data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.root,
            tanggal_mulai=timezone.localdate(),
            alokasi_fte=1.00,
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.save(update_fields=['can_view_hc', 'can_manage_hc_employees', 'updated_at'])
        HcGrant.objects.create(user=user, capability='can_view_hc', unit_kerja=self.root)
        HcGrant.objects.create(
            user=user, capability='can_manage_hc_employees', unit_kerja=self.root
        )
        return user

    def test_invite_creates_sent_invitation_and_email(self):
        with override_settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
        ):
            with self.captureOnCommitCallbacks(execute=True):
                invitation = invite_staff_account(
                    actor=self.manager,
                    employee=self.employee,
                    email='baru@example.com',
                    role='STAF_NAKES',
                    idempotency_key='inv-001',
                )
        self.assertEqual(invitation.state, 'SENT')
        self.assertEqual(invitation.email, 'baru@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(get_user_model().objects.filter(email='baru@example.com').exists())

    def test_invite_forbidden_role_is_denied(self):
        with self.assertRaises(PermissionDenied):
            invite_staff_account(
                actor=self.manager,
                employee=self.employee,
                email='admin@example.com',
                role='SUPER_ADMIN',
                idempotency_key='inv-002',
            )

    def test_accept_activates_account_and_links_employee(self):
        with override_settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
        ):
            with self.captureOnCommitCallbacks(execute=True):
                invitation = invite_staff_account(
                    actor=self.manager,
                    employee=self.employee,
                    email='baru2@example.com',
                    role='STAF_NAKES',
                    idempotency_key='inv-003',
                )
        user = accept_staff_invitation(
            token=invitation.raw_token, password='StrongPass123!'
        )
        self.assertTrue(user.check_password('StrongPass123!'))
        self.assertTrue(user.is_active)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.akun_id, user.pk)
        invitation.refresh_from_db()
        self.assertEqual(invitation.state, 'ACCEPTED')

    def test_accept_with_weak_password_is_rejected(self):
        with override_settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
        ):
            with self.captureOnCommitCallbacks(execute=True):
                invitation = invite_staff_account(
                    actor=self.manager,
                    employee=self.employee,
                    email='baru3@example.com',
                    role='STAF_NAKES',
                    idempotency_key='inv-004',
                )
        with self.assertRaises(Exception):
            accept_staff_invitation(token=invitation.raw_token, password='weak')

    def test_accept_expired_token_is_rejected(self):
        import hashlib
        raw = 'expired-token-raw'
        invitation = UndanganAkunPegawai.objects.create(
            employee=self.employee,
            email='expired@example.com',
            intended_role='STAF_NAKES',
            token_digest=hashlib.sha256(raw.encode()).hexdigest(),
            expiry=timezone.now() - timezone.timedelta(minutes=1),
            state='SENT',
        )
        with self.assertRaises(ValidationError):
            accept_staff_invitation(token=raw, password='StrongPass123!')
        invitation.refresh_from_db()
        self.assertEqual(invitation.state, 'EXPIRED')
