from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from sdm.akses import require_hc_capability
from sdm.models import HasilFormasi, PeristiwaSDM, RencanaFormasi, calculate_formasi
from sdm.services.risiko import (
    RISIKO_UNCONFIGURED,
    classify_risiko,
    resolve_ambang_risiko,
)


def save_plan(plan, *, user):
    """Persist a draft plan; approved plans are immutable and require a new draft."""
    require_hc_capability(
        user, 'can_plan_hc_workforce', unit=plan.unit_kerja_id
    )
    if plan.pk:
        existing = RencanaFormasi.objects.filter(pk=plan.pk).values_list(
            'status', flat=True
        ).first()
        if existing is None:
            raise ValidationError({'id': 'Rencana formasi tidak ditemukan.'})
        if existing == 'APPROVED':
            raise ValidationError(
                {'status': 'Rencana yang sudah disetujui tidak dapat diubah.'}
            )
    plan.full_clean()
    plan.save()
    return plan


def submit_for_review(plan, *, user):
    require_hc_capability(user, 'can_plan_hc_workforce', unit=plan.unit_kerja_id)
    with transaction.atomic():
        locked = RencanaFormasi.objects.select_for_update().get(pk=plan.pk)
        if locked.status != 'DRAFT':
            raise ValidationError({'status': 'Hanya draf yang dapat diajukan.'})
        calculate_formasi(locked)
        locked.status = 'REVIEW'
        locked.save(update_fields=['status', 'updated_at'])
        PeristiwaSDM.objects.create(
            actor=user,
            jenis_peristiwa='formasi_submitted',
            target_tipe='formasi_plan',
            target_id=str(locked.pk),
            status_sebelum='DRAFT',
            status_sesudah='REVIEW',
            alasan='rencana formasi diajukan untuk tinjauan',
        )
    return locked


def approve_plan(plan, *, user):
    require_hc_capability(user, 'can_plan_hc_workforce', unit=plan.unit_kerja_id)
    with transaction.atomic():
        locked = RencanaFormasi.objects.select_for_update().get(pk=plan.pk)
        if locked.status != 'REVIEW':
            raise ValidationError({'status': 'Hanya rencana dalam tinjauan yang dapat disetujui.'})
        if locked.created_by_id == getattr(user, 'pk', None):
            raise PermissionDenied('Pembuat rencana tidak dapat menyetujuinya sendiri.')
        result = calculate_formasi(locked)
        ambang = resolve_ambang_risiko(locked.unit_kerja, locked.profesi)
        if ambang is None:
            status_risiko = RISIKO_UNCONFIGURED
            ambang_marginal = ambang_kritis = None
        else:
            ambang_marginal, ambang_kritis = ambang
            status_risiko = classify_risiko(
                result['sufficiency_pct'],
                ambang_marginal=ambang_marginal,
                ambang_kritis=ambang_kritis,
            )
        previous = RencanaFormasi.objects.filter(
            unit_kerja_id=locked.unit_kerja_id,
            profesi__iexact=locked.profesi,
            status='APPROVED',
        ).exclude(pk=locked.pk)
        for old in previous.select_for_update():
            old.status = 'SUPERSEDED'
            old.save(update_fields=['status', 'updated_at'])
            PeristiwaSDM.objects.create(
                actor=user,
                jenis_peristiwa='formasi_superseded',
                target_tipe='formasi_plan',
                target_id=str(old.pk),
                status_sebelum='APPROVED',
                status_sesudah='SUPERSEDED',
                alasan=f'replaced_by_plan={locked.pk}',
            )
        HasilFormasi.objects.create(
            rencana=locked,
            calculation_version=result['calculation_version'],
            required_fte=result['required_fte'],
            required_headcount=result['required_headcount'],
            actual_fte=result['actual_fte'],
            gap_fte=result['gap_fte'],
            sufficiency_pct=result['sufficiency_pct'],
            inputs_digest=result['inputs_digest'],
            status_risiko=status_risiko,
            ambang_marginal_pct=ambang_marginal,
            ambang_kritis_pct=ambang_kritis,
            approved_by=user,
        )
        locked.status = 'APPROVED'
        locked.approved_by = user
        locked.approved_at = timezone.now()
        locked.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        PeristiwaSDM.objects.create(
            actor=user,
            jenis_peristiwa='formasi_approved',
            target_tipe='formasi_plan',
            target_id=str(locked.pk),
            status_sebelum='REVIEW',
            status_sesudah='APPROVED',
            alasan=f"calculation_version={result['calculation_version']}",
        )
    return locked
