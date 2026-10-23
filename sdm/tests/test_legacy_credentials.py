import hashlib
import json
import uuid
from datetime import date
from io import StringIO
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase

from accounts.models import NakesCredential, RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DokumenPegawai,
    HcGrant,
    Pegawai,
    PeristiwaSDM,
    TautanKredensialLama,
    VersiDokumen,
)
from sdm.services.kredensial_lama import resolve_legacy_credential
from sdm.storage_backend import PrivateStorageError, StoredPrivateObject


PDF = b'%PDF-1.7\\nlegacy fixture'


class FakePrivateStorage:
    def __init__(self):
        self.verified = []
        self.uploaded = []
        self.deleted = []
        self.signed = []

    def upload(self, file_obj, *, owner_id, sensitivity, filename, content_type):
        data = file_obj.read()
        stored = StoredPrivateObject(
            storage_key=f'personnel/{owner_id}/{uuid.uuid4()}.pdf',
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            content_type=content_type,
        )
        self.uploaded.append(stored.storage_key)
        return stored

    def delete(self, storage_key):
        self.deleted.append(storage_key)

    def create_signed_download(self, storage_key, *, expires_in=None):
        self.signed.append(storage_key)
        return f'https://private.example/object?opaque=1'

    def verify_anonymous_denial(self, storage_key):
        return True

    def verify_private_object(
        self, storage_key, *, expected_sha256, expected_size, expected_content_type
    ):
        self.verified.append(storage_key)
        return StoredPrivateObject(
            storage_key=storage_key,
            sha256=expected_sha256,
            size_bytes=expected_size,
            content_type=expected_content_type,
        )


class LegacyCredentialReconciliationTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Legacy', code='HC-LEGACY')
        self.user = get_user_model().objects.create_user(username='legacy-clinician')
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='STAF_NAKES',
            unit_kerja=self.unit,
            full_name='Legacy Clinician',
            profesi='PERAWAT',
        )
        self.employee = Pegawai.objects.create(
            akun=self.user,
            nama_lengkap='Legacy Clinician',
            nomor_pegawai='LEG-001',
            kategori='PPA',
            profesi='Perawat',
        )
        self.credential = NakesCredential.objects.create(
            user_profile=self.profile,
            doc_type='STR',
            title='STR lama',
            document_number='STR-001',
            issued_date=date(2024, 1, 1),
            valid_until=date(2028, 1, 1),
            file_url='https://legacy.example/credential.pdf',
            status='VERIFIED',
        )

    def _mapping(self, *, employee=None):
        storage_key = (
            f'personnel/{employee or self.employee.pk}/{uuid.uuid4()}.pdf'
        )
        return {
            'schema_version': 1,
            'reviewed_by': 'hc-reviewer',
            'reviewed_at': '2026-10-23T00:00:00+07:00',
            'mappings': [{
                'credential_id': self.credential.pk,
                'employee_id': str(employee or self.employee.pk),
                'storage_key': storage_key,
                'original_filename': 'str-001.pdf',
                'sha256': hashlib.sha256(PDF).hexdigest(),
                'size_bytes': len(PDF),
                'content_type': 'application/pdf',
            }],
        }

    def _run_apply(self, mapping):
        with TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / 'reviewed-mapping.json'
            artifact.write_text(json.dumps(mapping), encoding='utf-8')
            output = StringIO()
            call_command(
                'reconcile_hc_credentials',
                '--apply',
                '--mapping-artifact',
                str(artifact),
                stdout=output,
            )
            return output.getvalue()

    def test_resolver_returns_only_the_explicit_canonical_version(self):
        self.assertIsNone(resolve_legacy_credential(self.credential))

        document = DokumenPegawai.objects.create(
            employee=self.employee,
            document_type='CREDENTIAL',
            title=self.credential.title,
            sensitivity='personnel',
        )
        version = VersiDokumen.objects.create(
            document=document,
            version_number=1,
            original_filename='str-001.pdf',
            storage_key=f'personnel/{self.employee.pk}/{uuid.uuid4()}.pdf',
            sha256=hashlib.sha256(PDF).hexdigest(),
            size_bytes=len(PDF),
            content_type='application/pdf',
            issued_date=self.credential.issued_date,
            valid_until=self.credential.valid_until,
            status='VERIFIED',
        )
        TautanKredensialLama.objects.create(
            credential=self.credential, version=version
        )

        self.assertEqual(resolve_legacy_credential(self.credential), version)
        self.credential.refresh_from_db()
        self.assertEqual(
            self.credential.file_url,
            'https://legacy.example/credential.pdf',
        )

    def test_default_command_is_a_non_mutating_dry_run(self):
        output = StringIO()

        call_command('reconcile_hc_credentials', stdout=output)

        self.assertIn('DRY-RUN', output.getvalue())
        self.assertEqual(DokumenPegawai.objects.count(), 0)
        self.assertEqual(TautanKredensialLama.objects.count(), 0)
        self.assertEqual(NakesCredential.objects.count(), 1)

    def test_apply_requires_a_reviewed_mapping_artifact(self):
        with self.assertRaises(CommandError):
            call_command('reconcile_hc_credentials', '--apply', stdout=StringIO())

        self.assertEqual(DokumenPegawai.objects.count(), 0)

    def test_apply_rejects_employee_mismatch_before_storage_access(self):
        other_user = get_user_model().objects.create_user(username='other-clinician')
        other_employee = Pegawai.objects.create(
            akun=other_user, nama_lengkap='Other Clinician', kategori='PPA'
        )
        storage = FakePrivateStorage()

        with patch(
            'sdm.services.kredensial_lama.get_private_storage', return_value=storage
        ), self.assertRaises(CommandError):
            self._run_apply(self._mapping(employee=other_employee.pk))

        self.assertEqual(storage.verified, [])
        self.assertEqual(DokumenPegawai.objects.count(), 0)

    def test_apply_links_verified_private_object_idempotently(self):
        mapping = self._mapping()
        storage = FakePrivateStorage()
        output = StringIO()
        with TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / 'reviewed-mapping.json'
            artifact.write_text(json.dumps(mapping), encoding='utf-8')
            with patch(
                'sdm.services.kredensial_lama.get_private_storage',
                return_value=storage,
            ):
                call_command(
                    'reconcile_hc_credentials',
                    '--apply',
                    '--mapping-artifact',
                    str(artifact),
                    stdout=output,
                )
                call_command(
                    'reconcile_hc_credentials',
                    '--apply',
                    '--mapping-artifact',
                    str(artifact),
                    stdout=StringIO(),
                )

        self.assertEqual(DokumenPegawai.objects.count(), 1)
        self.assertEqual(VersiDokumen.objects.count(), 1)
        self.assertEqual(TautanKredensialLama.objects.count(), 1)
        link = TautanKredensialLama.objects.select_related('version__document').get()
        self.assertEqual(link.version.storage_key, mapping['mappings'][0]['storage_key'])
        self.assertEqual(link.version.document.employee, self.employee)
        self.assertEqual(link.version.status, 'VERIFIED')
        self.assertEqual(storage.verified, [mapping['mappings'][0]['storage_key']])
        self.assertEqual(
            NakesCredential.objects.get(pk=self.credential.pk).file_url,
            'https://legacy.example/credential.pdf',
        )
        self.assertEqual(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='legacy_credential_linked'
            ).count(),
            1,
        )
        self.assertIn('linked=1', output.getvalue())
        event = PeristiwaSDM.objects.get(jenis_peristiwa='legacy_credential_linked')
        self.assertNotIn(mapping['reviewed_by'], event.alasan)
        self.assertNotIn('credential_id=', event.alasan)

    def test_inventory_report_verifies_checksum_and_anonymous_denial_without_identifiers(self):
        mapping = self._mapping()
        storage = FakePrivateStorage()
        with patch(
            'sdm.services.kredensial_lama.get_private_storage', return_value=storage
        ):
            self._run_apply(mapping)
            output = StringIO()
            call_command(
                'reconcile_hc_credentials',
                '--inventory',
                '--verify-anonymous-denial',
                stdout=output,
            )

        report = output.getvalue()
        self.assertIn('INVENTORY', report)
        self.assertIn('verified=1', report)
        self.assertIn('anonymous_denied=1', report)
        self.assertNotIn(str(self.employee.pk), report)
        self.assertNotIn(self.user.username, report)

    def test_inventory_reports_missing_or_mismatched_objects_as_aggregate_only(self):
        mapping = self._mapping()
        good_storage = FakePrivateStorage()
        with patch(
            'sdm.services.kredensial_lama.get_private_storage',
            return_value=good_storage,
        ):
            self._run_apply(mapping)
        broken_storage = FakePrivateStorage()

        def fail_verification(*args, **kwargs):
            raise PrivateStorageError('provider secret detail')

        broken_storage.verify_private_object = fail_verification
        with patch(
            'sdm.services.kredensial_lama.get_private_storage',
            return_value=broken_storage,
        ):
            output = StringIO()
            call_command('reconcile_hc_credentials', '--inventory', stdout=output)

        report = output.getvalue()
        self.assertIn('missing_or_mismatched=1', report)
        self.assertNotIn('provider secret detail', report)
        self.assertNotIn(str(self.employee.pk), report)


class LegacyCredentialRouteTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Route', code='HC-ROUTE')
        self.owner = get_user_model().objects.create_user(
            username='legacy-route-owner', password='secret'
        )
        self.profile = UserProfile.objects.create(
            user=self.owner,
            role='STAF_NAKES',
            unit_kerja=self.unit,
            full_name='Route Owner',
            profesi='PERAWAT',
        )
        self.employee = Pegawai.objects.create(
            akun=self.owner,
            nama_lengkap='Route Owner',
            kategori='PPA',
        )
        self.storage = FakePrivateStorage()

    def _upload(self):
        self.client.force_login(self.owner)
        with patch(
            'sdm.services.kredensial_lama.get_private_storage',
            return_value=self.storage,
        ):
            return self.client.post('/portal-nakes/upload-kredensial/', {
                'doc_type': 'STR',
                'title': 'STR privat',
                'document_number': 'STR-PRIVATE',
                'issued_date': '2026-01-01',
                'valid_until': '2028-01-01',
                'file': SimpleUploadedFile(
                    'str-private.pdf', PDF, content_type='application/pdf'
                ),
            })

    def test_upload_creates_legacy_identity_linked_to_private_canonical_version(self):
        response = self._upload()

        credential = NakesCredential.objects.get(title='STR privat')
        version = credential.hc_document_link.version
        self.assertRedirects(response, '/portal-nakes/')
        self.assertEqual(credential.status, 'PENDING')
        self.assertFalse(credential.file)
        self.assertEqual(credential.file_url, '')
        self.assertEqual(version.document.employee, self.employee)
        self.assertEqual(version.status, 'PENDING')
        self.assertEqual(version.storage_key, self.storage.uploaded[0])
        event = PeristiwaSDM.objects.get(
            jenis_peristiwa='legacy_credential_uploaded', target_id=str(version.pk)
        )
        self.assertNotIn(credential.title, event.alasan)
        self.assertNotIn(self.owner.username, event.alasan)

    def test_upload_database_failure_cleans_private_object(self):
        self.client.force_login(self.owner)
        with patch(
            'sdm.services.kredensial_lama.get_private_storage',
            return_value=self.storage,
        ), patch(
            'sdm.services.kredensial_lama.TautanKredensialLama.save',
            side_effect=RuntimeError,
        ):
            response = self.client.post('/portal-nakes/upload-kredensial/', {
                'doc_type': 'STR',
                'title': 'STR gagal',
                'document_number': 'STR-FAIL',
                'file': SimpleUploadedFile(
                    'str-fail.pdf', PDF, content_type='application/pdf'
                ),
            })

        self.assertRedirects(response, '/portal-nakes/')
        self.assertEqual(NakesCredential.objects.count(), 0)
        self.assertEqual(self.storage.deleted, self.storage.uploaded)

    def test_unlinked_legacy_download_preserves_existing_authorized_behavior(self):
        credential = NakesCredential.objects.create(
            user_profile=self.profile,
            doc_type='STR',
            title='STR unresolved',
            file_url='https://legacy.example/credential.pdf',
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            f'/portal-nakes/kredensial/{credential.pk}/unduh/'
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], credential.file_url)

    def test_unlinked_approved_legacy_delete_preserves_row(self):
        credential = NakesCredential.objects.create(
            user_profile=self.profile,
            doc_type='STR',
            title='STR approved unresolved',
            status='VERIFIED',
            file_url='https://legacy.example/approved.pdf',
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            f'/portal-nakes/hapus-kredensial/{credential.pk}/'
        )

        self.assertRedirects(response, '/portal-nakes/')
        credential.refresh_from_db()
        self.assertEqual(credential.status, 'VERIFIED')
        self.assertEqual(credential.file_url, 'https://legacy.example/approved.pdf')

    def test_linked_delete_supersedes_without_deleting_approved_history(self):
        self._upload()
        credential = NakesCredential.objects.get(title='STR privat')
        version = credential.hc_document_link.version
        version.status = 'VERIFIED'
        version.save(update_fields=['status'])

        response = self.client.post(f'/portal-nakes/hapus-kredensial/{credential.pk}/')

        credential.refresh_from_db()
        version.refresh_from_db()
        self.assertRedirects(response, '/portal-nakes/')
        self.assertEqual(version.status, 'SUPERSEDED')
        self.assertEqual(credential.status, 'REJECTED')
        self.assertTrue(NakesCredential.objects.filter(pk=credential.pk).exists())
        self.assertTrue(VersiDokumen.objects.filter(pk=version.pk).exists())
        event = PeristiwaSDM.objects.get(
            jenis_peristiwa='legacy_credential_archived', target_id=str(version.pk)
        )
        self.assertNotIn(credential.title, event.alasan)
        self.assertNotIn(self.owner.username, event.alasan)
        portal = self.client.get('/portal-nakes/')
        self.assertNotContains(portal, 'STR privat')

    def test_linked_download_uses_authorized_short_lived_private_url(self):
        self._upload()
        credential = NakesCredential.objects.get(title='STR privat')

        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            response = self.client.get(f'/portal-nakes/kredensial/{credential.pk}/unduh/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://private.example/object?opaque=1')
        self.assertEqual(
            self.storage.signed,
            [credential.hc_document_link.version.storage_key],
        )
        event = PeristiwaSDM.objects.get(
            jenis_peristiwa='private_document_download',
            target_id=str(credential.hc_document_link.version_id),
        )
        self.assertNotIn('opaque=1', event.alasan)

    def test_linked_download_denies_anonymous_user(self):
        self._upload()
        credential = NakesCredential.objects.get(title='STR privat')
        self.client.logout()

        response = self.client.get(
            f'/portal-nakes/kredensial/{credential.pk}/unduh/'
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.assertEqual(self.storage.signed, [])

    def test_linked_review_updates_canonical_and_legacy_status(self):
        self._upload()
        credential = NakesCredential.objects.get(title='STR privat')
        reviewer = get_user_model().objects.create_user(username='legacy-route-reviewer')
        UserProfile.objects.create(
            user=reviewer, role='ADMIN_RS', unit_kerja=self.unit
        )
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_review_hc_credentials = True
        config.save(update_fields=['can_review_hc_credentials', 'updated_at'])
        HcGrant.objects.create(
            user=reviewer,
            capability='can_review_hc_credentials',
            unit_kerja=self.unit,
        )
        self.client.force_login(reviewer)

        response = self.client.post(
            f'/rekap-kps/verifikasi/{credential.pk}/',
            {'status': 'VERIFIED', 'verification_notes': 'checked privately'},
        )

        credential.refresh_from_db()
        version = credential.hc_document_link.version
        version.refresh_from_db()
        self.assertRedirects(response, '/rekap-kps/')
        self.assertEqual(credential.status, 'VERIFIED')
        self.assertEqual(version.status, 'VERIFIED')
        event = PeristiwaSDM.objects.get(
            jenis_peristiwa='private_document_reviewed', target_id=str(version.pk)
        )
        self.assertNotIn('checked privately', event.alasan)

    def test_linked_review_rejects_manual_expired_status(self):
        self._upload()
        credential = NakesCredential.objects.get(title='STR privat')
        reviewer = get_user_model().objects.create_user(username='legacy-expiry-reviewer')
        UserProfile.objects.create(
            user=reviewer, role='ADMIN_RS', unit_kerja=self.unit
        )
        self.client.force_login(reviewer)

        response = self.client.post(
            f'/rekap-kps/verifikasi/{credential.pk}/',
            {'status': 'EXPIRED', 'verification_notes': ''},
        )

        credential.refresh_from_db()
        self.assertRedirects(response, '/rekap-kps/')
        self.assertEqual(credential.status, 'PENDING')
        self.assertEqual(credential.hc_document_link.version.status, 'PENDING')

    def test_linked_review_without_explicit_hc_grant_is_denied(self):
        self._upload()
        credential = NakesCredential.objects.get(title='STR privat')
        reviewer = get_user_model().objects.create_user(username='legacy-no-grant-reviewer')
        UserProfile.objects.create(
            user=reviewer, role='ADMIN_RS', unit_kerja=self.unit
        )
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_review_hc_credentials = False
        config.save(update_fields=['can_review_hc_credentials', 'updated_at'])
        self.client.force_login(reviewer)

        response = self.client.post(
            f'/rekap-kps/verifikasi/{credential.pk}/',
            {'status': 'VERIFIED', 'verification_notes': ''},
        )

        credential.refresh_from_db()
        self.assertRedirects(response, '/rekap-kps/')
        self.assertEqual(credential.status, 'PENDING')
        self.assertEqual(credential.hc_document_link.version.status, 'PENDING')


class BackfillEmployeeCommandTests(TestCase):
    """Backfill is exact-match only; seeded accounts in the test DB are ignored."""

    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Backfill', code='HC-BF')
        self.baseline = Pegawai.objects.count()

    def _profile(self, username, *, nip='', profesi=''):
        user = get_user_model().objects.create_user(username=username)
        return UserProfile.objects.create(
            user=user, role='STAF_NAKES', unit_kerja=self.unit,
            nip_nrp=nip, profesi=profesi, full_name=f'Nama {username}',
        )

    def test_dry_run_creates_nothing(self):
        self._profile('bf-dry')

        output = StringIO()
        call_command('backfill_hc_employees', stdout=output)

        self.assertIn('DRY-RUN', output.getvalue())
        self.assertEqual(Pegawai.objects.count(), self.baseline)

    def test_apply_links_account_and_copies_identity(self):
        profile = self._profile('bf-apply', nip='BF-1', profesi='PERAWAT')

        call_command('backfill_hc_employees', '--apply', stdout=StringIO())

        employee = Pegawai.objects.get(akun_id=profile.user_id)
        self.assertEqual(employee.nomor_pegawai, 'BF-1')
        self.assertEqual(employee.profesi, 'PERAWAT')
        self.assertEqual(employee.nama_lengkap, 'Nama bf-apply')

    def test_apply_is_idempotent(self):
        self._profile('bf-twice')

        call_command('backfill_hc_employees', '--apply', stdout=StringIO())
        after_first = Pegawai.objects.count()
        output = StringIO()
        call_command('backfill_hc_employees', '--apply', stdout=output)

        self.assertEqual(Pegawai.objects.count(), after_first)
        self.assertIn('created=0', output.getvalue())

    def test_duplicate_employee_number_is_blanked_not_merged(self):
        first = self._profile('bf-dup-a', nip='DUP-1')
        second = self._profile('bf-dup-b', nip='DUP-1')

        output = StringIO()
        call_command('backfill_hc_employees', '--apply', stdout=output)

        self.assertEqual(
            Pegawai.objects.filter(nomor_pegawai='DUP-1').count(), 1
        )
        self.assertTrue(
            Pegawai.objects.filter(akun_id=first.user_id).exists()
        )
        self.assertTrue(
            Pegawai.objects.filter(akun_id=second.user_id).exists()
        )
        self.assertIn('duplicate_numbers_blanked=1', output.getvalue())

    def test_existing_employee_link_is_not_overwritten(self):
        profile = self._profile('bf-linked')
        existing = Pegawai.objects.create(
            akun_id=profile.user_id, nama_lengkap='Nama Manual', kategori='NON_PPA'
        )

        call_command('backfill_hc_employees', '--apply', stdout=StringIO())

        existing.refresh_from_db()
        self.assertEqual(existing.nama_lengkap, 'Nama Manual')
        self.assertEqual(
            Pegawai.objects.filter(akun_id=profile.user_id).count(), 1
        )


class LegacyUploadWithoutEmployeeTests(TestCase):
    """A deploy without the employee backfill must fail closed with a clear message."""

    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Tanpa Pegawai', code='HC-NOEMP')
        self.user = get_user_model().objects.create_user(
            username='unlinked-nakes', password='secret'
        )
        UserProfile.objects.create(
            user=self.user, role='STAF_NAKES', unit_kerja=self.unit
        )

    def test_upload_is_refused_and_no_public_or_local_file_is_created(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.user)

        response = self.client.post('/portal-nakes/upload-kredensial/', {
            'doc_type': 'STR',
            'title': 'STR tanpa identitas',
            'document_number': 'NOEMP-1',
            'file': SimpleUploadedFile('str.pdf', PDF, content_type='application/pdf'),
        })

        self.assertRedirects(response, '/portal-nakes/')
        self.assertFalse(
            NakesCredential.objects.filter(document_number='NOEMP-1').exists()
        )
        self.assertEqual(Pegawai.objects.filter(akun=self.user).count(), 0)
