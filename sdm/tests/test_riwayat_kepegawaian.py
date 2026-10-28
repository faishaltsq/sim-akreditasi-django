from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import resolve
from django.utils import timezone
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
    RiwayatKepegawaian,
)


class RiwayatKepegawaianCrudTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Riwayat', code='RW-TEST')
        self.user = get_user_model().objects.create_user(username='rw-admin')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.save(update_fields=['can_view_hc', 'can_manage_hc_employees', 'updated_at'])
        HcGrant.objects.create(
            user=self.user, capability='can_manage_hc_employees', unit_kerja=self.unit
        )
        HcGrant.objects.create(
            user=self.user, capability='can_view_hc', unit_kerja=self.unit
        )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Ahmad', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=400),
            alokasi_fte=Decimal('1.00'),
        )

    def test_routes_are_registered(self):
        self.assertEqual(
            resolve(f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/').view_name,
            'sdm:riwayat_create',
        )

    def test_profile_lists_every_history_row_newest_first(self):
        RiwayatKepegawaian.objects.create(
            pegawai=self.employee, kategori_pegawai='PKWT',
            tanggal_tmt=self.today - timedelta(days=800),
        )
        RiwayatKepegawaian.objects.create(
            pegawai=self.employee, kategori_pegawai='TETAP',
            tanggal_tmt=self.today - timedelta(days=10),
        )
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/')
        self.assertContains(response, 'Perjanjian Waktu Tertentu')
        self.assertContains(response, 'Tetap')
        rows = list(response.context['riwayat_list'])
        self.assertEqual(
            [row.kategori_pegawai for row in rows], ['TETAP', 'PKWT']
        )

    def test_create_records_audit_event(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/',
            {
                'kategori_pegawai': 'TETAP',
                'tanggal_tmt': (self.today - timedelta(days=30)).isoformat(),
                'jabatan_struktural': 'Kepala Ruang',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            RiwayatKepegawaian.objects.filter(pegawai=self.employee).count(), 1
        )
        event = PeristiwaSDM.objects.get(target_tipe='employee')
        self.assertEqual(event.jenis_peristiwa, 'riwayat_kepegawaian_created')

    def test_overlapping_open_ended_history_is_rejected(self):
        RiwayatKepegawaian.objects.create(
            pegawai=self.employee, kategori_pegawai='TETAP',
            tanggal_tmt=self.today - timedelta(days=300), tanggal_akhir=None,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/',
            {
                'kategori_pegawai': 'PKWT',
                'tanggal_tmt': self.today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            RiwayatKepegawaian.objects.filter(pegawai=self.employee).count(), 1
        )

    def test_last_remaining_history_cannot_be_deleted(self):
        history = RiwayatKepegawaian.objects.create(
            pegawai=self.employee, kategori_pegawai='TETAP',
            tanggal_tmt=self.today - timedelta(days=100),
        )
        self.client.force_login(self.user)
        response = self.client.post(
            f'/human-capital/pegawai/{self.employee.pk}/riwayat/{history.pk}/hapus/'
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(RiwayatKepegawaian.objects.filter(pk=history.pk).exists())

    def test_viewer_without_grant_is_denied(self):
        other = get_user_model().objects.create_user(username='rw-outsider')
        UserProfile.objects.create(user=other, role='STAF', unit_kerja=self.unit)
        self.client.force_login(other)
        response = self.client.get(
            f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/'
        )
        # Tanpa grant HC, pegawai di luar lingkup tidak terlihat: 404, bukan 403.
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/',
            {'kategori_pegawai': 'TETAP'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            RiwayatKepegawaian.objects.filter(pegawai=self.employee).exists()
        )
