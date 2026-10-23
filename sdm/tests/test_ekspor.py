from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from pasien.models import Bed, KunjunganPasien, Pasien, Ruangan
from sdm.models import (
    AktivitasBebanKerja,
    HcGrant,
    HasilFormasi,
    Pegawai,
    PenempatanPegawai,
    PesertaDiklat,
    ProgramDiklat,
    RencanaFormasi,
    SesiDiklat,
)
from sdm.services.analitik import compute_bor, staffing_bor_comparison
from sdm.services.kinerja import (
    check_in_by_token,
    complete_training,
    issue_certificate,
    record_attendance,
    register_participant,
)


class AnalyticsBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit BOR', code='HC-BOR')
        self.user = self._user('bor-user')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_view_hc_analytics = True
        config.can_manage_hc_training = True
        config.save(update_fields=[
            'can_view_hc', 'can_view_hc_analytics', 'can_manage_hc_training', 'updated_at',
        ])
        for capability in ('can_view_hc', 'can_view_hc_analytics', 'can_manage_hc_training'):
            HcGrant.objects.create(
                user=self.user, capability=capability, unit_kerja=self.unit
            )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai BOR', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user


class BorTests(AnalyticsBase):
    def _room(self, beds=2):
        room = Ruangan.objects.create(
            kode='BOR-1', nama='Ruang BOR', kelas='1', jenis='RANAP', kapasitas=beds
        )
        created = [
            Bed.objects.create(ruangan=room, kode_bed=f'B{i}', status='TERSEDIA')
            for i in range(beds)
        ]
        return room, created

    def test_bor_unavailable_without_active_beds(self):
        result = compute_bor(
            unit=self.unit,
            period_start=self.today - timedelta(days=5),
            period_end=self.today,
        )

        self.assertFalse(result['is_available'])
        self.assertIn('Tidak ada bed', result['unavailable_reason'])

    def test_bor_uses_admissions_not_current_bed_snapshot(self):
        room, beds = self._room(beds=2)
        patient = Pasien.objects.create(
            no_rm='RM-BOR-1', nama_lengkap='Pasien BOR', tanggal_lahir=self.today - timedelta(days=9000)
        )
        KunjunganPasien.objects.create(
            pasien=patient,
            jenis_kunjungan='RANAP',
            tanggal_masuk=timezone.now() - timedelta(days=2),
            tanggal_keluar=timezone.now() - timedelta(days=1),
            bed=beds[0],
            status='PULANG',
        )
        # Beds are physically empty now, but the historical period had occupancy.
        for bed in beds:
            bed.status = 'TERSEDIA'
            bed.save(update_fields=['status'])

        result = compute_bor(
            unit=self.unit,
            period_start=self.today - timedelta(days=2),
            period_end=self.today,
        )

        self.assertTrue(result['is_available'])
        self.assertGreater(result['value'], Decimal('0'))
        self.assertEqual(result['denominator'], Decimal('6'))

    def test_staffing_bor_reports_missing_plan_explicitly(self):
        room, beds = self._room(beds=1)

        result = staffing_bor_comparison(
            user=self.user, unit=self.unit,
            period_start=self.today - timedelta(days=5),
            period_end=self.today,
        )

        self.assertFalse(result['is_available'])
        self.assertIn('rencana formasi', result['reason'])


class TrainingCertificateTests(AnalyticsBase):
    def setUp(self):
        super().setUp()
        self.program = ProgramDiklat.objects.create(nama='BLS', jp=Decimal('4.00'))
        self.session = SesiDiklat.objects.create(
            program=self.program, tanggal=self.today, kapasitas=5
        )

    def test_certificate_requires_a_passing_evaluation(self):
        participant = register_participant(
            self.session, self.employee, actor=self.user
        )

        with self.assertRaises(ValidationError):
            issue_certificate(participant, actor=self.user)

        record_attendance(participant, actor=self.user, minutes=240)
        complete_training(
            participant, actor=self.user, score=Decimal('90'), passed=True
        )
        certificate = issue_certificate(participant, actor=self.user)

        self.assertTrue(certificate.nomor)
        self.assertEqual(issue_certificate(participant, actor=self.user).pk, certificate.pk)

    def test_failed_participant_cannot_receive_a_certificate(self):
        participant = register_participant(
            self.session, self.employee, actor=self.user
        )
        record_attendance(participant, actor=self.user, minutes=240)
        complete_training(
            participant, actor=self.user, score=Decimal('30'), passed=False
        )

        with self.assertRaises(ValidationError):
            issue_certificate(participant, actor=self.user)

    def test_qr_token_is_session_bound(self):
        participant = register_participant(
            self.session, self.employee, actor=self.user
        )
        other_session = SesiDiklat.objects.create(
            program=self.program, tanggal=self.today + timedelta(days=1), kapasitas=5
        )

        with self.assertRaises(ValidationError):
            check_in_by_token(
                participant.qr_token, session=other_session, actor=self.user
            )

        checked = check_in_by_token(
            participant.qr_token, session=self.session, actor=self.user
        )
        self.assertEqual(checked.pk, participant.pk)
        checked.refresh_from_db()
        self.assertEqual(checked.status, 'HADIR')

    def test_expired_qr_token_is_rejected(self):
        participant = register_participant(
            self.session, self.employee, actor=self.user
        )
        PesertaDiklat.objects.filter(pk=participant.pk).update(
            qr_expires_at=timezone.now() - timedelta(minutes=1)
        )
        participant.refresh_from_db()

        with self.assertRaises(ValidationError):
            check_in_by_token(
                participant.qr_token, session=self.session, actor=self.user
            )
