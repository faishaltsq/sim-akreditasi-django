from .models import Category, Framework, RumahSakitProfile
from .system_models import SystemConfig
from django.core.cache import cache


KELOMPOK_META = {
    'MANAJEMEN': {'label': 'Manajemen RS', 'icon': 'bi-building-gear', 'color': 'primary'},
    'PELAYANAN': {'label': 'Pelayanan Berfokus Pasien', 'icon': 'bi-heart-pulse', 'color': 'success'},
    'SASARAN_KP': {'label': 'Sasaran Keselamatan Pasien', 'icon': 'bi-shield-check', 'color': 'danger'},
    'PROGNAS': {'label': 'Program Nasional', 'icon': 'bi-flag', 'color': 'warning'},
    'PENDIDIKAN': {'label': 'Integrasi Pendidikan', 'icon': 'bi-mortarboard', 'color': 'info'},
}

_SIDEBAR_CACHE_TTL = 300  # 5 menit
_CATALOGUE_IDENTITY_KEY = 'sidebar_catalogue_identity'
# Short TTL so a catalogue switch that forgets to invalidate self-heals quickly.
_CATALOGUE_IDENTITY_TTL = 60


def invalidate_catalogue_caches():
    """Drop the sidebar's catalogue identity so the next request re-resolves it.

    Call this from every path that changes which catalogue is live. A catalogue
    activation rewrites `lifecycle`/`is_active` in place, so a sidebar keyed only
    on the pk would keep serving the previous edition for the whole TTL.
    """
    cache.delete(_CATALOGUE_IDENTITY_KEY)


def _catalogue_identity():
    """Return a cheap, cacheable identity string for the active catalogue.

    `Framework.active()` introspects the table description on every call, which
    is far too expensive for the per-request sidebar path. The resolved identity
    is therefore cached; a warm request performs no catalogue query at all.
    """
    identity = cache.get(_CATALOGUE_IDENTITY_KEY)
    if identity is not None:
        return identity

    active = Framework.active()
    identity = f'{active.pk}:{active.edition}:{active.version}' if active else 'none'
    cache.set(_CATALOGUE_IDENTITY_KEY, identity, _CATALOGUE_IDENTITY_TTL)
    return identity


def sidebar_context(request):
    # Cache framework + categories global (tidak bergantung user) selama 5 menit.
    # The catalogue identity is cached too: resolving it costs a schema
    # introspection query, and the warm request budget assumes the sidebar
    # performs no catalogue lookups at all.
    version_key = _catalogue_identity()

    framework = cache.get(f'sidebar_framework:{version_key}')
    categories = cache.get(f'sidebar_categories:{version_key}')
    categories_by_kelompok = cache.get(f'sidebar_categories_by_kelompok:{version_key}')

    if framework is None or categories is None:
        framework = Framework.active() if version_key != 'none' else None
        categories = []
        categories_by_kelompok = {}

        if framework:
            categories = list(framework.categories.prefetch_related(
                'items__record'
            ).order_by('order'))

            for code, meta in KELOMPOK_META.items():
                k_cats = [c for c in categories if c.kelompok == code]
                if k_cats:
                    categories_by_kelompok[code] = {
                        'label': meta['label'],
                        'icon': meta['icon'],
                        'color': meta['color'],
                        'categories': k_cats,
                        'count': len(k_cats),
                    }

        cache.set(f'sidebar_framework:{version_key}', framework, _SIDEBAR_CACHE_TTL)
        cache.set(f'sidebar_categories:{version_key}', categories, _SIDEBAR_CACHE_TTL)
        cache.set(
            f'sidebar_categories_by_kelompok:{version_key}',
            categories_by_kelompok, _SIDEBAR_CACHE_TTL,
        )

    # Precompute stat per pokja (2 query total). Tanpa ini, property model
    # (total_score/max_possible_score) menembak 2 query per kategori di setiap
    # render sidebar = 32 query di semua halaman.
    if categories:
        from django.db.models import Count, Sum
        from .models import QualityRecord, StandardItem
        cat_ids = [c.id for c in categories]
        sums = {
            row['standard_item__category']: (row['s'] or 0)
            for row in QualityRecord.objects
            .filter(standard_item__category_id__in=cat_ids)
            .values('standard_item__category').annotate(s=Sum('score'))
        }
        counts = {
            row['category']: row['n']
            for row in StandardItem.objects
            .filter(category_id__in=cat_ids)
            .values('category').annotate(n=Count('id'))
        }
        for c in categories:
            c._pre_total = sums.get(c.id, 0)
            c._pre_max = counts.get(c.id, 0) * 10

    rs_profile = cache.get('sidebar_rs_profile')
    if rs_profile is None:
        try:
            rs_profile = RumahSakitProfile.get_default()
            cache.set('sidebar_rs_profile', rs_profile, _SIDEBAR_CACHE_TTL)
        except Exception:
            pass

    sys_config = cache.get('sidebar_sys_config')
    if sys_config is None:
        try:
            sys_config = SystemConfig.get_solo()
            cache.set('sidebar_sys_config', sys_config, _SIDEBAR_CACHE_TTL)
        except Exception:
            pass

    # Sidebar standar terkait untuk unit-scoped user (Kepala Instalasi, dll)
    sidebar_unit_standar = None
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.is_unit_scoped and profile.unit_kerja:
                unit = profile.unit_kerja
                standar_map = unit.standar_terkait or {}
                if standar_map:
                    cat_map = {c.code: c for c in categories}
                    sidebar_unit_standar = []
                    for pokja_code, standar_list in standar_map.items():
                        cat = cat_map.get(pokja_code)
                        sidebar_unit_standar.append({
                            'code': pokja_code,
                            'category': cat,
                            'cat_id': cat.id if cat else None,
                            'standar': standar_list,
                        })
        except Exception:
            pass

    return {
        'sidebar_framework': framework,
        'sidebar_categories': categories,
        'categories_by_kelompok': categories_by_kelompok,
        'rs_profile': rs_profile,
        'sys_config': sys_config,
        'sidebar_unit_standar': sidebar_unit_standar,
    }
