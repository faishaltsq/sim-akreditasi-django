"""Pembuatan dan pencabutan HcGrant sesuai aturan ``sdm.akses``.

Aturan otorisasi tetap di ``sdm/akses.py``; modul ini hanya menyediakan cara
membuat grant yang sudah memenuhi aturan tersebut (aktif, berlaku, dan izin
role menyala).
"""
from django.db import transaction
from django.utils import timezone

from accounts.models import RolePermissionConfig
from sdm.models import HcGrant
from sdm.models.akses import HC_CAPABILITY_CHOICES

VALID_CAPABILITIES = dict(HC_CAPABILITY_CHOICES)


def pemberi_akses(user):
    """Return user bila berhak memberi grant, selain itu None."""
    if not getattr(user, 'is_authenticated', False):
        return None
    if user.is_superuser:
        return user
    profile = getattr(user, 'profile', None)
    if profile is not None and profile.has_permission('can_manage_users'):
        return user
    return None


def sinkronkan_grant(user, *, capabilities, unit=None, include_descendants=False,
                     valid_until=None, actor=None):
    """Selaraskan grant user pada satu lingkup dengan ``capabilities``.

    Hanya grant pada lingkup ``unit`` yang disentuh. Return ``(added, removed)``.
    """
    capabilities = {cap for cap in capabilities if cap in VALID_CAPABILITIES}
    scope = {'unit_kerja__isnull': True} if unit is None else {'unit_kerja_id': unit.pk}

    added = removed = 0
    with transaction.atomic():
        live = list(
            HcGrant.objects.filter(user=user, is_active=True, **scope)
            .select_related('unit_kerja')
        )
        by_capability = {}
        for grant in live:
            by_capability.setdefault(grant.capability, grant)

        to_disable = []
        to_update = []
        for capability, grant in by_capability.items():
            if capability not in capabilities:
                grant.is_active = False
                to_disable.append(grant)
                continue
            if (grant.include_descendants != include_descendants
                    or grant.valid_until != valid_until):
                grant.include_descendants = include_descendants
                grant.valid_until = valid_until
                to_update.append(grant)

        to_create = [
            HcGrant(
                user=user,
                capability=capability,
                unit_kerja=unit,
                include_descendants=include_descendants,
                valid_from=timezone.localdate(),
                valid_until=valid_until,
                is_active=True,
                granted_by=actor,
            )
            for capability in capabilities
            if capability not in by_capability
        ]

        if to_disable:
            HcGrant.objects.filter(pk__in=[g.pk for g in to_disable]).update(is_active=False)
        for grant in to_update:
            grant.save(update_fields=['include_descendants', 'valid_until'])
        if to_create:
            HcGrant.objects.bulk_create(to_create)

        added = len(to_create)
        removed = len(to_disable)

    return added, removed


def aktifkan_role_untuk(user, capabilities):
    """Nyalakan izin role untuk ``capabilities``; return himpunan yang diubah.

    Kapabilitas ``hc_health_*`` dilewati: gate-nya di ``_active_grants`` tidak
    memakai izin role.
    """
    profile = getattr(user, 'profile', None)
    if profile is None:
        return set()

    enabled = {
        cap for cap in capabilities
        if cap in VALID_CAPABILITIES and not cap.startswith('hc_health_')
    }
    if not enabled:
        return set()

    cfg = RolePermissionConfig.get_config_for_role(profile.role)
    fields = [cap for cap in enabled if hasattr(cfg, cap)]
    for field in fields:
        setattr(cfg, field, True)
    if fields:
        cfg.save(update_fields=fields + ['updated_at'])
    return set(fields)
