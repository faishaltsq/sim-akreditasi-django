"""Session, cookie and CSRF security tests.

Covers OWASP A07:2021 (Identification and Authentication Failures) and A05:2021
(Security Misconfiguration) for the session layer of SIM Akreditasi.

Sources read before writing these tests:

- ``config/settings.py``: SESSION_COOKIE_HTTPONLY=True, CSRF_COOKIE_HTTPONLY=True,
  SESSION_COOKIE_AGE=28800, SESSION_EXPIRE_AT_BROWSER_CLOSE=True, and (only when
  ``not DEBUG``) SESSION_COOKIE_SECURE/CSRF_COOKIE_SECURE=True plus HSTS.
  ``SESSION_COOKIE_SAMESITE`` is never set.
- ``django/contrib/auth/middleware.py`` ``get_user()``: a cached ``request.user``
  is re-fetched through the session auth hash; when the backend returns ``None``
  (deactivated user) the session is flushed and ``AnonymousUser`` is set.
- ``django/contrib/auth/backends.py`` ``user_can_authenticate()``: returns
  ``user.is_active``, which is what makes the flush above happen.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from akreditasi.tests_utils import DEFAULT_TEST_PASSWORD, login, make_user


class SessionFixationTest(TestCase):
    """The session key must rotate on login, defeating session fixation."""

    def setUp(self):
        self.user = make_user('sesi.fixasi', 'STAF_NAKES')

    def test_session_key_changes_after_login(self):
        """Anonymous session id must not survive authentication."""
        # Establish an anonymous session first.
        self.client.get(reverse('akreditasi:dashboard'))
        anonymous_key = self.client.session.session_key
        self.assertIsNotNone(
            anonymous_key, 'sesi anonim harus terbentuk sebelum login',
        )

        login(self.client, self.user)
        authenticated_key = self.client.session.session_key

        self.assertNotEqual(
            anonymous_key, authenticated_key,
            'ID sesi harus berubah setelah login (Django login() memanggil '
            'cycle_key()); ID yang sama memungkinkan session fixation.',
        )

    def test_pre_login_session_cannot_access_after_logout(self):
        """A captured pre-login key must not be reusable post-logout."""
        self.client.get(reverse('akreditasi:dashboard'))
        anonymous_key = self.client.session.session_key
        login(self.client, self.user)
        self.client.logout()

        self.client.cookies['sessionid'] = anonymous_key
        response = self.client.get(reverse('akreditasi:dashboard'))
        self.assertIn(
            response.status_code, (302, 403),
            'kunci sesi lama tidak boleh memberi akses setelah logout',
        )


class DeactivatedUserLockoutTest(TestCase):
    """is_active=False must terminate an existing session on the next request."""

    def setUp(self):
        self.user = make_user('sesi.nonaktif', 'STAF_NAKES')

    def test_deactivated_user_is_logged_out(self):
        """Django flushes the session when the backend refuses the user."""
        login(self.client, self.user)
        self.assertEqual(
            self.client.get(reverse('akreditasi:dashboard')).status_code, 200,
            'prasyarat: pengguna aktif harus bisa membuka dashboard',
        )

        self.user.is_active = False
        self.user.save(update_fields=['is_active'])

        response = self.client.get(reverse('akreditasi:dashboard'))
        self.assertIn(
            response.status_code, (302, 403),
            'pengguna yang dinonaktifkan harus langsung kehilangan akses',
        )
        if response.status_code == 302:
            self.assertIn('login', response.get('Location', ''))

    def test_deactivated_user_cannot_reauthenticate(self):
        """A deactivated user must not be able to log in again."""
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertFalse(
            self.client.login(
                username=self.user.username, password=DEFAULT_TEST_PASSWORD,
            ),
            'pengguna nonaktif tidak boleh bisa login',
        )


class CookieFlagTest(TestCase):
    """Cookie hardening flags must be present in production mode."""

    def setUp(self):
        self.user = make_user('sesi.cookie', 'STAF_NAKES')

    @override_settings(DEBUG=False, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_secure_flags_on_login_response(self):
        """Secure + HttpOnly must be set on the session cookie when not DEBUG."""
        response = self.client.post(
            reverse('accounts:login'),
            {'username': self.user.username, 'password': DEFAULT_TEST_PASSWORD},
        )
        self.assertIn(response.status_code, (200, 302))

        session_cookie = response.cookies.get('sessionid')
        if session_cookie is None:
            # The cookie may be set on the redirect target instead.
            session_cookie = self.client.cookies.get('sessionid')
        self.assertIsNotNone(session_cookie, 'cookie sessionid harus ada setelah login')

        self.assertTrue(
            session_cookie['secure'],
            'SESSION_COOKIE_SECURE harus aktif saat DEBUG=False',
        )
        self.assertTrue(
            session_cookie['httponly'],
            'SESSION_COOKIE_HTTPONLY harus aktif',
        )

    @override_settings(DEBUG=False)
    def test_samesite_is_explicitly_strict(self):
        """SESSION_COOKIE_SAMESITE is unset — Django defaults to 'Lax'.

        'Lax' still sends the session cookie on top-level cross-site GET
        navigations, which is the exact vector a CSRF/Lax-bypass chain needs.
        The hardened value is 'Strict'.
        """
        from django.conf import settings as conf

        configured = conf.SESSION_COOKIE_SAMESITE
        if configured != 'Strict':
            self.fail(
                'KONFIGURASI COOKIE LEMAH (A05): SESSION_COOKIE_SAMESITE '
                f'bernilai {configured!r}, bukan \'Strict\'. config/settings.py '
                'tidak pernah menetapkan SESSION_COOKIE_SAMESITE maupun '
                'CSRF_COOKIE_SAMESITE, sehingga Django memakai default \'Lax\'. '
                'Dengan \'Lax\', cookie sesi tetap dikirim pada navigasi GET '
                'lintas situs tingkat atas, yang cukup untuk rantai '
                'CSRF/Lax-bypass. Perbaikan: set SESSION_COOKIE_SAMESITE = '
                '\'Strict\' dan CSRF_COOKIE_SAMESITE = \'Strict\'.'
            )
        self.assertEqual(configured, 'Strict')

    def test_session_age_is_bounded(self):
        """Pinning the 8-hour session lifetime that does exist."""
        from django.conf import settings as conf

        self.assertEqual(conf.SESSION_COOKIE_AGE, 28800)
        self.assertTrue(conf.SESSION_EXPIRE_AT_BROWSER_CLOSE)


class CsrfEnforcementTest(TestCase):
    """CsrfViewMiddleware must reject state-changing POSTs without a token."""

    def setUp(self):
        self.admin = make_user('csrf.admin', 'ADMIN_RS')

    def test_post_without_token_is_rejected(self):
        """A POST with no CSRF token must not mutate state."""
        login(self.client, self.admin)
        # enforce_csrf_checks is off by default in the test client, so build a
        # client that actually enforces CSRF.
        from django.test import Client

        enforcing = Client(enforce_csrf_checks=True)
        enforcing.force_login(self.admin)
        response = enforcing.post(
            reverse('accounts:user_delete', args=[self.admin.id]),
        )
        self.assertEqual(
            response.status_code, 403,
            'POST tanpa token CSRF harus ditolak 403 oleh CsrfViewMiddleware',
        )

    def test_no_view_is_csrf_exempt(self):
        """No view in the repo may be decorated @csrf_exempt."""
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parent.parent
        this_file = pathlib.Path(__file__).resolve()
        offenders = []
        pattern = re.compile(r'csrf_exempt')
        for path in root.rglob('*.py'):
            if any(part in {'.venv', '.worktrees', 'migrations', '__pycache__'}
                   for part in path.parts):
                continue
            if path.resolve() == this_file:
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line) and not line.lstrip().startswith('#'):
                    offenders.append(f'{path.relative_to(root)}:{lineno}')

        if offenders:
            self.fail(
                'CSRF DIMATIKAN: ditemukan dekorator @csrf_exempt pada '
                f'{", ".join(offenders)}. Setiap view yang menonaktifkan '
                'perlindungan CSRF membuka jalur serangan cross-site request '
                'forgery terhadap aksi yang mengubah status. Perbaikan: hapus '
                '@csrf_exempt dan kirim token CSRF dari klien.'
            )
        self.assertEqual(offenders, [])

    def test_csrf_cookie_is_httponly(self):
        """Pinning CSRF_COOKIE_HTTPONLY=True from settings."""
        from django.conf import settings as conf

        self.assertTrue(conf.CSRF_COOKIE_HTTPONLY)
        self.assertTrue(conf.SESSION_COOKIE_HTTPONLY)
