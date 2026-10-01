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

# ── DEFINISI RESMI RENSTRA 5 TAHUN (2026–2030) RS MONSISKAMI ─────────────
RENSTRA_ANNUAL_FOCUS = {
    2026: {
        'tahun': 2026,
        'isu_strategis': 'Consolidation & Digital Foundation',
        'sub_tema': 'Transisi Digital RME, Integrasi SATUSEHAT & Keandalan SIMRS',
        'deskripsi': 'Fokus konsolidasi fondasi digital rekam medis, integrasi interoperabilitas SATUSEHAT Kemenkes, dan stabilisasi sistem SIMRS RS.',
        'fokus_items': [
            {'nomor': 1, 'nama': 'Kelengkapan RME < 24 Jam Pasca Visite', 'target': '100%', 'target_val': 100.0, 'satuan': '%', 'kode_ref': 'IMP-RANAP-03', 'unit_name': 'Rawat Inap & Yanmed'},
            {'nomor': 2, 'nama': 'Uptime Sistem SIMRS', 'target': '≥ 99,5%', 'target_val': 99.5, 'satuan': '%', 'kode_ref': 'IMP-RM-03', 'unit_name': 'Rekam Medis & SIMRS'},
            {'nomor': 3, 'nama': 'Integrasi Data RME ke SATUSEHAT', 'target': '100%', 'target_val': 100.0, 'satuan': '%', 'kode_ref': 'IMP-RM-01', 'unit_name': 'Rekam Medis & SIMRS'},
        ]
    },
    2027: {
        'tahun': 2027,
        'isu_strategis': 'Service Modernization & Cost Containment',
        'sub_tema': 'Kendali Mutu Biaya, Clinical Pathway Berbasis AI & Minimalisasi Pending Claim',
        'deskripsi': 'Standardisasi pelayanan klinis terpandu AI, kepatuhan formularium/clinical pathway, serta optimasi siklus casemix/klaim BPJS.',
        'fokus_items': [
            {'nomor': 1, 'nama': 'Kepatuhan Clinical Pathway Berbasis AI Decision Support', 'target': '≥ 85%', 'target_val': 85.0, 'satuan': '%', 'kode_ref': 'INM-08', 'unit_name': 'Komite Medik & Yanmed'},
            {'nomor': 2, 'nama': 'Variasi Biaya Antar-DPJP (Kendali Mutu & Biaya)', 'target': '≤ 10%', 'target_val': 10.0, 'satuan': '%', 'kode_ref': 'IMP-KEU-03', 'unit_name': 'Keuangan & Casemix'},
            {'nomor': 3, 'nama': 'Angka Pengembalian Berkas Klaim BPJS (Pending Claim)', 'target': '≤ 3%', 'target_val': 3.0, 'satuan': '%', 'kode_ref': 'IMP-KEU-02', 'unit_name': 'Keuangan & Casemix'},
        ]
    },
    2028: {
        'tahun': 2028,
        'isu_strategis': 'Capacity Expansion & Clinical Excellence',
        'sub_tema': 'Standarisasi Fasilitas KRIS, Efisiensi Alur UGD & Respons ICU/Bangsal',
        'deskripsi': 'Peningkatan kapasitas rawat inap berstandar KRIS 12 kriteria, eliminasi bottleneck waktu tunggu UGD, dan percepatan transfer kritis.',
        'fokus_items': [
            {'nomor': 1, 'nama': 'Length of Stay (LOS) Pasien di UGD < 6 Jam', 'target': '< 6 jam (≥ 85%)', 'target_val': 85.0, 'satuan': '%', 'kode_ref': 'IMP-UGD-02', 'unit_name': 'Instalasi Gawat Darurat'},
            {'nomor': 2, 'nama': 'Pemenuhan 12 Kriteria Standar KRIS Rawat Inap', 'target': '100%', 'target_val': 100.0, 'satuan': '%', 'kode_ref': 'IMP-RANAP-01', 'unit_name': 'Rawat Inap & Sarpras'},
            {'nomor': 3, 'nama': 'Turnaround Time Pindah Pasien ICU ke Bangsal (< 2 Jam)', 'target': '< 2 jam (≥ 80%)', 'target_val': 80.0, 'satuan': '%', 'kode_ref': 'IMP-ICU-03', 'unit_name': 'Intensive Care Unit (ICU)'},
        ]
    },
    2029: {
        'tahun': 2029,
        'isu_strategis': 'Market Leadership & Sustainability',
        'sub_tema': 'Green Hospital, Zero Accident K3RS & Efisiensi Energi Operasional',
        'deskripsi': 'Penerapan standar rumah sakit ramah lingkungan (Green Hospital), kepatuhan limbah B3/IPAL berbasis IoT, dan nihil kecelakaan kerja.',
        'fokus_items': [
            {'nomor': 1, 'nama': 'Kepatuhan Pengelolaan Limbah B3 / IPAL IoT (Green Hospital)', 'target': '100%', 'target_val': 100.0, 'satuan': '%', 'kode_ref': 'IMP-RAD-03', 'unit_name': 'K3RS & Sanitasi'},
            {'nomor': 2, 'nama': 'Angka Kecelakaan Kerja (K3RS)', 'target': '0%', 'target_val': 0.0, 'satuan': '%', 'kode_ref': 'IMP-FARM-03', 'unit_name': 'K3RS & SDM'},
            {'nomor': 3, 'nama': 'Efisiensi Konsumsi Energi/Air Operasional', 'target': '≥ 15%', 'target_val': 15.0, 'satuan': '%', 'kode_ref': 'IMP-GIZI-02', 'unit_name': 'Pemeliharaan Sarana (IPSRS)'},
        ]
    },
    2030: {
        'tahun': 2030,
        'isu_strategis': 'Regional Benchmark & High Reliability Organization',
        'sub_tema': 'Keseimbangan Beban Kerja (NASA-TLX), Retensi Staf & Indeks Kepuasan Publik',
        'deskripsi': 'Mewujudkan RS rujukan regional berstandar High Reliability Organization (HRO), kesejahteraan staf optimal, dan kepuasan publik paripurna.',
        'fokus_items': [
            {'nomor': 1, 'nama': 'Evaluasi Beban Kerja Staf Medis & Non-Medis (NASA-TLX)', 'target': 'Seimbang / Optimal', 'target_val': 80.0, 'satuan': 'Skor', 'kode_ref': 'IMP-SDM-01', 'unit_name': 'SDM & Diklat'},
            {'nomor': 2, 'nama': 'Indeks Kepuasan & Retensi Pegawai (Employee Satisfaction)', 'target': '≥ 85%', 'target_val': 85.0, 'satuan': '%', 'kode_ref': 'IMP-SDM-02', 'unit_name': 'SDM & Diklat'},
            {'nomor': 3, 'nama': 'Indeks Kepuasan Masyarakat (IKM) & Retensi Pasien', 'target': '≥ 90%', 'target_val': 90.0, 'satuan': '%', 'kode_ref': 'INM-11', 'unit_name': 'Humas & Mutu RS'},
        ]
    }
}


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
    try:
        tahun_int = int(tahun)
    except (ValueError, TypeError):
        tahun_int = 2026
    tahun = str(tahun_int)

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

    # Ambil catatan capaian terakhir untuk tahun ini per indikator
    indikators = qs.order_by('jenis', 'kode_indikator')
    current_renstra = RENSTRA_ANNUAL_FOCUS.get(tahun_int, RENSTRA_ANNUAL_FOCUS[2026])
    fokus_kode_set = {item['kode_ref'] for item in current_renstra['fokus_items']}

    # Ringkasan dan pembagian grup indikator
    summary = {}
    indikators_with_stats = []
    inm_list = []
    fokus_renstra_list = []
    imp_rs_other_list = []

    for ind in indikators:
        jenis_label = ind.get_jenis_display()
        if jenis_label not in summary:
            summary[jenis_label] = {'total': 0, 'tercapai': 0, 'belum': 0}
        summary[jenis_label]['total'] += 1

        last = ind.catatan.filter(tahun=tahun_int).order_by('-bulan').first()
        is_tercapai = bool(last and last.tercapai)
        if is_tercapai:
            summary[jenis_label]['tercapai'] += 1
        else:
            summary[jenis_label]['belum'] += 1

        # Tambahkan metadata dinamis untuk template
        ind.last_catatan = last
        ind.is_tercapai = is_tercapai
        ind.is_renstra_focus = ind.kode_indikator in fokus_kode_set

        indikators_with_stats.append(ind)
        if ind.jenis == 'NASIONAL':
            inm_list.append(ind)
        elif ind.is_renstra_focus:
            fokus_renstra_list.append(ind)
        else:
            imp_rs_other_list.append(ind)

    units = UnitKerja.objects.filter(level__lte=3).order_by('order', 'name')

    ctx = {
        'indikators': indikators_with_stats,
        'inm_list': inm_list,
        'fokus_renstra_list': fokus_renstra_list,
        'imp_rs_other_list': imp_rs_other_list,
        'current_renstra': current_renstra,
        'renstra_all': RENSTRA_ANNUAL_FOCUS,
        'summary': summary,
        'jenis_choices': IndikatorMutu.JENIS_CHOICES,
        'units': units,
        'filter_jenis': jenis,
        'filter_unit': unit_id,
        'filter_tahun': tahun_int,
        'tahun_choices': [2026, 2027, 2028, 2029, 2030],
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
