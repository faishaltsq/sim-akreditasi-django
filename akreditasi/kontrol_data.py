"""
Snapshot builder untuk dasbor eksekutif "ARIMA HOSPITAL INTEGRATED CONTROL".

Modul ini murni pembacaan: tidak menulis, tidak menyimpan, tidak memanggil AI.
Setiap angka berasal dari tabel yang sudah ada — tidak ada nilai karangan.

Kunci snapshot (nilai ``None`` berarti "belum ada data", bukan nol):

risk.total / by_level       RisikoUnit (dampak x probabilitas, ambang SystemConfig)
risk.overdue_rtl            TindakLanjutRisiko (status_aksi != SELESAI, tanggal_selesai lewat)
incident.total_12m / by_grade / open
                            InsidenKeselamatan (tingkat_keparahan, status_investigasi)
indicator.total / on_target / below_target / avg_pct
                            IndikatorMutu + CatatanIndikator (field ``tercapai``)
laporan.pending             LaporanMutu (status DRAF / DIVERIFIKASI)
emr.active_by_jenis / cppt_gap / assessment_gap / bed_occupancy_pct
                            pasien.KunjunganPasien, CPPT, AsesmenRisikoKlinis, Bed
ppa.total / compliant       accounts.NakesCredential (VERIFIED + belum kedaluwarsa)
ep.total / filled / without_evidence / evidence_review
                            StandardItem, QualityRecord, EvidenceReq, EvidenceFile
"""
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q

from .models import EvidenceFile, EvidenceReq, QualityRecord, StandardItem
from .risiko_models import (
    CatatanIndikator, IndikatorMutu, InsidenKeselamatan, LaporanMutu,
    RisikoUnit, TindakLanjutRisiko,
)

LEVEL_ORDER = ('SANGAT_TINGGI', 'TINGGI', 'SEDANG', 'RENDAH', 'SANGAT_RENDAH')
ACTIVE_VISIT_STATUSES = ('DAFTAR', 'TRIAGE', 'ASESMEN', 'RANAP')
OPEN_INCIDENT_STATUSES = ('DILAPORKAN', 'VERIFIKASI', 'INVESTIGASI')

SNAPSHOT_CACHE_SECONDS = 60
SNAPSHOT_CACHE_VERSION = 'v1'


def risk_level_for(score, cfg):
    """Ambang sama persis dengan ``RisikoUnit.risk_level`` — jangan duplikasi nilai."""
    if score >= cfg.risk_threshold_sangat_tinggi:
        return 'SANGAT_TINGGI'
    if score >= cfg.risk_threshold_tinggi:
        return 'TINGGI'
    if score >= cfg.risk_threshold_sedang:
        return 'SEDANG'
    if score >= cfg.risk_threshold_rendah:
        return 'RENDAH'
    return 'SANGAT_RENDAH'


def status_band(pct):
    """Tiga pita warna tunggal untuk semua kartu. ``None`` = belum ada data."""
    if pct is None:
        return None
    if pct >= 90:
        return 'good'
    if pct >= 70:
        return 'watch'
    return 'critical'


def _ratio(part, total):
    if not total:
        return None
    return round(part * 100.0 / total, 1)


def _unit_ids(unit, profile=None):
    """Unit + turunannya, dibatasi scope bila profil unit-scoped."""
    from .akses_indikator import unit_scope_ids
    ids = unit_scope_ids(unit)
    if profile is not None and getattr(profile, 'is_unit_scoped', False):
        allowed = set(unit_scope_ids(profile.unit_kerja)) if profile.unit_kerja else set()
        ids = [i for i in ids if i in allowed]
    return ids


def _risk_block(unit_ids):
    from .system_models import SystemConfig
    cfg = SystemConfig.get_solo()
    rows = list(
        RisikoUnit.objects.filter(unit_id__in=unit_ids)
        .values_list('dampak', 'probabilitas')
    )
    by_level = {lvl: 0 for lvl in LEVEL_ORDER}
    for dampak, probabilitas in rows:
        by_level[risk_level_for((dampak or 1) * (probabilitas or 1), cfg)] += 1

    overdue = TindakLanjutRisiko.objects.filter(
        risiko__unit_id__in=unit_ids,
        status_aksi__in=('BELUM', 'SEDANG'),
        tanggal_selesai__lt=date.today(),
    ).count()

    return {
        'total': len(rows) or None,
        'by_level': by_level,
        'high_count': by_level['SANGAT_TINGGI'] + by_level['TINGGI'],
        'overdue_rtl': overdue,
        'matrix': _risk_matrix(rows, cfg),
    }


def _risk_matrix(rows, cfg):
    """Grid 5x5 dampak x probabilitas, tiap sel sudah berlabel level risiko."""
    grid = [[0] * 5 for _ in range(5)]
    for dampak, probabilitas in rows:
        d = min(max(int(dampak or 1), 1), 5)
        p = min(max(int(probabilitas or 1), 1), 5)
        grid[d - 1][p - 1] += 1

    matrix = []
    for d in range(5, 0, -1):
        row = []
        for p in range(1, 6):
            row.append({
                'dampak': d,
                'probabilitas': p,
                'count': grid[d - 1][p - 1],
                'level': risk_level_for(d * p, cfg),
            })
        matrix.append(row)
    return matrix


def _incident_block(unit_ids):
    since = date.today() - timedelta(days=365)
    qs = InsidenKeselamatan.objects.filter(
        unit_id__in=unit_ids, tanggal_kejadian__gte=since)
    by_grade = {
        row['tingkat_keparahan']: row['n']
        for row in qs.values('tingkat_keparahan').annotate(n=Count('id'))
    }
    open_count = qs.filter(status_investigasi__in=OPEN_INCIDENT_STATUSES).count()
    total = sum(by_grade.values())
    return {
        'total_12m': total,
        'by_grade': by_grade,
        'open': open_count,
        'rca_done': qs.filter(rca_dilakukan=True).count(),
    }


def _indicator_block(unit_ids, year, profile=None):
    ind_qs = IndikatorMutu.objects.filter(aktif=True)
    if unit_ids:
        ind_qs = ind_qs.filter(Q(unit_id__in=unit_ids) | Q(unit_id__isnull=True))
    cat = CatatanIndikator.objects.filter(indikator__in=ind_qs, tahun=year)
    total_cat = cat.count()
    if not total_cat:
        return {'total': ind_qs.count() or None, 'on_target': None,
                'below_target': None, 'avg_pct': None, 'catatan_total': 0}

    # `tercapai` adalah @property pada model, bukan kolom DB: evaluasi di Python.
    rows = cat.select_related('indikator').only(
        'nilai_numerator', 'nilai_denominator',
        'indikator__target_nilai', 'indikator__arah_target',
    )
    on_target = sum(1 for row in rows if row.tercapai)
    avg_raw = (
        cat.filter(nilai_denominator__gt=0)
        .annotate(pct=ExpressionWrapper(
            F('nilai_numerator') * 100.0 / F('nilai_denominator'),
            output_field=FloatField()))
        .aggregate(a=Avg('pct'))['a']
    )
    return {
        'total': ind_qs.count(),
        'on_target': on_target,
        'below_target': total_cat - on_target,
        'avg_pct': round(avg_raw, 1) if avg_raw is not None else None,
        'catatan_total': total_cat,
    }


def _laporan_block(unit_ids):
    qs = LaporanMutu.objects.all()
    if unit_ids:
        qs = qs.filter(unit_id__in=unit_ids)
    return {
        'pending': qs.filter(status__in=('DRAF', 'DIVERIFIKASI')).count(),
        'published': qs.filter(status='TERBIT').count(),
        'total': qs.count() or None,
    }


def _emr_block(unit_ids):
    from accounts.models import UserProfile
    from pasien.models import AsesmenRisikoKlinis, Bed, CPPT, KunjunganPasien

    visits = KunjunganPasien.objects.filter(status__in=ACTIVE_VISIT_STATUSES)
    if unit_ids:
        names = list(
            UserProfile.objects.filter(unit_kerja_id__in=unit_ids)
            .values_list('unit_kerja__name', flat=True).distinct()
        )
        names = [n for n in names if n]
        if names:
            visits = visits.filter(Q(poliklinik__in=names) | Q(bed__ruangan__nama__in=names))

    by_jenis = {
        row['jenis_kunjungan']: row['n']
        for row in visits.values('jenis_kunjungan').annotate(n=Count('id'))
    }
    total_active = sum(by_jenis.values())
    if not total_active:
        # Bentuk dict harus sama dengan cabang normal: pemanggil (mis.
        # _kontrol_data_block) membaca key yang sama, dan KeyError di sini
        # menjatuhkan seluruh endpoint ringkasan AI.
        return {'active_by_jenis': by_jenis, 'active_total': 0, 'cppt_gap': None,
                'assessment_gap': None, 'bed_occupancy_pct': None,
                'bed_scope': 'hospital', 'bed_total': None,
                'cppt_total': None, 'assessment_total': None}

    annotated = visits.annotate(
        n_cppt=Count('cppt', distinct=True),
        n_asesmen=Count('asesmen_risiko', distinct=True),
    ).values_list('id', 'n_cppt', 'n_asesmen')
    rows = list(annotated)
    cppt_gap = sum(1 for _, n_cppt, _ in rows if not n_cppt)
    assessment_gap = sum(1 for _, _, n_asesmen in rows if not n_asesmen)

    beds = Bed.objects.exclude(status='TIDAK_AKTIF')
    occupied = beds.filter(status='TERISI').count()
    bed_total = beds.count()

    return {
        'active_by_jenis': by_jenis,
        'active_total': total_active,
        'cppt_gap': cppt_gap,
        'assessment_gap': assessment_gap,
        'cppt_total': CPPT.objects.filter(kunjungan__in=visits).count(),
        'assessment_total': AsesmenRisikoKlinis.objects.filter(kunjungan__in=visits).count(),
        # Bed tidak punya FK ke UnitKerja — angka ini selalu RS-wide, jangan
        # dibaca sebagai okupansi unit.
        'bed_occupancy_pct': _ratio(occupied, bed_total),
        'bed_scope': 'hospital',
        'bed_total': bed_total or None,
    }


def _ppa_block(unit_ids):
    from accounts.models import NakesCredential

    qs = NakesCredential.objects.all()
    if unit_ids:
        qs = qs.filter(user_profile__unit_kerja_id__in=unit_ids)
    total = qs.count()
    if not total:
        return {'total': None, 'compliant': None, 'pct': None}
    compliant = qs.filter(
        Q(status='VERIFIED') & (Q(valid_until__isnull=True) | Q(valid_until__gte=date.today()))
    ).count()
    return {'total': total, 'compliant': compliant, 'pct': _ratio(compliant, total)}


def _ep_block(unit_ids):
    """Cakupan EP selalu RS-wide: ``StandardItem`` tidak punya FK unit.

    Untuk unit, yang bisa dihitung hanyalah berapa item yang sudah punya
    ``QualityRecord`` berisi skor di unit itu.
    """
    ep_qs = StandardItem.objects.all()
    total = ep_qs.count()

    hospital_filled = (
        QualityRecord.objects.filter(score__gt=0)
        .values('standard_item_id').distinct().count()
    )

    unit_record_qs = QualityRecord.objects.filter(score__gt=0)
    if unit_ids:
        unit_record_qs = unit_record_qs.filter(unit_id__in=unit_ids)
    unit_filled = unit_record_qs.values('standard_item_id').distinct().count()

    files = EvidenceFile.objects.all()
    if unit_ids:
        files = files.filter(requirement__standard_item__record__unit_id__in=unit_ids)

    return {
        'total': total or None,
        'filled': hospital_filled,
        # Belum ada satu pun item berskor = belum ada data, bukan 0%.
        'pct': _ratio(hospital_filled, total) if hospital_filled else None,
        'unit_filled': unit_filled,
        'scope': 'hospital',
        'without_evidence': None,
        'evidence_total': files.count(),
        'evidence_review': files.filter(status='REVIEW').count(),
        'expiring': None,
    }


def build_unit_snapshot(unit, profile=None, year=None):
    """Bangun snapshot lengkap satu unit. Tidak di-cache di sini."""
    year = year or date.today().year
    unit_ids = _unit_ids(unit, profile)
    snapshot = {
        'unit': {
            'id': unit.id,
            'name': unit.name,
            'code': unit.code,
            'tipe': unit.get_tipe_unit_display() if hasattr(unit, 'get_tipe_unit_display') else '',
        } if unit else None,
        'year': year,
        'risk': _risk_block(unit_ids),
        'incident': _incident_block(unit_ids),
        'indicator': _indicator_block(unit_ids, year, profile),
        'laporan': _laporan_block(unit_ids),
        'emr': _emr_block(unit_ids),
        'ppa': _ppa_block(unit_ids),
        'ep': _ep_block(unit_ids),
    }
    snapshot['safety_proxy'] = safety_proxy(snapshot)
    return snapshot


def safety_proxy(snapshot):
    """Dua angka proxy budaya safety — BUKAN skor survei, dan tidak digabung.

    ``rtl_completion``  : 100 dikurangi persentase RTL lewat tenggat dari RTL
                          pada risiko tinggi/sangat tinggi. ``None`` bila tidak
                          ada RTL berjalan.
    ``reporting_rate``  : insiden dilaporkan per 100 risiko terdaftar, dibatasi
                          100. ``None`` bila belum ada risiko terdaftar.

    Sengaja tidak dirata-ratakan: unit tanpa insiden dan unit tanpa RTL
    berjalan adalah dua keadaan berbeda, bukan satu skor.
    """
    risk_total = snapshot['risk'].get('total') or 0
    incident_total = snapshot['incident'].get('total_12m') or 0
    overdue = snapshot['risk'].get('overdue_rtl') or 0
    high = snapshot['risk'].get('high_count') or 0

    reporting_rate = (
        min(round(incident_total * 100.0 / risk_total, 1), 100.0)
        if risk_total else None
    )
    rtl_completion = (
        max(0.0, round(100.0 - (overdue * 100.0 / high), 1))
        if high else None
    )
    return {
        'rtl_completion': rtl_completion,
        'reporting_rate': reporting_rate,
    }


def snapshot_cached(unit, profile=None, year=None):
    """Snapshot dengan cache 60 detik, kunci dibatasi scope pengguna."""
    if not unit:
        return None
    scope = 'all'
    if profile is not None and getattr(profile, 'is_unit_scoped', False):
        scope = f'unit{getattr(profile, "unit_kerja_id", 0) or 0}'
    key = f'kontrol:{SNAPSHOT_CACHE_VERSION}:{unit.id}:{scope}:{year or date.today().year}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    snapshot = build_unit_snapshot(unit, profile=profile, year=year)
    cache.set(key, snapshot, SNAPSHOT_CACHE_SECONDS)
    return snapshot


def sample_units(max_items=12):
    """'Unit Contoh' = unit aktif yang sudah punya data risiko / indikator / EP."""
    from .models import UnitKerja

    key = f'kontrol:units:v1:{max_items}'
    pks = cache.get(key)
    if pks is None:
        risk_units = set(RisikoUnit.objects.values_list('unit_id', flat=True))
        ind_units = set(IndikatorMutu.objects.values_list('unit_id', flat=True))
        ep_units = set(QualityRecord.objects.values_list('unit_id', flat=True))
        populated = risk_units | ind_units | ep_units

        units = list(
            UnitKerja.objects.filter(is_active=True).order_by('level', 'order', 'code')
        )
        with_data = [u for u in units if u.id in populated][:max_items]
        pks = [u.pk for u in (with_data or units[:max_items])]
        cache.set(key, pks, SNAPSHOT_CACHE_SECONDS)

    if not pks:
        return []
    by_pk = {u.pk: u for u in UnitKerja.objects.filter(pk__in=pks)}
    return [by_pk[pk] for pk in pks if pk in by_pk]
