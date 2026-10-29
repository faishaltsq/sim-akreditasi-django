"""Fase C2: halaman publik portal pelamar — tanpa login, akses lewat token."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from sdm.forms.rekrutmen_portal import LamaranPortalForm
from sdm.models import Lamaran, Pelamar
from sdm.services.rekrutmen_portal import (
    application_status,
    create_application,
    lowongan_terbuka,
)


def portal_lowongan(request):
    """Public vacancy board: only vacancies whose registration window is open."""
    return render(request, 'sdm/rekrutmen_portal/lowongan.html', {
        'vacancies': lowongan_terbuka(),
        'title': 'Lowongan Tersedia',
    })


def portal_daftar(request, vacancy_id):
    """Application form for one vacancy.

    On success the candidate is redirected to their token URL. That token is
    the only capability for reading the application back, so it is passed along
    in the redirect rather than shown as a bare secret on this page.
    """
    vacancy = get_object_or_404(lowongan_terbuka().filter(pk=vacancy_id))
    form = LamaranPortalForm(
        request.POST or None, request.FILES or None, vacancy=vacancy
    )
    if request.method == 'POST' and form.is_valid():
        try:
            lamaran = create_application(
                vacancy=vacancy,
                nama=form.cleaned_data['nama_lengkap'],
                email=form.cleaned_data['email'],
                telepon=form.cleaned_data['telepon'],
                files=form.files_by_jenis(),
            )
        except ValidationError as exc:
            # ``message_dict`` exists only when the error was raised keyed by
            # field; an unkeyed error becomes a non-field error instead of a
            # page crash.
            if hasattr(exc, 'error_dict'):
                for field, errors in exc.message_dict.items():
                    form.add_error(
                        field if field != 'lowongan' else None, errors
                    )
            else:
                form.add_error(None, exc.messages)
        else:
            messages.success(
                request,
                'Lamaran terkirim. Anda akan diarahkan ke halaman pemantauan '
                'status lamaran.',
            )
            return redirect(
                'sdm:portal_lamaran_status', token=lamaran.pelamar.token
            )
    return render(request, 'sdm/rekrutmen_portal/daftar.html', {
        'form': form,
        'vacancy': vacancy,
        'title': f'Daftar — {vacancy.judul}',
    })


def portal_lamaran_status(request, token):
    """Candidate dashboard: the stage this application has reached."""
    pelamar = get_object_or_404(Pelamar, token=token)
    lamaran = (
        Lamaran.objects.filter(pelamar=pelamar)
        .select_related('lowongan', 'lowongan__unit_kerja')
        .prefetch_related('berkas', 'penilaian')
        .order_by('-created_at')
        .first()
    )
    if lamaran is None:
        messages.error(request, 'Lamaran tidak ditemukan.')
        return redirect('sdm:portal_lowongan')
    return render(request, 'sdm/rekrutmen_portal/status.html', {
        'data': application_status(lamaran),
        'token': token,
        'title': 'Status Lamaran',
    })
