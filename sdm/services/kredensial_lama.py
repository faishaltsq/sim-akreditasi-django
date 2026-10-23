import hashlib
import json
import re
from datetime import datetime
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.text import get_valid_filename

from accounts.models import NakesCredential
from sdm.models import (
    DokumenPegawai,
    Pegawai,
    PeristiwaSDM,
    TautanKredensialLama,
    VersiDokumen,
)
from sdm.storage import (
    _authorize_document_write,
    _cleanup_uploaded_object,
    authorize_document_download,
    get_private_storage,
    review_document_version,
)
from sdm.storage_backend import PrivateStorageError


MAPPING_KEYS = {
    'credential_id',
    'employee_id',
    'storage_key',
    'original_filename',
    'sha256',
    'size_bytes',
    'content_type',
}


def resolve_legacy_credential(credential):
    link = TautanKredensialLama.objects.select_related(
        'credential__user_profile', 'version__document__employee'
    ).filter(
        credential_id=credential.pk
    ).first()
    if link and link.version.document.employee.akun_id != credential.user_profile.user_id:
        raise ValidationError('Tautan kredensial tidak cocok dengan akun pegawai.')
    return link.version if link else None


def create_legacy_credential(credential, file_obj, *, uploaded_by):
    employee = Pegawai.objects.select_related('akun').filter(
        akun_id=credential.user_profile.user_id
    ).first()
    if employee is None:
        raise ValidationError('Akun kredensial belum memiliki identitas pegawai Human Capital.')
    document = DokumenPegawai(
        employee=employee,
        document_type='CREDENTIAL',
        title=credential.title,
        sensitivity='personnel',
        created_by=uploaded_by,
    )
    _authorize_document_write(uploaded_by, document)
    document.full_clean()
    raw_name = getattr(file_obj, 'name', '')
    filename = get_valid_filename(
        raw_name.replace('\\', '/').rsplit('/', 1)[-1]
    )[:255] if isinstance(raw_name, str) else ''
    if not filename:
        raise ValidationError('Nama berkas tidak valid.')
    storage = get_private_storage()
    stored = storage.upload(
        file_obj,
        owner_id=str(employee.pk),
        sensitivity='personnel',
        filename=filename,
        content_type=getattr(file_obj, 'content_type', ''),
    )

    try:
        with transaction.atomic():
            credential.status = 'PENDING'
            credential.file = None
            credential.file_url = ''
            credential.save()
            document.save()
            version = VersiDokumen(
                document=document,
                version_number=1,
                original_filename=filename,
                storage_key=stored.storage_key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                issued_date=credential.issued_date,
                valid_until=credential.valid_until,
                status='PENDING',
                created_by=uploaded_by,
            )
            version.full_clean()
            version.save()
            link = TautanKredensialLama(credential=credential, version=version)
            link.full_clean()
            link.save()
            PeristiwaSDM.objects.create(
                actor=uploaded_by,
                jenis_peristiwa='legacy_credential_uploaded',
                target_tipe='document_version',
                target_id=str(version.pk),
                status_sesudah='PENDING',
                alasan='legacy route delegated to private canonical storage',
            )
    except Exception:
        _cleanup_uploaded_object(storage, stored.storage_key)
        raise PrivateStorageError('Document record could not be committed') from None
    return credential, version


def review_legacy_credential(credential, reviewer, *, status, notes=''):
    version = resolve_legacy_credential(credential)
    if version is None:
        return None
    if status == 'EXPIRED':
        raise ValidationError('Status kedaluwarsa ditentukan dari tanggal berlaku.')
    canonical_status = status
    with transaction.atomic():
        reviewed = review_document_version(
            reviewer, version, status=canonical_status, notes=notes
        )
        credential.status = status
        credential.verification_notes = notes
        credential.save(update_fields=['status', 'verification_notes', 'updated_at'])
    return reviewed


def archive_legacy_credential(credential, *, actor):
    version = resolve_legacy_credential(credential)
    if version is None:
        return False
    if credential.user_profile.user_id != getattr(actor, 'pk', None):
        raise PermissionDenied('Kredensial tidak tersedia.')
    with transaction.atomic():
        locked = VersiDokumen.objects.select_for_update().get(pk=version.pk)
        previous = locked.status
        locked.status = 'SUPERSEDED'
        locked.save(update_fields=['status'])
        credential.status = 'REJECTED'
        credential.verification_notes = 'Diarsipkan oleh pemilik.'
        credential.save(update_fields=['status', 'verification_notes', 'updated_at'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='legacy_credential_archived',
            target_tipe='document_version',
            target_id=str(locked.pk),
            status_sebelum=previous,
            status_sesudah='SUPERSEDED',
            alasan='owner archive requested through legacy route',
        )
    return True


def authorize_legacy_credential_download(credential, user):
    version = resolve_legacy_credential(credential)
    if version is None:
        return None
    return authorize_document_download(user, version)


def _validate_mapping_artifact(artifact):
    if not isinstance(artifact, dict) or set(artifact) != {
        'schema_version', 'reviewed_by', 'reviewed_at', 'mappings'
    }:
        raise ValidationError('Format artefak pemetaan tidak valid.')
    if type(artifact['schema_version']) is not int or artifact['schema_version'] != 1:
        raise ValidationError('Versi artefak pemetaan tidak didukung.')
    if not isinstance(artifact['reviewed_by'], str) or not artifact['reviewed_by'].strip():
        raise ValidationError('Reviewer artefak wajib dicatat.')
    try:
        reviewed_at = datetime.fromisoformat(artifact['reviewed_at'])
    except (TypeError, ValueError):
        raise ValidationError('Waktu tinjauan artefak tidak valid.') from None
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValidationError('Waktu tinjauan artefak harus menyertakan zona waktu.')
    if not isinstance(artifact['mappings'], list):
        raise ValidationError('Daftar pemetaan tidak valid.')

    if any(not isinstance(item, dict) for item in artifact['mappings']):
        raise ValidationError('Daftar pemetaan tidak valid.')
    ids = [item.get('credential_id') for item in artifact['mappings']]
    if any(type(item_id) is not int or item_id <= 0 for item_id in ids):
        raise ValidationError('ID kredensial tidak valid.')
    if len(ids) != len(set(ids)):
        raise ValidationError('Setiap kredensial hanya boleh dipetakan satu kali.')
    return hashlib.sha256(
        json.dumps(artifact, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        .encode('utf-8')
    ).hexdigest()


def _prepare_mapping(mapping):
    if not isinstance(mapping, dict) or set(mapping) != MAPPING_KEYS:
        raise ValidationError('Kolom pemetaan kredensial tidak valid.')
    if type(mapping['credential_id']) is not int or mapping['credential_id'] <= 0:
        raise ValidationError('ID kredensial tidak valid.')
    try:
        employee_id = str(UUID(mapping['employee_id']))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError('ID pegawai harus berupa UUID yang valid.') from None
    if employee_id != mapping['employee_id']:
        raise ValidationError('Format UUID pegawai harus kanonis.')
    key = mapping['storage_key']
    match = re.fullmatch(
        r'personnel/([0-9a-f-]{36})/([0-9a-f-]{36})\.(pdf|png|jpg|jpeg)',
        key if isinstance(key, str) else '',
    )
    if not match or match.group(1) != employee_id:
        raise ValidationError('Kunci objek tidak sesuai dengan pegawai.')
    try:
        if str(UUID(match.group(1))) != match.group(1) or str(UUID(match.group(2))) != match.group(2):
            raise ValueError
    except ValueError:
        raise ValidationError('Kunci objek tidak valid.') from None

    filename = mapping['original_filename']
    if not isinstance(filename, str):
        raise ValidationError('Nama berkas tidak valid.')
    filename = get_valid_filename(filename.replace('\\', '/').rsplit('/', 1)[-1])[:255]
    if not filename:
        raise ValidationError('Nama berkas tidak valid.')
    digest = mapping['sha256']
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValidationError('SHA-256 pemetaan tidak valid.')
    size = mapping['size_bytes']
    if type(size) is not int or size <= 0:
        raise ValidationError('Ukuran berkas pemetaan tidak valid.')
    content_type = mapping['content_type']
    if content_type not in ('application/pdf', 'image/png', 'image/jpeg'):
        raise ValidationError('Jenis berkas pemetaan tidak didukung.')
    ext_to_mime = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
    }
    if ext_to_mime[match.group(3)] != content_type:
        raise ValidationError('Ekstensi dan MIME berkas tidak sesuai.')
    return {
        **mapping,
        'employee_id': employee_id,
        'original_filename': filename,
    }


def _prepare_records(artifact):
    mapping_digest = _validate_mapping_artifact(artifact)
    prepared = []
    for source_mapping in artifact['mappings']:
        mapping = _prepare_mapping(source_mapping)
        credential = NakesCredential.objects.select_related(
            'user_profile__user'
        ).filter(pk=mapping['credential_id']).first()
        if credential is None:
            raise ValidationError('Artefak memuat kredensial yang tidak ditemukan.')
        employee = Pegawai.objects.filter(
            pk=mapping['employee_id'],
            akun_id=credential.user_profile.user_id,
        ).first()
        if employee is None:
            raise ValidationError(
                'Pemetaan pegawai harus cocok tepat dengan akun kredensial lama.'
            )
        link = TautanKredensialLama.objects.select_related(
            'version__document'
        ).filter(credential_id=credential.pk).first()
        if link:
            version = link.version
            if (
                version.document.employee_id != employee.pk
                or version.storage_key != mapping['storage_key']
                or version.sha256 != mapping['sha256']
                or version.size_bytes != mapping['size_bytes']
                or version.content_type != mapping['content_type']
            ):
                raise ValidationError('Pemetaan berbeda dari tautan kredensial yang sudah ada.')
        prepared.append({
            'credential': credential,
            'employee': employee,
            'mapping': mapping,
            'already_linked': link is not None,
        })
    return prepared, mapping_digest


def dry_run_credential_reconciliation(artifact=None):
    total = NakesCredential.objects.count()
    linked = TautanKredensialLama.objects.count()
    if artifact is None:
        eligible = NakesCredential.objects.exclude(
            pk__in=TautanKredensialLama.objects.values('credential_id')
        ).filter(user_profile__user__pegawai_hc__isnull=False).count()
    else:
        prepared, _digest = _prepare_records(artifact)
        eligible = sum(not row['already_linked'] for row in prepared)
        linked = TautanKredensialLama.objects.count()
    unresolved = max(0, total - linked - eligible)
    return {'total': total, 'linked': linked, 'eligible': eligible, 'unresolved': unresolved}


def apply_credential_reconciliation(artifact):
    prepared, mapping_digest = _prepare_records(artifact)
    pending = [row for row in prepared if not row['already_linked']]
    storage = get_private_storage() if pending else None
    for row in pending:
        mapping = row['mapping']
        verified = storage.verify_private_object(
            mapping['storage_key'],
            expected_sha256=mapping['sha256'],
            expected_size=mapping['size_bytes'],
            expected_content_type=mapping['content_type'],
        )
        if (
            verified.storage_key != mapping['storage_key']
            or verified.sha256 != mapping['sha256']
            or verified.size_bytes != mapping['size_bytes']
            or verified.content_type != mapping['content_type']
        ):
            raise PrivateStorageError('Private-object verification failed')

    linked = 0
    with transaction.atomic():
        for row in pending:
            credential = NakesCredential.objects.select_for_update().get(
                pk=row['credential'].pk
            )
            if TautanKredensialLama.objects.filter(credential=credential).exists():
                raise ValidationError('Kredensial berubah saat rekonsiliasi berlangsung.')
            employee = Pegawai.objects.select_for_update().get(pk=row['employee'].pk)
            status = 'VERIFIED' if credential.status == 'EXPIRED' else credential.status
            document = DokumenPegawai(
                employee=employee,
                document_type='CREDENTIAL',
                title=credential.title,
                sensitivity='personnel',
            )
            document.full_clean()
            document.save()
            mapping = row['mapping']
            version = VersiDokumen(
                document=document,
                version_number=1,
                original_filename=mapping['original_filename'],
                storage_key=mapping['storage_key'],
                sha256=mapping['sha256'],
                size_bytes=mapping['size_bytes'],
                content_type=mapping['content_type'],
                issued_date=credential.issued_date,
                valid_until=credential.valid_until,
                status=status,
                review_notes=(
                    f'Impor kredensial lama {credential.pk}; '
                    f'status sumber={credential.status}.'
                ),
            )
            version.full_clean()
            version.save()
            link = TautanKredensialLama(credential=credential, version=version)
            link.full_clean()
            link.save()
            PeristiwaSDM.objects.create(
                jenis_peristiwa='legacy_credential_linked',
                target_tipe='document_version',
                target_id=str(version.pk),
                status_sesudah=status,
                alasan=f'mapping_sha256={mapping_digest}',
            )
            linked += 1
    return {
        'linked': linked,
        'already_linked': len(prepared) - len(pending),
        'unresolved': max(
            0, NakesCredential.objects.count() - TautanKredensialLama.objects.count()
        ),
    }


def reconcile_private_inventory(*, verify_anonymous_denial=False):
    storage = get_private_storage()
    result = {
        'total': 0,
        'verified': 0,
        'missing_or_mismatched': 0,
        'anonymous_denied': 0,
        'anonymous_exposed_or_error': 0,
    }
    versions = VersiDokumen.objects.only(
        'storage_key', 'sha256', 'size_bytes', 'content_type'
    ).iterator()
    for version in versions:
        result['total'] += 1
        try:
            verified = storage.verify_private_object(
                version.storage_key,
                expected_sha256=version.sha256,
                expected_size=version.size_bytes,
                expected_content_type=version.content_type,
            )
            if (
                verified.storage_key != version.storage_key
                or verified.sha256 != version.sha256
                or verified.size_bytes != version.size_bytes
                or verified.content_type != version.content_type
            ):
                raise PrivateStorageError('Private-object verification failed')
            result['verified'] += 1
        except PrivateStorageError:
            result['missing_or_mismatched'] += 1

        if verify_anonymous_denial:
            try:
                storage.verify_anonymous_denial(version.storage_key)
                result['anonymous_denied'] += 1
            except PrivateStorageError:
                result['anonymous_exposed_or_error'] += 1
    return result
