"""Stempel unit kerja pada routing rawat jalan (P1).

Masalah yang dikunci di sini: ``pendaftaran_route`` menyimpan **label**
poliklinik ke ``k.poliklinik`` sedangkan ``POLI_UNIT_CODE`` berkunci **kode**.
Membaca peta itu dari nilai yang sudah dikonversi tidak pernah cocok, sehingga
episode POLI-JANTUNG tidak punya unit — dan tanpa unit,
``require_rajal_jantung_episode`` menolak setiap langkah klinis serta
``assign_dpjp`` menolak menetapkan DPJP.

Bukti yang dituntut: kode unit yang benar-benar tersimpan, penugasan DPJP yang
benar-benar dibuat, dan penolakan yang tetap terjadi untuk poli lain. Tidak ada
tes yang hanya memeriksa keberadaan simbol.
"""
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien, PenugasanDpjpEpisode
from pasien.services.igd_assessment_workflow import require_rajal_jantung_episode
from pasien.services.poli_dpjp import eligible_dpjp_accounts

POLI_JANTUNG = 'POLI-JANTUNG'
POLI_PARU = 'POLI-PARU'

class RoutingFixture(TestCase):
    """Satu loket pendaftaran, satu akun dokter jantung, satu pasien."""

    @classmethod
    def setUpTestData(cls):
        cls.jantung = UnitKerja.objects.get_or_create(
            code=POLI_JANTUNG, defaults={'name': 'Poliklinik Jantung', 'level': 3},
        )[0]
        cls.paru = UnitKerja.objects.get_or_create(
            code=POLI_PARU, defaults={'name': 'Poliklinik Paru', 'level': 3},
        )[0]
        cls.desk = UnitKerja.objects.get_or_create(
            code='PENDAFTARAN-ADMISSION',
            defaults={'name': 'Pendaftaran & Admisi', 'level': 2},
        )[0]

        cls.officer = User.objects.create_user('loket_rajal', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=cls.officer, defaults={'role': 'ADMIN_RS', 'unit_kerja': cls.desk},
        )
        cls.doctor = User.objects.create_user('dr_jantung_routing', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=cls.doctor, defaults={
                'role': 'STAF_NAKES', 'profesi': 'DOKTER_SPESIALIS',
                'unit_kerja': cls.jantung, 'full_name': 'dr. Kirana Wulandari, Sp.JP',
            },
        )
        cls.patient = Pasien.objects.create(
            no_rm='RM-ROUTE-P1', nama_lengkap='Pasien Routing P1',
            tanggal_lahir='1962-01-09', jenis_kelamin='P',
        )

    def make_visit(self, no_kunjungan):
        return KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan=no_kunjungan,
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            poliklinik='Poli Umum', status='DAFTAR',
        )

    def route(self, visit, poli_code, **extra):
        self.client.force_login(self.officer)
        payload = {'tujuan': 'RAJAL', 'poliklinik': poli_code, 'flag_khusus': 'NORMAL'}
        payload.update(extra)
        return self.client.post(reverse('pasien:pendaftaran_route', args=[visit.pk]), payload)

class RajalUnitStampTest(RoutingFixture):
    """P1: unit diambil dari KODE poliklinik, bukan dari label tersimpan."""

    def test_routing_to_poli_jantung_stamps_unit_by_code(self):
        visit = self.make_visit('KJ-ROUTE-01')
        response = self.route(visit, 'POLI_JANTUNG')
        self.assertEqual(response.status_code, 302)

        visit.refresh_from_db()
        # Label tetap tersimpan sebagai label...
        self.assertEqual(visit.poliklinik, 'Poli Jantung & Pembuluh Darah')
        # ...tetapi unit diambil dari kode, bukan dari label itu.
        self.assertEqual(visit.unit_kerja_id, self.jantung.pk)
        self.assertEqual(visit.unit_kerja.code, POLI_JANTUNG)

    def test_routing_to_poli_jantung_then_dpjp_assignment_succeeds(self):
        visit = self.make_visit('KJ-ROUTE-02')
        self.route(visit, 'POLI_JANTUNG')
        visit.refresh_from_db()

        response = self.client.post(
            reverse('pasien:rajal_dpjp_simpan', args=[visit.pk]),
            {'dpjp_user': self.doctor.pk},
        )
        self.assertEqual(response.status_code, 302)

        rows = list(PenugasanDpjpEpisode.objects.filter(visit=visit, is_active=True))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].doctor_id, self.doctor.pk)
        self.assertEqual(rows[0].unit_id, self.jantung.pk)

        visit.refresh_from_db()
        self.assertEqual(visit.dpjp, 'dr. Kirana Wulandari, Sp.JP')
        # Guard tidak dilonggarkan: episode ini lolos justru karena unitnya benar.
        require_rajal_jantung_episode(visit)

    def test_visit_routed_to_another_poli_is_still_rejected(self):
        visit = self.make_visit('KJ-ROUTE-03')
        self.route(visit, 'POLI_PARU')
        visit.refresh_from_db()

        self.assertEqual(visit.unit_kerja.code, POLI_PARU)
        with self.assertRaises(PermissionDenied):
            require_rajal_jantung_episode(visit)

        response = self.client.post(
            reverse('pasien:rajal_dpjp_simpan', args=[visit.pk]),
            {'dpjp_user': self.doctor.pk},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PenugasanDpjpEpisode.objects.filter(visit=visit).exists())

    def test_poli_without_unit_code_leaves_unit_empty_without_crashing(self):
        """``POLI_UNIT_CODE['POLI_UMUM'] is None`` — jangan menebak unit lain."""
        visit = self.make_visit('KJ-ROUTE-04')
        response = self.route(visit, 'POLI_UMUM')
        self.assertEqual(response.status_code, 302)

        visit.refresh_from_db()
        self.assertEqual(visit.poliklinik, 'Poli Umum')
        self.assertIsNone(visit.unit_kerja_id)

    def test_unknown_poli_key_keeps_previous_behaviour(self):
        """Nilai bebas yang tidak ada di peta tetap tersimpan apa adanya."""
        visit = self.make_visit('KJ-ROUTE-05')
        response = self.route(visit, 'Poli Jantung & Pembuluh Darah')
        self.assertEqual(response.status_code, 302)

        visit.refresh_from_db()
        self.assertEqual(visit.poliklinik, 'Poli Jantung & Pembuluh Darah')
        self.assertIsNone(visit.unit_kerja_id)

class EligibleDoctorSelectorTest(RoutingFixture):
    """Pemilih DPJP hanya berisi akun dokter yang benar-benar ada."""

    def test_selector_contains_only_doctor_professions(self):
        accounts = list(eligible_dpjp_accounts())
        self.assertEqual([account.pk for account in accounts], [self.doctor.pk])
