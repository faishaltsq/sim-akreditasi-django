from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai, PenempatanPegawai


_INVALID_UNIT = object()


def _active_grants(user, capability, *, today=None):
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
        return HcGrant.objects.none()
    if capability not in dict(HcGrant.CAPABILITY_CHOICES):
        return HcGrant.objects.none()
    if not capability.startswith('hc_health_'):
        profile = UserProfile.objects.filter(user_id=user.pk).first()
        if profile is not None and not profile.has_permission(capability):
            return HcGrant.objects.none()

    today = today or timezone.localdate()
    return HcGrant.objects.filter(
        user_id=user.pk,
        capability=capability,
        is_active=True,
        valid_from__lte=today,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today)).select_related(
        'unit_kerja'
    )


def _resolve_active_unit(unit):
    if unit is None:
        return None
    unit_id = getattr(unit, 'pk', unit)
    if not isinstance(unit_id, int) or isinstance(unit_id, bool):
        return _INVALID_UNIT
    return UnitKerja.objects.filter(pk=unit_id, is_active=True).first() or _INVALID_UNIT


def _unit_scope_ids(grants):
    allowed_ids = set()
    for grant in grants:
        if grant.unit_kerja_id is None:
            return None
        root = grant.unit_kerja
        if not root.is_active:
            continue
        allowed_ids.add(root.pk)
        if grant.include_descendants:
            visited = {root.pk}
            frontier = [root.pk]
            while frontier:
                children = list(
                    UnitKerja.objects.filter(
                        parent_id__in=frontier, is_active=True
                    ).exclude(pk__in=visited).values_list('pk', flat=True)
                )
                visited.update(children)
                allowed_ids.update(children)
                frontier = children
    return allowed_ids


def _current_assignments(employee_id, *, today=None):
    today = today or timezone.localdate()
    return PenempatanPegawai.objects.filter(
        pegawai_id=employee_id,
        tanggal_mulai__lte=today,
    ).filter(Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=today))


def _unplaced_employee_ids(scope_ids, *, today=None):
    """Employees without an active placement, scoped by their account's unit only."""
    placed = _current_assignments_for_today(today).values('pegawai_id')
    return Pegawai.objects.filter(
        akun__profile__unit_kerja_id__in=scope_ids,
    ).exclude(pk__in=placed).values('pk')


def _current_assignments_for_today(today):
    return PenempatanPegawai.objects.filter(tanggal_mulai__lte=today).filter(
        Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=today)
    )


def _employee_scope_unit_ids(employee, *, today=None):
    """Active unit ids scoping an employee: placements first, else the account unit."""
    unit_ids = set(
        _current_assignments(employee.pk, today=today)
        .filter(unit_kerja__is_active=True)
        .values_list('unit_kerja_id', flat=True)
    )
    if unit_ids:
        return unit_ids
    return set(
        UnitKerja.objects.filter(
            is_active=True,
            user_profiles__user_id=getattr(employee, 'akun_id', None),
        ).values_list('pk', flat=True)
    )


def visible_employees(user, *, unit=None, capability='can_view_hc'):
    """Return only employees covered by an explicit, currently valid HC grant."""
    grants = list(_active_grants(user, capability))
    if not grants:
        return Pegawai.objects.none()

    scope_ids = _unit_scope_ids(grants)
    queryset = Pegawai.objects.all()
    today = timezone.localdate()
    if scope_ids is not None:
        if not scope_ids:
            return queryset.none()
        queryset = queryset.filter(
            Q(
                penempatan__unit_kerja_id__in=scope_ids,
                penempatan__unit_kerja__is_active=True,
                penempatan__tanggal_mulai__lte=today,
            )
            & (
                Q(penempatan__tanggal_selesai__isnull=True)
                | Q(penempatan__tanggal_selesai__gte=today)
            )
            | Q(pk__in=_unplaced_employee_ids(scope_ids, today=today))
        )

    if unit is not None:
        target = _resolve_active_unit(unit)
        if target is _INVALID_UNIT:
            return queryset.none()
        if scope_ids is not None and target.pk not in scope_ids:
            return queryset.none()
        queryset = queryset.filter(
            Q(
                penempatan__unit_kerja_id=target.pk,
                penempatan__unit_kerja__is_active=True,
                penempatan__tanggal_mulai__lte=today,
            )
            & (
                Q(penempatan__tanggal_selesai__isnull=True)
                | Q(penempatan__tanggal_selesai__gte=today)
            )
            | Q(
                pk__in=_unplaced_employee_ids({target.pk}, today=today),
            )
        )

    return queryset.distinct()


def visible_units(user, *, capability='can_view_hc'):
    """Return active units covered by the user's currently valid capability grants."""
    grants = list(_active_grants(user, capability))
    if not grants:
        return UnitKerja.objects.none()

    scope_ids = _unit_scope_ids(grants)
    units = UnitKerja.objects.filter(is_active=True)
    if scope_ids is None:
        return units
    if not scope_ids:
        return units.none()
    return units.filter(pk__in=scope_ids)


def require_any_hc_capability(user, capabilities, *, unit=None, employee=None):
    """Raise PermissionDenied unless at least one capability grant covers scope."""
    for capability in capabilities:
        try:
            return require_hc_capability(
                user, capability, unit=unit, employee=employee
            )
        except PermissionDenied:
            continue
    raise PermissionDenied('Hak akses Human Capital tidak tersedia.')


def require_hc_capability(user, capability, *, unit=None, employee=None):
    """Raise PermissionDenied unless an active grant covers the requested scope."""
    grants = list(_active_grants(user, capability))
    if not grants:
        raise PermissionDenied('Hak akses Human Capital tidak tersedia.')

    scope_ids = _unit_scope_ids(grants)
    if scope_ids is not None and not scope_ids:
        raise PermissionDenied('Hak akses Human Capital tidak tersedia.')

    target = None
    if unit is not None:
        target = _resolve_active_unit(unit)
        if target is _INVALID_UNIT:
            raise PermissionDenied('Unit kerja tidak tersedia.')
        if scope_ids is not None and target.pk not in scope_ids:
            raise PermissionDenied('Akses Human Capital di luar lingkup unit.')

    if employee is not None and scope_ids is not None:
        employee_unit_ids = _employee_scope_unit_ids(employee)
        if target is not None:
            employee_unit_ids &= {target.pk}
        if not employee_unit_ids & scope_ids:
            raise PermissionDenied('Pegawai di luar lingkup unit.')

    return None
