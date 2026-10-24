"""Selected-framework read context and central catalogue-write guard (Track C).

This module hardens edition-scoped access across the whole application:

* ``resolve_catalogue(user, *, framework_id=None)`` resolves the Framework the
  current request/operation should operate against: either an explicit permitted
  archive selection, or the validated active catalogue. Malformed/unknown input
  fails closed — there is never an unscoped fallback.
* ``require_catalogue_write(user, *, item, operation)`` is the single gate every
  catalogue mutation (score, edit, create, delete, upload, link, unlink,
  auto-score) must pass before touching rows, files or audit state. It rejects
  writes to archived/staged catalogues even for SUPER_ADMIN, and reuses the
  existing role/unit permission model.

UI text is Bahasa Indonesia. A target/accreditation year is not the instrument
edition; edition identity lives on ``Framework.edition`` / ``Framework.lifecycle``.
"""

import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError

from .models import (
    Category,
    EvidenceFile,
    EvidenceReq,
    Framework,
    QualityRecord,
    StandardItem,
)

logger = logging.getLogger(__name__)

# Operations that mutate catalogue-backed data and therefore require an ACTIVE
# edition plus existing role/unit permission.
MUTATING_OPERATIONS = frozenset({
    'score', 'edit', 'create', 'delete', 'upload', 'link', 'unlink', 'auto_score',
})

# Read-only operations permitted on an archived (readable) catalogue.
READ_ONLY_OPERATIONS = frozenset({'view', 'export', 'detail', 'list'})


def _framework_for_item(item):
    """Walk the FK chain from a catalogue-backed item to its Framework.

    Returns ``None`` when the item is detached (no framework reachable).
    """
    if item is None:
        return None
    if isinstance(item, Framework):
        return item
    if isinstance(item, Category):
        return getattr(item, 'framework', None)
    if isinstance(item, StandardItem):
        cat = getattr(item, 'category', None)
        return getattr(cat, 'framework', None) if cat is not None else None
    if isinstance(item, QualityRecord):
        si = getattr(item, 'standard_item', None)
        if si is None:
            return None
        cat = getattr(si, 'category', None)
        return getattr(cat, 'framework', None) if cat is not None else None
    if isinstance(item, EvidenceFile):
        req = getattr(item, 'requirement', None)
        if req is None:
            return None
        si = getattr(req, 'standard_item', None)
        if si is None:
            return None
        cat = getattr(si, 'category', None)
        return getattr(cat, 'framework', None) if cat is not None else None
    if isinstance(item, EvidenceReq):
        si = getattr(item, 'standard_item', None)
        if si is None:
            return None
        cat = getattr(si, 'category', None)
        return getattr(cat, 'framework', None) if cat is not None else None

    # Generic fallback: walk common catalogue FK attributes.
    for attr in ('category', 'standard_item', 'requirement', 'framework'):
        child = getattr(item, attr, None)
        if child is None:
            continue
        fw = _framework_for_item(child)
        if fw is not None:
            return fw
    return None


def _user_role(user):
    """Best-effort role string for the user, mirroring accounts.UserProfile."""
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None
    return getattr(profile, 'role', None)


def _user_unit(user):
    """Best-effort linked unit kerja for the user."""
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None
    return getattr(profile, 'unit_kerja', None)


def _user_can_write_on_active(user, fw, item, operation):
    """Existing role/unit permission model applied to an ACTIVE framework.

    Mirrors views._can_modify_ep so behaviour is identical to the pre-Track-C
    shortcuts, but centralized here and applied uniformly.
    """
    if not user or not user.is_authenticated:
        return False
    # Superuser / SUPER_ADMIN always may write on an ACTIVE catalogue.
    if getattr(user, 'is_superuser', False):
        return True
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    role = getattr(profile, 'role', None)
    if role == 'SUPER_ADMIN':
        return True

    # Admin RS / coordinator / surveyor may edit their in-scope EPs.
    admin_roles = ('SUPER_ADMIN', 'ADMIN_RS', 'SURVEYOR_INTERNAL', 'KOORDINATOR_POKJA')
    if role in admin_roles:
        # Unit-scoped admins are still bounded by standar_terkait.
        if getattr(profile, 'is_unit_scoped', False) and getattr(profile, 'unit_kerja', None):
            return _unit_scoped_allows(user, item)
        return True

    # Other roles (KEPALA_UNIT, STAF_NAKES, ASESOR): unit-scoped mapping only.
    if getattr(profile, 'is_unit_scoped', False) and getattr(profile, 'unit_kerja', None):
        return _unit_scoped_allows(user, item)

    return False


def _unit_scoped_allows(user, item):
    """Unit-scoped user may write only when the item's category is in
    the unit's ``standar_terkait`` mapping (and sub-standard allowed)."""
    profile = getattr(user, 'profile', None)
    unit = getattr(profile, 'unit_kerja', None) if profile is not None else None
    if unit is None:
        return False
    mapping = getattr(unit, 'standar_terkait', None) or {}
    standard_item = None
    if isinstance(item, StandardItem):
        standard_item = item
    elif isinstance(item, QualityRecord):
        standard_item = getattr(item, 'standard_item', None)
    elif isinstance(item, EvidenceFile):
        req = getattr(item, 'requirement', None)
        standard_item = getattr(req, 'standard_item', None) if req is not None else None
    elif isinstance(item, EvidenceReq):
        standard_item = getattr(item, 'standard_item', None)
    if standard_item is None or not getattr(standard_item, 'category_id', None):
        return False
    cat_code = standard_item.category.code
    if cat_code not in mapping:
        return False
    allowed_subs = mapping[cat_code]
    if not allowed_subs:
        return True
    return getattr(standard_item, 'sub_standard', None) in allowed_subs


def resolve_catalogue(user, *, framework_id=None):
    """Resolve the Framework for the current request.

    Parameters
    ----------
    user:
        The requesting user (used only to decide whether an archived framework
        may be selected explicitly; archive reads stay permitted).
    framework_id:
        Explicit primary key of a framework. When given, that exact framework is
        returned (permitted archive selection or active selection). Malformed or
        unknown input fails closed — there is no fallback.

    Returns
    -------
    Framework

    Raises
    ------
    Framework.DoesNotExist
        When ``framework_id`` is given but no such framework exists.
    PermissionDenied
        When no active catalogue exists and no explicit id was given (no
        unscoped fallback).
    ValueError
        When ``framework_id`` is not a valid primary key.
    """
    if framework_id is not None:
        try:
            fw = Framework.objects.get(pk=framework_id)
        except (ValueError, ValidationError):
            raise ValueError(f"ID katalog tidak valid: {framework_id!r}")
        except Framework.DoesNotExist:
            raise Framework.DoesNotExist(
                f"Katalog dengan id {framework_id!r} tidak ditemukan."
            )
        # Explicit selection: active or archived are both readable. Staged
        # (DRAFT/VALIDATED) candidates are not readable through this path.
        if fw.lifecycle not in ('ACTIVE', 'ARCHIVED'):
            raise PermissionDenied(
                f"Katalog '{fw.name}' masih dalam tahap staging ({fw.lifecycle}); "
                "tidak boleh dipilih melalui resolver ini."
            )
        return fw

    # No explicit id → the validated active catalogue, no unscoped fallback.
    active = Framework.active()
    if active is None:
        raise PermissionDenied(
            "Tidak ada katalog aktif (lifecycle=ACTIVE). Tidak ada fallback "
            "tanpa cakupan; pilih katalog secara eksplisit atau aktifkan "
            "katalog melalui cutover yang direview."
        )
    return active


def require_catalogue_write(user, *, item, operation):
    """Central gate before every catalogue mutation.

    Checks lifecycle (must be ACTIVE) plus the existing role/unit permission.
    Rejects archived/staged writes before any row/file/audit is touched —
    including for SUPER_ADMIN. ``operation`` is one of ``MUTATING_OPERATIONS``
    and is recorded in the denial message/audit trail.

    Raises
    ------
    PermissionDenied
        When the write is not permitted.
    ValueError
        When ``operation`` is not a recognised mutating operation or the item
        cannot be resolved to a catalogue.
    """
    if operation not in MUTATING_OPERATIONS:
        raise ValueError(
            f"Operasi katalog tidak dikenal: {operation!r}. "
            f"Gunakan salah satu: {sorted(MUTATING_OPERATIONS)}"
        )

    fw = _framework_for_item(item)
    if fw is None:
        raise PermissionDenied(
            "Tidak dapat menentukan katalog untuk item ini; operasi dibatalkan."
        )

    # Lifecycle guard: only the ACTIVE edition may be written. Archived and
    # staged catalogues are read-only for every role, including SUPER_ADMIN.
    if fw.lifecycle != 'ACTIVE':
        logger.warning(
            "Catalogue write rejected: user=%s operation=%s framework=%s lifecycle=%s",
            getattr(user, 'username', None), operation, fw.pk, fw.lifecycle,
        )
        raise PermissionDenied(
            f"Katalog '{fw.name}' tidak dapat ditulis (status: {fw.get_lifecycle_display()}). "
            f"Operasi '{operation}' hanya diizinkan pada katalog AKTIF."
        )

    # Existing role/unit permission.
    if not _user_can_write_on_active(user, fw, item, operation):
        logger.warning(
            "Catalogue write rejected (authorization): user=%s role=%s operation=%s framework=%s",
            getattr(user, 'username', None), _user_role(user), operation, fw.pk,
        )
        raise PermissionDenied(
            f"Akses ditolak: EP berada di luar cakupan unit Anda untuk operasi '{operation}'."
        )

    return None
