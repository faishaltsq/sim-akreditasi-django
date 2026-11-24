"""Keadaan produksi hari ini: 0 akun dokter dari 29 pengguna (P3).

Tanpa tes, keadaan ini dapat bergeser diam-diam ke dua arah yang sama-sama
salah: pemilih DPJP tiba-tiba menawarkan akun non-dokter, atau pendaftaran
berhenti bekerja karena pemilihnya kosong. Yang dikunci di sini karena itu
tiga hal sekaligus:

* ``eligible_dpjp_accounts()`` kosong saat tidak ada akun berprofesi dokter,
  dan pemilihnya menyatakan sebabnya di layar;
* pendaftaran tetap berjalan tanpa DPJP — episode hanya belum punya DPJP
  berotoritas;
* langkah klinis tetap ditolak 403 tanpa DPJP aktif (ADR-11 butir 4).

Angka 29 sengaja dicerminkan sebagai 29 akun non-dokter di fixture: yang diuji
adalah **predikat profesinya**, bukan hitungan produksi.
"""
import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import (
    IgdAssessmentWorkflow, KunjunganPasien, Pasien, PenugasanDpjpEpisode,
)
from pasien.services.poli_dpjp import eligible_dpjp_accounts

from .tests_poli_workflow import TEST_STORAGES

POLI_JANTUNG = 'POLI-JANTUNG'
EMPTY_STATE_MESSAGE = 'Belum ada akun dokter terdaftar.'

#: Profesi non-dokter yang benar-benar ada di ``UserProfile.PROFESI_CHOICES``.
NON_DOCTOR_PROFESSIONS = (
    'PERAWAT', 'BIDAN', 'APOTEKER', 'TTK', 'ANALIS_LAB', 'RADIOGRAFER',
    'NUTRISIONIS', 'FISIOTERAPIS', 'PEREKAM_MEDIS', 'LAINNYA',
)

class NoDoctorAccountsFixture(TestCase):
    """29 pengguna aktif, tidak satu pun berprofesi dokter."""

    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.get_or_create(
            code=POLI_JANTUNG, defaults={'name': 'Poliklinik Jantung', 'level': 3},
        )[0]
        cls.desk = UnitKerja.objects.get_or_create(
            code='PENDAFTARAN-ADMISSION',
            defaults={'name': 'Pendaftaran & Admisi', 'level': 2},
        )[0]

        cls.admin = cls._account('admin_rs_nol_dokter', 'ADMIN_RS', '', cls.desk)
        cls.officer = cls._account('petugas_loket', 'STAF_NAKES', 'PEREKAM_MEDIS', cls.desk)
        cls.nurse = cls._account('perawat_poli', 'STAF_NAKES', 'PERAWAT', cls.unit)
        # 26 akun lagi supaya totalnya 29 — semuanya non-dokter.
        for index in range(26):
            profesi = NON_DOCTOR_PROFESSIONS[index % len(NON_DOCTOR_PROFESSIONS)]
            cls._account(f'staf_nol_dokter_{index:02d}', 'STAF_NAKES', profesi, cls.unit)

        cls.patient = Pasien.objects.create(
            no_rm='RM-NO-DOCTOR', nama_lengkap='Pasien Tanpa DPJP',
            tanggal_lahir='1958-08-08', jenis_kelamin='L',
        )

    @classmethod
    def _account(cls, username, role, profesi, unit):
        user = User.objects.create_user(username, password='fixture-only')
        UserProfile.objects.update_or_create(
            user=user, defaults={'role': role, 'profesi': profesi, 'unit_kerja': unit},
        )
        return user

    def make_visit(self, no_kunjungan):
        return KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan=no_kunjungan, jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), unit_kerja=self.unit,
            poliklinik='Poli Jantung & Pembuluh Darah', status='DAFTAR',
        )

class EmptyDoctorDirectoryTest(NoDoctorAccountsFixture):
    """Pemilih DPJP kosong dan sebabnya dinyatakan di layar."""

    def test_production_like_directory_has_zero_eligible_doctor_accounts(self):
        # 29 akun, seluruhnya non-dokter — bentuk direktori produksi hari ini.
        self.assertEqual(
            User.objects.filter(username__startswith='staf_nol_dokter_').count(), 26)
        self.assertEqual(
            User.objects.filter(
                username__in=('admin_rs_nol_dokter', 'petugas_loket', 'perawat_poli'),
            ).count(), 3)
        self.assertEqual(eligible_dpjp_accounts().count(), 0)
        # Kosong karena profesinya memang non-dokter, bukan karena profil hilang.
        self.assertFalse(
            UserProfile.objects.filter(
                profesi__in=('DOKTER_UMUM', 'DOKTER_SPESIALIS', 'DOKTER_GIGI'),
            ).exists()
        )

    def test_rajal_dashboard_renders_empty_state_message(self):
        self.make_visit('KJ-NO-DOCTOR-01')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('pasien:rajal_dashboard'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(EMPTY_STATE_MESSAGE, body)
        # Tidak ada akun yang ditawarkan sebagai opsi.
        for account in (self.admin, self.nurse, self.officer):
            self.assertNotIn(f'<option value="{account.pk}">', body)

    def test_registration_form_renders_empty_state_message(self):
        self.client.force_login(self.officer)
        response = self.client.get(reverse('pasien:kunjungan_baru'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(EMPTY_STATE_MESSAGE, response.content.decode())

    def test_registration_still_works_without_any_doctor_account(self):
        self.client.force_login(self.officer)
        response = self.client.post(reverse('pasien:kunjungan_baru'), {
            'pasien_id': self.patient.pk,
            'jenis_kunjungan': 'RAJAL',
            'tanggal_masuk': timezone.now().strftime('%Y-%m-%dT%H:%M:%S%z'),
            'poliklinik': 'POLI_JANTUNG',
            'penjamin': 'UMUM',
            'no_kunjungan': 'KJ-NO-DOCTOR-02',
        })
        self.assertEqual(response.status_code, 302)

        visit = KunjunganPasien.objects.get(no_kunjungan='KJ-NO-DOCTOR-02')
        self.assertEqual(visit.status, 'DAFTAR')
        # Registrasi berhasil, tetapi tidak ada penugasan yang dikarang.
        self.assertEqual(visit.dpjp, '')
        self.assertFalse(PenugasanDpjpEpisode.objects.filter(visit=visit).exists())

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class NoDpjpBlocksClinicalStepTest(NoDoctorAccountsFixture):
    """ADR-11 butir 4: tanpa DPJP aktif, langkah klinis ditolak 403."""

    def draft(self, visit, step, fields, version=0):
        self.client.force_login(self.nurse)
        return self.client.post(
            reverse('pasien:poli_workflow_draft', args=[visit.pk, step]),
            data=json.dumps({'fields': fields, 'version': version}),
            content_type='application/json',
        )

    def test_clinical_step_write_returns_403_without_active_dpjp(self):
        visit = self.make_visit('KJ-NO-DOCTOR-03')
        response = self.draft(visit, 1, {'penjamin': 'UMUM'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=visit).exists())

    def test_dpjp_assignment_endpoint_cannot_pick_a_non_doctor_account(self):
        visit = self.make_visit('KJ-NO-DOCTOR-04')
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('pasien:rajal_dpjp_simpan', args=[visit.pk]),
            {'dpjp_user': self.nurse.pk},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PenugasanDpjpEpisode.objects.filter(visit=visit).exists())
