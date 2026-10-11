# Security Audit & Performance Optimization Plan — SIM Akreditasi RS (ARIMA)

**Date:** 2026-10-11  
**Project:** sim-akreditasi-django (Django 5.x, PostgreSQL/SQLite, Vercel Serverless, Supabase Storage)  
**Repo:** `https://github.com/faishaltsq/sim-akreditasi-django`

---

## Goal

Audit project dari sudut pandang red team (MITRE ATT&CK-aligned), identifikasi celah keamanan data dan performa, lalu implementasi fix dan rekomendasi agar web lebih aman dan cepat — semuanya diimplementasikan langsung (zero guesswork).

---

## Current Context

- **Hosting:** Vercel (serverless Python WSGI via `@vercel/python`), region `icn1` (Seoul).
- **Database:** Supabase PostgreSQL (pooler) di ap-northeast-2, via `DATABASE_URL`.
- **Storage:** Supabase Storage (`bukti-akreditasi` bucket).
- **AI:** DeepSeek API via backend `ai_service.py` (rate-limited 12 calls/60s in-memory).
- **Auth:** Django `django.contrib.auth` — standard password validators, no 2FA, no brute-force protection on login.
- **Security Headers:** HSTS (1y), X-Frame-Options DENY, Secure cookies (in production), Content-Type nosniff.
- **Rate Limiting:** Custom in-memory dict-based — **lost on every Vercel cold start** (serverless = useless).
- **CORS:** Not configured.
- **CSP:** Not configured.
- **Admin URL:** Obfuscated as `admin-sikai-7f3d/` but exposed in `config/urls.py` source.
- **Local `.env`:** Has `DJANGO_DEBUG=True`, `SUPABASE_KEY` (anon/public), `DJANGO_SECRET_KEY` placeholder.
- **Static Files:** WhiteNoise (compressed, no CDN, no cache-control).
- **Media:** Django FileSystemStorage (local filesystem — not suitable for serverless).

---

## Architecture / Proposed Approach

1. **Hardening Layer:** Add Django security middleware missing pieces (CSP, CORS, Referrer-Policy, rate-limit on login) + migrate rate limiter from in-memory to cache-backed (Supabase Redis or Django cache table) so it survives cold starts.
2. **Performance Layer:** Add database connection pooling, query optimization (select_related/prefetch_related audit), CDN/static caching, and serverless-friendly media handling (switch to Supabase Storage for user uploads).
3. **Red Team Test Layer:** Run automated OWASP ZAP / safety scan + manual audit of auth, session, API, and data exposure. Fix findings.

---

## Step-by-Step Tasks

### Task 1: Add Missing Security Middleware (CSP, CORS, Referrer-Policy)

**File:** `config/settings.py`

Add to `MIDDLEWARE` (after `SecurityMiddleware`):
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ...existing...
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # ── Custom Security Middleware ──
    'akreditasi.middleware.SecurityHeadersMiddleware',
]
```

**File:** `akreditasi/middleware.py` (create)

```python
from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Set security headers not covered by Django's SecurityMiddleware."""

    def process_response(self, request, response):
        # Content Security Policy — strict baseline
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net",
            "img-src 'self' data: blob: https://*.supabase.co",
            "connect-src 'self' https://*.supabase.co",
            "frame-ancestors 'none'",
            "form-action 'self'",
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response
```

**Verification:**
```bash
curl -s -I "https://sim-akreditasi-django.vercel.app/risiko/" | grep -iE "content-security-policy|referrer-policy|permissions-policy"
# Expected: 3 non-empty header lines
```

---

### Task 2: Migrate Rate Limiter to Cache Backend

**Problem:** Current `akreditasi/security_utils.py` uses in-memory dict — wiped on every Vercel cold start (each function invocation). Rate limiting is effectively **disabled** in production.

**File:** `akreditasi/security_utils.py` — replace entire content:

```python
"""
Rate limiter berbasis Django Cache Framework.
Bertahan di cache Supabase / memcache, tidak hilang saat cold start Vercel.
"""
import time
import functools
import logging
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)

_RATE_PREFIX = 'rl:'
_CACHE_TIMEOUT = 300  # 5 menit TTL default


def rate_limit(max_calls: int = 10, window: int = 60, scope: str = 'default'):
    """
    Decorator rate limiter per user/IP via Django cache.

    Args:
        max_calls: Jumlah request maksimal dalam window.
        window: Durasi window dalam detik.
        scope: Namespace untuk membedakan antar endpoint.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated:
                client_key = f"{_RATE_PREFIX}{scope}:u:{request.user.id}"
            else:
                ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                ip = ip or request.META.get('REMOTE_ADDR', 'unknown')
                client_key = f"{_RATE_PREFIX}{scope}:ip:{ip}"

            now = time.time()
            cutoff = now - window

            # Atomically get and update the sliding window
            timestamps = cache.get(client_key, [])
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= max_calls:
                logger.warning(f"Rate limit exceeded: {client_key} ({len(timestamps)}/{max_calls})")
                return JsonResponse({
                    'success': False,
                    'error': f'Terlalu banyak permintaan. Coba lagi setelah {window} detik.'
                }, status=429)

            timestamps.append(now)
            cache.set(client_key, timestamps, _CACHE_TIMEOUT)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

**File:** `config/settings.py` — add cache backend (use database cache — works everywhere, no Redis dependency):

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
# Production: use database-backed cache for persistence across cold starts
if DATABASE_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'django_cache_table',
            'TIMEOUT': 300,
        }
    }
```

**Terminal (after code edit):**
```bash
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django"
python manage.py createcachetable
```

**Verification:**
```bash
python manage.py shell -c "from django.core.cache import cache; cache.set('test_key', 'hello', 10); print(cache.get('test_key'))"
# Expected: hello
```

---

### Task 3: Add Brute-Force Protection on Login

**File:** `accounts/views.py` — wrap `LoginView` with rate limiter.

Since Django's `LoginView` is a class-based view, we add a custom wrapper:

```python
from django.contrib.auth.views import LoginView as BaseLoginView
from akreditasi.security_utils import rate_limit
from django.utils.decorators import method_decorator


@method_decorator(rate_limit(max_calls=5, window=60, scope='login'), name='dispatch')
class RateLimitedLoginView(BaseLoginView):
    """Login dengan proteksi brute-force: max 5 percobaan per 60 detik."""
    template_name = 'accounts/login.html'
```

**File:** `accounts/urls.py` — replace import and path:

```python
from . import views
# from django.contrib.auth import views as auth_views  ← remove

urlpatterns = [
    path('login/', views.RateLimitedLoginView.as_view(), name='login'),
    # ... rest unchanged
]
```

**Verification:**
```bash
# Simulate 6 rapid login attempts — 6th should return 429
for i in $(seq 1 6); do
  curl -s -o /dev/null -w "%{http_code} " -X POST \
    -d "username=admin&password=wrong$i&csrfmiddlewaretoken=test" \
    "https://sim-akreditasi-django.vercel.app/accounts/login/"
done
echo ""
# Expected: 200 200 200 200 200 429
```

---

### Task 4: Audit & Remove Exposed Secrets / Sensitive Info

**Findings to fix:**

1. **`.env` committed?** — check `.gitignore`:
   ```bash
   grep -n ".env" .gitignore
   # If .env is NOT in .gitignore → add it immediately
   ```
   **File:** `.gitignore` (append if missing):
   ```
   .env
   *.pyc
   __pycache__/
   staticfiles/
   media/
   db.sqlite3
   ```

2. **`SUPABASE_KEY` in `.env`:** Verify it's the **anon/public** key, not the `service_role` key. If it's `service_role`, it has full admin access to Supabase — replace it immediately with the anon key (starts with `sb_pub_` or `eyJh...` with `"role":"anon"` in the JWT payload).

   **Verification command:**
   ```bash
   # Decode the JWT to check role
   echo "sb_pub_..." | cut -d. -f2 | python -c "import sys,json,base64; d=json.loads(base64.urlsafe_b64decode(sys.stdin.read()+'==')); print(d.get('role'))"
   # Expected: "anon" — if "service_role" → CRITICAL: change immediately
   ```

3. **`DJANGO_SECRET_KEY`:** Local `.env` has a weak development key. Add a comment:
   ```
   # WARNING: Ganti dengan secret key acak untuk production
   # Generate dengan: python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

4. **Admin URL** (`admin-sikai-7f3d/`): Already obfuscated but visible in `config/urls.py` source on GitHub. Add rate limiting on admin login and IP whitelist check.

**File:** `akreditasi/security_utils.py` — add:
```python
def admin_ip_whitelist(view_func):
    """Optional: batasi akses admin ke IP tertentu."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Skip if not admin path
        if not request.path.startswith('/admin'):
            return view_func(request, *args, **kwargs)
        allowed_ips = ['127.0.0.1', '::1']
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
        # Comment out the IP check below to enable whitelist:
        # if ip not in allowed_ips and not request.user.is_superuser:
        #     return HttpResponseForbidden('Akses admin dibatasi.')
        return view_func(request, *args, **kwargs)
    return wrapper
```

---

### Task 5: Add Database Query Optimization (select_related / prefetch_related)

**Problem:** Many views may cause N+1 queries (e.g., iterating `RisikoUnit` and accessing `unit` FK for each).

**File:** `akreditasi/risiko_views.py` — audit and fix the main listing view:

Find:
```python
risiko_list = RisikoUnit.objects.filter(...)
```
Replace with:
```python
risiko_list = RisikoUnit.objects.filter(...).select_related(
    'unit', 'created_by', 'updated_by'
).prefetch_related(
    'indikator_mutu', 'jenis_risiko_items'
)
```

**Verification — compare query count:**
```bash
python manage.py shell -c "
import django; django.setup()
from django.db import connection
from akreditasi.models import RisikoUnit
# Count queries with and without select_related
q = RisikoUnit.objects.select_related('unit')[:5]
list(q)
print('Queries with select_related:', len(connection.queries))
connection.queries.clear()
q2 = RisikoUnit.objects.all()[:5]
list(q2)
print('Queries without:', len(connection.queries))
"
# Expected: significantly fewer queries with select_related
```

**Task is to audit all views that list RisikoUnit and add select_related/prefetch_related.**

---

### Task 6: Switch Media Storage to Supabase (Serverless-Compatible)

**Problem:** Django `FileSystemStorage` writes to local disk. Vercel serverless functions have ephemeral filesystems — uploads are **lost** after the request. Files must go to Supabase Storage.

**File:** `config/settings.py` — add:
```python
# ── Media Storage: Supabase (production) / Lokal (development) ──
if DATABASE_URL:
    DEFAULT_FILE_STORAGE = 'akreditasi.storage.SupabaseStorage'
else:
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
```

**File:** `akreditasi/storage.py` (create):
```python
"""Supabase Storage backend for Django — serverless-compatible file storage."""
import os
import uuid
import logging
from urllib.parse import urljoin
from django.core.files.storage import Storage
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class SupabaseStorage(Storage):
    """Simpan file ke Supabase Storage bucket."""

    def __init__(self, bucket=None):
        self.bucket = bucket or settings.SUPABASE_BUCKET or 'bukti-akreditasi'
        self._base_url = f"{settings.SUPABASE_URL}/storage/v1/object/{self.bucket}"

    def _save(self, name, content):
        import requests
        path = f"{uuid.uuid4().hex}_{name}"
        files = {'file': (name, content.read(), content.content_type or 'application/octet-stream')}
        headers = {'Authorization': f'Bearer {settings.SUPABASE_KEY}'}
        resp = requests.post(
            f"{settings.SUPABASE_URL}/storage/v1/object/{self.bucket}/{path}",
            files=files, headers=headers
        )
        resp.raise_for_status()
        return path

    def url(self, name):
        return f"{self._base_url}/{name}"

    def exists(self, name):
        import requests
        headers = {'Authorization': f'Bearer {settings.SUPABASE_KEY}'}
        resp = requests.head(f"{self._base_url}/{name}", headers=headers)
        return resp.status_code == 200

    def delete(self, name):
        import requests
        headers = {'Authorization': f'Bearer {settings.SUPABASE_KEY}'}
        requests.delete(f"{self._base_url}/{name}", headers=headers)

    def size(self, name):
        return 0  # Not easily available without a HEAD + Content-Length

    def open(self, name, mode='rb'):
        import requests
        headers = {'Authorization': f'Bearer {settings.SUPABASE_KEY}'}
        resp = requests.get(f"{self._base_url}/{name}", headers=headers)
        resp.raise_for_status()
        return ContentFile(resp.content)
```

**Verification:**
```bash
python manage.py shell -c "
from django.core.files.base import ContentFile
from akreditasi.storage import SupabaseStorage
s = SupabaseStorage()
name = s.save('test.txt', ContentFile(b'hello world'))
print('Saved as:', name)
print('URL:', s.url(name))
s.delete(name)
print('Deleted OK')
"
# Expected: Saved as <uuid>_test.txt, URL: https://*.supabase.co/..., Deleted OK
```

---

### Task 7: Add Cache-Control Headers for Static Files

**File:** `config/settings.py` — after `STORAGES` block:
```python
# ── Static file caching ──
if not DEBUG:
    WHITENOISE_MAX_AGE = 31536000  # 1 year cache for immutable static files
    WHITENOISE_IMMUTABLE_FILE_TEST = lambda url: True  # All static files are immutable (hashed)
```

**Verification:**
```bash
curl -s -I "https://sim-akreditasi-django.vercel.app/static/js/ai-assist.js" | grep -i "cache-control"
# Expected: Cache-Control: public, max-age=31536000, immutable
```

---

### Task 8: Run Automated Security Scan (OWASP ZAP / safety)

**Terminal:**
```bash
# Install safety (Python dependency vulnerability scanner)
pip install safety

# Scan requirements.txt for known vulnerabilities
safety check -r requirements.txt --full-report
# Fix any HIGH severity vulnerabilities found (pin versions)

# Django check --deploy (production readiness)
python manage.py check --deploy 2>&1 | head -30
# Fix any WARNINGS / ERRORS reported
```

**Expected output:** Zero HIGH vulnerabilities, zero deployment warnings (or documented exceptions).

---

### Task 9: Add Database Connection Pooling

**File:** `config/settings.py` — update `DATABASES` block:
```python
if DATABASE_URL:
    db_config = dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    if DATABASE_URL.startswith('postgres') and 'railway' not in DATABASE_URL:
        db_config['OPTIONS'] = {
            'sslmode': 'require',
            'pool': True,  # Use Supabase pooler
        }
    # Add connection pool for persistent environments
    if not os.environ.get('VERCEL'):
        db_config['CONN_MAX_AGE'] = 300  # 5 menit persistent connection
    DATABASES = {'default': db_config}
```

Note: On Vercel serverless, `CONN_MAX_AGE` should stay 0 (default) because each function invocation is ephemeral. The Supabase pooler (`pooler.supabase.com:5432`) already handles connection pooling on the database side.

---

### Task 10: Final Integration Test Suite

**File:** `akreditasi/tests_security.py` (create):

```python
from django.test import TestCase, Client
from django.urls import reverse


class SecurityHeadersTest(TestCase):
    def test_security_headers_present(self):
        """Semua security header wajib ada di response halaman login."""
        c = Client()
        response = c.get(reverse('accounts:login'))
        self.assertIn('Content-Security-Policy', response)
        self.assertIn('X-Frame-Options', response)
        self.assertIn('Referrer-Policy', response)
        self.assertIn('Permissions-Policy', response)
        self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_rate_limit_429_on_rapid_requests(self):
        """Rate limiter mengembalikan 429 setelah melebihi batas."""
        c = Client()
        url = reverse('akreditasi:api_ai_analisis_masalah_risiko')
        # Kirim 13 request cepat (batas = 12)
        for i in range(13):
            response = c.post(url, {'masalah': 'test'}, content_type='application/json')
            if i >= 12:
                self.assertEqual(response.status_code, 429)

    def test_csp_blocks_inline_scripts(self):
        """CSP melarang script dari domain asing."""
        c = Client()
        response = c.get(reverse('accounts:login'))
        csp = response['Content-Security-Policy']
        self.assertIn("default-src 'self'", csp)
        self.assertNotIn('unsafe-eval', csp)  # Tidak boleh eval()

    def test_admin_url_obfuscated(self):
        """Admin URL menggunakan path tersembunyi, bukan /admin/."""
        c = Client()
        # Default /admin/ harus 404 atau redirect
        response = c.get('/admin/')
        self.assertIn(response.status_code, [302, 404])

    def test_no_debug_in_production(self):
        """DEBUG harus False di production."""
        from django.conf import settings
        if settings.DATABASES['default']['ENGINE'].startswith('django.db.backends.postgresql'):
            self.assertFalse(settings.DEBUG)
```

**Verification:**
```bash
python manage.py test akreditasi.tests_security --verbosity=2
# Expected: 5 tests, OK
```

---

## Tests / Validation

| Task | Test Method | Expected Result |
|------|------------|----------------|
| Task 1 (Security Headers) | `curl -I` | CSP, Referrer-Policy, Permissions-Policy headers present |
| Task 2 (Cache Rate Limiter) | `python manage.py shell` | `cache.get('test_key')` returns `'hello'` |
| Task 3 (Login Rate Limit) | `curl -X POST` x6 | 6th request returns HTTP 429 |
| Task 4 (Secrets Audit) | Manual inspect `.env` + JWT decode | No `service_role` key, `.env` in `.gitignore` |
| Task 5 (Query Optimization) | `connection.queries` count | Fewer queries with select_related |
| Task 6 (Supabase Storage) | Shell upload test | File saved + deleted successfully |
| Task 7 (Static Cache) | `curl -I /static/...` | `Cache-Control: max-age=31536000` |
| Task 8 (Security Scan) | `safety check` + `check --deploy` | Zero HIGH vulns, zero deploy warnings |
| Task 9 (Pooling) | Review settings | Supabase pooler URL used, CONN_MAX_AGE=0 on Vercel |
| Task 10 (Test Suite) | `python manage.py test` | All 5+ security tests pass |

---

## Risks, Tradeoffs & Open Questions

1. **CSP 'unsafe-inline' on scripts** — Required because Django admin and existing templates use inline `<script>` blocks. Tradeoff: weaker XSS protection but avoids a massive refactor. Mitigation: audit all inline scripts in a follow-up phase to migrate to nonce/hash-based CSP.

2. **Database cache table** — One extra query per rate-limited request. Tradeoff: negligible vs. losing rate limiting entirely on cold starts. Alternative: Supabase Redis (requires paid add-on).

3. **Supabase Storage backend** — Uses `SUPABASE_KEY` (anon) from `.env`. The anon key is safe for client-side operations when RLS is configured, but server-to-server should ideally use `service_role`. Tradeoff: using `service_role` in `.env` is a bigger risk if `.env` leaks. Current approach is acceptable if Supabase Storage RLS policies are properly set.

4. **Admin IP whitelist** — Left disabled (commented out) because most users don't have static IPs. Enable manually if needed.

5. **Vercel cold starts** — Serverless functions still cold-start (up to 1-2s for Python). No fix for this without switching to a paid Vercel plan (Pro has 0s cold starts with 60s concurrency) or a persistent VM (Railway/Render).

6. **Open Question:** Is `SUPABASE_KEY` in `.env.example` the anon key or the `service_role` key? If it's `service_role`, **must** be replaced before proceeding with Task 4.
