import logging
import os

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.text import get_valid_filename

from sdm.akses import require_hc_capability
from sdm.models import DokumenPegawai, PeristiwaSDM, VersiDokumen
from sdm.storage_backend import PrivateStorageError, SupabasePrivateStorage


logger = logging.getLogger(__name__)


def get_private_storage():
    return SupabasePrivateStorage(
        base_url=getattr(settings, 'SUPABASE_URL', '') or '',
        api_key=os.environ.get('HC_PRIVATE_STORAGE_SERVICE_KEY', ''),
        bucket=getattr(settings, 'HC_PRIVATE_STORAGE_BUCKET', 'human-capital-private'),
    )


def _safe_original_filename(file_obj):
    raw_name = getattr(file_obj, 'name', '')
    if not isinstance(raw_name, str):
        raise ValidationError({'file': 'Nama berkas tidak valid.'})
    name = raw_name.replace('\\', '/').rsplit('/', 1)[-1]
    safe_name = get_valid_filename(name)[:255]
    if not safe_name:
        raise ValidationError({'file': 'Nama berkas tidak valid.'})
    return safe_name


def _is_own_credential(user, document):
    return (
        document.sensitivity == 'personnel'
        and document.document_type == 'CREDENTIAL'
        and document.employee.akun_id == getattr(user, 'pk', None)
        and getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_active', False)
    )


def _authorize_document_write(user, document):
    if _is_own_credential(user, document):
        return
    capability = (
        'hc_health_write'
        if document.sensitivity == 'health'
        else 'can_manage_hc_documents'
    )
    require_hc_capability(user, capability, employee=document.employee)


def _cleanup_uploaded_object(storage, storage_key):
    try:
        storage.delete(storage_key)
    except PrivateStorageError:
        logger.error('Private-object cleanup failed after document rollback.')


def store_private_document(
    file_obj,
    *,
    employee,
    sensitivity,
    document_type,
    title,
    uploaded_by,
    issued_date=None,
    valid_until=None,
):
    if sensitivity not in dict(DokumenPegawai.SENSITIVITY_CHOICES):
        raise ValidationError({'sensitivity': 'Klasifikasi dokumen tidak valid.'})
    if not getattr(employee, 'pk', None):
        raise ValidationError({'employee': 'Pegawai harus tersimpan terlebih dahulu.'})

    document = DokumenPegawai(
        employee=employee,
        document_type=document_type,
        title=title,
        sensitivity=sensitivity,
        created_by=uploaded_by,
    )
    _authorize_document_write(uploaded_by, document)
    document.full_clean()
    filename = _safe_original_filename(file_obj)
    storage = get_private_storage()
    stored = storage.upload(
        file_obj,
        owner_id=str(employee.pk),
        sensitivity=sensitivity,
        filename=filename,
        content_type=getattr(file_obj, 'content_type', ''),
    )

    try:
        with transaction.atomic():
            document.save()
            version = VersiDokumen(
                document=document,
                version_number=1,
                original_filename=filename,
                storage_key=stored.storage_key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                issued_date=issued_date,
                valid_until=valid_until,
                created_by=uploaded_by,
            )
            version.full_clean()
            version.save()
            PeristiwaSDM.objects.create(
                actor=uploaded_by,
                jenis_peristiwa='private_document_uploaded',
                target_tipe='document_version',
                target_id=str(version.pk),
                status_sesudah='PENDING',
                alasan=f'sensitivity={sensitivity}',
            )
    except Exception:
        _cleanup_uploaded_object(storage, stored.storage_key)
        raise PrivateStorageError('Document record could not be committed') from None

    return document, version


def store_document_version(
    file_obj,
    *,
    document,
    uploaded_by,
    issued_date=None,
    valid_until=None,
):
    if not getattr(document, 'pk', None):
        raise ValidationError({'document': 'Dokumen harus tersimpan terlebih dahulu.'})
    _authorize_document_write(uploaded_by, document)
    filename = _safe_original_filename(file_obj)
    storage = get_private_storage()
    stored = storage.upload(
        file_obj,
        owner_id=str(document.employee_id),
        sensitivity=document.sensitivity,
        filename=filename,
        content_type=getattr(file_obj, 'content_type', ''),
    )

    try:
        with transaction.atomic():
            locked_document = DokumenPegawai.objects.select_for_update().get(pk=document.pk)
            previous = list(
                locked_document.versions.select_for_update().order_by('-version_number')
            )
            version = VersiDokumen(
                document=locked_document,
                version_number=(previous[0].version_number + 1) if previous else 1,
                original_filename=filename,
                storage_key=stored.storage_key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                issued_date=issued_date,
                valid_until=valid_until,
                status='PENDING',
                created_by=uploaded_by,
            )
            version.full_clean()
            version.save()
            for old_version in previous:
                if old_version.status != 'SUPERSEDED':
                    old_status = old_version.status
                    old_version.status = 'SUPERSEDED'
                    old_version.save(update_fields=['status'])
                    PeristiwaSDM.objects.create(
                        actor=uploaded_by,
                        jenis_peristiwa='private_document_superseded',
                        target_tipe='document_version',
                        target_id=str(old_version.pk),
                        status_sebelum=old_status,
                        status_sesudah='SUPERSEDED',
                        alasan=f'replaced_by_version={version.version_number}',
                    )
            PeristiwaSDM.objects.create(
                actor=uploaded_by,
                jenis_peristiwa='private_document_uploaded',
                target_tipe='document_version',
                target_id=str(version.pk),
                status_sesudah='PENDING',
                alasan=(
                    f'sensitivity={locked_document.sensitivity}; '
                    f'version={version.version_number}'
                ),
            )
    except Exception:
        _cleanup_uploaded_object(storage, stored.storage_key)
        raise PrivateStorageError('Document record could not be committed') from None

    return version


def review_document_version(reviewer, version, *, status, notes=''):
    if status not in {'PENDING', 'VERIFIED', 'REJECTED'}:
        raise ValidationError({'status': 'Status tinjauan tidak valid.'})
    if not isinstance(notes, str):
        raise ValidationError({'notes': 'Catatan tinjauan tidak valid.'})
    require_hc_capability(
        reviewer,
        'can_review_hc_credentials',
        employee=version.document.employee,
    )
    if version.created_by_id == getattr(reviewer, 'pk', None):
        raise PermissionDenied('Pengunggah tidak dapat meninjau dokumennya sendiri.')

    from django.utils import timezone

    with transaction.atomic():
        locked = VersiDokumen.objects.select_for_update().select_related(
            'document__employee'
        ).get(pk=version.pk)
        if locked.status == 'SUPERSEDED' or locked.document.versions.filter(
            version_number__gt=locked.version_number
        ).exists():
            raise ValidationError({'status': 'Versi yang sudah digantikan tidak dapat ditinjau.'})
        if locked.status not in {'PENDING', 'VERIFIED', 'REJECTED'}:
            raise ValidationError({'status': 'Transisi status tinjauan tidak valid.'})

        old_status = locked.status
        locked.status = status
        locked.review_notes = notes
        locked.reviewed_by = reviewer if status != 'PENDING' else None
        locked.reviewed_at = timezone.now() if status != 'PENDING' else None
        locked.full_clean()
        locked.save(update_fields=[
            'status', 'review_notes', 'reviewed_by', 'reviewed_at'
        ])
        PeristiwaSDM.objects.create(
            actor=reviewer,
            jenis_peristiwa='private_document_reviewed',
            target_tipe='document_version',
            target_id=str(locked.pk),
            status_sebelum=old_status,
            status_sesudah=status,
            alasan='credential review completed',
        )
    return locked


def authorize_document_download(user, version, *, expires_in=None):
    document = version.document
    if document.sensitivity == 'health':
        capability = 'hc_health_read'
    elif document.sensitivity == 'personnel':
        capability = 'can_view_hc'
    else:
        raise PermissionDenied('Klasifikasi dokumen tidak tersedia.')

    if not _is_own_credential(user, document):
        try:
            require_hc_capability(user, capability, employee=document.employee)
        except PermissionDenied:
            if document.document_type != 'CREDENTIAL':
                raise
            require_hc_capability(
                user,
                'can_review_hc_credentials',
                employee=document.employee,
            )
    storage = get_private_storage()
    signed_url = storage.create_signed_download(
        version.storage_key, expires_in=expires_in
    )
    with transaction.atomic():
        PeristiwaSDM.objects.create(
            actor=user,
            jenis_peristiwa='private_document_download',
            target_tipe='document_version',
            target_id=str(version.pk),
            status_sesudah='signed_url_issued',
            alasan=f'sensitivity={document.sensitivity}',
        )
    return signed_url
