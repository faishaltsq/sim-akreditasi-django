"""Read-only, visit-scoped professional catalogue/quote and narrowly scoped finance POST."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,ObjectDoesNotExist
from django.http import JsonResponse,Http404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_POST
from klinis.models import LayananProfesional,ProfessionalCareGrant
from sdm.models import Pegawai
from sdm.services.professional_care import require_scope,eligible_performers,eligible_supervisors,scoped_staff_choices,resolve_professional_context
from klinis.services.professional_tariffs import quote_professional_service
from .services.igd_assessment_workflow import get_visit


def _enabled():
    if not settings.IGD_WORKFLOW_ENABLED or not getattr(settings,'IGD_PROFESSIONAL_CARE_ENABLED',False):raise Http404


def _query(request):
    unknown=set(request.GET)-{'service','profession','grade','q','offset','limit','at','quantity','performer','supervisor'}
    if unknown:raise ValidationError('Parameter tidak dikenal.')
    if len(request.GET.get('q',''))>100:raise ValidationError('Pencarian terlalu panjang.')
    offset=int(request.GET.get('offset',0));limit=int(request.GET.get('limit',25))
    if not 0<=offset<=10000 or not 1<=limit<=50:raise ValidationError('Halaman tidak valid.')
    from django.forms import DateTimeField
    at=DateTimeField(required=False).clean(request.GET.get('at')) or timezone.now()
    return offset,limit,at


@login_required
@require_GET
@never_cache
def igd_professional_catalogue(request,pk):
    _enabled();visit,_=get_visit(pk,request.user);require_scope(request.user,visit)
    try:
        offset,limit,at=_query(request)
        from django.db.models import Q
        employee=Pegawai.objects.filter(akun=request.user,status='AKTIF',akun__is_active=True).first()
        staff=scoped_staff_choices(request.user,visit,at=at)
        if not staff:
            return JsonResponse({'services':[],'professions':[],'grades':[],'performers':[],'has_more':False,'unavailable':'Hubungkan akun dengan profesi/jenjang HC terverifikasi; terbitkan SPK dan pemetaan layanan.'})
        professions={str(e.profesi_master_id):{'id':e.profesi_master_id,'name':e.profesi_master.nama} for e in staff}
        if request.GET.get('profession') and request.GET['profession'] not in professions:raise ValidationError('Profesi bukan konteks pelaksana.')
        filtered=[e for e in staff if not request.GET.get('profession') or str(e.profesi_master_id)==request.GET['profession']]
        grades={str(e.jenjang_master_id):{'id':str(e.jenjang_master_id),'name':e.jenjang_master.nama} for e in filtered}
        if request.GET.get('grade') and request.GET['grade'] not in grades:raise ValidationError('Jenjang bukan konteks pelaksana.')
        filtered=[e for e in filtered if not request.GET.get('grade') or str(e.jenjang_master_id)==request.GET['grade']]
        service_ids=LayananProfesional.objects.filter(authority_mappings__catalog_item__jenjang_id__in=[e.jenjang_master_id for e in filtered],authority_mappings__is_active=True).values_list('pk',flat=True)
        support_ids=ProfessionalCareGrant.objects.filter(user=request.user,unit_id=visit.unit_kerja_id,capability='SUPPORT_SERVICE',is_active=True).values_list('service_id',flat=True)
        qs=LayananProfesional.objects.filter(Q(pk__in=service_ids)|Q(pk__in=support_ids),is_active=True,reviewed_by__isnull=False,reviewed_at__isnull=False).exclude(source_version='').filter(name__icontains=request.GET.get('q','')).order_by('code')

        rows=list(qs.values('id','code','name','group','note_format')[offset:offset+limit+1])
        performers=[];supervisors=[]
        if request.GET.get('service'):
            selected=qs.get(pk=int(request.GET['service']))
            performers=eligible_performers(request.user,visit,selected,at=at)
            performers=[p for p in performers if (not request.GET.get('profession') or str(p['profession_id'])==request.GET['profession']) and (not request.GET.get('grade') or p['grade_id']==request.GET['grade'])]
            supervisors=eligible_supervisors(request.user,visit,selected,at=at)
        return JsonResponse({'services':rows[:limit],'professions':list(professions.values()),'grades':list(grades.values()),'performers':performers,'supervisors':supervisors,'actor_performer_id':str(employee.pk) if employee else None,'has_more':len(rows)>limit,'unavailable':'' if not request.GET.get('service') or performers else 'SPK, pemetaan atau kewenangan efektif belum tersedia.'})
    except (ValidationError,ValueError,TypeError,ObjectDoesNotExist) as exc:
        return JsonResponse({'error':str(exc)},status=400)


@login_required
@require_GET
@never_cache
def igd_professional_quote(request,pk):
    _enabled();visit,_=get_visit(pk,request.user);require_scope(request.user,visit)
    try:
        _,_,at=_query(request)
        service=LayananProfesional.objects.get(pk=int(request.GET.get('service','')))
        context=resolve_professional_context(request.user,visit,service,at=at,performer=request.GET.get('performer'),supervisor=request.GET.get('supervisor'))
        if request.GET.get('profession') and str(context['profession_id'])!=request.GET['profession'] or request.GET.get('grade') and context['grade_id']!=request.GET['grade']:raise ValidationError('Konteks profesi/jenjang berubah.')
        quote=quote_professional_service(visit,context,service,at=at,quantity=request.GET.get('quantity','1'))
        return JsonResponse({'quote':quote})
    except (ValidationError,ValueError,TypeError,ObjectDoesNotExist) as exc:
        return JsonResponse({'error':str(exc)},status=400)


@login_required
@require_POST
@never_cache
def igd_professional_void(request,pk):
    _enabled()
    from .igd_workflow_views import _action_response
    return _action_response(request,pk,'professional_void')
