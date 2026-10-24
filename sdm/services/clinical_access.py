"""Clinical privilege enforcement service (Task A5/A6)."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from sdm.akses import require_hc_capability
from sdm.models import (
    ClinicalActionCode,
    PeristiwaSDM,
    PrivilegeSnapshot,
    TraineePlacement,
)


def effective_privileges(employee, *, unit, at=None):
    """Return the set of controlled action codes an employee may perform in a
    unit at a point in time, based on active, non-revoked privilege snapshots.

    Trainees never hold independent privileges; their temporary codes are
    evaluated separately via trainee_effective_actions.
    """
    at = at or timezone.localdate()
    unit_id = getattr(unit, 'pk', unit)

    snapshots = PrivilegeSnapshot.objects.filter(
        pegawai=employee,
        unit_kerja_id=unit_id,
        valid_from__lte=at,
    ).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=at)
    )

    codes = set()
    for snapshot in snapshots.select_related('action_code'):
        if snapshot.action_code.is_active:
            codes.add(snapshot.action_code.code)
    return codes


def trainee_effective_actions(trainee, *, unit, at=None):
    """Return temporary action codes a trainee may perform under supervision
    in a unit at a point in time (active placement only)."""
    at = at or timezone.localdate()
    unit_id = getattr(unit, 'pk', unit)
    placement = TraineePlacement.objects.filter(
        pegawai=trainee,
        is_active=True,
        tanggal_mulai__lte=at,
        tanggal_selesai__gte=at,
        unit_kerja_id=unit_id,
    ).first()
    if not placement:
        return set()
    return set(placement.temporary_action_codes or [])


def require_clinical_action(user, *, action_code, encounter, at=None):
    """Raise PermissionDenied unless the user holds the action code for the
    encounter unit, or a supervised trainee holds it with countersignature.

    Additive to patient-module/object authorization; never replaces it.
    """
    at = at or timezone.localdate()
    unit = getattr(encounter, 'unit_kerja', None) or getattr(encounter, 'unit', None)
    if unit is None:
        raise PermissionDenied('Tindakan klinis membutuhkan unit kerja kunjungan.')

    require_hc_capability(user, 'can_view_hc', unit=unit)

    employee = getattr(user, 'pegawai_hc', None)
    if employee is None:
        raise PermissionDenied('Pengguna tidak terhubung dengan data pegawai.')

    codes = effective_privileges(employee, unit=unit, at=at)
    if action_code in codes:
        return

    trainee_codes = trainee_effective_actions(employee, unit=unit, at=at)
    if action_code in trainee_codes:
        action = ClinicalActionCode.objects.filter(code=action_code).first()
        if action and action.requires_countersignature_for_trainee:
            countersigned_by = (
                getattr(encounter, 'counter_signed_by', None)
                or getattr(encounter, 'diajukan_oleh', None)
            )
            if countersigned_by:
                return
        raise PermissionDenied(
            'Magang memerlukan tanda tangan pembimbing untuk tindakan ini.'
        )

    raise PermissionDenied(
        f'Kewenangan klinis {action_code} tidak berlaku untuk unit ini pada waktu tersebut.'
    )


def issue_spk(*, actor, employee, unit, action_codes, valid_from, valid_until=None,
              source_decision=None, reason=''):
    """Create immutable privilege snapshots from an approved SPK decision."""
    require_hc_capability(actor, 'can_review_hc_credentials', unit=unit)
    unit_id = getattr(unit, 'pk', unit)

    snapshots = []
    with transaction.atomic():
        for code in action_codes:
            action = ClinicalActionCode.objects.filter(code=code, is_active=True).first()
            if not action:
                raise ValidationError(
                    {'action_codes': f'Kode aksi tidak aktif atau tidak diketahui: {code}'}
                )
            snapshots.append(
                PrivilegeSnapshot(
                    pegawai=employee,
                    unit_kerja_id=unit_id,
                    action_code=action,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    granted_by=actor,
                    source_decision=source_decision,
                )
            )
        created = PrivilegeSnapshot.objects.bulk_create(snapshots)

    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='spk_issued',
        target_tipe='employee',
        target_id=str(employee.pk),
        alasan=(
            f'spk={getattr(source_decision, "nomor_spk", "")}; '
            f'codes={",".join(action_codes)}; reason={reason}'
        ),
    )
    return created


def revoke_spk(*, actor, employee, unit, action_codes, at=None, reason=''):
    """Revoke (deactivate) privilege snapshots effective at a date."""
    require_hc_capability(actor, 'can_review_hc_credentials', unit=unit)
    at = at or timezone.localdate()
    unit_id = getattr(unit, 'pk', unit)

    with transaction.atomic():
        snapshots = PrivilegeSnapshot.objects.filter(
            pegawai=employee,
            unit_kerja_id=unit_id,
            action_code__code__in=action_codes,
            valid_from__lte=at,
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=at)
        )
        for snapshot in snapshots:
            snapshot.valid_until = at
            snapshot.save(update_fields=['valid_until'])

    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='spk_revoked',
        target_tipe='employee',
        target_id=str(employee.pk),
        alasan=f'codes={",".join(action_codes)}; reason={reason}',
    )
