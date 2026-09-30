"""
Views Indikator Mutu — INM Kemenkes + IMP-RS per Bidang Kerja
"""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.http import JsonResponse

from .risiko_models import IndikatorMutu, CatatanIndikator
from .models import UnitKerja, AuditLog


def _log(user, aksi, obj, detail=''):
    AuditLog.objects.create(
        user=user, aksi=aksi,
        model_name=obj.__class__.__name__,
        object_repr=str(obj)[:250],
        detail=detail,
    )


def _is_manager(user):
    """SUPER_ADMIN, ADMIN_RS, KOORDINATOR, KEPALA_UNIT."""
    if user.is_superuser:
        return True
    p = getattr(user, 'profile', None)
    return p and p.role in ('SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR', 'KEPALA_UNIT')


# ── 1. Dashboard Indikator Mutu ──────────────────────────────────────────

@login_required
def indikator_dashboard(request):
    """Dashboard overview: INM, IMP-RS, IMP-Unit, ringkasan capaian."""
    jenis = request.GET.get('jenis', '')
    unit_id = request.GET.get('unit', '')
    tahun = request.GET.get('tahun', '2026')

    qs = IndikatorMutu.objects.filter(aktif=True).select_related('unit', 'ep_terkait')

    # Filter
    if jenis:
        qs = qs.filter(jenis=jenis)
    if unit_id:
        qs = qs.filter(unit_id=unit_id)

    # Unit-scoped user: hanya lihat indikator unit sendiri + NASIONAL
    profile = getattr(request.user, 'profile', None)
    is_unit_scoped = profile and profile.is_unit_scoped
    if is_unit_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja
        # Ambil unit sendiri + semua child
        unit_ids = list(UnitKerja.objects.filter(
            Q(pk=user_unit.pk) | Q(parent=user_unit) | Q(parent__parent=user_unit)
        ).values_list('pk', flat=True))
        qs = qs.filter(Q(unit_id__in=unit_ids) | Q(jenis='NASIONAL'))

    indikators = qs.order_by('jenis', 'kode_indikator')

    # Ringkasan per jenis
    summary = {}
    for ind in indikators:
        jenis_label = ind.get_jenis_display()
        if jenis_label not in summary:
            summary[jenis_label] = {'total': 0, 'tercapai': 0, 'belum': 0}
        summary[jenis_label]['total'] += 1
        # Cek capaian terakhir
        last = ind.catatan.filter(tahun=int(tahun) if tahun.isdigit() else 2026).order_by('-bulan').first()
        if last and last.tercapai:
            summary[jenis_label]['tercapai'] += 1
        else:
            summary[jenis_label]['belum'] += 1

    units = UnitKerja.objects.filter(level__lte=3).order_by('order', 'name')

    ctx = {
        'indikators': indikators,
        'summary': summary,
        'jenis_choices': IndikatorMutu.JENIS_CHOICES,
        'units': units,
        'filter_jenis': jenis,
        'filter_unit': unit_id,
        'filter_tahun': tahun,
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'akreditasi/indikator_dashboard.html', ctx)


# ── 2. Detail Indikator ──────────────────────────────────────────────────

@login_required
def indikator_detail(request, indikator_id):
    ind = get_object_or_404(IndikatorMutu.objects.select_related('unit', 'ep_terkait'), pk=indikator_id)
    tahun = int(request.GET.get('tahun', 2026))
    catatan = ind.catatan.filter(tahun=tahun).order_by('bulan')

    # Data chart: 12 bulan
    chart_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des']
    chart_data = [None] * 12
    for c in catatan:
        if 1 <= c.bulan <= 12:
            chart_data[c.bulan - 1] = float(c.nilai_capaian)

    ctx = {
        'ind': ind,
        'catatan': catatan,
        'tahun': tahun,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'target_line': float(ind.target_nilai),
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'akreditasi/indikator_detail.html', ctx)


# ── 3. Input Capaian Bulanan ─────────────────────────────────────────────

@login_required
def indikator_input_capaian(request, indikator_id):
    if not _is_manager(request.user):
        messages.error(request, 'Akses ditolak.')
        return redirect('akreditasi:indikator_dashboard')

    ind = get_object_or_404(IndikatorMutu.objects.select_related('unit'), pk=indikator_id)

    if request.method == 'POST':
        try:
            bulan = int(request.POST['bulan'])
            tahun = int(request.POST['tahun'])
            num = Decimal(request.POST['nilai_numerator'])
            den = Decimal(request.POST['nilai_denominator'])
            catatan_text = request.POST.get('catatan', '')

            if den <= 0:
                raise ValueError('Denominator harus > 0')

            obj, created = CatatanIndikator.objects.update_or_create(
                indikator=ind, bulan=bulan, tahun=tahun,
                defaults={
                    'nilai_numerator': num,
                    'nilai_denominator': den,
                    'catatan': catatan_text,
                }
            )
            _log(request.user, 'CREATE' if created else 'UPDATE', obj,
                 f'Capaian {ind.kode_indikator} bulan {bulan}/{tahun}: {float(obj.nilai_capaian):.1f}%')
            messages.success(request, f'Capaian bulan {bulan}/{tahun} berhasil disimpan.')
            return redirect('akreditasi:indikator_detail', indikator_id=ind.pk)
        except (ValueError, InvalidOperation) as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    ctx = {
        'ind': ind,
        'bulan_choices': list(range(1, 13)),
    }
    return render(request, 'akreditasi/indikator_input_capaian.html', ctx)
