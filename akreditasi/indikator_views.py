"""
Views Indikator Mutu — INM Kemenkes + IMP-RS per Bidang Kerja
"""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse

from .risiko_models import IndikatorMutu, CatatanIndikator
from .models import UnitKerja, AuditLog, StandardItem

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


def get_dynamic_renstra_dict():
    """Load Renstra data from DB with safe fallback to RENSTRA_ANNUAL_FOCUS static dict."""
    try:
        from .risiko_models import RenstraRoadmap
        roadmaps = list(
            RenstraRoadmap.objects.filter(aktif=True)
            .prefetch_related('fokus_items__indikator_mutu')
            .order_by('urutan', 'tahun')
        )
        if not roadmaps:
            return RENSTRA_ANNUAL_FOCUS
        result = {}
        for rm in roadmaps:
            fokus_list = []
            # .all() memakai cache prefetch (Meta.ordering sudah ['nomor']);
            # .order_by() membuat queryset baru & membatalkan prefetch indikator_mutu
            for item in rm.fokus_items.all():
                kode = item.indikator_mutu.kode_indikator if item.indikator_mutu else item.kode_ref
                fokus_list.append({
                    'nomor':       item.nomor,
                    'nama':        item.nama_fokus,
                    'target':      item.target_label,
                    'target_val':  float(item.target_nilai),
                    'satuan':      item.satuan,
                    'kode_ref':    kode,
                    'unit_name':   item.unit_kerja_label,
                })
            result[rm.tahun] = {
                'tahun':          rm.tahun,
                'isu_strategis':  rm.isu_strategis,
                'sub_tema':       rm.sub_tema,
                'deskripsi':      rm.deskripsi,
                'fokus_items':    fokus_list,
            }
        return result
    except Exception:
        return RENSTRA_ANNUAL_FOCUS


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

    # Normalize canonical 3-tier filter → DB codes (support both old and new)
    JENIS_CANONICAL_MAP = {
        'INM':  ['INM', 'NASIONAL'],
        'IMRS': ['IMRS', 'IMP_RS'],
        'IMU':  ['IMU', 'IMP_UNIT'],
    }

    # Filter
    if jenis:
        db_codes = JENIS_CANONICAL_MAP.get(jenis, [jenis])
        qs = qs.filter(jenis__in=db_codes)
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
    # (prefetch sekali — dulu 1 query per indikator di loop)
    from django.db.models import Prefetch
    indikators = qs.order_by('jenis', 'kode_indikator').prefetch_related(
        Prefetch(
            'catatan',
            queryset=CatatanIndikator.objects.filter(tahun=tahun_int).order_by('-bulan'),
            to_attr='catatan_tahun_cache',
        )
    )
    _renstra_data = get_dynamic_renstra_dict()
    _fallback_year = next(iter(_renstra_data.keys())) if _renstra_data else 2026
    current_renstra = _renstra_data.get(tahun_int, _renstra_data.get(_fallback_year, {}))
    fokus_kode_set = {item['kode_ref'] for item in current_renstra.get('fokus_items', []) if item.get('kode_ref')}

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

        _ct = ind.catatan_tahun_cache
        last = _ct[0] if _ct else None
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

    # ── Chart.js: tren capaian bulanan (Jan–Des) ────────────────
    import json as _json
    from decimal import Decimal as _Dec
    BULAN_LABELS = ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des']

    # Ambil semua catatan indikator untuk tahun ini yang indikatornya masuk filter
    ind_ids = [i.pk for i in indikators_with_stats]
    catatan_qs = CatatanIndikator.objects.filter(
        indikator_id__in=ind_ids, tahun=tahun_int
    ).values('bulan').annotate(
        avg_num=Sum('nilai_numerator'),
        avg_den=Sum('nilai_denominator'),
        count=Count('id'),
    ).order_by('bulan')

    # Build monthly avg capaian %
    monthly_avg = {}
    for c in catatan_qs:
        if c['avg_den'] and c['avg_den'] > 0:
            pct = float(round((c['avg_num'] / c['avg_den']) * 100, 1))
        else:
            pct = 0.0
        monthly_avg[c['bulan']] = {'pct': pct, 'count': c['count']}

    chart_labels = _json.dumps(BULAN_LABELS)
    chart_capaian = _json.dumps([monthly_avg.get(m, {}).get('pct', None) for m in range(1, 13)])
    chart_jumlah  = _json.dumps([monthly_avg.get(m, {}).get('count', 0) for m in range(1, 13)])

    # Per-jenis monthly breakdown for stacked bar
    jenis_map = {'NASIONAL': 'INM Nasional', 'IMP_RS': 'IMP-RS', 'IMP_UNIT': 'IMP Unit'}
    chart_jenis_datasets = []
    jenis_colors = {'NASIONAL': '#0d9488', 'IMP_RS': '#6366f1', 'IMP_UNIT': '#f59e0b'}
    for jcode, jlabel in jenis_map.items():
        j_ids = [i.pk for i in indikators_with_stats if i.jenis == jcode]
        if not j_ids:
            continue
        j_cat = CatatanIndikator.objects.filter(
            indikator_id__in=j_ids, tahun=tahun_int
        ).values('bulan').annotate(n=Count('id')).order_by('bulan')
        j_monthly = {c['bulan']: c['n'] for c in j_cat}
        chart_jenis_datasets.append({
            'label': jlabel,
            'data': [j_monthly.get(m, 0) for m in range(1, 13)],
            'backgroundColor': jenis_colors.get(jcode, '#94a3b8'),
        })
    chart_jenis_json = _json.dumps(chart_jenis_datasets)

    ctx = {
        'indikators': indikators_with_stats,
        'inm_list': inm_list,
        'fokus_renstra_list': fokus_renstra_list,
        'imp_rs_other_list': imp_rs_other_list,
        'current_renstra': current_renstra,
        'renstra_all': _renstra_data,
        'summary': summary,
        'jenis_choices': IndikatorMutu.JENIS_CHOICES,
        'units': units,
        'filter_jenis': jenis,
        'filter_unit': unit_id,
        'filter_tahun': tahun_int,
        'tahun_choices': list(_renstra_data.keys()) if _renstra_data else [2026, 2027, 2028, 2029, 2030],
        'is_manager': _is_manager(request.user),
        'chart_labels': chart_labels,
        'chart_capaian': chart_capaian,
        'chart_jumlah': chart_jumlah,
        'chart_jenis_json': chart_jenis_json,
    }
    return render(request, 'akreditasi/indikator_dashboard.html', ctx)


# ── 2. Detail Indikator ──────────────────────────────────────────────────

@login_required
def indikator_detail(request, indikator_id):
    import json as _json
    ind = get_object_or_404(IndikatorMutu.objects.select_related('unit', 'ep_terkait'), pk=indikator_id)
    tahun = int(request.GET.get('tahun', 2026))
    catatan = ind.catatan.filter(tahun=tahun).order_by('bulan')

    # Data chart: 12 bulan — json.dumps agar None berubah menjadi null di JavaScript
    chart_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des']
    chart_data_raw = [None] * 12
    for c in catatan:
        if 1 <= c.bulan <= 12:
            chart_data_raw[c.bulan - 1] = float(c.nilai_capaian)

    ctx = {
        'ind': ind,
        'catatan': catatan,
        'tahun': tahun,
        'chart_labels': _json.dumps(chart_labels),
        'chart_data': _json.dumps(chart_data_raw),
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

            file_bukti = request.FILES.get('bukti_dokumen')
            if file_bukti:
                ext = file_bukti.name.split('.')[-1].lower() if '.' in file_bukti.name else ''
                allowed_exts = {'pdf', 'docx', 'doc', 'jpg', 'jpeg', 'png', 'xlsx', 'xls'}
                if ext not in allowed_exts:
                    raise ValueError(f'Format berkas .{ext} tidak diizinkan. Gunakan PDF, DOCX, XLSX, atau gambar.')
                if file_bukti.size > 10 * 1024 * 1024:
                    raise ValueError('Ukuran berkas melebihi batas maksimal 10 MB.')

            defaults = {
                'nilai_numerator': num,
                'nilai_denominator': den,
                'catatan': catatan_text,
            }
            if file_bukti:
                defaults['bukti_dokumen'] = file_bukti

            obj, created = CatatanIndikator.objects.update_or_create(
                indikator=ind, bulan=bulan, tahun=tahun,
                defaults=defaults
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


# ── 4. Form Tambah & Edit Indikator Mutu ──────────────────────────────────

@login_required
def indikator_tambah(request):
    """Halaman dan action untuk menambahkan Indikator Mutu baru."""
    if not _is_manager(request.user):
        messages.error(request, 'Anda tidak memiliki hak akses menambah Indikator Mutu.')
        return redirect('akreditasi:indikator_dashboard')

    if request.method == 'POST':
        try:
            nama = request.POST['nama_indikator'].strip()
            kode = request.POST['kode_indikator'].strip()
            unit_id = request.POST.get('unit')
            jenis = request.POST.get('jenis', 'IMP_UNIT')
            dimensi = request.POST.get('dimensi_mutu', 'AMAN')
            num = request.POST['numerator'].strip()
            den = request.POST['denominator'].strip()
            target_val = Decimal(request.POST['target_nilai'])
            satuan = request.POST.get('satuan', '%').strip() or '%'
            rencana = request.POST.get('rencana_aksi', '').strip()
            pj = request.POST.get('pj', '').strip()
            ep_id = request.POST.get('ep_terkait') or None
            arah_target = request.POST.get('arah_target', 'MIN')
            ss_id = request.POST.get('sasaran_strategis') or None

            if IndikatorMutu.objects.filter(kode_indikator=kode).exists():
                messages.error(request, f'Kode indikator "{kode}" sudah digunakan.')
                raise ValueError('Kode indikator sudah ada')

            ind = IndikatorMutu.objects.create(
                nama_indikator=nama,
                kode_indikator=kode,
                unit_id=int(unit_id) if unit_id else None,
                jenis=jenis,
                dimensi_mutu=dimensi,
                numerator=num,
                denominator=den,
                target_nilai=target_val,
                satuan=satuan,
                ep_terkait_id=int(ep_id) if ep_id else None,
                rencana_aksi=rencana,
                pj=pj,
                aktif=True,
                arah_target=arah_target,
                sasaran_strategis_id=int(ss_id) if ss_id else None,
            )
            _log(request.user, 'CREATE', ind, f'Membuat indikator mutu {kode}: {nama}')
            messages.success(request, f'Indikator Mutu [{kode}] berhasil dibuat.')
            return redirect('akreditasi:indikator_detail', indikator_id=ind.pk)
        except Exception as e:
            if 'Kode indikator sudah ada' not in str(e):
                messages.error(request, f'Gagal membuat indikator: {e}')

    units = UnitKerja.objects.filter(is_active=True).order_by('name')
    ep_list = StandardItem.objects.select_related('category').order_by('category__code', 'code')[:200]
    from .risiko_models import RenstraRoadmap as _RR
    renstra_list = _RR.objects.filter(aktif=True).order_by('tahun')
    ctx = {
        'ind': None,
        'is_edit': False,
        'units': units,
        'ep_list': ep_list,
        'renstra_list': renstra_list,
        'jenis_choices': IndikatorMutu.JENIS_CHOICES,
        'dimensi_choices': IndikatorMutu.DIMENSI_CHOICES,
        'arah_choices': IndikatorMutu.ARAH_CHOICES,
    }
    return render(request, 'akreditasi/indikator_form.html', ctx)


@login_required
def indikator_edit(request, indikator_id):
    """Halaman dan action untuk mengedit Indikator Mutu eksisting."""
    if not _is_manager(request.user):
        messages.error(request, 'Anda tidak memiliki hak akses mengubah Indikator Mutu.')
        return redirect('akreditasi:indikator_dashboard')

    ind = get_object_or_404(IndikatorMutu, pk=indikator_id)

    if request.method == 'POST':
        try:
            nama = request.POST['nama_indikator'].strip()
            kode = request.POST['kode_indikator'].strip()
            unit_id = request.POST.get('unit')
            jenis = request.POST.get('jenis', 'IMP_UNIT')
            dimensi = request.POST.get('dimensi_mutu', 'AMAN')
            num = request.POST['numerator'].strip()
            den = request.POST['denominator'].strip()
            target_val = Decimal(request.POST['target_nilai'])
            satuan = request.POST.get('satuan', '%').strip() or '%'
            rencana = request.POST.get('rencana_aksi', '').strip()
            pj = request.POST.get('pj', '').strip()
            ep_id = request.POST.get('ep_terkait') or None
            arah_target = request.POST.get('arah_target', 'MIN')
            ss_id = request.POST.get('sasaran_strategis') or None

            # Check unique kode if changed
            if kode != ind.kode_indikator and IndikatorMutu.objects.filter(kode_indikator=kode).exists():
                messages.error(request, f'Kode indikator "{kode}" sudah digunakan oleh indikator lain.')
                raise ValueError('Kode indikator sudah ada')

            ind.nama_indikator = nama
            ind.kode_indikator = kode
            ind.unit_id = int(unit_id) if unit_id else None
            ind.jenis = jenis
            ind.dimensi_mutu = dimensi
            ind.numerator = num
            ind.denominator = den
            ind.target_nilai = target_val
            ind.satuan = satuan
            ind.ep_terkait_id = int(ep_id) if ep_id else None
            ind.rencana_aksi = rencana
            ind.pj = pj
            ind.arah_target = arah_target
            ind.sasaran_strategis_id = int(ss_id) if ss_id else None
            ind.save()

            _log(request.user, 'UPDATE', ind, f'Mengedit indikator mutu {kode}: {nama}')
            messages.success(request, f'Indikator Mutu [{kode}] berhasil diperbarui.')
            return redirect('akreditasi:indikator_detail', indikator_id=ind.pk)
        except Exception as e:
            if 'Kode indikator sudah ada' not in str(e):
                messages.error(request, f'Gagal menyimpan perubahan: {e}')

    units = UnitKerja.objects.filter(is_active=True).order_by('name')
    ep_list = StandardItem.objects.select_related('category').order_by('category__code', 'code')[:200]
    from .risiko_models import RenstraRoadmap as _RR2
    renstra_list = _RR2.objects.filter(aktif=True).order_by('tahun')
    ctx = {
        'ind': ind,
        'is_edit': True,
        'units': units,
        'ep_list': ep_list,
        'renstra_list': renstra_list,
        'jenis_choices': IndikatorMutu.JENIS_CHOICES,
        'dimensi_choices': IndikatorMutu.DIMENSI_CHOICES,
        'arah_choices': IndikatorMutu.ARAH_CHOICES,
    }
    return render(request, 'akreditasi/indikator_form.html', ctx)


# ── API JSON Endpoints: Trend & Unit Comparison Charts ──────────────────────

@login_required
def api_indikator_tren(request, indikator_id):
    """Monthly trend data for a single indicator — 12 months of a given year."""
    ind = get_object_or_404(IndikatorMutu, pk=indikator_id)
    tahun = int(request.GET.get('tahun', 2026))
    catatan = CatatanIndikator.objects.filter(
        indikator=ind, tahun=tahun
    ).order_by('bulan')

    data = [None] * 12
    for c in catatan:
        data[c.bulan - 1] = float(c.nilai_capaian)

    arah = getattr(ind, 'arah_target', 'MIN')
    return JsonResponse({
        'kode': ind.kode_indikator,
        'nama': ind.nama_indikator,
        'jenis': ind.jenis_standar,
        'target': float(ind.target_nilai),
        'arah_target': arah,
        'satuan': ind.satuan,
        'tahun': tahun,
        'labels': [f'Bln {i}' for i in range(1, 13)],
        'data': data,
    })


@login_required
def api_indikator_komparasi_unit(request):
    """Cross-unit comparison for a given indicator jenis (INM/IMRS/IMU) and month/year."""
    jenis = request.GET.get('jenis', 'INM')
    bulan = int(request.GET.get('bulan', 1))
    tahun = int(request.GET.get('tahun', 2026))

    # Map legacy jenis codes to canonical
    jenis_map = {'NASIONAL': 'INM', 'IMP_RS': 'IMRS', 'IMP_UNIT': 'IMU'}
    canonical = jenis_map.get(jenis, jenis)
    # Collect all DB jenis codes that map to this canonical
    db_codes = [canonical]
    for k, v in jenis_map.items():
        if v == canonical:
            db_codes.append(k)

    indicators = IndikatorMutu.objects.filter(
        jenis__in=db_codes, aktif=True
    ).select_related('unit')

    results = []
    for ind in indicators:
        cat = CatatanIndikator.objects.filter(
            indikator=ind, bulan=bulan, tahun=tahun
        ).first()
        capaian = float(cat.nilai_capaian) if cat else None
        target = float(ind.target_nilai)
        arah = getattr(ind, 'arah_target', 'MIN')
        if capaian is not None:
            tercapai = capaian <= target if arah == 'MAX' else capaian >= target
        else:
            tercapai = None
        results.append({
            'indikator_id': ind.pk,
            'kode': ind.kode_indikator,
            'nama': ind.nama_indikator,
            'unit': ind.unit.name if ind.unit else 'Hospital-wide',
            'unit_id': ind.unit_id,
            'target': target,
            'capaian': capaian,
            'tercapai': tercapai,
            'arah_target': arah,
        })
    return JsonResponse({'jenis': canonical, 'bulan': bulan, 'tahun': tahun, 'items': results})

