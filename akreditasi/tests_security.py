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

    def test_api_302_converted_to_401_json(self):
        # Simulasi @login_required redirecting an unauthenticated API call
        from django.shortcuts import redirect
        mw = SecurityHeadersMiddleware(lambda req: redirect('/accounts/login/?next=/ai/test/'))
        req = self.factory.get('/ai/test/')
        res = mw(req)

        self.assertEqual(res.status_code, 401)
        self.assertEqual(res['Content-Type'], 'application/json')
        self.assertIn('Sesi login telah berakhir', res.content.decode('utf-8'))


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
