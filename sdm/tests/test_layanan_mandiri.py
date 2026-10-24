"""RED tests for Task B7: self-service reviewable corrections."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    HcGrant,
    LayananMandiri,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
)
from sdm.services.layanan_mandiri import decide_staff_request, submit_staff_request


class StaffSelfServiceTests(TestCase):
    def setUp(self):
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='DIR-HC')
        self.other = UnitKerja.objects.create(name='Unit Lain', code='DIR-OTHER')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Sendiri',
            kategori='NON_PPA',
            profesi='Administrasi',
            status='AKTIF',
            data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.root,
            tanggal_mulai='2026-10-23',
            alokasi_fte=1.00,
        )
        self.user = self._user('staff-own')
        self.employee.akun = self.user
        self.employee.save(update_fields=['akun', 'updated_at'])
        self.reviewer = self._user('hr-reviewer')

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

    def test_employee_submits_own_profile_correction(self):
        request = submit_staff_request(
            actor=self.user,
            kind='PROFILE_CORRECTION',
            payload={'telepon': '08123456789'},
            idempotency_key='req-001',
        )
        self.assertEqual(request.state, 'SUBMITTED')
        self.assertEqual(request.employee, self.employee)
        self.assertTrue(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='staff_request_submitted', target_id=str(self.employee.pk)
            ).exists()
        )

    def test_reviewer_approves_own_scoped_request(self):
        req = submit_staff_request(
            actor=self.user,
            kind='TRAINING_REQUEST',
            payload={'program': 'BHD'},
            idempotency_key='req-002',
        )
        decided = decide_staff_request(
            request=req, actor=self.reviewer, decision='approve', reason='Disetujui.'
        )
        self.assertEqual(decided.state, 'APPROVED')
        self.assertEqual(decided.reviewer, self.reviewer)

    def test_reviewer_rejects_with_reason(self):
        req = submit_staff_request(
            actor=self.user,
            kind='LEAVE_REQUEST',
            payload={'tanggal': '2026-11-01'},
            idempotency_key='req-003',
        )
        decided = decide_staff_request(
            request=req, actor=self.reviewer, decision='reject', reason='Kuota penuh.'
        )
        self.assertEqual(decided.state, 'REJECTED')
        self.assertEqual(decided.decision_reason, 'Kuota penuh.')

    def test_idempotent_resubmit_returns_same_request(self):
        first = submit_staff_request(
            actor=self.user,
            kind='DOCUMENT_REQUEST',
            payload={'jenis': 'SKP'},
            idempotency_key='req-idem',
        )
        second = submit_staff_request(
            actor=self.user,
            kind='DOCUMENT_REQUEST',
            payload={'jenis': 'SKP'},
            idempotency_key='req-idem',
        )
        self.assertEqual(first.pk, second.pk)
