"""Scoped operation adapters consumed by the existing version/replay transaction."""
from django import forms
from django.conf import settings
from django.core.exceptions import PermissionDenied,ValidationError
from django.db.models import Max
from django.utils import timezone
from klinis.models import LayananProfesional
from klinis.services.professional_tariffs import quote_professional_service,decimal_value
from pasien.models import TindakanAsesmen,BillingItem,CPPT
from .igd_assessment_workflow import WorkflowConflict
from sdm.services.professional_care import resolve_professional_context,require_scope

PRO_OPERATIONS={'professional_execute','professional_void','cppt_create','cppt_save','cppt_sign','cppt_verify','cppt_correct'}


def _service(data):
    try:return LayananProfesional.objects.get(pk=int(data.get('service_id')))
    except (ValueError,TypeError,LayananProfesional.DoesNotExist) as exc:raise ValidationError('Layanan tidak ditemukan.') from exc


def _occurred(data):
    value=forms.DateTimeField(required=False).clean(data.get('occurred_at')) or timezone.now()
    now=timezone.now()
    reason=data.get('retrospective_reason','')
    if not isinstance(reason,str) or len(reason)>2000 or value>now or ((now-value).total_seconds()>60 and len(reason.strip())<5):raise ValidationError('Waktu di masa depan tidak valid; waktu retrospektif memerlukan alasan.')
    return value


def authorize_professional_operation(operation,visit,workflow,actor,data):
    from .professional_billing import void_authorized
    from .professional_cppt import _writable
    if not getattr(settings,'IGD_PROFESSIONAL_CARE_ENABLED',False):raise PermissionDenied('Layanan profesional belum diaktifkan.')
    require_scope(actor,visit);_writable(visit,workflow)
    if operation=='professional_void':
        line=TindakanAsesmen.objects.filter(kunjungan=visit,billing_item_id=data.get('billing_id'),professional_service__isnull=False).first()
        if not line:raise PermissionDenied('Tagihan di luar kepemilikan layanan ini.')
        void_authorized(actor,visit,line.professional_service)
    elif operation=='cppt_verify':
        from .professional_cppt import verification_authority
        note=CPPT.objects.get(pk=data.get('note_id'),kunjungan=visit)
        verification_authority(actor,visit,note)
    elif operation in {'cppt_save','cppt_sign','cppt_correct'}:
        note=CPPT.objects.get(pk=data.get('note_id'),kunjungan=visit)
        if note.created_by_id!=actor.pk or not note.professional_snapshot:raise PermissionDenied('Catatan bukan milik penulis.')
        resolve_professional_context(actor,visit,LayananProfesional.objects.get(pk=note.professional_snapshot['service_id']),at=timezone.now(),supervisor=(note.professional_snapshot.get('supervisor') or {}).get('performer_id'),for_update=True)
    else:
        resolve_professional_context(actor,visit,_service(data),at=_occurred(data) if operation=='professional_execute' else timezone.now(),performer=data.get('performer'),supervisor=data.get('supervisor'),for_update=True)


def execute_professional(visit,workflow,actor,data):
    from .professional_cppt import create_care_note
    allowed={'source','action_id','service_id','quantity','occurred_at','retrospective_reason','quote_fingerprint','performer','supervisor'}
    if set(data)-allowed or data.get('source') not in {'PLANNED','DIRECT'}:raise ValidationError('Intent pelaksanaan tidak valid.')
    service=_service(data);occurred=_occurred(data)
    context=resolve_professional_context(actor,visit,service,at=occurred,performer=data.get('performer'),supervisor=data.get('supervisor'),for_update=True)
    quantity=decimal_value(data.get('quantity','1'),quantity=True)
    quote=quote_professional_service(visit,context,service,at=occurred,quantity=quantity,for_update=True)
    if data.get('quote_fingerprint')!=quote['fingerprint']:raise WorkflowConflict('Harga/kewenangan/penjamin berubah; tinjau ulang preview.')
    if quote['status']=='UNPRICED' and not service.allow_unpriced:raise ValidationError('Tarif belum ditetapkan; kebijakan pencatatan pending belum disetujui.')
    line=None
    if data['source']=='PLANNED':
        line=TindakanAsesmen.objects.select_for_update().filter(pk=data.get('action_id'),kunjungan=visit).first()
        matches=line and (line.professional_service_id==service.pk or not line.professional_service_id and ((line.jenis=='BEBAS' and line.kode==service.code) or service.icd9_id and line.icd9_id==service.icd9_id or service.siki_id and line.siki_id==service.siki_id))
        if not matches or line.quantity!=quantity:raise ValidationError('Layanan/kuantitas tidak sesuai rencana.')
        if line.execution_status=='PERFORMED':
            if line.professional_snapshot.get('performer_id')!=context['performer_id'] or line.price_snapshot.get('fingerprint')!=quote['fingerprint']:raise WorkflowConflict('Pelaksanaan terdahulu berbeda; bukan layanan baru.')
            return {'action_id':line.pk,'cppt_id':line.execution_cppt_id,'billing_id':line.billing_item_id}
        if line.execution_status!='PLANNED' or line.tarif_penjamin!=visit.penjamin:raise WorkflowConflict('Status rencana/penjamin berubah.')
        if line.billing_item_id or line.execution_cppt_id:raise WorkflowConflict('Rencana sudah terhubung ke catatan/tagihan; tinjau kepemilikan historis.')
    elif data.get('action_id'):raise ValidationError('Pelaksanaan langsung tidak boleh menunjuk rencana tersembunyi.')
    if line is None:
        sequence=(visit.tindakan_asesmen.aggregate(n=Max('urutan'))['n'] or 0)+1
        line=TindakanAsesmen(kunjungan=visit,urutan=sequence,jenis='BEBAS',kode=service.code,nama=service.name,execution_status='PLANNED',tarif_penjamin=visit.penjamin,quantity=quantity)
    line.professional_service=service;line.professional_snapshot=context;line.price_snapshot=quote
    line.execution_status='PERFORMED';line.performed_by_id=context['performer_account_id'];line.performed_at=occurred;line.recorded_at=timezone.now()
    line.financial_status='PENDING' if quote['status']=='UNPRICED' else quote['status'];line.tarif_acuan=quote['unit_total'];line.tarif=None
    line.execution_team={'MEDICAL':'MEDIS','NURSING':'KEPERAWATAN'}.get(context['group'],'')
    if data.get('retrospective_reason'):line.catatan_klinis+='\nPencatatan retrospektif: '+data['retrospective_reason']
    line.save()
    fmt='ADIME' if context['profession_code'] in {'DIET','NUTR'} else 'SPIRITUAL' if service.authority_kind=='SUPPORT' else service.note_format
    note=create_care_note(visit,workflow,actor,format_code=fmt,payload={},context=context,source_action=line)
    if quote['status']!='UNPRICED':
        line.billing_item=BillingItem.objects.create(kunjungan=visit,kategori='JASA_MEDIS',nama_item=line.nama,kode_icd=line.kode,sumber='PROFESI',kuantitas=quantity,harga_satuan=quote['unit_total'],dicatat_oleh=actor,professional_price_snapshot=quote)
    line.execution_cppt=note;line.save(professional_update=True,update_fields=['billing_item','execution_cppt'])
    return {'action_id':line.pk,'cppt_id':note.pk,'billing_id':line.billing_item_id,'financial_status':line.financial_status}


def dispatch_professional(operation,visit,workflow,actor,data,request_id):
    from .professional_cppt import create_care_note,save_care_note,sign_care_note,verify_cppt,correct_care_note
    if operation=='professional_execute':return execute_professional(visit,workflow,actor,data)
    if operation=='professional_void':
        from .professional_billing import _void_charge
        if set(data)-{'billing_id','reason'}:raise ValidationError('Field void tidak valid.')
        return _void_charge(visit,workflow,actor,data,request_id)
    if operation=='cppt_create':
        if set(data)-{'service_id','format_code','payload'}:raise ValidationError('Field CPPT tidak valid.')
        service=_service(data);context=resolve_professional_context(actor,visit,service,at=timezone.now(),for_update=True)
        note=create_care_note(visit,workflow,actor,format_code=data.get('format_code'),payload=data.get('payload'),context=context)
        return {'cppt_id':note.pk,'note_version':note.version}
    allowed={'note_id','note_version'}|({'payload'} if operation=='cppt_save' else {'payload','reason'} if operation=='cppt_correct' else set())
    if set(data)-allowed:raise ValidationError('Field operasi CPPT tidak valid.')
    if operation=='cppt_save':return save_care_note(actor,data['note_id'],data['note_version'],data['payload'])
    if operation=='cppt_sign':return sign_care_note(actor,data['note_id'],data['note_version'])
    if operation=='cppt_verify':return verify_cppt(actor,data['note_id'],data['note_version'],request_id)
    if operation=='cppt_correct':return correct_care_note(actor,data['note_id'],data['note_version'],data['payload'],data.get('reason'))
    raise ValidationError('Operasi profesional tidak dikenal.')
