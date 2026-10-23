import hashlib

from django.contrib import messages
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from sdm.akses import require_hc_capability, visible_employees, visible_units
from sdm.forms import (
    AktivitasBebanKerjaForm,
    DokumenForm,
    KebutuhanPelatihanForm,
    LamaranForm,
    LowonganForm,
    MulaiOrientasiForm,
    PegawaiCreateForm,
    PegawaiEditForm,
    PengajuanKredensialForm,
    ProgramOrientasiForm,
    RencanaFormasiForm,
    ReviewDokumenForm,
    RincianKewenanganForm,
    VerifikasiSumberForm,
)
from django.http import HttpResponse

from sdm.models import (
    AktivitasBebanKerja,
    InsidenK3Pegawai,
    KebutuhanPelatihan,
    Lamaran,
    Lowongan,
    Pegawai,
    PenempatanPegawai,
    PengajuanKredensial,
    PenilaianKinerja,
    PenilaianTalent,
    PenugasanKlinis,
    PenugasanOrientasi,
    HcGrant,
    PeristiwaSDM,
    ProgramOrientasi,
    RencanaFormasi,
    RisikoK3Pegawai,
    SesiDiklat,
    SkenarioSDM,
    SnapshotAnalitikSDM,
    VersiDokumen,
    calculate_formasi,
)
from sdm.services.kepatuhan import (
    documents_for_employee,
    evaluate_employee_compliance,
    expiry_bands,
)
from sdm.services.analitik import (
    compliance_audit,
    export_audit_pdf,
    export_audit_xlsx,
)
from sdm.services.dashboard import build_hc_dashboard
from sdm.services.formasi import approve_plan, save_plan, submit_for_review
from sdm.services.rekrutmen import (
    decide_credential,
    move_application,
    record_psv,
    start_orientation,
)
from sdm.services.penempatan import save_assignment
from sdm.storage import (
    authorize_document_download,
    review_document_version,
    store_private_document,
)
from sdm.storage_backend import PrivateStorageError


PAGE_SIZE = 25


def _form_context(request, form, title, *, employee=None):
    return render(request, 'sdm/pegawai/form.html', {
        'form': form,
        'title': title,
        'employee': employee,
    })


@login_required
def pegawai_list(request):
    require_hc_capability(request.user, 'can_view_hc')
    queryset = visible_employees(request.user).select_related('akun').order_by(
        'nama_lengkap', 'pk'
    )
    units = visible_units(request.user).order_by('level', 'order', 'code')

    search_q = request.GET.get('q', '').strip()[:100]
    if search_q:
        queryset = queryset.filter(
            Q(nama_lengkap__icontains=search_q)
            | Q(nomor_pegawai__icontains=search_q)
            | Q(profesi__icontains=search_q)
            | Q(jabatan__icontains=search_q)
        )

    unit_filter = request.GET.get('unit', '').strip()
    if unit_filter:
        try:
            unit_id = int(unit_filter)
        except (TypeError, ValueError):
            queryset = queryset.none()
        else:
            queryset = visible_employees(request.user, unit=unit_id).filter(
                pk__in=queryset.values('pk')
            ).order_by('nama_lengkap', 'pk')

    status_filter = request.GET.get('status', '').strip()
    if status_filter in dict(Pegawai.STATUS_CHOICES):
        queryset = queryset.filter(status=status_filter)

    category_filter = request.GET.get('kategori', '').strip()
    if category_filter in dict(Pegawai.KATEGORI_CHOICES):
        queryset = queryset.filter(kategori=category_filter)

    profession_filter = request.GET.get('profesi', '').strip()[:120]
    if profession_filter:
        queryset = queryset.filter(profesi__icontains=profession_filter)

    page_obj = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get('page'))
    page_employees = list(page_obj.object_list)
    employee_ids = [employee.pk for employee in page_employees]
    today = timezone.localdate()
    placements = PenempatanPegawai.objects.filter(
        pegawai_id__in=employee_ids,
        unit_kerja__in=units,
        tanggal_mulai__lte=today,
    ).filter(
        Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=today)
    ).select_related('unit_kerja').order_by('unit_kerja__level', 'unit_kerja__code')
    placements_by_employee = {}
    for placement in placements:
        placements_by_employee.setdefault(placement.pegawai_id, []).append(placement)
    for employee in page_employees:
        employee.active_placements = placements_by_employee.get(employee.pk, [])
    page_obj.object_list = page_employees

    params = request.GET.copy()
    params.pop('page', None)
    can_create = visible_units(
        request.user, capability='can_manage_hc_employees'
    ).exists()
    return render(request, 'sdm/pegawai/list.html', {
        'page_obj': page_obj,
        'units': units,
        'search_q': search_q,
        'selected_unit': unit_filter,
        'selected_status': status_filter,
        'selected_category': category_filter,
        'profession_filter': profession_filter,
        'status_choices': Pegawai.STATUS_CHOICES,
        'category_choices': Pegawai.KATEGORI_CHOICES,
        'pagination_query': params.urlencode(),
        'can_create': can_create,
    })


@login_required
def pegawai_create(request):
    require_hc_capability(request.user, 'can_view_hc')
    require_hc_capability(request.user, 'can_manage_hc_employees')
    form = PegawaiCreateForm(
        request.POST or None,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        unit = form.cleaned_data['unit_kerja']
        require_hc_capability(
            request.user, 'can_manage_hc_employees', unit=unit
        )
        try:
            with transaction.atomic():
                employee = form.save(commit=False)
                employee.full_clean()
                employee.save()
                save_assignment(PenempatanPegawai(
                    pegawai=employee,
                    unit_kerja=unit,
                    tanggal_mulai=form.cleaned_data['tanggal_mulai'],
                    tanggal_selesai=form.cleaned_data['tanggal_selesai'],
                    alokasi_fte=form.cleaned_data['alokasi_fte'],
                ))
                PeristiwaSDM.objects.create(
                    actor=request.user,
                    jenis_peristiwa='employee_created',
                    target_tipe='employee',
                    target_id=str(employee.pk),
                    status_sesudah=employee.status,
                    alasan='Pegawai dan penempatan awal dibuat.',
                )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        except IntegrityError:
            form.add_error(
                'nomor_pegawai', 'Nomor pegawai tersebut sudah digunakan.'
            )
        else:
            return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    return _form_context(request, form, 'Tambah Pegawai')


@login_required
def pegawai_edit(request, employee_id):
    employee = get_object_or_404(
        visible_employees(request.user), pk=employee_id
    )
    require_hc_capability(
        request.user, 'can_manage_hc_employees', employee=employee
    )
    form = PegawaiEditForm(request.POST or None, instance=employee)
    if request.method == 'POST' and form.is_valid():
        old_status = employee.status
        try:
            with transaction.atomic():
                updated = form.save(commit=False)
                updated.full_clean()
                updated.save()
                PeristiwaSDM.objects.create(
                    actor=request.user,
                    jenis_peristiwa='employee_updated',
                    target_tipe='employee',
                    target_id=str(updated.pk),
                    status_sebelum=old_status,
                    status_sesudah=updated.status,
                    alasan='Data kepegawaian diperbarui.',
                )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        except IntegrityError:
            form.add_error(
                'nomor_pegawai', 'Nomor pegawai tersebut sudah digunakan.'
            )
        else:
            return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    return _form_context(
        request,
        form,
        f'Edit Pegawai — {employee.nama_lengkap}',
        employee=employee,
    )


@login_required
def pegawai_detail(request, employee_id):
    employee = get_object_or_404(
        visible_employees(request.user), pk=employee_id
    )
    require_hc_capability(request.user, 'can_view_hc', employee=employee)
    units = visible_units(request.user)
    assignments = employee.penempatan.filter(
        unit_kerja__in=units
    ).select_related('unit_kerja').order_by('-tanggal_mulai', '-pk')
    documents = documents_for_employee(employee).prefetch_related('versions')
    compliance = evaluate_employee_compliance(employee)
    events = PeristiwaSDM.objects.filter(
        target_tipe='employee', target_id=str(employee.pk)
    ).exclude(jenis_peristiwa__icontains='health').select_related('actor')[:100]
    can_manage = visible_units(
        request.user, capability='can_manage_hc_employees'
    ).exists()
    can_manage_documents = visible_units(
        request.user, capability='can_manage_hc_documents'
    ).exists()
    if can_manage:
        try:
            require_hc_capability(
                request.user, 'can_manage_hc_employees', employee=employee
            )
        except PermissionDenied:
            can_manage = False
    if can_manage_documents:
        try:
            require_hc_capability(
                request.user, 'can_manage_hc_documents', employee=employee
            )
        except PermissionDenied:
            can_manage_documents = False
    return render(request, 'sdm/pegawai/detail.html', {
        'employee': employee,
        'assignments': assignments,
        'documents': documents,
        'compliance': compliance,
        'events': events,
        'can_manage': can_manage,
        'can_manage_documents': can_manage_documents,
    })


@login_required
def dokumen_upload(request, employee_id):
    employee = get_object_or_404(
        visible_employees(request.user), pk=employee_id
    )
    require_hc_capability(
        request.user, 'can_manage_hc_documents', employee=employee
    )
    form = DokumenForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            store_private_document(
                form.cleaned_data['file'],
                employee=employee,
                sensitivity=form.cleaned_data['sensitivity'],
                document_type=form.cleaned_data['document_type'],
                title=form.cleaned_data['title'],
                uploaded_by=request.user,
                issued_date=form.cleaned_data['issued_date'],
                valid_until=form.cleaned_data['valid_until'],
            )
        except (ValidationError, PrivateStorageError):
            form.add_error(
                None,
                'Dokumen gagal disimpan ke penyimpanan privat. Tidak ada data yang dicatat.',
            )
        else:
            return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    return render(request, 'sdm/dokumen/form.html', {
        'form': form,
        'employee': employee,
        'title': 'Unggah Dokumen Kepegawaian',
    })


@login_required
@require_POST
def dokumen_review(request, version_id):
    version = get_object_or_404(
        VersiDokumen.objects.select_related('document__employee'),
        pk=version_id,
    )
    employee = version.document.employee
    if version.document.sensitivity == 'health' or (
        version.document.document_type == 'HEALTH'
    ):
        raise PermissionDenied('Dokumen kesehatan kerja ditinjau melalui jalur K3.')
    get_object_or_404(visible_employees(request.user), pk=employee.pk)
    form = ReviewDokumenForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Keputusan tinjauan tidak valid.')
        return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    try:
        review_document_version(
            request.user,
            version,
            status=form.cleaned_data['status'],
            notes=form.cleaned_data['notes'],
        )
    except PermissionDenied:
        raise
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, 'Status dokumen berhasil diperbarui.')
    return redirect('sdm:pegawai_detail', employee_id=employee.pk)


@login_required
def dokumen_download(request, version_id):
    version = get_object_or_404(
        VersiDokumen.objects.select_related('document__employee'), pk=version_id
    )
    if version.document.sensitivity == 'health' or (
        version.document.document_type == 'HEALTH'
    ):
        raise PermissionDenied('Dokumen kesehatan kerja tidak tersedia di sini.')
    signed_url = authorize_document_download(request.user, version)
    return redirect(signed_url)


@login_required
def formasi_list(request):
    require_hc_capability(request.user, 'can_plan_hc_workforce')
    units = visible_units(request.user, capability='can_plan_hc_workforce')
    plans = RencanaFormasi.objects.filter(unit_kerja__in=units).select_related(
        'unit_kerja', 'result'
    ).order_by('-periode_mulai', 'unit_kerja__code')
    return render(request, 'sdm/formasi/daftar.html', {
        'plans': plans,
        'can_create': units.exists(),
    })


@login_required
def formasi_create(request):
    require_hc_capability(request.user, 'can_plan_hc_workforce')
    form = RencanaFormasiForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        plan = form.save(commit=False)
        plan.created_by = request.user
        try:
            save_plan(plan, user=request.user)
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            return redirect('sdm:formasi_detail', plan_id=plan.pk)
    return render(request, 'sdm/formasi/form.html', {
        'form': form,
        'title': 'Rencana Formasi Baru',
    })


@login_required
def formasi_detail(request, plan_id):
    units = visible_units(request.user, capability='can_plan_hc_workforce')
    plan = get_object_or_404(
        RencanaFormasi.objects.select_related('unit_kerja'), pk=plan_id,
        unit_kerja__in=units,
    )
    require_hc_capability(
        request.user, 'can_plan_hc_workforce', unit=plan.unit_kerja_id
    )
    activities = plan.activities.all()
    calculation = None
    if plan.status != 'DRAFT':
        try:
            calculation = calculate_formasi(plan)
        except ValidationError as exc:
            calculation = {'error': '; '.join(exc.messages)}
    return render(request, 'sdm/formasi/detail.html', {
        'plan': plan,
        'activities': activities,
        'calculation': calculation,
        'activity_form': AktivitasBebanKerjaForm(),
        'can_edit': plan.status == 'DRAFT',
    })


@login_required
@require_POST
def formasi_add_activity(request, plan_id):
    units = visible_units(request.user, capability='can_plan_hc_workforce')
    plan = get_object_or_404(
        RencanaFormasi.objects.select_related('unit_kerja'), pk=plan_id,
        unit_kerja__in=units,
    )
    require_hc_capability(
        request.user, 'can_plan_hc_workforce', unit=plan.unit_kerja_id
    )
    if plan.status != 'DRAFT':
        messages.error(request, 'Aktivitas hanya dapat diubah pada draf.')
        return redirect('sdm:formasi_detail', plan_id=plan.pk)
    form = AktivitasBebanKerjaForm(request.POST)
    if form.is_valid():
        form.save(plan)
    else:
        messages.error(request, 'Aktivitas tidak valid.')
    return redirect('sdm:formasi_detail', plan_id=plan.pk)


@login_required
@require_POST
def formasi_submit(request, plan_id):
    units = visible_units(request.user, capability='can_plan_hc_workforce')
    plan = get_object_or_404(
        RencanaFormasi.objects.filter(pk=plan_id, unit_kerja__in=units)
    )
    try:
        submit_for_review(plan, user=request.user)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, 'Rencana diajukan untuk tinjauan.')
    return redirect('sdm:formasi_detail', plan_id=plan.pk)


@login_required
@require_POST
def formasi_approve(request, plan_id):
    units = visible_units(request.user, capability='can_plan_hc_workforce')
    plan = get_object_or_404(
        RencanaFormasi.objects.filter(pk=plan_id, unit_kerja__in=units)
    )
    try:
        approve_plan(plan, user=request.user)
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Rencana formasi disetujui.')
    return redirect('sdm:formasi_detail', plan_id=plan.pk)


@login_required
def dashboard(request):
    unit_id = (request.GET.get('unit') or '').strip()
    unit = None
    if unit_id:
        units = visible_units(request.user)
        unit = units.filter(pk=unit_id).first() if unit_id.isdigit() else None
    profesi = request.GET.get('profesi', '')
    status = request.GET.get('status', '')
    metrics = _cached_dashboard(request.user, unit, profesi, status)
    cache.set('hc-dashboard-nav:' + str(request.user.pk), True, 120)
    return render(request, 'sdm/dashboard.html', {
        **metrics,
        'unit_options': visible_units(request.user).order_by('level', 'order', 'code'),
        'selected_unit': str(unit.pk) if unit else '',
        'profession_choices': (
            visible_employees(request.user)
            .exclude(profesi='')
            .values_list('profesi', flat=True)
            .distinct()
            .order_by('profesi')
        ),
        'status_choices': Pegawai.STATUS_CHOICES,
        'nav_items': _hc_navigation(request.user),
    })


def _dashboard_cache_key(user, unit, profesi, status):
    """Cache key scoped by identity, permissions, unit, profession and status."""
    capabilities = sorted(
        (capability, unit_id if unit_id is not None else -1)
        for capability, unit_id in HcGrant.objects.filter(
            user=user, is_active=True
        ).values_list('capability', 'unit_kerja_id')
    )
    version = cache.get('hc-dashboard-version', 0)
    digest = hashlib.sha256(
        f'{user.pk}|{user.is_superuser}|{capabilities}|{getattr(unit, "pk", "")}'
        f'|{profesi}|{status}|{version}'.encode('utf-8')
    ).hexdigest()[:32]
    return f'hc-dashboard:{digest}'


def _cached_dashboard(user, unit, profesi, status):
    key = _dashboard_cache_key(user, unit, profesi, status)
    cached = cache.get(key)
    if cached is not None:
        return cached
    metrics = build_hc_dashboard(user, filters={
        'unit': unit, 'profesi': profesi, 'status': status,
    })
    cache.set(key, metrics, 120)
    return metrics


def _hc_navigation(user):
    """Return only entry points the user may actually open."""
    from sdm.akses import visible_units as _units

    items = []
    if _units(user, capability='can_view_hc').exists():
        items.append({'url_name': 'sdm:pegawai_list', 'label': 'Direktori Pegawai'})
    if _units(user, capability='can_plan_hc_workforce').exists():
        items.append({'url_name': 'sdm:formasi_list', 'label': 'Peta Ketenagaan'})
    return items


# ── Level 2–5 entry points ────────────────────────────────────────────────

def _scoped_or_404(model, user, pk, *, capability, **filters):
    units = visible_units(user, capability=capability)
    return get_object_or_404(
        model.objects.filter(**filters), pk=pk, unit_kerja__in=units
    )


@login_required
def rekrutmen_list(request):
    require_hc_capability(request.user, 'can_manage_hc_recruitment')
    units = visible_units(request.user, capability='can_manage_hc_recruitment')
    vacancies = Lowongan.objects.filter(unit_kerja__in=units).select_related(
        'unit_kerja'
    ).prefetch_related('applications')
    return render(request, 'sdm/rekrutmen/daftar.html', {
        'vacancies': vacancies,
        'can_create': units.exists(),
    })


@login_required
def rekrutmen_detail(request, vacancy_id):
    vacancy = _scoped_or_404(
        Lowongan, request.user, vacancy_id,
        capability='can_manage_hc_recruitment',
    )
    require_hc_capability(
        request.user, 'can_manage_hc_recruitment', unit=vacancy.unit_kerja_id
    )
    return render(request, 'sdm/rekrutmen/detail.html', {
        'vacancy': vacancy,
        'applications': vacancy.applications.select_related('employee').prefetch_related('history'),
        'stage_choices': Lamaran.STATUS_CHOICES,
    })


@login_required
@require_POST
def rekrutmen_move(request, application_id):
    application = get_object_or_404(
        Lamaran.objects.select_related('lowongan'),
        pk=application_id,
        lowongan__unit_kerja__in=visible_units(
            request.user, capability='can_manage_hc_recruitment'
        ),
    )
    try:
        move_application(
            application,
            target=request.POST.get('status', ''),
            actor=request.user,
            notes=(request.POST.get('notes') or '')[:500],
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Tahap lamaran diperbarui.')
    return redirect('sdm:rekrutmen_detail', vacancy_id=application.lowongan_id)


@login_required
def kredensial_list(request):
    require_hc_capability(request.user, 'can_review_hc_credentials')
    units = visible_units(request.user, capability='can_review_hc_credentials')
    requests_qs = PengajuanKredensial.objects.filter(
        unit_kerja__in=units
    ).select_related('employee', 'unit_kerja').order_by('-created_at')
    return render(request, 'sdm/kredensial/daftar.html', {'requests': requests_qs})


@login_required
def kredensial_detail(request, request_id):
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    return render(request, 'sdm/kredensial/detail.html', {
        'credential_request': credential_request,
        'privileges': credential_request.privileges.all(),
        'psv_records': credential_request.employee.psv_records.select_related('version')[:20],
        'spk_list': credential_request.employee.clinical_assignments.select_related('decision'),
    })


@login_required
@require_POST
def kredensial_decide(request, request_id):
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    try:
        decide_credential(
            credential_request,
            actor=request.user,
            outcome=request.POST.get('outcome', ''),
            notes=(request.POST.get('notes') or '')[:2000],
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Keputusan komite dicatat.')
    return redirect('sdm:kredensial_detail', request_id=credential_request.pk)


@login_required
def kredensial_cetak_spk(request, assignment_id):
    assignment = _scoped_or_404(
        PenugasanKlinis, request.user, assignment_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials', unit=assignment.unit_kerja_id
    )
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='spk_printed',
        target_tipe='clinical_assignment',
        target_id=str(assignment.pk),
        status_sesudah='PRINTED',
        alasan='spk render requested',
    )
    return render(request, 'sdm/kredensial/cetak_spk.html', {'assignment': assignment})


@login_required
def orientasi_list(request):
    require_hc_capability(request.user, 'can_manage_hc_orientation')
    units = visible_units(request.user, capability='can_manage_hc_orientation')
    assignments = PenugasanOrientasi.objects.filter(
        unit_kerja__in=units
    ).select_related('employee', 'program', 'unit_kerja').prefetch_related('completions')
    return render(request, 'sdm/orientasi/daftar.html', {'assignments': assignments})


@login_required
def orientasi_detail(request, assignment_id):
    assignment = _scoped_or_404(
        PenugasanOrientasi, request.user, assignment_id,
        capability='can_manage_hc_orientation',
    )
    require_hc_capability(
        request.user, 'can_manage_hc_orientation', unit=assignment.unit_kerja_id
    )
    return render(request, 'sdm/orientasi/detail.html', {
        'assignment': assignment,
        'completions': assignment.completions.select_related('activity'),
        'progress': assignment.progress_pct,
    })


@login_required
def kinerja_list(request):
    require_hc_capability(request.user, 'can_manage_hc_appraisals')
    units = visible_units(request.user, capability='can_manage_hc_appraisals')
    appraisals = PenilaianKinerja.objects.filter(
        employee__penempatan__unit_kerja__in=units
    ).distinct().select_related('employee', 'periode')
    return render(request, 'sdm/kinerja/daftar.html', {'appraisals': appraisals})


@login_required
def diklat_list(request):
    require_hc_capability(request.user, 'can_manage_hc_training')
    sessions = SesiDiklat.objects.select_related('program').prefetch_related(
        'participants'
    ).order_by('-tanggal')
    return render(request, 'sdm/diklat/daftar.html', {'sessions': sessions})


@login_required
def k3_list(request):
    require_hc_capability(request.user, 'hc_health_write')
    units = visible_units(request.user, capability='hc_health_write')
    incidents = InsidenK3Pegawai.objects.filter(
        unit_kerja__in=units
    ).select_related('employee', 'unit_kerja').prefetch_related('followups')
    return render(request, 'sdm/k3/daftar.html', {
        'incidents': incidents,
        'risks': RisikoK3Pegawai.objects.filter(unit_kerja__in=units),
        'unit_options': units.order_by('level', 'order', 'code'),
        'employee_options': visible_employees(request.user).order_by('nama_lengkap'),
    })


@login_required
def analitik_dashboard(request):
    require_hc_capability(request.user, 'can_view_hc_analytics')
    units = visible_units(request.user, capability='can_view_hc_analytics')
    unit = units.filter(pk=request.GET.get('unit')).first() if request.GET.get('unit', '').isdigit() else units.first()
    audit = None
    if unit is not None:
        audit = compliance_audit(user=request.user, unit=unit)
    return render(request, 'sdm/analitik/daftar.html', {
        'unit_options': units.order_by('level', 'order', 'code'),
        'selected_unit': unit,
        'audit': audit,
        'snapshots': SnapshotAnalitikSDM.objects.filter(unit_kerja__in=units)[:20],
        'scenarios': SkenarioSDM.objects.filter(unit_kerja__in=units)[:20],
        'talents': PenilaianTalent.objects.filter(
            employee__penempatan__unit_kerja__in=units
        ).distinct()[:20],
    })


@login_required
def analitik_export(request):
    require_hc_capability(request.user, 'can_export_hc')
    units = visible_units(request.user, capability='can_export_hc')
    unit = units.filter(pk=request.GET.get('unit')).first() if request.GET.get('unit', '').isdigit() else units.first()
    if unit is None:
        raise PermissionDenied('Tidak ada unit dalam lingkup ekspor.')
    audit = compliance_audit(user=request.user, unit=unit)
    payload = export_audit_xlsx(audit)
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='hc_audit_exported',
        target_tipe='unit',
        target_id=str(unit.pk),
        status_sesudah='EXPORTED',
        alasan='redacted compliance audit export',
    )
    response = HttpResponse(
        payload,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="audit-kepatuhan-{unit.code}.xlsx"'
    )
    return response


# ── Level 2–5 create actions ──────────────────────────────────────────────

@login_required
def rekrutmen_create(request):
    require_hc_capability(request.user, 'can_manage_hc_recruitment')
    form = LowonganForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        vacancy = form.save(commit=False)
        vacancy.created_by = request.user
        vacancy.save()
        return redirect('sdm:rekrutmen_detail', vacancy_id=vacancy.pk)
    return render(request, 'sdm/rekrutmen/form.html', {
        'form': form, 'title': 'Lowongan Baru',
    })


@login_required
@require_POST
def rekrutmen_add_application(request, vacancy_id):
    vacancy = _scoped_or_404(
        Lowongan, request.user, vacancy_id,
        capability='can_manage_hc_recruitment',
    )
    require_hc_capability(
        request.user, 'can_manage_hc_recruitment', unit=vacancy.unit_kerja_id
    )
    form = LamaranForm(request.POST)
    if form.is_valid():
        application = form.save(commit=False)
        application.lowongan = vacancy
        application.save()
        messages.success(request, 'Lamaran dicatat.')
    else:
        messages.error(request, 'Data lamaran tidak valid.')
    return redirect('sdm:rekrutmen_detail', vacancy_id=vacancy.pk)


@login_required
def kredensial_create(request):
    require_hc_capability(request.user, 'can_review_hc_credentials')
    form = PengajuanKredensialForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        credential_request = form.save(commit=False)
        credential_request.submitted_by = request.user
        require_hc_capability(
            request.user, 'can_review_hc_credentials',
            unit=credential_request.unit_kerja_id,
        )
        credential_request.save()
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
    return render(request, 'sdm/kredensial/form.html', {
        'form': form, 'title': 'Pengajuan Kredensial Baru',
    })


@login_required
@require_POST
def kredensial_add_privilege(request, request_id):
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    form = RincianKewenanganForm(request.POST)
    if form.is_valid():
        privilege = form.save(commit=False)
        privilege.pengajuan = credential_request
        privilege.save()
    else:
        messages.error(request, 'Rincian kewenangan tidak valid.')
    return redirect('sdm:kredensial_detail', request_id=credential_request.pk)


@login_required
@require_POST
def kredensial_psv(request, request_id):
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    form = VerifikasiSumberForm(request.POST)
    version = credential_request.employee.documents.filter(
        document_type='CREDENTIAL', versions__status='VERIFIED'
    ).order_by('-created_at').first()
    if version is None:
        messages.error(request, 'Belum ada dokumen kredensial terverifikasi.')
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
    if not form.is_valid():
        messages.error(request, 'Data PSV tidak valid.')
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
    try:
        record_psv(
            credential_request.employee,
            version.versions.filter(status='VERIFIED').first(),
            actor=request.user,
            issuer=form.cleaned_data['issuer'],
            reference=form.cleaned_data['reference'],
            method=form.cleaned_data['method'],
            outcome=form.cleaned_data['outcome'],
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'PSV tercatat.')
    return redirect('sdm:kredensial_detail', request_id=credential_request.pk)


@login_required
def orientasi_create(request):
    require_hc_capability(request.user, 'can_manage_hc_orientation')
    program_form = ProgramOrientasiForm(request.POST or None, user=request.user)
    start_form = MulaiOrientasiForm(request.POST or None, user=request.user)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'program' and program_form.is_valid():
            program_form.save()
            messages.success(request, 'Program orientasi dibuat.')
            return redirect('sdm:orientasi_create')
        if action == 'assign' and start_form.is_valid():
            try:
                start_orientation(
                    start_form.cleaned_data['employee'],
                    start_form.cleaned_data['program'],
                    actor=request.user,
                )
            except (PermissionDenied, ValidationError) as exc:
                message = getattr(exc, 'messages', None)
                messages.error(request, '; '.join(message) if message else str(exc))
            else:
                messages.success(request, 'Orientasi dimulai.')
                return redirect('sdm:orientasi_list')
    return render(request, 'sdm/orientasi/form.html', {
        'program_form': program_form, 'start_form': start_form,
        'title': 'Program & Penugasan Orientasi',
    })


@login_required
@require_POST
def orientasi_complete(request, completion_id):
    from sdm.models import PenyelesaianOrientasi
    from sdm.services.rekrutmen import complete_activity

    completion = get_object_or_404(
        PenyelesaianOrientasi.objects.select_related('assignment__employee'),
        pk=completion_id,
        assignment__unit_kerja__in=visible_units(
            request.user, capability='can_manage_hc_orientation'
        ),
    )
    try:
        complete_activity(
            completion, actor=request.user,
            notes=(request.POST.get('notes') or '')[:500],
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Aktivitas orientasi ditandatangani.')
    return redirect('sdm:orientasi_detail', assignment_id=completion.assignment_id)


@login_required
@require_POST
def kinerja_finalize(request, appraisal_id):
    from sdm.services.kinerja import finalize_appraisal

    appraisal = get_object_or_404(
        PenilaianKinerja.objects.filter(
            employee__penempatan__unit_kerja__in=visible_units(
                request.user, capability='can_manage_hc_appraisals'
            )
        ).distinct(),
        pk=appraisal_id,
    )
    try:
        finalize_appraisal(appraisal, actor=request.user)
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Penilaian difinalkan.')
    return redirect('sdm:kinerja_list')


@login_required
def diklat_create(request):
    require_hc_capability(request.user, 'can_manage_hc_training')
    form = KebutuhanPelatihanForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        need = form.save(commit=False)
        unit = visible_units(
            request.user, capability='can_manage_hc_training'
        ).first()
        if unit is None:
            raise PermissionDenied('Tidak ada unit dalam lingkup pelatihan.')
        need.unit_kerja = unit
        need.rule_version = 'manual-v1'
        need.save()
        return redirect('sdm:diklat_list')
    return render(request, 'sdm/diklat/form.html', {
        'form': form, 'title': 'Usulan Kebutuhan Pelatihan',
    })


@login_required
@require_POST
def diklat_certificate(request, participant_id):
    from sdm.models import PesertaDiklat
    from sdm.services.kinerja import issue_certificate

    participant = get_object_or_404(
        PesertaDiklat.objects.select_related('sesi__program', 'employee'),
        pk=participant_id,
    )
    try:
        certificate = issue_certificate(participant, actor=request.user)
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, f'Sertifikat {certificate.nomor} diterbitkan.')
    return redirect('sdm:diklat_list')


@login_required
@require_POST
def k3_report(request):
    from sdm.services.k3 import report_incident

    unit_id = (request.POST.get('unit') or '').strip()
    employee_id = (request.POST.get('employee') or '').strip()
    unit = None
    if unit_id.isdigit():
        unit = visible_units(request.user, capability='hc_health_write').filter(
            pk=unit_id
        ).first()
    employee = None
    if unit is not None and employee_id:
        employee = visible_employees(request.user, unit=unit).filter(
            pk=employee_id
        ).first()
    if unit is None or employee is None:
        messages.error(request, 'Unit atau pegawai di luar lingkup.')
        return redirect('sdm:k3_list')
    try:
        report_incident(
            employee, actor=request.user, unit_kerja=unit,
            kategori=request.POST.get('kategori', ''),
            deskripsi=(request.POST.get('deskripsi') or '')[:2000],
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Insiden K3 dicatat.')
    return redirect('sdm:k3_list')


@login_required
def analitik_export_pdf(request):
    require_hc_capability(request.user, 'can_export_hc')
    units = visible_units(request.user, capability='can_export_hc')
    unit = units.filter(pk=request.GET.get('unit')).first() if request.GET.get('unit', '').isdigit() else units.first()
    if unit is None:
        raise PermissionDenied('Tidak ada unit dalam lingkup ekspor.')
    audit = compliance_audit(user=request.user, unit=unit)
    payload = export_audit_pdf(audit)
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='hc_audit_exported',
        target_tipe='unit',
        target_id=str(unit.pk),
        status_sesudah='EXPORTED',
        alasan='redacted compliance audit pdf export',
    )
    response = HttpResponse(payload, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="audit-kepatuhan-{unit.code}.pdf"'
    )
    return response
