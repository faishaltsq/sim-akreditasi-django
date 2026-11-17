"""Synthetic browser fixture only: local SQLite, loopback and disposable storage."""
from .settings import *

assert not os.environ.get('DATABASE_URL')
QA_ROOT=Path(os.environ['TMPDIR'])/'professional-browser'/'final'
QA_ROOT.mkdir(parents=True,exist_ok=True)
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':QA_ROOT/'fixture.sqlite3'}}
IGD_WORKFLOW_ENABLED=True
IGD_PROFESSIONAL_CARE_ENABLED=True
DEBUG=True
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
ALLOWED_HOSTS=['127.0.0.1','localhost','testserver']
MEDIA_ROOT=QA_ROOT/'media'
TEMPLATES[0]['OPTIONS']['loaders']=['django.template.loaders.filesystem.Loader','django.template.loaders.app_directories.Loader']
TEMPLATES[0]['APP_DIRS']=False
