from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DokumenPegawai,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
    VersiDokumen,
)
from sdm.storage_backend import PrivateStorageError, SupabasePrivateStorage
from sdm.tests.test_storage_backend import FakeResponse, FakeSession, PDF
from sdm.storage import (
    authorize_document_download,
    review_document_version,
    store_document_version,
    store_private_document,
)


class PrivateDocumentServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Dokumen', code='HC-DOC')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Dokumen', kategori='PPA'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        self.session = FakeSession(FakeResponse(200, {
            'signedURL': (
                f"/storage/v1/object/sign/hc-private/personnel/"
                f"{self.employee.pk}/{uuid.uuid4()}.pdf?token=temporary"
            )
        }))
        self.storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co',
            api_key='service-key',
            bucket='hc-private',
            session=self.session,
        )
        self.personnel_uploader = self._user('hc-personnel-uploader')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_manage_hc_documents = True
        config.save(update_fields=['can_manage_hc_documents', 'updated_at'])
        self._grant(self.personnel_uploader, 'can_manage_hc_documents')
        self.health_uploader = get_user_model().objects.create_user(
            username='hc-health-uploader'
        )
        self._grant(self.health_uploader, 'hc_health_write')

    def _user(self, username, *, role='ADMIN_RS'):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role=role, unit_kerja=self.unit)
        return user

    def _grant(self, user, capability):
        return HcGrant.objects.create(
            user=user,
            capability=capability,
            unit_kerja=self.unit,
        )

    def _upload(
        self, *, sensitivity='personnel', document_type='CREDENTIAL', storage=None
    ):
        with patch(
            'sdm.storage.get_private_storage',
            return_value=storage or self.storage,
        ):
            return store_private_document(
                SimpleUploadedFile(
                    'credential.pdf', PDF, content_type='application/pdf'
                ),
                employee=self.employee,
                sensitivity=sensitivity,
                document_type=document_type,
                title='Credential scan',
                uploaded_by=(
                    self.health_uploader
                    if sensitivity == 'health'
                    else self.personnel_uploader
                ),
            )

    def test_upload_creates_private_document_version_and_hash(self):
        document, version = self._upload()

        self.assertEqual(document.employee, self.employee)
        self.assertEqual(document.sensitivity, 'personnel')
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.content_type, 'application/pdf')
        self.assertEqual(version.size_bytes, len(PDF))
        self.assertEqual(self.session.calls[0][0], 'POST')
        self.assertTrue(version.storage_key.startswith(f'personnel/{self.employee.pk}/'))
        self.assertNotIn('token=', version.storage_key)

    def test_new_upload_supersedes_previous_version_and_resets_review(self):
        document, first = self._upload()

        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            second = store_document_version(
                SimpleUploadedFile(
                    'credential-renewal.pdf', PDF, content_type='application/pdf'
                ),
                document=document,
                uploaded_by=self.personnel_uploader,
                issued_date=self.today,
                valid_until=self.today + timedelta(days=365),
            )

        first.refresh_from_db()
        self.assertEqual(first.status, 'SUPERSEDED')
        self.assertEqual(second.version_number, 2)
        self.assertEqual(second.status, 'PENDING')
        self.assertIsNone(second.reviewed_by_id)
        self.assertNotEqual(first.storage_key, second.storage_key)
        event = PeristiwaSDM.objects.get(
            target_id=str(first.pk),
            jenis_peristiwa='private_document_superseded',
        )
        self.assertEqual(event.status_sebelum, 'PENDING')
        self.assertEqual(event.status_sesudah, 'SUPERSEDED')

    def test_credential_review_requires_authorized_independent_reviewer(self):
        _document, version = self._upload()
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_review_hc_credentials = True
        config.save(update_fields=['can_review_hc_credentials', 'updated_at'])
        self._grant(self.personnel_uploader, 'can_review_hc_credentials')

        with self.assertRaises(PermissionDenied):
            review_document_version(
                self.personnel_uploader, version, status='VERIFIED'
            )

        reviewer = self._user('hc-independent-reviewer')
        self._grant(reviewer, 'can_review_hc_credentials')
        reviewed = review_document_version(
            reviewer,
            version,
            status='VERIFIED',
            notes='review note must not enter audit metadata',
        )

        self.assertEqual(reviewed.status, 'VERIFIED')
        self.assertEqual(reviewed.reviewed_by, reviewer)
        event = PeristiwaSDM.objects.get(
            target_id=str(version.pk), jenis_peristiwa='private_document_reviewed'
        )
        self.assertNotIn('review note', event.alasan)
        self.assertNotIn(reviewer.username, event.alasan)

    def test_superseded_version_cannot_be_reviewed(self):
        document, first = self._upload()
        reviewer = self._user('hc-superseded-reviewer')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_review_hc_credentials = True
        config.save(update_fields=['can_review_hc_credentials', 'updated_at'])
        self._grant(reviewer, 'can_review_hc_credentials')
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            store_document_version(
                SimpleUploadedFile('new.pdf', PDF, content_type='application/pdf'),
                document=document,
                uploaded_by=self.personnel_uploader,
            )

        with self.assertRaises(ValidationError):
            review_document_version(reviewer, first, status='VERIFIED')

    def test_employee_can_upload_own_credential_without_hr_grant(self):
        owner = get_user_model().objects.create_user(username='credential-owner')
        self.employee.akun = owner
        self.employee.save(update_fields=['akun', 'updated_at'])

        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            document, version = store_private_document(
                SimpleUploadedFile('own-str.pdf', PDF, content_type='application/pdf'),
                employee=self.employee,
                sensitivity='personnel',
                document_type='CREDENTIAL',
                title='STR sendiri',
                uploaded_by=owner,
            )

        self.assertEqual(document.employee, self.employee)
        self.assertEqual(version.created_by, owner)

    def test_employee_can_download_own_credential_without_hr_grant(self):
        owner = get_user_model().objects.create_user(username='credential-reader')
        self.employee.akun = owner
        self.employee.save(update_fields=['akun', 'updated_at'])
        document, version = self._upload()
        self.session.response = FakeResponse(200, {
            'signedURL': (
                f'/storage/v1/object/sign/hc-private/{version.storage_key}'
                '?token=temporary'
            )
        })

        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            signed_url = authorize_document_download(owner, version)

        self.assertIn(version.storage_key, signed_url)

    def test_failed_storage_upload_creates_no_document(self):
        failed_storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co',
            api_key='service-key',
            bucket='hc-private',
            session=FakeSession(FakeResponse(503, text='provider detail')),
        )

        with self.assertRaises(PrivateStorageError):
            self._upload(storage=failed_storage)

        self.assertEqual(DokumenPegawai.objects.count(), 0)
        self.assertEqual(VersiDokumen.objects.count(), 0)

    def test_database_failure_triggers_private_object_cleanup(self):
        with patch('sdm.models.dokumen.VersiDokumen.save', side_effect=IntegrityError):
            with self.assertRaises(PrivateStorageError):
                self._upload()

        self.assertEqual(DokumenPegawai.objects.count(), 0)
        self.assertEqual([call[0] for call in self.session.calls], ['POST', 'DELETE'])

    def test_database_failure_during_reupload_cleans_new_object_and_preserves_current_version(self):
        document, first = self._upload()
        self.session.calls.clear()

        with patch('sdm.storage.get_private_storage', return_value=self.storage), patch(
            'sdm.storage.PeristiwaSDM.objects.create', side_effect=IntegrityError
        ):
            with self.assertRaises(PrivateStorageError):
                store_document_version(
                    SimpleUploadedFile(
                        'credential-renewal.pdf', PDF, content_type='application/pdf'
                    ),
                    document=document,
                    uploaded_by=self.personnel_uploader,
                )

        first.refresh_from_db()
        self.assertEqual(first.status, 'PENDING')
        self.assertEqual(document.versions.count(), 1)
        self.assertEqual([call[0] for call in self.session.calls], ['POST', 'DELETE'])

    def test_reupload_by_employee_owner_returns_to_pending_review(self):
        owner = get_user_model().objects.create_user(username='credential-reuploader')
        self.employee.akun = owner
        self.employee.save(update_fields=['akun', 'updated_at'])
        document, first = self._upload()
        first.status = 'VERIFIED'
        first.reviewed_by = self.personnel_uploader
        first.reviewed_at = timezone.now()
        first.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            second = store_document_version(
                SimpleUploadedFile('own-renewal.pdf', PDF, content_type='application/pdf'),
                document=document,
                uploaded_by=owner,
            )

        first.refresh_from_db()
        self.assertEqual(first.status, 'SUPERSEDED')
        self.assertEqual(second.status, 'PENDING')
        self.assertIsNone(second.reviewed_by_id)
        self.assertIsNone(second.reviewed_at)
        self.assertEqual(second.review_notes, '')

    def test_download_requires_matching_grant_and_audits_without_signed_token(self):
        _document, version = self._upload()
        user = self._user('hc-document-reader')
        role_config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        role_config.can_view_hc = True
        role_config.save(update_fields=['can_view_hc', 'updated_at'])
        self._grant(user, 'can_view_hc')
        self.session.response = FakeResponse(200, {
            'signedURL': (
                f'/storage/v1/object/sign/hc-private/{version.storage_key}'
                '?token=temporary'
            )
        })

        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            signed_url = authorize_document_download(user, version)

        self.assertTrue(signed_url.startswith('https://project.supabase.co/'))
        event = PeristiwaSDM.objects.get(
            target_id=str(version.pk), jenis_peristiwa='private_document_download'
        )
        self.assertEqual(event.actor, user)
        self.assertEqual(event.jenis_peristiwa, 'private_document_download')
        self.assertNotIn('temporary', event.alasan)

    def test_health_download_needs_specific_health_grant(self):
        _document, version = self._upload(
            sensitivity='health', document_type='HEALTH'
        )
        user = self._user('hr-health-denied')
        self._grant(user, 'can_view_hc')

        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            with self.assertRaises(PermissionDenied):
                authorize_document_download(user, version)

        self.assertEqual(len(self.session.calls), 1)
