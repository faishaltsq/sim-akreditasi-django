"""
Views Indikator Mutu — INM Kemenkes + IMP-RS per Bidang Kerja
"""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Q, Sum, Exists, OuterRef
from django.http import JsonResponse

from .risiko_models import IndikatorMutu, CatatanIndikator, InmUnitMapping
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
    """SUPER_ADMIN, ADMIN_RS, KOORDINATOR_POKJA, KEPALA_UNIT."""
    if user.is_superuser:
        return True
    p = getattr(user, 'profile', None)
    return p and p.role in ('SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA', 'KEPALA_UNIT')


def _ai_status_kartu():
    """Status AI untuk kartu Sinkronisasi EP di form indikator.

    Dipakai template supaya operator tahu AI aktif/nonaktif SEBELUM menekan
    tombol — kalau tidak, hasil Tier B (kecocokan kata) terbaca sebagai AI.
    """
    try:
        from .ai_views import _ai_status
        return _ai_status()
    except Exception:            # konfigurasi rusak tidak boleh merontokkan form
        return None


# ── Resolusi cakupan unit untuk peta distribusi INM ──────────────────────────

INM_JENIS = ('INM', 'NASIONAL')


def unit_subtree_ids(unit):
    """Semua id unit: dirinya sendiri + seluruh turunan (kedalaman berapa pun).

    Ditelusuri lewat UnitKerja.parent. Pohon unit RS tidak seragam — ada
    'Instalasi Rawat Inap' yang muncul sebagai IRIN (lvl 2) sekaligus RANAP
    (lvl 3, induknya BID-YAN), dan unit lvl 4–5 tidak terjangkau query
    kedalaman-2 yang lama.
    """
    ids = {unit.pk}
    frontier = [unit.pk]
    while frontier:
        children = list(
            UnitKerja.objects.filter(parent_id__in=frontier).values_list('pk', flat=True)
        )
        new = [c for c in children if c not in ids]
        ids.update(new)
        frontier = new
    return ids


def unit_ancestor_ids(unit):
    """Id unit itu sendiri + seluruh leluhurnya sampai akar."""
    ids = []
    node = unit
    seen = set()
    while node is not None and node.pk not in seen:
        seen.add(node.pk)
        ids.append(node.pk)
        node = node.parent
    return ids


def _mapping_scope_q(profile):
    """Q untuk InmUnitMapping yang berlaku bagi user ini.

    Pemetaan dipasang pada unit induk (mis. 'IRIN' = seluruh rawat inap), jadi
    yang dicocokkan adalah leluhur unit user — bukan turunannya. Unit anak
    otomatis mewarisi peta induknya; unit induk tidak ikut memiliki peta anak.
    """
    q = Q(unit_id__in=unit_ancestor_ids(profile.unit_kerja))
    role = getattr(profile, 'role', '') or ''
    if role:
        q |= Q(role_scope=role)
    return q


def inm_qs_for_user(profile, qs=None):
    """Indikator yang boleh dilihat user ini.

    Urutan keputusan:
    1. Tidak ada profile / tidak unit-scoped → tidak dibatasi.
    2. Tabel peta distribusi masih KOSONG → tidak dibatasi. Ini guard roll-out:
       saat ini produksi belum punya satu baris pun; kalau kosong dianggap
       "tidak ada yang boleh lihat", seluruh menu INM hilang begitu deploy.
    3. Selain itu → indikator milik unit/subtree-nya, ditambah INM yang
       dipetakan ke unit atau role-nya. INM yang tidak dipetakan tidak tampil.
    """
    qs = qs if qs is not None else IndikatorMutu.objects.all()
    if profile is None or not profile.is_unit_scoped or not profile.unit_kerja:
        return qs

    if not InmUnitMapping.objects.exists():
        return qs

    unit_ids = unit_subtree_ids(profile.unit_kerja)
    mapped_ids = list(
        InmUnitMapping.objects.filter(_mapping_scope_q(profile))
        .values_list('indikator_id', flat=True)
    )
    return qs.filter(Q(unit_id__in=unit_ids) | Q(pk__in=mapped_ids))


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

    # Lingkup = GABUNGAN dua sumber, bukan irisan:
    #   1. indikator_aktif_scoped() — indikator milik unit/subtree-nya.
    #   2. inm_qs_for_user()        — INM yang dipetakan ke unit/role-nya.
    # INM nasional ber-unit NULL sengaja dikecualikan oleh (1), jadi mengiris
    # keduanya akan menghapus justru INM yang dipetakan (regresi DashboardTest).
    # Memakai Q(jenis='NASIONAL') sendirian juga salah: seluruh INM bocor.
    from .akses_indikator import indikator_aktif_scoped
    profile = getattr(request.user, 'profile', None)
    _scoped = indikator_aktif_scoped(profile)
    if profile is None or not getattr(profile, 'is_unit_scoped', False):
        qs = _scoped
    elif InmUnitMapping.objects.exists():
        # Peta distribusi sudah diisi: INM yang dipetakan ikut terlihat walau
        # unit-nya NULL (INM nasional). Selama tabel masih kosong, guard
        # roll-out inm_qs_for_user mengembalikan semuanya — memakainya di sini
        # akan membocorkan seluruh INM ke setiap unit.
        _mapped = inm_qs_for_user(profile, IndikatorMutu.objects.filter(aktif=True))
        qs = (IndikatorMutu.objects.filter(aktif=True)
              .filter(Q(pk__in=_scoped.values('pk')) | Q(pk__in=_mapped.values('pk'))))
    else:
        qs = _scoped
    qs = qs.select_related('unit', 'ep_terkait')

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

    # Lingkup sudah diterapkan oleh indikator_aktif_scoped() di atas; jalur
    # peta distribusi INM tidak dipakai lagi di sini agar tidak dobel filter.

    # Katalog INM hanya memuat INM kanonik. Baris realisasi per-unit
    # (BAB-*-INM-*) tetap dipakai untuk capaian unit, tapi tidak lagi muncul
    # sebagai entri sendiri — dulu "Kepatuhan Kebersihan Tangan" tampil 8x.
    qs = qs.exclude(jenis__in=INM_JENIS, inm_induk__isnull=False)

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
        if ind.jenis in INM_JENIS and ind.inm_induk_id is None:
            inm_list.append(ind)
        elif ind.is_renstra_focus:
            fokus_renstra_list.append(ind)
        else:
            imp_rs_other_list.append(ind)

    # Realisasi per-unit: bila unit user punya baris sendiri untuk INM tersebut,
    # yang ditampilkan adalah angka unit itu — bukan agregat RS.
    _unit_ids = (
        unit_subtree_ids(profile.unit_kerja)
        if (profile and profile.is_unit_scoped and profile.unit_kerja) else set()
    )
    for ind in inm_list:
        ind.unit_row = None
    if _unit_ids and inm_list:
        _rows = (
            IndikatorMutu.objects.filter(
                inm_induk_id__in=[i.pk for i in inm_list],
                unit_id__in=_unit_ids,
                aktif=True,
            )
            .select_related('unit')
            .prefetch_related(Prefetch(
                'catatan',
                queryset=CatatanIndikator.objects.filter(tahun=tahun_int).order_by('-bulan'),
                to_attr='ct',
            ))
            .order_by('unit_id')
        )
        _by_inm = {}
        for _r in _rows:
            _by_inm[_r.inm_induk_id] = _r
        for ind in inm_list:
            row = _by_inm.get(ind.pk)
            if not row:
                continue
            ind.unit_row = row
            last = row.ct[0] if row.ct else None
            _was = ind.is_tercapai
            ind.last_catatan = last
            ind.is_tercapai = bool(last and last.tercapai)
            if ind.is_tercapai != _was:
                _label = ind.get_jenis_display()
                _inc, _dec = ('tercapai', 'belum') if ind.is_tercapai else ('belum', 'tercapai')
                summary[_label][_inc] += 1
                summary[_label][_dec] -= 1

    units = UnitKerja.objects.filter(level__lte=3).order_by('order', 'name')

    # ── Chart.js: tren capaian bulanan (Jan–Des) ────────────────
    import json as _json
    from decimal import Decimal as _Dec
    BULAN_LABELS = ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des']

    # Ambil semua catatan indikator untuk tahun ini yang indikatornya masuk filter
    ind_ids = [i.pk for i in indikators_with_stats]
    # Average of per-indicator capaian, one value per indicator per month.
    # Pooling numerators and denominators across indicators mixes units and
    # lets one high-volume indicator decide the whole month's number.
    monthly_samples = {}
    for c in (CatatanIndikator.objects
              .filter(indikator_id__in=ind_ids, tahun=tahun_int)
              .select_related('indikator')):
        if not c.nilai_denominator or c.nilai_denominator <= 0:
            continue
        monthly_samples.setdefault(c.bulan, []).append(float(c.nilai_capaian))

    monthly_avg = {
        m: {'pct': round(sum(v) / len(v), 1), 'count': len(v)}
        for m, v in monthly_samples.items() if v
    }

    chart_labels = _json.dumps(BULAN_LABELS)
    chart_capaian = _json.dumps([monthly_avg.get(m, {}).get('pct', None) for m in range(1, 13)])
    chart_jumlah  = _json.dumps([monthly_avg.get(m, {}).get('count', 0) for m in range(1, 13)])

    # Seri kedua: realisasi unit user sendiri, agar angka unit tidak tenggelam
    # di rata-rata rumah sakit. Kosong untuk user non-unit-scoped.
    chart_unit_label = ''
    chart_unit_capaian = '[]'
    if _unit_ids and ind_ids:
        unit_row_ids = list(
            IndikatorMutu.objects
            .filter(inm_induk_id__in=ind_ids, unit_id__in=_unit_ids, aktif=True)
            .values_list('pk', flat=True)
        )
        if unit_row_ids:
            unit_samples = {}
            for c in (CatatanIndikator.objects
                      .filter(indikator_id__in=unit_row_ids, tahun=tahun_int)
                      .select_related('indikator')):
                if not c.nilai_denominator or c.nilai_denominator <= 0:
                    continue
                unit_samples.setdefault(c.bulan, []).append(float(c.nilai_capaian))
            unit_monthly = {
                m: round(sum(v) / len(v), 1) for m, v in unit_samples.items() if v
            }
            chart_unit_label = profile.unit_kerja.name
            chart_unit_capaian = _json.dumps([unit_monthly.get(m) for m in range(1, 13)])

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

    # ── Grafik per-indikator tunggal (bukan rata-rata semua indikator) ──────
    try:
        indikator_id = int(request.GET.get('indikator') or 0)
    except (ValueError, TypeError):
        indikator_id = 0

    # Semua indikator pada filter tetap ada di dropdown; yang belum diukur tahun
    # ini hanya diberi penanda. Menyembunyikannya membuat unit mengira indikator
    # miliknya belum terdaftar.
    data_ind_ids = set(
        CatatanIndikator.objects.filter(tahun=tahun_int, indikator__in=qs)
        .values_list('indikator_id', flat=True).distinct()
    )
    indikator_choices = list(
        qs.annotate(
            punya_data=Exists(
                CatatanIndikator.objects.filter(indikator=OuterRef('pk'), tahun=tahun_int)
            )
        ).order_by('jenis', 'kode_indikator')
    )
    selected_indikator = next((i for i in indikator_choices if i.pk == indikator_id), None)

    ind_data, ind_colors, ind_meta = [], [], []
    ind_target, ind_arah = 0.0, 'MIN'
    _ep_bukti_total_req = 0
    _ep_bukti_terunggah = 0
    if selected_indikator and selected_indikator.ep_terkait_id:
        _reqs = selected_indikator.ep_terkait.evidence_reqs.prefetch_related('files')
        _ep_bukti_total_req = _reqs.count()
        _ep_bukti_terunggah = sum(1 for r in _reqs if list(r.files.all()))
    if selected_indikator:
        ind_target = round(float(selected_indikator.target_nilai), 1)
        ind_arah = getattr(selected_indikator, 'arah_target', 'MIN')
        ind_cat = {}
        for c in CatatanIndikator.objects.filter(indikator=selected_indikator, tahun=tahun_int):
            if 1 <= c.bulan <= 12:
                ind_cat[c.bulan] = c
        for m in range(1, 13):
            c = ind_cat.get(m)
            v = float(c.nilai_capaian) if c else None
            ind_data.append(v)
            if v is None:
                ind_colors.append('rgba(203, 213, 225, 0.4)')
                ind_meta.append(None)
            else:
                ok = (v <= ind_target) if ind_arah == 'MAX' else (v >= ind_target)
                ind_colors.append('#198754' if ok else '#dc3545')
                # Detail tooltip panjang: formula, teks catatan pengukuran, status
                ind_meta.append({
                    'capaian': v,
                    'num': float(c.nilai_numerator),
                    'den': float(c.nilai_denominator),
                    'catatan': (c.catatan or '').strip(),
                    'tercapai': ok,
                })

    ctx = {
        'indikators': indikators_with_stats,
        'inm_list': inm_list,
        'fokus_renstra_list': fokus_renstra_list,
        'imp_rs_other_list': imp_rs_other_list,
        'current_renstra': current_renstra,
        'renstra_all': _renstra_data,
        'summary': summary,
        'jenis_choices': [
            ('INM',  'INM — Indikator Nasional Mutu'),
            ('IMRS', 'IMRS — Indikator Mutu Rumah Sakit'),
            ('IMU',  'IMU — Indikator Mutu Unit'),
        ],
        'units': units,
        'filter_jenis': jenis,
        'filter_unit': unit_id,
        'filter_tahun': tahun_int,
        'tahun_choices': list(_renstra_data.keys()) if _renstra_data else [2026, 2027, 2028, 2029, 2030],
        'is_manager': _is_manager(request.user),
        'chart_labels': chart_labels,
        'chart_capaian': chart_capaian,
        'chart_unit_label': chart_unit_label,
        'chart_unit_capaian': chart_unit_capaian,
        'chart_jumlah': chart_jumlah,
        'chart_bulan_count_json': _json.dumps(
            {str(m): monthly_avg.get(m, {}).get('count', 0) for m in range(1, 13)}
        ),
        'chart_jenis_json': chart_jenis_json,
        'indikator_choices': indikator_choices,
        'filter_indikator': indikator_id,
        'indikator_terpilih': selected_indikator,
        'has_indikator': bool(selected_indikator),
        # Ringkasan dokumen bukti EP untuk indikator terpilih: berapa kebutuhan
        # pembuktian dan berapa yang sudah punya berkas.
        'ep_bukti_total_req': _ep_bukti_total_req,
        'ep_bukti_terunggah': _ep_bukti_terunggah,
        'chart_indikator_data_json': _json.dumps(ind_data),
        'chart_indikator_colors_json': _json.dumps(ind_colors),
        'chart_indikator_target_json': _json.dumps(ind_target),
        'chart_indikator_target_line_json': _json.dumps([ind_target] * 12),
        'chart_indikator_satuan': (selected_indikator.satuan if selected_indikator else '%'),
        'chart_indikator_arah': ind_arah,
        'chart_indikator_meta_json': _json.dumps(ind_meta),
        'chart_indikator_nama': (selected_indikator.nama_indikator if selected_indikator else ''),
        'chart_indikator_kode': (selected_indikator.kode_indikator if selected_indikator else ''),
        'chart_indikator_dimensi': (selected_indikator.get_dimensi_mutu_display() if selected_indikator else ''),
        'chart_indikator_jumlah': sum(1 for m in ind_meta if m),
        'chart_indikator_num_label': (selected_indikator.numerator if selected_indikator else ''),
        'chart_indikator_den_label': (selected_indikator.denominator if selected_indikator else ''),
        'chart_indikator_pj': (selected_indikator.pj if selected_indikator else ''),
        'chart_indikator_rencana_aksi': (selected_indikator.rencana_aksi if selected_indikator else ''),
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

    # Panel "Dokumen Bukti dari Standar Akreditasi": daftar kebutuhan bukti (EvidenceReq)
    # milik EP yang tertaut, beserta berkas yang sudah diunggah. Tanpa ini template
    # selalu jatuh ke cabang "EP tidak memiliki daftar kebutuhan bukti".
    evidence = []
    evidence_terpenuhi = 0
    evidence_total_file = 0
    if ind.ep_terkait_id:
        reqs = (ind.ep_terkait.evidence_reqs
                .prefetch_related('files')
                .order_by('category_type', 'id'))
        for req in reqs:
            files = list(req.files.all())
            evidence_total_file += len(files)
            if files:
                evidence_terpenuhi += 1
            evidence.append({'req': req, 'files': files})
    evidence_total_req = len(evidence)
    evidence_pct = (round(evidence_terpenuhi * 100 / evidence_total_req)
                    if evidence_total_req else 0)

    ctx = {
        'ind': ind,
        'catatan': catatan,
        'tahun': tahun,
        'chart_labels': _json.dumps(chart_labels),
        'chart_data': _json.dumps(chart_data_raw),
        'target_line': float(ind.target_nilai),
        'is_manager': _is_manager(request.user),
        'evidence': evidence,
        'evidence_total_req': evidence_total_req,
        'evidence_terpenuhi': evidence_terpenuhi,
        'evidence_total_file': evidence_total_file,
        'evidence_pct': evidence_pct,
    }
    return render(request, 'akreditasi/indikator_detail.html', ctx)


# ── 3. Input Capaian Bulanan ─────────────────────────────────────────────

@login_required
def indikator_input_capaian(request, indikator_id):
    if not _is_manager(request.user):
        messages.error(request, 'Akses ditolak.')
        return redirect('akreditasi:indikator_dashboard')

    ind = get_object_or_404(IndikatorMutu.objects.select_related('unit'), pk=indikator_id)

    profile = getattr(request.user, 'profile', None)
    if not inm_qs_for_user(profile, IndikatorMutu.objects.filter(pk=ind.pk)).exists():
        messages.error(request, 'Indikator ini bukan tanggung jawab unit Anda.')
        return redirect('akreditasi:indikator_dashboard')

    # INM kanonik: capaian diisi pada baris realisasi unit, bukan baris RS.
    if (request.method == 'GET' and ind.inm_induk_id is None and ind.jenis in INM_JENIS
            and profile and profile.is_unit_scoped and profile.unit_kerja):
        own = (
            IndikatorMutu.objects.filter(
                inm_induk=ind, unit_id__in=unit_subtree_ids(profile.unit_kerja), aktif=True
            ).order_by('unit_id').first()
        )
        if own and own.pk != ind.pk:
            return redirect('akreditasi:indikator_input_capaian', indikator_id=own.pk)

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
    # Tanpa cap: katalog STARKES punya >500 EP, dan EP yang terpotong tidak akan
    # pernah bisa dipilih manual dari form.
    ep_list = StandardItem.objects.select_related('category').order_by('category__code', 'code')
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
        # Kartu Sinkronisasi EP menampilkan status AI sebelum tombol ditekan.
        'ai_status': _ai_status_kartu(),
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
            # Provenance EP: mengganti EP lewat form = keputusan manusia.
            # Tanpa reset, skor AI lama menempel di link manual dan guard
            # auto-sync berikutnya salah membaca asal tautan.
            ep_baru = int(ep_id) if ep_id else None
            if ep_baru != ind.ep_terkait_id:
                if ep_baru:
                    ind.ep_sumber = 'MANUAL'
                    ind.ep_skor = None
                else:
                    ind.ep_sumber = ''
                    ind.ep_skor = None
            ind.ep_terkait_id = ep_baru
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
    # Tanpa cap: katalog STARKES punya >500 EP, dan EP yang terpotong tidak akan
    # pernah bisa dipilih manual dari form.
    ep_list = StandardItem.objects.select_related('category').order_by('category__code', 'code')
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
        # Kartu Sinkronisasi EP menampilkan status AI sebelum tombol ditekan.
        'ai_status': _ai_status_kartu(),
    }
    return render(request, 'akreditasi/indikator_form.html', ctx)


# ── API JSON Endpoints: Trend & Unit Comparison Charts ──────────────────────

@login_required
def api_indikator_tren(request, indikator_id):
    """Monthly trend data for a single indicator — 12 months of a given year."""
    profile = getattr(request.user, 'profile', None)
    ind = get_object_or_404(inm_qs_for_user(profile, IndikatorMutu.objects.all()), pk=indikator_id)
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

    profile = getattr(request.user, 'profile', None)
    indicators = inm_qs_for_user(
        profile, IndikatorMutu.objects.filter(jenis__in=db_codes, aktif=True)
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



# ── Matriks distribusi INM ↔ unit (khusus manager) ───────────────────────────

@login_required
def indikator_inm_matrix(request):
    """Peta distribusi INM: unit mana melihat/menginput INM mana.

    Hanya manager (SUPER_ADMIN/ADMIN_RS/KOORDINATOR/KEPALA_UNIT/SU) yang boleh
    membuka dan mengubah pemetaan. Setiap perubahan dicatat ke AuditLog.
    """
    from django.core.exceptions import PermissionDenied

    if not _is_manager(request.user):
        raise PermissionDenied('Hanya manager yang boleh mengubah peta distribusi INM.')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        ind = get_object_or_404(IndikatorMutu, pk=request.POST.get('indikator') or 0)

        if action == 'hapus':
            mapping = InmUnitMapping.objects.filter(pk=request.POST.get('mapping') or 0).first()
            if mapping:
                _log(request.user, 'DELETE', mapping,
                     f'Hapus pemetaan {ind.kode_indikator}')
                mapping.delete()
                messages.success(request, f'Pemetaan {ind.kode_indikator} dihapus.')
            else:
                messages.error(request, 'Pemetaan tidak ditemukan.')
            return redirect('akreditasi:indikator_inm_matrix')

        if action in ('tambah', 'pj', 'input'):
            mapping = InmUnitMapping.objects.filter(
                pk=request.POST.get('mapping') or 0
            ).first()
            unit = UnitKerja.objects.filter(pk=request.POST.get('unit') or 0).first()
            role = request.POST.get('role_scope', '') or ''

            if mapping is None:
                if not unit and not role:
                    messages.error(request, 'Pilih unit atau cakupan role.')
                    return redirect('akreditasi:indikator_inm_matrix')
                mapping, _created = InmUnitMapping.objects.get_or_create(
                    indikator=ind, unit=unit, role_scope=role,
                    defaults={'is_pj': request.POST.get('is_pj') == '1'},
                )
            else:
                _created = False

            if action == 'pj':
                mapping.is_pj = not mapping.is_pj
            elif action == 'input':
                mapping.boleh_input = not mapping.boleh_input
            mapping.save()
            _log(request.user, 'CREATE' if _created else 'UPDATE', mapping,
                 f'{action} pemetaan {ind.kode_indikator}')
            messages.success(request, f'Pemetaan {ind.kode_indikator} diperbarui.')
            return redirect('akreditasi:indikator_inm_matrix')

        messages.error(request, 'Aksi tidak dikenali.')
        return redirect('akreditasi:indikator_inm_matrix')

    inms = list(
        IndikatorMutu.objects
        .filter(jenis__in=INM_JENIS, inm_induk__isnull=True, aktif=True)
        .order_by('kode_indikator')
    )
    mappings = (InmUnitMapping.objects
                .select_related('indikator', 'unit')
                .order_by('indikator__kode_indikator', 'unit__order', 'unit__name'))
    by_indicator = {}
    for m in mappings:
        by_indicator.setdefault(m.indikator_id, []).append(m)

    rows = [(ind, by_indicator.get(ind.pk, [])) for ind in inms]
    units = UnitKerja.objects.filter(level__lte=3, is_active=True).order_by('order', 'name')
    unmapped = [ind for ind, maps in rows if not maps]

    return render(request, 'akreditasi/indikator_inm_matrix.html', {
        'rows': rows,
        'units': units,
        'role_choices': InmUnitMapping.ROLE_CHOICES,
        'unmapped': unmapped,
        'total_mapping': mappings.count(),
    })
