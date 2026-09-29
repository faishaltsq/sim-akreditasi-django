from .models import Category, Framework, RumahSakitProfile
from .system_models import SystemConfig


KELOMPOK_META = {
    'MANAJEMEN': {'label': 'Manajemen RS', 'icon': 'bi-building-gear', 'color': 'primary'},
    'PELAYANAN': {'label': 'Pelayanan Berfokus Pasien', 'icon': 'bi-heart-pulse', 'color': 'success'},
    'SASARAN_KP': {'label': 'Sasaran Keselamatan Pasien', 'icon': 'bi-shield-check', 'color': 'danger'},
    'PROGNAS': {'label': 'Program Nasional', 'icon': 'bi-flag', 'color': 'warning'},
    'PENDIDIKAN': {'label': 'Integrasi Pendidikan', 'icon': 'bi-mortarboard', 'color': 'info'},
}


def sidebar_context(request):
    framework = Framework.objects.first()
    categories = []
    categories_by_kelompok = {}

    if framework:
        categories = list(framework.categories.prefetch_related(
            'items__record'
        ).order_by('order'))

        # Kelompokkan kategori untuk sidebar & matriks
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

    rs_profile = None
    try:
        rs_profile = RumahSakitProfile.get_default()
    except Exception:
        pass

    sys_config = None
    try:
        sys_config = SystemConfig.get_solo()
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
