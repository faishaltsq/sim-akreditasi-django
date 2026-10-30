from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from sdm.akses import require_hc_capability
from sdm.models import Lamaran
from sdm.services.undangan import invite_staff_account


@login_required
@require_POST
def invite_hired_account(request, application_id):
    application = get_object_or_404(
        Lamaran.objects.select_related('lowongan', 'employee__akun'), pk=application_id,
    )
    require_hc_capability(
        request.user, 'can_manage_hc_recruitment', unit=application.lowongan.unit_kerja_id,
    )
    destination = redirect('sdm:rekrutmen_detail', vacancy_id=application.lowongan_id)
    employee = application.employee
    if application.status != 'DITERIMA' or not employee or not employee.akun_id:
        messages.error(request, 'Lamaran belum memiliki akun pegawai hasil rekrutmen.')
        return destination
    account = employee.akun
    if account.has_usable_password() or not account.email:
        messages.error(request, 'Akun sudah memiliki sandi atau email pegawai belum tersedia.')
        return destination
    try:
        invitation = invite_staff_account(
            actor=request.user, employee=employee, email=account.email,
            role='STAF_NAKES', idempotency_key=None,
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return destination
    if invitation.state == 'FAILED':
        messages.error(request, 'Undangan gagal dikirim; periksa konfigurasi email.')
    else:
        messages.success(request, 'Undangan aktivasi dijadwalkan untuk dikirim.')
    return destination
