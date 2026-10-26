"""C-3: per-request supporting-document requirement checklist."""
from django.utils import timezone

from sdm.models import DokumenSyaratKredensial, EntriLogbookKlinis, VersiDokumen
from sdm.models.kredensial import KeputusanKredensial

# domain → jenis → expected document kind / health flag.
DEFAULT_ROWS = [
    {'domain': 'LEGA', 'jenis': 'CV', 'kind': 'CV', 'health': False},
    {'domain': 'LEGA', 'jenis': 'SURAT_PERMOHONAN', 'kind': None, 'health': False},
    {'domain': 'KOMP', 'jenis': 'SERTIFIKAT_KOMPETENSI',
     'kind': 'SERTIFIKAT_KOMPETENSI', 'health': False},
    {'domain': 'KOMP', 'jenis': 'LOGBOOK_36BULAN', 'kind': 'LOGBOOK', 'health': False},
    {'domain': 'SEHAT', 'jenis': 'SEHAT_JASMANI', 'kind': 'MCU', 'health': True},
    {'domain': 'SEHAT', 'jenis': 'SEHAT_PSIKOLOGIS', 'kind': 'PSIKOLOGIS', 'health': True},
    {'domain': 'ETIK', 'jenis': 'BEBAS_SANKSI', 'kind': 'BEBAS_SANKSI', 'health': False},
    {'domain': 'ETIK', 'jenis': 'MALPRACTICE_RECORD',
     'kind': 'MALPRACTICE_RECORD', 'health': False},
    {'domain': 'ETIK', 'jenis': 'KEANGGOTAAN', 'kind': 'KEANGGOTAAN', 'health': False},
    {'domain': 'KINE', 'jenis': 'PENGANTAR_KSM', 'kind': 'PENGANTAR_KSM', 'health': False},
    {'domain': 'PROS', 'jenis': 'BERITA_ACARA', 'kind': None, 'health': False},
    {'domain': 'PROS', 'jenis': 'REKOMENDASI_KOMITE', 'kind': None, 'health': False},
]

WORKFLOW_JENIS = set(DokumenSyaratKredensial.WORKFLOW_JENIS)


def populate_requirements(pengajuan):
    """Idempotent row creation: one row per (pengajuan, jenis)."""
    rows = []
    for spec in DEFAULT_ROWS:
        row, created = DokumenSyaratKredensial.objects.get_or_create(
            pengajuan=pengajuan,
            jenis=spec['jenis'],
            defaults={
                'domain': spec['domain'],
                'status': 'INFO' if spec['jenis'] in WORKFLOW_JENIS else 'KURANG',
            },
        )
        rows.append((row, created))
    return rows


def _latest_valid_version(employee, kind, *, health, today):
    """Newest non-rejected version that is either undated or not yet expired.

    PENDING counts as present evidence (it is awaiting review, not invalid);
    only REJECTED and SUPERSEDED are excluded so the checklist never claims
    a document the employee does not actually have.
    """
    sensitivity = 'health' if health else 'personnel'
    base = VersiDokumen.objects.filter(
        document__employee=employee,
        document__jenis_berkas=kind,
        document__sensitivity=sensitivity,
    ).exclude(status__in=('REJECTED', 'SUPERSEDED')).select_related('document')
    dated = base.filter(
        valid_until__isnull=False, valid_until__gte=today,
    ).order_by('-version_number', '-pk').first()
    if dated is not None:
        return dated
    return base.filter(valid_until__isnull=True).order_by(
        '-version_number', '-pk'
    ).first()


def _logbook_satisfied(employee, *, today):
    return EntriLogbookKlinis.objects.filter(
        employee=employee,
        tanggal__gte=today.replace(year=today.year - 3),
    ).exists()


def evaluate_requirements(pengajuan):
    """Refresh status per row from documents, logbook, and workflow state."""
    today = timezone.localdate()
    decision = KeputusanKredensial.objects.filter(pengajuan=pengajuan).first()
    rows = DokumenSyaratKredensial.objects.filter(pengajuan=pengajuan)
    for row in rows:
        if row.jenis in WORKFLOW_JENIS:
            row.status = 'INFO'
            if row.jenis == 'BERITA_ACARA' and decision is not None:
                row.note = 'Rapat sudah diputuskan.'
            row.save(update_fields=['status', 'note'])
            continue
        if row.jenis == 'LOGBOOK_36BULAN':
            ok = _logbook_satisfied(pengajuan.employee, today=today)
            if ok:
                row.logbook_ok = True
                row.status = 'TERPENUHI'
            elif pengajuan.logbook_id:
                row.logbook_ok = True
                row.status = 'TERPENUHI'
            else:
                row.logbook_ok = False
                row.status = 'KURANG'
            row.save(update_fields=['logbook_ok', 'status'])
            continue
        spec = next(
            (item for item in DEFAULT_ROWS if item['jenis'] == row.jenis), None
        )
        if spec is None or spec['kind'] is None:
            continue
        version = _latest_valid_version(
            pengajuan.employee, spec['kind'], health=spec['health'], today=today,
        )
        row.document_version = version
        row.status = 'TERPENUHI' if version is not None else 'KURANG'
        row.save(update_fields=['document_version', 'status'])
    return list(rows)


EVIDENCE_AKTIF = 'AKTIF'
EVIDENCE_KADALUARSA = 'KADALUARSA'
EVIDENCE_BELUM = 'BELUM'

EVIDENCE_LABELS = {
    EVIDENCE_AKTIF: 'Aktif',
    EVIDENCE_KADALUARSA: 'Kadaluarsa',
    EVIDENCE_BELUM: 'Belum Diunggah',
}


def evaluate_employee_requirements(employee, *, as_of=None):
    """Read-only checklist for an unsaved request (D-2).

    Returns one row per evidence requirement with ``evidence_state`` in
    AKTIF / KADALUARSA / BELUM. Never writes ``DokumenSyaratKredensial``:
    rows belong to a saved request, not to a pre-submission preview.
    """
    as_of = as_of or timezone.localdate()
    jenis_labels = dict(DokumenSyaratKredensial.JENIS_CHOICES)
    rows = []
    for spec in DEFAULT_ROWS:
        if spec['jenis'] in WORKFLOW_JENIS or spec['kind'] is None:
            continue
        current = _latest_valid_version(
            employee, spec['kind'], health=spec['health'], today=as_of,
        )
        if current is not None:
            state = EVIDENCE_AKTIF
        elif _has_any_version(employee, spec['kind'], health=spec['health']):
            state = EVIDENCE_KADALUARSA
        else:
            state = EVIDENCE_BELUM
        rows.append({
            'domain': spec['domain'],
            'jenis': spec['jenis'],
            'label': jenis_labels.get(spec['jenis'], spec['jenis']),
            'upload_kind': spec['kind'],
            'evidence_state': state,
            'evidence_label': EVIDENCE_LABELS[state],
            'document_version': current,
        })
    return rows


def _has_any_version(employee, kind, *, health):
    sensitivity = 'health' if health else 'personnel'
    return VersiDokumen.objects.filter(
        document__employee=employee,
        document__jenis_berkas=kind,
        document__sensitivity=sensitivity,
    ).exclude(status='REJECTED').exists()
