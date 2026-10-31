"""
Unit scope helper untuk kontrol akses berbasis unit kerja pada aplikasi pasien.
"""

DEFAULT_UNIT_BY_JENIS = {
    'IGD':   'IGD',
    'RAJAL': 'RAJAL',
    'RANAP': 'RANAP',
}


def get_unit_scope(profile):
    """Return set of accessible UnitKerja instances, or None for unlimited (admin)."""
    if profile is None:
        return None
    user = getattr(profile, 'user', None)
    if profile.role in ('SUPER_ADMIN', 'ADMIN_RS', 'DIREKTUR') or getattr(user, 'is_superuser', False):
        return None  # Unrestricted
    if not profile.unit_kerja:
        return set()
    # Include unit_kerja and its descendants if hierarchical
    scope = {profile.unit_kerja}
    if hasattr(profile.unit_kerja, 'get_descendants'):
        scope.update(profile.unit_kerja.get_descendants())
    elif hasattr(profile.unit_kerja, 'children'):
        def collect(u):
            for c in u.children.all():
                if c not in scope:
                    scope.add(c)
                    collect(c)
        collect(profile.unit_kerja)
    return scope


def scope_kunjungan_qs(qs, profile):
    """Batasi queryset KunjunganPasien ke unit dalam scope profil."""
    from django.db.models import Q
    scope = get_unit_scope(profile)
    if scope is None:
        return qs
    if not scope:
        return qs.none()
    scope_codes = {u.code.upper() for u in scope if u.code}
    matching_jenis = [j for j, c in DEFAULT_UNIT_BY_JENIS.items() if any(c.upper() in uc for uc in scope_codes)]
    if matching_jenis:
        return qs.filter(Q(unit_kerja__in=scope) | Q(unit_kerja__isnull=True, jenis_kunjungan__in=matching_jenis))
    return qs.filter(unit_kerja__in=scope)


def scope_pasien_qs(qs, profile):
    """Batasi queryset Pasien ke pasien yang memiliki kunjungan dalam scope profil."""
    from django.db.models import Q
    scope = get_unit_scope(profile)
    if scope is None:
        return qs
    if not scope:
        return qs.none()
    scope_codes = {u.code.upper() for u in scope if u.code}
    matching_jenis = [j for j, c in DEFAULT_UNIT_BY_JENIS.items() if any(c.upper() in uc for uc in scope_codes)]
    if matching_jenis:
        return qs.filter(
            Q(kunjungan__unit_kerja__in=scope) |
            Q(kunjungan__unit_kerja__isnull=True, kunjungan__jenis_kunjungan__in=matching_jenis)
        ).distinct()
    return qs.filter(kunjungan__unit_kerja__in=scope).distinct()
