"""Permission-filtered Human Capital navigation flags (one query per request)."""
from django.db import DatabaseError
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserProfile
from sdm.models import HcGrant, Pegawai


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


def _has_linked_pegawai(user):
    """True when the account is bound to an sdm.Pegawai row.

    ``request.user`` is a ``SimpleLazyObject``; a plain ``getattr`` there goes
    through ``__getattr__`` and can miss the reverse ``akun`` descriptor. The
    explicit query is unambiguous and also avoids ``RelatedObjectDoesNotExist``
    (an ``AttributeError`` subclass) leaking out of the descriptor.
    """
    if not getattr(user, 'pk', None):
        return False
    return Pegawai.objects.filter(akun_id=user.pk).exists()


def _is_nakes(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    profile = UserProfile.objects.filter(user_id=user.pk).only('role').first()
    return profile is not None and profile.is_nakes


def hc_navigation(request):
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return {}

    if not hasattr(request, '_hc_navigation_cache'):
        try:
            capabilities = granted_capabilities(user)
            pribadi = _has_linked_pegawai(user) or _is_nakes(user)
        except DatabaseError:
            # This processor runs on every page. During a deploy the new code can
            # serve before migrations finish; a missing sdm table must degrade to
            # "no Human Capital menu", never to a 500 on unrelated pages.
            capabilities = set()
            pribadi = False
        request._hc_navigation_cache = {
            'nav_kredensial_pribadi': pribadi,
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
