"""Logbook aggregation for the 3-year re-credential requirement (C-2)."""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from sdm.models import EntriLogbookKlinis


def logbook_recap(employee, *, months=36):
    """Aggregate one employee's logbook within the trailing window.

    Returns ``{'mandiri', 'supervisi', 'total', 'dari_tanggal', 'per_tindakan'}``;
    ``per_tindakan`` rows carry ``{'label', 'mandiri', 'supervisi'}``. One query,
    no per-row loop, no fabricated percentage when data is missing.
    """
    today = timezone.localdate()
    years, months_left = divmod(months, 12)
    month_index = today.month - 1 - months_left
    year, month_index = today.year - years + month_index // 12, month_index % 12
    month = month_index + 1
    day = min(today.day, 28)  # clamp: month lengths and Feb 29 vary
    dari_tanggal = today.replace(year=year, month=month, day=day)
    rows = (
        EntriLogbookKlinis.objects.filter(
            employee=employee, tanggal__gte=dari_tanggal
        )
        .values('katalog_tindakan__nama', 'tindakan')
        .annotate(
            mandiri=Sum('jumlah_mandiri'),
            supervisi=Sum('jumlah_supervisi'),
        )
        .order_by('katalog_tindakan__nama', 'tindakan')
    )
    per_tindakan = []
    mandiri_total = 0
    supervisi_total = 0
    for row in rows:
        label = row['katalog_tindakan__nama'] or row['tindakan'] or '—'
        m = row['mandiri'] or 0
        s = row['supervisi'] or 0
        mandiri_total += m
        supervisi_total += s
        per_tindakan.append({'label': label, 'mandiri': m, 'supervisi': s})
    return {
        'mandiri': mandiri_total,
        'supervisi': supervisi_total,
        'total': mandiri_total + supervisi_total,
        'dari_tanggal': dari_tanggal,
        'per_tindakan': per_tindakan,
    }
