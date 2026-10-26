"""Isolated source-preparation tests; never use these settings for deployment."""
SECRET_KEY = 'source-preparation-tests-not-a-production-key'
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'akreditasi.apps.AkreditasiConfig',
    'pasien.apps.PasienConfig',
]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
MIGRATION_MODULES = {'akreditasi': None, 'pasien': None}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
