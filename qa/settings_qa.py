"""Override settings khusus QA. JANGAN diimpor dari settings produksi.

Tiga override ini yang membuat pengujian 1.295 akun layak jalan:
  - signed_cookies : session tidak menulis ke DB (default db = 1.295 write)
  - MD5PasswordHasher : authenticate() <1 ms (PBKDF2 default ~500 ms)
  - LOGGING null : traceback 403/400 tidak membanjiri stdout
"""
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root': {'handlers': ['null'], 'level': 'CRITICAL'},
}
