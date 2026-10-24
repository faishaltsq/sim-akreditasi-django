"""Metric population scope and explicit metric metadata (Task A1)."""

from django.db.models import Q
from django.utils import timezone

from sdm.akses import visible_employees
from sdm.models import Pegawai, PenempatanPegawai


def resolve_metric_population(user, *, unit=None, as_of=None, origin_policy=None):
    """Return the employee QuerySet for a metric at a point in time.

    Uses effective-dated placements (active at as_of), not just today's
    placements, so historical scope is evaluated at the requested dates.
    Applies origin_policy to exclude unclassified/demo employment from
    production FTE when the policy says so.
    """
    as_of = as_of or timezone.localdate()
    origin_policy = origin_policy or {'exclude_unclassified': False}

    employees = visible_employees(user, unit=unit)

    active_placements = PenempatanPegawai.objects.filter(
        Q(tanggal_mulai__lte=as_of)
        & (Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=as_of))
    )
    placed_ids = set(active_placements.values_list('pegawai_id', flat=True))

    if unit is not None:
        unit_pk = getattr(unit, 'pk', unit)
        placed_ids = {
            pid
            for pid in placed_ids
            if PenempatanPegawai.objects.filter(
                pegawai_id=pid,
                unit_kerja_id=unit_pk,
                tanggal_mulai__lte=as_of,
            ).filter(
                Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=as_of)
            ).exists()
        }

    employees = employees.filter(pk__in=placed_ids)

    if origin_policy.get('exclude_unclassified'):
        employees = employees.exclude(data_origin='UNCLASSIFIED')

    return employees


def metric_metadata(*, value, numerator, denominator, scope, period, coverage,
                    is_available, reason=''):
    return {
        'value': value,
        'numerator': numerator,
        'denominator': denominator,
        'scope': scope,
        'period': period,
        'coverage': coverage,
        'is_available': is_available,
        'reason': reason,
    }
