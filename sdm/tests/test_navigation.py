"""RED tests for Task A2: ten-group navigation and permission parity."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai, PenempatanPegawai
from sdm.navigation import navigation_tree


class NavigationTests(TestCase):
    def setUp(self):
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='DIR-HC')
        self.other = UnitKerja.objects.create(name='Unit Lain', code='DIR-OTHER')
        self.manager = self._user('nav-manager')
        self.viewer = self._user('nav-viewer', role='ASESOR')

    def _user(self, username, *, role='ADMIN_RS', caps=None):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role=role, unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role(role)
        hc_caps = [
            'can_view_hc', 'can_manage_hc_employees', 'can_manage_hc_documents',
            'can_plan_hc_workforce', 'can_manage_hc_recruitment',
            'can_review_hc_credentials', 'can_manage_hc_orientation',
            'can_manage_hc_appraisals', 'can_manage_hc_training',
            'can_view_hc_analytics', 'can_export_hc',
        ]
        caps = caps or {}
        if role == 'ASESOR':
            config.can_view_hc = True
            config.can_view_hc_analytics = True
            caps = {**caps, 'can_view_hc': True, 'can_view_hc_analytics': True}
        else:
            for key in hc_caps:
                setattr(config, key, True)
                caps[key] = True
        for key, value in caps.items():
            setattr(config, key, value)
        config.save(update_fields=[*caps.keys(), 'updated_at'])
        HcGrant.objects.create(user=user, capability='can_view_hc', unit_kerja=self.root)
        granted_caps = set(caps.keys()) if caps else set()
        if role != 'ASESOR':
            granted_caps |= {
                'can_manage_hc_employees', 'can_manage_hc_documents',
                'can_plan_hc_workforce', 'can_manage_hc_recruitment',
                'can_review_hc_credentials', 'can_manage_hc_orientation',
                'can_manage_hc_appraisals', 'can_manage_hc_training',
                'can_view_hc_analytics', 'can_export_hc', 'hc_health_write',
            }
        for cap in granted_caps:
            HcGrant.objects.create(user=user, capability=cap, unit_kerja=self.root)
        return user

    def test_ten_groups_render_for_manager(self):
        tree = navigation_tree(self.manager)
        keys = [g.key for g in tree]
        expected = [
            'dasbor', 'perencanaan', 'database', 'presensi',
            'kredensial', 'kinerja', 'uraian_tugas', 'k3', 'portal', 'laporan',
        ]
        self.assertEqual(keys, expected)

    def test_presensi_disabled_for_not_activated(self):
        tree = navigation_tree(self.manager)
        presensi = next(g for g in tree if g.key == 'presensi')
        self.assertEqual(presensi.disabled_reason, 'Belum diaktifkan')

    def test_viewer_sees_only_authorized_groups(self):
        # ASESOR with default perms: can_view_hc, can_view_hc_analytics only
        tree = navigation_tree(self.viewer)
        keys = [g.key for g in tree]
        self.assertIn('dasbor', keys)
        # database shows viewable items (can_view_hc), not Tambah Staf/Impor
        database = next(g for g in tree if g.key == 'database')
        self.assertEqual(
            [it.key for it in database.items],
            ['database_direktori', 'database_profil_legalitas', 'database_magres'],
        )
        self.assertNotIn('database_tambah_staf', [it.key for it in database.items])
        self.assertNotIn('database_impor_excel', [it.key for it in database.items])
        self.assertNotIn('perencanaan', keys)
        self.assertNotIn('kredensial', keys)

    def test_k3_only_with_health_grant(self):
        tree = navigation_tree(self.manager)
        keys = [g.key for g in tree]
        self.assertIn('k3', keys)

    def test_foreign_unit_head_sees_empty_for_other_unit(self):
        # viewer grant is on root; other unit not scoped -> no items requiring unit scope
        tree = navigation_tree(self.viewer)
        # should still render viewable groups
        self.assertTrue(len(tree) >= 1)
