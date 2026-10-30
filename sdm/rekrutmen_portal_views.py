"""Fase C2: halaman publik portal pelamar — tanpa login, akses lewat token."""
from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from sdm.forms.rekrutmen_portal import LamaranPortalForm
from sdm.models import KonfirmasiOffering, Lamaran, Pelamar, SesiUjian
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
                pendidikan_terakhir=form.cleaned_data['pendidikan_terakhir'],
                ipk=form.cleaned_data['ipk'],
                tanggal_lahir=form.cleaned_data['tanggal_lahir'],
                pengalaman_bulan=form.cleaned_data['pengalaman_bulan'],
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
    sesi_aktif = SesiUjian.objects.filter(
        lamaran__pelamar=pelamar, status='BERLANGSUNG'
    ).select_related('paket', 'lamaran__lowongan')
    return render(request, 'sdm/rekrutmen_portal/status.html', {
        'data': application_status(lamaran),
        'sesi_aktif': sesi_aktif,
        'token': token,
        'title': 'Status Lamaran',
    })


# ── Fase C4: pengerjaan ujian kompetensi (CBT) ───────────────────────────
def portal_ujian(request, token, sesi_id):
    """Exam paper for one session, reached by the candidate's own token."""
    pelamar = get_object_or_404(Pelamar, token=token)
    sesi = get_object_or_404(
        SesiUjian.objects.select_related('paket', 'lamaran'),
        pk=sesi_id,
        lamaran__pelamar=pelamar,
    )
    from sdm.services.ujian_rekrutmen import selesaikan_sesi, soal_untuk_sesi

    if sesi.is_kedaluwarsa():
        selesaikan_sesi(sesi, paksa=True)

    if sesi.status != 'BERLANGSUNG':
        return render(request, 'sdm/rekrutmen_portal/ujian_selesai.html', {
            'sesi': sesi, 'token': token, 'title': 'Ujian Selesai',
        })

    terjawab = {str(j.soal_id): j.jawaban for j in sesi.jawaban.all()}
    soal = soal_untuk_sesi(sesi)
    for item in soal:
        item.jawaban_tersimpan = terjawab.get(str(item.pk), '')
    return render(request, 'sdm/rekrutmen_portal/ujian.html', {
        'sesi': sesi,
        'soal': soal,
        'sisa_detik': sesi.sisa_detik(),
        'token': token,
        'title': 'Ujian Kompetensi',
    })


def portal_ujian_jawab(request, token, sesi_id):
    """Save all posted answers and optionally submit the paper."""
    pelamar = get_object_or_404(Pelamar, token=token)
    sesi = get_object_or_404(
        SesiUjian.objects.select_related('paket'),
        pk=sesi_id,
        lamaran__pelamar=pelamar,
    )
    if request.method != 'POST':
        return redirect(
            'sdm:portal_ujian', token=token, sesi_id=sesi.pk
        )

    from sdm.services.ujian_rekrutmen import catat_jawaban, selesaikan_sesi

    try:
        with transaction.atomic():
            sesi = SesiUjian.objects.select_for_update().select_related('paket').get(pk=sesi.pk)
            if sesi.is_kedaluwarsa():
                selesaikan_sesi(sesi, paksa=True)
                messages.error(request, 'Waktu ujian sudah habis.')
            elif sesi.status != 'BERLANGSUNG':
                messages.error(request, 'Sesi ujian sudah berakhir.')
            else:
                valid_ids = {str(pk) for pk in sesi.paket.soal.values_list('pk', flat=True)}
                answers = [
                    (key[len('jawaban_'):], request.POST.getlist(key))
                    for key in request.POST if key.startswith('jawaban_')
                ]
                if any(
                    soal_id not in valid_ids or len(values) != 1
                    or values[0] not in ('A', 'B', 'C', 'D')
                    for soal_id, values in answers
                ):
                    raise ValueError('Jawaban tidak dikenal atau soal tidak ada di paket ini.')
                for soal_id, values in answers:
                    catat_jawaban(sesi, soal_id, values[0])
                if request.POST.get('submit'):
                    selesaikan_sesi(sesi, paksa=True)
                    messages.success(request, 'Jawaban terkirim.')
                else:
                    messages.success(request, 'Jawaban tersimpan.')
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
        sesi.refresh_from_db()
        if sesi.is_kedaluwarsa():
            selesaikan_sesi(sesi, paksa=True)
    return redirect('sdm:portal_ujian', token=token, sesi_id=sesi.pk)


def portal_ujian_fokus(request, token, sesi_id):
    """Anti-cheating ping: the candidate left the exam page."""
    pelamar = get_object_or_404(Pelamar, token=token)
    sesi = get_object_or_404(
        SesiUjian, pk=sesi_id, lamaran__pelamar=pelamar
    )
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    from sdm.services.ujian_rekrutmen import catat_pindah_fokus
    return JsonResponse({'pindah_fokus': catat_pindah_fokus(sesi)})


# ── Fase C6: MCU & konfirmasi surat penawaran ──────────────────────────────
def portal_offering(request, token):
    """Candidate view of their offering letter and the accept/decline form."""
    offering = get_object_or_404(
        KonfirmasiOffering.objects.select_related(
            'lamaran', 'lamaran__lowongan'
        ),
        token=token,
    )
    if request.method == 'POST':
        from sdm.services.mcu_offering_rekrutmen import konfirmasi_offering
        keputusan = request.POST.get('keputusan')
        setuju = {'setuju': True, 'tolak': False}.get(keputusan)
        ip = request.META.get('REMOTE_ADDR')
        try:
            konfirmasi_offering(
                token=token, setuju=setuju, ip=ip,
                catatan=(request.POST.get('catatan') or '')[:1000],
            )
        except ValidationError as exc:
            for errors in exc.message_dict.values():
                messages.error(request, '; '.join(errors))
        else:
            messages.success(
                request,
                'Terima kasih, keputusan Anda telah tercatat.'
                if setuju else
                'Keputusan Anda telah tercatat. Terima kasih atas minat Anda.',
            )
        return redirect('sdm:portal_offering', token=token)

    response = render(request, 'sdm/rekrutmen_portal/offering.html', {
        'offering': offering,
        'lamaran': offering.lamaran,
        'title': 'Surat Penawaran Kerja',
    })
    response['Cache-Control'] = 'private, no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


def portal_offering_unduh(request, token):
    """The offering token authorizes its candidate-facing PDF."""
    offering = get_object_or_404(KonfirmasiOffering, token=token)
    if not offering.berkas:
        raise Http404
    response = FileResponse(offering.berkas.open('rb'), content_type='application/pdf')
    response['Cache-Control'] = 'private, no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response
