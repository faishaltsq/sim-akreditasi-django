from decimal import Decimal
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import RequestFactory,override_settings
from django.urls import reverse
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


@override_settings(IGD_WORKFLOW_ENABLED=True,IGD_PROFESSIONAL_CARE_ENABLED=True)
class ProfessionalConfigurationTest(ProfessionalCareCase):
    def limit(self,conditions):
        from klinis.models import BatasanKewenanganProfesional
        from sdm.professional_policy import limits_digest
        self.privilege.status_spk='DISETUJUI_MANDIRI_TERBATAS';self.privilege.batasan='Batas individual sintetis';self.privilege.save()
        return BatasanKewenanganProfesional.objects.create(privilege=self.privilege,narrative_digest=limits_digest(self.privilege.batasan),conditions=conditions,valid_from=timezone.localdate(),valid_until=timezone.localdate(),source_version='qa-reviewed-limits',reviewed_by=self.user,reviewed_at=timezone.now(),is_active=True)

    def test_reviewed_quantity_limit_is_enforced(self):
        from klinis.services.professional_tariffs import quote_professional_service
        mentor=self.mentor();self.limit({'max_quantity':'1'})
        context=self.context(supervisor=mentor.pk)
        self.assertTrue(context['limits_policy'])
        quote_professional_service(self.visit,context,self.service,at=timezone.now(),quantity=Decimal('1'))
        with self.assertRaises(PermissionDenied):quote_professional_service(self.visit,context,self.service,at=timezone.now(),quantity=Decimal('2'))

    def test_reviewed_age_limit_is_enforced(self):
        mentor=self.mentor();self.limit({'min_age':150})
        with self.assertRaises(PermissionDenied):self.context(supervisor=mentor.pk)

    def test_changed_narrative_invalidates_interpretation(self):
        mentor=self.mentor();self.limit({'max_quantity':'1'})
        self.privilege.batasan='Sumber mandat berubah';self.privilege.save()
        with self.assertRaises(PermissionDenied):self.context(supervisor=mentor.pk)

    def test_unknown_restriction_not_silently_ignored(self):
        with self.assertRaises(ValidationError):self.limit({'unimplemented_condition':'unknown'})

    def test_supervisor_picker_is_procedure_scoped(self):
        mentor=self.mentor();self.privilege.status_spk='DISETUJUI_SUPERVISI';self.privilege.save()
        self.client.force_login(self.user)
        result=self.client.get(reverse('pasien:igd_professional_catalogue',args=[self.visit.pk]),{'service':self.service.pk})
        self.assertEqual(result.status_code,200)
        self.assertEqual([row['performer_id'] for row in result.json()['supervisors']],[str(mentor.pk)])

    def test_superuser_still_needs_separate_tariff_grant(self):
        from klinis.models import TarifLayananProfesi
        self.user.is_staff=True;self.user.is_superuser=True;self.user.save()
        request=RequestFactory().get('/admin/');request.user=self.user
        self.assertFalse(admin.site._registry[TarifLayananProfesi].has_add_permission(request))

    def test_tariff_admin_does_not_cross_product_unit_service_grants(self):
        from akreditasi.models import UnitKerja
        from klinis.models import ProfessionalCareGrant,TarifLayananProfesi,LayananProfesional
        self.user.is_staff=True;self.user.is_superuser=True;self.user.save()
        reviewer=User.objects.create_user('qa-tariff-reviewer')
        unit2=UnitKerja.objects.create(code='QA-UNIT-2',name='Unit sintetis',level=2)
        service2=LayananProfesional.objects.create(code='QA.CARE2',name='Layanan QA2',group='MEDICAL',authority_kind='CLINICAL',is_active=True,reviewed_by=reviewer,reviewed_at=timezone.now(),source_version='qa-fixture')
        for unit,service in [(self.unit,self.service),(unit2,service2)]:
            ProfessionalCareGrant.objects.create(user=self.user,unit=unit,service=service,capability='MANAGE_TARIFF',valid_from=timezone.localdate(),valid_until=timezone.localdate(),is_active=True,source_version='qa-fixture',reviewed_by=reviewer,reviewed_at=timezone.now())
        prices=[]
        for unit,service in [(self.unit,self.service),(unit2,service2),(self.unit,service2)]:
            prices.append(TarifLayananProfesi.objects.create(unit=unit,service=service,profession=self.profession,grade=self.grade,payor=self.visit.penjamin,valid_from=timezone.localdate(),jasa_sarana=50,jasa_pelayanan=150,source_version='qa-fixture'))
        request=RequestFactory().get('/admin/');request.user=self.user
        manager=admin.site._registry[TarifLayananProfesi]
        self.assertEqual(set(manager.get_queryset(request).values_list('pk',flat=True)),{prices[0].pk,prices[1].pk})
        self.assertFalse(manager.has_view_permission(request,prices[2]))

    def test_trainee_is_not_independent_by_profile(self):
        from sdm.models import TraineePlacement
        mentor=self.mentor()
        TraineePlacement.objects.create(pegawai=self.employee,unit_kerja=self.unit,institution='QA',program='QA',supervisor=mentor,tanggal_mulai=timezone.localdate(),tanggal_selesai=timezone.localdate(),temporary_action_codes=['professional_care'],requires_countersignature=True)
        with self.assertRaises(PermissionDenied):self.context(supervisor=mentor.pk)
