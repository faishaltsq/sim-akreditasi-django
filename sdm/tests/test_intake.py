"""Intake finalization boundary (Task 2)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DrafInputPegawai,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
)
from sdm.services.intake import finalize_staff_intake


STEP1 = {
    'nama_depan': 'Budi', 'nama_belakang': 'Santoso',
    'nik': '3201010101010001', 'telepon': '081234567890',
    'email_terverifikasi': 'budi@example.com',
    'alamat_ktp': 'Jl. Merdeka 1', 'alamat_sama_dengan_ktp': True,
}


class IntakeFinalizationTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='INT-HC')
        self.other = UnitKerja.objects.create(name='Unit Rahasia', code='INT-OTHER')
        self.manager = self._user('intake-manager')

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.save(update_fields=['can_view_hc', 'can_manage_hc_employees', 'updated_at'])
        HcGrant.objects.create(user=user, capability='can_view_hc', unit_kerja=self.root)
        HcGrant.objects.create(
            user=user, capability='can_manage_hc_employees', unit_kerja=self.root,
            include_descendants=True,
        )
        return user

    def _draft(self, *, steps=('1', '2', '3', '4', '5'), version=1, unit=None,
               fte='1.00', **overrides):
        payload = {
            '1': dict(STEP1),
            '2': {
                'nomor_pegawai': 'INT-001', 'kategori': 'NON_PPA',
                'profesi': 'Administrasi', 'jabatan': 'Staf', 'status': 'AKTIF',
                'kategori_pegawai': 'TETAP', 'unit_kerja': (unit or self.root).pk,
                'tanggal_mulai': self.today.isoformat(), 'alokasi_fte': fte,
            },
            '3': {},
            '4': {},
            '5': {},
        }
        payload.update(overrides)
        return DrafInputPegawai.objects.create(
            owner=self.manager,
            current_step=5,
            version=version,
            expires_at=timezone.now() + timedelta(days=1),
            draft_data={key: payload[key] for key in steps},
        )

    def test_all_five_steps_are_required(self):
        draft = self._draft(steps=('1', '2'))
        with self.assertRaises(ValidationError):
            finalize_staff_intake(
                actor=self.manager, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-1',
            )
        self.assertFalse(Pegawai.objects.exists())

    def test_blank_but_present_optional_step_is_complete(self):
        draft = self._draft()  # steps 3/4/5 present and empty
        employee = finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-2',
        )
        self.assertEqual(employee.nomor_pegawai, 'INT-001')

    def test_stale_version_is_refused_without_writing(self):
        draft = self._draft(version=3)
        with self.assertRaises(ValidationError):
            finalize_staff_intake(
                actor=self.manager, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-3',
            )
        self.assertFalse(Pegawai.objects.exists())
        draft.refresh_from_db()
        self.assertEqual(draft.state, 'DRAFT')

    def test_foreign_unit_is_refused(self):
        draft = self._draft(unit=self.other)
        with self.assertRaises(PermissionDenied):
            finalize_staff_intake(
                actor=self.manager, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-4',
            )
        self.assertFalse(Pegawai.objects.exists())

    def test_duplicate_nip_is_refused(self):
        Pegawai.objects.create(nomor_pegawai='INT-001', nama_lengkap='Existing',
                               kategori='NON_PPA')
        draft = self._draft()
        with self.assertRaises(ValidationError):
            finalize_staff_intake(
                actor=self.manager, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-5',
            )
        self.assertEqual(Pegawai.objects.count(), 1)

    def test_fte_above_one_is_refused(self):
        draft = self._draft(fte='1.50')
        with self.assertRaises(ValidationError):
            finalize_staff_intake(
                actor=self.manager, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-6',
            )
        self.assertFalse(Pegawai.objects.exists())

    def test_placement_goes_through_the_assignment_service(self):
        draft = self._draft(fte='0.75')
        employee = finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-7',
        )
        assignment = employee.penempatan.get()
        self.assertEqual(assignment.alokasi_fte, Decimal('0.75'))
        self.assertEqual(assignment.unit_kerja, self.root)

    def test_matching_replay_returns_the_same_employee(self):
        draft = self._draft()
        first = finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-8',
        )
        second = finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-8',
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Pegawai.objects.count(), 1)
        self.assertEqual(PenempatanPegawai.objects.count(), 1)
        self.assertEqual(
            PeristiwaSDM.objects.filter(jenis_peristiwa='employee_created').count(), 1
        )

    def test_different_key_on_finalized_draft_is_refused(self):
        draft = self._draft()
        finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-9',
        )
        with self.assertRaises(ValidationError):
            finalize_staff_intake(
                actor=self.manager, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-other',
            )
        self.assertEqual(Pegawai.objects.count(), 1)

    def test_expired_draft_is_refused(self):
        draft = self._draft()
        DrafInputPegawai.objects.filter(pk=draft.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        with self.assertRaises(ValidationError):
            finalize_staff_intake(
                actor=self.manager, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-10',
            )
        draft.refresh_from_db()
        self.assertEqual(draft.state, 'EXPIRED')
        self.assertFalse(Pegawai.objects.exists())

    def test_foreign_owners_draft_is_not_found(self):
        draft = self._draft()
        intruder = self._user('intake-intruder')
        with self.assertRaises(ValidationError):
            finalize_staff_intake(
                actor=intruder, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-11',
            )
        self.assertFalse(Pegawai.objects.exists())

    def test_license_validity_label_is_not_a_typo(self):
        from sdm.models import IzinProfesiPegawai
        labels = dict(IzinProfesiPegawai.VALIDITY_MODE_CHOICES)
        self.assertEqual(labels['DATED'], 'Tanggal Berlaku')

    def test_str_and_multiple_sips_are_persisted(self):
        draft = self._draft(**{'3': {
            'izin_subtype': 'STR', 'nomor_izin': 'STR-001',
            'validity_mode': 'LIFETIME', 'izin_profesi': 'Perawat',
            'pendidikan_tingkat': 'S1', 'pendidikan_institusi': 'Universitas A',
            'sip-TOTAL_FORMS': '2', 'sip-INITIAL_FORMS': '0',
            'sip-MIN_NUM_FORMS': '0', 'sip-MAX_NUM_FORMS': '1000',
            'sip-0-nomor_izin': 'SIP-001', 'sip-0-lokasi_praktik': 'RS ARima',
            'sip-0-is_local_rs': 'on', 'sip-0-tanggal_terbit': '2026-01-01',
            'sip-0-tanggal_berakhir': '2031-01-01',
            'sip-1-nomor_izin': 'SIP-002', 'sip-1-lokasi_praktik': 'Klinik X',
            'sip-1-tanggal_terbit': '2026-02-01',
            'sip-1-tanggal_berakhir': '2031-02-01',
        }})
        employee = finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-sip',
        )
        permits = employee.izin_profesi.order_by('nomor_izin')
        self.assertEqual(permits.count(), 3)
        self.assertEqual(
            list(permits.values_list('subtype', flat=True)),
            ['SIP', 'SIP', 'STR'],
        )
        local = permits.get(nomor_izin='SIP-001')
        self.assertTrue(local.is_local_rs)
        self.assertEqual(local.validity_mode, 'DATED')
        self.assertEqual(permits.get(subtype='STR').validity_mode, 'LIFETIME')
        self.assertEqual(employee.riwayat_pendidikan.count(), 1)

    def test_sub_unit_must_descend_from_the_selected_unit(self):
        child = UnitKerja.objects.create(
            name='Ruang Melati', code='INT-HC-RM', parent=self.root
        )
        foreign_child = UnitKerja.objects.create(
            name='Ruang Asing', code='INT-OTHER-RA', parent=self.other
        )
        draft = self._draft(**{'2': {
            'nomor_pegawai': 'INT-002', 'kategori': 'NON_PPA',
            'status': 'AKTIF', 'kategori_pegawai': 'TETAP',
            'unit_kerja': self.root.pk, 'sub_unit': foreign_child.pk,
            'tanggal_mulai': self.today.isoformat(), 'alokasi_fte': '1.00',
        }})
        with self.assertRaises(ValidationError):
            finalize_staff_intake(
                actor=self.manager, draft_id=draft.pk,
                expected_version=1, idempotency_key='k-sub',
            )
        self.assertFalse(Pegawai.objects.exists())

        draft.draft_data['2']['sub_unit'] = child.pk
        draft.save(update_fields=['draft_data', 'updated_at'])
        employee = finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-sub2',
        )
        assignment = employee.penempatan.get()
        self.assertEqual(assignment.unit_kerja, child)
        self.assertEqual(assignment.unit_induk, self.root)

    def test_empty_profession_master_does_not_block_intake(self):
        from sdm.models import MasterProfesiPegawai
        self.assertEqual(MasterProfesiPegawai.objects.count(), 0)
        draft = self._draft()
        employee = finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-prof',
        )
        self.assertIsNone(employee.profesi_master)
        self.assertEqual(employee.profesi, 'Administrasi')

    def test_intake_never_creates_a_login(self):
        from django.contrib.auth import get_user_model
        draft = self._draft(**{'4': {
            'create_account': True, 'email': 'budi@example.com',
            'intended_role': 'STAF_NAKES', 'account_active': True,
        }})
        before = get_user_model().objects.count()
        employee = finalize_staff_intake(
            actor=self.manager, draft_id=draft.pk,
            expected_version=1, idempotency_key='k-acct',
        )
        self.assertIsNone(employee.akun_id)
        self.assertEqual(get_user_model().objects.count(), before)

    def test_admin_role_cannot_be_delegated_by_intake(self):
        from sdm.forms.intake import IntakeStep4Form
        form = IntakeStep4Form(data={
            'create_account': 'on', 'email': 'x@example.com',
            'intended_role': 'ADMIN_RS', 'account_active': 'on',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('intended_role', form.errors)

    def test_email_is_required_only_when_account_is_requested(self):
        from sdm.forms.intake import IntakeStep4Form
        without = IntakeStep4Form(data={'intended_role': 'STAF_NAKES'})
        self.assertTrue(without.is_valid())
        with_account = IntakeStep4Form(data={'create_account': 'on',
                                             'intended_role': 'STAF_NAKES'})
        self.assertFalse(with_account.is_valid())
        self.assertIn('email', with_account.errors)

    def test_finalize_view_redirects_to_the_created_employee(self):
        draft = self._draft()
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('sdm:pegawai_intake_finalize', kwargs={'draft_id': draft.pk}),
            {'expected_version': str(draft.version)},
        )
        employee = Pegawai.objects.get(nomor_pegawai='INT-001')
        self.assertRedirects(response, reverse('sdm:pegawai_detail', kwargs={
            'employee_id': employee.pk,
        }))
