from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from akreditasi.models import UnitKerja
from sdm.admin import HcGrantAdmin
from sdm.models import HcGrant, PeristiwaSDM


class HumanCapitalAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(
            username='hc-super-admin', is_staff=True, is_superuser=True
        )
        self.recipient = user_model.objects.create_user(username='hc-recipient')
        self.unit = UnitKerja.objects.create(name='Unit HC Admin', code='HC-ADMIN')
        self.factory = RequestFactory()
        self.request = self.factory.post('/admin/sdm/hcgrant/add/')
        self.request.user = self.admin_user
        self.grant_admin = HcGrantAdmin(HcGrant, admin.site)

    def test_only_superuser_can_manage_grants(self):
        staff = get_user_model().objects.create_user(
            username='hc-admin-staff', is_staff=True
        )
        request = self.factory.get('/admin/')
        request.user = staff

        self.assertFalse(self.grant_admin.has_module_permission(request))
        self.assertFalse(self.grant_admin.has_view_permission(request))
        self.assertFalse(self.grant_admin.has_add_permission(request))
        self.assertFalse(self.grant_admin.has_change_permission(request))
        self.assertFalse(self.grant_admin.has_delete_permission(request))

    def test_creating_a_grant_records_its_scope_and_actor(self):
        grant = HcGrant(
            user=self.recipient,
            capability='can_manage_hc_employees',
            unit_kerja=self.unit,
            include_descendants=True,
        )

        self.grant_admin.save_model(self.request, grant, form=None, change=False)

        event = PeristiwaSDM.objects.get(target_id=str(grant.pk))
        self.assertEqual(event.actor, self.admin_user)
        self.assertEqual(event.jenis_peristiwa, 'hc_grant_created')
        self.assertEqual(event.status_sesudah, 'active')
        self.assertIn('can_manage_hc_employees', event.alasan)
        self.assertIn(str(self.unit.pk), event.alasan)

    def test_revocation_is_audited_and_grant_deletion_is_disabled(self):
        grant = HcGrant.objects.create(
            user=self.recipient,
            capability='can_view_hc',
            unit_kerja=self.unit,
            granted_by=self.admin_user,
        )
        grant.is_active = False
        self.grant_admin.save_model(self.request, grant, form=None, change=True)

        event = PeristiwaSDM.objects.get(target_id=str(grant.pk))
        self.assertEqual(event.jenis_peristiwa, 'hc_grant_updated')
        self.assertEqual(event.status_sebelum, 'active')
        self.assertEqual(event.status_sesudah, 'revoked')
        self.assertFalse(self.grant_admin.has_delete_permission(self.request))


class HumanCapitalAdminRegistrationTests(TestCase):
    def test_master_data_models_are_registered(self):
        from django.contrib import admin as django_admin

        from sdm.models import (
            AturanDokumen,
            InsidenK3Pegawai,
            Lowongan,
            PemetaanStandarSDM,
            PengajuanKredensial,
            PenugasanKlinis,
            PeriodeKinerja,
            ProgramDiklat,
            ProgramOrientasi,
            RencanaFormasi,
            SnapshotAnalitikSDM,
        )

        for model in (
            AturanDokumen, PemetaanStandarSDM, RencanaFormasi, Lowongan,
            PengajuanKredensial, PenugasanKlinis, ProgramOrientasi,
            PeriodeKinerja, ProgramDiklat, InsidenK3Pegawai,
            SnapshotAnalitikSDM,
        ):
            with self.subTest(model=model.__name__):
                self.assertIn(model, django_admin.site._registry)

    def test_snapshot_is_read_only_in_admin(self):
        from django.contrib import admin as django_admin

        from sdm.models import SnapshotAnalitikSDM

        model_admin = django_admin.site._registry[SnapshotAnalitikSDM]
        request = type('Req', (), {'user': type('U', (), {'is_superuser': True})()})()
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
