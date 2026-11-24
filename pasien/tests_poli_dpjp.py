"""Siklus hidup penugasan DPJP episode POLI-JANTUNG (F0.11, ADR-12).

Setiap tes menuntut keadaan ORM yang dapat dibaca ulang, bukan keberadaan
simbol: jumlah baris ``PenugasanDpjpEpisode`` yang aktif, isi
``KunjunganPasien.dpjp``, nomor versi workflow, dan status HTTP jalur nyata.

Bukti yang diminta dispatch ada di ``EndToEndDpjpTest``: daftar → tetapkan
DPJP → simpan langkah 1, seluruhnya lewat HTTP, tanpa Django admin.
"""
import json

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import (
    IgdAssessmentWorkflow, KunjunganPasien, Pasien, PenugasanDpjpEpisode,
)
from pasien.services.poli_dpjp import (
    assert_display_writable, assign_dpjp, clear_dpjp, reconcile_dpjp_display,
)

from .tests_poli_workflow import TEST_STORAGES

POLI_JANTUNG = 'POLI-JANTUNG'
POLI_PD = 'POLI-PD'

class DpjpFixture(TestCase):
    """Dua akun dokter nyata, satu perawat, satu administrasi unit."""

    counter = 0

    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.get_or_create(
            code=POLI_JANTUNG, defaults={'name': 'Poliklinik Jantung', 'level': 3},
        )[0]
        cls.other_unit = UnitKerja.objects.get_or_create(
            code=POLI_PD, defaults={'name': 'Poliklinik Penyakit Dalam', 'level': 3},
        )[0]

        cls.admin = cls._account('admisi_jantung', 'ADMIN_RS', '', cls.unit)
        cls.doctor_a = cls._account('dr_jantung_a', 'STAF_NAKES', 'DOKTER_SPESIALIS', cls.unit,
                                    full_name='dr. Anindya Prameswari, Sp.JP')
        cls.doctor_b = cls._account('dr_jantung_b', 'STAF_NAKES', 'DOKTER_SPESIALIS', cls.unit,
                                    full_name='dr. Bagas Wicaksono, Sp.JP')
        cls.nurse = cls._account('perawat_jantung', 'STAF_NAKES', 'PERAWAT', cls.unit,
                                 full_name='Ns. Ratih Kusuma')
        cls.records = cls._account('rekam_medis_jantung', 'STAF_NAKES', 'PEREKAM_MEDIS', cls.unit,
                                   full_name='Rekam Medis Jantung')

        cls.patient = Pasien.objects.create(
            no_rm='RM-DPJP-01', nama_lengkap='Pasien Uji DPJP',
            tanggal_lahir='1968-03-03', jenis_kelamin='L',
        )

    @classmethod
    def _account(cls, username, role, profesi, unit, *, full_name=''):
        user = User.objects.create_user(username, password='fixture-only')
        UserProfile.objects.update_or_create(
            user=user, defaults={
                'role': role, 'unit_kerja': unit, 'full_name': full_name,
                'profesi': profesi,
            },
        )
        return user

    def make_visit(self, *, unit=None, with_dpjp=False, no_kunjungan=None):
        type(self).counter += 1
        visit = KunjunganPasien.objects.create(
            pasien=self.patient,
            no_kunjungan=no_kunjungan or f'KJ-DPJP-{self.counter:03d}',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            unit_kerja=unit or self.unit, poliklinik='POLI_JANTUNG',
        )
        if with_dpjp:
            assign_dpjp(visit, self.doctor_a, self.admin)
        return visit

    def active_rows(self, visit):
        return PenugasanDpjpEpisode.objects.filter(visit=visit, is_active=True)

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class RegistrationDpjpTest(DpjpFixture):
    """Requirement 1: pendaftaran dengan DPJP membuat penugasan di transaksi yang sama."""

    def register(self, **extra):
        self.client.force_login(self.admin)
        suffix = extra.pop('suffix', '01')
        payload = {
            'pasien_id': self.patient.pk,
            'jenis_kunjungan': 'RAJAL',
            'tanggal_masuk': timezone.now().strftime('%Y-%m-%dT%H:%M:%S%z'),
            'poliklinik': 'Poli Jantung & Pembuluh Darah',
            'penjamin': 'UMUM',
            'no_kunjungan': f'KJ-REG-{suffix}',
        }
        payload.update(extra)
        return self.client.post(reverse('pasien:kunjungan_baru'), payload)

    def test_registration_with_dpjp_creates_exactly_one_active_assignment(self):
        response = self.register(dpjp_user=self.doctor_a.pk)
        self.assertEqual(response.status_code, 302)

        visit = KunjunganPasien.objects.get(no_kunjungan='KJ-REG-01')
        rows = list(self.active_rows(visit))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].doctor_id, self.doctor_a.pk)
        self.assertEqual(rows[0].assignment_type, 'PRIMARY')
        self.assertEqual(rows[0].unit_id, self.unit.pk)
        self.assertEqual(rows[0].assigned_by_id, self.admin.pk)
        self.assertTrue(rows[0].source_version.startswith('REGISTRASI:'))
        self.assertEqual(visit.dpjp, 'dr. Anindya Prameswari, Sp.JP')

    def test_registration_without_dpjp_creates_no_assignment(self):
        response = self.register(suffix='02')
        self.assertEqual(response.status_code, 302)

        visit = KunjunganPasien.objects.get(no_kunjungan='KJ-REG-02')
        self.assertFalse(PenugasanDpjpEpisode.objects.filter(visit=visit).exists())
        self.assertEqual(visit.dpjp, '')

    def test_registration_refuses_non_doctor_account(self):
        before = KunjunganPasien.objects.count()
        response = self.register(dpjp_user=self.nurse.pk, suffix='03')
        # ``kunjungan_baru`` menangkap galat dan kembali ke formulir (200) tanpa
        # menyimpan kunjungan: penugasan dan kunjungan hidup di transaksi yang sama.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(KunjunganPasien.objects.count(), before)
        self.assertFalse(KunjunganPasien.objects.filter(no_kunjungan='KJ-REG-03').exists())

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class DpjpLifecycleTest(DpjpFixture):
    """Requirement 2 dan 4: ganti, cabut, dan idempotensi lewat endpoint dasbor."""

    def assign_via_http(self, visit, doctor):
        self.client.force_login(self.admin)
        return self.client.post(
            reverse('pasien:rajal_dpjp_simpan', args=[visit.pk]),
            {'dpjp_user': doctor.pk if doctor else ''},
        )

    def test_change_deactivates_old_and_activates_new_never_two_active(self):
        visit = self.make_visit(with_dpjp=True)
        self.assertEqual(self.active_rows(visit).count(), 1)

        response = self.assign_via_http(visit, self.doctor_b)
        self.assertEqual(response.status_code, 302)

        active = list(self.active_rows(visit))
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].doctor_id, self.doctor_b.pk)

        old = PenugasanDpjpEpisode.objects.get(visit=visit, doctor=self.doctor_a)
        self.assertFalse(old.is_active)  # dinonaktifkan, tidak dihapus
        self.assertEqual(PenugasanDpjpEpisode.objects.filter(visit=visit).count(), 2)

        visit.refresh_from_db()
        self.assertEqual(visit.dpjp, 'dr. Bagas Wicaksono, Sp.JP')

    def test_clearing_dpjp_leaves_no_active_assignment(self):
        visit = self.make_visit(with_dpjp=True)
        response = self.assign_via_http(visit, None)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(self.active_rows(visit).count(), 0)
        visit.refresh_from_db()
        self.assertEqual(visit.dpjp, '')
        # Riwayat tetap ada: yang hilang hanya keaktifan, bukan bukti.
        self.assertEqual(PenugasanDpjpEpisode.objects.filter(visit=visit).count(), 1)

    def test_resubmitting_same_dpjp_is_idempotent(self):
        visit = self.make_visit(with_dpjp=True)
        first = self.active_rows(visit).get()

        self.assertEqual(self.assign_via_http(visit, self.doctor_a).status_code, 302)
        self.assertEqual(self.assign_via_http(visit, self.doctor_a).status_code, 302)

        rows = self.active_rows(visit)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().pk, first.pk)
        self.assertEqual(PenugasanDpjpEpisode.objects.filter(visit=visit).count(), 1)

    def test_endpoint_rejects_visit_outside_poli_jantung(self):
        visit = self.make_visit(unit=self.other_unit)
        response = self.assign_via_http(visit, self.doctor_a)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PenugasanDpjpEpisode.objects.filter(visit=visit).exists())

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class DpjpAuthorityTest(DpjpFixture):
    """Hanya peran administrasi unit yang boleh menetapkan DPJP (ADR-12 butir 4)."""

    def post_assignment(self, user, visit, doctor):
        self.client.force_login(user)
        return self.client.post(
            reverse('pasien:rajal_dpjp_simpan', args=[visit.pk]),
            {'dpjp_user': doctor.pk},
        )

    def test_nurse_cannot_assign_dpjp(self):
        visit = self.make_visit()
        response = self.post_assignment(self.nurse, visit, self.doctor_a)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PenugasanDpjpEpisode.objects.filter(visit=visit).exists())
        visit.refresh_from_db()
        self.assertEqual(visit.dpjp, '')

    def test_records_officer_cannot_assign_dpjp(self):
        visit = self.make_visit()
        response = self.post_assignment(self.records, visit, self.doctor_a)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PenugasanDpjpEpisode.objects.filter(visit=visit).exists())

    def test_doctor_cannot_assign_self(self):
        visit = self.make_visit()
        response = self.post_assignment(self.doctor_a, visit, self.doctor_a)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PenugasanDpjpEpisode.objects.filter(visit=visit).exists())

class DpjpDisplaySyncTest(DpjpFixture):
    """Requirement 5: kedua arah sinkronisasi string ↔ penugasan."""

    def test_string_follows_assignment(self):
        visit = self.make_visit()
        assign_dpjp(visit, self.doctor_b, self.admin)
        visit.refresh_from_db()
        self.assertEqual(visit.dpjp, 'dr. Bagas Wicaksono, Sp.JP')

    def test_stale_string_is_reconciled_from_assignment(self):
        visit = self.make_visit(with_dpjp=True)
        # Simulasi jalur lama yang menulis string langsung tanpa penugasan.
        KunjunganPasien.objects.filter(pk=visit.pk).update(dpjp='dr. Karangan, Sp.JP')
        visit.refresh_from_db()
        self.assertEqual(visit.dpjp, 'dr. Karangan, Sp.JP')

        restored = reconcile_dpjp_display(visit)
        self.assertEqual(restored, 'dr. Anindya Prameswari, Sp.JP')
        visit.refresh_from_db()
        self.assertEqual(visit.dpjp, 'dr. Anindya Prameswari, Sp.JP')

    def test_legacy_string_write_is_rejected_when_assignment_exists(self):
        visit = self.make_visit(with_dpjp=True)
        with self.assertRaises(PermissionDenied):
            assert_display_writable(visit, 'dr. Karangan, Sp.JP')
        # Penulisan yang sama dengan turunan penugasan tetap boleh (inert).
        assert_display_writable(visit, 'dr. Anindya Prameswari, Sp.JP')

    def test_legacy_string_write_is_inert_without_assignment(self):
        visit = self.make_visit()
        assert_display_writable(visit, 'dr. Jaga IGD')  # tidak melempar

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class NoDpjpBlocksClinicalStepTest(DpjpFixture):
    """ADR-11 butir 4: episode tanpa DPJP tidak boleh masuk langkah klinis."""

    def test_step_one_write_returns_403_without_assignment(self):
        visit = self.make_visit()
        self.client.force_login(self.nurse)
        response = self.client.post(
            reverse('pasien:poli_workflow_draft', args=[visit.pk, 1]),
            data=json.dumps({'fields': {'penjamin': 'UMUM'}, 'version': 0}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=visit).exists())

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class EndToEndDpjpTest(DpjpFixture):
    """Bukti dispatch: daftar → tetapkan DPJP → simpan langkah 1, tanpa admin."""

    def test_register_assign_and_save_step_one_without_django_admin(self):
        # 1. Registrasi lewat HTTP oleh petugas administrasi.
        self.client.force_login(self.admin)
        response = self.client.post(reverse('pasien:kunjungan_baru'), {
            'pasien_id': self.patient.pk,
            'jenis_kunjungan': 'RAJAL',
            'tanggal_masuk': timezone.now().strftime('%Y-%m-%dT%H:%M:%S%z'),
            'poliklinik': 'Poli Jantung & Pembuluh Darah',
            'penjamin': 'UMUM',
            'no_kunjungan': 'KJ-E2E-001',
            'dpjp_user': self.doctor_a.pk,
        })
        self.assertEqual(response.status_code, 302)
        visit = KunjunganPasien.objects.get(no_kunjungan='KJ-E2E-001')

        # 2. Penetapan DPJP sudah terjadi di transaksi registrasi (bukan admin).
        self.assertEqual(self.active_rows(visit).count(), 1)

        # 3. Perawat poli menyimpan langkah 1 lewat route asesmen.
        self.client.force_login(self.nurse)
        response = self.client.post(
            reverse('pasien:poli_workflow_draft', args=[visit.pk, 1]),
            data=json.dumps({
                'fields': {'penjamin': 'UMUM', 'jenis_kunjungan_klinis': 'BARU'},
                'version': 0,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        body = response.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['version'], 1)
        self.assertEqual(body['values']['jenis_kunjungan_klinis'], 'BARU')

        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=visit)
        self.assertEqual(workflow.service_line, 'RAJAL_JANTUNG')
        self.assertEqual(workflow.version, 1)
        self.assertEqual(workflow.updated_by_id, self.nurse.pk)
        self.assertEqual(workflow.draft_payload['1']['penjamin'], 'UMUM')

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class ClearDpjpServiceTest(DpjpFixture):
    """``clear_dpjp`` tidak menghapus bukti dan menolak peran klinis."""

    def test_clear_is_idempotent_and_keeps_history(self):
        visit = self.make_visit(with_dpjp=True)
        self.assertEqual(clear_dpjp(visit, self.admin), 1)
        self.assertEqual(clear_dpjp(visit, self.admin), 0)
        self.assertEqual(PenugasanDpjpEpisode.objects.filter(visit=visit).count(), 1)
        visit.refresh_from_db()
        self.assertEqual(visit.dpjp, '')

    def test_nurse_cannot_clear(self):
        visit = self.make_visit(with_dpjp=True)
        with self.assertRaises(PermissionDenied):
            clear_dpjp(visit, self.nurse)
        self.assertEqual(self.active_rows(visit).count(), 1)
