"""Permission-filtered Human Capital navigation flags (one query per request)."""
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserProfile
from sdm.models import HcGrant


def granted_capabilities(user, *, today=None):
    """Return the set of capability codes the user holds at least one live grant for."""
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
        return set()

    today = today or timezone.localdate()
    grants = HcGrant.objects.filter(
        user_id=user.pk,
        is_active=True,
        valid_from__lte=today,
        unit_kerja__isnull=False,
        unit_kerja__is_active=True,
    ).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=today)
    ).values_list('capability', flat=True)

    capabilities = set(grants)
    if not capabilities:
        return capabilities

    profile = UserProfile.objects.filter(user_id=user.pk).first()
    if profile is None:
        return capabilities
    return {
        capability
        for capability in capabilities
        if capability.startswith('hc_health_') or profile.has_permission(capability)
    }


def hc_navigation(request):
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return {}

    if not hasattr(request, '_hc_navigation_cache'):
        capabilities = granted_capabilities(user)
        request._hc_navigation_cache = {
            'nav_pegawai': 'can_view_hc' in capabilities,
            'nav_formasi': 'can_plan_hc_workforce' in capabilities,
            'nav_rekrutmen': 'can_manage_hc_recruitment' in capabilities,
            'nav_kredensial': 'can_review_hc_credentials' in capabilities,
            'nav_orientasi': 'can_manage_hc_orientation' in capabilities,
            'nav_kinerja': 'can_manage_hc_appraisals' in capabilities,
            'nav_diklat': 'can_manage_hc_training' in capabilities,
            'nav_k3': 'hc_health_write' in capabilities,
            'nav_analitik': 'can_view_hc_analytics' in capabilities,
        }
    return request._hc_navigation_cache
