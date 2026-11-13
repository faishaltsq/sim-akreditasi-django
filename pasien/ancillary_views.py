from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from pasien.models import OrderPenunjang
from .services.penunjang_results import service_orders,record_result


@login_required
@never_cache
def worklist(request,kind=None):
    kind=kind or request.GET.get('jenis','LAB')
    status=request.GET.get('status','')
    if kind not in ('LAB','RADIOLOGI','EKG','LAINNYA') or status not in ('','ORDERED','PROSES','SELESAI'):
        return HttpResponseBadRequest('Jenis/status penunjang tidak valid.')
    base=service_orders(request.user,read_only=True).filter(jenis=kind).select_related('kunjungan__pasien').order_by('-created_at','-pk')
    qs=base.filter(status=status) if status else base
    page=Paginator(qs,50).get_page(request.GET.get('page'))
    critical=list(base.filter(is_critical_value=True).exclude(status='SELESAI')[:50])
    records=[*page,*critical]
    try:
        editable=set(service_orders(request.user).filter(pk__in=[order.pk for order in records]).values_list('pk',flat=True))
    except PermissionDenied:
        editable=set()
    for order in records:
        order.can_record_result=order.pk in editable
    return render(request,'pasien/laboratorium_dashboard.html',{'orders':page,'page_obj':page,'kind':kind,
        'critical_orders':critical,
        'total_pending':base.filter(status='ORDERED').count(),'total_proses':base.filter(status='PROSES').count(),
        'total_selesai':base.filter(status='SELESAI').count(),'status_filter':status})


@login_required
@require_POST
@never_cache
def update_result(request,pk,kind=None):
    order=get_object_or_404(service_orders(request.user),pk=pk)
    if kind and order.jenis!=kind:
        return HttpResponseBadRequest('Jenis order tidak sesuai endpoint.')
    data={key:request.POST.get(key,'') for key in ('status','hasil_pemeriksaan','critical_value_catatan')}
    data['is_critical_value']=request.POST.get('is_critical_value')=='1'
    try:
        record_result(order.pk,request.user,data,expected_state=request.POST.get('expected_state') or None,
            correction_reason=request.POST.get('correction_reason',''))
    except (ValueError,TypeError) as exc:
        messages.error(request,str(exc))
    else:
        messages.success(request,f'Hasil order #{order.pk} tercatat.')
    return redirect(reverse('pasien:ancillary_worklist')+'?'+urlencode({'jenis':order.jenis}))
