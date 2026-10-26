"""D-3: staged credential workflow (additive to the legacy status field)."""
from django.core.exceptions import PermissionDenied, ValidationError

from sdm.akses import require_hc_capability
from sdm.models import PeristiwaSDM, PengajuanKredensial
from sdm.models.kredensial import TahapKredensial

# Forward order; a transition may only move to a later stage.
STAGE_ORDER = [
    'VERIFIKASI_SDM',
    'REVIEW_SUBKOMITE',
    'REKOMENDASI_KETUA_KOMITE',
    'BERKAS_LENGKAP',
    'DIAJUKAN_DIREKTUR',
    'SK_TERBIT',
]

# Which capability a caller must hold to move the request into a stage.
STAGE_CAPABILITY = {
    'VERIFIKASI_SDM': 'can_manage_hc_documents',
    'REVIEW_SUBKOMITE': 'hc_review_subkomite',
    'REKOMENDASI_KETUA_KOMITE': 'hc_recommend_komite',
    'BERKAS_LENGKAP': 'hc_recommend_komite',
    'DIAJUKAN_DIREKTUR': 'hc_approve_credentials',
    'SK_TERBIT': 'hc_approve_credentials',
    'DITOLAK': 'hc_approve_credentials',
}

STAGE_LABELS = dict(TahapKredensial.TAHAP_CHOICES)


def current_stage(application):
    """Latest recorded stage, or None when the request never advanced."""
    row = TahapKredensial.objects.filter(pengajuan=application).order_by(
        '-created_at', '-pk'
    ).first()
    return row.tahap if row else None


def current_stage_row(application):
    return TahapKredensial.objects.filter(pengajuan=application).order_by(
        '-created_at', '-pk'
    ).first()


def stage_history(application):
    return list(
        TahapKredensial.objects.filter(pengajuan=application).select_related('aktor')
        .order_by('created_at', 'pk')
    )


def stepper_rows(application):
    """Ordered rows for the UI stepper, marking done/current/pending."""
    reached = {row.tahap for row in stage_history(application)}
    latest = current_stage(application)
    rows = []
    for stage in STAGE_ORDER:
        rows.append({
            'tahap': stage,
            'label': STAGE_LABELS[stage],
            'done': stage in reached and stage != latest,
            'current': stage == latest,
        })
    return rows


def advance_stage(application, *, actor, tahap, catatan='', kekurangan=''):
    """Record one forward stage transition; never mutates legacy status."""
    if tahap not in dict(TahapKredensial.TAHAP_CHOICES):
        raise ValidationError({'tahap': 'Tahap tidak dikenal.'})
    capability = STAGE_CAPABILITY.get(tahap)
    if capability is None:
        raise ValidationError({'tahap': 'Tahap tidak memiliki kapabilitas.'})
    require_hc_capability(actor, capability, unit=application.unit_kerja_id)

    previous = current_stage(application)
    if tahap != 'DITOLAK' and previous is not None:
        if tahap not in STAGE_ORDER or previous not in STAGE_ORDER:
            raise ValidationError({'tahap': 'Transisi tahap tidak valid.'})
        if STAGE_ORDER.index(tahap) <= STAGE_ORDER.index(previous):
            raise ValidationError({
                'tahap': f'Tahap {STAGE_LABELS[tahap]} sudah dilalui atau bukan lanjutan.'
            })

    row = TahapKredensial.objects.create(
        pengajuan=application,
        tahap=tahap,
        aktor=actor,
        catatan=(catatan or '')[:2000],
        kekurangan=(kekurangan or '')[:2000],
    )
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='credential_stage_advanced',
        target_tipe='credential_request',
        target_id=str(application.pk),
        status_sebelum=previous or '',
        status_sesudah=tahap,
        alasan=(kekurangan or catatan or 'stage advanced')[:200],
    )
    return row
