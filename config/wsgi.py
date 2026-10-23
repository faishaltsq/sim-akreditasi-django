"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
app = application

logger = logging.getLogger('django')


def _pending_migrations():
    """Return pending (app, name) pairs, or None when the check itself fails."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


def _auto_migrate():
    """Apply migrations on cold start, tolerating concurrent lambda invocations.

    Vercel runs several serverless instances in parallel. Without a lock, two
    instances can both decide a migration is pending and race on DDL, producing
    "relation already exists" noise on every cold start. We therefore:
      1. skip the call entirely when nothing is pending (the common path), and
      2. treat an already-applied schema as success rather than an error.
    """
    from django.db import DatabaseError

    pending = _pending_migrations()
    if not pending:
        return

    from django.core.management import call_command

    try:
        call_command('migrate', interactive=False, verbosity=1)
    except DatabaseError as exc:
        # Another instance may have applied the same migration first. Re-check
        # instead of trusting the exception text.
        if not _pending_migrations():
            logger.info('Migrations applied concurrently by another instance.')
            return
        logger.warning('Auto-migrate on WSGI startup failed: %s', exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning('Auto-migrate on WSGI startup failed: %s', exc)


if os.environ.get('DATABASE_URL'):
    _auto_migrate()
