"""Logbook aggregation for the 3-year re-credential requirement (C-2)."""
from datetime import timedelta

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


def logbook_recap_5tahun(employee, *, years=5, end_date=None):
    """5-year trailing recap untuk PMK 13/2025.

    Mengumpulkan entri logbook karyawan dalam window 5 tahun trailing.
    Mengembalikan ``{'tahun_labels', 'total_5tahun', 'mandiri', 'supervisi',
    'kolaborasi', 'per_tindakan', 'terverifikasi', 'tahunan'}``.

    Bucket tahunan: T1 paling tua hingga T5 (terbaru); tiap bucket 365 hari
    dihitung mundur dari tanggal akhir.
    """
    today = end_date or timezone.localdate()
    start_date = today - timedelta(days=years * 365 + 5)
    # Bucket terindeks tahun kalender relatif terhadap tahun terakhir (T5 = tahun
    # berjalan). Perbedaan indeks 365 hari = 1 tahun, jadi T5 = tahun berjalan,
    # T1 = empat tahun sebelumnya.
    tahun_terakhir = today.year

    recap = {
        'tahun_labels': [f'T{i}' for i in range(1, years + 1)],
        'total_5tahun': 0,
        'total': 0,
        'mandiri': 0,
        'supervisi': 0,
        'kolaborasi': 0,
        'per_tindakan': [],
        'terverifikasi': 0,
        'tahunan': [0] * years,
    }

    entries = (
        EntriLogbookKlinis.objects.filter(
            employee=employee, tanggal__gte=start_date
        )
        .select_related('katalog_tindakan')
        .prefetch_related('verifikasi')
        .order_by('tanggal')
    )

    for entry in entries:
        idx = entry.tanggal.year - tahun_terakhir + (years - 1)
        if not 0 <= idx < years:
            continue
        m = entry.jumlah_mandiri or 0
        s = entry.jumlah_supervisi or 0
        k = entry.jumlah_kolaborasi or 0
        total = m + s + k

        recap['mandiri'] += m
        recap['supervisi'] += s
        recap['kolaborasi'] += k
        recap['total_5tahun'] += total
        recap['tahunan'][idx] += total

        label = entry.katalog_tindakan.nama if entry.katalog_tindakan else entry.tindakan
        kode = entry.katalog_tindakan.kode if entry.katalog_tindakan else '-'
        is_verified = any(v.status == VerifikasiLogbook.VERIFIED for v in entry.verifikasi.all())

        row = next(
            (item for item in recap['per_tindakan'] if item['label'] == label), None,
        )
        if row is None:
            row = {
                'label': label,
                'kode': kode,
                'mandiri': 0, 'supervisi': 0, 'kolaborasi': 0,
                'total': 0, 'tahunan': [0] * years,
                'verified_count': 0,
                'status_verifikasi': 'Menunggu',
            }
            recap['per_tindakan'].append(row)
        row['mandiri'] += m
        row['supervisi'] += s
        row['kolaborasi'] += k
        row['total'] += total
        row['tahunan'][idx] += total

        if is_verified:
            recap['terverifikasi'] += total
            row['verified_count'] += total

    for item in recap['per_tindakan']:
        if item.get('verified_count', 0) > 0:
            item['status_verifikasi'] = 'Terverifikasi'
        else:
            item['status_verifikasi'] = 'Menunggu'

    recap['total'] = recap['total_5tahun']
    return recap


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
    """Raise PermissionDenied unless an HC review grant covers entry's unit
    or the user's own pegawai row is a jenjang-qualified preseptor there."""
    try:
        pegawai = user.pegawai_hc
    except AttributeError:
        pegawai = None
    if pegawai is not None and pegawai.status == 'AKTIF':
        from sdm.services.preseptor import eligible_preceptors
        if eligible_preceptors(entry.unit_kerja).filter(pk=pegawai.pk).exists():
            return
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
