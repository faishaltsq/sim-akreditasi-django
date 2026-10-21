"""
Suite pengujian keamanan menyeluruh untuk SIM Akreditasi RS (ARIMA).
Mencakup:
1. Security Headers (CSP, Referrer-Policy, Permissions-Policy, X-Content-Type-Options)
2. Rate Limiting pada API (DeepSeek/AI endpoint & general)
3. Brute-force protection pada login view
4. Query optimization & regression check
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from akreditasi.security_utils import rate_limit
from akreditasi.middleware import SecurityHeadersMiddleware
from accounts.views import RateLimitedLoginView


class SecurityHeadersTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityHeadersMiddleware(lambda req: HttpResponse("OK"))

    def test_security_headers_injected(self):
        request = self.factory.get('/')
        response = self.middleware(request)

        # Content Security Policy
        self.assertIn('Content-Security-Policy', response)
        csp = response['Content-Security-Policy']
        self.assertIn("default-src 'self'", csp)
        self.assertIn("cdn.jsdelivr.net", csp)
        self.assertIn("frame-ancestors 'none'", csp)

        # Referrer Policy
        self.assertEqual(response.get('Referrer-Policy'), 'strict-origin-when-cross-origin')

        # Permissions Policy
        self.assertIn('camera=()', response.get('Permissions-Policy', ''))
        self.assertIn('geolocation=()', response.get('Permissions-Policy', ''))

        # Standard nosniff
        self.assertEqual(response.get('X-Content-Type-Options'), 'nosniff')

    def test_login_redirect_dipertahankan(self):
        """Endpoint /ai/ dan /api/ tetap mengikuti @login_required biasa.

        Middleware ini pernah mengubah redirect ke login menjadi JSON 401,
        tapi itu memutus alur login browser dan membunuh ?next= yang dipakai
        django.contrib.auth untuk kembali ke halaman asal. ai-assist.js sudah
        menangani resp.redirected, jadi perubahannya tidak perlu.
        """
        from django.shortcuts import redirect
        mw = SecurityHeadersMiddleware(lambda req: redirect('/accounts/login/?next=/ai/test/'))
        req = self.factory.get('/ai/test/')
        res = mw(req)

        self.assertEqual(res.status_code, 302)
        self.assertIn('/accounts/login/', res['Location'])
        self.assertIn('next=/ai/test/', res['Location'])
        # header tetap dipasang walau responsnya redirect
        self.assertIn('Content-Security-Policy', res)
        self.assertEqual(res['X-Content-Type-Options'], 'nosniff')


class RateLimiterTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_rate_limit_allows_under_threshold(self):
        @rate_limit(max_calls=3, window=10, scope='test_allow')
        def sample_api(request):
            return JsonResponse({'status': 'ok'})

        request = self.factory.get('/api/test/', REMOTE_ADDR='192.168.1.100')
        res1 = sample_api(request)
        res2 = sample_api(request)

        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)

    def test_rate_limit_blocks_json_over_threshold(self):
        @rate_limit(max_calls=2, window=10, scope='test_block_json')
        def sample_json(request):
            return JsonResponse({'status': 'ok'})

        request = self.factory.get('/ai/generate/', REMOTE_ADDR='192.168.1.101')
        res1 = sample_json(request)
        res2 = sample_json(request)
        res3 = sample_json(request)  # Exceeds limit

        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res3.status_code, 429)
        self.assertIn('Terlalu banyak permintaan', res3.content.decode('utf-8'))

    def test_rate_limit_blocks_html_view(self):
        @rate_limit(max_calls=2, window=10, scope='test_block_html')
        def sample_html(request):
            return HttpResponse("Form")

        request = self.factory.get('/login/', REMOTE_ADDR='192.168.1.102')
        res1 = sample_html(request)
        res2 = sample_html(request)
        res3 = sample_html(request)  # Exceeds limit

        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res3.status_code, 429)
        self.assertIn('Akses Dibatasi Sementara', res3.content.decode('utf-8'))

    def _view(self):
        calls = {'n': 0}

        @rate_limit(max_calls=3, window=60, scope='ip-test')
        def view(request):
            calls['n'] += 1
            return HttpResponse('ok')

        return view, calls

    def test_rate_limit_keys_on_last_xff_hop(self):
        """Spoofed first-hop XFF entries share one bucket keyed on the edge-observed last hop."""
        view, calls = self._view()
        # 3 requests, each with a DIFFERENT spoofed first hop but the same real last hop
        for spoofed in ['6.6.6.6', '7.7.7.7', '8.8.8.8']:
            request = self.factory.get(
                '/api/test/',
                HTTP_X_FORWARDED_FOR=f'{spoofed}, 36.86.50.10',
                REMOTE_ADDR='10.0.0.1',
            )
            response = view(request)
            self.assertEqual(response.status_code, 200)
        # 4th request with yet another spoofed first hop -> throttled (same last-hop bucket)
        request = self.factory.get(
            '/api/test/',
            HTTP_X_FORWARDED_FOR='9.9.9.9, 36.86.50.10',
            REMOTE_ADDR='10.0.0.1',
        )
        self.assertEqual(view(request).status_code, 429)

    def test_extract_client_ip_fallback_chain(self):
        from akreditasi.security_utils import extract_client_ip
        # multi-hop: last hop wins
        r = self.factory.get('/', HTTP_X_FORWARDED_FOR='6.6.6.6, 36.86.50.10', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(extract_client_ip(r), '36.86.50.10')
        # no XFF: X-Real-IP wins
        r = self.factory.get('/', HTTP_X_REAL_IP='36.86.50.11', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(extract_client_ip(r), '36.86.50.11')
        # neither header: REMOTE_ADDR
        r = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        self.assertEqual(extract_client_ip(r), '192.168.1.100')
        # empty XFF string: falls through, must not return ''
        r = self.factory.get('/', HTTP_X_FORWARDED_FOR='', REMOTE_ADDR='10.0.0.2')
        self.assertEqual(extract_client_ip(r), '10.0.0.2')


class AllowedHostsTest(TestCase):
    """A05/A02: foreign Host headers must be rejected with 400 (host-header injection)."""

    def test_foreign_host_rejected(self):
        from django.conf import settings
        self.assertNotIn('.vercel.app', settings.ALLOWED_HOSTS)
        self.assertNotIn('.railway.app', settings.ALLOWED_HOSTS)
        self.assertNotIn('.onrender.com', settings.ALLOWED_HOSTS)
        self.assertNotIn('.pythonanywhere.com', settings.ALLOWED_HOSTS)
        self.assertIn('sim-akreditasi-django.vercel.app', settings.ALLOWED_HOSTS)
        self.assertIn('sim-akreditasi-web-production.up.railway.app', settings.ALLOWED_HOSTS)

    def test_legit_domains_accepted(self):
        for host in ('sim-akreditasi-django.vercel.app',
                     'sim-akreditasi-web-production.up.railway.app'):
            response = self.client.get('/accounts/login/', HTTP_HOST=host, secure=True)
            self.assertNotEqual(response.status_code, 400)


class LoginBruteForceProtectionTest(TestCase):
    def test_login_url_accessible(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('csrfmiddlewaretoken', response.content.decode('utf-8'))

    def test_login_brute_force_triggers_429(self):
        # 8 request diperbolehkan, request ke-9 harus 429
        for i in range(8):
            res = self.client.post(reverse('accounts:login'), {
                'username': 'fakeuser',
                'password': f'wrongpass{i}'
            }, REMOTE_ADDR='10.0.0.99')
            # Login gagal mengembalikan 200 (re-render form dengan error)
            self.assertEqual(res.status_code, 200)

        # Percobaan ke-9
        blocked_res = self.client.post(reverse('accounts:login'), {
            'username': 'fakeuser',
            'password': 'wrongpass9'
        }, REMOTE_ADDR='10.0.0.99')

        self.assertEqual(blocked_res.status_code, 429)
        self.assertIn('Akses Dibatasi Sementara', blocked_res.content.decode('utf-8'))
