"""
Decorator untuk kontrol akses modul Manajemen Pasien berdasarkan unit kerja & profesi user.
"""
from functools import wraps
from django.core.exceptions import PermissionDenied


def require_patient_module(module_name):
    """
    Decorator untuk view pasien. Cek apakah user memiliki akses ke modul tertentu
    ('igd', 'rajal', 'pendaftaran', 'ranap', 'farmasi', 'laboratorium', 'master_pasien', 'riwayat').
    Jika tidak, raise PermissionDenied (HTTP 403).
    SUPER_ADMIN / ADMIN_RS / DIREKTUR selalu diizinkan.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.conf import settings
                from django.shortcuts import redirect
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")

            allowed = request.user.profile.get_allowed_patient_modules()
            if module_name not in allowed:
                raise PermissionDenied(
                    f"Akses ditolak: Unit kerja Anda tidak memiliki wewenang untuk modul '{module_name}'."
                )
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
