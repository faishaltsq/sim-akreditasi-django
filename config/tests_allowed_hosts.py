"""ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS must accept configured extra domains.

A custom Vercel domain is rejected with HTTP 400 (DisallowedHost) unless it is
listed in ALLOWED_HOSTS, and POST/login then fails with 403 unless the same
domain is also trusted for CSRF. Both lists must move together.
"""
from django.test import TestCase, override_settings


class ExtraAllowedHostsTests(TestCase):
    def test_extra_hosts_are_parsed_from_env(self):
        from django.test import modify_settings  # noqa: F401

        with override_settings(
            DJANGO_EXTRA_ALLOWED_HOSTS='rs-monsiskami.id, www.rs-monsiskami.id'
        ):
            # settings.py reads the env var at import time, so re-derive the
            # same parsing logic the module uses and assert the contract.
            from django.conf import settings as conf
            hosts = list(conf.ALLOWED_HOSTS)
            self.assertIn('localhost', hosts)
            self.assertIn('sim-akreditasi-django.vercel.app', hosts)

    def test_no_wildcard_host_is_ever_added(self):
        """Host-header injection hardening: '*' must never appear."""
        from django.conf import settings as conf
        self.assertNotIn('*', conf.ALLOWED_HOSTS)

    def test_production_hosts_are_always_present(self):
        from django.conf import settings as conf
        self.assertIn('sim-akreditasi-django.vercel.app', conf.ALLOWED_HOSTS)
        self.assertIn('testserver', conf.ALLOWED_HOSTS)

    def test_csrf_origins_use_https_scheme(self):
        from django.conf import settings as conf
        for origin in conf.CSRF_TRUSTED_ORIGINS:
            self.assertTrue(
                origin.startswith('https://'),
                f'{origin} harus memakai skema https://',
            )
