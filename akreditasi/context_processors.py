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

    return {
        'sidebar_framework': framework,
        'sidebar_categories': categories,
        'rs_profile': rs_profile,
    }
