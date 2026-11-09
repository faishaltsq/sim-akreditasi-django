"""Test model Logbook Harian Non-Medis (semua unit kerja)."""

from datetime import date

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from akreditasi.models import UnitKerja
from sdm.models import Pegawai


def buat_unit(kode, nama, tipe='BAGIAN', parent=None):
    return UnitKerja.objects.create(code=kode, name=nama, level=2, tipe_unit=tipe, parent=parent)


def buat_pegawai(nama, unit=None):
    p = Pegawai.objects.create(
        nama_lengkap=nama, kategori='NON_PPA', profesi='Administrasi',
    )
    return p


class LogbookNonMedisModelTest(TestCase):

    def setUp(self):
        self.unit = buat_unit('PENDAFTARAN', 'Unit Pendaftaran', tipe='BAGIAN')
        self.pegawai = buat_pegawai('Budi Santoso', unit=self.unit)
        self.user = User.objects.create_user('log_nm', password='x')

    def test_buat_entry_minimal(self):
        from akreditasi.logbook_nonmedis_models import LogbookNonMedis

        e = LogbookNonMedis.objects.create(
            unit=self.unit, pegawai=self.pegawai, pelaksana_nama='Budi Santoso',
            tanggal=date(2026, 11, 9), dibuat_oleh=self.user,
        )
        self.assertEqual(e.status, 'DRAF')
        self.assertEqual(str(e.unit), str(self.unit))
        self.assertEqual(e.shift, '')

    def test_unik_per_unit_pegawai_tanggal(self):
        from akreditasi.logbook_nonmedis_models import LogbookNonMedis

        LogbookNonMedis.objects.create(
            unit=self.unit, pegawai=self.pegawai, tanggal=date(2026, 11, 9))
        with self.assertRaises(IntegrityError):
            LogbookNonMedis.objects.create(
                unit=self.unit, pegawai=self.pegawai, tanggal=date(2026, 11, 9))

    def test_ensure_checklist_idempoten(self):
        from akreditasi.logbook_nonmedis_models import LogbookNonMedis

        e = LogbookNonMedis.objects.create(
            unit=self.unit, pegawai=self.pegawai, tanggal=date(2026, 11, 9))
        dibuat = e.ensure_checklist()
        self.assertGreaterEqual(dibuat, 3)
        self.assertEqual(e.checklist.count(), dibuat)
        # idempoten — pemanggilan ulang tidak menduplikasi
        self.assertEqual(e.ensure_checklist(), 0)
        self.assertEqual(e.checklist.count(), dibuat)

    def test_checklist_unik_per_kunci(self):
        from akreditasi.logbook_nonmedis_models import ChecklistNonMedis, LogbookNonMedis

        e = LogbookNonMedis.objects.create(
            unit=self.unit, pegawai=self.pegawai, tanggal=date(2026, 11, 9))
        e.ensure_checklist()
        kunci = e.checklist.first().kunci
        with self.assertRaises(IntegrityError):
            ChecklistNonMedis.objects.create(logbook=e, kunci=kunci, parameter='X')

    def test_bukti_path_mengandung_id(self):
        from akreditasi.logbook_nonmedis_models import _path_bukti_nonmedis, BuktiNonMedis, LogbookNonMedis

        e = LogbookNonMedis.objects.create(
            unit=self.unit, pegawai=self.pegawai, tanggal=date(2026, 11, 9))
        b = BuktiNonMedis(logbook=e, judul='Laporan')
        b.logbook_id = e.pk
        path = _path_bukti_nonmedis(b, 'dummy.pdf')
        self.assertEqual(path, f'logbook-nonmedis/{e.pk}/dummy.pdf')
