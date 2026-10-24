"""Setelan test khusus Integrated Control.

Bukan setelan produksi: DB in-memory, migration dimatikan, cache lokal, dan
hasher cepat. Dipakai lewat ``DJANGO_SETTINGS_MODULE=config.control_test_settings``
supaya test UI tidak pernah menyentuh ``db.sqlite3`` atau DATABASE_URL.
"""
from .settings import *  # noqa: F401,F403

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': ':memory:',
}}
MIGRATION_MODULES = {
    'accounts': None,
    'akreditasi': None,
    'pasien': None,
    'sdm': None,
}
CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'control-workspace-tests',
}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
