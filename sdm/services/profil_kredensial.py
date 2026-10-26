"""D-1: read-only credential profile card for the submission screens."""
from django.utils import timezone

from sdm.services.legalitas import legal_status

LICENSE_STATE_LABELS = {
    'VALID': 'Berlaku',
    'EXPIRED': 'Kedaluwarsa',
}


def credential_profile(employee, *, as_of=None):
    """Return the read-only identity/licence facts shown above the form.

    Legal state comes from ``legal_status`` so the card can never disagree
    with the permits view; an absent licence reads as 'Belum ada' rather
    than a fabricated status.
    """
    as_of = as_of or timezone.localdate()
    placements = employee.penempatan.select_related('unit_kerja').order_by(
        'tanggal_mulai', 'pk'
    )
    first = placements.first()
    current = employee.penempatan.filter(
        tanggal_mulai__lte=as_of,
    ).filter(
        unit_kerja__isnull=False,
    ).order_by('-tanggal_mulai', '-pk').first()
    masa_kerja = ''
    if first is not None and first.tanggal_mulai:
        delta_days = (as_of - first.tanggal_mulai).days
        if delta_days >= 0:
            masa_kerja = f'{delta_days // 365} tahun {(delta_days % 365) // 30} bulan'

    licenses = {}
    for item in legal_status(employee, as_of=as_of).items:
        subtype = item.get('subtype')
        if subtype in ('STR', 'SIP', 'SIPA') and subtype not in licenses:
            licenses[subtype] = {
                'label': LICENSE_STATE_LABELS.get(item.get('band'), item.get('label')),
                'nomor': item.get('nomor_izin', ''),
                'berakhir': item.get('tanggal_berakhir'),
            }

    return {
        'nama': employee.nama_lengkap,
        'nomor_pegawai': employee.nomor_pegawai or '',
        'profesi': (
            employee.profesi_master.nama if employee.profesi_master
            else employee.profesi
        ),
        'jabatan': employee.jabatan or '',
        'unit_kerja': current.unit_kerja if current else None,
        'masa_kerja': masa_kerja,
        'licenses': [
            {
                'subtype': subtype,
                'label': licenses.get(subtype, {}).get('label', 'Belum ada'),
                'nomor': licenses.get(subtype, {}).get('nomor', ''),
                'berakhir': licenses.get(subtype, {}).get('berakhir'),
            }
            for subtype in ('STR', 'SIP')
        ],
    }
