"""Scoped Excel staff import routes (Task 8)."""

import io

import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import BatchImporPegawai, HcGrant, Pegawai


class StaffImportRouteTests(TestCase):
    def setUp(self):
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='RT-HC')
        self.manager = self._user('route-manager')
        self.reader = self._user('route-reader', manage=False)

    def _user(self, username, *, manage=True):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        # Role permissions are global per role; keep the role enabled and vary
        # each fixture user's authority with HcGrant below.
        config.can_manage_hc_employees = True
        config.save(update_fields=[
            'can_view_hc', 'can_manage_hc_employees', 'updated_at',
        ])
        HcGrant.objects.create(user=user, capability='can_view_hc', unit_kerja=self.root)
        if manage:
            HcGrant.objects.create(
                user=user, capability='can_manage_hc_employees', unit_kerja=self.root
            )
        return user

    def _workbook(self, rows):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Staf'
        ws.append([
            'nomor_pegawai', 'nama_lengkap', 'kategori', 'profesi', 'jabatan',
            'status', 'kategori_pegawai', 'unit_code', 'tanggal_mulai',
            'tanggal_selesai', 'alokasi_fte',
        ])
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def test_template_download_requires_manage_grant(self):
        self.client.force_login(self.reader)
        response = self.client.get(reverse('sdm:pegawai_import_template'))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:pegawai_import_template'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'spreadsheetml', response['Content-Type']
        )

    def test_upload_creates_no_canonical_rows_before_confirmation(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('sdm:pegawai_import'), {
            'workbook': self._workbook([[
                'RT-001', 'Fixture Import', 'NON_PPA', 'Administrasi', 'Staf',
                'AKTIF', 'TETAP', 'RT-HC', '2026-01-01', '', '1.00',
            ]]),
            'idempotency_key': 'route-1',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Pegawai.objects.filter(nomor_pegawai='RT-001').exists())

    def test_apply_is_post_only(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('sdm:pegawai_import'), {
            'workbook': self._workbook([[
                'RT-002', 'Fixture Apply', 'NON_PPA', 'Administrasi', 'Staf',
                'AKTIF', 'TETAP', 'RT-HC', '2026-01-01', '', '1.00',
            ]]),
            'idempotency_key': 'route-2',
        })
        batch_id = response['Location'].rstrip('/').split('/')[-1]
        get_response = self.client.get(
            reverse('sdm:pegawai_import_apply', kwargs={'batch_id': batch_id})
        )
        self.assertEqual(get_response.status_code, 405)

    def test_apply_rejects_hash_other_than_the_reviewed_preview(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('sdm:pegawai_import'), {
            'workbook': self._workbook([[
                'RT-HASH', 'Fixture Hash', 'NON_PPA', 'Administrasi', 'Staf',
                'AKTIF', 'TETAP', 'RT-HC', '2026-01-01', '', '1.00',
            ]]),
            'idempotency_key': 'route-hash',
        })
        batch_id = response['Location'].rstrip('/').split('/')[-1]
        batch = BatchImporPegawai.objects.get(pk=batch_id)
        apply_response = self.client.post(
            reverse('sdm:pegawai_import_apply', kwargs={'batch_id': batch_id}),
            {'preview_hash': '0' * 64},
        )
        self.assertRedirects(
            apply_response,
            reverse('sdm:pegawai_import_preview', kwargs={'batch_id': batch_id}),
        )
        batch.refresh_from_db()
        self.assertEqual(batch.state, 'PREVIEWED')
        self.assertFalse(Pegawai.objects.filter(nomor_pegawai='RT-HASH').exists())

    def test_foreign_batch_is_not_found(self):
        other = UnitKerja.objects.create(name='Unit Lain', code='RT-OTHER')
        outsider = self._user('route-outsider')
        HcGrant.objects.filter(user=outsider).update(unit_kerja=other)
        self.client.force_login(self.manager)
        response = self.client.post(reverse('sdm:pegawai_import'), {
            'workbook': self._workbook([[
                'RT-003', 'Fixture Foreign', 'NON_PPA', 'Administrasi', 'Staf',
                'AKTIF', 'TETAP', 'RT-HC', '2026-01-01', '', '1.00',
            ]]),
            'idempotency_key': 'route-3',
        })
        batch_id = response['Location'].rstrip('/').split('/')[-1]
        self.client.force_login(outsider)
        response = self.client.get(
            reverse('sdm:pegawai_import_preview', kwargs={'batch_id': batch_id})
        )
        self.assertEqual(response.status_code, 404)
