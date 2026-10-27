"""Siklus penilaian kinerja 6 tahap (ARIMA) — tahapan + penilaian butir.

Aturan finalisasi & IDP tetap di ``sdm.services.kinerja``; modul ini
menyediakan tahapan, reviewer otomatis dari atasan langsung, dan penyimpanan
skor butir.
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from sdm.akses import require_hc_capability
from sdm.models import (
    ButirPenilaian,
    PenilaianKinerja,
    PeristiwaSDM,
    TahapPenilaian,
)

# Forward order; transisi hanya maju (skip diperbolehkan, ala kredensial).
STAGE_ORDER = [
    'DATA_TERKUMPUL',
    'SELF_ASSESSMENT',
    'REVIEW_ATASAN',
    'KALIBRASI_MUTU',
    'FEEDBACK',
    'TERKUNCI',
]

# Kapabilitas yang wajib dipegang aktor untuk masuk tahap. SELF_ASSESSMENT
# aktornya pegawai sendiri, TERKUNCI hanya lewat finalize_appraisal.
STAGE_CAPABILITY = {
    'DATA_TERKUMPUL': 'can_manage_hc_appraisals',
    'REVIEW_ATASAN': 'can_manage_hc_appraisals',
    'KALIBRASI_MUTU': 'hc_calibrate_appraisals',
    'FEEDBACK': 'can_manage_hc_appraisals',
}

STAGE_LABELS = dict(TahapPenilaian.TAHAP_CHOICES)


def current_stage(appraisal):
    """Tahap terakhir tercatat, atau None bila belum ada."""
    row = TahapPenilaian.objects.filter(appraisal=appraisal).order_by(
        '-created_at', '-pk'
    ).first()
    return row.tahap if row else None


def stage_history(appraisal):
    return list(
        TahapPenilaian.objects.filter(appraisal=appraisal)
        .select_related('aktor')
        .order_by('created_at', 'pk')
    )


def stepper_rows(appraisal):
    """Baris stepper UI: done/current/pending per tahap."""
    reached = {row.tahap for row in stage_history(appraisal)}
    latest = current_stage(appraisal)
    final = appraisal.status == 'FINAL'
    rows = []
    for stage in STAGE_ORDER:
        if stage == 'TERKUNCI':
            done = final
            current = False
        else:
            done = stage in reached and stage != latest
            current = stage == latest and not final
        rows.append({
            'tahap': stage,
            'label': STAGE_LABELS[stage],
            'done': done,
            'current': current,
        })
    return rows


def advance_stage(appraisal, *, actor, tahap, catatan=''):
    """Catat satu transisi tahap maju (append-only, forward-only).

    SELF_ASSESSMENT hanya boleh oleh pegawai yang dinilai; TERKUNCI hanya
    lewat ``finalize_appraisal``. Skip tahap diperbolehkan bila aktor
    memegang kapabilitas tahap tujuan.
    """
    if tahap not in dict(TahapPenilaian.TAHAP_CHOICES):
        raise ValidationError({'tahap': 'Tahap tidak dikenal.'})
    if appraisal.status == 'FINAL':
        raise ValidationError({'status': 'Penilaian sudah final.'})

    if tahap == 'SELF_ASSESSMENT':
        if appraisal.employee.akun_id != getattr(actor, 'pk', None):
            raise PermissionDenied('Hanya pegawai yang dinilai dapat mengisi evaluasi mandiri.')
    elif tahap == 'TERKUNCI':
        raise ValidationError({'tahap': 'Penguncian hanya melalui finalisasi.'})
    else:
        capability = STAGE_CAPABILITY.get(tahap)
        if capability is None:
            raise ValidationError({'tahap': 'Tahap tidak memiliki kapabilitas.'})
        require_hc_capability(actor, capability, employee=appraisal.employee)

    previous = current_stage(appraisal)
    if previous is not None:
        if previous not in STAGE_ORDER:
            raise ValidationError({'tahap': 'Riwayat tahap tidak valid.'})
        if STAGE_ORDER.index(tahap) <= STAGE_ORDER.index(previous):
            raise ValidationError({
                'tahap': f'Tahap {STAGE_LABELS[tahap]} sudah dilalui atau bukan lanjutan.'
            })

    row = TahapPenilaian.objects.create(
        appraisal=appraisal,
        tahap=tahap,
        aktor=actor,
        catatan=(catatan or '')[:2000],
    )
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='appraisal_stage_advanced',
        target_tipe='appraisal',
        target_id=str(appraisal.pk),
        status_sebelum=previous or '',
        status_sesudah=tahap,
        alasan=(catatan or 'tahap penilaian dimajukan')[:200],
    )
    return row


def resolve_reviewer(pegawai):
    """Akun atasan langsung dari penempatan aktif terbaru, atau None.

    Penempatan tanpa atasan dilewati; bila tidak ada, reviewer diisi manual.
    """
    from sdm.models import PenempatanPegawai

    penempatan = (
        PenempatanPegawai.objects
        .filter(pegawai=pegawai, atasan_langsung__isnull=False)
        .order_by('-tanggal_mulai', '-pk')
        .select_related('atasan_langsung')
        .first()
    )
    if penempatan is None:
        return None
    return penempatan.atasan_langsung.akun_id


SKOR_MIN_ = Decimal('0.00')


def simpan_skor(appraisal, skor_map, *, actor, overwrite=True):
    """Simpan skor butir ``{butir_id: Decimal/str/int 0..5}``.

    ``overwrite=False`` hanya mengisi butir yang belum terskor (dipakai
    sinkronisasi agar skor manual tidak pernah ditimpa).
    """
    require_hc_capability(actor, 'can_manage_hc_appraisals', employee=appraisal.employee)
    if appraisal.status == 'FINAL':
        raise ValidationError({'status': 'Penilaian sudah final.'})
    if not skor_map:
        return 0

    butir_qs = appraisal.items.filter(pk__in=list(skor_map.keys()))
    by_id = {row.pk: row for row in butir_qs}
    updates = []
    seen = set()
    for butir_id, raw in skor_map.items():
        row = by_id.get(int(butir_id))
        if row is None:
            raise ValidationError({'items': f'Butir {butir_id} bukan milik penilaian ini.'})
        seen.add(row.pk)
        if not overwrite and row.score is not None:
            continue
        try:
            skor = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({'items': f'Skor butir "{row.nama}" tidak valid.'})
        if skor < Decimal('0.00') or skor > Decimal('5.00'):
            raise ValidationError({'items': f'Skor butir "{row.nama}" harus 0-5.'})
        row.score = skor.quantize(Decimal('0.01'))
        updates.append(row)

    with transaction.atomic():
        for row in updates:
            row.save(update_fields=['score'])
        if appraisal.reviewer_id is None and actor.pk:
            appraisal.reviewer_id = actor.pk
            appraisal.save(update_fields=['reviewer'])
    return len(updates)
