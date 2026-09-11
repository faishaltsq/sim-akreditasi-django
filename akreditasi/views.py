import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.views.decorators.http import require_POST
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from .models import (
    Category, StandardItem, QualityRecord,
    EvidenceReq, EvidenceFile, UnitKerja, Framework, AuditLog
)
from .forms import StandardItemForm, QualityRecordForm, UnitKerjaForm, EvidenceFileUploadForm
from .supabase_storage import upload_to_supabase_storage


@login_required
def dashboard(request):
    active_cat_id = request.GET.get('cat')
    selected_unit_id = request.GET.get('unit', 'ALL')

    categories = Category.objects.all().order_by('order')
    if not categories.exists():
        return render(request, 'akreditasi/empty.html')

    if active_cat_id:
        active_category = get_object_or_404(Category, id=active_cat_id)
    else:
        active_category = categories.first()

    items_qs = active_category.items.prefetch_related(
        'evidence_reqs__files',
        'record__unit'
    ).order_by('order', 'code')

    if selected_unit_id != 'ALL':
        items_qs = items_qs.filter(record__unit_id=selected_unit_id)

    items = list(items_qs)

    total_possible = len(items) * 10
    total_score = sum(getattr(item, 'record', None).score if hasattr(item, 'record') and item.record else 0 for item in items)
    percentage = round((total_score / total_possible) * 100) if total_possible > 0 else 0

    total_cost = 0
    capex_cost = 0
    opex_cost = 0
    non_cost_count = 0

    for item in items:
        rec = getattr(item, 'record', None)
        if rec:
            cost = float(rec.est_cost or 0)
            total_cost += cost
            if 'Capex' in (rec.budget_source or '') or 'Sarpras' in (rec.budget_source or ''):
                capex_cost += cost
            elif cost > 0:
                opex_cost += cost
            else:
                non_cost_count += 1

    units = UnitKerja.objects.all().order_by('code')

    status_badge = active_category.status_level if active_category else {'label': 'BELUM', 'badge': 'danger'}

    context = {
        'categories': categories,
        'active_category': active_category,
        'items': items,
        'units': units,
        'selected_unit_id': selected_unit_id,
        'total_score': total_score,
        'total_possible': total_possible,
        'percentage': percentage,
        'status_badge': status_badge,
        'total_cost': total_cost,
        'capex_cost': capex_cost,
        'opex_cost': opex_cost,
        'non_cost_count': non_cost_count,
    }
    return render(request, 'akreditasi/dashboard.html', context)


@login_required
@require_POST
def quick_score(request, record_id):
    record = get_object_or_404(QualityRecord, id=record_id)
    try:
        data = json.loads(request.body)
        new_score = int(data.get('score', 0))
        if new_score in [10, 5, 0]:
            old_score = record.score
            record.score = new_score
            record.save()

            AuditLog.objects.create(
                user=request.user,
                aksi='SCORE',
                model_name='QualityRecord',
                object_repr=f"{record.standard_item.code} - {record.unit.name}",
                detail=f"Skor diubah dari {old_score} ke {new_score}"
            )

            cat = record.standard_item.category
            return JsonResponse({
                'success': True,
                'score': new_score,
                'cat_score': cat.total_score,
                'cat_max': cat.max_possible_score,
                'cat_percentage': cat.percentage,
            })
        return JsonResponse({'success': False, 'error': 'Invalid score'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def ep_create(request):
    if request.method == 'POST':
        item_form = StandardItemForm(request.POST)
        record_form = QualityRecordForm(request.POST)
        if item_form.is_valid() and record_form.is_valid():
            with transaction.atomic():
                item = item_form.save()
                record = record_form.save(commit=False)
                record.standard_item = item
                record.save()

                req_types = request.POST.getlist('req_type[]')
                req_titles = request.POST.getlist('req_title[]')
                for t, title in zip(req_types, req_titles):
                    if t and title:
                        EvidenceReq.objects.create(
                            standard_item=item,
                            category_type=t,
                            title=title,
                            is_mandatory=True
                        )

                AuditLog.objects.create(
                    user=request.user,
                    aksi='CREATE',
                    model_name='StandardItem',
                    object_repr=item.code,
                    detail=f"EP baru ditambahkan: {item.description[:100]}"
                )

                messages.success(request, f"Elemen Penilaian {item.code} berhasil ditambahkan!")
                return redirect(f"/dashboard/?cat={item.category.id}")
    else:
        init_cat = request.GET.get('cat')
        initial_data = {}
        if init_cat:
            initial_data['category'] = init_cat
        item_form = StandardItemForm(initial=initial_data)
        record_form = QualityRecordForm()

    return render(request, 'akreditasi/ep_form.html', {
        'item_form': item_form,
        'record_form': record_form,
        'title': 'Tambah Elemen Penilaian Baru',
    })


@login_required
def ep_edit(request, item_id):
    item = get_object_or_404(StandardItem, id=item_id)
    record, _ = QualityRecord.objects.get_or_create(
        standard_item=item,
        defaults={'unit': UnitKerja.objects.first(), 'score': 0}
    )

    if request.method == 'POST':
        item_form = StandardItemForm(request.POST, instance=item)
        record_form = QualityRecordForm(request.POST, instance=record)
        if item_form.is_valid() and record_form.is_valid():
            with transaction.atomic():
                item_form.save()
                record_form.save()

                AuditLog.objects.create(
                    user=request.user,
                    aksi='UPDATE',
                    model_name='StandardItem',
                    object_repr=item.code,
                    detail="Data EP dan Siklus PDCA diperbarui"
                )

                messages.success(request, f"Perubahan pada {item.code} berhasil disimpan!")
                return redirect(f"/dashboard/?cat={item.category.id}")
    else:
        item_form = StandardItemForm(instance=item)
        record_form = QualityRecordForm(instance=record)

    return render(request, 'akreditasi/ep_form.html', {
        'item_form': item_form,
        'record_form': record_form,
        'item': item,
        'title': f'Edit EP: {item.code}',
    })


@login_required
def ep_detail(request, item_id):
    item = get_object_or_404(StandardItem, id=item_id)
    record = getattr(item, 'record', None)
    upload_form = EvidenceFileUploadForm()
    return render(request, 'akreditasi/ep_detail.html', {
        'item': item,
        'record': record,
        'upload_form': upload_form,
    })


@login_required
@require_POST
def upload_bukti(request, req_id):
    evidence_req = get_object_or_404(EvidenceReq, id=req_id)
    file_obj = request.FILES.get('file')

    if not file_obj:
        messages.error(request, "Pilih berkas terlebih dahulu.")
        return redirect('akreditasi:ep_detail', item_id=evidence_req.standard_item.id)

    res = upload_to_supabase_storage(file_obj, file_obj.name)
    if res.get('success'):
        size_mb = f"{file_obj.size / (1024 * 1024):.1f} MB" if file_obj.size >= 1024 * 1024 else f"{file_obj.size / 1024:.0f} KB"
        EvidenceFile.objects.create(
            requirement=evidence_req,
            file=file_obj if not res.get('is_cloud') else None,
            file_url=res.get('url', ''),
            file_name=file_obj.name,
            file_size=size_mb,
            status='VALID'
        )
        AuditLog.objects.create(
            user=request.user,
            aksi='UPLOAD',
            model_name='EvidenceFile',
            object_repr=f"{evidence_req.standard_item.code} - {file_obj.name}",
            detail="Berkas bukti berhasil diunggah"
        )
        messages.success(request, f"Berkas '{file_obj.name}' berhasil diunggah!")
    else:
        messages.error(request, f"Gagal mengunggah berkas: {res.get('error', 'Unknown error')}")

    return redirect('akreditasi:ep_detail', item_id=evidence_req.standard_item.id)


@login_required
@require_POST
def ep_delete(request, item_id):
    item = get_object_or_404(StandardItem, id=item_id)
    code = item.code
    cat_id = item.category.id
    item.delete()

    AuditLog.objects.create(
        user=request.user,
        aksi='DELETE',
        model_name='StandardItem',
        object_repr=code,
        detail="Elemen Penilaian dihapus permanen"
    )
    messages.success(request, f"Elemen Penilaian {code} telah dihapus.")
    return redirect(f"/dashboard/?cat={cat_id}")


@login_required
def unit_list_create(request):
    units = UnitKerja.objects.all().order_by('code')
    if request.method == 'POST':
        form = UnitKerjaForm(request.POST)
        if form.is_valid():
            u = form.save()
            messages.success(request, f"Unit Kerja '{u.name}' berhasil ditambahkan!")
            return redirect('akreditasi:unit_list')
    else:
        form = UnitKerjaForm()
    return render(request, 'akreditasi/unit_form.html', {'units': units, 'form': form})


@login_required
def rekap_view(request):
    categories = Category.objects.all().order_by('order')
    items = StandardItem.objects.select_related('category', 'record__unit').prefetch_related('evidence_reqs__files').order_by('category__order', 'order', 'code')

    total_possible = items.count() * 10
    total_score = sum(i.record.score for i in items if hasattr(i, 'record') and i.record)
    overall_pct = round((total_score / total_possible) * 100) if total_possible > 0 else 0

    total_rka = sum(float(i.record.est_cost or 0) for i in items if hasattr(i, 'record') and i.record)

    return render(request, 'akreditasi/rekap.html', {
        'categories': categories,
        'items': items,
        'total_possible': total_possible,
        'total_score': total_score,
        'overall_pct': overall_pct,
        'total_rka': total_rka,
    })


@login_required
def export_excel(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Matriks PDCA STARKES"

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border_thin = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0'),
    )

    headers = [
        "Pokja", "Sub-Standar", "Kode EP", "Unit Kerja", "Asesmen Baseline",
        "PLAN: Indikator Mutu", "PLAN: Mitigasi Risiko",
        "DO: Bukti Pembuktian", "CHECK: Skor (0/5/10)", "CHECK: Catatan",
        "ACTION: RTL", "PIC", "Target Waktu", "Estimasi Biaya (Rp)", "Sumber Anggaran", "Status Anggaran"
    ]
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center

    items = StandardItem.objects.select_related('category', 'record__unit').prefetch_related('evidence_reqs').order_by('category__order', 'order')

    for item in items:
        rec = getattr(item, 'record', None)
        bukti_list = [f"[{req.category_type}] {req.title}" for req in item.evidence_reqs.all()]
        bukti_str = "\n".join(bukti_list)

        row = [
            item.category.code,
            item.sub_standard,
            item.code,
            rec.unit.name if rec and rec.unit else "-",
            rec.baseline_data if rec else "-",
            rec.quality_target if rec else "-",
            rec.risk_mitigation if rec else "-",
            bukti_str,
            rec.score if rec else 0,
            rec.eval_notes if rec else "-",
            rec.action_plan if rec else "-",
            rec.pic if rec else "-",
            rec.target_date if rec else "-",
            float(rec.est_cost or 0) if rec else 0,
            rec.budget_source if rec else "-",
            rec.get_budget_status_display() if rec else "-",
        ]
        ws.append(row)

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = border_thin
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 22
    ws.column_dimensions['E'].width = 30
    ws.column_dimensions['F'].width = 25
    ws.column_dimensions['G'].width = 25
    ws.column_dimensions['H'].width = 30
    ws.column_dimensions['I'].width = 12
    ws.column_dimensions['J'].width = 25
    ws.column_dimensions['K'].width = 30
    ws.column_dimensions['L'].width = 15
    ws.column_dimensions['M'].width = 12
    ws.column_dimensions['N'].width = 18
    ws.column_dimensions['O'].width = 20
    ws.column_dimensions['P'].width = 15

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="Matriks_PDCA_Akreditasi_RS.xlsx"'
    wb.save(response)
    return response
