"""Scoped Excel staff import routes (Task 8)."""

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from sdm.akses import require_hc_capability, visible_units
from sdm.forms.impor import ImporWorkbookForm
from sdm.models import BatchImporPegawai
from sdm.services.impor_pegawai import (
    TEMPLATE_VERSION,
    apply_staff_import,
    preview_staff_import,
)


def _owned_batch(user, batch_id):
    # Filter ownership in the lookup so foreign UUIDs do not disclose existence.
    return get_object_or_404(
        BatchImporPegawai, pk=batch_id, uploader_id=getattr(user, 'pk', None)
    )


@login_required
def import_template(request):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')
    from io import BytesIO

    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Staf'
    sheet.append([
        'nomor_pegawai', 'nama_lengkap', 'kategori', 'profesi', 'jabatan',
        'status', 'kategori_pegawai', 'unit_code', 'tanggal_mulai',
        'tanggal_selesai', 'alokasi_fte',
    ])
    sheet.append([
        'CONTOH-001', 'Nama Pegawai', 'NON_PPA', 'Administrasi', 'Staf',
        'AKTIF', 'TETAP', visible_units(
            request.user, capability='can_manage_hc_employees'
        ).values_list('code', flat=True).first() or 'KODE-UNIT',
        '2026-01-01', '', '1.00',
    ])
    reference = workbook.create_sheet('Referensi')
    reference.append(['unit_code', 'unit_name'])
    for unit in visible_units(
        request.user, capability='can_manage_hc_employees'
    ).order_by('level', 'order', 'code'):
        reference.append([unit.code, unit.name])
    buffer = BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="template-impor-staf-v{TEMPLATE_VERSION}.xlsx"'
    )
    return response


@login_required
def import_upload(request):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')
    form = ImporWorkbookForm(
        request.POST or None, request.FILES or None,
        initial={'idempotency_key': uuid.uuid4().hex},
    )
    if request.method == 'POST' and form.is_valid():
        try:
            batch = preview_staff_import(
                actor=request.user,
                workbook=form.cleaned_data['workbook'],
                idempotency_key=form.cleaned_data['idempotency_key'],
            )
        except ValidationError as exc:
            form.add_error('workbook', '; '.join(exc.messages))
        else:
            return redirect('sdm:pegawai_import_preview', batch_id=batch.pk)
    return render(request, 'sdm/pegawai/import_upload.html', {
        'form': form,
        'title': 'Impor Data Pegawai',
    })


@login_required
def import_preview(request, batch_id):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')
    batch = _owned_batch(request.user, batch_id)
    return render(request, 'sdm/pegawai/import_preview.html', {
        'batch': batch,
        'rows': batch.decisions or [],
        'title': 'Pratinjau Impor Pegawai',
    })


@login_required
@require_POST
def import_apply(request, batch_id):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')
    batch = _owned_batch(request.user, batch_id)
    try:
        batch = apply_staff_import(
            actor=request.user,
            batch_id=batch.pk,
            preview_hash=request.POST.get('preview_hash') or '',
        )
    except (PermissionDenied, ValidationError) as exc:
        detail = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        messages.error(request, detail or 'Impor tidak dapat diterapkan.')
        return redirect('sdm:pegawai_import_preview', batch_id=batch.pk)
    return redirect('sdm:pegawai_import_result', batch_id=batch.pk)


@login_required
def import_result(request, batch_id):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')
    batch = _owned_batch(request.user, batch_id)
    return render(request, 'sdm/pegawai/import_result.html', {
        'batch': batch,
        'title': 'Hasil Impor Pegawai',
    })
