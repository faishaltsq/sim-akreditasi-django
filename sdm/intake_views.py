"""Resumable five-step intake views (Task B4)."""

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.akses import require_hc_capability, visible_units
from sdm.forms import PegawaiCreateForm
from sdm.forms.intake import (
    IntakeStep1Form,
    IntakeStep2Form,
    IntakeStep3Form,
    IntakeStep4Form,
    IntakeStep5Form,
)
from sdm.models import (
    DrafInputPegawai,
    DokumenPegawai,
    IzinProfesiPegawai,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
    ProfilPribadiPegawai,
    RiwayatKepegawaian,
    RiwayatPendidikanPegawai,
    VersiDokumen,
)
from sdm.services.intake import validate_personal_data
from sdm.storage import INTAKE_MAX_BYTES, store_private_document


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
        form = form_class(request.POST, **form_kwargs)
        if form.is_valid():
            data = dict(draft.draft_data) if draft and draft.draft_data else {}
            cleaned = dict(form.cleaned_data)
            for key, value in cleaned.items():
                if hasattr(value, 'pk') and not isinstance(value, str):
                    cleaned[key] = value.pk
                elif isinstance(value, (date,)):
                    cleaned[key] = value.isoformat()
                elif isinstance(value, Decimal):
                    cleaned[key] = str(value)
            data[str(step)] = cleaned
            version = (draft.version + 1) if draft else 1
            expires_at = timezone.now() + timedelta(days=DRAFT_TTL_DAYS)
            if draft:
                draft.draft_data = data
                draft.version = version
                draft.current_step = min(step + 1, 5)
                draft.expires_at = expires_at
                draft.state = 'DRAFT'
                draft.save()
            else:
                draft = DrafInputPegawai.objects.create(
                    owner=request.user,
                    current_step=min(step + 1, 5),
                    draft_data=data,
                    version=version,
                    expires_at=expires_at,
                )
            if step < 5:
                return redirect('sdm:pegawai_wizard_resume', step=step + 1, draft_id=draft.pk)
            return redirect('sdm:pegawai_intake_finalize', draft_id=draft.pk)
    else:
        form_class = STEP_FORMS[step]
        initial = (draft.draft_data or {}).get(str(step), {}) if draft else {}
        form_kwargs = {"user": request.user} if step == 2 else {}
        form = form_class(initial=initial, **form_kwargs)

    units = visible_units(request.user, capability='can_manage_hc_employees')
    return render(request, 'sdm/pegawai/wizard.html', {
        'form': form,
        'step': step,
        'prev_step': step - 1,
        'step_label': STEP_LABELS[step],
        'step_labels': STEP_LABELS,
        'draft': draft,
        'units': units,
        'title': f'Input Pegawai — Langkah {step}: {STEP_LABELS[step]}',
    })


@login_required
def intake_finalize(request, draft_id):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')

    draft = get_object_or_404(_draft_queryset(request.user), pk=draft_id)
    if draft.state != 'DRAFT':
        messages.error(request, 'Draf tidak dapat diselesaikan (status: %s).' % draft.get_state_display())
        return redirect('sdm:pegawai_wizard_step', step=1)

    if request.method == 'POST':
        try:
            employee = finalize_staff_intake(
                actor=request.user,
                draft_id=draft.pk,
                expected_version=draft.version,
                idempotency_key=f'intake-{draft.pk}',
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc) or 'Gagal menyelesaikan input pegawai.')
            return redirect('sdm:pegawai_wizard_resume', step=1, draft_id=draft.pk)
        messages.success(request, 'Pegawai berhasil terdaftar.')
        return redirect('sdm:pegawai_detail', employee_id=employee.pk)

    return render(request, 'sdm/pegawai/wizard_finalize.html', {
        'draft': draft,
        'step_count': 5,
        'title': 'Selesaikan Input Pegawai',
    })


def finalize_staff_intake(*, actor, draft_id, expected_version, idempotency_key):
    """Validate all steps and staged objects; commit canonical rows once."""
    require_hc_capability(actor, 'can_view_hc')
    require_hc_capability(actor, 'can_manage_hc_employees')

    draft = get_object_or_404(DrafInputPegawai.objects.filter(owner=actor), pk=draft_id)
    if draft.state != 'DRAFT':
        raise PermissionDenied('Draf tidak dalam status yang dapat diselesaikan.')
    if draft.version != expected_version:
        raise ValidationError('Versi draf tidak sesuai. Muat ulang dan coba lagi.')
    if draft.expires_at and draft.expires_at <= timezone.now():
        draft.state = 'EXPIRED'
        draft.save(update_fields=['state', 'updated_at'])
        raise ValidationError('Draf telah kadaluarsa.')

    data = draft.draft_data or {}
    required_steps = {'1', '2'}
    missing = [s for s in required_steps if s not in data]
    if missing:
        raise ValidationError(f'Langkah belum lengkap: {", ".join(missing)}')

    step1 = data.get('1', {})
    step2 = data.get('2', {})
    step3 = data.get('3', {})
    step4 = data.get('4', {})

    # Validate personal data via shared contract.
    try:
        validate_personal_data({
            'nik': step1.get('nik', ''),
            'nama_depan': step1.get('nama_depan', ''),
            'nama_belakang': step1.get('nama_belakang', ''),
            'gelar_depan': step1.get('gelar_depan', ''),
            'gelar_belakang': step1.get('gelar_belakang', ''),
            'tempat_lahir': step1.get('tempat_lahir', ''),
            'tanggal_lahir': step1.get('tanggal_lahir'),
            'gender': step1.get('gender', ''),
            'agama': step1.get('agama', ''),
            'status_pernikahan': step1.get('status_pernikahan', ''),
            'telepon': step1.get('telepon', ''),
            'email_terverifikasi': step1.get('email_terverifikasi', ''),
            'alamat_ktp': step1.get('alamat_ktp', ''),
            'alamat_domisili': step1.get('alamat_domisili', ''),
            'alamat_sama_dengan_ktp': step1.get('alamat_sama_dengan_ktp', False),
        })
    except ValidationError as exc:
        raise ValidationError({'identitas': exc.message_dict})

    unit_pk = step2.get('unit_kerja')
    if not unit_pk:
        raise ValidationError({'unit': 'Unit kerja wajib dipilih.'})
    try:
        unit = UnitKerja.objects.get(pk=unit_pk)
    except UnitKerja.DoesNotExist:
        raise ValidationError({'unit': 'Unit kerja tidak valid.'})
    require_hc_capability(
        actor, 'can_manage_hc_employees', unit=unit
    )

    with transaction.atomic():
        # Re-check draft not concurrently finalized.
        draft.refresh_from_db()
        if draft.state != 'DRAFT' or draft.version != expected_version:
            raise ValidationError('Draf telah diperbarui di tab lain. Muat ulang.')

        employee = Pegawai.objects.create(
            nama_lengkap=' '.join(
                [p for p in (step1.get('gelar_depan', ''), step1.get('nama_depan', ''),
                             step1.get('nama_belakang', ''), step1.get('gelar_belakang', '')) if p]
            ) or 'Pegawai Baru',
            nomor_pegawai=(step2.get('nomor_pegawai') or '').strip(),
            kategori=step2.get('kategori', 'NON_PPA'),
            profesi=(step2.get('profesi') or '').strip(),
            jabatan=(step2.get('jabatan') or '').strip(),
            status=step2.get('status', 'AKTIF'),
            data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=employee,
            unit_kerja=unit,
            tanggal_mulai=step2.get('tanggal_mulai') or timezone.localdate(),
            tanggal_selesai=step2.get('tanggal_selesai'),
            alokasi_fte=step2.get('alokasi_fte') or 1.00,
        )
        RiwayatKepegawaian.objects.create(
            pegawai=employee,
            kategori_pegawai=step2.get('kategori_pegawai', 'TETAP'),
            tanggal_tmt=step2.get('tanggal_tmt'),
            tanggal_akhir=step2.get('tanggal_akhir'),
            nomor_kontrak=step2.get('nomor_kontrak', '') or '',
            tanggal_mulai_kontrak=step2.get('tanggal_mulai_kontrak'),
            tanggal_selesai_kontrak=step2.get('tanggal_selesai_kontrak'),
            jam_kontrak_per_minggu=step2.get('jam_kontrak_per_minggu'),
            jam_fulltime_referensi=step2.get('jam_fulltime_referensi') or 40.00,
            jabatan_struktural=step2.get('jabatan', '') or '',
            review_status='UNREVIEWED',
            provenance='Draf intake manual',
        )

        # Personal profile.
        profil = ProfilPribadiPegawai.objects.create(
            employee=employee,
            nik=(step1.get('nik') or '').strip(),
            nama_depan=step1.get('nama_depan', '') or '',
            nama_belakang=step1.get('nama_belakang', '') or '',
            gelar_depan=step1.get('gelar_depan', '') or '',
            gelar_belakang=step1.get('gelar_belakang', '') or '',
            tempat_lahir=step1.get('tempat_lahir', '') or '',
            tanggal_lahir=step1.get('tanggal_lahir'),
            gender=step1.get('gender', '') or '',
            agama=step1.get('agama', '') or '',
            status_pernikahan=step1.get('status_pernikahan', '') or '',
            telepon=step1.get('telepon', '') or '',
            email_terverifikasi=step1.get('email_terverifikasi', '') or '',
            alamat_ktp=step1.get('alamat_ktp', '') or '',
            alamat_domisili=step1.get('alamat_domisili') or step1.get('alamat_ktp', '') or '',
            alamat_sama_dengan_ktp=step1.get('alamat_sama_dengan_ktp', True),
        )

        # Licenses.
        if step3.get('izin_subtype'):
            IzinProfesiPegawai.objects.create(
                pegawai=employee,
                subtype=step3.get('izin_subtype'),
                nomor_izin=step3.get('nomor_izin', '') or '',
                pemberi_izin=step3.get('pemberi_izin', '') or '',
                profesi=step3.get('izin_profesi', '') or '',
                validity_mode=step3.get('validity_mode', 'DATED'),
                tanggal_terbit=step3.get('tanggal_terbit'),
                tanggal_berakhir=step3.get('tanggal_berakhir'),
                organisasi_praktik=step3.get('organisasi_praktik', '') or '',
                lokasi_praktik=step3.get('lokasi_praktik', '') or '',
                is_local_rs=bool(step3.get('is_local_rs')),
            )

        # Education.
        if step3.get('pendidikan_tingkat'):
            RiwayatPendidikanPegawai.objects.create(
                pegawai=employee,
                tingkat=step3.get('pendidikan_tingkat'),
                institusi=step3.get('pendidikan_institusi', '') or '',
                program_studi=step3.get('pendidikan_program', '') or '',
                tanggal_lulus=step3.get('tanggal_lulus'),
            )

        # Documents: metadata staged in step 5 only; file binding left to B5 import
        # or explicit upload. Here we record intent without file bytes.
        step5 = data.get('5') or {}
        document_title = step5.get('dokumen_judul', '')
        if document_title:
            DokumenPegawai.objects.create(
                employee=employee,
                document_type='OTHER',
                jenis_berkas=(step5 or {}).get('dokumen_jenis_berkas', 'OTHER'),
                title=document_title,
                sensitivity='personnel',
                created_by=actor,
            )

        draft.state = 'FINALIZED'
        draft.save(update_fields=['state', 'updated_at'])

        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='employee_created',
            target_tipe='employee',
            target_id=str(employee.pk),
            status_sesudah=employee.status,
            alasan='Dibuat melalui wizard input lima langkah.',
        )

    return employee
