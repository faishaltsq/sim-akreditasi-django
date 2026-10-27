"""Intake attachment staging and photo normalization (Task 4)."""

import io
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DrafInputPegawai, DokumenPegawai, HcGrant, LampiranDrafPegawai,
    PeristiwaSDM,
)
from sdm.services.intake import (
    finalize_staff_intake, normalize_profile_photo, stage_intake_attachment,
)
from sdm.storage_backend import PrivateStorageError, SupabasePrivateStorage
from sdm.tests.test_storage_backend import FakeResponse, FakeSession, JPEG, PDF

MAX = 5_242_880


def _jpeg_bytes(width=400, height=500):
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), (200, 180, 160)).save(buffer, format='JPEG')
    return buffer.getvalue()


class IntakeUploadTests(TestCase):
    def setUp(self):
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='UP-HC')
        self.manager = self._user('upload-manager')
        self.draft = DrafInputPegawai.objects.create(
            owner=self.manager, current_step=5, version=2,
            expires_at=timezone.now() + timedelta(days=1),
            draft_data={
                '1': {'nama_depan': 'Budi'},
                '2': {'unit_kerja': self.root.pk},
            },
        )
        self.session = FakeSession(FakeResponse(200))
        self.storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co', api_key='service-key',
            bucket='hc-private', session=self.session,
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.can_manage_hc_documents = True
        config.save(update_fields=[
            'can_view_hc', 'can_manage_hc_employees',
            'can_manage_hc_documents', 'updated_at',
        ])
        for capability in (
            'can_view_hc', 'can_manage_hc_employees', 'can_manage_hc_documents',
        ):
            HcGrant.objects.create(
                user=user, capability=capability, unit_kerja=self.root
            )
        return user

    def test_stage_persists_object_and_metadata(self):
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            attachment = stage_intake_attachment(
                actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                file_obj=SimpleUploadedFile('ktp.pdf', PDF, 'application/pdf'),
                artifact_kind='KTP',
            )
        self.assertEqual(attachment.state, 'STAGED')
        self.assertEqual(attachment.size_bytes, len(PDF))
        self.assertTrue(attachment.storage_key.startswith('personnel/'))

    def test_second_staged_ktp_is_refused_before_upload(self):
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            stage_intake_attachment(
                actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                file_obj=SimpleUploadedFile('ktp.pdf', PDF, 'application/pdf'),
                artifact_kind='KTP',
            )
            calls_after_first = len(self.session.calls)
            with self.assertRaises(ValidationError):
                stage_intake_attachment(
                    actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                    file_obj=SimpleUploadedFile('ktp-baru.pdf', PDF, 'application/pdf'),
                    artifact_kind='KTP',
                )
        self.assertEqual(len(self.session.calls), calls_after_first)
        self.assertEqual(
            LampiranDrafPegawai.objects.filter(
                draft=self.draft, artifact_kind='KTP', state='STAGED'
            ).count(),
            1,
        )

    def test_oversize_file_is_refused_before_upload(self):
        big = SimpleUploadedFile('ktp.pdf', b'%PDF-' + b'x' * MAX, 'application/pdf')
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            with self.assertRaises(ValidationError):
                stage_intake_attachment(
                    actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                    file_obj=big, artifact_kind='KTP',
                )
        self.assertEqual(LampiranDrafPegawai.objects.count(), 0)
        self.assertEqual(self.session.calls, [])

    def test_png_is_rejected_for_intake(self):
        png = b'\x89PNG\r\n\x1a\n' + b'x' * 32
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            with self.assertRaises(ValidationError):
                stage_intake_attachment(
                    actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                    file_obj=SimpleUploadedFile('ktp.png', png, 'image/png'),
                    artifact_kind='KTP',
                )
        self.assertEqual(LampiranDrafPegawai.objects.count(), 0)

    def test_stale_version_does_not_upload(self):
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            with self.assertRaises(ValidationError):
                stage_intake_attachment(
                    actor=self.manager, draft_id=self.draft.pk, expected_version=1,
                    file_obj=SimpleUploadedFile('ktp.pdf', PDF, 'application/pdf'),
                    artifact_kind='KTP',
                )
        self.assertEqual(self.session.calls, [])

    def test_storage_failure_leaves_no_row(self):
        failing = SupabasePrivateStorage(
            base_url='https://project.supabase.co', api_key='service-key',
            bucket='hc-private', session=FakeSession(FakeResponse(500)),
        )
        with patch('sdm.storage.get_private_storage', return_value=failing):
            with self.assertRaises(PrivateStorageError):
                stage_intake_attachment(
                    actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                    file_obj=SimpleUploadedFile('ktp.pdf', PDF, 'application/pdf'),
                    artifact_kind='KTP',
                )
        self.assertEqual(LampiranDrafPegawai.objects.count(), 0)

    def test_foreign_draft_is_refused(self):
        intruder = self._user('upload-intruder')
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            with self.assertRaises(ValidationError):
                stage_intake_attachment(
                    actor=intruder, draft_id=self.draft.pk, expected_version=2,
                    file_obj=SimpleUploadedFile('ktp.pdf', PDF, 'application/pdf'),
                    artifact_kind='KTP',
                )
        self.assertEqual(LampiranDrafPegawai.objects.count(), 0)

    def test_photo_is_normalized_to_a_bounded_jpeg(self):
        raw = _jpeg_bytes(width=3000, height=4000)
        data, content_type = normalize_profile_photo(
            SimpleUploadedFile('foto.jpg', raw, 'image/jpeg')
        )
        self.assertEqual(content_type, 'image/jpeg')
        self.assertLess(len(data), len(raw))
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            self.assertLessEqual(max(image.size), 512)

    def test_photo_rejects_a_non_image(self):
        with self.assertRaises(ValidationError):
            normalize_profile_photo(
                SimpleUploadedFile('foto.jpg', b'not-an-image', 'image/jpeg')
            )

    def test_photo_rejects_a_tiny_source(self):
        with self.assertRaises(ValidationError):
            normalize_profile_photo(
                SimpleUploadedFile('foto.jpg', _jpeg_bytes(80, 80), 'image/jpeg')
            )

    def test_finalization_binds_staged_photo_to_a_typed_document(self):
        self.draft.draft_data = {
            '1': {'nama_depan': 'Budi'},
            '2': {
                'nomor_pegawai': 'UP-001', 'kategori': 'NON_PPA',
                'kategori_pegawai': 'TETAP', 'status': 'AKTIF',
                'unit_kerja': self.root.pk,
                'tanggal_mulai': timezone.localdate().isoformat(),
                'alokasi_fte': '1.00',
            },
            '3': {}, '4': {}, '5': {},
        }
        self.draft.save(update_fields=['draft_data', 'updated_at'])
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            attachment = stage_intake_attachment(
                actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                file_obj=SimpleUploadedFile(
                    'foto.jpg', _jpeg_bytes(), 'image/jpeg'
                ),
                artifact_kind='FOTO_PROFIL',
            )
        employee = finalize_staff_intake(
            actor=self.manager, draft_id=self.draft.pk,
            expected_version=2, idempotency_key='upload-bind-1',
        )
        attachment.refresh_from_db()
        employee.profil_pribadi.refresh_from_db()
        self.assertEqual(attachment.state, 'BOUND')
        self.assertEqual(attachment.bound_version.document.employee, employee)
        self.assertEqual(attachment.bound_version.document.jenis_berkas, 'FOTO')
        self.assertEqual(
            employee.profil_pribadi.foto_profil_versi,
            attachment.bound_version,
        )
        self.assertEqual(
            DokumenPegawai.objects.filter(employee=employee).count(), 1
        )
        self.assertTrue(PeristiwaSDM.objects.filter(
            actor=self.manager,
            jenis_peristiwa='private_document_uploaded',
            target_id=str(attachment.bound_version_id),
        ).exists())

    def test_attachment_remove_route_is_post_only(self):
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            attachment = stage_intake_attachment(
                actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                file_obj=SimpleUploadedFile('ktp.pdf', PDF, 'application/pdf'),
                artifact_kind='KTP',
            )
        self.client.force_login(self.manager)
        url = reverse(
            'sdm:pegawai_intake_attachment_remove',
            kwargs={'attachment_id': attachment.pk},
        )
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_owner_can_remove_a_staged_attachment(self):
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            attachment = stage_intake_attachment(
                actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                file_obj=SimpleUploadedFile('ktp.pdf', PDF, 'application/pdf'),
                artifact_kind='KTP',
            )
        self.client.force_login(self.manager)
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            response = self.client.post(
                reverse(
                    'sdm:pegawai_intake_attachment_remove',
                    kwargs={'attachment_id': attachment.pk},
                ),
                {'expected_version': str(self.draft.version)},
            )
        self.assertEqual(response.status_code, 302)
        attachment.refresh_from_db()
        self.assertEqual(attachment.state, 'DELETED')

    def test_foreign_user_gets_the_same_generic_redirect(self):
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            attachment = stage_intake_attachment(
                actor=self.manager, draft_id=self.draft.pk, expected_version=2,
                file_obj=SimpleUploadedFile('ktp.pdf', PDF, 'application/pdf'),
                artifact_kind='KTP',
            )
        intruder = self._user('upload-remover')
        self.client.force_login(intruder)
        response = self.client.post(
            reverse(
                'sdm:pegawai_intake_attachment_remove',
                kwargs={'attachment_id': attachment.pk},
            ),
            {'expected_version': str(self.draft.version)},
        )
        self.assertEqual(response.status_code, 302)
        attachment.refresh_from_db()
        self.assertEqual(attachment.state, 'STAGED')


class KtpOcrAutoFillTests(TestCase):
    """Step-5 KTP upload runs OCR and pre-fills draft step 1."""

    def setUp(self):
        self.root = UnitKerja.objects.create(name='Direktorat OCR', code='UP-OCR')
        self.manager = self._user('ocr-manager')
        self.draft = DrafInputPegawai.objects.create(
            owner=self.manager, current_step=5, version=2,
            expires_at=timezone.now() + timedelta(days=1),
            draft_data={
                '1': {'nama_depan': 'Budi'},
                '2': {'unit_kerja': self.root.pk},
            },
        )
        self.session = FakeSession(FakeResponse(200))
        self.storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co', api_key='service-key',
            bucket='hc-private', session=self.session,
        )
        from akreditasi.system_models import SystemConfig
        config = SystemConfig.get_solo()
        config.ai_enabled = True
        config.ai_api_key = 'test-key-sk-12345'
        config.save()

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.can_manage_hc_documents = True
        config.save(update_fields=[
            'can_view_hc', 'can_manage_hc_employees',
            'can_manage_hc_documents', 'updated_at',
        ])
        for capability in (
            'can_view_hc', 'can_manage_hc_employees', 'can_manage_hc_documents',
        ):
            HcGrant.objects.create(
                user=user, capability=capability, unit_kerja=self.root
            )
        return user

    def _post_step5(self, *, jenis='KTP'):
        self.client.force_login(self.manager)
        return self.client.post(
            reverse('sdm:pegawai_wizard_resume',
                    kwargs={'step': 5, 'draft_id': self.draft.pk}),
            {
                'expected_version': str(self.draft.version),
                'jenis_berkas': jenis,
                'judul': 'KTP Pegawai',
                'berkas': SimpleUploadedFile(
                    'ktp.jpg', JPEG, 'image/jpeg'
                ),
            },
        )

    def _patched(self, ocr_return=None, ocr_side_effect=None):
        return (
            patch('sdm.intake_views.get_private_storage',
                  return_value=self.storage),
            patch('sdm.intake_views.extract_ktp_fields',
                  return_value=ocr_return, side_effect=ocr_side_effect),
        )

    def test_ktp_upload_writes_ocr_fields_into_draft_step1(self):
        faked = {'nik': '3204012509880003', 'nama_lengkap': 'Rina Kartika',
                 'tempat_lahir': 'Bandung', 'tanggal_lahir': '1988-09-25',
                 'gender': 'PEREMPUAN', 'alamat': 'Jl. Melati No. 3'}
        storage_patch, ocr_patch = self._patched(ocr_return=faked)
        with storage_patch, ocr_patch:
            response = self._post_step5()
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        step1 = self.draft.draft_data.get('1') or {}
        self.assertEqual(step1.get('nik'), '3204012509880003')
        self.assertEqual(step1.get('alamat'), 'Jl. Melati No. 3')
        self.assertEqual(step1.get('gender'), 'PEREMPUAN')
        # Existing operator value is never clobbered by OCR (fill-empty-only).
        self.assertEqual(step1.get('nama_depan'), 'Budi')
        self.assertEqual(
            self.draft.attachments.filter(
                artifact_kind='KTP', state='STAGED'
            ).count(),
            1,
        )

    def test_ocr_prefills_empty_operator_name(self):
        faked = {'nik': '', 'nama_lengkap': 'Rina Kartika',
                 'tempat_lahir': '', 'tanggal_lahir': '',
                 'gender': '', 'alamat': ''}
        self.draft.draft_data['1'] = {}
        self.draft.save(update_fields=['draft_data', 'updated_at'])
        storage_patch, ocr_patch = self._patched(ocr_return=faked)
        with storage_patch, ocr_patch:
            response = self._post_step5()
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(
            self.draft.draft_data['1'].get('nama_depan'), 'Rina Kartika'
        )

    def test_ocr_empty_fields_leave_draft_untouched(self):
        from sdm.services import ktp_ocr
        blank = {key: '' for key in ktp_ocr.KTP_OCR_FIELDS}
        storage_patch, ocr_patch = self._patched(ocr_return=blank)
        with storage_patch, ocr_patch:
            response = self._post_step5()
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.draft_data['1'].get('nama_depan'), 'Budi')
        self.assertNotIn('nik', self.draft.draft_data['1'])

    def test_ocr_failure_still_stages_file(self):
        storage_patch, ocr_patch = self._patched(
            ocr_side_effect=ValueError('boom')
        )
        with storage_patch, ocr_patch:
            response = self._post_step5()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.draft.attachments.filter(
                artifact_kind='KTP', state='STAGED'
            ).count(),
            1,
        )
