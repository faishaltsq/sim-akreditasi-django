"""RED tests for Task B1: staff census provenance and reconciliation."""

import io

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from akreditasi.models import UnitKerja
from sdm.models import Pegawai, PenempatanPegawai


class ReconcileHcStaffTests(TestCase):
    def setUp(self):
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='DIR-HC')

        self.seeded = Pegawai.objects.create(
            nama_lengkap='Pegawai Seeder',
            nomor_pegawai='HC-ROOT-STAF_NAKES-001',
            kategori='PPA',
            profesi='Perawat',
            status='AKTIF',
            data_origin='UNCLASSIFIED',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.seeded,
            unit_kerja=self.root,
            tanggal_mulai='2026-10-23',
            alokasi_fte=1.00,
        )

        self.accountless = Pegawai.objects.create(
            nama_lengkap='Pegawai Tanpa Akun',
            nomor_pegawai='HC-ROOT-NON_PPA-002',
            kategori='NON_PPA',
            profesi='Administrasi',
            status='AKTIF',
            data_origin='UNCLASSIFIED',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.accountless,
            unit_kerja=self.root,
            tanggal_mulai='2026-10-23',
            alokasi_fte=1.00,
        )

        self.dup = Pegawai.objects.create(
            nama_lengkap='Duplikat NIP',
            nomor_pegawai='DUP-001',
            kategori='NON_PPA',
            profesi='Administrasi',
            status='AKTIF',
            data_origin='UNCLASSIFIED',
        )

    def test_dry_run_preserves_counts_and_rows(self):
        before = (Pegawai.objects.count(), PenempatanPegawai.objects.count())
        call_command('reconcile_hc_staff', reviewed_artifact='nonexistent.json')
        self.assertEqual(before, (Pegawai.objects.count(), PenempatanPegawai.objects.count()))

    def test_dry_run_reports_unclassified_rows(self):
        out = io.StringIO()
        call_command('reconcile_hc_staff', reviewed_artifact='nonexistent.json', stdout=out)
        self.assertIn('unclassified=3', out.getvalue())

    def test_apply_without_readable_artifact_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command('reconcile_hc_staff', reviewed_artifact='nonexistent.json', apply=True)

    def test_apply_without_artifact_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command('reconcile_hc_staff', apply=True)
