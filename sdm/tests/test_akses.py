from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from akreditasi.system_models import SystemConfig
from sdm.akses import require_hc_capability, visible_employees
from sdm.models import HcGrant, Pegawai, PenempatanPegawai, PeristiwaSDM


class HumanCapitalAccessTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.root = UnitKerja.objects.create(name='Direktorat Layanan', code='HC-ROOT')
        self.child = UnitKerja.objects.create(
            name='Unit Klinis', code='HC-CHILD', parent=self.root
        )
        self.other = UnitKerja.objects.create(name='Unit Lain', code='HC-OTHER')
        self.staff = Pegawai.objects.create(nama_lengkap='Staf Unit', kategori='PPA')
        self.child_staff = Pegawai.objects.create(
            nama_lengkap='Staf Anak', kategori='NON_PPA'
        )
        self.other_staff = Pegawai.objects.create(
            nama_lengkap='Staf Lain', kategori='NON_PPA'
        )
        self._place(self.staff, self.root)
        self._place(self.child_staff, self.child)
        self._place(self.other_staff, self.other)

    def _place(self, employee, unit, *, end_date=None):
        return PenempatanPegawai.objects.create(
            pegawai=employee,
            unit_kerja=unit,
            tanggal_mulai=self.today - timedelta(days=10),
            tanggal_selesai=end_date,
            alokasi_fte=Decimal('1.00'),
        )

    def _user(self, username, *, superuser=False, role=None, unit=None):
        user = get_user_model().objects.create_user(
            username=username, is_superuser=superuser
        )
        if role:
            UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
        return user

    def _grant(self, user, capability, *, unit=None, descendants=False, **kwargs):
        return HcGrant.objects.create(
            user=user,
            capability=capability,
            unit_kerja=unit,
            include_descendants=descendants,
            **kwargs,
        )

    def test_null_unit_head_gets_no_hospital_scope(self):
        head = self._user('head-null', role='KEPALA_UNIT')

        self.assertFalse(visible_employees(head).exists())

    def test_unit_grant_is_limited_to_its_unit_by_default(self):
        user = self._user('unit-hr')
        self._grant(user, 'can_view_hc', unit=self.root)

        self.assertEqual(
            set(visible_employees(user).values_list('pk', flat=True)),
            {self.staff.pk},
        )

    def test_every_role_uses_expected_hc_default_with_scoped_grant(self):
        for index, (role, _label) in enumerate(UserProfile.ROLE_CHOICES):
            with self.subTest(role=role):
                user = self._user(f'role-hc-{index}', role=role, unit=self.root)
                self._grant(user, 'can_view_hc', unit=self.root)

                visible = set(visible_employees(user).values_list('pk', flat=True))
                if role == 'SUPER_ADMIN':
                    self.assertEqual(visible, {self.staff.pk})
                else:
                    self.assertFalse(visible)

    def test_role_permission_is_an_additional_gate_for_scoped_grants(self):
        user = self._user('profile-unit-hr', role='KEPALA_UNIT', unit=self.root)
        self._grant(user, 'can_view_hc', unit=self.root)

        self.assertFalse(visible_employees(user).exists())
        config = RolePermissionConfig.get_config_for_role('KEPALA_UNIT')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])

        self.assertEqual(
            set(visible_employees(user).values_list('pk', flat=True)),
            {self.staff.pk},
        )

    def test_user_override_can_revoke_a_role_permission(self):
        user = self._user('custom-unit-hr', role='KEPALA_UNIT', unit=self.root)
        self._grant(user, 'can_view_hc', unit=self.root)
        config = RolePermissionConfig.get_config_for_role('KEPALA_UNIT')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        profile = UserProfile.objects.get(user=user)
        profile.custom_permissions = {'can_view_hc': False}
        profile.save(update_fields=['custom_permissions', 'updated_at'])

        self.assertFalse(visible_employees(user).exists())

    def test_user_override_can_enable_only_with_matching_explicit_grant(self):
        user = self._user('custom-unit-hr-enabled', role='KEPALA_UNIT', unit=self.root)
        self._grant(user, 'can_view_hc', unit=self.root)
        profile = UserProfile.objects.get(user=user)
        profile.custom_permissions = {'can_view_hc': True}
        profile.save(update_fields=['custom_permissions', 'updated_at'])

        self.assertEqual(
            set(visible_employees(user).values_list('pk', flat=True)),
            {self.staff.pk},
        )

    def test_descendant_scope_is_included_only_when_explicit(self):
        user = self._user('unit-hr-descendants')
        self._grant(user, 'can_view_hc', unit=self.root, descendants=True)

        self.assertEqual(
            set(visible_employees(user).values_list('pk', flat=True)),
            {self.staff.pk, self.child_staff.pk},
        )

    def test_hospital_scope_requires_an_explicit_null_unit_grant(self):
        user = self._user('hospital-hr')
        self._grant(user, 'can_view_hc', unit=None)

        self.assertEqual(
            set(visible_employees(user).values_list('pk', flat=True)),
            {self.staff.pk, self.child_staff.pk, self.other_staff.pk},
        )

    def test_expired_or_revoked_grants_do_not_authorize_access(self):
        user = self._user('former-hr')
        self._grant(
            user,
            'can_view_hc',
            unit=None,
            valid_from=self.today - timedelta(days=10),
            valid_until=self.today - timedelta(days=1),
        )
        self._grant(user, 'can_view_hc', unit=None, is_active=False)

        self.assertFalse(visible_employees(user).exists())

    def test_invalid_or_inactive_unit_filter_fails_closed(self):
        user = self._user('scoped-hr')
        self._grant(user, 'can_view_hc', unit=self.root, descendants=True)
        self.other.is_active = False
        self.other.save(update_fields=['is_active'])

        self.assertFalse(visible_employees(user, unit=self.other).exists())
        self.assertFalse(visible_employees(user, unit=999999).exists())

    def test_direct_employee_authorization_rejects_foreign_unit(self):
        user = self._user('unit-operator')
        self._grant(user, 'can_manage_hc_employees', unit=self.root)

        with self.assertRaises(PermissionDenied):
            require_hc_capability(
                user, 'can_manage_hc_employees', employee=self.child_staff
            )

    def test_direct_employee_authorization_allows_matching_unit(self):
        user = self._user('unit-operator-valid')
        self._grant(user, 'can_manage_hc_employees', unit=self.root)

        require_hc_capability(
            user, 'can_manage_hc_employees', unit=self.root, employee=self.staff
        )

    def test_superuser_does_not_bypass_explicit_health_grant(self):
        admin = self._user('technical-admin', superuser=True)
        self._grant(admin, 'can_view_hc', unit=None)

        with self.assertRaises(PermissionDenied):
            require_hc_capability(admin, 'hc_health_read')

    def test_health_grant_is_specific_and_auditable(self):
        clinician = self._user('occupational-clinician')
        self._grant(clinician, 'hc_health_read', unit=self.root)
        event = PeristiwaSDM.objects.create(
            actor=clinician,
            jenis_peristiwa='health_record_read',
            target_tipe='employee',
            target_id=str(self.staff.pk),
            alasan='Authorized occupational-health review',
        )

        require_hc_capability(
            clinician, 'hc_health_read', unit=self.root, employee=self.staff
        )
        self.assertEqual(event.target_id, str(self.staff.pk))
        with self.assertRaises(PermissionDenied):
            require_hc_capability(
                clinician, 'hc_health_write', unit=self.root, employee=self.staff
            )

    def test_user_with_hc_grants_must_be_revoked_before_account_deletion(self):
        user = self._user('granted-user')
        grant = self._grant(user, 'can_view_hc', unit=self.root)

        with self.assertRaises(ProtectedError):
            user.delete()

        self.assertTrue(HcGrant.objects.filter(pk=grant.pk, is_active=True).exists())

    def test_expired_health_grant_is_denied(self):
        clinician = self._user('former-occupational-clinician')
        self._grant(
            clinician,
            'hc_health_read',
            unit=self.root,
            valid_from=self.today - timedelta(days=10),
            valid_until=self.today - timedelta(days=1),
        )

        with self.assertRaises(PermissionDenied):
            require_hc_capability(
                clinician, 'hc_health_read', unit=self.root, employee=self.staff
            )

    def test_survey_freeze_keeps_hr_reads_but_blocks_writes(self):
        SystemConfig._solo_cache = None
        self.addCleanup(lambda: setattr(SystemConfig, '_solo_cache', None))
        user = self._user('freeze-hr', role='KEPALA_UNIT', unit=self.root)
        self._grant(user, 'can_view_hc', unit=self.root)
        self._grant(user, 'can_manage_hc_employees', unit=self.root)
        role_config = RolePermissionConfig.get_config_for_role('KEPALA_UNIT')
        role_config.can_view_hc = True
        role_config.can_manage_hc_employees = True
        role_config.save(update_fields=[
            'can_view_hc', 'can_manage_hc_employees', 'updated_at'
        ])
        system_config = SystemConfig.get_solo()
        system_config.survey_freeze_mode = True
        system_config.save(update_fields=['survey_freeze_mode'])

        self.assertEqual(list(visible_employees(user)), [self.staff])
        with self.assertRaises(PermissionDenied):
            require_hc_capability(
                user, 'can_manage_hc_employees', unit=self.root, employee=self.staff
            )

    def test_audit_events_cannot_be_edited_or_deleted(self):
        event = PeristiwaSDM.objects.create(
            jenis_peristiwa='employee_created',
            target_tipe='employee',
            target_id=str(self.staff.pk),
        )
        event.jenis_peristiwa = 'rewritten'

        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

    def test_audit_queryset_updates_are_rejected(self):
        event = PeristiwaSDM.objects.create(
            jenis_peristiwa='employee_created',
            target_tipe='employee',
            target_id=str(self.staff.pk),
        )

        with self.assertRaises(ValidationError):
            PeristiwaSDM.objects.filter(pk=event.pk).update(alasan='rewritten')

    def test_audit_queryset_deletes_are_rejected(self):
        event = PeristiwaSDM.objects.create(
            jenis_peristiwa='employee_created',
            target_tipe='employee',
            target_id=str(self.staff.pk),
        )

        with self.assertRaises(ValidationError):
            PeristiwaSDM.objects.filter(pk=event.pk).delete()

    def test_audit_bulk_updates_are_rejected(self):
        event = PeristiwaSDM.objects.create(
            jenis_peristiwa='employee_created',
            target_tipe='employee',
            target_id=str(self.staff.pk),
        )
        event.alasan = 'rewritten'

        with self.assertRaises(ValidationError):
            PeristiwaSDM.objects.bulk_update([event], ['alasan'])

    def test_control_center_exposes_new_role_permission_fields(self):
        admin = self._user(
            'hc-permission-admin', superuser=True, role='SUPER_ADMIN'
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('accounts:admin_control_center'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'can_view_hc')
        self.assertContains(response, 'can_manage_hc_employees')
        self.assertContains(response, 'can_export_hc')

    def test_role_permission_endpoint_updates_hc_capability(self):
        admin = self._user(
            'hc-permission-editor', superuser=True, role='SUPER_ADMIN'
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse('accounts:update_role_permissions'),
            data='{"ADMIN_RS":{"can_view_hc":true}}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            RolePermissionConfig.objects.get(role='ADMIN_RS').can_view_hc
        )


class StageCapabilityTests(TestCase):
    """D-0: per-stage credential capabilities are first-class and scoped."""

    STAGE_CAPABILITIES = (
        'hc_verify_credentials',
        'hc_review_subkomite',
        'hc_recommend_komite',
        'hc_approve_credentials',
    )

    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Tahap', code='HC-TAHAP')
        self.other_unit = UnitKerja.objects.create(name='Unit Tahap Lain', code='HC-TAHAP2')

    def test_stage_capabilities_are_declared(self):
        from sdm.models import HcGrant

        choices = dict(HcGrant.CAPABILITY_CHOICES)
        for capability in self.STAGE_CAPABILITIES:
            self.assertIn(capability, choices)

    def test_role_configuration_exposes_stage_fields(self):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        for capability in self.STAGE_CAPABILITIES:
            self.assertTrue(hasattr(config, capability), capability)
            self.assertFalse(getattr(config, capability), capability)

    def test_grant_without_role_permission_is_denied(self):
        user = get_user_model().objects.create_user(username='stage-denied')
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        HcGrant.objects.create(
            user=user, capability='hc_review_subkomite', unit_kerja=self.unit,
        )
        with self.assertRaises(PermissionDenied):
            require_hc_capability(user, 'hc_review_subkomite', unit=self.unit)

    def test_grant_with_role_permission_is_allowed(self):
        user = get_user_model().objects.create_user(username='stage-allowed')
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.hc_review_subkomite = True
        config.save(update_fields=['hc_review_subkomite', 'updated_at'])
        HcGrant.objects.create(
            user=user, capability='hc_review_subkomite', unit_kerja=self.unit,
        )
        self.assertIsNone(
            require_hc_capability(user, 'hc_review_subkomite', unit=self.unit)
        )

    def test_stage_capability_still_respects_unit_scope(self):
        user = get_user_model().objects.create_user(username='stage-scope')
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.other_unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.hc_approve_credentials = True
        config.save(update_fields=['hc_approve_credentials', 'updated_at'])
        HcGrant.objects.create(
            user=user, capability='hc_approve_credentials', unit_kerja=self.other_unit,
        )
        with self.assertRaises(PermissionDenied):
            require_hc_capability(user, 'hc_approve_credentials', unit=self.unit)

    def test_stage_capabilities_do_not_widen_legacy_review_access(self):
        user = get_user_model().objects.create_user(username='stage-legacy')
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.hc_review_subkomite = True
        config.hc_recommend_komite = True
        config.hc_approve_credentials = True
        config.save(update_fields=[
            'hc_review_subkomite', 'hc_recommend_komite',
            'hc_approve_credentials', 'updated_at',
        ])
        HcGrant.objects.create(
            user=user, capability='hc_review_subkomite', unit_kerja=self.unit,
        )
        # Legacy review capability is not implied by any stage capability.
        with self.assertRaises(PermissionDenied):
            require_hc_capability(
                user, 'can_review_hc_credentials', unit=self.unit,
            )
