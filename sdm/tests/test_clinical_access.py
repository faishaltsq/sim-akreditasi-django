"""RED tests for Task A5: clinical privilege workflow and trainee placement."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    ClinicalActionCode,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PenugasanKlinis,
    PeristiwaSDM,
    PrivilegeSnapshot,
    TraineePlacement,
)
from sdm.services.clinical_access import (
    effective_privileges,
    issue_spk,
    require_clinical_action,
    revoke_spk,
    trainee_effective_actions,
)


class ClinicalPrivilegeTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Poli Umum', code='POL-UM')
        self.doctor = Pegawai.objects.create(
            nama_lengkap='Dokter', kategori='PPA', profesi='Dokter Umum',
            status='AKTIF', data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.doctor, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=1.00,
        )
        self.actor = self._user('committee-actor')
        self.code = ClinicalActionCode.objects.create(
            code='PRESCRIBE', label='Resep Obat', is_active=True,
        )
        pengajuan = __import__('sdm.models', fromlist=['PengajuanKredensial']).PengajuanKredensial.objects.create(
            employee=self.doctor, unit_kerja=self.unit, status='DISETUJUI',
            submitted_by=self.actor,
        )
        pengajuan.full_clean()
        keputusan = __import__('sdm.models', fromlist=['KeputusanKredensial']).KeputusanKredensial.objects.create(
            pengajuan=pengajuan, outcome='DISETUJUI', decided_by=self.actor,
        )
        self.spk = PenugasanKlinis.objects.create(
            employee=self.doctor,
            unit_kerja=self.unit,
            decision=keputusan,
            nomor_spk='SPK-001',
            versi=1,
            berlaku_mulai=self.today,
            berlaku_sampai=self.today + timezone.timedelta(days=365),
            is_active=True,
            issued_by=self.actor,
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_review_hc_credentials = True
        config.save(update_fields=['can_view_hc', 'can_review_hc_credentials', 'updated_at'])
        HcGrant.objects.create(user=user, capability='can_view_hc', unit_kerja=self.unit)
        HcGrant.objects.create(
            user=user, capability='can_review_hc_credentials', unit_kerja=self.unit
        )
        self.doctor.akun = user
        self.doctor.save(update_fields=['akun', 'updated_at'])
        return user

    def test_effective_privileges_empty_before_spk(self):
        self.assertEqual(effective_privileges(self.doctor, unit=self.unit, at=self.today), set())

    def test_issue_spk_creates_immutable_snapshots(self):
        created = issue_spk(
            actor=self.actor,
            employee=self.doctor,
            unit=self.unit,
            action_codes=['PRESCRIBE'],
            valid_from=self.today,
            valid_until=self.today + timezone.timedelta(days=365),
            source_decision=self.spk,
            reason='Persetujuan komite',
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(
            effective_privileges(self.doctor, unit=self.unit, at=self.today),
            {'PRESCRIBE'},
        )
        self.assertTrue(
            PeristiwaSDM.objects.filter(jenis_peristiwa='spk_issued').exists()
        )

    def test_revoke_spk_deactivates_snapshot(self):
        issue_spk(
            actor=self.actor, employee=self.doctor, unit=self.unit,
            action_codes=['PRESCRIBE'], valid_from=self.today,
            source_decision=self.spk, reason='r',
        )
        revoke_spk(
            actor=self.actor, employee=self.doctor, unit=self.unit,
            action_codes=['PRESCRIBE'], at=self.today + timezone.timedelta(days=10),
            reason='cabut',
        )
        future = self.today + timezone.timedelta(days=20)
        self.assertNotIn('PRESCRIBE', effective_privileges(self.doctor, unit=self.unit, at=future))

    def test_require_clinical_action_denied_without_privilege(self):
        class Encounter:
            unit_kerja = self.unit

        with self.assertRaises(PermissionDenied):
            require_clinical_action(
                self.actor, action_code='PRESCRIBE', encounter=Encounter(), at=self.today
            )

    def test_require_clinical_action_allowed_with_privilege(self):
        issue_spk(
            actor=self.actor, employee=self.doctor, unit=self.unit,
            action_codes=['PRESCRIBE'], valid_from=self.today,
            source_decision=self.spk, reason='r',
        )

        class Encounter:
            unit_kerja = self.unit

        require_clinical_action(
            self.actor, action_code='PRESCRIBE', encounter=Encounter(), at=self.today
        )  # should not raise


class TraineePlacementTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Poli Umum', code='POL-UM')
        self.trainee = Pegawai.objects.create(
            nama_lengkap='Magang', kategori='NON_PPA', profesi='Magang',
            status='AKTIF', data_origin='MANUAL',
        )
        self.supervisor = Pegawai.objects.create(
            nama_lengkap='Pembimbing', kategori='PPA', profesi='Dokter Spesialis',
            status='AKTIF', data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.trainee, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=1.00,
        )
        self.placement = TraineePlacement.objects.create(
            pegawai=self.trainee,
            unit_kerja=self.unit,
            institution='FK',
            program='Pendidikan Dokter',
            supervisor=self.supervisor,
            tanggal_mulai=self.today,
            tanggal_selesai=self.today + timezone.timedelta(days=30),
            temporary_action_codes=['PRESCRIBE'],
            requires_countersignature=True,
            is_active=True,
        )

    def test_trainee_actions_only_when_placement_active(self):
        actions = trainee_effective_actions(self.trainee, unit=self.unit, at=self.today)
        self.assertIn('PRESCRIBE', actions)
        future = self.today + timezone.timedelta(days=40)
        self.assertEqual(
            trainee_effective_actions(self.trainee, unit=self.unit, at=future), set()
        )
