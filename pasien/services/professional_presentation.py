"""Snapshot-only readers and bounded presentation data for step 9."""
from django.conf import settings
from copy import deepcopy
from django.utils import timezone
from .professional_cppt import FIELDS,note_snapshot
from .professional_billing import professional_billing_summary

LABELS={'subjektif':'S — Subjektif','objektif':'O — Objektif','asesmen':'A — Asesmen','plan':'P — Rencana','asesmen_gizi':'Asesmen gizi','diagnosis_gizi':'Diagnosis gizi','intervensi':'Intervensi','monitoring':'Monitoring','evaluasi':'Evaluasi','kondisi_psikospiritual':'Kondisi psikospiritual','pendampingan':'Pendampingan','respon_pasien':'Respons pasien'}


def snapshot_professional_care(visit):
    notes=[]
    for note in visit.cppt.order_by('pk').prefetch_related('care_revisions__verification'):
        entry=note_snapshot(note)
        revision=next((r for r in note.care_revisions.all() if r.version==note.version),None)
        verification=getattr(revision,'verification',None) if revision else None
        entry.update(author_name=note.nama_ppa,profession=note.profesi,
                     verification={'verifier_id':verification.verifier_id,'verifier_name':verification.verifier_name,'at':verification.performed_at.isoformat(),'digest':verification.digest,'assignment_id':verification.assignment_id,'assignment_snapshot':verification.assignment_snapshot} if verification else None,
                     historical_unattributed=note.status=='LEGACY' and note.verifikasi_dpjp)
        notes.append(entry)
    return {'notes':notes,'billing':professional_billing_summary(visit),
            'actions':list(visit.tindakan_asesmen.order_by('pk').values('id','nama','execution_status','quantity','professional_service_id','professional_snapshot','price_snapshot','financial_status','execution_cppt_id','billing_item_id','performed_at','recorded_at')),
            'charges':list(visit.billing.order_by('pk').values('id','nama_item','kuantitas','harga_satuan','is_void','professional_price_snapshot')),
            'voids':list(visit.billing.filter(void_record__isnull=False).values('id','void_record__amount','void_record__reason','void_record__actor_id','void_record__created_at'))}


def professional_panel_context(visit,workflow,actor,revision=None):
    from pasien.models import PenugasanDpjpEpisode
    from sdm.services.professional_care import has_grant
    enabled=getattr(settings,'IGD_PROFESSIONAL_CARE_ENABLED',False)
    historical=bool(workflow and workflow.status=='FINAL' and revision)
    data=deepcopy(revision.snapshot.get('professional_care',{})) if historical else snapshot_professional_care(visit)
    if historical and 'professional_care' not in revision.snapshot:
        data={'actions':deepcopy(revision.snapshot.get('actions',[])),'notes':[{'id':row.get('id'),'format_code':'SOAP','status':'LEGACY','version':None,'author_name':row.get('nama_ppa',''),
                       'actual_at':row.get('tanggal'),'recorded_at':None,'author_id':row.get('created_by_id'),'professional_snapshot':{},
                       'content':{key:row.get(key,'') for key in FIELDS['SOAP']},'verification':None,'historical_unattributed':bool(row.get('verifikasi_dpjp'))}
                      for row in revision.snapshot.get('cppt',[])]}
    show=historical or enabled or bool(data.get('actions') and any(row.get('professional_service_id') for row in data['actions'])) or any(note.get('status')!='LEGACY' for note in data.get('notes',[]))
    editable=enabled and settings.IGD_WORKFLOW_ENABLED and visit.jenis_kunjungan=='IGD' and visit.status not in {'PULANG','RUJUK','MENINGGAL','BATAL'} and not historical and actor.profile.role!='ASESOR'
    today=timezone.localdate()
    dpjp=editable and PenugasanDpjpEpisode.objects.filter(visit=visit,doctor=actor,unit_id=visit.unit_kerja_id,is_active=True,valid_from__lte=today,valid_until__gte=today).exists()
    for note in data.get('notes',[]):
        reasons=note.get('content',{}).get('unavailable_reasons',{})
        note['fields']=[{'key':key,'label':LABELS[key],'value':note.get('content',{}).get(key) or ('Tidak tercatat: '+reasons[key] if reasons.get(key) else 'Belum tercatat')} for key in FIELDS.get(note.get('format_code'),FIELDS['SOAP'])]
        note['can_edit']=editable and note.get('author_id')==actor.pk and note.get('status')!='LEGACY'
        note['can_verify']=bool(dpjp and note.get('status')=='SIGNED' and not note.get('verification'))
    can_void=bool(editable and has_grant(actor,visit,'VOID_UNPAID_CHARGE',at=timezone.now()))
    return {'professional_show':show,'professional_enabled':enabled,'professional_can_edit':editable,
            'professional_data':data,'professional_notes':data.get('notes',[]),'professional_totals':data.get('billing'),
            'professional_can_void':can_void,'professional_note_formats':[{'code':code,'fields':[{'key':key,'label':LABELS[key]} for key in fields]} for code,fields in FIELDS.items()]}
