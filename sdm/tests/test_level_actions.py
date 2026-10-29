from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AktivitasOrientasi,
    HcGrant,
    InsidenK3Pegawai,
    Lamaran,
    Lowongan,
    Pegawai,
    PenempatanPegawai,
    IzinProfesiPegawai,
    PengajuanKredensial,
    ProgramOrientasi,
)


class CreateFlowBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Aksi', code='HC-ACT')
        self.user = self._user('action-user')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        for field in (
            'can_view_hc', 'can_manage_hc_recruitment', 'can_review_hc_credentials',
            'can_manage_hc_orientation', 'can_manage_hc_appraisals',
            'can_manage_hc_training', 'can_view_hc_analytics', 'can_export_hc',
            'can_plan_hc_workforce',
        ):
            setattr(config, field, True)
        config.save()
        for capability in (
            'can_view_hc', 'can_manage_hc_recruitment', 'can_review_hc_credentials',
            'can_manage_hc_orientation', 'can_manage_hc_appraisals',
            'can_manage_hc_training', 'can_view_hc_analytics', 'can_export_hc',
            'can_plan_hc_workforce', 'hc_health_write',
        ):
            HcGrant.objects.create(
                user=self.user, capability=capability, unit_kerja=self.unit
            )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Aksi', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )
        # STR & SIP aktif: pengajuan AWAL/REKREDENSIAL mensyaratkan legalitas
        # yang berlaku, jadi fixture harus menyediakannya.
        IzinProfesiPegawai.objects.create(
            pegawai=self.employee, subtype='STR', nomor_izin='STR-TEST-001',
            profesi='Perawat', pemberi_izin='Kemenkes', validity_mode='DATED',
            tanggal_terbit=self.today,
            tanggal_berakhir=self.today + timedelta(days=365),
            is_local_rs=True,
        )
        IzinProfesiPegawai.objects.create(
            pegawai=self.employee, subtype='SIP', nomor_izin='SIP-TEST-001',
            profesi='Perawat', pemberi_izin='Dinkes', validity_mode='DATED',
            tanggal_terbit=self.today,
            tanggal_berakhir=self.today + timedelta(days=365),
            is_local_rs=True,
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        return user


class RecruitmentCreateTests(CreateFlowBase):
    def test_create_vacancy_then_add_application(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('sdm:rekrutmen_create'), {
            'unit_kerja': self.unit.pk,
            'profesi': 'Perawat',
            'judul': 'Perawat IGD',
            'jumlah_kebutuhan': '2',
            'status': 'DIBUKA',
            'jalur': 'EKSTERNAL',
        })

        self.assertEqual(response.status_code, 302)
        vacancy = Lowongan.objects.get(judul='Perawat IGD')
        self.assertEqual(vacancy.created_by, self.user)

        response = self.client.post(
            reverse('sdm:rekrutmen_add_application', kwargs={'vacancy_id': vacancy.pk}),
            {'nama_pelamar': 'Pelamar Baru', 'kontak': '0812'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Lamaran.objects.filter(lowongan=vacancy, nama_pelamar='Pelamar Baru').exists()
        )

    def test_create_vacancy_rejects_foreign_unit(self):
        other = UnitKerja.objects.create(name='Unit Asing', code='HC-ACT-2')
        self.client.force_login(self.user)

        response = self.client.post(reverse('sdm:rekrutmen_create'), {
            'unit_kerja': other.pk,
            'profesi': 'Perawat',
            'judul': 'Tidak Boleh',
            'jumlah_kebutuhan': '1',
            'status': 'DIBUKA',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Lowongan.objects.filter(judul='Tidak Boleh').exists())


class CredentialCreateTests(CreateFlowBase):
    def test_create_request_then_add_privilege(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('sdm:kredensial_create'), {
            'employee': self.employee.pk,
            'unit_kerja': self.unit.pk,
            'jenis': 'AWAL',
        })

        self.assertEqual(response.status_code, 302)
        credential_request = PengajuanKredensial.objects.get(employee=self.employee)

        response = self.client.post(
            reverse('sdm:kredensial_add_privilege', kwargs={'request_id': credential_request.pk}),
            {'kewenangan': 'Asuhan dasar', 'catatan': ''},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(credential_request.privileges.count(), 1)

    def test_psv_without_verified_document_is_refused(self):
        credential_request = PengajuanKredensial.objects.create(
            employee=self.employee, unit_kerja=self.unit, submitted_by=self.user
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sdm:kredensial_psv', kwargs={'request_id': credential_request.pk}),
            {'issuer': 'Kemenkes', 'reference': 'X', 'method': 'Situs', 'outcome': 'VALID'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.employee.psv_records.count(), 0)


class OrientationCreateTests(CreateFlowBase):
    def test_create_program_then_assign_and_sign_off(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('sdm:orientasi_create'), {
            'action': 'program',
            'nama': 'Orientasi IGD',
            'unit_kerja': self.unit.pk,
            'berlaku_hari': '14',
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        program = ProgramOrientasi.objects.get(nama='Orientasi IGD')
        AktivitasOrientasi.objects.create(program=program, nama='Alur IGD', wajib=True)

        response = self.client.post(reverse('sdm:orientasi_create'), {
            'action': 'assign',
            'employee': self.employee.pk,
            'program': program.pk,
        })
        self.assertEqual(response.status_code, 302)
        assignment = self.employee.orientations.get()
        completion = assignment.completions.get()

        response = self.client.post(
            reverse('sdm:orientasi_complete', kwargs={'completion_id': completion.pk}),
            {'notes': 'ok'},
        )
        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'SELESAI')


class MalformedInputTests(CreateFlowBase):
    def test_k3_report_rejects_non_numeric_unit_without_500(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('sdm:k3_report'), {
            'unit': 'abc', 'employee': 'x',
            'kategori': 'LAINNYA', 'deskripsi': 'deskripsi uji',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(InsidenK3Pegawai.objects.count(), 0)

    def test_k3_report_rejects_blank_unit(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('sdm:k3_report'), {
            'unit': '', 'employee': '',
            'kategori': 'LAINNYA', 'deskripsi': 'deskripsi uji',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(InsidenK3Pegawai.objects.count(), 0)


class LowonganKriteriaTests(CreateFlowBase):
    """Fase C1: kriteria lowongan & jendela pendaftaran."""

    def test_tanggal_tutup_sebelum_buka_ditolak(self):
        from sdm.forms.level2_5 import LowonganForm
        form = LowonganForm(data={
            'unit_kerja': str(self.unit.pk), 'profesi': 'Perawat',
            'judul': 'Terbalik', 'jumlah_kebutuhan': '1', 'status': 'DIBUKA',
            'jalur': 'EKSTERNAL',
            'tanggal_buka': '2026-11-01', 'tanggal_tutup': '2026-10-01',
        }, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('tanggal_tutup', form.errors)

    def test_ipk_di_luar_rentang_ditolak(self):
        from sdm.forms.level2_5 import LowonganForm
        form = LowonganForm(data={
            'unit_kerja': str(self.unit.pk), 'profesi': 'Perawat',
            'judul': 'IPK Salah', 'jumlah_kebutuhan': '1', 'status': 'DRAFT',
            'jalur': 'INTERNAL', 'ipk_minimal': '5.00',
        }, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('ipk_minimal', form.errors)

    def test_pendaftaran_terbuka_hanya_dalam_jendela_dan_status_dibuka(self):
        today = timezone.localdate()
        vacancy = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Perawat IGD',
            jumlah_kebutuhan=2, status='DIBUKA', jalur='EKSTERNAL',
            tanggal_buka=today - timedelta(days=1),
            tanggal_tutup=today + timedelta(days=30),
        )
        self.assertTrue(vacancy.is_pendaftaran_terbuka)

        vacancy.status = 'DITUTUP'
        self.assertFalse(vacancy.is_pendaftaran_terbuka)

        vacancy.status = 'DIBUKA'
        vacancy.tanggal_buka = today + timedelta(days=5)
        self.assertFalse(vacancy.is_pendaftaran_terbuka)

    def test_status_draft_tidak_membuka_pendaftaran(self):
        today = timezone.localdate()
        vacancy = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Draf Perawat',
            jumlah_kebutuhan=1, status='DRAFT', jalur='INTERNAL',
            tanggal_buka=today, tanggal_tutup=today + timedelta(days=10),
        )
        self.assertFalse(vacancy.is_pendaftaran_terbuka)
