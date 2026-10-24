"""Self-service staff request service (Task B7)."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_employees
from sdm.models import LayananMandiri, Pegawai, PeristiwaSDM


def submit_staff_request(*, actor, kind, payload, idempotency_key):
    """Submit a self-service request scoped to the actor's own employee."""
    require_hc_capability(actor, 'can_view_hc')

    employees = visible_employees(actor)
    try:
        employee = employees.get(akun=actor)
    except Pegawai.DoesNotExist:
        raise PermissionDenied('Akun Anda tidak terhubung dengan data pegawai.')

    if idempotency_key:
        existing = (
            LayananMandiri.objects.filter(
                employee=employee, kind=kind, idempotency_key=idempotency_key
            )
            .order_by('-created_at')
            .first()
        )
        if existing:
            return existing

    draft = (
        LayananMandiri.objects.filter(employee=employee, kind=kind, state='DRAFT')
        .order_by('-created_at')
        .first()
    )
    if draft:
        draft.state = 'SUBMITTED'
        draft.payload = payload or {}
        draft.idempotency_key = idempotency_key or draft.idempotency_key
        draft.updated_at = timezone.now()
        draft.save(update_fields=['state', 'payload', 'idempotency_key', 'updated_at'])
    else:
        draft = LayananMandiri.objects.create(
            employee=employee,
            kind=kind,
            payload=payload or {},
            state='SUBMITTED',
            idempotency_key=idempotency_key,
        )

    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='staff_request_submitted',
        target_tipe='employee',
        target_id=str(employee.pk),
        alasan=f'kind={kind}; id={draft.pk}',
    )
    return draft


def decide_staff_request(*, request, actor, decision, reason):
    """Approve or reject a staff self-service request. Reviewer must have scope."""
    require_hc_capability(actor, 'can_view_hc')
    require_hc_capability(actor, 'can_manage_hc_employees', employee=request.employee)

    if request.state not in {'SUBMITTED', 'IN_REVIEW'}:
        raise ValidationError('Pengajuan tidak dapat diputuskan lagi.')

    with transaction.atomic():
        request.state = 'APPROVED' if decision == 'approve' else 'REJECTED'
        request.decision_reason = reason or ''
        request.decided_at = timezone.now()
        request.reviewer = actor
        request.save(
            update_fields=['state', 'decision_reason', 'decided_at', 'reviewer', 'updated_at']
        )

        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='staff_request_decided',
            target_tipe='employee',
            target_id=str(request.employee.pk),
            alasan=f'kind={request.kind}; decision={decision}; id={request.pk}',
        )
    return request
