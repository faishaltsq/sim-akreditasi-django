"""Permission-scoped dashboard metrics for Arima Human Capital."""
from django.db.models import Count, Q
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_employees, visible_units
from sdm.models import (
    DokumenPegawai,
    Pegawai,
    PenugasanOrientasi,
    RencanaFormasi,
    SesiDiklat,
    VersiDokumen,
)
from sdm.models.pengingat import visible_reminders
from sdm.services.kepatuhan import evaluate_employee_compliance, expiry_bands
from sdm.services.metric_scope import metric_metadata, resolve_metric_population


def _scoped_employees(user, *, unit=None, profesi='', status=''):
    queryset = visible_employees(user, unit=unit)
    if profesi:
        queryset = queryset.filter(profesi__iexact=profesi)
    if status in dict(Pegawai.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    return queryset


def build_hc_dashboard(user, *, filters=None):
    """Return only metrics the caller may see, with explicit unavailable states."""
    filters = filters or {}
    unit = filters.get('unit')
    profesi = (filters.get('profesi') or '').strip()
    status = (filters.get('status') or '').strip()

    require_hc_capability(user, 'can_view_hc', unit=unit)

    today = timezone.localdate()
    scope_units = visible_units(user)
    if unit is not None:
        scope_units = scope_units.filter(pk=getattr(unit, 'pk', unit))

    employees = _scoped_employees(user, unit=unit, profesi=profesi, status=status)
    employee_count = employees.count()
    active_count = employees.filter(status='AKTIF').count()

    expiring = expiry_bands(as_of=today)
    scope_employee_ids = set(employees.values_list('pk', flat=True))
    expiring_in_scope = {
        band: [v for v in items if v.document.employee_id in scope_employee_ids]
        for band, items in expiring.items()
    }

    documents = DokumenPegawai.objects.filter(
        employee_id__in=scope_employee_ids, sensitivity='personnel'
    ).exclude(document_type='HEALTH')

    pending_reviews = VersiDokumen.objects.filter(
        document__in=documents, status='PENDING'
    ).count()

    # Training coverage: annual window (current calendar year) per source policy.
    training_coverage = None
    year_start = today.replace(month=1, day=1)
    training_sessions = SesiDiklat.objects.filter(
        tanggal__gte=year_start, tanggal__lte=today
    ).prefetch_related('participants')
    if scope_employee_ids and training_sessions.exists():
        eligible = len(scope_employee_ids)
        completed = set()
        for session in training_sessions:
            for participant in session.participants.all():
                if participant.status == 'LULUS' and participant.employee_id in scope_employee_ids:
                    completed.add(participant.employee_id)
        if eligible:
            training_coverage = round(len(completed) / eligible * 100, 1)

    overdue_orientation = PenugasanOrientasi.objects.filter(
        unit_kerja__in=scope_units,
        status='BERJALAN',
        tenggat__lt=today,
    ).count()
    if not scope_units.exists():
        overdue_orientation = 0

    # Compliance scope uses all visible employees (honest denominator); unclassified
    # exclusion applies to FTE/staffing production calculations separately.
    population = resolve_metric_population(
        user, unit=unit, as_of=today,
        origin_policy={'exclude_unclassified': False},
    )
    compliance_results = []
    for employee in population:
        summary = evaluate_employee_compliance(employee, as_of=today)
        if summary.has_data:
            compliance_results.append(summary)
    complete = sum(1 for s in compliance_results if s.completeness_pct == 100.0)
    applicable = len(compliance_results)
    compliance_pct = None
    if applicable:
        compliance_pct = round(complete / applicable * 100, 1)

    staffing = []
    if scope_units.exists():
        plans = RencanaFormasi.objects.filter(
            unit_kerja__in=scope_units, status='APPROVED'
        ).select_related('unit_kerja', 'result').order_by('-periode_mulai')
        for plan in plans:
            if not hasattr(plan, 'result'):
                continue
            staffing.append({
                'unit': plan.unit_kerja,
                'profesi': plan.profesi,
                'required_fte': plan.result.required_fte,
                'actual_fte': plan.result.actual_fte,
                'gap_fte': plan.result.gap_fte,
                'sufficiency_pct': plan.result.sufficiency_pct,
                'period': (plan.periode_mulai, plan.periode_selesai),
            })

    return {
        'generated_at': timezone.now(),
        'filters': {'unit': unit, 'profesi': profesi, 'status': status},
        'active_employees': active_count,
        'total_employees': employee_count,
        'has_employees': employee_count > 0,
        'compliance_pct': compliance_pct,
        'compliance_requirements_applicable': applicable,
        'compliance_employees_complete': complete,
        'compliance_scope_count': len(compliance_results),
        'pending_reviews': pending_reviews,
        'expiring': expiring_in_scope,
        'expiring_30': len(expiring_in_scope.get('lt_30', [])),
        'expired': len(expiring_in_scope.get('expired', [])),
        'staffing': staffing,
        'has_staffing': bool(staffing),
        'reminders': visible_reminders(user),
        'training_coverage': training_coverage,
        'overdue_orientation': overdue_orientation,
        'level_cards': _level_cards(user, unit=unit),
    }


def _level_cards(user, *, unit=None):
    """Five functional-level entry cards; only delivered and permitted ones link."""
    from sdm.akses import visible_units

    def allowed(capability):
        return visible_units(user, capability=capability).exists()

    return [
        {
            'level': 'Level 1', 'title': 'Perencanaan & Kepegawaian',
            'description': 'Direktori, e-file, kalkulator FTE.',
            'url_name': 'sdm:pegawai_list' if allowed('can_view_hc') else None,
            'links': [
                {'label': 'Direktori', 'url_name': 'sdm:pegawai_list',
                 'allowed': allowed('can_view_hc')},
                {'label': 'Formasi', 'url_name': 'sdm:formasi_list',
                 'allowed': allowed('can_plan_hc_workforce')},
            ],
        },
        {
            'level': 'Level 2', 'title': 'Rekrutmen & Kredensial',
            'description': 'Rekrutmen, PSV, RKK/SPK, orientasi.',
            'links': [
                {'label': 'Rekrutmen', 'url_name': 'sdm:rekrutmen_list',
                 'allowed': allowed('can_manage_hc_recruitment')},
                {'label': 'Kredensial', 'url_name': 'sdm:kredensial_list',
                 'allowed': allowed('can_review_hc_credentials')},
                {'label': 'Orientasi', 'url_name': 'sdm:orientasi_list',
                 'allowed': allowed('can_manage_hc_orientation')},
            ],
        },
        {
            'level': 'Level 3', 'title': 'Kinerja & Pengembangan',
            'description': 'Penilaian kinerja, TNA, diklat.',
            'links': [
                {'label': 'Kinerja', 'url_name': 'sdm:kinerja_list',
                 'allowed': allowed('can_manage_hc_appraisals')},
                {'label': 'Diklat', 'url_name': 'sdm:diklat_list',
                 'allowed': allowed('can_manage_hc_training')},
            ],
        },
        {
            'level': 'Level 4', 'title': 'Kesehatan & Keselamatan Kerja',
            'description': 'Risiko K3, MCU, insiden (akses terbatas).',
            'links': [
                {'label': 'K3', 'url_name': 'sdm:k3_list',
                 'allowed': allowed('hc_health_write')},
            ],
        },
        {
            'level': 'Level 5', 'title': 'Analitik & Kepatuhan',
            'description': 'Snapshot, audit KPS, talent, skenario.',
            'links': [
                {'label': 'Analitik', 'url_name': 'sdm:analitik_dashboard',
                 'allowed': allowed('can_view_hc_analytics')},
                {'label': 'Audit & Ekspor', 'url_name': 'sdm:analitik_dashboard',
                 'allowed': allowed('can_export_hc')},
            ],
        },
    ]
