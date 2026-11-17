"""Loopback-only synthetic PostgreSQL verification; never a deployment settings module."""
from copy import deepcopy
from .settings import *

DATABASES=deepcopy(DATABASES)
assert DATABASES['default']['ENGINE']=='django.db.backends.postgresql'
assert DATABASES['default']['HOST']=='127.0.0.1' and str(DATABASES['default']['PORT'])=='15482'
assert DATABASES['default']['NAME']=='igd_professional_qa'
DATABASES['default'].setdefault('OPTIONS',{})['sslmode']='disable'
DATABASES['default']['CONN_MAX_AGE']=0
DATABASES['default']['CONN_HEALTH_CHECKS']=False
