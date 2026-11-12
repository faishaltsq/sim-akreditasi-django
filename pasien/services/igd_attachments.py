import hashlib
from pathlib import Path
from django import forms
from pasien.forms_igd_operations import OperationForm
from pasien.models import LampiranAsesmen
from .igd_assessment_workflow import WorkflowValidation


class MetadataForm(OperationForm):
    jenis = forms.ChoiceField(choices=LampiranAsesmen.JENIS)
    filename = forms.CharField(max_length=255)
    size = forms.IntegerField(min_value=1,max_value=10*1024*1024)
    sha256 = forms.RegexField(r'^[a-f0-9]{64}$')


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
    record.file.save(values['filename'],uploaded,save=False)
    uploaded._igd_saved_name = record.file.name
    record.save()
    return {'attachment_id':record.pk}
