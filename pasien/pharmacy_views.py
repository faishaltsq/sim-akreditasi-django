import json
from uuid import uuid4
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from klinis.services.penunjang_catalogue import list_choices
from klinis.services.medication_catalogue import medication_choices
from pasien.models import ResepElektronik, PharmacyServiceGrant, PpraReviewRequest
from .services.igd_assessment_workflow import get_visit
from .services.prescriptions import transition_prescription
from .services.ppra_review import review_ppra


def body(request,allowed):
    if len(request.body)>256*1024:
        raise ValueError('Payload terlalu besar.')
    data=json.loads(request.body)
    if not isinstance(data,dict) or set(data)-set(allowed):
        raise ValueError('Atribut permintaan tidak valid.')
    return data


def catalogue_query(request):
    parent=request.GET.get('parent')
    page=int(request.GET.get('page','1'))
    if page<1 or page>10000:
        raise ValueError('Halaman tidak valid.')
    return {'parent_id':int(parent) if parent else None,'query':request.GET.get('q',''),'page':page}


@login_required
@require_GET
@never_cache
def ancillary_catalogue(request,pk):
    get_visit(pk,request.user)
    try:
        return JsonResponse(list_choices(request.user,**catalogue_query(request)))
    except (ValueError,TypeError):
        return JsonResponse({'success':False,'error':'Parameter katalog penunjang tidak valid.'},status=400)


@login_required
@require_GET
@never_cache
def medication_catalogue(request,pk):
    visit,_=get_visit(pk,request.user)
    try:
        return JsonResponse(medication_choices(request.user,visit=visit,kind=request.GET.get('kind','OBAT'),
            level=request.GET.get('level','class'),formulary=request.GET.get('formulary',''),**catalogue_query(request)))
    except (ValueError,TypeError):
        return JsonResponse({'success':False,'error':'Parameter katalog obat tidak valid.'},status=400)


@login_required
@require_POST
@never_cache
def pharmacy_transition(request,resep_pk):
    try:
        if request.content_type=='application/json':
            data=body(request,{'action','version','request_id','reason'})
        else:
            data={'action':request.POST.get('aksi'),'version':int(request.POST.get('version','-1')),
                  'request_id':request.POST.get('request_id'),'reason':request.POST.get('reason','')}
        get_object_or_404(ResepElektronik,pk=resep_pk)
        result=transition_prescription(request.user,resep_pk,data.get('action'),data.get('version'),data.get('request_id'),data.get('reason',''))
    except (ValueError,TypeError,UnicodeDecodeError) as exc:
        if request.content_type=='application/json':
            return JsonResponse({'success':False,'error':str(exc)},status=400)
        messages.error(request,str(exc)); return redirect('pasien:farmasi_antrean')
    if request.content_type=='application/json':
        return JsonResponse({'success':True,**result})
    messages.success(request,'Status resep diperbarui. '+('Billing masih memerlukan rekonsiliasi.' if result.get('financial_pending') else ''))
    return redirect('pasien:farmasi_antrean')


@login_required
@require_POST
@never_cache
def ppra_decision(request,pk):
    try:
        data=body(request,{'decision','reason','digest'}) if request.content_type=='application/json' else request.POST
        get_object_or_404(PpraReviewRequest,pk=pk)
        result=review_ppra(request.user,pk,data.get('decision'),data.get('reason',''),data.get('digest'))
        if request.content_type=='application/json':
            return JsonResponse({'success':True,**result})
        messages.success(request,'Keputusan PPRA tercatat.')
    except (ValueError,TypeError,UnicodeDecodeError) as exc:
        if request.content_type=='application/json':
            return JsonResponse({'success':False,'error':str(exc)},status=400)
        messages.error(request,str(exc))
    return redirect('pasien:farmasi_antrean')


def worklist(request):
    grants=PharmacyServiceGrant.objects.filter(user=request.user)
    qs=ResepElektronik.objects.filter(serving_unit_id__in=grants.values('unit_id')).exclude(status='DRAFT').select_related('kunjungan__pasien','dokter_peresep','apoteker').prefetch_related('items')
    status=request.GET.get('status','AKTIF');q=request.GET.get('q','')[:200]
    if q:
        qs=qs.filter(Q(no_resep__icontains=q)|Q(kunjungan__pasien__nama_lengkap__icontains=q)|Q(kunjungan__pasien__no_rm__icontains=q))
    counts={'total':qs.count(),'dikirim':qs.filter(status='DIKIRIM').count(),'dispensing':qs.filter(status='DISPENSING').count(),'selesai':qs.filter(status='SELESAI').count()}
    if status=='AKTIF':
        qs=qs.filter(status__in=['DIKIRIM','DISPENSING'])
    elif status in ('DIKIRIM','DISPENSING','SELESAI','BATAL'):
        qs=qs.filter(status=status)
    page=Paginator(qs,50).get_page(request.GET.get('page'))
    for rx in page:
        rx.operation_key=str(uuid4())
    ppra=PpraReviewRequest.objects.filter(resep__serving_unit_id__in=grants.filter(can_ppra_review=True).values('unit_id'),decision='PENDING').exclude(requested_by=request.user).exclude(resep__dokter_peresep=request.user).select_related('resep').prefetch_related('resep__items')
    return render(request,'pasien/farmasi_antrean.html',{'resep_list':page,'page_obj':page,'status_filter':status,'q':q,'counts':counts,'ppra_requests':ppra})
