from .models import Category, Framework


def sidebar_context(request):
    framework = Framework.objects.first()
    categories = []
    if framework:
        categories = framework.categories.prefetch_related(
            'items__record'
        ).order_by('order')
    return {
        'sidebar_framework': framework,
        'sidebar_categories': categories,
    }
