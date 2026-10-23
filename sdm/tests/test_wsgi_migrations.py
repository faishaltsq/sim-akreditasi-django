"""Cold-start migration guard: must be a no-op when nothing is pending."""
from unittest.mock import patch

from django.test import SimpleTestCase


class AutoMigrateTests(SimpleTestCase):
    def test_no_migrate_call_when_nothing_is_pending(self):
        from config import wsgi

        with patch.object(wsgi, '_pending_migrations', return_value=[]), patch(
            'django.core.management.call_command'
        ) as call_command:
            wsgi._auto_migrate()

        call_command.assert_not_called()

    def test_concurrent_ddl_is_treated_as_success(self):
        from django.db import DatabaseError

        from config import wsgi

        with patch.object(
            wsgi, '_pending_migrations', side_effect=[[('sdm', '0002')], []]
        ), patch(
            'django.core.management.call_command',
            side_effect=DatabaseError('relation already exists'),
        ), patch.object(wsgi.logger, 'warning') as warning:
            wsgi._auto_migrate()

        warning.assert_not_called()

    def test_real_failure_is_reported(self):
        from django.db import DatabaseError

        from config import wsgi

        with patch.object(
            wsgi, '_pending_migrations', side_effect=[[('sdm', '0002')], [('sdm', '0002')]]
        ), patch(
            'django.core.management.call_command',
            side_effect=DatabaseError('connection refused'),
        ), patch.object(wsgi.logger, 'warning') as warning:
            wsgi._auto_migrate()

        warning.assert_called_once()
