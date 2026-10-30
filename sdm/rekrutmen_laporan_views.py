"""Scoped recruitment reporting and confidential evidence downloads."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from sdm.akses import require_hc_capability, visible_units
from sdm.models import Lamaran, PeristiwaSDM
from sdm.services.rekrutmen_laporan import audit_package, dashboard_pdf, dashboard_rows


@login_required
@require_GET
@never_cache
def dashboard(request):
    require_hc_capability(request.user, 'can_manage_hc_recruitment')
    units = visible_units(request.user, capability='can_manage_hc_recruitment')
    return render(request, 'sdm/rekrutmen/laporan.html', {'rows': dashboard_rows(units)})


@login_required
@require_GET
@never_cache
def dashboard_export(request):
    require_hc_capability(request.user, 'can_manage_hc_recruitment')
    require_hc_capability(request.user, 'can_export_hc')
    units = visible_units(request.user, capability='can_manage_hc_recruitment')
    rows = dashboard_rows(units)
    export_ids = set(visible_units(request.user, capability='can_export_hc').values_list('pk', flat=True))
    if any(row['vacancy'].unit_kerja_id not in export_ids for row in rows):
        raise PermissionDenied('Hak ekspor tidak mencakup seluruh unit pada dasbor.')
    response = HttpResponse(dashboard_pdf(rows), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rekap-rekrutmen.pdf"'
    return response


@login_required
@require_GET
@never_cache
def bukti_audit(request, application_id):
    require_hc_capability(request.user, 'can_manage_hc_recruitment')
    application = get_object_or_404(
        Lamaran.objects.select_related('lowongan'), pk=application_id,
        lowongan__unit_kerja__in=visible_units(request.user, capability='can_manage_hc_recruitment'),
    )
    unit = application.lowongan.unit_kerja_id
    require_hc_capability(request.user, 'can_export_hc', unit=unit)
    require_hc_capability(request.user, 'hc_health_read', unit=unit)
    content = audit_package(application)
    PeristiwaSDM.objects.create(actor=request.user, jenis_peristiwa='recruitment_audit_exported',
                                target_tipe='application', target_id=str(application.pk))
    response = HttpResponse(content, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="bukti-rekrutmen-{application.pk}.zip"'
    return response
