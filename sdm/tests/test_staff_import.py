"""RED tests for Task B5: staff Excel import preview/apply."""

import io

import openpyxl
from django.test import TestCase

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import BatchImporPegawai, HcGrant, Pegawai, PenempatanPegawai
from sdm.services.impor_pegawai import (
    apply_staff_import,
    preview_staff_import,
)


class StaffImportTests(TestCase):
    def setUp(self):
        from django.utils import timezone

        self.today = timezone.localdate()
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='DIR-HC')
        self.manager = self._user('impor-manager')

    def _user(self, username):
        from django.contrib.auth import get_user_model as _gm
        user = _gm().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.save(update_fields=['can_view_hc', 'can_manage_hc_employees', 'updated_at'])
        HcGrant.objects.create(user=user, capability='can_view_hc', unit_kerja=self.root)
        HcGrant.objects.create(user=user, capability='can_manage_hc_employees', unit_kerja=self.root)
        return user

    def _workbook(self, rows):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Staf'
        ws.append([
            'nomor_pegawai', 'nama_lengkap', 'kategori', 'profesi', 'jabatan', 'status',
            'kategori_pegawai', 'unit_code', 'tanggal_mulai', 'tanggal_selesai', 'alokasi_fte',
        ])
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def test_preview_creates_zero_canonical_rows(self):
        before = (Pegawai.objects.count(), PenempatanPegawai.objects.count())
        batch = preview_staff_import(
            actor=self.manager,
            workbook=self._workbook([['IMP-001', 'Orang Baru', 'NON_PPA', 'Administrasi', 'Staf', 'AKTIF', 'TETAP', 'DIR-HC', str(self.today), '', '1.00']]),
            idempotency_key='preview-001',
        )
        self.assertEqual(batch.state, 'PREVIEWED')
        self.assertEqual(batch.row_create, 1)
        self.assertEqual(batch.row_blocked, 0)
        self.assertEqual((Pegawai.objects.count(), PenempatanPegawai.objects.count()), before)

    def test_apply_then_repeat_apply_returns_same_batch(self):
        batch = preview_staff_import(
            actor=self.manager,
            workbook=self._workbook([['IMP-002', 'Orang Baru 2', 'NON_PPA', 'Administrasi', 'Staf', 'AKTIF', 'TETAP', 'DIR-HC', str(self.today), '', '1.00']]),
            idempotency_key='preview-002',
        )
        applied = apply_staff_import(actor=self.manager, batch_id=batch.pk, preview_hash=batch.preview_hash)
        again = apply_staff_import(actor=self.manager, batch_id=batch.pk, preview_hash=batch.preview_hash)
        self.assertEqual(applied.pk, again.pk)
        self.assertEqual(applied.state, 'APPLIED')
        self.assertTrue(Pegawai.objects.filter(nomor_pegawai='IMP-002').exists())

    def test_blocked_row_not_applied(self):
        batch = preview_staff_import(
            actor=self.manager,
            workbook=self._workbook([['', 'Tanpa NIP', 'NON_PPA', '', '', 'AKTIF', 'TETAP', 'DIR-HC', str(self.today), '', '1.00']]),
            idempotency_key='preview-003',
        )
        self.assertEqual(batch.state, 'BLOCKED')
        with self.assertRaises(Exception):
            apply_staff_import(actor=self.manager, batch_id=batch.pk, preview_hash=batch.preview_hash)

    def test_preview_blocks_unit_outside_operator_scope(self):
        foreign = UnitKerja.objects.create(name='Foreign unit', code='IMPORT-FOREIGN')
        batch = preview_staff_import(
            actor=self.manager,
            workbook=self._workbook([[
                'FOREIGN-001', 'Fixture', 'NON_PPA', 'Administrasi', 'Staf',
                'AKTIF', 'TETAP', foreign.code, str(self.today), '', '1.00',
            ]]),
            idempotency_key='foreign-preview',
        )
        self.assertEqual(batch.state, 'BLOCKED')
        self.assertEqual(batch.row_create, 0)
        self.assertEqual(batch.row_blocked, 1)
        self.assertFalse(Pegawai.objects.filter(nomor_pegawai='FOREIGN-001').exists())

    def test_apply_persists_employment_history_from_basic_template(self):
        batch = preview_staff_import(
            actor=self.manager,
            workbook=self._workbook([[
                'HISTORY-001', 'Fixture History', 'NON_PPA', 'Administrasi', 'Staf',
                'AKTIF', 'PKWT', self.root.code, str(self.today), '', '0.75',
            ]]),
            idempotency_key='history-preview',
        )
        apply_staff_import(
            actor=self.manager, batch_id=batch.pk, preview_hash=batch.preview_hash
        )
        employee = Pegawai.objects.get(nomor_pegawai='HISTORY-001')
        history = employee.riwayat_kepegawaian.get()
        self.assertEqual(history.kategori_pegawai, 'PKWT')
        self.assertEqual(history.tanggal_tmt, self.today)
