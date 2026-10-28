import datetime
import hashlib
from datetime import timedelta

from django.contrib import messages
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from sdm.akses import require_hc_capability, visible_employees, visible_units
from sdm.services.logbook import entries_to_verify, logbook_recap, verify_entry
from sdm.services.dokumen_kredensial import (
    REGISTRY as DOKUMEN_KREDENSIAL_REGISTRY,
    finalize as finalize_dokumen_kredensial,
    generate_draft as generate_dokumen_kredensial,
)
from sdm.forms.kredensial_portal import PengajuanPortalForm
from sdm.forms import (
    AktivitasBebanKerjaForm,
    DokumenForm,
    EntriLogbookForm,
    KebutuhanPelatihanForm,
    LamaranForm,
    LowonganForm,
    MulaiOrientasiForm,
    PegawaiCreateForm,
    PegawaiEditForm,
    PengajuanKredensialForm,
    PenilaianTindakanFormSet,
    ProgramOrientasiForm,
    RencanaFormasiForm,
    ReviewDokumenForm,
    RiwayatKepegawaianForm,
    RincianKewenanganForm,
    VerifikasiSumberForm,
    ImunisasiPegawaiForm,
    InsidenK3PegawaiForm,
    PemeriksaanKesehatanKerjaForm,
    TindakLanjutK3Form,
)
from django.http import HttpResponse

from sdm.models import (
    AktivitasBebanKerja,
    EntriLogbookKlinis,
    VerifikasiLogbook,
    InsidenK3Pegawai,
    KebutuhanPelatihan,
    Lamaran,
    Lowongan,
    Pegawai,
    PenempatanPegawai,
    DokumenSyaratKredensial,
    DokumenPegawai,
    DrafDokumenKredensial,
    TahapKredensial,
    PengajuanKredensial,
    PenilaianTindakan,
    PenilaianKinerja,
    PeriodeKinerja,
    ButirPenilaian,
    TahapPenilaian,
    PenilaianTalent,
    PenugasanKlinis,
    PenugasanOrientasi,
    HcGrant,
    KatalogTindakan,
    MasterJenjangProfesi,
    MasterProfesiPegawai,
    PeristiwaSDM,
    PrivilegeSnapshot,
    ProgramOrientasi,
    RincianKewenangan,
    RencanaFormasi,
    RiwayatKepegawaian,
    ImunisasiPegawai,
    InsidenK3Pegawai,
    PemeriksaanKesehatanKerja,
    RisikoK3Pegawai,
    SesiDiklat,
    TindakLanjutK3,
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
from sdm.services.formasi import (
    save_plan, submit_for_review, review_hrd, review_budget,
    review_director,
)
from sdm.services.k3 import (
    add_followup,
    record_health_exam,
    record_immunization,
    report_incident,
)
from sdm.services.rekrutmen import (
    decide_credential,
    move_application,
    record_psv,
    rekomendasikan_kredensial,
    revoke_spk,
    start_orientation,
    terbitkan_spk_lengkap,
)
from sdm.services.clinical_access import revoke_spk as revoke_spk_privileges
from sdm.services.publikasi_bukti import build_kps_pack, publish_kps_artifact
from sdm.services.penempatan import save_assignment
from sdm.storage import (
    authorize_document_download,
    get_private_storage,
    review_document_version,
    store_private_document,
)
from sdm.services.intake import build_staff_profile
from sdm.services.profil_kredensial import credential_profile
from sdm.services.workflow_kredensial import (
    current_stage,
    current_stage_row,
    stage_history,
    stepper_rows,
)
from sdm.services.syarat_kredensial import (
    DEFAULT_ROWS as DEFAULT_SYARAT_ROWS,
    evaluate_employee_requirements,
    evaluate_requirements,
    populate_requirements,
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
def riwayat_create(request, employee_id):
    employee = get_object_or_404(
        visible_employees(request.user), pk=employee_id
    )
    require_hc_capability(request.user, 'can_manage_hc_employees', employee=employee)
    form = RiwayatKepegawaianForm(request.POST or None, employee=employee)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                history = form.save()
                PeristiwaSDM.objects.create(
                    actor=request.user,
                    jenis_peristiwa='riwayat_kepegawaian_created',
                    target_tipe='employee',
                    target_id=str(employee.pk),
                    status_sesudah=history.kategori_pegawai,
                    alasan=f'Riwayat kepegawaian ditambahkan (TMT {history.tanggal_tmt or "belum dicatat"}).',
                )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    return _form_context(
        request,
        form,
        f'Tambah Riwayat Kepegawaian — {employee.nama_lengkap}',
        employee=employee,
    )


@login_required
def riwayat_edit(request, employee_id, riwayat_id):
    history = get_object_or_404(
        RiwayatKepegawaian.objects.filter(pegawai__in=visible_employees(request.user)),
        pk=riwayat_id,
    )
    if history.pegawai_id != employee_id:
        raise Http404('Riwayat kepegawaian tidak ditemukan.')
    require_hc_capability(request.user, 'can_manage_hc_employees', employee=history.pegawai)
    form = RiwayatKepegawaianForm(
        request.POST or None, instance=history, employee=history.pegawai
    )
    if request.method == 'POST' and form.is_valid():
        before = history.kategori_pegawai
        try:
            with transaction.atomic():
                updated = form.save()
                PeristiwaSDM.objects.create(
                    actor=request.user,
                    jenis_peristiwa='riwayat_kepegawaian_updated',
                    target_tipe='employee',
                    target_id=str(updated.pegawai_id),
                    status_sebelum=before,
                    status_sesudah=updated.kategori_pegawai,
                    alasan='Riwayat kepegawaian diperbarui.',
                )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            return redirect('sdm:pegawai_detail', employee_id=history.pegawai_id)
    return _form_context(
        request,
        form,
        f'Ubah Riwayat Kepegawaian — {history.pegawai.nama_lengkap}',
        employee=history.pegawai,
    )


@login_required
def riwayat_delete(request, employee_id, riwayat_id):
    history = get_object_or_404(
        RiwayatKepegawaian.objects.filter(pegawai__in=visible_employees(request.user)),
        pk=riwayat_id,
    )
    if history.pegawai_id != employee_id:
        raise Http404('Riwayat kepegawaian tidak ditemukan.')
    require_hc_capability(request.user, 'can_manage_hc_employees', employee=history.pegawai)
    if request.method == 'POST':
        siblings = RiwayatKepegawaian.objects.filter(
            pegawai=history.pegawai
        ).exclude(pk=history.pk).count()
        if siblings == 0:
            messages.error(
                request,
                'Riwayat terakhir tidak dapat dihapus; pegawai wajib memiliki minimal satu riwayat kepegawaian.',
            )
            return redirect('sdm:pegawai_detail', employee_id=history.pegawai_id)
        with transaction.atomic():
            RiwayatKepegawaian.objects.filter(pk=history.pk).delete()
            PeristiwaSDM.objects.create(
                actor=request.user,
                jenis_peristiwa='riwayat_kepegawaian_deleted',
                target_tipe='employee',
                target_id=str(history.pegawai_id),
                status_sebelum=history.kategori_pegawai,
                alasan=f'Riwayat dihapus (TMT {history.tanggal_tmt or "belum dicatat"}).',
            )
    return redirect('sdm:pegawai_detail', employee_id=history.pegawai_id)


@login_required
def pegawai_detail(request, employee_id):
    employee = get_object_or_404(
        visible_employees(request.user), pk=employee_id
    )
    require_hc_capability(request.user, 'can_view_hc', employee=employee)
    units = visible_units(request.user)
    assignments = employee.penempatan.filter(
        unit_kerja__in=units
    ).select_related('unit_kerja', 'unit_induk').order_by('-tanggal_mulai', '-pk')
    # Penempatan yang sedang berjalan adalah yang menentukan unit profil; riwayat
    # diurutkan dari yang terbaru, jadi ambil yang tanggal mulainya <= hari ini.
    today = timezone.localdate()
    current_placement = next(
        (a for a in assignments if a.is_current and a.tanggal_mulai <= today),
        assignments.first() if assignments else None,
    )
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
    from sdm.services.legalitas import legal_status
    legal = legal_status(employee)
    return render(request, 'sdm/pegawai/detail.html', {
        'employee': employee,
        'profile': build_staff_profile(employee, viewer=request.user),
        'assignments': assignments,
        'current_placement': current_placement,
        'documents': documents,
        'compliance': compliance,
        'events': events,
        'can_manage': can_manage,
        'can_manage_documents': can_manage_documents,
        'riwayat_list': employee.riwayat_kepegawaian.order_by('-tanggal_tmt', '-pk'),
        'legal': legal,
    })


@login_required
def pegawai_avatar(request, employee_id):
    employee = get_object_or_404(visible_employees(request.user), pk=employee_id)
    require_hc_capability(request.user, 'can_view_hc', employee=employee)
    personal = getattr(employee, 'profil_pribadi', None)
    version = getattr(personal, 'foto_profil_versi', None)
    if version is None:
        raise Http404('Foto profil belum tersedia.')
    document = version.document
    if (
        document.employee_id != employee.pk
        or document.document_type != 'IDENTITY'
        or document.jenis_berkas != 'FOTO'
        or document.sensitivity != 'personnel'
        or version.content_type != 'image/jpeg'
        or version.status not in ('PENDING', 'VERIFIED')
        or not 1 <= version.size_bytes <= 2_000_000
    ):
        raise Http404('Foto profil belum tersedia.')
    storage = get_private_storage()
    try:
        data = storage.fetch_object(version.storage_key, max_bytes=2_000_000)
    except PrivateStorageError:
        raise Http404('Foto profil tidak dapat dibaca.') from None
    if (
        len(data) != version.size_bytes
        or not data.startswith(b'\xff\xd8\xff')
        or hashlib.sha256(data).hexdigest() != version.sha256
    ):
        raise Http404('Foto profil tidak dapat dibaca.')
    response = HttpResponse(data, content_type='image/jpeg')
    response['Cache-Control'] = 'private, max-age=300'
    response['Content-Disposition'] = 'inline'
    return response


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
        if form.cleaned_data['sensitivity'] == 'health':
            # Health documents need a separate capability; check it here so the
            # user sees a form error instead of a bare 403 mid-save.
            try:
                require_hc_capability(
                    request.user, 'hc_health_write', employee=employee,
                )
            except PermissionDenied:
                form.add_error(
                    'sensitivity',
                    'Dokumen kesehatan kerja memerlukan hak akses Kesehatan Kerja '
                    '(hc_health_write); minta pemberian akses kepada admin SDM.',
                )
                return render(request, 'sdm/dokumen/form.html', {
                    'form': form,
                    'employee': employee,
                    'title': 'Unggah Dokumen Kepegawaian',
                })
        try:
            document, _version = store_private_document(
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
            # store_private_document has no kind parameter; record it on the
            # document it just returned so the requirement checklist can match.
            document.jenis_berkas = form.cleaned_data['jenis_berkas']
            document.save(update_fields=['jenis_berkas'])
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
        review_director(plan, user=request.user)
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Rencana formasi disetujui.')
    return redirect('sdm:formasi_detail', plan_id=plan.pk)


@login_required
def formasi_peta(request):
    """Gap analysis map with four-band risk coding (F-A3).

    Only plans carrying an approved, immutable result appear. A plan still in
    draft is reported as `Belum dapat dihitung`, never coloured.
    """
    from sdm.services.risiko import gap_rows, gap_totals

    require_hc_capability(request.user, 'can_plan_hc_workforce')
    units = visible_units(request.user, capability='can_plan_hc_workforce')

    unit_id = (request.GET.get('unit') or '').strip()
    selected_unit = None
    if unit_id.isdigit():
        selected_unit = units.filter(pk=unit_id).first()

    profesi = (request.GET.get('profesi') or '').strip()[:120]
    hanya_defisit = request.GET.get('hanya_defisit') in ('1', 'on', 'true')

    rows = gap_rows(
        request.user,
        unit=selected_unit,
        profesi=profesi,
        hanya_defisit=hanya_defisit,
    )

    pending_count = RencanaFormasi.objects.filter(
        unit_kerja__in=units,
    ).exclude(status='APPROVED').count()

    return render(request, 'sdm/formasi/peta.html', {
        'rows': rows,
        'totals': gap_totals(rows),
        'units': units.order_by('level', 'order', 'code'),
        'selected_unit': str(selected_unit.pk) if selected_unit else '',
        'profesi': profesi,
        'hanya_defisit': hanya_defisit,
        'pending_count': pending_count,
        'profession_options': (
            RencanaFormasi.objects.filter(unit_kerja__in=units)
            .exclude(profesi='')
            .values_list('profesi', flat=True)
            .distinct()
            .order_by('profesi')
        ),
    })


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


def privileges_without_penilaian(credential_request):
    """Privilege lines that have no peer-review verdict yet, in display order."""
    judged = set(
        credential_request.penilaian_tindakan.values_list('rincian_id', flat=True)
    )
    return [
        rincian for rincian in credential_request.privileges.all()
        if rincian.pk not in judged
    ]


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
    """Landing page: six Kredensial sub-menu cards (pola dashboard sdm)."""
    require_hc_capability(request.user, 'can_review_hc_credentials')
    cards = [
        {
            'level': 'A', 'title': 'Master Katalog RKK',
            'description': 'Katalog kewenangan klinis per jenjang karir dan tingkat supervisi.',
            'links': [{'url_name': 'sdm:kredensial_katalog', 'label': 'Buka Katalog',
                       'allowed': True}],
        },
        {
            'level': 'B', 'title': 'Pengajuan Mandiri',
            'description': 'Portal pengajuan mandiri: kredensial awal, re-kredensial 3 tahunan, penambahan kewenangan.',
            'links': [
                {'url_name': 'sdm:kredensial_pengajuan_sendiri', 'label': 'Pengajuan Saya',
                 'allowed': True},
                {'url_name': 'sdm:kredensial_create', 'label': 'Ajukan untuk Pegawai',
                 'allowed': True},
            ],
        },
        {
            'level': 'C', 'title': 'Verifikasi & Mitra Bestari',
            'description': 'Daftar pengajuan, PSV, dan panel evaluasi mitra bestari.',
            'links': [{'url_name': 'sdm:kredensial_daftar_pengajuan', 'label': 'Daftar Pengajuan',
                       'allowed': True}],
        },
        {
            'level': 'D', 'title': 'E-SPK & E-RKK',
            'description': 'Penerbitan SPK/RKK oleh Direktur Utama beserta pencetakan.',
            'links': [{'url_name': 'sdm:kredensial_spk_list', 'label': 'Daftar SPK',
                       'allowed': True}],
        },
        {
            'level': 'E', 'title': 'Kontrol Akses RME',
            'description': 'Pemetaan kewenangan efektif dan tindakan terkunci di RME.',
            'links': [{'url_name': 'sdm:kredensial_akses_rme', 'label': 'Lihat Akses',
                       'allowed': True}],
        },
        {
            'level': 'F', 'title': 'Peta & Direktori Kewenangan',
            'description': 'Pencarian cepat wewenang klinis staf per unit.',
            'links': [{'url_name': 'sdm:kredensial_peta', 'label': 'Buka Peta',
                       'allowed': True}],
        },
    ]
    return render(request, 'sdm/kredensial/landing.html', {
        'sub_menu_cards': cards,
    })


@login_required
def kredensial_daftar_pengajuan(request):
    """Filtered, paginated list of credential requests (pola pegawai_list)."""
    require_hc_capability(request.user, 'can_review_hc_credentials')
    units = visible_units(request.user, capability='can_review_hc_credentials')
    queryset = PengajuanKredensial.objects.filter(
        unit_kerja__in=units
    ).select_related('employee', 'unit_kerja').order_by('-created_at')

    status_filter = request.GET.get('status', '').strip()
    if status_filter in dict(PengajuanKredensial.STATUS_CHOICES):
        queryset = queryset.filter(status=status_filter)

    page_obj = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'sdm/kredensial/daftar.html', {
        'page_obj': page_obj,
        'status_choices': PengajuanKredensial.STATUS_CHOICES,
        'selected_status': status_filter,
        'pagination_query': params.urlencode(),
    })


@login_required
def kredensial_spk_list(request):
    """List of issued clinical assignments (SPK) in scope."""
    require_hc_capability(request.user, 'can_review_hc_credentials')
    units = visible_units(request.user, capability='can_review_hc_credentials')
    assignments = PenugasanKlinis.objects.filter(
        unit_kerja__in=units
    ).select_related('employee', 'unit_kerja', 'decision').order_by('-issued_at')
    return render(request, 'sdm/kredensial/spk_daftar.html', {
        'assignments': assignments,
    })


def _syarat_rows(credential_request):
    """Populate (idempotent) then evaluate the six-domain checklist rows."""
    populate_requirements(credential_request)
    rows = evaluate_requirements(credential_request)
    return sorted(rows, key=lambda row: (row.domain, row.jenis))


def _missing_requirement_labels(credential_request):
    """Labels of non-INFO rows still KURANG; empty means nothing is missing."""
    return [
        row.get_jenis_display() for row in _syarat_rows(credential_request)
        if row.status == 'KURANG'
    ]


def _detail_context(credential_request, *, jenjang_filter=None):
    """Shared detail-page context (page render and blocked decision re-render)."""
    employee = credential_request.employee
    profesi = employee.profesi_master
    jenjang_qs = list(
        MasterJenjangProfesi.objects.filter(profesi=profesi).order_by('urutan')
    ) if profesi else []
    katalog_qs = KatalogTindakan.objects.none()
    katalog_error = ''
    if profesi is None:
        katalog_error = (
            'Profesi pegawai belum tertaut ke master profesi; '
            'katalog RKK tidak dapat dimuat.'
        )
    else:
        katalog_qs = KatalogTindakan.objects.filter(
            jenjang__profesi=profesi, is_active=True,
        ).exclude(tingkat_supervisi='T').select_related('jenjang').order_by(
            'jenjang__urutan', 'kode'
        )
        # K2 kaskade: pilih jenjang/spesialisasi dulu, katalog menyusut.
        if jenjang_filter == '':
            pass  # operator memilih "semua jenjang profesi"
        elif jenjang_filter:
            try:
                katalog_qs = katalog_qs.filter(jenjang_id=jenjang_filter)
            except (TypeError, ValueError, ValidationError):
                katalog_qs = KatalogTindakan.objects.none()
        elif employee.jenjang_master_id:
            katalog_qs = katalog_qs.filter(
                jenjang_id=employee.jenjang_master_id,
            )
        if not katalog_qs.exists():
            katalog_error = (
                f'Katalog RKK untuk profesi {profesi.nama} pada jenjang ini '
                'belum tersedia; pilih jenjang lain atau isi kewenangan manual.'
            )
    return {
        'credential_request': credential_request,
        'privileges': credential_request.privileges.select_related(
            'catalog_item', 'catalog_item__jenjang',
        ),
        'katalog': katalog_qs,
        'katalog_error': katalog_error,
        'profesi_label': profesi.nama if profesi else '—',
        'jenjang_labels': [j.nama for j in jenjang_qs],
        'jenjang_options': jenjang_qs,
        'jenjang_aktif': jenjang_filter or getattr(
            employee, 'jenjang_master_id', None,
        ),
        'psv_records': credential_request.employee.psv_records.select_related('version')[:20],
        'spk_list': credential_request.employee.clinical_assignments.select_related('decision'),
        'logbook_recap': logbook_recap(credential_request.employee),
        'requirements': _syarat_rows(credential_request),
        'requirement_domain_labels': DokumenSyaratKredensial.DOMAIN_CHOICES,
        'stepper': stepper_rows(credential_request),
        'stage_history': stage_history(credential_request),
        'current_stage': current_stage(credential_request),
        'stage_choices': TahapKredensial.TAHAP_CHOICES,
    }


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
    raw_jenjang = request.GET.get('jenjang')
    if raw_jenjang is None:
        jenjang_filter = None  # param tak dikirim: default terkunci jenjang pegawai
    elif raw_jenjang.strip() == '':
        jenjang_filter = ''  # '— semua jenjang profesi —'
    else:
        raw_jenjang = raw_jenjang.strip()
        jenjang_filter = raw_jenjang if MasterJenjangProfesi.objects.filter(
            pk=raw_jenjang,
            profesi=credential_request.employee.profesi_master,
        ).exists() else None
    return render(request, 'sdm/kredensial/detail.html', _detail_context(
        credential_request, jenjang_filter=jenjang_filter,
    ))


@login_required
@require_POST
def kredensial_decide(request, request_id):
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    notes = (request.POST.get('notes') or '')[:2000]
    missing = _missing_requirement_labels(credential_request)
    if missing and not request.POST.get('abaikan_syarat'):
        messages.warning(
            request,
            'Belum lengkap: ' + ', '.join(missing)
            + '. Centang "putuskan tanpa kelengkapan" untuk melanjutkan.',
        )
        return render(request, 'sdm/kredensial/detail.html', {
            **_detail_context(credential_request),
            'missing_requirements': missing,
        })
    if missing:
        notes = (notes + '\n' if notes else '') + 'Syarat belum lengkap: ' + ', '.join(missing)
    try:
        decide_credential(
            credential_request,
            actor=request.user,
            outcome=request.POST.get('outcome', ''),
            notes=notes[:2000],
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
    verify_url = request.build_absolute_uri(
        reverse('sdm:kredensial_detail', args=[assignment.decision.pengajuan_id])
    )
    qr_data_url = None
    try:
        import base64
        import io

        import qrcode

        buffer = io.BytesIO()
        qrcode.make(
            f'{verify_url}?nomor_spk={assignment.nomor_spk}'
        ).save(buffer, format='PNG')
        qr_data_url = 'data:image/png;base64,' + base64.b64encode(
            buffer.getvalue()
        ).decode('ascii')
    except Exception:
        qr_data_url = None  # plain-text fallback URL stays in the template
    return render(request, 'sdm/kredensial/cetak_spk.html', {
        'assignment': assignment,
        'qr_data_url': qr_data_url,
        'verify_url': verify_url,
    })


@login_required
@require_POST
def kredensial_rekomendasikan(request, request_id):
    """Committee recommendation action (DIREKOMENDASI) before director decision."""
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    try:
        rekomendasikan_kredensial(
            credential_request,
            actor=request.user,
            catatan=(request.POST.get('catatan') or '')[:2000],
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Rekomendasi komite dicatat.')
    return redirect('sdm:kredensial_detail', request_id=credential_request.pk)


@login_required
@require_POST
def kredensial_terbitkan_spk(request, request_id):
    """Executive approval: issue SPK + RKK privilege snapshots (Direktur)."""
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    nomor_spk = (request.POST.get('nomor_spk') or '').strip()[:80]
    berlaku_mulai = request.POST.get('berlaku_mulai') or ''
    berlaku_sampai = (request.POST.get('berlaku_sampai') or '').strip() or None
    if not nomor_spk or not berlaku_mulai:
        messages.error(request, 'Nomor SPK dan tanggal berlaku mulai wajib diisi.')
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
    from datetime import date
    try:
        mulai = date.fromisoformat(berlaku_mulai)
        sampai = date.fromisoformat(berlaku_sampai) if berlaku_sampai else None
        terbitkan_spk_lengkap(
            credential_request, actor=request.user, nomor_spk=nomor_spk,
            berlaku_mulai=mulai, berlaku_sampai=sampai,
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, f'SPK {nomor_spk} diterbitkan beserta RKK.')
    return redirect('sdm:kredensial_detail', request_id=credential_request.pk)


@login_required
@require_POST
def kredensial_cabut_spk(request, assignment_id):
    """Revoke an SPK and close its privilege snapshots effective today."""
    assignment = _scoped_or_404(
        PenugasanKlinis, request.user, assignment_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials', unit=assignment.unit_kerja_id
    )
    alasan = (request.POST.get('alasan') or '').strip()
    if not alasan:
        messages.error(request, 'Alasan pencabutan wajib diisi.')
        return redirect('sdm:kredensial_detail', request_id=assignment.decision.pengajuan_id)
    try:
        revoke_spk(assignment, actor=request.user, reason=alasan)
        revoke_spk_privileges(
            actor=request.user,
            employee=assignment.employee,
            unit=assignment.unit_kerja_id,
            action_codes=[
                s.action_code.code
                for s in assignment.privilege_snapshots.select_related('action_code')
            ],
            at=timezone.localdate(),
            reason=alasan,
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'SPK dicabut beserta snapshot kewenangan.')
    return redirect('sdm:kredensial_detail', request_id=assignment.decision.pengajuan_id)


@login_required
def kredensial_cetak_rkk(request, assignment_id):
    """Print the e-RKK attachment: all privilege lines incl. TIDAK_DIBERIKAN."""
    assignment = _scoped_or_404(
        PenugasanKlinis, request.user, assignment_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials', unit=assignment.unit_kerja_id
    )
    lines = list(
        assignment.decision.pengajuan.privileges.select_related('catalog_item')
    )
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='rkk_printed',
        target_tipe='clinical_assignment',
        target_id=str(assignment.pk),
        status_sesudah='PRINTED',
        alasan='rkk render requested',
    )
    return render(request, 'sdm/kredensial/cetak_rkk.html', {
        'assignment': assignment,
        'lines': lines,
    })


@login_required
def kredensial_bukti_audit(request, request_id):
    """STARKES audit evidence sheet: request form + PSV checklist + peer review."""
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    return render(request, 'sdm/kredensial/bukti_audit.html', {
        'credential_request': credential_request,
        'privileges': credential_request.privileges.select_related(
            'catalog_item', 'catalog_item__jenjang',
        ),
        'profesi_label': (
            credential_request.employee.profesi_master.nama
            if credential_request.employee.profesi_master else '—'
        ),
        'jenjang_labels': [
            j.nama for j in MasterJenjangProfesi.objects.filter(
                profesi=credential_request.employee.profesi_master,
            ).order_by('urutan')
        ] if credential_request.employee.profesi_master else [],
        'psv_records': credential_request.employee.psv_records.select_related('version'),
        'penilaian': credential_request.penilaian_tindakan.select_related('rincian'),
        'requirements': _syarat_rows(credential_request),
    })


@login_required
def kredensial_berita_acara_rapat(request, request_id):
    """C-4: committee minutes print sheet; hand-filled attendees, no DB model."""
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    tanggal_rapat = None
    raw_tanggal = (request.GET.get('tanggal') or '').strip()
    if raw_tanggal:
        try:
            tanggal_rapat = datetime.date.fromisoformat(raw_tanggal)
        except ValueError:
            tanggal_rapat = None
    decision = getattr(credential_request, 'decision', None)
    if tanggal_rapat is None:
        tanggal_rapat = (
            timezone.localdate(decision.decided_at) if decision else None
        )
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='berita_acara_rapat_printed',
        target_tipe='credential_request',
        target_id=str(credential_request.pk),
        status_sesudah='PRINTED',
        alasan='committee minutes render requested',
    )
    return render(request, 'sdm/kredensial/berita_acara_rapat.html', {
        'credential_request': credential_request,
        'decision': decision,
        'tanggal_rapat': tanggal_rapat,
        'privileges': credential_request.privileges.select_related(
            'catalog_item', 'catalog_item__jenjang',
        ),
        'penilaian': credential_request.penilaian_tindakan.select_related('rincian'),
    })


@login_required
@require_POST
def kredensial_syarat_tautkan(request, request_id, row_id):
    """C-3: link an existing employee document version to a requirement row."""
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    row = get_object_or_404(
        DokumenSyaratKredensial, pk=row_id, pengajuan=credential_request,
    )
    if row.jenis in DokumenSyaratKredensial.WORKFLOW_JENIS:
        messages.error(request, 'Baris alur kerja tidak dapat ditautkan manual.')
        return HttpResponse(status=400)
    version = VersiDokumen.objects.filter(
        pk=request.POST.get('document_version') or '',
        document__employee=credential_request.employee,
    ).first()
    if version is None:
        messages.error(request, 'Berkas tidak ditemukan untuk pegawai ini.')
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
    row.document_version = version
    row.status = 'TERPENUHI'
    row.save()
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='syarat_linked',
        target_tipe='credential_requirement',
        target_id=str(row.pk),
        status_sebelum='KURANG',
        status_sesudah='TERPENUHI',
        alasan=f'jenis={row.jenis};version={version.pk}',
    )
    messages.success(request, 'Berkas pendukung ditautkan.')
    return redirect('sdm:kredensial_detail', request_id=credential_request.pk)


@login_required
@require_POST
def kredensial_syarat_upload(request, request_id, row_id):
    """C-3: upload a new private document for a requirement row, then link it."""
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    row = get_object_or_404(
        DokumenSyaratKredensial, pk=row_id, pengajuan=credential_request,
    )
    if row.jenis in DokumenSyaratKredensial.WORKFLOW_JENIS:
        messages.error(request, 'Baris alur kerja tidak menerima unggahan.')
        return HttpResponse(status=400)
    berkas = request.FILES.get('berkas')
    if berkas is None:
        messages.error(request, 'Pilih berkas terlebih dahulu.')
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
    spec = next(
        (item for item in DEFAULT_SYARAT_ROWS if item['jenis'] == row.jenis), None
    )
    kind = (spec or {}).get('kind') or row.jenis
    health = bool((spec or {}).get('health'))
    sensitivity = 'health' if health else 'personnel'
    document_type = 'HEALTH' if health else 'CREDENTIAL'
    try:
        _document, version = store_private_document(
            berkas,
            employee=credential_request.employee,
            sensitivity=sensitivity,
            document_type=document_type,
            title=f'{row.get_jenis_display()} — kredensial',
            uploaded_by=request.user,
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
    if kind != 'OTHER':
        version.document.jenis_berkas = kind if kind in dict(
            DokumenPegawai.DOCUMENT_KIND_CHOICES
        ) else version.document.jenis_berkas
        version.document.save(update_fields=['jenis_berkas'])
    row.document_version = version
    row.status = 'TERPENUHI'
    row.save()
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='syarat_linked',
        target_tipe='credential_requirement',
        target_id=str(row.pk),
        status_sebelum='KURANG',
        status_sesudah='TERPENUHI',
        alasan=f'jenis={row.jenis};version={version.pk};upload=true',
    )
    messages.success(request, 'Berkas pendukung diunggah dan ditautkan.')
    return redirect('sdm:kredensial_detail', request_id=credential_request.pk)


@login_required
def kredensial_akses_rme(request):
    """Read-only clinical access control view (Sub-Menu E).

    Shows effective privileges vs locked catalog actions for one employee+unit.
    Enforcement in the future RME module uses require_clinical_action (see
    sdm/services/clinical_access.py); this module documents access only.
    """
    require_hc_capability(request.user, 'can_review_hc_credentials')
    units = visible_units(request.user, capability='can_review_hc_credentials').order_by(
        'level', 'order', 'code'
    )
    employee_id = request.GET.get('pegawai', '').strip()
    unit_id = request.GET.get('unit', '').strip()
    pegawai = None
    selected_unit = None
    granted, locked = [], []
    if employee_id:
        pegawai = get_object_or_404(
            Pegawai, pk=employee_id, penempatan__unit_kerja__in=units,
        )
        if unit_id:
            selected_unit = get_object_or_404(units, pk=unit_id)
        else:
            placement = pegawai.penempatan.filter(
                tanggal_mulai__lte=timezone.localdate(),
            ).filter(
                Q(tanggal_selesai__isnull=True)
                | Q(tanggal_selesai__gte=timezone.localdate())
            ).select_related('unit_kerja').order_by('unit_kerja__level').first()
            selected_unit = placement.unit_kerja if placement else None
        if selected_unit is not None:
            today = timezone.localdate()
            snapshots = PrivilegeSnapshot.objects.filter(
                pegawai=pegawai, unit_kerja=selected_unit, valid_from__lte=today,
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=today)
            ).select_related('action_code')
            granted = sorted(snapshots, key=lambda s: s.action_code.code)
            snapshot_codes = {s.action_code.code for s in granted}
            locked = list(
                KatalogTindakan.objects.filter(
                    is_active=True,
                    jenjang__profesi_id=pegawai.profesi_master_id,
                ).select_related('jenjang').exclude(
                    tingkat_supervisi='T',
                ).exclude(
                    kode__in=snapshot_codes,
                ).order_by('kode')
            )
    employees = visible_employees(request.user).order_by('nama_lengkap')
    return render(request, 'sdm/kredensial/akses_rme.html', {
        'units': units,
        'employees': employees[:200],
        'pegawai': pegawai,
        'selected_unit': selected_unit,
        'granted': granted,
        'locked': locked,
        'selected_employee': employee_id,
        'selected_unit_id': unit_id,
    })


@login_required
def kredensial_peta(request):
    """Hospital clinical mapping: who holds which privileges where (Sub-Menu F)."""
    require_hc_capability(request.user, 'can_review_hc_credentials')
    units = visible_units(request.user, capability='can_review_hc_credentials')
    search_q = request.GET.get('q', '').strip()[:100]
    unit_filter = request.GET.get('unit', '').strip()

    today = timezone.localdate()
    snapshots = PrivilegeSnapshot.objects.select_related(
        'pegawai', 'unit_kerja', 'action_code',
    ).filter(
        unit_kerja__in=units,
        valid_from__lte=today,
    ).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=today)
    ).order_by('pegawai__nama_lengkap', 'action_code__code')

    if search_q:
        snapshots = snapshots.filter(pegawai__nama_lengkap__icontains=search_q)
    selected_unit_id = None
    if unit_filter:
        try:
            unit_id = int(unit_filter)
        except (TypeError, ValueError):
            snapshots = snapshots.none()
        else:
            snapshots = snapshots.filter(unit_kerja_id=unit_id)
            selected_unit_id = unit_id

    # M/S status per action code from the RKK catalog; actions outside the
    # catalog (EXT-*) count as independent grants.
    katalog_status = dict(
        KatalogTindakan.objects.values_list('kode', 'tingkat_supervisi')
    )
    rows = {}
    matriks_map = {}
    for snapshot in snapshots:
        kode = snapshot.action_code.code
        tingkat = katalog_status.get(kode, 'M')
        row = rows.setdefault(snapshot.pegawai_id, {
            'pegawai': snapshot.pegawai, 'units': set(),
            'total': 0, 'mandiri': 0, 'supervisi': 0,
        })
        row['total'] += 1
        row['units'].add(snapshot.unit_kerja.code)
        if tingkat == 'S':
            row['supervisi'] += 1
        else:
            row['mandiri'] += 1
        if selected_unit_id:
            matriks_map.setdefault(kode, {})[snapshot.pegawai_id] = tingkat

    rows = sorted(rows.values(), key=lambda r: r['pegawai'].nama_lengkap)
    matriks_actions = sorted(matriks_map.keys())
    matriks = [
        {
            'pegawai': row['pegawai'],
            'cells': [
                {'action': action, 'tingkat': matriks_map[action].get(row['pegawai'].pk, '')}
                for action in matriks_actions
            ],
        }
        for row in rows
    ]
    params = request.GET.copy()
    params.pop('page', None)
    page_obj = Paginator(rows, PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'sdm/kredensial/peta.html', {
        'page_obj': page_obj,
        'units': units.order_by('level', 'order', 'code'),
        'search_q': search_q,
        'selected_unit': unit_filter,
        'selected_unit_id': selected_unit_id,
        'matriks_actions': matriks_actions,
        'matriks': matriks,
        'pagination_query': params.urlencode(),
    })


@login_required
def kredensial_katalog(request):
    """Sub-Menu A: master catalog RKK grouped by committee then career grade.

    Global model (no unit_kerja scope), so capability-only guard.
    Editing via Django admin.
    """
    require_hc_capability(request.user, 'can_review_hc_credentials')
    katalog = KatalogTindakan.objects.filter(
        is_active=True,
    ).select_related('jenjang__profesi').order_by(
        'jenjang__profesi__keluarga', 'jenjang__profesi__nama', 'jenjang__urutan', 'kode'
    )

    profesi_filter = request.GET.get('profesi', '').strip()
    jenjang_filter = request.GET.get('jenjang', '').strip()
    search_q = request.GET.get('q', '').strip()[:100]
    if profesi_filter:
        try:
            katalog = katalog.filter(jenjang__profesi_id=int(profesi_filter))
        except (TypeError, ValueError):
            katalog = katalog.none()
    if jenjang_filter:
        try:
            katalog = katalog.filter(jenjang_id=jenjang_filter)
        except (TypeError, ValueError, ValidationError):
            katalog = katalog.none()
    if search_q:
        katalog = katalog.filter(nama__icontains=search_q)

    page_obj = Paginator(katalog, PAGE_SIZE).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    profesi_list = MasterProfesiPegawai.objects.filter(is_active=True).order_by(
        'keluarga', 'nama'
    )
    jenjang_list = MasterJenjangProfesi.objects.select_related('profesi').order_by(
        'profesi__nama', 'urutan'
    )

    # Group current page by komite (= keluarga profesi) then jenjang.
    komite_order = [
        ('MEDIS', 'Komite Medis'),
        ('KEPERAWATAN_KEBIDANAN', 'Komite Keperawatan & Kebidanan'),
        ('NAKES_LAIN', 'Komite Tenaga Kesehatan Lainnya'),
        ('NON_KLINIS', 'Non Klinis'),
    ]
    groups = []
    for keluarga, label in komite_order:
        jenjang_map = {}
        for item in page_obj.object_list:
            if item.jenjang.profesi.keluarga != keluarga:
                continue
            jenjang_map.setdefault(item.jenjang, []).append(item)
        if jenjang_map:
            groups.append({'label': label, 'jenjang': [
                {'jenjang': jenjang_obj, 'items': items}
                for jenjang_obj, items in jenjang_map.items()
            ]})

    return render(request, 'sdm/kredensial/katalog.html', {
        'page_obj': page_obj,
        'profesi_list': profesi_list,
        'jenjang_list': jenjang_list,
        'groups': groups,
        'search_q': search_q,
        'selected_profesi': profesi_filter,
        'selected_jenjang': jenjang_filter,
        'pagination_query': params.urlencode(),
    })


@login_required
def orientasi_list(request):
    require_hc_capability(request.user, 'can_manage_hc_orientation')
    units = visible_units(request.user, capability='can_manage_hc_orientation')
    assignments = PenugasanOrientasi.objects.filter(
        unit_kerja__in=units
    ).select_related('employee', 'program', 'unit_kerja').prefetch_related('completions')
    # O5.1: filter unit & status (dashboard KPS 4 & 8).
    unit_filter = (request.GET.get('unit') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()
    if unit_filter.isdigit():
        assignments = assignments.filter(unit_kerja_id=int(unit_filter))
    if status_filter == 'WARNING':
        assignments = assignments.filter(status='BERJALAN', tenggat__lt=timezone.localdate())
    elif status_filter:
        assignments = assignments.filter(status=status_filter)
    return render(request, 'sdm/orientasi/daftar.html', {
        'assignments': assignments,
        'unit_options': units,
        'unit_filter': unit_filter,
        'status_filter': status_filter,
    })


@login_required
def orientasi_detail(request, assignment_id):
    assignment = _scoped_or_404(
        PenugasanOrientasi, request.user, assignment_id,
        capability='can_manage_hc_orientation',
    )
    require_hc_capability(
        request.user, 'can_manage_hc_orientation', unit=assignment.unit_kerja_id
    )
    # O5.4: ringkasan logbook milik pegawai selama masa orientasi.
    from sdm.models import EntriLogbookKlinis
    entri = EntriLogbookKlinis.objects.filter(
        employee_id=assignment.employee_id,
        tanggal__gte=assignment.tanggal_mulai,
        tanggal__lte=assignment.tenggat,
    )
    ringkasan_logbook = {
        'total': entri.count(),
        'mandiri': sum(entri.values_list('jumlah_mandiri', flat=True) or [0]),
        'supervisi': sum(entri.values_list('jumlah_supervisi', flat=True) or [0]),
        'kolaborasi': sum(entri.values_list('jumlah_kolaborasi', flat=True) or [0]),
        'terverifikasi': entri.filter(sudah_diverifikasi=True).count(),
    }
    return render(request, 'sdm/orientasi/detail.html', {
        'assignment': assignment,
        'completions': assignment.completions.select_related('activity'),
        'progress': assignment.progress_pct,
        'ringkasan_logbook': ringkasan_logbook,
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
def kinerja_periode_baru(request):
    """Buat periode penilaian (DRAFT); FINAL diatur admin."""
    require_hc_capability(request.user, 'can_manage_hc_appraisals')
    error = None
    if request.method == 'POST':
        nama = (request.POST.get('nama') or '').strip()
        mulai = request.POST.get('tanggal_mulai') or None
        selesai = request.POST.get('tanggal_selesai') or None
        if not nama or not mulai or not selesai:
            error = 'Nama dan rentang tanggal wajib diisi.'
        else:
            periode = PeriodeKinerja.objects.create(
                nama=nama, tanggal_mulai=mulai, tanggal_selesai=selesai,
            )
            messages.success(request, f'Periode "{periode.nama}" dibuat.')
            return redirect('sdm:kinerja_list')
    return render(request, 'sdm/kinerja/form_periode.html', {'error': error})


@login_required
def kinerja_buat(request):
    """Buat (atau pakai existing) penilaian untuk pegawai + periode."""
    require_hc_capability(request.user, 'can_manage_hc_appraisals')
    employee_options = visible_employees(request.user).order_by('nama_lengkap')
    periode_options = PeriodeKinerja.objects.order_by('-tanggal_mulai')
    if request.method == 'POST':
        employee = employee_options.filter(
            pk=request.POST.get('employee')
        ).first()
        periode = periode_options.filter(pk=request.POST.get('periode')).first()
        if employee is None or periode is None:
            messages.error(request, 'Pegawai dan periode wajib dipilih.')
        else:
            appraisal, created = PenilaianKinerja.objects.get_or_create(
                periode=periode, employee=employee,
            )
            if created:
                from sdm.services.workflow_kinerja import resolve_reviewer
                reviewer_pk = resolve_reviewer(employee)
                if reviewer_pk:
                    appraisal.reviewer_id = reviewer_pk
                    appraisal.save(update_fields=['reviewer'])
                messages.success(request, 'Penilaian dibuat.')
            else:
                messages.info(request, 'Penilaian sudah ada.')
            return redirect('sdm:kinerja_detail', appraisal_id=appraisal.pk)
    return render(request, 'sdm/kinerja/form_buat.html', {
        'employee_options': employee_options,
        'periode_options': periode_options,
    })


def _appraisal_or_404(request, appraisal_id):
    return get_object_or_404(
        PenilaianKinerja.objects.filter(
            employee__penempatan__unit_kerja__in=visible_units(
                request.user, capability='can_manage_hc_appraisals'
            )
        ).distinct(),
        pk=appraisal_id,
    )


@login_required
def kinerja_detail(request, appraisal_id):
    require_hc_capability(request.user, 'can_manage_hc_appraisals')
    appraisal = _appraisal_or_404(request, appraisal_id)
    from sdm.services.workflow_kinerja import (
        current_stage, stepper_rows,
    )

    eval_saya = request.user.pk == appraisal.employee.akun_id
    if request.method == 'POST':
        aksi = request.POST.get('aksi')
        if aksi == 'self_assessment':
            if appraisal.employee.akun_id != request.user.pk:
                raise PermissionDenied('Hanya pegawai yang dinilai dapat mengisi evaluasi mandiri.')
            appraisal.self_assessment = (request.POST.get('self_assessment') or '')[:5000]
            appraisal.self_assessed_at = timezone.now()
            appraisal.save(update_fields=['self_assessment', 'self_assessed_at'])
            from sdm.services.workflow_kinerja import advance_stage
            try:
                advance_stage(
                    appraisal, actor=request.user, tahap='SELF_ASSESSMENT',
                    catatan='Evaluasi mandiri diisi',
                )
            except ValidationError as exc:
                pass  # tahap sudah pernah dicatat — isi tetap tersimpan
            messages.success(request, 'Evaluasi mandiri tersimpan.')
        elif aksi == 'kalibrasi':
            require_hc_capability(request.user, 'hc_calibrate_appraisals',
                                  employee=appraisal.employee)
            appraisal.kalibrasi_catatan = (request.POST.get('kalibrasi_catatan') or '')[:5000]
            appraisal.calibrated_at = timezone.now()
            appraisal.save(update_fields=['kalibrasi_catatan', 'calibrated_at'])
            from sdm.services.workflow_kinerja import advance_stage
            advance_stage(
                appraisal, actor=request.user, tahap='KALIBRASI_MUTU',
                catatan=appraisal.kalibrasi_catatan[:200],
            )
            messages.success(request, 'Kalibrasi dicatat.')
        elif aksi == 'feedback':
            appraisal.feedback_notes = (request.POST.get('feedback_notes') or '')[:5000]
            appraisal.feedback_at = timezone.now()
            appraisal.save(update_fields=['feedback_notes', 'feedback_at'])
            from sdm.services.workflow_kinerja import advance_stage
            advance_stage(
                appraisal, actor=request.user, tahap='FEEDBACK',
                catatan=appraisal.feedback_notes[:200],
            )
            messages.success(request, 'Feedback dicatat.')
        elif aksi == 'skor':
            from sdm.services.workflow_kinerja import simpan_skor, advance_stage
            skor_map = {
                key[len('skor_'):]: value
                for key, value in request.POST.items()
                if key.startswith('skor_')
            }
            try:
                simpan_skor(appraisal, skor_map, actor=request.user)
                advance_stage(
                    appraisal, actor=request.user, tahap='REVIEW_ATASAN',
                    catatan='Skor atas direview',
                )
            except (PermissionDenied, ValidationError) as exc:
                msgs = getattr(exc, 'messages', None)
                messages.error(request, '; '.join(msgs) if msgs else str(exc))
            else:
                messages.success(request, 'Skor tersimpan.')
        return redirect('sdm:kinerja_detail', appraisal_id=appraisal.pk)

    items = appraisal.items.select_related('indikator').order_by('kategori', 'pk')
    tahapan_rows = stepper_rows(appraisal)
    riwayat = appraisal.tahapan.select_related('aktor').order_by('-created_at', '-pk')
    return render(request, 'sdm/kinerja/detail.html', {
        'appraisal': appraisal,
        'items': items,
        'tahapan_rows': tahapan_rows,
        'tahap_kini': current_stage(appraisal),
        'riwayat': riwayat,
        'eval_saya': eval_saya,
        'boleh_sinkron': appraisal.status != 'FINAL',
    })


@login_required
@require_POST
def kinerja_sinkron(request, appraisal_id):
    from sdm.services.sinkron_kinerja import sinkronkan_data

    require_hc_capability(request.user, 'can_manage_hc_appraisals')
    appraisal = _appraisal_or_404(request, appraisal_id)
    try:
        dibuat, diperbarui = sinkronkan_data(appraisal, actor=request.user)
    except (PermissionDenied, ValidationError, ValueError) as exc:
        msgs = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(msgs) if msgs else str(exc))
    else:
        messages.success(
            request, f'Sinkronisasi selesai: {dibuat} butir baru, {diperbarui} diperbarui.'
        )
    return redirect('sdm:kinerja_detail', appraisal_id=appraisal.pk)


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
def k3_imunisasi_tambah(request):
    require_hc_capability(request.user, 'hc_health_write')
    form = ImunisasiPegawaiForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        immunization = form.save(commit=False)
        try:
            record_immunization(
                immunization.employee, actor=request.user,
                jenis=immunization.jenis, dosis_ke=immunization.dosis_ke,
                tanggal=immunization.tanggal,
                berlaku_sampai=immunization.berlaku_sampai,
                pemberi=immunization.pemberi,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
        else:
            messages.success(request, 'Imunisasi dicatat.')
            return redirect('sdm:k3_list')
    return render(request, 'sdm/k3/form.html', {'form': form, 'title': 'Tambah Imunisasi'})


@login_required
def k3_mcu_tambah(request):
    require_hc_capability(request.user, 'hc_health_write')
    form = PemeriksaanKesehatanKerjaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        exam = form.save(commit=False)
        try:
            record_health_exam(
                exam.employee, actor=request.user, tanggal=exam.tanggal,
                status_kebugaran=exam.status_kebugaran,
                ringkasan_klinis=exam.ringkasan_klinis,
                berlaku_sampai=exam.berlaku_sampai, pemeriksa=exam.pemeriksa,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
        else:
            messages.success(request, 'Pemeriksaan kesehatan kerja dicatat.')
            return redirect('sdm:k3_list')
    return render(request, 'sdm/k3/form.html', {'form': form, 'title': 'Tambah MCU'})


@login_required
def k3_insiden_tambah(request):
    require_hc_capability(request.user, 'hc_health_write')
    units = visible_units(request.user, capability='hc_health_write')
    form = InsidenK3PegawaiForm(request.POST or None)
    form.fields['employee'].queryset = visible_employees(request.user)
    form.fields['unit_kerja'].queryset = units
    if request.method == 'POST' and form.is_valid():
        incident = form.save(commit=False)
        try:
            report_incident(
                incident.employee, actor=request.user, unit_kerja=incident.unit_kerja,
                kategori=incident.kategori, deskripsi=incident.deskripsi,
                tanggal=incident.tanggal,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
        else:
            messages.success(request, 'Insiden K3 dicatat.')
            return redirect('sdm:k3_list')
    return render(request, 'sdm/k3/form.html', {'form': form, 'title': 'Lapor Insiden K3'})


@login_required
def k3_tindak_lanjut_tambah(request, incident_id):
    require_hc_capability(request.user, 'hc_health_write')
    incident = get_object_or_404(
        InsidenK3Pegawai.objects.filter(
            unit_kerja__in=visible_units(request.user, capability='hc_health_write')
        ), pk=incident_id
    )
    form = TindakLanjutK3Form(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        followup = form.save(commit=False)
        try:
            add_followup(
                incident, actor=request.user, tindakan=followup.tindakan,
                penanggung_jawab=followup.penanggung_jawab, tenggat=followup.tenggat,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
        else:
            messages.success(request, 'Tindak lanjut dicatat.')
            return redirect('sdm:k3_list')
    return render(request, 'sdm/k3/form.html', {'form': form, 'title': 'Tindak Lanjut Insiden'})


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


@login_required
def kps_report(request):
    """Sanitized KPS staff sample pack from reviewed active-edition mappings."""
    require_hc_capability(request.user, 'can_export_hc')
    units = visible_units(request.user, capability='can_export_hc')
    unit = units.filter(pk=request.GET.get('unit')).first() if request.GET.get('unit', '').isdigit() else units.first()
    if unit is None:
        raise PermissionDenied('Tidak ada unit dalam lingkup ekspor.')
    framework_id = request.GET.get('framework')
    if not framework_id:
        messages.error(request, 'Kerangka wajib dipilih.')
        return redirect('sdm:analitik_dashboard')
    try:
        employee_ids = [int(x) for x in request.GET.getlist('employee') if x.isdigit()]
    except ValueError:
        employee_ids = []
    artifact = build_kps_pack(
        actor=request.user, employee_ids=employee_ids,
        framework_id=int(framework_id),
    )
    messages.success(request, f'Paket KPS {artifact["employee_count"]} pegawai siap ditinjau.')
    request.session['kps_pack_artifact'] = {
        'generated_at': artifact['generated_at'],
        'framework_id': artifact['framework_id'],
        'framework_name': artifact['framework_name'],
        'as_of': artifact['as_of'],
        'actor_id': artifact['actor_id'],
        'employee_count': artifact['employee_count'],
        'workbook_hash': artifact['workbook_hash'],
    }
    return redirect('sdm:kps_pack_preview')


@login_required
def kps_pack_preview(request):
    artifact = request.session.get('kps_pack_artifact')
    if not artifact:
        messages.error(request, 'Tidak ada paket KPS yang tersedia.')
        return redirect('sdm:analitik_dashboard')
    return render(request, 'sdm/kps/pack_preview.html', {'artifact': artifact})


@login_required
def kps_pack_publish(request):
    if request.method != 'POST':
        raise PermissionDenied('Publikasi hanya melalui POST.')
    artifact = request.session.get('kps_pack_artifact')
    if not artifact:
        raise PermissionDenied('Paket tidak tersedia.')
    requirement_id = (request.POST.get('requirement') or '').strip()
    try:
        publish_kps_artifact(
            actor=request.user,
            artifact={**artifact, 'workbook_bytes': b''},
            requirement_id=requirement_id,
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
        return redirect('sdm:kps_pack_preview')
    messages.success(request, 'Paket KPS diterbitkan sebagai bukti untuk ditinjau.')
    del request.session['kps_pack_artifact']
    return redirect('sdm:analitik_dashboard')

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
    profile = None
    selected_employee = form['employee'].value()
    if selected_employee:
        from sdm.models import Pegawai
        employee = Pegawai.objects.filter(pk=selected_employee).first()
        if employee is not None:
            profile = credential_profile(employee)
    return render(request, 'sdm/kredensial/form.html', {
        'form': form, 'title': 'Pengajuan Kredensial Baru',
        'profile': profile,
    })


@login_required
def kredensial_pengajuan_sendiri(request):
    """Self-service portal: the logged-in employee files their own RKK request.

    Own-employee staff do not need an HC grant here; the page only ever sees
    their own rows, so an empty grant is not an access barrier (C-5).
    """
    pegawai = getattr(request.user, 'pegawai_hc', None)
    if pegawai is None:
        messages.warning(
            request,
            'Akun Anda belum terhubung dengan data pegawai, sehingga pengajuan '
            'kredensial mandiri dan logbook belum dapat dibuka. Hubungi bagian '
            'SDM untuk menautkan akun Anda ke data pegawai.',
        )
        return redirect('akreditasi:dashboard')

    form = PengajuanPortalForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        credential_request = form.save(commit=False)
        credential_request.employee = pegawai
        credential_request.submitted_by = request.user
        unit = form.cleaned_data.get('unit_kerja')
        if unit is None:
            latest = pegawai.penempatan.select_related('unit_kerja').order_by(
                '-tanggal_mulai', '-pk'
            ).first()
            unit = latest.unit_kerja if latest else None
        if unit is None:
            messages.error(
                request,
                'Data penempatan unit kerja belum ada; hubungi SDM.',
            )
            return redirect('sdm:kredensial_pengajuan_sendiri')
        credential_request.unit_kerja = unit
        credential_request.save()
        messages.success(request, 'Pengajuan kredensial mandiri terkirim.')
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)

    my_requests = list(
        PengajuanKredensial.objects.filter(employee=pegawai)
        .select_related('unit_kerja').order_by('-created_at')
    )
    for item in my_requests:
        row = current_stage_row(item)
        item.stage_label = row.get_tahap_display() if row else ''
        item.stage_kekurangan = row.kekurangan if row else ''
        item.editable = item.status in EDITABLE_STATUS
    today = timezone.localdate()
    spk_ews = PenugasanKlinis.objects.filter(
        employee=pegawai, is_active=True, berlaku_sampai__isnull=False,
        berlaku_sampai__lt=today + timedelta(days=90),
    ).order_by('berlaku_sampai')
    logbook_entries = EntriLogbookKlinis.objects.filter(
        employee=pegawai
    ).select_related('unit_kerja', 'katalog_tindakan').order_by(
        '-tanggal', '-created_at'
    )[:25]
    from sdm.services.syarat_kredensial import DEFAULT_ROWS
    owned_kinds = set(
        DokumenPegawai.objects.filter(employee=pegawai).values_list(
            'jenis_berkas', flat=True
        )
    )
    draft_by_jenis = {
        draft.jenis: draft
        for draft in DrafDokumenKredensial.objects.filter(pegawai=pegawai)
    }
    supporting_documents = []
    for row in DEFAULT_ROWS:
        if not row['kind']:
            continue
        draft = draft_by_jenis.get(row['jenis'])
        supporting_documents.append({
            'jenis': row['jenis'],
            'label': dict(DokumenSyaratKredensial.JENIS_CHOICES).get(row['jenis']),
            'ada': row['kind'] in owned_kinds,
            'can_generate': row['jenis'] in DOKUMEN_KREDENSIAL_REGISTRY,
            'has_draft': draft is not None,
            'has_final': draft is not None and draft.versi_dokumen_id is not None,
        })
    return render(request, 'sdm/kredensial/pengajuan_saya.html', {
        'form': form,
        'profile': credential_profile(pegawai),
        'checklist': (
            evaluate_employee_requirements(pegawai)
            if (request.GET.get('jenis') or '').strip() else None
        ),
        'selected_jenis': (request.GET.get('jenis') or '').strip(),
        'my_requests': my_requests,
        'spk_ews': spk_ews,
        'today': today,
        'ews_threshold': today + timedelta(days=90),
        'logbook_entries': logbook_entries,
        'logbook_recap': logbook_recap(pegawai),
        'supporting_documents': supporting_documents,
    })


def _dokumen_kredensial_pegawai(request):
    """Caller's own employee row, or a guidance redirect. Takes no employee id."""
    pegawai = getattr(request.user, 'pegawai_hc', None)
    if pegawai is None:
        messages.warning(
            request,
            'Akun Anda belum terhubung dengan data pegawai, sehingga pengajuan '
            'kredensial mandiri dan logbook belum dapat dibuka. Hubungi bagian '
            'SDM untuk menautkan akun Anda ke data pegawai.',
        )
        return None, redirect('akreditasi:dashboard')
    return pegawai, None


def _dokumen_kredensial_title(jenis):
    return DOKUMEN_KREDENSIAL_REGISTRY[jenis]['title']


@login_required
@require_POST
def dokumen_kredensial_generate(request, jenis):
    """Create or refresh the caller's draft for one generatable document."""
    pegawai, response = _dokumen_kredensial_pegawai(request)
    if response is not None:
        return response
    if jenis not in DOKUMEN_KREDENSIAL_REGISTRY:
        raise Http404('Jenis dokumen tidak dapat digenerate.')
    generate_dokumen_kredensial(pegawai, jenis, user=request.user)
    messages.success(request, f'Draf {_dokumen_kredensial_title(jenis)} siap diisi.')
    return redirect('sdm:kredensial_pengajuan_sendiri')


@login_required
def dokumen_kredensial_edit(request, jenis):
    """Fill only the manual fields of the caller's own draft."""
    pegawai, response = _dokumen_kredensial_pegawai(request)
    if response is not None:
        return response
    if jenis not in DOKUMEN_KREDENSIAL_REGISTRY:
        raise Http404('Jenis dokumen tidak dapat digenerate.')
    draf = get_object_or_404(DrafDokumenKredensial, pegawai=pegawai, jenis=jenis)

    if request.method == 'POST':
        isian = dict(draf.isian or {})
        for key, _hint in DOKUMEN_KREDENSIAL_REGISTRY[jenis]['manual_fields']:
            nilai = (request.POST.get(key) or '').strip()
            if nilai:
                isian[key] = nilai
            else:
                isian.pop(key, None)
        draf.isian = isian
        draf.save(update_fields=['isian', 'updated_at'])
        messages.success(request, 'Isian dokumen disimpan. Tinjau lalu finalkan.')
        return redirect('sdm:dokumen_kredensial_edit', jenis=jenis)

    existing = draf.isian or {}
    manual_fields = [
        {
            'key': key,
            'label': hint,
            'value': existing.get(key) if isinstance(existing.get(key), str) else '',
        }
        for key, hint in DOKUMEN_KREDENSIAL_REGISTRY[jenis]['manual_fields']
    ]
    return render(request, 'sdm/kredensial/dokumen_edit.html', {
        'draf': draf,
        'jenis': jenis,
        'title': _dokumen_kredensial_title(jenis),
        'manual_fields': manual_fields,
        'has_final': draf.versi_dokumen_id is not None,
    })


@login_required
@require_POST
def dokumen_kredensial_finalize(request, jenis):
    """Render the draft and store it as the document's next PDF version."""
    pegawai, response = _dokumen_kredensial_pegawai(request)
    if response is not None:
        return response
    if jenis not in DOKUMEN_KREDENSIAL_REGISTRY:
        raise Http404('Jenis dokumen tidak dapat digenerate.')
    draf = get_object_or_404(DrafDokumenKredensial, pegawai=pegawai, jenis=jenis)
    finalize_dokumen_kredensial(draf, user=request.user)
    messages.success(request, 'Dokumen difinalkan dan siap diunduh.')
    return redirect('sdm:dokumen_kredensial_download', jenis=jenis)


@login_required
def dokumen_kredensial_download(request, jenis):
    """Serve the caller's own finalized PDF from private storage."""
    pegawai, response = _dokumen_kredensial_pegawai(request)
    if response is not None:
        return response
    if jenis not in DOKUMEN_KREDENSIAL_REGISTRY:
        raise Http404('Jenis dokumen tidak dapat digenerate.')
    draf = get_object_or_404(DrafDokumenKredensial, pegawai=pegawai, jenis=jenis)
    version = draf.versi_dokumen
    if version is None:
        messages.error(
            request,
            'Dokumen belum difinalkan sehingga belum ada PDF untuk diunduh.',
        )
        return redirect('sdm:dokumen_kredensial_edit', jenis=jenis)

    storage = get_private_storage()
    try:
        data = storage.fetch_object(version.storage_key)
    except PrivateStorageError:
        raise Http404('Berkas PDF tidak dapat dibaca.') from None
    if (
        len(data) != version.size_bytes
        or hashlib.sha256(data).hexdigest() != version.sha256
        or not data.startswith(b'%PDF')
    ):
        raise Http404('Berkas PDF tidak dapat dibaca.')

    filename = (
        f'{pegawai.nama_lengkap} - {_dokumen_kredensial_title(jenis)} '
        f'v{version.version_number}.pdf'
    )
    for bad in ('"', '\\', '\r', '\n'):
        filename = filename.replace(bad, ' ')
    response = HttpResponse(data, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def kredensial_panel_bestari(request, request_id):
    """Peer review (mitra bestari) panel: verdict per privilege line."""
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    privileges = credential_request.privileges.all().order_by('pk')
    FormSet = PenilaianTindakanFormSet

    if request.method == 'POST':
        formset = FormSet(request.POST, instance=credential_request)
        if formset.is_valid():
            has_rows = False
            with transaction.atomic():
                for form in formset:
                    if not form.has_changed():
                        continue
                    PenilaianTindakan.objects.update_or_create(
                        pengajuan=credential_request,
                        rincian=form.cleaned_data['rincian'],
                        defaults={
                            'rekomendasi': form.cleaned_data['rekomendasi'],
                            'catatan_khusus': form.cleaned_data['catatan_khusus'],
                            'reviewed_by': request.user,
                        },
                    )
                    has_rows = True
                if has_rows and credential_request.status == 'DIAJUKAN':
                    credential_request.status = 'DITINJAU'
                    credential_request.save(update_fields=['status', 'updated_at'])
                    PeristiwaSDM.objects.create(
                        actor=request.user,
                        jenis_peristiwa='peer_review_submitted',
                        target_tipe='credential_request',
                        target_id=str(credential_request.pk),
                        status_sesudah='DITINJAU',
                        alasan='panel evaluasi mitra bestari menyimpan penilaian',
                    )
            messages.success(request, 'Penilaian mitra bestari disimpan.')
            return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
        messages.error(request, 'Penilaian tidak valid; periksa kembali.')
    else:
        initial = [
            {'rincian': rincian}
            for rincian in privileges_without_penilaian(credential_request)
        ]
        formset = FormSet(instance=credential_request, initial=initial)
    return render(request, 'sdm/kredensial/bestari.html', {
        'credential_request': credential_request,
        'privileges': privileges,
        'formset': formset,
    })


@login_required
def kredensial_add_privilege(request, request_id):
    """Add one RKK line: catalog auto-loads for the employee's profession."""
    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    require_hc_capability(
        request.user, 'can_review_hc_credentials',
        unit=credential_request.unit_kerja_id,
    )
    if request.method != 'POST':
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)

    form = RincianKewenanganForm(request.POST, pengajuan=credential_request)
    if not form.is_valid():
        messages.error(request, 'Rincian kewenangan tidak valid.')
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)

    privilege = form.save(commit=False)
    privilege.pengajuan = credential_request
    if privilege.catalog_item_id:
        jenjang_id = getattr(
            credential_request.employee, 'jenjang_master_id', None
        )
        if (
            jenjang_id
            and privilege.catalog_item.jenjang_id != jenjang_id
        ):
            messages.error(
                request,
                'Tindakan katalog bukan milik jenjang karir pegawai.',
            )
            return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
        if not privilege.kewenangan:
            privilege.kewenangan = privilege.catalog_item.nama
        # Requested level follows the catalog's default supervision level.
        privilege.usulan = RincianKewenangan.USULAN_DARI_TINGKAT[
            privilege.catalog_item.tingkat_supervisi
        ]
    elif not privilege.kewenangan:
        messages.error(
            request, 'Pilih tindakan dari katalog atau isi nama kewenangan manual.'
        )
        return redirect('sdm:kredensial_detail', request_id=credential_request.pk)
    privilege.save()
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


# ── C-2: structured clinical logbook ─────────────────────────────────────

def _portal_pegawai_or_none(user):
    """Own-employee resolver for self-service surfaces (plan K-A8 overlap)."""
    return getattr(user, 'pegawai_hc', None)


def _resolve_post_pegawai(request):
    """Pegawai from POST 'employee' (or 'pegawai' filter name); malformed UUID counts as absent."""
    raw = (request.POST.get('employee') or request.POST.get('pegawai') or '').strip()
    try:
        return Pegawai.objects.filter(pk=raw).first()
    except (ValueError, TypeError, ValidationError):
        return None


def _logbook_context(user, *, pegawai_filter=None):
    """Shared logbook list context: scope rows to own employee or HC units."""
    base = EntriLogbookKlinis.objects.select_related(
        'employee', 'unit_kerja', 'katalog_tindakan'
    )
    pegawai = _portal_pegawai_or_none(user)
    has_grant = HcGrant.objects.filter(
        user=user, capability='can_review_hc_credentials'
    ).exists() and visible_units(
        user, capability='can_review_hc_credentials'
    ).exists()
    if not has_grant:
        return pegawai, (
            base.filter(employee=pegawai) if pegawai else base.none()
        )
    units = visible_units(user, capability='can_review_hc_credentials')
    queryset = base.filter(employee__penempatan__unit_kerja__in=units).distinct()
    selected = None
    if pegawai_filter:
        selected = visible_employees(
            user, capability='can_review_hc_credentials'
        ).filter(pk=pegawai_filter).first()
        if selected:
            queryset = queryset.filter(employee=selected)
    return selected, queryset


@login_required
def logbook_list(request):
    employee, queryset = _logbook_context(
        request.user, pegawai_filter=request.GET.get('pegawai') or None,
    )
    page_obj = Paginator(queryset.order_by('-tanggal', '-created_at'), PAGE_SIZE).get_page(
        request.GET.get('page')
    )
    employees = None
    if HcGrant.objects.filter(
        user=request.user, capability='can_review_hc_credentials'
    ).exists():
        employees = visible_employees(
            request.user, capability='can_review_hc_credentials'
        ).order_by('nama_lengkap')
    target = employee or _portal_pegawai_or_none(request.user)
    can_manage = target is not None and _logbook_target_allowed(request.user, target)
    quick_form = None
    if can_manage:
        # Newest action of that employee preselects the quick-entry row.
        latest = EntriLogbookKlinis.objects.filter(
            employee=target, katalog_tindakan__isnull=False,
        ).order_by('-tanggal', '-created_at').values(
            'katalog_tindakan_id', 'unit_kerja_id'
        ).first() or {}
        quick_form = EntriLogbookForm(
            employee=target,
            user=request.user,
            initial={
                'tanggal': timezone.localdate(),
                'katalog_tindakan': latest.get('katalog_tindakan_id'),
                'unit_kerja': latest.get('unit_kerja_id'),
                'modus': 'katalog',
            },
        )
    return render(request, 'sdm/logbook/daftar.html', {
        'page_obj': page_obj,
        'selected_employee': employee,
        'employees': employees,
        'can_manage': can_manage,
        'quick_form': quick_form,
        'quick_target': target,
    })


@login_required
@require_POST
def logbook_cepat(request):
    """One-row quick entry; reuses EntriLogbookForm so validation never forks."""
    pegawai = _portal_pegawai_or_none(request.user)
    posted_employee = _resolve_post_pegawai(request)
    if pegawai is not None and (
        posted_employee is None or posted_employee.pk == pegawai.pk
    ):
        target = pegawai
    else:
        target = posted_employee
    if target is None:
        messages.error(request, 'Akun belum terhubung data pegawai.')
        return redirect('sdm:logbook_list')
    if not _logbook_target_allowed(request.user, target):
        raise PermissionDenied('Pegawai di luar lingkup.')
    form = EntriLogbookForm(request.POST, employee=target, user=request.user)
    if form.is_valid():
        entry = form.save(commit=False)
        entry.employee = target
        entry.created_by = request.user
        entry.save()
        PeristiwaSDM.objects.create(
            actor=request.user,
            jenis_peristiwa='logbook_entry_created',
            target_tipe='logbook_entry',
            target_id=str(entry.pk),
            status_sesudah='CREATED',
            alasan='logbook quick entry recorded',
        )
        messages.success(request, 'Entri logbook dicatat.')
    else:
        messages.error(request, 'Data tidak valid; periksa kembali.')
    back = reverse('sdm:logbook_list')
    if request.POST.get('pegawai'):
        back = f'{back}?pegawai={request.POST["pegawai"]}'
    return redirect(back)


def _preseptor_units(pegawai):
    """Units where this pegawai qualifies as preseptor (jenjang rule or grant)."""
    from sdm.models import PenempatanPegawai
    from sdm.services.preseptor import eligible_preceptors

    unit_ids = PenempatanPegawai.objects.filter(
        pegawai=pegawai, tanggal_selesai__isnull=True,
    ).values_list('unit_kerja_id', flat=True)
    return {
        unit_id
        for unit_id in unit_ids
        if eligible_preceptors(unit_id).filter(pk=pegawai.pk).exists()
    }


@login_required
def logbook_verifikasi(request):
    """Preseptor queue: entries with no decision or a rejected latest one."""
    try:
        pegawai_sendiri = request.user.pegawai_hc
    except AttributeError:
        pegawai_sendiri = None
    is_preseptor = (
        pegawai_sendiri is not None
        and pegawai_sendiri.status == 'AKTIF'
        and _preseptor_units(pegawai_sendiri).exists()
    )
    has_grant = HcGrant.objects.filter(
        user=request.user, capability='can_review_hc_credentials',
    ).exists()
    if not has_grant and not is_preseptor:
        raise PermissionDenied('Hak verifikasi logbook tidak tersedia.')
    page_obj = Paginator(
        entries_to_verify(request.user).order_by('-tanggal', '-created_at'),
        PAGE_SIZE,
    ).get_page(request.GET.get('page'))
    preseptor_map = _preseptor_map(page_obj)
    for entry in page_obj.object_list:
        entry.preseptor_names = ', '.join(preseptor_map.get(entry.unit_kerja_id, []))
    return render(request, 'sdm/logbook/verifikasi.html', {
        'page_obj': page_obj,
    })


def _preseptor_map(page_obj):
    """entry.pk -> list of eligible preseptor names for that entry's unit."""
    unit_ids = {e.unit_kerja_id for e in page_obj.object_list}
    from sdm.services.preseptor import eligible_preceptors
    hasil = {}
    for unit_id in unit_ids:
        if unit_id is None:
            continue
        for p in eligible_preceptors(unit_id):
            hasil.setdefault(unit_id, []).append(p.nama_lengkap)
    return hasil


@login_required
@require_POST
def logbook_verifikasi_aksi(request, entry_id):
    status = {'approve': VerifikasiLogbook.VERIFIED, 'reject': VerifikasiLogbook.REJECTED}.get(
        request.POST.get('aksi')
    )
    if status is None:
        raise Http404('Aksi verifikasi tidak dikenal.')
    entry = get_object_or_404(
        EntriLogbookKlinis.objects.select_related('unit_kerja'), pk=entry_id,
    )
    verify_entry(
        user=request.user, entry=entry, status=status,
        catatan=request.POST.get('catatan', '').strip(),
    )
    messages.success(request, 'Keputusan verifikasi dicatat.')
    return redirect('sdm:logbook_verifikasi')


@login_required
def logbook_create(request):
    """POST-only creation; HC reviewers pick any visible employee, portal staff
    may only create for their own employee record."""
    if request.method == 'POST':
        pegawai = _portal_pegawai_or_none(request.user)
        posted_employee = _resolve_post_pegawai(request)
        if pegawai is not None and (
            posted_employee is None or posted_employee.pk == pegawai.pk
        ):
            form_employee = pegawai
        else:
            form_employee = posted_employee
        form = EntriLogbookForm(
            request.POST, employee=form_employee, user=request.user,
        )
        if form.is_valid():
            entry = form.save(commit=False)
            target = form_employee
            if target is None:
                messages.error(request, 'Akun belum terhubung data pegawai.')
                return redirect('sdm:logbook_list')
            if not _logbook_target_allowed(request.user, target):
                raise PermissionDenied('Pegawai di luar lingkup.')
            entry.employee = target
            entry.created_by = request.user
            entry.save()
            PeristiwaSDM.objects.create(
                actor=request.user,
                jenis_peristiwa='logbook_entry_created',
                target_tipe='logbook_entry',
                target_id=str(entry.pk),
                status_sesudah='CREATED',
                alasan='logbook entry recorded',
            )
            messages.success(request, 'Entri logbook dicatat.')
            return redirect('sdm:logbook_list')
        messages.error(request, 'Data tidak valid; periksa kembali.')
    return redirect('sdm:logbook_list')


def _logbook_target_allowed(user, target):
    """HC grant covering target's placement unit, or target == own employee."""
    if target.pk == getattr(_portal_pegawai_or_none(user), 'pk', None):
        return True
    try:
        visible_employees(user).get(pk=target.pk)
    except (Pegawai.DoesNotExist, PermissionDenied):
        return False
    return True


@login_required
@require_POST
def logbook_edit(request, entry_id):
    entry = get_object_or_404(
        EntriLogbookKlinis.objects.select_related('employee'), pk=entry_id,
    )
    own = entry.employee_id == getattr(_portal_pegawai_or_none(request.user), 'pk', None)
    if not own:
        require_hc_capability(
            request.user, 'can_review_hc_credentials', employee=entry.employee,
        )
    if entry.sudah_diverifikasi:
        messages.error(request, 'Entri sudah diverifikasi preseptor dan tidak dapat diubah.')
        return redirect('sdm:logbook_list')
    form = EntriLogbookForm(
        request.POST,
        instance=entry,
        employee=entry.employee,
        user=request.user,
    )
    if form.is_valid():
        updated = form.save(commit=False)
        updated.employee = entry.employee
        updated.save()
        PeristiwaSDM.objects.create(
            actor=request.user,
            jenis_peristiwa='logbook_entry_updated',
            target_tipe='logbook_entry',
            target_id=str(entry.pk),
            status_sebelum='UPDATED_PRIOR',
            status_sesudah='UPDATED',
            alasan='logbook entry revised',
        )
        messages.success(request, 'Entri logbook diperbarui.')
    else:
        messages.error(request, 'Data tidak valid; periksa kembali.')
    return redirect('sdm:logbook_list')


@login_required
@require_POST
def logbook_delete(request, entry_id):
    entry = get_object_or_404(
        EntriLogbookKlinis.objects.select_related('employee'), pk=entry_id,
    )
    own = entry.employee_id == getattr(_portal_pegawai_or_none(request.user), 'pk', None)
    if not own:
        require_hc_capability(
            request.user, 'can_review_hc_credentials', employee=entry.employee,
        )
        if entry.created_by_id not in (None, request.user.pk):
            # HC reviewers may only delete rows they created; portal staff their own.
            hc_creator_grant = HcGrant.objects.filter(
                user=request.user, capability='can_review_hc_credentials',
            ).exists()
            raise PermissionDenied(
                'Hanya pembuat entri atau pemilik yang dapat menghapus.'
            ) if not hc_creator_grant else None
    if entry.sudah_diverifikasi:
        messages.error(request, 'Entri sudah diverifikasi preseptor dan tidak dapat dihapus.')
        return redirect('sdm:logbook_list')
    entry.delete()
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='logbook_entry_deleted',
        target_tipe='logbook_entry',
        target_id=str(entry_id),
        status_sebelum='CREATED',
        status_sesudah='DELETED',
        alasan='logbook entry removed',
    )
    messages.success(request, 'Entri logbook dihapus.')
    return redirect('sdm:logbook_list')


# ── C-5: self-service supporting-document upload ─────────────────────────

# Kinds a portal user may upload into their own vault. Health and legal-risk
# documents stay with HC staff (owner decision #3).
# A request may still be edited by its owner while it is a draft or has been
# returned for correction; once the committee has it, editing is closed.
EDITABLE_STATUS = {'DRAFT', 'DIAJUKAN'}

PORTAL_UPLOAD_KINDS = {
    'CV': ('personnel', 'CREDENTIAL'),
    'SERTIFIKAT_KOMPETENSI': ('personnel', 'CREDENTIAL'),
    'TRAINING_RECORD': ('personnel', 'TRAINING'),
    'KEANGGOTAAN': ('personnel', 'PROFESSIONAL'),
    'MCU': ('health', 'HEALTH'),
    'PSIKOLOGIS': ('health', 'HEALTH'),
    'BEBAS_SANKSI': ('personnel', 'PROFESSIONAL'),
}


def _portal_redirect(request):
    """Return to the portal, keeping the jenis the user was inspecting."""
    next_jenis = (request.POST.get('next_jenis') or '').strip()
    if next_jenis in dict(PengajuanKredensial.JENIS_CHOICES):
        return redirect(f"{reverse('sdm:kredensial_pengajuan_sendiri')}?jenis={next_jenis}")
    return redirect('sdm:kredensial_pengajuan_sendiri')


@login_required
@require_POST
def portal_dokumen_upload(request):
    """Own-vault upload: the employee record comes from the session, never POST."""
    pegawai = _portal_pegawai_or_none(request.user)
    if pegawai is None:
        raise PermissionDenied('Akun Anda tidak terhubung dengan data pegawai.')
    jenis = (request.POST.get('jenis_berkas') or '').strip()
    spec = PORTAL_UPLOAD_KINDS.get(jenis)
    if spec is None:
        raise PermissionDenied('Jenis berkas tidak dapat diunggah dari portal.')
    berkas = request.FILES.get('berkas')
    if berkas is None:
        messages.error(request, 'Pilih berkas terlebih dahulu.')
        return _portal_redirect(request)
    sensitivity, document_type = spec
    try:
        document, _version = store_private_document(
            berkas,
            employee=pegawai,
            sensitivity=sensitivity,
            document_type=document_type,
            title=f'{dict(DokumenPegawai.DOCUMENT_KIND_CHOICES).get(jenis, jenis)} — unggahan mandiri',
            uploaded_by=request.user,
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        document.jenis_berkas = jenis
        document.save(update_fields=['jenis_berkas'])
        messages.success(request, 'Dokumen berhasil diunggah ke berkas pribadi Anda.')
    return _portal_redirect(request)


# ── D-3: staged credential workflow ──────────────────────────────────────

@login_required
@require_POST
def kredensial_tahap(request, request_id):
    """Advance the credential request one stage; the legacy status is untouched."""
    from sdm.services.workflow_kredensial import advance_stage

    credential_request = _scoped_or_404(
        PengajuanKredensial, request.user, request_id,
        capability='can_review_hc_credentials',
    )
    try:
        advance_stage(
            credential_request,
            actor=request.user,
            tahap=(request.POST.get('tahap') or '').strip(),
            catatan=(request.POST.get('catatan') or '')[:2000],
            kekurangan=(request.POST.get('kekurangan') or '')[:2000],
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        messages.success(request, 'Tahap kredensial diperbarui.')
    return redirect('sdm:kredensial_detail', request_id=credential_request.pk)


# ── D-4: credential evidence documents mapped to STARKES EP ─────────────

@login_required
def kredensial_bukti_starkes(request):
    """Printable index of the 13 credential evidence documents and their EPs."""
    require_hc_capability(request.user, 'can_review_hc_credentials')
    from sdm.services.bukti_kredensial import map_to_catalog

    rows = map_to_catalog()
    return render(request, 'sdm/kredensial/bukti_starkes.html', {
        'rows': rows,
        'unmatched_total': sum(len(row['unmatched']) for row in rows),
    })


@login_required
def kredensial_pengajuan_ubah(request, request_id):
    """Edit one's own request while it is still editable (draft or returned)."""
    pegawai = _portal_pegawai_or_none(request.user)
    if pegawai is None:
        raise PermissionDenied('Akun Anda tidak terhubung dengan data pegawai.')
    credential_request = get_object_or_404(
        PengajuanKredensial, pk=request_id, employee=pegawai,
    )
    if credential_request.status not in EDITABLE_STATUS:
        raise PermissionDenied(
            'Pengajuan sudah diproses dan tidak dapat diubah.'
        )
    form = PengajuanPortalForm(
        request.POST or None, user=request.user, instance=credential_request,
    )
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        updated.employee = pegawai
        updated.unit_kerja = credential_request.unit_kerja
        updated.save()
        PeristiwaSDM.objects.create(
            actor=request.user,
            jenis_peristiwa='credential_request_edited',
            target_tipe='credential_request',
            target_id=str(updated.pk),
            status_sesudah=updated.status,
            alasan=f'portal edit; jenis={updated.jenis}',
        )
        messages.success(request, 'Pengajuan kredensial diperbarui.')
        return redirect('sdm:kredensial_pengajuan_sendiri')
    return render(request, 'sdm/kredensial/pengajuan_ubah.html', {
        'form': form,
        'credential_request': credential_request,
        'profile': credential_profile(pegawai),
    })


@login_required
@require_POST
def orientasi_asesmen(request, assignment_id):
    """O3.2: record one post-test score (>= 80 passes; failure extends deadline)."""
    from decimal import Decimal, InvalidOperation
    from sdm.models import PenugasanOrientasi
    from sdm.services.orientasi import record_assessment

    assignment = get_object_or_404(
        PenugasanOrientasi.objects.select_related('program', 'employee'),
        pk=assignment_id,
        unit_kerja__in=visible_units(
            request.user, capability='can_manage_hc_orientation'
        ),
    )
    raw = (request.POST.get('nilai') or '').strip()
    try:
        nilai = Decimal(raw)
    except (InvalidOperation, ValueError):
        messages.error(request, 'Nilai tidak valid.')
        return redirect('sdm:orientasi_detail', assignment_id=assignment.pk)
    try:
        record_assessment(
            assignment, nilai=nilai, penguji=request.user,
            catatan=(request.POST.get('catatan') or '')[:500],
        )
    except (PermissionDenied, ValidationError) as exc:
        message = getattr(exc, 'messages', None)
        messages.error(request, '; '.join(message) if message else str(exc))
    else:
        terakhir = assignment.assessments.order_by('-percobaan').first()
        messages.success(
            request,
            'Asesmen tercatat: ' + ('LULUS.' if terakhir.lulus else
                                    'REMEDI; tenggat diperpanjang.'),
        )
    return redirect('sdm:orientasi_detail', assignment_id=assignment.pk)


@login_required
def orientasi_sertifikat(request, assignment_id):
    """O4.4: download the certificate PDF for a completed assignment."""
    from django.http import HttpResponse
    from sdm.models import PenugasanOrientasi
    from sdm.services.orientasi import render_sertifikat_pdf

    assignment = get_object_or_404(
        PenugasanOrientasi.objects.select_related('program', 'employee'),
        pk=assignment_id,
    )
    milik_sendiri = getattr(request.user, 'pegawai_hc', None) == assignment.employee
    if not milik_sendiri:
        require_hc_capability(request.user, 'can_manage_hc_orientation')
    pdf = render_sertifikat_pdf(assignment)
    response = HttpResponse(pdf, content_type='application/pdf')
    nama = f"Sertifikat Orientasi {assignment.employee.nama_lengkap}.pdf"
    for bad in ('"', '\\', '\r', '\n'):
        nama = nama.replace(bad, ' ')
    response['Content-Disposition'] = f'attachment; filename="{nama}"'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def orientasi_tor_pdf(request, program_id):
    """O4.4: download the TOR/KAK PDF rendered from program data."""
    from django.http import HttpResponse
    from sdm.models import ProgramOrientasi
    from sdm.services.orientasi import render_tor_pdf

    program = get_object_or_404(ProgramOrientasi, pk=program_id)
    require_hc_capability(request.user, 'can_manage_hc_orientation')
    pdf = render_tor_pdf(program)
    response = HttpResponse(pdf, content_type='application/pdf')
    nama = f"TOR {program.nama}.pdf"
    for bad in ('"', '\\', '\r', '\n'):
        nama = nama.replace(bad, ' ')
    response['Content-Disposition'] = f'attachment; filename="{nama}"'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def orientasi_rekap_pdf(request):
    """O5.2: PDF recap of the orientation dashboard, honoring filters."""
    from django.http import HttpResponse
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from reportlab.lib import colors
    from sdm.services.orientasi import _pdf_styles, _pdf_kop

    require_hc_capability(request.user, 'can_manage_hc_orientation')
    units = visible_units(request.user, capability='can_manage_hc_orientation')
    assignments = PenugasanOrientasi.objects.filter(
        unit_kerja__in=units,
    ).select_related('employee', 'program', 'unit_kerja')
    unit_filter = (request.GET.get('unit') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()
    if unit_filter.isdigit():
        assignments = assignments.filter(unit_kerja_id=int(unit_filter))
    if status_filter == 'WARNING':
        assignments = assignments.filter(status='BERJALAN', tenggat__lt=timezone.localdate())
    elif status_filter:
        assignments = assignments.filter(status=status_filter)

    styles = _pdf_styles()
    story = []
    _pdf_kop(story, styles)
    story.append(Paragraph('REKAPITULASI ORIENTASI STAF', styles['title']))
    story.append(Paragraph(
        f'Dicetak {timezone.localdate()} · status={status_filter or "SEMUA"}, '
        f'unit={unit_filter or "SEMUA"}', styles['footnote'],
    ))
    story.append(Spacer(1, 4 * mm))
    rows = [[
        'Nama', 'Program', 'Unit', 'Mulai', 'Tenggat', 'Status',
    ]]
    for a in assignments.order_by('-tanggal_mulai')[:300]:
        rows.append([
            a.employee.nama_lengkap[:28], a.program.nama[:30],
            (a.unit_kerja.name if a.unit_kerja else '')[:18],
            str(a.tanggal_mulai), str(a.tenggat), a.status,
        ])
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(table)
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm,
                      bottomMargin=14 * mm).build(story)
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        'attachment; filename="rekap-orientasi.pdf"'
    )
    response['Cache-Control'] = 'private, no-store'
    return response
