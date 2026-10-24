"""Own-profile staff portal (Task A9)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from sdm.akses import visible_employees
from sdm.models import (
    DokumenPegawai,
    LayananMandiri,
    Pegawai,
    PenugasanKlinis,
    PengingatSDM,
)
from sdm.services.kepatuhan import documents_for_employee, evaluate_employee_compliance
from sdm.services.layanan_mandiri import submit_staff_request
from sdm.services.legalitas import legal_status


def _own_employee(user):
    """Return the actor's own employee or raise; never grants unit-wide access."""
    try:
        return visible_employees(user).get(akun=user)
    except Pegawai.DoesNotExist:
        raise PermissionDenied('Akun Anda tidak terhubung dengan data pegawai.')


@login_required
def portal_index(request):
    employee = _own_employee(request.user)

    documents = documents_for_employee(employee).prefetch_related('versions')
    compliance = evaluate_employee_compliance(employee)
    legal = legal_status(employee)
    assignments = employee.penempatan.select_related('unit_kerja').order_by(
        '-tanggal_mulai', '-pk'
    )
    spk = PenugasanKlinis.objects.filter(
        employee=employee, is_active=True
    ).select_related('unit_kerja').order_by('-issued_at')
    reminders = PengingatSDM.objects.filter(
        recipient=request.user, read_at__isnull=True
    ).order_by('due_date')[:20]
    requests = LayananMandiri.objects.filter(employee=employee).order_by('-created_at')[:20]

    return render(request, 'sdm/portal/index.html', {
        'employee': employee,
        'documents': documents,
        'compliance': compliance,
        'legal': legal,
        'assignments': assignments,
        'spk': spk,
        'reminders': reminders,
        'requests': requests,
        'title': 'Portal Mandiri',
    })


@login_required
def portal_request_create(request):
    employee = _own_employee(request.user)

    if request.method == 'POST':
        kind = (request.POST.get('kind') or '').strip()
        allowed = {choice[0] for choice in LayananMandiri.KIND_CHOICES}
        if kind not in allowed:
            messages.error(request, 'Jenis pengajuan tidak valid.')
            return redirect('sdm:portal_index')
        payload = {
            key: value for key, value in request.POST.items()
            if key not in {'csrfmiddlewaretoken', 'kind'}
        }
        try:
            submit_staff_request(
                actor=request.user,
                kind=kind,
                payload=payload,
                idempotency_key=(request.POST.get('idempotency_key') or '').strip(),
            )
        except (PermissionDenied, ValidationError) as exc:
            message = getattr(exc, 'messages', None)
            messages.error(request, '; '.join(message) if message else str(exc))
        else:
            messages.success(request, 'Pengajuan Anda telah dikirim untuk ditinjau.')
        return redirect('sdm:portal_index')

    return render(request, 'sdm/portal/pengajuan.html', {
        'employee': employee,
        'kind_choices': LayananMandiri.KIND_CHOICES,
        'title': 'Ajukan Layanan Mandiri',
    })


@login_required
def portal_request_cancel(request, request_id):
    employee = _own_employee(request.user)
    if request.method != 'POST':
        raise PermissionDenied('Pembatalan harus melalui POST.')

    staff_request = get_object_or_404(
        LayananMandiri.objects.filter(employee=employee), pk=request_id
    )
    if staff_request.state not in {'DRAFT', 'SUBMITTED'}:
        messages.error(request, 'Pengajuan ini tidak dapat dibatalkan.')
        return redirect('sdm:portal_index')

    staff_request.state = 'CANCELLED'
    staff_request.save(update_fields=['state', 'updated_at'])
    messages.success(request, 'Pengajuan dibatalkan.')
    return redirect('sdm:portal_index')
