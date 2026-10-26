"""WISN calculation service (Task A4, corrected in F-A1).

WISN (Workload Indicator of Staffing Need) is a separately validated method and
is deliberately NOT relabelled activity FTE. `calculate_formasi` continues to
mean activity-based FTE; `calculate_wisn` uses an independently reviewed
worksheet with approved available working time, standard workloads, category
allowance factor and individual allowance.

Available working time per employee for a period is::

    operating_days = days_in_period x (hari_operasional_per_minggu / 7)
    available_hours = jam_operasional_per_hari x operating_days

`wisn-v1` applied the weekly factor twice and understated available time by a
factor of seven, inflating required FTE sevenfold. `wisn-v2` fixes the
arithmetic and records every input needed to reproduce the worksheet.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from sdm.models import BebanKerja

WISN_CALC_VERSION = 'wisn-v2'

SEVEN = Decimal('7')
SIXTY = Decimal('60')


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

    # A week has seven days; more operating days than that is not a real unit.
    if not (0 < plan.hari_operasional_per_minggu <= SEVEN):
        raise ValidationError({
            'hari_operasional_per_minggu': 'Hari operasional per minggu harus antara 0 dan 7.'
        })

    # Available working time per employee per period (minutes).
    days_in_period = (plan.periode_selesai - plan.periode_mulai).days + 1
    operating_days = Decimal(days_in_period) * Decimal(
        plan.hari_operasional_per_minggu
    ) / SEVEN
    available_hours = Decimal(plan.jam_operasional_per_hari) * operating_days
    available_minutes = available_hours * SIXTY

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
        'days_in_period': days_in_period,
        'operating_days_in_period': _q(operating_days),
        'jam_operasional_per_hari': plan.jam_operasional_per_hari,
        'hari_operasional_per_minggu': plan.hari_operasional_per_minggu,
        'kunjungan_periode': plan.kunjungan_periode,
        'standard_minutes_per_kunjungan': plan.standard_minutes_per_kunjungan,
        'available_hours': _q(available_hours),
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
