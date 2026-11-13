from django.core import signing
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from klinis.models import MasterIcd10, SdkiDiagnosis, SlkiLuaran, SikiIntervensi, Pemetaan3S
from .igd_assessment_workflow import WorkflowValidation

COMPONENTS={'medical':('diagnosa_masuk',MasterIcd10),'sdki':('diagnosa_keperawatan_sdki',SdkiDiagnosis),
            'slki':('luaran_keperawatan_slki',SlkiLuaran),'siki':('intervensi_keperawatan_siki',SikiIntervensi)}


def validate_components(visit,user,payload,version):
    from .igd_planning import code_of
    values=dict(payload); modes=values.pop('component_modes',{})
    tickets=values.pop('component_tickets',{})
    if not isinstance(modes,dict) or set(modes)-set(COMPONENTS) or not isinstance(tickets,dict) or set(tickets)-set(COMPONENTS):
        raise WorkflowValidation({'component_modes':['Komponen tidak dikenal.']})
    provenance=dict(visit.diagnosis_provenance or {})
    stored=dict(provenance.get('components',{})); profession=user.profile.profesi
    effective={key:values.get(field,getattr(visit,field)) for key,(field,_) in COMPONENTS.items()}
    for key,(field,model) in COMPONENTS.items():
        mode=modes.get(key,stored.get(key,{}).get('mode','MANUAL'))
        changed=field in values and values[field]!=getattr(visit,field)
        if key not in modes and not changed:
            continue
        if (key=='medical' and profession not in ('DOKTER_UMUM','DOKTER_SPESIALIS')) or (key!='medical' and profession not in ('PERAWAT','BIDAN')):
            raise PermissionDenied('Komponen ini hanya dapat diubah profesi penanggung jawabnya.')
        if mode not in ('MANUAL','MASTER','AI') or not isinstance(effective[key],str) or len(effective[key])>10000:
            raise WorkflowValidation({field:['Mode/nilai komponen tidak valid.']})
        codes=[code_of(line) for line in effective[key].splitlines() if line.strip()]
        if key in ('medical','sdki') and len(codes)>1 and mode!='MANUAL':
            raise WorkflowValidation({field:['Pilih satu kode pada komponen ini.']})
        if mode in ('MASTER','AI'):
            records={r.kode:r for r in model.objects.filter(kode__in=codes)}
            if any(code not in records for code in codes):
                raise WorkflowValidation({field:['Kode tidak ditemukan pada katalog.']})
            if key in ('slki','siki') and codes:
                sdkicode=code_of(effective['sdki'])
                qs=Pemetaan3S.objects.filter(sdki__kode=sdkicode)
                if key=='siki' and modes.get('slki',stored.get('slki',{}).get('mode')) in ('MASTER','AI'):
                    qs=qs.filter(slki__kode__in=[code_of(s) for s in effective['slki'].splitlines()])
                if set(codes)-set(qs.values_list(key+'__kode',flat=True)):
                    raise WorkflowValidation({field:['Kode tidak sesuai hubungan 3S terpilih. Gunakan Manual untuk koreksi di luar pemetaan.']})
            values[field]='\n'.join(f'{code} — {records[code].nama}' for code in dict.fromkeys(codes))
        preserved_ai=mode=='AI' and not changed and stored.get(key,{}).get('mode')=='AI'
        if mode=='AI' and not preserved_ai:
            try:
                claim=signing.loads(tickets.get(key,''),salt='igd-ai-target',max_age=900)
                if claim['visit']!=visit.pk or claim['user']!=user.pk or claim['version']!=version or claim['target']!=key or set(codes)-set(claim['codes']):
                    raise ValueError('binding')
            except (ValueError,KeyError,TypeError,signing.BadSignature) as exc:
                raise WorkflowValidation({field:['Kandidat AI tidak sesuai komponen/versi.']}) from exc
        if not preserved_ai:
            stored[key]={'mode':mode,'accepted_by':user.pk,'accepted_at':timezone.now().isoformat()}
    provenance.update(schema_version=2,components=stored)
    values.pop('ai_ticket',None)
    values.pop('diagnosis_mode',None)
    return values,provenance
