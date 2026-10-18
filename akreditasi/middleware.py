"""
Custom Security Middleware untuk SIM Akreditasi RS (ARIMA).
Menambahkan Content-Security-Policy (CSP), Referrer-Policy, dan Permissions-Policy.
"""
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Set security headers not covered by Django's default SecurityMiddleware."""

    def process_response(self, request, response):
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
