from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_local_env(path):
    """Load KEY=VALUE pairs from .env without overriding platform variables.

    Production platforms inject environment variables directly; this only fills
    gaps during local development. Secrets stay out of settings and out of git.
    """
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env(BASE_DIR / '.env')

# ── KEAMANAN: SECRET_KEY & DEBUG ─────────────────────────────────────────
IS_PRODUCTION = bool(os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER') or os.environ.get('VERCEL') or os.environ.get('DATABASE_URL'))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if IS_PRODUCTION:
        import secrets
        SECRET_KEY = secrets.token_urlsafe(50)
    else:
        SECRET_KEY = 'django-insecure-sim-akreditasi-dev-only-change-in-production'

# Default DEBUG: False di production, True di lokal
DEBUG = os.environ.get('DJANGO_DEBUG', 'False' if IS_PRODUCTION else 'True').lower() in ('true', '1')

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]
# Domain produksi eksplisit — TANPA wildcard platform (host-header injection hardening).
ALLOWED_HOSTS += [
    'sim-akreditasi-django.vercel.app',
    'sim-akreditasi-web-production.up.railway.app',
    'testserver',
]
# Domain tambahan (alias/domain kustom Vercel) lewat env, dipisah koma.
# Django menolak Host yang tidak terdaftar dengan 400 DisallowedHost, jadi
# domain kustom baru wajib masuk sini; tanpa wildcard host-header tetap aman.
for _host in os.environ.get('DJANGO_EXTRA_ALLOWED_HOSTS', '').split(','):
    _host = _host.strip().replace('https://', '').replace('http://', '').strip('/')
    if _host and _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)
# Preview deployment Vercel memakai hostname acak per build. Tambahkan host
# deployment yang sedang berjalan dari env (satu host spesifik, tetap bukan
# wildcard) supaya preview tidak kena DisallowedHost 400.
for _host_var in ('VERCEL_URL', 'VERCEL_BRANCH_URL',
                  'VERCEL_PROJECT_PRODUCTION_URL'):
    _host = (os.environ.get(_host_var) or '').strip()
    if _host:
        _host = _host.replace('https://', '').replace('http://', '').strip('/')
        if _host and _host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_host)

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if o.strip()
]
CSRF_TRUSTED_ORIGINS += [
    'https://sim-akreditasi-django.vercel.app',
    'https://sim-akreditasi-web-production.up.railway.app',
]
# Setiap domain di ALLOWED_HOSTS juga harus dipercaya untuk POST/CSRF; login
# dan form akan gagal (403) kalau hanya satu daftar yang diisi.
for _host in os.environ.get('DJANGO_EXTRA_ALLOWED_HOSTS', '').split(','):
    _host = _host.strip().replace('https://', '').replace('http://', '').strip('/')
    if _host:
        _origin = f'https://{_host}'
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)
for _host_var in ('VERCEL_URL', 'VERCEL_BRANCH_URL',
                  'VERCEL_PROJECT_PRODUCTION_URL'):
    _host = (os.environ.get(_host_var) or '').strip()
    if _host:
        _origin = 'https://' + _host.replace('https://', '').replace('http://', '').strip('/')
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

CSRF_FAILURE_VIEW = 'akreditasi.views.custom_csrf_failure'

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

RAILWAY_PUBLIC_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_PUBLIC_DOMAIN}')

RAILWAY_STATIC_URL = os.environ.get('RAILWAY_STATIC_URL')
if RAILWAY_STATIC_URL:
    ALLOWED_HOSTS.append(RAILWAY_STATIC_URL)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_STATIC_URL}')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ── KEAMANAN: HTTPS, COOKIE, & HEADERS ───────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000          # 1 tahun HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 28800                 # Session kedaluwarsa setelah 8 jam
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
X_FRAME_OPTIONS = 'DENY'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'accounts',
    'akreditasi',
    'pasien',
    'sdm.apps.SdmConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'akreditasi.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'akreditasi.context_processors.sidebar_context',
                'sdm.context_processors.hc_navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    conn_age = 0 if os.environ.get('VERCEL') else 600
    db_config = dj_database_url.parse(DATABASE_URL, conn_max_age=conn_age)
    if DATABASE_URL.startswith('postgres') and 'railway' not in DATABASE_URL:
        db_config['OPTIONS'] = {'sslmode': 'require'}
    DATABASES = {'default': db_config}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ── CACHE FRAMEWORK: RATE LIMITING & PERFORMANCE ─────────────────────────
if DATABASE_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'django_cache_table',
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'arima-local-cache',
            'TIMEOUT': 300,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'id'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

if not DEBUG:
    WHITENOISE_MAX_AGE = 31536000  # 1 tahun Cache-Control untuk static assets

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
SUPABASE_BUCKET = os.environ.get('SUPABASE_BUCKET', 'bukti-akreditasi')

STORAGES = {
    'default': {
        'BACKEND': (
            'akreditasi.storage.SupabaseMediaStorage'
            if (SUPABASE_URL and SUPABASE_KEY and (IS_PRODUCTION or os.environ.get('USE_SUPABASE_STORAGE')))
            else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    'staticfiles': {
        # Fingerprinted URLs keep year-long browser/CDN caching safe after deploys.
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Arima Human Capital private bucket. The service key is read directly from
# HC_PRIVATE_STORAGE_SERVICE_KEY by sdm.storage and is never exposed in settings.
HC_PRIVATE_STORAGE_BUCKET = os.environ.get(
    'HC_PRIVATE_STORAGE_BUCKET', 'human-capital-private'
)

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# SQLite (lokal & uji) tidak mendukung UniqueConstraint.nulls_distinct (W047).
# Aturan "satu laporan per periode per cakupan" dijaga LaporanMutu.save() pada
# semua backend; constraint database tetap dipakai di Postgres produksi.
SILENCED_SYSTEM_CHECKS = ['models.W047']

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'akreditasi:kontrol_hub'
LOGOUT_REDIRECT_URL = 'accounts:login'

from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {
    message_constants.DEBUG: 'secondary',
    message_constants.INFO: 'info',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR: 'danger',
}

# ── SatuSehat Kemenkes FHIR Integration (Permenkes 24/2022) ──────────
SATUSEHAT_BASE_URL = os.environ.get('SATUSEHAT_BASE_URL', 'https://api-satusehat-stg.dto.kemkes.go.id')
SATUSEHAT_CLIENT_ID = os.environ.get('SATUSEHAT_CLIENT_ID', '')
SATUSEHAT_CLIENT_SECRET = os.environ.get('SATUSEHAT_CLIENT_SECRET', '')
SATUSEHAT_ORG_ID = os.environ.get('SATUSEHAT_ORG_ID', '')

# ── BPJS Kesehatan Bridging (VClaim v2 + Antrean Online) ─────────────
BPJS_VCLAIM_BASE_URL = os.environ.get('BPJS_VCLAIM_BASE_URL', 'https://apijkn-dev.bpjs-kesehatan.go.id/vclaim-rest-dev')
BPJS_ANTREAN_BASE_URL = os.environ.get('BPJS_ANTREAN_BASE_URL', 'https://apijkn-dev.bpjs-kesehatan.go.id/antreanrs-dev')
BPJS_CONS_ID = os.environ.get('BPJS_CONS_ID', '')
BPJS_SECRET_KEY = os.environ.get('BPJS_SECRET_KEY', '')
BPJS_USER_KEY = os.environ.get('BPJS_USER_KEY', '')
BPJS_KODE_PPK = os.environ.get('BPJS_KODE_PPK', '0000000')

# Canonical public origin used to build account-activation links. It must be
# set explicitly in production: deriving a token URL from ALLOWED_HOSTS or the
# request Host header lets a spoofed host reach an emailed credential link.
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '')
