"""Single-use staff account activation (Task 9)."""

import hashlib

from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from sdm.models import UndanganAkunPegawai
from sdm.services.undangan import accept_staff_invitation

GENERIC_ERROR = 'Tautan aktivasi tidak valid atau sudah digunakan.'


def _render_private(request, template, context):
    response = render(request, template, context)
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


def _pending_invitation(token):
    digest = hashlib.sha256((token or '').encode()).hexdigest()
    return UndanganAkunPegawai.objects.filter(
        token_digest=digest, state='SENT'
    ).select_related('employee').first()


@csrf_protect
@require_http_methods(['GET', 'POST'])
def activate(request, token):
    invitation = _pending_invitation(token)
    if invitation is None or not invitation.is_active:
        return _render_private(request, 'accounts/staff_activation.html', {
            'invalid': True, 'message': GENERIC_ERROR,
        })
    if request.method == 'GET':
        return _render_private(request, 'accounts/staff_activation.html', {
            'invitation': invitation, 'email': invitation.email,
        })

    password1 = request.POST.get('new_password1') or ''
    password2 = request.POST.get('new_password2') or ''
    if password1 != password2:
        return _render_private(request, 'accounts/staff_activation.html', {
            'invitation': invitation, 'email': invitation.email,
            'error': 'Konfirmasi sandi tidak sama.',
        })
    try:
        user = accept_staff_invitation(token=token, password=password1)
    except ValidationError as exc:
        return _render_private(request, 'accounts/staff_activation.html', {
            'invitation': invitation, 'email': invitation.email,
            'error': ' '.join(exc.messages) or GENERIC_ERROR,
        })
    request.session['staff_activation_active'] = bool(user.is_active)
    return redirect('accounts:staff_activation_complete')


@require_GET
def activation_complete(request):
    active = request.session.pop('staff_activation_active', None)
    return _render_private(request, 'accounts/staff_activation_complete.html', {
        'active': active,
    })
