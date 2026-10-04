"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
app = application

# Run migrations on serverless cold start if DATABASE_URL is present
if os.environ.get('DATABASE_URL'):
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False)
    except Exception as e:
        import logging
        logging.getLogger('django').warning(f'Auto-migrate on WSGI startup failed: {e}')
