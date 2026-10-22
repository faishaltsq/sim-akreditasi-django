from .models import Category, Framework, RumahSakitProfile, active_framework
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


def sidebar_context(request):
    # Jangan cache instance model. Instance ``Category`` yang di-pickle membawa
    # prefetch ``items`` dan atribut ``_pre_*`` hasil hitung request sebelumnya;
    # begitu PK dipakai ulang (mis. setelah rollback atau reseed), cache
    # menyajikan pokja milik framework lain beserta angka EP yang salah.
    # Yang di-cache hanya penanda framework aktif; kategori selalu dibaca ulang
    # (satu query) supaya angkanya tidak pernah basi.
    framework = active_framework()
    fw_key = framework.pk if framework else 'none'
    if cache.get('sidebar_fw_key') != fw_key:
        cache.set('sidebar_fw_key', fw_key, _SIDEBAR_CACHE_TTL)

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

    # Precompute stat per pokja (3 query total). Tanpa ini, property model
    # (total_score/max_possible_score/ep_selesai) menembak 2-3 query per
    # kategori di setiap render sidebar = 48 query di semua halaman.
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
        # EP yang sudah dinilai: record dengan skor > 0 (skor 0 = belum terpenuhi)
        done = {
            row['standard_item__category']: row['n']
            for row in QualityRecord.objects
            .filter(standard_item__category_id__in=cat_ids, score__gt=0)
            .values('standard_item__category').annotate(n=Count('id'))
        }
        for c in categories:
            c._pre_total = sums.get(c.id, 0)
            c._pre_max = counts.get(c.id, 0) * 10
            c._pre_ep_total = counts.get(c.id, 0)
            c._pre_ep_selesai = done.get(c.id, 0)

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
