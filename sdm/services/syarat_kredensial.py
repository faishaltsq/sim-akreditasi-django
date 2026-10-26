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
    sensitivity = 'health' if health else 'personnel'
    return (
        VersiDokumen.objects.filter(
            document__employee=employee,
            document__jenis_berkas=kind,
            document__sensitivity=sensitivity,
        )
        .exclude(status__in=('REJECTED', 'PENDING'))
        .filter(valid_until__isnull=False)
        .filter(valid_until__gte=today)
        .select_related('document')
        .order_by('-version_number', '-pk')
        .first()
        or VersiDokumen.objects.filter(
            document__employee=employee,
            document__jenis_berkas=kind,
            document__sensitivity=sensitivity,
            valid_until__isnull=True,
        )
        .exclude(status__in=('REJECTED', 'PENDING'))
        .select_related('document')
        .order_by('-version_number', '-pk')
        .first()
    )


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
