"""
Custom Security Middleware untuk SIM Akreditasi RS (ARIMA).
Menambahkan Content-Security-Policy (CSP), Referrer-Policy, dan Permissions-Policy.
"""
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.http import JsonResponse


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Set security headers not covered by Django's default SecurityMiddleware,
    serta memastikan endpoint API (/ai/, /api/) mengembalikan JSON 401 saat sesi kedaluwarsa."""

    def process_response(self, request, response):
        # Jika request API diarahkan (302) ke halaman login karena unauthenticated,
        # ubah menjadi JSON 401 agar frontend tidak menerima HTML tak terduga.
        if response.status_code == 302 and (request.path.startswith('/ai/') or request.path.startswith('/api/')):
            location = response.get('Location', '')
            if 'login' in location:
                return JsonResponse({
                    'success': False,
                    'error': 'Sesi login telah berakhir. Silakan muat ulang halaman atau login kembali.',
                    'authenticated': False
                }, status=401)
        # Content Security Policy — protect against XSS and unauthorized resource loading
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
            "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net",
            "img-src 'self' data: blob: https://*.supabase.co",
            "connect-src 'self' https://*.supabase.co https://cdn.jsdelivr.net",
            "frame-ancestors 'none'",
            "form-action 'self'",
        ]
        
        # Don't overwrite if already set
        if 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = '; '.join(csp_directives)

        if 'Referrer-Policy' not in response:
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        if 'Permissions-Policy' not in response:
            response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        if 'X-Content-Type-Options' not in response:
            response['X-Content-Type-Options'] = 'nosniff'

        return response
