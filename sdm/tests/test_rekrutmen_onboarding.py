from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from sdm.models import (
    AktivitasOrientasi, BerkasPelamar, Lamaran, Pegawai, Pelamar,
    ProgramOrientasi, UrutanNomorPegawai,
)
from sdm.services.rekrutmen import hire_application
from sdm.storage_backend import StoredPrivateObject
from sdm.tests.test_rekrutmen import LevelTwoBase


class OnboardingTests(LevelTwoBase):
    def setUp(self):
        super().setUp()
        self.candidate = Pelamar.objects.create(
            nama_lengkap='Pelamar Uji', email='candidate@example.com',
            telepon='12345', tanggal_lahir=date(2000, 1, 2),
            pendidikan_terakhir='S1',
        )
        self.application = Lamaran.objects.create(
            lowongan=self.lowongan, pelamar=self.candidate,
            nama_pelamar=self.candidate.nama_lengkap, status='DITERIMA',
        )

    def configure_numbering(self):
        return UrutanNomorPegawai.objects.create(
            scope='rekrutmen', period_start=date(2000, 1, 1),
            format_pattern='EMP-{year}-{counter:04d}',
        )

    def test_missing_numbering_fails_without_creating_employee(self):
        with self.assertRaises(ValidationError):
            hire_application(self.application, actor=self.recruiter, idempotency_key='hire')
        self.assertFalse(Pegawai.objects.filter(nama_lengkap='Pelamar Uji').exists())

    def test_stale_accepted_application_is_rechecked(self):
        self.configure_numbering()
        Lamaran.objects.filter(pk=self.application.pk).update(status='DITOLAK')
        with self.assertRaises(ValidationError):
            hire_application(self.application, actor=self.recruiter, idempotency_key='hire')
        self.assertFalse(Pegawai.objects.filter(nama_lengkap='Pelamar Uji').exists())

    def test_counter_creates_distinct_numbers_for_distinct_hires(self):
        self.configure_numbering()
        program = ProgramOrientasi.objects.create(nama='Umum', jenis='UMUM')
        AktivitasOrientasi.objects.create(program=program, nama='Pengenalan')
        other = Lamaran.objects.create(
            lowongan=self.lowongan, nama_pelamar='Pelamar Kedua', status='DITERIMA',
        )
        first = hire_application(self.application, actor=self.recruiter, idempotency_key='hire-1')
        second = hire_application(other, actor=self.recruiter, idempotency_key='hire-2')
        self.assertNotEqual(first.nomor_pegawai, second.nomor_pegawai)

    def test_invalid_number_pattern_fails_without_employee(self):
        sequence = self.configure_numbering()
        sequence.format_pattern = 'EMP-{year}'
        sequence.save(update_fields=['format_pattern'])
        with self.assertRaises(ValidationError):
            hire_application(self.application, actor=self.recruiter, idempotency_key='hire')
        self.assertFalse(Pegawai.objects.filter(nama_lengkap='Pelamar Uji').exists())

    def test_hire_transfers_private_file_and_is_idempotent(self):
        self.configure_numbering()
        program = ProgramOrientasi.objects.create(nama='Umum', jenis='UMUM')
        AktivitasOrientasi.objects.create(program=program, nama='Pengenalan')
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            BerkasPelamar.objects.create(
                lamaran=self.application, jenis='IJAZAH',
                berkas=SimpleUploadedFile('ijazah.pdf', b'%PDF-test', content_type='application/pdf'),
            )
            with patch('sdm.services.rekrutmen.get_private_storage') as storage:
                storage.return_value.upload.return_value = StoredPrivateObject(
                    f'personnel/{uuid4()}/{uuid4()}.pdf', 'a' * 64, 9, 'application/pdf',
                )
                first = hire_application(self.application, actor=self.recruiter, idempotency_key='hire')
                second = hire_application(self.application, actor=self.recruiter, idempotency_key='hire')
            self.assertEqual(first.pk, second.pk)
            self.assertEqual(first.documents.count(), 1)
            self.assertEqual(first.documents.get().jenis_berkas, 'IJAZAH')
            self.assertEqual(first.documents.get().versions.count(), 1)
            self.assertEqual(first.orientations.count(), 1)
            self.assertTrue(first.nomor_pegawai.startswith('EMP-'))
            self.assertEqual(first.akun.email, self.candidate.email)
            self.assertFalse(first.akun.has_usable_password())
            self.assertEqual(first.profil_pribadi.tanggal_lahir, self.candidate.tanggal_lahir)
            self.assertEqual(first.profil_pribadi.telepon, self.candidate.telepon)
            self.assertEqual(storage.return_value.upload.call_count, 1)

    def test_failed_orientation_rolls_back_and_cleans_new_copy(self):
        self.configure_numbering()
        ProgramOrientasi.objects.create(nama='Kosong', jenis='UMUM')
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            source = BerkasPelamar.objects.create(
                lamaran=self.application, jenis='IJAZAH',
                berkas=SimpleUploadedFile('ijazah.pdf', b'%PDF-test', content_type='application/pdf'),
            )
            with patch('sdm.services.rekrutmen.get_private_storage') as storage:
                storage.return_value.upload.return_value = StoredPrivateObject(
                    f'personnel/{uuid4()}/{uuid4()}.pdf', 'a' * 64, 9, 'application/pdf',
                )
                with self.assertRaises(ValidationError):
                    hire_application(self.application, actor=self.recruiter, idempotency_key='hire')
                storage.return_value.delete.assert_called_once()
            self.assertTrue(source.berkas.storage.exists(source.berkas.name))
        self.assertFalse(Pegawai.objects.filter(nama_lengkap='Pelamar Uji').exists())
        self.application.refresh_from_db()
        self.assertIsNone(self.application.employee_id)
