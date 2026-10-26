"""Gap analysis and risk classification (F-A3).

The four-colour risk model from the source document is a management signal, so
it must never be guessed. Two rules govern this module:

* A threshold that is not configured yields ``BELUM_DIKONFIGURASI``. Falling
  back to a hardcoded 80/95 would silently colour an unconfigured hospital
  green on one dataset and red on another.
* The thresholds in force at approval are copied onto the immutable
  :class:`~sdm.models.HasilFormasi`, so a report printed next year reproduces
  the colour that was actually approved.
"""

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from sdm.models import HasilFormasi, StandarKetenagaan

# Labels used by StandarKetenagaan rows of jenis=AMBANG_RISIKO.
NAMA_AMBANG_MARGINAL = 'Ambang Ketercukupan Marginal'
NAMA_AMBANG_KRITIS = 'Ambang Defisit Kritis'

RISIKO_KRITIS = 'DEFISIT_KRITIS'
RISIKO_MARGINAL = 'MARGINAL'
RISIKO_IDEAL = 'IDEAL'
RISIKO_SURPLUS = 'SURPLUS'
RISIKO_UNCONFIGURED = 'BELUM_DIKONFIGURASI'

RISIKO_LABELS = {
    RISIKO_KRITIS: 'Defisit Kritis',
    RISIKO_MARGINAL: 'Ketercukupan Marginal',
    RISIKO_IDEAL: 'Ideal',
    RISIKO_SURPLUS: 'Surplus',
    RISIKO_UNCONFIGURED: 'Belum Dikonfigurasi',
}

# Bootstrap badge classes, kept here so a template never invents a colour.
RISIKO_BADGES = {
    RISIKO_KRITIS: 'text-bg-danger',
    RISIKO_MARGINAL: 'text-bg-warning',
    RISIKO_IDEAL: 'text-bg-success',
    RISIKO_SURPLUS: 'text-bg-info text-dark',
    RISIKO_UNCONFIGURED: 'text-bg-light text-dark border',
}

RISIKO_ICONS = {
    RISIKO_KRITIS: '🔴',
    RISIKO_MARGINAL: '🟡',
    RISIKO_IDEAL: '🟢',
    RISIKO_SURPLUS: '🔵',
    RISIKO_UNCONFIGURED: '⚪',
}


def classify_risiko(sufficiency_pct, *, ambang_marginal, ambang_kritis):
    """Return the risk band for a sufficiency percentage.

    ``suff`` = actual FTE / required FTE x 100.
    """
    if sufficiency_pct is None or ambang_marginal is None or ambang_kritis is None:
        return RISIKO_UNCONFIGURED
    suff = Decimal(sufficiency_pct)
    if suff > Decimal('100.00'):
        return RISIKO_SURPLUS
    if suff >= Decimal(ambang_marginal):
        return RISIKO_IDEAL
    if suff >= Decimal(ambang_kritis):
        return RISIKO_MARGINAL
    return RISIKO_KRITIS


def _pick_ambang(unit_kerja, profesi, nama, *, as_of):
    """Resolve one threshold: unit-specific first, then hospital-wide."""
    base = StandarKetenagaan.objects.filter(
        jenis='AMBANG_RISIKO',
        nama=nama,
        profesi__iexact=profesi,
        is_active=True,
        berlaku_mulai__lte=as_of,
    ).filter(Q(berlaku_sampai__isnull=True) | Q(berlaku_sampai__gte=as_of))

    unit_id = getattr(unit_kerja, 'pk', unit_kerja)
    specific = base.filter(unit_kerja_id=unit_id).order_by('-berlaku_mulai').first()
    if specific is not None:
        return specific.nilai
    hospital = base.filter(unit_kerja__isnull=True).order_by('-berlaku_mulai').first()
    return hospital.nilai if hospital is not None else None


def resolve_ambang_risiko(unit_kerja, profesi, *, as_of=None):
    """Return ``(ambang_marginal, ambang_kritis)`` or ``None`` when incomplete.

    Returning ``None`` rather than a partial pair forces callers to render
    ``Belum dikonfigurasi`` instead of half a rule.
    """
    as_of = as_of or timezone.localdate()
    marginal = _pick_ambang(
        unit_kerja, profesi, NAMA_AMBANG_MARGINAL, as_of=as_of
    )
    kritis = _pick_ambang(
        unit_kerja, profesi, NAMA_AMBANG_KRITIS, as_of=as_of
    )
    if marginal is None or kritis is None:
        return None
    return (marginal, kritis)


def gap_rows(user, *, unit=None, profesi='', hanya_defisit=False, as_of=None):
    """Build the gap map rows visible to ``user``.

    One query set with ``select_related``; the caller renders it without
    touching the database again, so the page cost does not grow with the
    number of plans.
    """
    from sdm.akses import visible_units

    units = visible_units(user, capability='can_plan_hc_workforce')
    queryset = (
        HasilFormasi.objects
        .filter(rencana__status='APPROVED', rencana__unit_kerja__in=units)
        .select_related('rencana', 'rencana__unit_kerja')
        .order_by('rencana__unit_kerja__code', 'rencana__profesi')
    )
    if unit is not None:
        queryset = queryset.filter(rencana__unit_kerja=unit)
    if profesi:
        queryset = queryset.filter(rencana__profesi__iexact=profesi)

    rows = []
    for hasil in queryset:
        plan = hasil.rencana
        risiko = hasil.status_risiko or RISIKO_UNCONFIGURED
        if hanya_defisit and risiko not in (RISIKO_KRITIS, RISIKO_MARGINAL):
            continue
        rows.append({
            'hasil': hasil,
            'rencana': plan,
            'unit': plan.unit_kerja,
            'profesi': plan.profesi,
            'periode': (plan.periode_mulai, plan.periode_selesai),
            'required_fte': hasil.required_fte,
            'required_headcount': hasil.required_headcount,
            'actual_fte': hasil.actual_fte,
            'gap_fte': hasil.gap_fte,
            'sufficiency_pct': hasil.sufficiency_pct,
            'risiko': risiko,
            'risiko_label': RISIKO_LABELS.get(risiko, risiko),
            'risiko_badge': RISIKO_BADGES.get(risiko, RISIKO_BADGES[RISIKO_UNCONFIGURED]),
            'risiko_icon': RISIKO_ICONS.get(risiko, RISIKO_ICONS[RISIKO_UNCONFIGURED]),
            'buat_usulan_url': _usulan_query(plan, hasil),
        })
    return rows


def _usulan_query(plan, hasil):
    """Query string that pre-fills the submission form from a deficit row."""
    from urllib.parse import urlencode

    params = {
        'unit': plan.unit_kerja_id,
        'profesi': plan.profesi,
        'jumlah': max(hasil.required_headcount - 0, 1),
    }
    return '?' + urlencode(params)


def gap_totals(rows):
    """Sum only what is displayed, so the footer never contradicts the table."""
    return {
        'jumlah_baris': len(rows),
        'required_fte': sum((r['required_fte'] for r in rows), Decimal('0.0000')),
        'actual_fte': sum((r['actual_fte'] for r in rows), Decimal('0.0000')),
        'gap_fte': sum((r['gap_fte'] for r in rows), Decimal('0.0000')),
        'jumlah_kritis': sum(1 for r in rows if r['risiko'] == RISIKO_KRITIS),
        'jumlah_marginal': sum(1 for r in rows if r['risiko'] == RISIKO_MARGINAL),
        'jumlah_surplus': sum(1 for r in rows if r['risiko'] == RISIKO_SURPLUS),
    }
