"""RED tests for Task A6: versioned job descriptions."""

from django.test import TestCase
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import MasterUraianTugas, PenerimaanUraianTugas, Pegawai


class UraianTugasTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Poli Umum', code='POL-UM')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai', kategori='NON_PPA', profesi='Administrasi',
            status='AKTIF', data_origin='MANUAL',
        )

    def test_versioned_jobdesc_new_revision_requires_renewed_ack(self):
        jd = MasterUraianTugas.objects.create(
            position_code='DR-001', position_title='Dokter Residen',
            unit_kerja=self.unit, content='Versi 1', version=1, status='APPROVED',
            valid_from=self.today,
        )
        ack = PenerimaanUraianTugas.objects.create(
            employee=self.employee, uraian_tugas=jd,
            version_acknowledged=1, status='ACKNOWLEDGED',
        )
        self.assertEqual(ack.version_acknowledged, 1)

        # New revision
        jd2 = MasterUraianTugas.objects.create(
            position_code='DR-001', position_title='Dokter Residen',
            unit_kerja=self.unit, content='Versi 2', version=2, status='APPROVED',
            valid_from=self.today,
        )
        self.assertNotEqual(jd.pk, jd2.pk)
        self.assertTrue(MasterUraianTugas.objects.filter(version=2).exists())

    def test_ack_unique_per_employee_version(self):
        jd = MasterUraianTugas.objects.create(
            position_code='AP-001', position_title='Apoteker',
            unit_kerja=self.unit, content='x', version=1, status='APPROVED',
            valid_from=self.today,
        )
        PenerimaanUraianTugas.objects.create(
            employee=self.employee, uraian_tugas=jd,
            version_acknowledged=1,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PenerimaanUraianTugas.objects.create(
                employee=self.employee, uraian_tugas=jd,
                version_acknowledged=1,
            )
