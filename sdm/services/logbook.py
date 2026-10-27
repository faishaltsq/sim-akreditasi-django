"""Logbook aggregation for the 3-year re-credential requirement (C-2)."""
from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Q, Subquery, Sum
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_units
from sdm.models import EntriLogbookKlinis, VerifikasiLogbook

CAPABILITY_VERIFIKASI = 'can_review_hc_credentials'


def logbook_recap(employee, *, months=36):
    """Aggregate one employee's logbook within the trailing window.

    Returns ``{'mandiri', 'supervisi', 'kolaborasi', 'total', 'dari_tanggal', 'per_tindakan'}``;
    ``per_tindakan`` rows carry ``{'label', 'mandiri', 'supervisi', 'kolaborasi'}``.
    One grouped aggregate query; totals are summed from the grouped results.
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
            kolaborasi=Sum('jumlah_kolaborasi'),
        )
        .order_by('katalog_tindakan__nama', 'tindakan')
    )
    per_tindakan = []
    mandiri_total = 0
    supervisi_total = 0
    kolaborasi_total = 0
    for row in rows:
        label = row['katalog_tindakan__nama'] or row['tindakan'] or '-'
        m = row['mandiri'] or 0
        s = row['supervisi'] or 0
        k = row['kolaborasi'] or 0
        mandiri_total += m
        supervisi_total += s
        kolaborasi_total += k
        per_tindakan.append({'label': label, 'mandiri': m, 'supervisi': s, 'kolaborasi': k})
    return {
        'mandiri': mandiri_total,
        'supervisi': supervisi_total,
        'kolaborasi': kolaborasi_total,
        'total': mandiri_total + supervisi_total + kolaborasi_total,
        'dari_tanggal': dari_tanggal,
        'per_tindakan': per_tindakan,
    }


def entries_to_verify(user):
    """Entries in the reviewer's units with no decision or a REJECTED latest one."""
    units = visible_units(user, capability=CAPABILITY_VERIFIKASI)
    latest = VerifikasiLogbook.objects.filter(entri=OuterRef('pk')).order_by(
        '-verified_at', '-created_at'
    )
    return EntriLogbookKlinis.objects.filter(
        unit_kerja__in=units,
    ).annotate(
        status_verifikasi=Subquery(latest.values('status')[:1]),
    ).filter(
        Q(status_verifikasi__isnull=True) | Q(status_verifikasi=VerifikasiLogbook.REJECTED)
    ).select_related('employee', 'unit_kerja', 'katalog_tindakan')


def require_verifikator(user, entry):
    """Raise PermissionDenied unless an HC review grant covers the entry's unit."""
    require_hc_capability(user, CAPABILITY_VERIFIKASI, unit=entry.unit_kerja)


def verify_entry(*, user, entry, status, catatan=''):
    """Append one decision; the newest row decides the entry's locked state."""
    if status not in dict(VerifikasiLogbook.STATUS_CHOICES):
        raise ValueError(f'Status verifikasi tidak dikenal: {status}')
    require_verifikator(user, entry)
    return VerifikasiLogbook.objects.create(
        entri=entry, verifikator=user, status=status, catatan=catatan,
        verified_at=timezone.now(),
    )
