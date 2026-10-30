from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AktivitasOrientasi,
    DokumenPegawai,
    HcGrant,
    Lamaran,
    Lowongan,
    Pegawai,
    PenempatanPegawai,
    PengajuanKredensial,
    PenugasanKlinis,
    PenugasanOrientasi,
    ProgramOrientasi,
    RincianKewenangan,
    VerifikasiSumber,
    VersiDokumen,
)
from sdm.services.rekrutmen import (
    complete_activity,
    decide_credential,
    hire_application,
    issue_spk,
    move_application,
    record_psv,
    revoke_spk,
    start_orientation,
)


class LevelTwoBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Level2', code='HC-L2')
        self.other = UnitKerja.objects.create(name='Unit Lain L2', code='HC-L2-2')
        self.recruiter = self._user('recruiter')
        self.committee = self._user('committee')
        self.config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        self.config.can_manage_hc_recruitment = True
        self.config.can_review_hc_credentials = True
        self.config.can_manage_hc_orientation = True
        self.config.can_manage_hc_documents = True
        self.config.save(update_fields=[
            'can_manage_hc_recruitment', 'can_review_hc_credentials',
            'can_manage_hc_orientation', 'can_manage_hc_documents', 'updated_at',
        ])
        for capability in (
            'can_manage_hc_recruitment', 'can_review_hc_credentials',
            'can_manage_hc_orientation', 'can_manage_hc_documents',
        ):
            for user in (self.recruiter, self.committee):
                HcGrant.objects.create(
                    user=user, capability=capability, unit_kerja=self.unit
                )
        self.lowongan = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Perawat Baru'
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user

    def _application(self):
        return Lamaran.objects.create(
            lowongan=self.lowongan, nama_pelamar='Pelamar Uji'
        )


class RecruitmentWorkflowTests(LevelTwoBase):
    def test_stage_cannot_be_skipped(self):
        application = self._application()

        with self.assertRaises(ValidationError):
            move_application(application, target='DITERIMA', actor=self.recruiter)

    def test_wawancara_tidak_bisa_lompat_ke_diterima_tanpa_mcu(self):
        """Alur dokumen: MCU (KPS 3) wajib sebelum penawaran kerja."""
        application = self._application()
        for stage in ('SELEKSI_ADMIN', 'TES_KOMPETENSI', 'WAWANCARA'):
            application = move_application(
                application, target=stage, actor=self.recruiter
            )
        with self.assertRaises(ValidationError):
            move_application(application, target='DITERIMA', actor=self.recruiter)

    def test_mcu_dan_offering_menjadi_jalur_wajib(self):
        application = self._application()
        for stage in (
            'SELEKSI_ADMIN', 'TES_KOMPETENSI', 'WAWANCARA', 'MCU', 'OFFERING',
        ):
            application = move_application(
                application, target=stage, actor=self.recruiter
            )
        application.refresh_from_db()
        self.assertEqual(application.status, 'OFFERING')
        self.assertEqual(application.history.count(), 5)

    def test_each_stage_records_history(self):
        application = self._application()

        move_application(application, target='SELEKSI_ADMIN', actor=self.recruiter)
        application.refresh_from_db()

        self.assertEqual(application.status, 'SELEKSI_ADMIN')
        self.assertEqual(application.history.count(), 1)

    def test_hiring_is_idempotent_and_creates_one_employee(self):
        from sdm.models import UrutanNomorPegawai

        UrutanNomorPegawai.objects.create(
            scope='rekrutmen', period_start=self.today,
            format_pattern='EMP-{year}-{counter:04d}',
        )
        program = ProgramOrientasi.objects.create(nama='Orientasi Umum', jenis='UMUM')
        AktivitasOrientasi.objects.create(program=program, nama='Pengenalan')
        application = self._application()
        for stage in (
            'SELEKSI_ADMIN', 'TES_KOMPETENSI', 'WAWANCARA', 'MCU',
            'OFFERING', 'DITERIMA',
        ):
            application = move_application(
                application, target=stage, actor=self.recruiter
            )

        first = hire_application(
            application, actor=self.recruiter, idempotency_key='hire-1'
        )
        second = hire_application(
            application, actor=self.recruiter, idempotency_key='hire-1'
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Pegawai.objects.filter(nama_lengkap='Pelamar Uji').count(), 1)

    def test_hiring_rejects_a_non_accepted_application(self):
        application = self._application()

        with self.assertRaises(ValidationError):
            hire_application(
                application, actor=self.recruiter, idempotency_key='hire-2'
            )

    def test_foreign_unit_recruiter_is_denied(self):
        outsider = self._user('foreign-recruiter')
        HcGrant.objects.create(
            user=outsider, capability='can_manage_hc_recruitment', unit_kerja=self.other
        )
        application = self._application()

        with self.assertRaises(PermissionDenied):
            move_application(application, target='SELEKSI_ADMIN', actor=outsider)


class CredentialWorkflowTests(LevelTwoBase):
    def setUp(self):
        super().setUp()
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Kredensial', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=20),
            alokasi_fte=Decimal('1.00'),
        )
        self.document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL',
            title='STR', sensitivity='personnel',
        )
        self.version = VersiDokumen.objects.create(
            document=self.document, version_number=1, original_filename='str.pdf',
            storage_key=f'personnel/{self.employee.pk}/{self.document.pk}.pdf',
            sha256='a' * 64, size_bytes=10, content_type='application/pdf',
            status='VERIFIED', valid_until=self.today + timedelta(days=365),
        )
        self.application = PengajuanKredensial.objects.create(
            employee=self.employee, unit_kerja=self.unit,
            submitted_by=self.recruiter,
        )
        RincianKewenangan.objects.create(
            pengajuan=self.application, kewenangan='Asuhan keperawatan dasar'
        )

    def test_psv_records_exact_version_and_verifier(self):
        record = record_psv(
            self.employee, self.version, actor=self.committee,
            issuer='Kemenkes', reference='STR-1', method='Situs resmi',
            outcome='VALID',
        )

        self.assertEqual(record.version, self.version)
        self.assertEqual(record.verifier, self.committee)

    def test_psv_rejects_a_version_from_another_employee(self):
        other_employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Lain', kategori='PPA'
        )
        PenempatanPegawai.objects.create(
            pegawai=other_employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=5),
            alokasi_fte=Decimal('1.00'),
        )

        with self.assertRaises(ValidationError):
            record_psv(
                other_employee, self.version, actor=self.committee,
                issuer='Kemenkes', reference='STR-1', method='Situs resmi',
                outcome='VALID',
            )

    def test_spk_requires_an_approved_committee_decision(self):
        with self.assertRaises(ValidationError):
            issue_spk(
                self.application, actor=self.committee, nomor_spk='SPK-001',
                berlaku_mulai=self.today,
            )

    def test_rejected_committee_decision_blocks_spk(self):
        decide_credential(
            self.application, actor=self.committee, outcome='DITOLAK', notes='tidak lengkap'
        )

        with self.assertRaises(ValidationError):
            issue_spk(
                self.application, actor=self.committee, nomor_spk='SPK-002',
                berlaku_mulai=self.today,
            )

    def test_approved_decision_allows_numbered_spk_and_revocation(self):
        decide_credential(
            self.application, actor=self.committee, outcome='DISETUJUI'
        )
        assignment = issue_spk(
            self.application, actor=self.committee, nomor_spk='SPK-003',
            berlaku_mulai=self.today,
            berlaku_sampai=self.today + timedelta(days=365),
        )

        self.assertEqual(assignment.nomor_spk, 'SPK-003')
        self.assertEqual(assignment.versi, 1)
        revoke_spk(assignment, actor=self.committee, reason='rotasi unit')
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

    def test_expired_credential_blocks_spk_issuance(self):
        self.version.valid_until = self.today - timedelta(days=1)
        self.version.save(update_fields=['valid_until'])
        decide_credential(self.application, actor=self.committee, outcome='DISETUJUI')

        with self.assertRaises(ValidationError):
            issue_spk(
                self.application, actor=self.committee, nomor_spk='SPK-004',
                berlaku_mulai=self.today,
            )

    def test_committee_decision_is_immutable(self):
        decide_credential(self.application, actor=self.committee, outcome='DISETUJUI')
        decision = self.application.decision

        with self.assertRaises(ValidationError):
            decision.outcome = 'DITOLAK'
            decision.save()


class OrientationWorkflowTests(LevelTwoBase):
    def setUp(self):
        super().setUp()
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Orientasi', kategori='PPA'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=2),
            alokasi_fte=Decimal('1.00'),
        )
        self.program = ProgramOrientasi.objects.create(
            nama='Orientasi Umum', unit_kerja=self.unit, berlaku_hari=14
        )
        self.first = AktivitasOrientasi.objects.create(
            program=self.program, nama='Kebijakan RS', wajib=True, urutan=1
        )
        self.second = AktivitasOrientasi.objects.create(
            program=self.program, nama='PPI Dasar', wajib=True, urutan=2
        )

    def test_starting_orientation_creates_pending_activities_and_due_date(self):
        assignment = start_orientation(
            self.employee, self.program, actor=self.recruiter
        )

        self.assertEqual(assignment.completions.count(), 2)
        self.assertEqual(assignment.tenggat, self.today + timedelta(days=14))
        self.assertEqual(assignment.progress_pct, 0.0)

    def test_completing_all_required_activities_finishes_assignment(self):
        assignment = start_orientation(
            self.employee, self.program, actor=self.recruiter
        )
        for completion in assignment.completions.all():
            complete_activity(completion, actor=self.recruiter)

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'SELESAI')
        self.assertEqual(assignment.progress_pct, 100.0)

    def test_program_without_activities_cannot_be_assigned(self):
        empty = ProgramOrientasi.objects.create(nama='Kosong', unit_kerja=self.unit)

        with self.assertRaises(ValidationError):
            start_orientation(self.employee, empty, actor=self.recruiter)

    def test_rotation_keeps_previous_assignment_history(self):
        first_assignment = start_orientation(
            self.employee, self.program, actor=self.recruiter
        )
        second_program = ProgramOrientasi.objects.create(
            nama='Orientasi Unit Lain', unit_kerja=self.unit
        )
        AktivitasOrientasi.objects.create(
            program=second_program, nama='Alur unit', wajib=True
        )

        start_orientation(self.employee, second_program, actor=self.recruiter)

        self.assertEqual(
            PenugasanOrientasi.objects.filter(employee=self.employee).count(), 2
        )
        self.assertTrue(
            PenugasanOrientasi.objects.filter(pk=first_assignment.pk).exists()
        )
