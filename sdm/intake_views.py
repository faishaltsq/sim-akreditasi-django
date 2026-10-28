"""Resumable five-step intake views (Task B4)."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_units
from sdm.forms import PegawaiCreateForm
from sdm.storage import get_private_storage
from sdm.forms.intake import (
    SipFormSet,
    optional_formset,
    IntakeStep1Form,
    IntakeStep2Form,
    IntakeStep3Form,
    IntakeStep4Form,
    IntakeStep5Form,
)
from sdm.models import (
    DrafInputPegawai,
)
from sdm.services.intake import (
    finalize_staff_intake,
    remove_intake_attachment,
    stage_intake_attachment,
)
from sdm.services.ktp_ocr import extract_ktp_fields


STEP_FORMS = {
    1: IntakeStep1Form,
    2: IntakeStep2Form,
    3: IntakeStep3Form,
    4: IntakeStep4Form,
    5: IntakeStep5Form,
}
STEP_LABELS = {
    1: 'Identitas & Kontak',
    2: 'Kepegawaian & Penempatan',
    3: 'Legalitas & Pendidikan',
    4: 'Akun & Akses',
    5: 'Dokumen Pendukung',
}
DRAFT_TTL_DAYS = 7

KTP_OCR_DRAFT_KEYS = (
    'nik', 'nama_lengkap', 'tanggal_lahir', 'gender', 'alamat',
)


def _run_ktp_ocr(request, draft, storage_key):
    """Fetch the staged KTP object and pre-fill empty draft step-1 fields.

    Runs AFTER the draft-save transaction commits: the DeepSeek call can take
    seconds, and holding the draft's select_for_update lock across it would
    stall concurrent editors. Best-effort by contract — a failed read leaves
    the staged file intact and the operator fills step 1 manually.
    """
    try:
        data = get_private_storage().fetch_object(storage_key)
        fields = extract_ktp_fields(data, actor=request.user)
    except Exception:
        messages.warning(
            request,
            'KTP tersimpan, namun pembacaan otomatis (OCR) tidak berhasil. '
            'Lengkapi data identitas secara manual.',
        )
        return
    with transaction.atomic():
        # Re-guard on the live version: another save between our commit and
        # this read must not be clobbered by a stale draft_data write.
        locked = DrafInputPegawai.objects.select_for_update().filter(
            pk=draft.pk, version=draft.version
        ).first()
        if locked is None:
            return
        merged = dict(locked.draft_data or {})
        step1 = dict(merged.get('1') or {})
        filled = False
        for key in KTP_OCR_DRAFT_KEYS:
            value = (fields.get(key) or '').strip()
            target = 'nama_depan' if key == 'nama_lengkap' else key
            if value and not (step1.get(target) or '').strip():
                step1[target] = value
                filled = True
        if filled:
            merged['1'] = step1
            locked.draft_data = merged
            locked.save(update_fields=['draft_data', 'updated_at'])
    if not filled:
        messages.warning(
            request,
            'KTP tersimpan, namun pembacaan otomatis (OCR) tidak mengenali '
            'data apa pun. Lengkapi data identitas secara manual.',
        )


def _draft_queryset(user):
    return DrafInputPegawai.objects.filter(owner=user)


@login_required
def intake_wizard(request, step=1, draft_id=None):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')

    step = int(step)
    if step < 1 or step > 5:
        raise PermissionDenied('Langkah intake tidak valid.')

    draft = None
    if draft_id:
        draft = get_object_or_404(
            _draft_queryset(request.user), pk=draft_id
        )
        if draft.state in ('FINALIZED', 'REVOKED', 'EXPIRED'):
            messages.warning(
                request, 'Draf tidak dapat diedit lagi (status: %s).' % draft.get_state_display()
            )
            return redirect('sdm:pegawai_wizard_step', step=1)
        if draft.expires_at and draft.expires_at <= timezone.now():
            draft.state = 'EXPIRED'
            draft.save(update_fields=['state', 'updated_at'])
            messages.error(request, 'Draf telah kadaluarsa.')
            return redirect('sdm:pegawai_wizard_step', step=1)

    if request.method == "POST":
        form_class = STEP_FORMS[step]
        form_kwargs = {"user": request.user} if step == 2 else {}
        form = form_class(request.POST, request.FILES, **form_kwargs)
        sip_formset = (
            optional_formset(SipFormSet, request.POST, 'sip') if step == 3 else None
        )
        raw_version = (request.POST.get('expected_version') or '').strip()
        if draft is not None:
            if not raw_version.isdigit():
                form.add_error(None, 'Versi draf tidak dikirim. Muat ulang halaman ini.')
            elif int(raw_version) != draft.version:
                messages.error(
                    request,
                    'Draf telah diperbarui di tab lain. Muat ulang sebelum menyimpan.',
                )
                return render(request, 'sdm/pegawai/wizard.html', {
                    'form': form,
                    'sip_formset': sip_formset,
                    'step': step,
                    'prev_step': step - 1,
                    'step_label': STEP_LABELS[step],
                    'step_labels': STEP_LABELS,
                    'draft': draft,
                    'units': visible_units(
                        request.user, capability='can_manage_hc_employees'
                    ),
                    'title': f'Input Pegawai — Langkah {step}: {STEP_LABELS[step]}',
                }, status=409)
        if form.is_valid():
            ktp_ocr_needed = False
            staged_ktp_key = ''
            cleaned = dict(form.cleaned_data)
            for field in ('foto_profil', 'berkas'):
                cleaned.pop(field, None)
            if step == 3 and sip_formset is not None:
                # An unbound formset (no management fields in POST) means the
                # operator submitted zero SIP rows; validating it would always
                # fail and block a legitimate step-3 save.
                if sip_formset.is_bound and not sip_formset.is_valid():
                    form.add_error(None, 'Periksa kembali isian SIP.')
                elif sip_formset.is_bound:
                    for index, sip in enumerate(sip_formset.forms):
                        if not sip.cleaned_data:
                            continue
                        for field, value in sip.cleaned_data.items():
                            if hasattr(value, 'pk') and not isinstance(value, str):
                                value = value.pk
                            elif isinstance(value, date):
                                value = value.isoformat()
                            cleaned[f'sip-{index}-{field}'] = value
            for key, value in cleaned.items():
                if hasattr(value, 'pk') and not isinstance(value, str):
                    cleaned[key] = value.pk
                elif isinstance(value, date):
                    cleaned[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    cleaned[key] = str(value)
            expires_at = timezone.now() + timedelta(days=DRAFT_TTL_DAYS)
            if draft:
                version_conflict = False
                with transaction.atomic():
                    locked = DrafInputPegawai.objects.select_for_update().get(
                        owner=request.user, pk=draft.pk
                    )
                    if locked.version != int(raw_version):
                        version_conflict = True
                    else:
                        staged = []
                        uploads = [('foto_profil', 'FOTO_PROFIL')]
                        selected_kind = (cleaned.get('jenis_berkas') or '').strip()
                        if form.cleaned_data.get('berkas'):
                            kind = (
                                selected_kind
                                if selected_kind in dict(
                                    IntakeStep5Form.JENIS_PENDUKUNG_CHOICES
                                )
                                else 'OTHER'
                            )
                            uploads.append(('berkas', kind))
                        for field, kind in uploads:
                            uploaded = form.cleaned_data.get(field)
                            if not uploaded:
                                continue
                            try:
                                staged.append(stage_intake_attachment(
                                    actor=request.user,
                                    draft_id=locked.pk,
                                    expected_version=locked.version,
                                    file_obj=uploaded,
                                    artifact_kind=kind,
                                ))
                            except ValidationError as exc:
                                form.add_error(field, _message_of(exc))
                        staged_ktp = next(
                            (a for a in staged if a.artifact_kind == 'KTP'), None
                        )
                        ktp_ocr_needed = staged_ktp is not None and not form.errors
                        staged_ktp_key = (
                            staged_ktp.storage_key if staged_ktp else ''
                        )
                        if form.errors:
                            # A request that stages photo successfully but rejects
                            # KTP must not leave the photo behind and duplicate it
                            # on retry.
                            for attachment in staged:
                                try:
                                    remove_intake_attachment(
                                        actor=request.user,
                                        attachment_id=attachment.pk,
                                        expected_version=locked.version,
                                    )
                                except ValidationError:
                                    # Keep the STAGED row when object deletion
                                    # fails; it stays traceable and the operator
                                    # sees the original form error.
                                    pass
                            return render(request, 'sdm/pegawai/wizard.html', {
                                'form': form, 'sip_formset': sip_formset,
                                'step': step, 'prev_step': step - 1,
                                'step_label': STEP_LABELS[step],
                                'step_labels': STEP_LABELS,
                                'draft': locked,
                                'units': visible_units(
                                    request.user,
                                    capability='can_manage_hc_employees',
                                ),
                                'title': (
                                    f'Input Pegawai — Langkah {step}: '
                                    f'{STEP_LABELS[step]}'
                                ),
                            })
                        data = dict(locked.draft_data or {})
                        data[str(step)] = cleaned
                        locked.draft_data = data
                        locked.version += 1
                        locked.current_step = min(step + 1, 5)
                        locked.expires_at = expires_at
                        locked.state = 'DRAFT'
                        locked.save(update_fields=[
                            'draft_data', 'version', 'current_step',
                            'expires_at', 'state', 'updated_at',
                        ])
                if version_conflict:
                    messages.error(
                        request,
                        'Draf telah diperbarui di tab lain. Muat ulang sebelum menyimpan.',
                    )
                    return render(request, 'sdm/pegawai/wizard.html', {
                        'form': form, 'sip_formset': sip_formset,
                        'step': step, 'prev_step': step - 1,
                        'step_label': STEP_LABELS[step], 'step_labels': STEP_LABELS,
                        'draft': locked,
                        'units': visible_units(
                            request.user, capability='can_manage_hc_employees'
                        ),
                        'title': f'Input Pegawai — Langkah {step}: {STEP_LABELS[step]}',
                    }, status=409)
                draft = locked
            else:
                draft = DrafInputPegawai.objects.create(
                    owner=request.user,
                    current_step=min(step + 1, 5),
                    draft_data={str(step): cleaned},
                    version=1,
                    expires_at=expires_at,
                )
            if step < 5:
                if ktp_ocr_needed:
                    _run_ktp_ocr(request, draft, staged_ktp_key)
                    return redirect(
                        'sdm:pegawai_wizard_resume', step=1, draft_id=draft.pk
                    )
                return redirect('sdm:pegawai_wizard_resume', step=step + 1, draft_id=draft.pk)
            if ktp_ocr_needed:
                _run_ktp_ocr(request, draft, staged_ktp_key)
            return redirect('sdm:pegawai_intake_finalize', draft_id=draft.pk)
    else:
        form_class = STEP_FORMS[step]
        initial = (draft.draft_data or {}).get(str(step), {}) if draft else {}
        form_kwargs = {"user": request.user} if step == 2 else {}
        form = form_class(initial=initial, **form_kwargs)
        sip_formset = SipFormSet(prefix='sip') if step == 3 else None

    units = visible_units(request.user, capability='can_manage_hc_employees')
    return render(request, 'sdm/pegawai/wizard.html', {
        'form': form,
        'sip_formset': sip_formset,
        'step': step,
        'prev_step': step - 1,
        'step_label': STEP_LABELS[step],
        'step_labels': STEP_LABELS,
        'draft': draft,
        'units': units,
        'title': f'Input Pegawai — Langkah {step}: {STEP_LABELS[step]}',
    })


@login_required
@require_POST
def intake_attachment_remove(request, attachment_id):
    try:
        expected_version = int(request.POST.get('expected_version') or '')
        draft_id = remove_intake_attachment(
            actor=request.user,
            attachment_id=attachment_id,
            expected_version=expected_version,
        )
    except (TypeError, ValueError, ValidationError):
        messages.error(request, 'Lampiran tidak dapat dihapus.')
        return redirect('sdm:pegawai_create')
    messages.success(request, 'Lampiran dihapus.')
    return redirect(
        'sdm:pegawai_wizard_resume', step=5, draft_id=draft_id
    )


def _message_of(exc):
    if isinstance(exc, ValidationError):
        if hasattr(exc, 'message_dict'):
            return ' '.join(
                f'{field}: {", ".join(msgs)}'
                for field, msgs in exc.message_dict.items()
            )
        return ' '.join(exc.messages)
    return str(exc) or 'Gagal menyelesaikan input pegawai.'


@login_required
def intake_finalize(request, draft_id):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')

    draft = get_object_or_404(_draft_queryset(request.user), pk=draft_id)
    if draft.state == 'FINALIZED' and draft.finalized_employee_id:
        return redirect('sdm:pegawai_detail', employee_id=draft.finalized_employee_id)
    if draft.state != 'DRAFT':
        messages.error(
            request,
            'Draf tidak dapat diselesaikan (status: %s).' % draft.get_state_display(),
        )
        return redirect('sdm:pegawai_wizard_step', step=1)

    if request.method == 'POST':
        raw_version = (request.POST.get('expected_version') or '').strip()
        try:
            if not raw_version.isdigit():
                raise ValidationError('Versi draf tidak dikirim. Muat ulang halaman ini.')
            employee = finalize_staff_intake(
                actor=request.user,
                draft_id=draft.pk,
                expected_version=int(raw_version),
                idempotency_key=f'intake-{draft.pk}',
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, _message_of(exc))
            return redirect(
                'sdm:pegawai_wizard_resume', step=5, draft_id=draft.pk
            )
        messages.success(request, 'Pegawai berhasil terdaftar.')
        step4 = (draft.draft_data or {}).get('4') or {}
        if step4.get('create_account') and step4.get('email'):
            from django.db import transaction
            from sdm.services.undangan import invite_staff_account

            def _invite(employee_pk=employee.pk, email=step4['email'],
                        role=step4.get('intended_role') or 'STAF_NAKES',
                        intended_is_active=bool(step4.get('account_active'))):
                from sdm.models import Pegawai
                try:
                    invite_staff_account(
                        actor=request.user,
                        employee=Pegawai.objects.get(pk=employee_pk),
                        email=email,
                        role=role,
                        intended_is_active=intended_is_active,
                        idempotency_key=f'intake-invite-{employee_pk}',
                    )
                except Exception:
                    pass

            transaction.on_commit(_invite)
        return redirect('sdm:pegawai_detail', employee_id=employee.pk)

    return render(request, 'sdm/pegawai/wizard_finalize.html', {
        'draft': draft,
        'step_count': 5,
        'title': 'Selesaikan Input Pegawai',
    })
