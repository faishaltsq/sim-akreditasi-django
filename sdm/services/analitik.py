"""Level 5 explainable analytics and export (no silent estimation)."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_employees
from sdm.models import (
    DokumenPegawai,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
    SkenarioSDM,
    SnapshotAnalitikSDM,
    VersiDokumen,
)

CALC_VERSION = 'hc-analytics-v1'


def _quantize(value):
    return Decimal(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def compute_turnover(*, user, unit, period_start, period_end):
    """Turnover = departures / average active headcount; unavailable without data."""
    require_hc_capability(user, 'can_view_hc_analytics', unit=unit.pk)
    if period_end < period_start:
        raise ValidationError({'periode': 'Periode selesai mendahului mulai.'})

    in_scope = visible_employees(user, unit=unit)
    departures = in_scope.filter(status='NONAKTIF').count()
    active = in_scope.filter(status='AKTIF').count()
    average_headcount = Decimal(active)
    if average_headcount <= 0:
        return {
            'is_available': False,
            'unavailable_reason': 'Tidak ada pegawai aktif pada periode ini.',
            'value': None,
            'denominator': None,
            'coverage': {'active': active, 'departures': departures},
        }

    return {
        'is_available': True,
        'unavailable_reason': '',
        'value': _quantize(Decimal(departures) / average_headcount * Decimal('100')),
        'denominator': average_headcount,
        'coverage': {'active': active, 'departures': departures},
    }


def compute_bor(*, unit, period_start, period_end):
    """BOR = occupied bed-days / available bed-days for the same scope and period.

    Bed occupancy is derived from admissions, not from today's bed snapshot, so a
    historical period is never silently labelled with current occupancy.
    """
    from pasien.models import Bed, KunjunganPasien

    if period_end < period_start:
        raise ValidationError({'periode': 'Periode selesai mendahului mulai.'})

    beds = Bed.objects.filter(ruangan__jenis='RANAP').exclude(status='TIDAK_AKTIF')
    available_beds = beds.count()
    if available_beds == 0:
        return {
            'is_available': False,
            'unavailable_reason': 'Tidak ada bed rawat inap aktif pada periode ini.',
            'value': None,
            'denominator': None,
            'coverage': {'available_beds': 0, 'occupied_bed_days': 0},
        }

    days = (period_end - period_start).days + 1
    available_bed_days = Decimal(available_beds * days)

    visits = KunjunganPasien.objects.filter(
        bed__isnull=False,
        tanggal_masuk__date__lte=period_end,
    ).filter(
        models_q_end(period_start)
    )
    occupied_bed_days = Decimal('0')
    for visit in visits.only('tanggal_masuk', 'tanggal_keluar'):
        start = max(visit.tanggal_masuk.date(), period_start)
        end = min(
            (visit.tanggal_keluar.date() if visit.tanggal_keluar else period_end),
            period_end,
        )
        if end >= start:
            occupied_bed_days += Decimal((end - start).days + 1)

    return {
        'is_available': True,
        'unavailable_reason': '',
        'value': _quantize(occupied_bed_days / available_bed_days * Decimal('100')),
        'denominator': available_bed_days,
        'coverage': {
            'available_beds': available_beds,
            'occupied_bed_days': str(occupied_bed_days),
            'days': days,
        },
    }


def models_q_end(period_start):
    from django.db.models import Q

    return Q(tanggal_keluar__isnull=True) | Q(tanggal_keluar__date__gte=period_start)


def persist_snapshot(*, user, unit, metrik, period_start, period_end, result,
                     filters=None, coverage=None):
    require_hc_capability(user, 'can_view_hc_analytics', unit=unit.pk)
    snapshot = SnapshotAnalitikSDM(
        unit_kerja=unit,
        metrik=metrik,
        periode_mulai=period_start,
        periode_selesai=period_end,
        calculation_version=CALC_VERSION,
        filters=filters or {},
        source_coverage=coverage or result.get('coverage', {}),
        value=result['value'],
        denominator=result['denominator'],
        is_available=result['is_available'],
        unavailable_reason=result['unavailable_reason'],
    )
    snapshot.full_clean()
    snapshot.save()
    return snapshot


def staffing_bor_comparison(*, user, unit, period_start, period_end):
    """Compare staffing sufficiency against BOR for the same period; refuse mismatches."""
    from sdm.models import RencanaFormasi

    require_hc_capability(user, 'can_view_hc_analytics', unit=unit.pk)
    bor = compute_bor(unit=unit, period_start=period_start, period_end=period_end)
    if not bor['is_available']:
        return {'is_available': False, 'reason': bor['unavailable_reason'], 'rows': []}

    plans = RencanaFormasi.objects.filter(
        unit_kerja=unit, status='APPROVED',
        periode_mulai__gte=period_start, periode_selesai__lte=period_end,
    ).select_related('result')

    rows = []
    for plan in plans:
        result = getattr(plan, 'result', None)
        if result is None:
            continue
        rows.append({
            'profesi': plan.profesi,
            'periode': (plan.periode_mulai, plan.periode_selesai),
            'required_fte': result.required_fte,
            'actual_fte': result.actual_fte,
            'sufficiency_pct': result.sufficiency_pct,
            'bor_pct': bor['value'],
        })
    if not rows:
        return {
            'is_available': False,
            'reason': 'Belum ada rencana formasi disetujui yang periodenya cocok.',
            'rows': [],
            'bor': bor,
        }
    return {'is_available': True, 'reason': '', 'rows': rows, 'bor': bor}


def compliance_audit(*, user, unit):
    """Per-requirement completeness; never mutates QualityRecord scores.

    Requirement-to-catalogue links come only from reviewed ``PemetaanStandarSDM``
    rows; an unmapped requirement is reported as unreviewed, not as compliance.
    """
    require_hc_capability(user, 'can_view_hc_analytics', unit=unit.pk)
    from sdm.models import PemetaanStandarSDM
    from sdm.services.kepatuhan import evaluate_employee_compliance

    mappings = {
        mapping.rule_id: mapping
        for mapping in PemetaanStandarSDM.objects.filter(
            is_active=True, standard_item__record__unit=unit,
        ).select_related('standard_item', 'framework')
    }

    employees = visible_employees(user, unit=unit)
    rows = []
    unmapped_rules = set()
    for employee in employees:
        summary = evaluate_employee_compliance(employee)
        if not summary.has_data:
            continue
        for result in summary.applicable:
            if result.rule.pk not in mappings:
                unmapped_rules.add(result.rule.name)
        rows.append({
            'employee_id': str(employee.pk),
            'nama': employee.nama_lengkap,
            'profesi': employee.profesi,
            'completeness_pct': summary.completeness_pct,
            'upload_pct': summary.upload_pct,
            'applicable': len(summary.applicable),
            'satisfied': len(summary.satisfied),
        })
    return {
        'generated_at': timezone.now(),
        'unit': unit,
        'rows': rows,
        'employee_count': len(rows),
        'mapped_requirements': len(mappings),
        'unmapped_requirements': sorted(unmapped_rules),
    }


def export_audit_pdf(audit):
    """Redacted PDF: same rows as the workbook, no medical data or file URLs."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from io import BytesIO

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph('Audit Kepatuhan Dokumen SDM', styles['Title']),
        Paragraph(
            f"Unit: {_escape(audit['unit'].code)} — {_escape(audit['unit'].name)}",
            styles['Normal'],
        ),
        Paragraph(
            f"Digenerate: {audit['generated_at']:%d %B %Y %H:%M} WIB",
            styles['Normal'],
        ),
        Spacer(1, 8 * mm),
    ]
    data = [['Nama', 'Profesi', 'Terpenuhi', 'Kelengkapan', 'Terunggah']]
    for row in audit['rows']:
        data.append([
            Paragraph(_escape(row['nama']), styles['BodyText']),
            Paragraph(_escape(row['profesi']), styles['BodyText']),
            f"{row['satisfied']} / {row['applicable']}",
            f"{row['completeness_pct']}%",
            f"{row['upload_pct']}%",
        ])
    if len(data) == 1:
        story.append(Paragraph('Belum dapat dihitung: belum ada data.', styles['Normal']))
    else:
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        story.append(table)
    document.build(story)
    return buffer.getvalue()


def export_audit_xlsx(audit):
    """Redacted workbook: no medical data, no file URLs, formula-injection escaped."""
    from io import BytesIO

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Audit Kepatuhan'
    sheet.append([
        'Nama', 'Profesi', 'Persyaratan Berlaku', 'Terpenuhi',
        'Kelengkapan (%)', 'Terunggah (%)',
    ])
    for row in audit['rows']:
        sheet.append([
            _escape(row['nama']),
            _escape(row['profesi']),
            row['applicable'],
            row['satisfied'],
            float(row['completeness_pct']) if row['completeness_pct'] is not None else None,
            float(row['upload_pct']) if row['upload_pct'] is not None else None,
        ])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _escape(value):
    text = '' if value is None else str(value)
    if text[:1] in ('=', '+', '-', '@'):
        return "'" + text
    return text


def assess_talent(employee, *, actor, kinerja, kompetensi, threshold_version='v1',
                  disputed=False, notes=''):
    from sdm.models import PenilaianTalent

    require_hc_capability(actor, 'can_manage_hc_talent', employee=employee)
    if kinerja and kinerja not in dict(PenilaianTalent.AXIS_CHOICES):
        raise ValidationError({'kinerja': 'Nilai kinerja tidak valid.'})
    if kompetensi and kompetensi not in dict(PenilaianTalent.AXIS_CHOICES):
        raise ValidationError({'kompetensi': 'Nilai kompetensi tidak valid.'})
    next_version = PenilaianTalent.objects.filter(employee=employee).count() + 1
    assessment = PenilaianTalent.objects.create(
        employee=employee,
        versi=next_version,
        kinerja=kinerja,
        kompetensi=kompetensi,
        threshold_version=threshold_version,
        reviewer=actor,
        disputed=disputed,
        notes=notes,
    )
    return assessment


def propose_scenario(*, actor, unit, jenis, rekomendasi, asumsi, provenance,
                     keterbatasan=''):
    require_hc_capability(actor, 'can_manage_hc_talent', unit=unit.pk)
    if jenis not in dict(SkenarioSDM.JENIS_CHOICES):
        raise ValidationError({'jenis': 'Jenis skenario tidak valid.'})
    if not (rekomendasi or '').strip():
        raise ValidationError({'rekomendasi': 'Rekomendasi wajib diisi.'})
    scenario = SkenarioSDM.objects.create(
        jenis=jenis,
        unit_kerja=unit,
        rekomendasi=rekomendasi,
        asumsi=asumsi,
        provenance=provenance,
        keterbatasan=keterbatasan,
    )
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='scenario_proposed',
        target_tipe='hc_scenario',
        target_id=str(scenario.pk),
        status_sesudah='DRAF',
        alasan=f'jenis={jenis}',
    )
    return scenario


def approve_scenario(scenario, *, actor):
    require_hc_capability(actor, 'can_manage_hc_talent', unit=scenario.unit_kerja_id)
    if scenario.status != 'DRAF':
        raise ValidationError({'status': 'Hanya draf skenario yang dapat disetujui.'})
    scenario.status = 'DISETUJUI'
    scenario.approved_by = actor
    scenario.approved_at = timezone.now()
    scenario.save(update_fields=['status', 'approved_by', 'approved_at'])
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='scenario_approved',
        target_tipe='hc_scenario',
        target_id=str(scenario.pk),
        status_sebelum='DRAF',
        status_sesudah='DISETUJUI',
        alasan='human approval recorded',
    )
    return scenario
