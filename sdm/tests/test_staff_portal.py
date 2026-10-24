"""RED tests for Task A9: own-profile staff portal."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, LayananMandiri, Pegawai, PenempatanPegawai


class StaffPortalTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Poli Umum', code='POL-UM')
        self.other = UnitKerja.objects.create(name='Unit Lain', code='UNIT-2')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Sendiri', kategori='NON_PPA', profesi='Administrasi',
            status='AKTIF', data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=1.00,
        )
        self.user = get_user_model().objects.create_user(username='own-staff')
        UserProfile.objects.create(user=self.user, role='STAF_NAKES', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('STAF_NAKES')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(user=self.user, capability='can_view_hc', unit_kerja=self.unit)
        self.employee.akun = self.user
        self.employee.save(update_fields=['akun', 'updated_at'])

    def test_portal_requires_linked_employee(self):
        stranger = get_user_model().objects.create_user(username='no-employee')
        UserProfile.objects.create(user=stranger, role='STAF_NAKES', unit_kerja=self.unit)
        HcGrant.objects.create(user=stranger, capability='can_view_hc', unit_kerja=self.unit)
        self.client.force_login(stranger)

        response = self.client.get('/human-capital/saya/')

        self.assertEqual(response.status_code, 403)

    def test_portal_renders_own_profile(self):
        self.client.force_login(self.user)

        response = self.client.get('/human-capital/saya/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Portal Mandiri')
        self.assertContains(response, self.employee.nama_lengkap)

    def test_portal_does_not_show_foreign_employee(self):
        foreign = Pegawai.objects.create(
            nama_lengkap='Pegawai Asing', kategori='NON_PPA', status='AKTIF',
            data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=foreign, unit_kerja=self.other,
            tanggal_mulai=self.today, alokasi_fte=1.00,
        )
        self.client.force_login(self.user)

        response = self.client.get('/human-capital/saya/')

        self.assertNotContains(response, 'Pegawai Asing')

    def test_portal_submit_own_request(self):
        self.client.force_login(self.user)

        response = self.client.post('/human-capital/saya/ajukan/', {
            'kind': 'PROFILE_CORRECTION',
            'keterangan': 'Mohon perbarui nomor telepon.',
            'idempotency_key': 'portal-001',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            LayananMandiri.objects.filter(
                employee=self.employee, kind='PROFILE_CORRECTION', state='SUBMITTED'
            ).exists()
        )

    def test_portal_cancel_own_request(self):
        self.client.force_login(self.user)
        self.client.post('/human-capital/saya/ajukan/', {
            'kind': 'TRAINING_REQUEST', 'keterangan': 'BHD',
        })
        request_obj = LayananMandiri.objects.get(employee=self.employee)

        response = self.client.post(
            f'/human-capital/saya/ajukan/{request_obj.pk}/batal/'
        )

        self.assertEqual(response.status_code, 302)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.state, 'CANCELLED')

    def test_portal_cannot_cancel_foreign_request(self):
        foreign = Pegawai.objects.create(
            nama_lengkap='Pegawai Asing 2', kategori='NON_PPA', status='AKTIF',
            data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=foreign, unit_kerja=self.other,
            tanggal_mulai=self.today, alokasi_fte=1.00,
        )
        foreign_request = LayananMandiri.objects.create(
            employee=foreign, kind='LEAVE_REQUEST', state='SUBMITTED',
        )
        self.client.force_login(self.user)

        response = self.client.post(
            f'/human-capital/saya/ajukan/{foreign_request.pk}/batal/'
        )

        self.assertEqual(response.status_code, 404)
        foreign_request.refresh_from_db()
        self.assertEqual(foreign_request.state, 'SUBMITTED')
