"""Regresi 403 login mobile: POST duplikat (double-tap) tidak boleh menampilkan 403.

Skenario nyata dari log Vercel production arima.web.id:
  1. GET  /accounts/login/          -> 200 (form + token CSRF dibuat)
  2. POST /accounts/login/ (token1) -> 302 login sukses, token diputar
  3. POST /accounts/login/ (token1, dikirim ulang browser HP) -> middleware
     menolak token basi. custom_csrf_failure harus mengarahkan user yang
     sudah terautentikasi ke dashboard, BUKAN halaman 403 Django.

Tanpa session/login 403 tetap wajar (jalur Django default dipertahankan).
"""
from django.test import TestCase, Client
from django.urls import reverse

from django.contrib.auth.models import User


class DoubleSubmitLoginCsrfTests(TestCase):
    def setUp(self):
        self.credentials = {
            'username': 'siska',
            'password': 'rahasia-kuat-123',
        }
        self.user = User.objects.create_user(**self.credentials)
        self.client = Client(enforce_csrf_checks=True)

    def _login_page_token(self):
        """GET form login, ekstrak csrfmiddlewaretoken dari HTML."""
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        import re
        m = re.search(
            r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']',
            html,
        )
        self.assertIsNotNone(m, 'csrfmiddlewaretoken tidak ditemukan di form')
        return m.group(1)

    def test_second_post_after_successful_login_redirects_to_dashboard(self):
        token = self._login_page_token()

        first = self.client.post(
            reverse('accounts:login'),
            {**self.credentials, 'csrfmiddlewaretoken': token},
        )
        # Login pertama harus sukses (302) dan session terbentuk
        self.assertEqual(first.status_code, 302)
        self.assertTrue('_auth_user_id' in self.client.session)

        # POST kedua dengan token lama (double-tap) -> redirect dashboard, bukan 403
        second = self.client.post(
            reverse('accounts:login'),
            {**self.credentials, 'csrfmiddlewaretoken': token},
        )
        self.assertEqual(second.status_code, 302)
        self.assertEqual(second['Location'], '/control/')
        self.assertNotIn(
            b'CSRF', second.content,
            'Respons double-submit tidak boleh berisi halaman 403 CSRF',
        )

    def test_anonymous_invalid_csrf_login_still_returns_403(self):
        """Tanpa session login, POST dengan token salah tetap 403 (keamanan)."""
        self.client.get(reverse('accounts:login'))
        resp = self.client.post(
            reverse('accounts:login'),
            {
                **self.credentials,
                'csrfmiddlewaretoken': 'token-palsu-tidak-valid',
            },
        )
        self.assertEqual(resp.status_code, 403)

    def test_authenticated_post_with_stale_token_on_other_page_not_redirected(self):
        """Jalur redirect hanya untuk /accounts/login/; halaman lain tetap 403 default."""
        token = self._login_page_token()
        self.client.post(
            reverse('accounts:login'),
            {**self.credentials, 'csrfmiddlewaretoken': token},
        )
        stale_resp = self.client.post(
            '/insiden/lapor/',
            {'csrfmiddlewaretoken': 'token-basi'},
        )
        self.assertEqual(stale_resp.status_code, 403)
