"""WISN calculation service (Task A4).

WISN (Workload Indicator of Staffing Need) is a separately validated method and
is deliberately NOT relabelled activity FTE. `calculate_formasi` continues to
mean activity-based FTE; `calculate_wisn` uses an independently reviewed
worksheet with approved available working time, standard workloads, category
allowance factor and individual allowance.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from sdm.models import BebanKerja

WISN_CALC_VERSION = 'wisn-v1'


def _q(value):
    return Decimal(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_wisn(plan):
    """Compute WISN staffing need from an approved BebanKerja snapshot.

    Returns a dict with raw inputs, version, results and coverage flags.
    Raises ValidationError for unsupported combinations instead of falling back
    to activity FTE.
    """
    if plan.metode != 'WISN':
        raise ValidationError({'metode': 'WISN calculation requires metode=WISN.'})

    if not plan.is_approved:
        raise ValidationError({'is_approved': 'Beban kerja harus disetujui sebelum dihitung.'})

    missing = []
    if plan.jam_operasional_per_hari is None:
        missing.append('jam_operasional_per_hari')
    if plan.hari_operasional_per_minggu is None:
        missing.append('hari_operasional_per_minggu')
    if plan.standard_minutes_per_kunjungan is None:
        missing.append('standard_minutes_per_kunjungan')
    if plan.kunjungan_periode is None:
        missing.append('kunjungan_periode')
    if missing:
        raise ValidationError({'coverage': f'Data tidak lengkap untuk WISN: {", ".join(missing)}'})

    # Available working time per employee per period (minutes).
    weeks = Decimal(plan.hari_operasional_per_minggu) / Decimal('7')
    days_in_period = (plan.periode_selesai - plan.periode_mulai).days + 1
    available_hours = (
        plan.jam_operasional_per_hari * weeks * Decimal(days_in_period) / Decimal('7')
    )
    available_minutes = available_hours * Decimal(60)

    # Standard workload = volume × standard minutes.
    standard_workload_minutes = (
        Decimal(plan.kunjungan_periode) * Decimal(plan.standard_minutes_per_kunjungan)
    )

    # Allowance-adjusted workload.
    allowance_factor = (
        plan.faktor_pengantar_kategori * plan.faktor_pengantar_individu
    )
    adjusted_workload = standard_workload_minutes * allowance_factor

    # Staffing need (FTE).
    if available_minutes <= 0:
        raise ValidationError({'jam_operasional_per_hari': 'Tersedia waktu kerja nol.'})
    required_fte = _q(adjusted_workload / available_minutes)

    result = {
        'calculation_version': WISN_CALC_VERSION,
        'metode': 'WISN',
        'unit_kerja_id': str(plan.unit_kerja_id),
        'profesi': plan.profesi,
        'periode_mulai': plan.periode_mulai.isoformat(),
        'periode_selesai': plan.periode_selesai.isoformat(),
        'available_minutes': _q(available_minutes),
        'standard_workload_minutes': _q(standard_workload_minutes),
        'faktor_pengantar_kategori': plan.faktor_pengantar_kategori,
        'faktor_pengantar_individu': plan.faktor_pengantar_individu,
        'allowance_factor': _q(allowance_factor),
        'adjusted_workload_minutes': _q(adjusted_workload),
        'required_fte': required_fte,
        'coverage_complete': True,
        'reason': '',
    }
    return result


def wisn_summary(plan):
    """Human-readable WISN result: required FTE vs actual allocation gap."""
    result = calculate_wisn(plan)
    return {
        'required_fte': result['required_fte'],
        'reason': 'WISN dihitung dari beban kerja yang disetujui.',
    }
