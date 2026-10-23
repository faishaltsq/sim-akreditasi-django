from importlib import import_module

from django.apps import apps
from django.test import SimpleTestCase
from django.urls import get_resolver, resolve



class HumanCapitalRegistrationTests(SimpleTestCase):
    def test_app_is_installed_and_importable(self):
        app_config = apps.get_app_config('sdm')

        self.assertEqual(app_config.name, 'sdm')
        self.assertEqual(import_module('sdm.urls').app_name, 'sdm')
        import_module('sdm.admin')
        import_module('sdm.migrations')

    def test_directory_and_dashboard_are_registered(self):
        namespace_resolver = get_resolver().namespace_dict['sdm'][1]
        self.assertIsNotNone(namespace_resolver.pattern.match('human-capital/'))

        self.assertEqual(
            resolve('/human-capital/pegawai/').view_name,
            'sdm:pegawai_list',
        )
        self.assertEqual(
            resolve('/human-capital/').view_name,
            'sdm:dashboard',
        )

    def test_existing_accreditation_routes_remain_unchanged(self):
        self.assertEqual(resolve('/').view_name, 'akreditasi:dashboard')
        self.assertEqual(resolve('/control/').view_name, 'akreditasi:kontrol_hub')
        self.assertEqual(
            resolve('/portal-nakes/upload-kredensial/').view_name,
            'akreditasi:upload_kredensial',
        )
        self.assertEqual(
            resolve('/portal-nakes/kredensial/1/unduh/').view_name,
            'akreditasi:download_kredensial',
        )
        self.assertEqual(
            resolve('/rekap-kps/verifikasi/1/').view_name,
            'akreditasi:verify_kredensial',
        )
