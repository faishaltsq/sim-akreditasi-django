import hashlib
import logging
import os
from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from django import forms
from django.conf import settings
from django.core.files.storage import default_storage
from akreditasi.storage import SupabaseMediaStorage
from sdm.storage_backend import PrivateStorageError, SupabasePrivateStorage
from pasien.forms_igd_operations import OperationForm
from pasien.models import LampiranAsesmen
from .igd_assessment_workflow import WorkflowValidation


class MetadataForm(OperationForm):
    jenis = forms.ChoiceField(choices=LampiranAsesmen.JENIS)
    filename = forms.CharField(max_length=255)
    size = forms.IntegerField(min_value=1,max_value=10*1024*1024)
    sha256 = forms.RegexField(r'^[a-f0-9]{64}$')


PRIVATE_PREFIX = 'igd-private/'


def private_storage():
    return SupabasePrivateStorage(
        base_url=getattr(settings,'SUPABASE_URL',''),
        api_key=os.environ.get('IGD_PRIVATE_STORAGE_SERVICE_KEY') or os.environ.get('HC_PRIVATE_STORAGE_SERVICE_KEY',''),
        bucket=getattr(settings,'IGD_PRIVATE_STORAGE_BUCKET','igd-clinical-private'),
    )


def cleanup_attachment(uploaded):
    name = getattr(uploaded,'_igd_saved_name',None)
    if not name:
        return
    try:
        if name.startswith(PRIVATE_PREFIX):
            private_storage().delete(name[len(PRIVATE_PREFIX):])
        else:
            default_storage.delete(name)
        uploaded._igd_saved_name = None
    except Exception:
        logging.getLogger(__name__).error('IGD attachment cleanup failed after rollback.')


def attachment_file(record):
    if record.file.name.startswith(PRIVATE_PREFIX):
        data = private_storage().fetch_object(record.file.name[len(PRIVATE_PREFIX):],max_bytes=10*1024*1024)
        if len(data) != record.ukuran:
            raise PrivateStorageError('Attachment size mismatch')
        return BytesIO(data)
    if isinstance(default_storage,SupabaseMediaStorage):
        import requests
        try:
            with requests.get(record.file.url,stream=True,timeout=15,allow_redirects=False) as response:
                if response.status_code != 200:
                    raise PrivateStorageError('Legacy attachment unavailable')
                chunks, size = [], 0
                for chunk in response.iter_content(chunk_size=65536):
                    size += len(chunk)
                    if size > 10*1024*1024:
                        raise PrivateStorageError('Attachment exceeds download limit')
                    chunks.append(chunk)
                return BytesIO(b''.join(chunks))
        except requests.RequestException:
            raise PrivateStorageError('Attachment unavailable') from None
    return record.file.open('rb')


def store_attachment(visit, workflow, user, data, uploaded):
    from .igd_actions import validate
    values = validate(MetadataForm,data)
    if uploaded is None or uploaded.size != values['size'] or Path(uploaded.name).name != values['filename']:
        raise WorkflowValidation({'file':['Berkas atau metadata tidak cocok.']})
    content = uploaded.read()
    uploaded.seek(0)
    extension = Path(uploaded.name).suffix.lower()
    valid_magic = (extension=='.pdf' and content.startswith(b'%PDF-')) or (extension=='.png' and content.startswith(b'\x89PNG\r\n\x1a\n')) or (extension in ('.jpg','.jpeg') and content.startswith(b'\xff\xd8\xff'))
    if not valid_magic or hashlib.sha256(content).hexdigest() != values['sha256']:
        raise WorkflowValidation({'file':['Gunakan PDF, PNG atau JPEG dengan isi/ekstensi yang sesuai.']})
    record = LampiranAsesmen(kunjungan=visit,jenis=values['jenis'],nama_asli=values['filename'],
                              ukuran=uploaded.size,diunggah_oleh=user)
    try:
        if isinstance(default_storage,SupabaseMediaStorage):
            backend = private_storage()
            mime = {'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}[extension]
            stored = backend.upload(uploaded,owner_id=str(uuid5(NAMESPACE_URL,f'igd-visit:{visit.pk}')),
                sensitivity='health',filename=values['filename'],content_type=mime)
            uploaded._igd_saved_name = PRIVATE_PREFIX + stored.storage_key
            backend.verify_private_object(stored.storage_key,expected_sha256=values['sha256'],
                expected_size=uploaded.size,expected_content_type=mime)
            if not backend.verify_anonymous_denial(stored.storage_key):
                raise PrivateStorageError('Clinical object is not private')
            record.file = uploaded._igd_saved_name
        else:
            record.file.save(values['filename'],uploaded,save=False)
            uploaded._igd_saved_name = record.file.name
        record.save()
    except PrivateStorageError:
        cleanup_attachment(uploaded)
        raise WorkflowValidation({'file':['Storage privat tidak tersedia; lampiran belum disimpan.']}) from None
    except Exception:
        cleanup_attachment(uploaded)
        raise
    return {'attachment_id':record.pk}
