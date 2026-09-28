from .models import Category, Framework, RumahSakitProfile


def sidebar_context(request):
    framework = Framework.objects.first()
    categories = []
    if framework:
        categories = framework.categories.prefetch_related(
            'items__record'
        ).order_by('order')

    rs_profile = None
    try:
        rs_profile = RumahSakitProfile.get_default()
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
                    # Enrichment: cari Category objects berdasarkan code
                    cat_map = {c.code: c for c in categories}
                    sidebar_unit_standar = []
                    for pokja_code, standar_list in standar_map.items():
                        cat = cat_map.get(pokja_code)
                        sidebar_unit_standar.append({
                            'code': pokja_code,
                            'category': cat,   # bisa None jika pokja belum di-seed
                            'cat_id': cat.id if cat else None,
                            'standar': standar_list,
                        })
        except Exception:
            pass

    return {
        'sidebar_framework': framework,
        'sidebar_categories': categories,
        'rs_profile': rs_profile,
        'sidebar_unit_standar': sidebar_unit_standar,
    }
