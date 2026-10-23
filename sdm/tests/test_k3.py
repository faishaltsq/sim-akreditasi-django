from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AksesDaruratK3,
    HcGrant,
    InsidenK3Pegawai,
    Pegawai,
    PenempatanPegawai,
    TindakLanjutK3,
)
from sdm.services.k3 import (
    add_followup,
    assign_investigation,
    can_read_clinical_detail,
    close_incident,
    fitness_summary,
    record_health_exam,
    record_immunization,
    report_incident,
    request_break_glass,
    review_break_glass,
)


class LevelFourBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit K3', code='HC-K3')
        self.clinician = self._user('k3-clinician')
        self.hr = self._user('hr-operator')
        self.admin = self._user('technical-admin', superuser=True)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        for capability in ('hc_health_read', 'hc_health_write', 'hc_health_break_glass'):
            HcGrant.objects.create(
                user=self.clinician, capability=capability, unit_kerja=self.unit
            )
        HcGrant.objects.create(
            user=self.hr, capability='can_view_hc', unit_kerja=self.unit
        )
        HcGrant.objects.create(
            user=self.admin, capability='can_view_hc', unit_kerja=self.unit
        )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai K3', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )

    def _user(self, username, *, superuser=False):
        user = get_user_model().objects.create_user(
            username=username, is_superuser=superuser
        )
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user


class HealthBoundaryTests(LevelFourBase):
    def test_technical_superuser_without_health_grant_cannot_read_clinical_detail(self):
        self.assertFalse(can_read_clinical_detail(self.admin, self.employee))

    def test_hr_operator_cannot_read_clinical_detail(self):
        self.assertFalse(can_read_clinical_detail(self.hr, self.employee))

    def test_granted_clinician_can_read_clinical_detail(self):
        self.assertTrue(can_read_clinical_detail(self.clinician, self.employee))

    def test_hr_cannot_record_a_health_exam(self):
        with self.assertRaises(PermissionDenied):
            record_health_exam(
                self.employee, actor=self.hr, tanggal=self.today,
                status_kebugaran='FIT',
            )

    def test_clinician_records_exam_and_outside_sees_only_summary(self):
        record_health_exam(
            self.employee, actor=self.clinician, tanggal=self.today,
            status_kebugaran='FIT_DENGAN_CATATAN',
            ringkasan_klinis='Detail klinis rahasia',
            berlaku_sampai=self.today + timedelta(days=365),
        )

        summary = fitness_summary(self.employee, user=self.hr)

        self.assertEqual(summary['status_kebugaran'], 'Fit dengan catatan')
        self.assertNotIn('ringkasan_klinis', summary)

    def test_immunization_requires_a_health_write_grant(self):
        with self.assertRaises(PermissionDenied):
            record_immunization(
                self.employee, actor=self.hr, jenis='Hepatitis B',
                dosis_ke=1, tanggal=self.today,
            )

        record = record_immunization(
            self.employee, actor=self.clinician, jenis='Hepatitis B',
            dosis_ke=1, tanggal=self.today,
        )
        self.assertEqual(record.dosis_ke, 1)

    def test_employee_self_access_does_not_grant_clinical_detail(self):
        self.employee.akun = self.hr
        self.employee.save(update_fields=['akun', 'updated_at'])

        self.assertFalse(can_read_clinical_detail(self.hr, self.employee))


class IncidentWorkflowTests(LevelFourBase):
    def _incident(self):
        return report_incident(
            self.employee, actor=self.clinician, unit_kerja=self.unit,
            kategori='TERTUSUK_JARUM',
            deskripsi='Tertusuk jarum saat tindakan di ruang perawatan.',
        )

    def test_incident_intake_records_category_and_status(self):
        incident = self._incident()

        self.assertEqual(incident.status, 'BARU')
        self.assertEqual(incident.kategori, 'TERTUSUK_JARUM')

    def test_short_description_is_rejected(self):
        with self.assertRaises(ValidationError):
            report_incident(
                self.employee, actor=self.clinician, unit_kerja=self.unit,
                kategori='TERTUSUK_JARUM', deskripsi='pendek',
            )

    def test_investigation_requires_health_write_and_sets_status(self):
        incident = self._incident()

        with self.assertRaises(PermissionDenied):
            assign_investigation(
                incident, actor=self.hr, investigator=self.clinician
            )

        assign_investigation(
            incident, actor=self.clinician, investigator=self.clinician
        )
        incident.refresh_from_db()
        self.assertEqual(incident.status, 'INVESTIGASI')

    def test_closure_requires_completed_followups(self):
        incident = self._incident()
        assign_investigation(
            incident, actor=self.clinician, investigator=self.clinician
        )
        add_followup(
            incident, actor=self.clinician, tindakan='Pemeriksaan serologi'
        )
        incident.refresh_from_db()

        with self.assertRaises(ValidationError):
            close_incident(incident, actor=self.clinician)

        TindakLanjutK3.objects.filter(insiden=incident).update(selesai=True)
        close_incident(incident, actor=self.clinician)
        incident.refresh_from_db()
        self.assertEqual(incident.status, 'SELESAI')

    def test_closure_without_followup_is_rejected(self):
        incident = self._incident()

        with self.assertRaises(ValidationError):
            close_incident(incident, actor=self.clinician)


class BreakGlassTests(LevelFourBase):
    def test_break_glass_requires_reason_and_expires(self):
        access = request_break_glass(
            self.employee, actor=self.clinician, reason='Kecelakaan kerja massal'
        )

        self.assertTrue(access.is_valid())
        self.assertGreater(access.expires_at, timezone.now())

    def test_break_glass_without_reason_is_rejected(self):
        with self.assertRaises(ValidationError):
            request_break_glass(self.employee, actor=self.clinician, reason='  ')

    def test_hr_cannot_request_break_glass(self):
        with self.assertRaises(PermissionDenied):
            request_break_glass(
                self.employee, actor=self.hr, reason='Penasaran'
            )

    def test_review_marks_access_as_closed(self):
        access = request_break_glass(
            self.employee, actor=self.clinician, reason='Paparan biologis'
        )

        review_break_glass(access, reviewer=self.clinician, notes='Sesuai indikasi')
        access.refresh_from_db()

        self.assertFalse(access.is_valid())
        self.assertIsNotNone(access.reviewed_at)
