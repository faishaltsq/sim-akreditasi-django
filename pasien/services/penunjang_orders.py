from uuid import uuid4
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from klinis.services.penunjang_catalogue import resolve_items, item_snapshot
from pasien.models import OrderPenunjang
from .igd_assessment_workflow import WorkflowValidation


def order_batch(visit, workflow, user, data):
    if user.profile.profesi not in ('DOKTER_UMUM','DOKTER_SPESIALIS'):
        raise PermissionDenied('Pengiriman order memerlukan dokter.')
    if set(data)!={'items'} or not isinstance(data['items'],list):
        raise WorkflowValidation({'items':['Gunakan daftar pemeriksaan.']})
    entries=data['items']
    if any(not isinstance(e,dict) for e in entries):
        raise ValueError('Item harus berupa objek.')
    items=resolve_items(user,[e.get('item_id') for e in entries])
    batch=uuid4(); prepared=[]
    for entry,item in zip(entries,items):
        if set(entry)-{'item_id','prioritas','indication','preparation','diagnosis_id'}:
            raise ValueError('Atribut order tidak dikenal.')
        indication=entry.get('indication',''); priority=entry.get('prioritas')
        if not isinstance(indication,str) or not 1<=len(indication.strip())<=4000 or priority not in ('CITO','RUTIN'):
            raise ValueError('Indikasi dan prioritas order wajib diisi.')
        preparation=entry.get('preparation',{})
        allowed={'fasting','pregnancy','contrast_allergy','specimen','site','region','side','contrast','external_destination'}
        if not isinstance(preparation,dict) or set(preparation)-allowed:
            raise ValueError('Persiapan pemeriksaan tidak valid.')
        for field,value in preparation.items():
            if not isinstance(value,str) or len(value)>500:
                raise ValueError('Catatan persiapan maksimal 500 karakter.')
            if field in ('fasting','pregnancy','contrast_allergy') and value not in ('YES','NO','UNKNOWN','NA'):
                raise ValueError('Status persiapan tidak valid.')
        for field in item.preparation_schema.get('required',[]):
            if field not in allowed or not preparation.get(field):
                raise ValueError('Lengkapi persiapan wajib untuk pemeriksaan ini.')
        for field,choices in item.variants.items():
            if field not in allowed or preparation.get(field) not in choices:
                raise ValueError('Pilih varian pemeriksaan yang sesuai katalog.')
        diagnosis=None
        if entry.get('diagnosis_id') is not None:
            if type(entry['diagnosis_id']) is not int:
                raise ValueError('ID diagnosis tidak valid.')
            diagnosis=visit.diagnoses.filter(pk=entry['diagnosis_id'],active=True).first()
            if diagnosis is None:
                raise ValueError('Diagnosis bukan milik kunjungan ini.')
        snapshot=item_snapshot(item)
        snapshot['diagnosis']={'kode':diagnosis.kode,'nama':diagnosis.nama} if diagnosis else None
        prepared.append(dict(kunjungan=visit,catalogue_item=item,catalogue_snapshot=snapshot,batch_id=batch,
            jenis=item.jenis_order,nama_pemeriksaan=item.nama,prioritas=priority,catatan_klinis=indication.strip(),
            preparation=preparation,diagnosis=diagnosis,ordered_by=user,destination_id=item.destination_id,
            dokter_pengirim=user.get_full_name() or user.username))
    orders=[OrderPenunjang.objects.create(**fields) for fields in prepared]
    return {'order_ids':[row.pk for row in orders],'batch_id':str(batch)}
