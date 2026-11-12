import json

from django.conf import settings
from django import forms
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404
from akreditasi.security_utils import rate_limit
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from .forms_igd_workflow import STEPS, VITAL_FIELDS, form_for_step
from .services.igd_assessment_workflow import (
    CLINICAL_PROFESSIONS, WorkflowConflict, WorkflowValidation, get_visit, save_step,
)


def require_rollout():
    if not getattr(settings, 'IGD_WORKFLOW_ENABLED', False):
        raise Http404


@login_required
@require_GET
@never_cache
def igd_workflow(request, pk):
    visit, workflow = get_visit(pk, request.user)
    if not workflow:
        require_rollout()
    try:
        step = int(request.GET.get('step', workflow.last_step if workflow else 1))
        if step not in STEPS:
            raise ValueError
    except (ValueError, TypeError):
        return HttpResponseBadRequest('Langkah tidak valid.')
    form = form_for_step(step, instance=visit)
    if workflow and step in (4, 10):
        phase = 'INITIAL' if step == 4 else 'EVALUATION'
        observation = workflow.observations.filter(phase=phase).order_by('-observed_at', '-pk').first()
        if observation:
            for name in VITAL_FIELDS:
                form.initial[name] = observation.data.get(name)
    profile = request.user.profile
    readonly = bool((workflow and workflow.status == 'FINAL') or visit.jenis_kunjungan != 'IGD'
                    or visit.status in ('PULANG','RUJUK','MENINGGAL','BATAL')
                    or not settings.IGD_WORKFLOW_ENABLED or profile.role == 'ASESOR' or profile.profesi not in CLINICAL_PROFESSIONS)
    if readonly:
        for field in form.fields.values():
            field.disabled = True
    revision = workflow.revisions.order_by('-revision').first() if workflow else None
    historical = revision.snapshot.get('visit',{}) if revision and workflow.status == 'FINAL' else None
    if historical is not None:
        for name in form.fields:
            if name in historical and not (step in (4,10) and name in VITAL_FIELDS):
                form.initial[name] = historical[name]
    observations = workflow.observations.all() if workflow else []
    from .forms_igd_operations import InvestigationForm, CpptForm, ActionPlanForm, SignatureForm, FinalizationForm, AddendumForm
    from .services.igd_finalization import missing_sections
    from akreditasi.models import StandardItem, Framework
    from .models import Bed, POLIKLINIK_CHOICES
    for name in ('fisik_head_to_toe','penanda_anatomi','skrining_jatuh_detail','skrining_gizi_detail'):
        if name in form.fields:
            form.fields[name].widget = forms.HiddenInput()
    if 'disposisi_kontrol_poli' in form.fields:
        form.fields['disposisi_kontrol_poli'].widget = forms.Select(choices=[('','— Pilih Poli —'),*POLIKLINIK_CHOICES],attrs={'class':'form-select'})
    if 'waktu_kematian' in form.fields:
        form.fields['waktu_kematian'].widget = forms.DateTimeInput(format='%Y-%m-%dT%H:%M',attrs={'type':'datetime-local','class':'form-control'})
    order_form, cppt_form, plan_form = InvestigationForm(auto_id='order_%s'), CpptForm(auto_id='cppt_%s'), ActionPlanForm(auto_id='plan_%s')
    ep_items = StandardItem.objects.filter(category__framework=Framework.active()).order_by('code')
    plan_form.fields['standard_item'].widget = forms.Select(choices=[('','— EP belum dipilih —'),*[(r.pk,f'{r.code} — {r.sub_title}') for r in ep_items]],attrs={'class':'form-select'})
    final_form = FinalizationForm(auto_id='final_%s')
    final_form.fields['bed_id'].widget = forms.Select(choices=[('','— Pilih Bed —'),*[(b.pk,str(b)) for b in Bed.objects.filter(status='TERSEDIA').select_related('ruangan')]],attrs={'class':'form-select'})
    organs = [('kepala_leher','Kepala & Leher'),('mata','Mata'),('tht','THT'),('thorax','Thorax'),('abdomen','Abdomen'),('ekstremitas','Ekstremitas'),('kulit','Kulit')]
    morse = [('jatuh_riwayat','Riwayat jatuh',[(0,'Tidak'),(25,'Ya')]),('jatuh_diagnosis','Diagnosis sekunder',[(0,'Tidak'),(15,'Ya')]),('jatuh_alat','Alat bantu',[(0,'Tidak / tirah baring / dibantu perawat'),(15,'Tongkat / kruk / walker'),(30,'Berpegangan perabot')]),('jatuh_infus','Infus / akses IV',[(0,'Tidak'),(20,'Ya')]),('jatuh_jalan','Cara berjalan',[(0,'Normal / tirah baring'),(10,'Lemah'),(20,'Terganggu')]),('jatuh_mental','Status mental',[(0,'Menyadari kemampuan'),(15,'Lupa keterbatasan')])]
    actions = list(visit.tindakan_asesmen.select_related('standard_item','billing_item').all())
    from decimal import Decimal
    totals = {'medical':Decimal('0'),'nursing':Decimal('0'),'unknown':0}
    for line in actions:
        if line.execution_status == 'CANCELLED':
            continue
        if line.tarif_efektif is None:
            totals['unknown'] += 1
        else:
            totals['nursing' if line.execution_team == 'KEPERAWATAN' or line.jenis == 'SIKI' else 'medical'] += line.quantity * line.tarif_efektif
    totals['all'] = totals['medical'] + totals['nursing']
    totals['fulfilled_ep'] = len({line.standard_item_id for line in actions if line.standard_item_id and line.ep_status == 'TERPENUHI' and line.execution_status != 'CANCELLED'})
    signature_form = SignatureForm(auto_id='sign_%s',initial={'exemptions':workflow.exemptions if workflow else {}})
    signature_form.fields['exemptions'].widget = forms.HiddenInput()
    addendum_form = AddendumForm(auto_id='addendum_%s')
    section_choices = [('MEDIS','Medis')] if profile.profesi in ('DOKTER_UMUM','DOKTER_SPESIALIS') else [('KEPERAWATAN','Keperawatan')]
    signature_form.fields['section'].choices = section_choices
    addendum_form.fields['section'].choices = section_choices
    exemption_labels = [('triage','Triase'),('anamnesis','Anamnesis'),('primary_survey','Primary Survey'),('initial_vitals','TTV Awal'),('screening','Skrining'),('physical_exam','Pemeriksaan Fisik'),('diagnosis','Diagnosis'),('nursing','3S Keperawatan'),('investigations','Penunjang'),('care','Pelaksanaan Asuhan'),('evaluation','Evaluasi Akhir')]
    return render(request, 'pasien/igd_workflow.html', {
        'kunjungan': visit, 'pasien': visit.pasien, 'workflow': workflow,
        'version': workflow.version if workflow else 0,
        'steps': [{'number': n, 'title': title} for n, (title, fields) in STEPS.items()],
        'step': step, 'step_title': STEPS[step][0], 'form': form, 'readonly': readonly,
        'orders': visit.order_penunjang.all(), 'cppt': visit.cppt.all(),
        'billing': visit.billing.all(), 'observations': observations,
        'order_form':order_form,'cppt_form':cppt_form,'plan_form':plan_form,
        'signature_form':signature_form,'final_form':final_form,'addendum_form':addendum_form,
        'exemption_fields':[{'key':key,'label':label,'reason':workflow.exemptions.get(key,'') if workflow else ''} for key,label in exemption_labels],
        'clinical_actions':actions,'action_totals':totals,'rollout_enabled':settings.IGD_WORKFLOW_ENABLED,
        'can_sign_medical':profile.profesi in ('DOKTER_UMUM','DOKTER_SPESIALIS') and profile.role!='ASESOR',
        'can_sign_nursing':profile.profesi in ('PERAWAT','BIDAN') and profile.role!='ASESOR',
        'missing_sections':missing_sections(visit,workflow) if workflow else [],
        'organs':[{'key':key,'label':label,'value':(historical.get('fisik_head_to_toe',{}) if historical is not None else visit.fisik_head_to_toe).get(key,'')} for key,label in organs],
        'morse_questions':[{'key':key,'label':label,'choices':choices,'selected':(historical.get('skrining_jatuh_detail',{}) if historical is not None else visit.skrining_jatuh_detail).get(key)} for key,label,choices in morse],
        'mst_detail':historical.get('skrining_gizi_detail',{}) if historical is not None else visit.skrining_gizi_detail,
        'markers':historical.get('penanda_anatomi',[]) if historical is not None else visit.penanda_anatomi,
        'attachments':visit.lampiran_asesmen.all(),
        'latest_revision':revision,
    })


@login_required
@require_POST
@never_cache
def igd_workflow_draft(request, pk, step):
    require_rollout()
    if request.content_type != 'application/json':
        return JsonResponse({'success': False, 'error': 'Gunakan JSON.'}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or not isinstance(data.get('fields'), dict) or 'version' not in data:
            raise ValueError('Payload harus berisi fields dan version.')
        if set(data) - {'fields', 'version'}:
            raise ValueError('Atribut payload tidak valid.')
        if any(not isinstance(key, str) for key in data['fields']):
            raise ValueError('Nama field tidak valid.')
        workflow = save_step(pk, request.user, step, data['fields'], data['version'])
    except WorkflowConflict as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=409)
    except WorkflowValidation as exc:
        return JsonResponse({'success': False, 'error': str(exc), 'fields': exc.errors}, status=400)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        return JsonResponse({'success': False, 'error': 'Payload atau nilai field tidak valid.'}, status=400)
    saved_visit, _ = get_visit(pk, request.user)
    return JsonResponse({'success': True, 'version': workflow.version,
                         'values': {name:getattr(saved_visit,name) for name in STEPS[step][1]},
                         'saved_at': workflow.updated_at.isoformat(), 'step': workflow.last_step})


def _action_response(request, pk, forced=None):
    from .services.igd_actions import perform_action
    require_rollout()
    try:
        body = json.loads(request.body)
        if not isinstance(body,dict) or set(body) - {'operation','fields','version','request_id'}:
            raise ValueError('body')
        operation = forced or body.get('operation')
        if forced and body.get('operation',forced) != forced:
            raise ValueError('operation')
        result = perform_action(pk,request.user,operation,body.get('fields'),body.get('version'),body.get('request_id'))
    except WorkflowConflict as exc:
        return JsonResponse({'success':False,'error':str(exc)},status=409)
    except WorkflowValidation as exc:
        return JsonResponse({'success':False,'error':str(exc),'fields':exc.errors},status=400)
    except (ValueError,TypeError,UnicodeDecodeError):
        return JsonResponse({'success':False,'error':'Payload aksi tidak valid.'},status=400)
    return JsonResponse({'success':True,**result})


@login_required
@require_POST
@never_cache
def igd_workflow_action(request,pk):
    return _action_response(request,pk)


@login_required
@require_POST
@never_cache
def igd_workflow_finalize(request,pk):
    return _action_response(request,pk,'finalize')


@login_required
@require_POST
@never_cache
def igd_workflow_addendum(request,pk):
    return _action_response(request,pk,'addendum')


@login_required
@require_POST
@rate_limit(max_calls=5,window=60,scope='igd_clinical_ai')
@never_cache
def igd_workflow_ai(request,pk):
    require_rollout()
    visit, workflow = get_visit(pk,request.user,write=True)
    try:
        data = json.loads(request.body)
        if not isinstance(data,dict) or set(data)-{'query'} or not isinstance(data.get('query',''),str) or len(data.get('query',''))>4000:
            raise ValueError
    except (ValueError,TypeError,UnicodeDecodeError):
        return JsonResponse({'success':False,'error':'Kueri saran tidak valid.'},status=400)
    from klinis.services.ai_igd import generate_igd_suggestions
    result = generate_igd_suggestions(visit,request.user,data.get('query',''))
    if result['success']:
        result['ticket'] = signing.dumps({'visit':visit.pk,'user':request.user.pk,'version':workflow.version if workflow else 0,
            'medical':[r['kode'] for r in result['suggestions']['medical']],
            'nursing':[r['sdki_kode'] for r in result['suggestions']['nursing']]},salt='igd-ai-suggestion',compress=True)
    return JsonResponse(result,status=200 if result['success'] else 503)


@login_required
@require_GET
@never_cache
def igd_workflow_catalogue(request,pk):
    require_rollout()
    get_visit(pk,request.user)
    from klinis.models import MasterIcd10, MasterIcd9, SdkiDiagnosis, SikiIntervensi, Pemetaan3S
    q = request.GET.get('q','')[:100]
    kind = request.GET.get('type','ICD10')
    models = {'ICD10':MasterIcd10,'ICD9':MasterIcd9,'SDKI':SdkiDiagnosis,'SIKI':SikiIntervensi}
    if kind not in models:
        return JsonResponse({'error':'Jenis katalog tidak valid.'},status=400)
    rows = list(models[kind].objects.filter(Q(kode__icontains=q)|Q(nama__icontains=q)).order_by('kode').values('kode','nama')[:30])
    if kind == 'SDKI':
        for row in rows:
            mappings = Pemetaan3S.objects.filter(sdki__kode=row['kode']).select_related('slki','siki')[:30]
            row['slki'] = list({m.slki.kode:f'{m.slki.kode} — {m.slki.nama}' for m in mappings}.values())
            row['siki'] = list({m.siki.kode:f'{m.siki.kode} — {m.siki.nama}' for m in mappings}.values())
    return JsonResponse({'results':rows})


@login_required
@require_GET
@never_cache
def igd_workflow_resume(request,pk):
    visit, workflow = get_visit(pk,request.user)
    if not workflow:
        raise Http404
    revisions = workflow.revisions.order_by('-revision')
    if request.GET.get('revision'):
        try:
            revisions = revisions.filter(revision=int(request.GET['revision']))
        except ValueError:
            return HttpResponseBadRequest('Nomor revisi tidak valid.')
    revision = revisions.first()
    if not revision:
        raise Http404
    from .services.igd_actions import digest
    from .models import KunjunganPasien
    sections = [{'number':number,'title':title,'rows':[{'label':KunjunganPasien._meta.get_field(name).verbose_name,'value':revision.snapshot.get('visit',{}).get(name)} for name in names]} for number,(title,names) in STEPS.items() if names]
    return render(request,'pasien/igd_workflow_resume.html',{'record':revision,'snapshot':revision.snapshot,'workflow':workflow,'sections':sections,'record_digest':digest(revision.snapshot)})


@login_required
@require_GET
@never_cache
def igd_workflow_records(request):
    from .models import IgdAssessmentWorkflow
    from .unit_scope import get_unit_scope
    profile = getattr(request.user,'profile',None)
    if not profile or not ({'igd','riwayat'} & profile.get_allowed_patient_modules()):
        raise PermissionDenied
    scope = get_unit_scope(profile)
    qs = IgdAssessmentWorkflow.objects.filter(status='FINAL').select_related('kunjungan__pasien')
    if scope is not None:
        ids = [unit.pk for unit in scope]
        qs = qs.filter(Q(origin_unit_id__in=ids)|Q(kunjungan__unit_kerja_id__in=ids))
    return render(request,'pasien/igd_workflow_records.html',{'records':qs.order_by('-finalized_at')[:100]})


@login_required
@require_POST
@never_cache
def igd_workflow_upload(request,pk):
    import hashlib
    from pathlib import Path
    from django.core.files.storage import default_storage
    from .services.igd_actions import perform_action
    require_rollout()
    uploaded = request.FILES.get('file')
    if uploaded is None or uploaded.size > 10*1024*1024 or set(request.POST)-{'csrfmiddlewaretoken','version','request_id','jenis'}:
        return JsonResponse({'success':False,'error':'Berkas wajib, maksimal 10 MB; metadata tidak valid.'},status=400)
    checksum = hashlib.sha256()
    for chunk in uploaded.chunks():
        checksum.update(chunk)
    uploaded.seek(0)
    try:
        try:
            result = perform_action(pk,request.user,'attachment',{'jenis':request.POST.get('jenis','PENUNJANG'),
                'filename':Path(uploaded.name).name,'size':uploaded.size,'sha256':checksum.hexdigest()},
                request.POST.get('version'),request.POST.get('request_id'),attachment=uploaded)
        except Exception:
            stored = getattr(uploaded,'_igd_saved_name',None)
            if stored:
                default_storage.delete(stored)
            raise
    except WorkflowConflict as exc:
        return JsonResponse({'success':False,'error':str(exc)},status=409)
    except WorkflowValidation as exc:
        return JsonResponse({'success':False,'error':str(exc),'fields':exc.errors},status=400)
    return JsonResponse({'success':True,**result})


@login_required
@require_GET
@never_cache
def igd_workflow_download(request,pk,attachment_id):
    from django.http import FileResponse
    from .models import LampiranAsesmen
    get_visit(pk,request.user)
    record = get_object_or_404(LampiranAsesmen,pk=attachment_id,kunjungan_id=pk)
    response = FileResponse(record.file.open('rb'),as_attachment=True,filename=record.nama_asli,content_type='application/octet-stream')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
