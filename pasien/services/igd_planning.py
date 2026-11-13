from django.core import signing
from django.utils import timezone
from klinis.models import MasterIcd10, SdkiDiagnosis, SlkiLuaran, SikiIntervensi, Pemetaan3S
from .igd_assessment_workflow import WorkflowValidation


def code_of(value):
    return str(value or '').split(' — ',1)[0].strip()


def validate_planning(visit, user, payload, version):
    from django.core.exceptions import PermissionDenied
    nursing={'diagnosa_keperawatan_sdki','luaran_keperawatan_slki','intervensi_keperawatan_siki'}
    for field in nursing | {'diagnosa_masuk','tatalaksana_resusitasi','tatalaksana_terapi'}:
        if field in payload and payload[field]!=getattr(visit,field):
            allowed={'PERAWAT','BIDAN'} if field in nursing else {'DOKTER_UMUM','DOKTER_SPESIALIS'}
            if user.profile.profesi not in allowed:
                raise PermissionDenied('Perubahan komponen tidak sesuai profesi.')
    if 'component_modes' in payload or visit.diagnosis_provenance.get('schema_version') == 2:
        from .igd_planning_components import validate_components
        return validate_components(visit,user,payload,version)
    values = dict(payload)
    mode = values.get('diagnosis_mode',visit.diagnosis_mode)
    diagnosis_fields = ('diagnosa_masuk','diagnosa_keperawatan_sdki','luaran_keperawatan_slki','intervensi_keperawatan_siki')
    effective = {field:values.get(field,getattr(visit,field)) for field in diagnosis_fields}
    provenance = {'mode':mode,'accepted_by':user.pk,'accepted_at':timezone.now().isoformat()}
    if mode == 'AI':
        ticket = values.pop('ai_ticket',None)
        if not ticket:
            if visit.diagnosis_provenance.get('mode') != 'AI' or any(effective[f] != getattr(visit,f) for f in diagnosis_fields):
                raise WorkflowValidation({'diagnosis_mode':['Terima kandidat dari respons AI yang sah atau pilih Manual/Master.']})
            provenance = visit.diagnosis_provenance
        else:
            try:
                claims = signing.loads(ticket,salt='igd-ai-suggestion',max_age=900)
                if claims['visit'] != visit.pk or claims['user'] != user.pk or claims['version'] != version:
                    raise ValueError('binding')
                if effective['diagnosa_masuk'] != visit.diagnosa_masuk and effective['diagnosa_masuk'] and code_of(effective['diagnosa_masuk']) not in claims['medical']:
                    raise ValueError('medical code')
                if effective['diagnosa_keperawatan_sdki'] != visit.diagnosa_keperawatan_sdki and effective['diagnosa_keperawatan_sdki'] and code_of(effective['diagnosa_keperawatan_sdki']) not in claims['nursing']:
                    raise ValueError('nursing code')
                provenance['accepted_fields'] = [field for field in diagnosis_fields if effective[field] != getattr(visit,field)]
                provenance['candidate_codes'] = {'medical':claims['medical'],'nursing':claims['nursing']}
            except (signing.BadSignature,KeyError,TypeError,ValueError) as exc:
                raise WorkflowValidation({'ai_ticket':['Kandidat AI kedaluwarsa atau tidak sesuai episode/data terpilih.']}) from exc
    if mode in ('MASTER','AI'):
        for field, model in [('diagnosa_masuk',MasterIcd10),('diagnosa_keperawatan_sdki',SdkiDiagnosis)]:
            if mode == 'AI' and effective[field] == getattr(visit,field):
                continue
            if effective[field]:
                master = model.objects.filter(kode=code_of(effective[field])).first()
                if not master:
                    raise WorkflowValidation({field:['Kode tidak ditemukan pada master.']})
                values[field] = f'{master.kode} — {master.nama}'
        sdkicode = code_of(effective['diagnosa_keperawatan_sdki'])
        if mode == 'AI' and not any(effective[field] != getattr(visit,field) for field in diagnosis_fields[1:]):
            sdkicode = ''
        if sdkicode:
            mapped = Pemetaan3S.objects.filter(sdki__kode=sdkicode)
            for field, model, relation in [('luaran_keperawatan_slki',SlkiLuaran,'slki'),('intervensi_keperawatan_siki',SikiIntervensi,'siki')]:
                if effective[field]:
                    codes = [code_of(line) for line in str(effective[field]).splitlines() if line.strip()]
                    allowed = set(mapped.values_list(relation+'__kode',flat=True))
                    if any(code not in allowed for code in codes):
                        raise WorkflowValidation({field:['Kode tidak sesuai pemetaan SDKI terpilih; gunakan Manual jika perlu koreksi.']})
                    labels = {r.kode:r.nama for r in model.objects.filter(kode__in=codes)}
                    values[field] = '\n'.join(f'{code} — {labels[code]}' for code in dict.fromkeys(codes))
    values.pop('ai_ticket',None)
    return values, provenance
