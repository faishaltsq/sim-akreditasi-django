from decimal import Decimal
from uuid import uuid4
from django.test import override_settings,SimpleTestCase
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from pasien.professional_test_support import ProfessionalCareCase


class ChargeStateTest(SimpleTestCase):
    def test_unknown_free_and_posted(self):
        from pasien.services.professional_billing import charge_state
        self.assertEqual(charge_state(None,False),'PENDING')
        self.assertEqual(charge_state(Decimal('0'),True),'FREE')
        self.assertEqual(charge_state(Decimal('10'),False),'POSTED')


@override_settings(IGD_WORKFLOW_ENABLED=True,IGD_PROFESSIONAL_CARE_ENABLED=True)
class ProfessionalExecutionTest(ProfessionalCareCase):
    def price(self,free=False):
        from klinis.models import TarifLayananProfesi
        return TarifLayananProfesi.objects.create(service=self.service,unit=self.unit,profession=self.profession,grade=self.grade,payor=self.visit.penjamin,valid_from=timezone.localdate(),jasa_sarana=0 if free else 50000,jasa_pelayanan=0 if free else 150000,is_free=free,review_state='APPROVED',is_active=True,reviewed_by=self.user,reviewed_at=timezone.now(),source_version='qa-fixture')

    def intent(self,action=None):
        from klinis.services.professional_tariffs import quote_professional_service
        quote=quote_professional_service(self.visit,self.context(),self.service,at=timezone.now())
        return {'source':'PLANNED' if action else 'DIRECT','action_id':action.pk if action else None,'service_id':self.service.pk,'quantity':'1','quote_fingerprint':quote['fingerprint']}

    def execute(self,data,version=0,key=None):
        from pasien.services.igd_actions import perform_action
        return perform_action(self.visit.pk,self.user,'professional_execute',data,version,key or uuid4())

    def test_execution_links_one_draft_one_bill(self):
        from pasien.models import CPPT,BillingItem,TindakanAsesmen
        self.price();result=self.execute(self.intent())
        self.assertEqual(TindakanAsesmen.objects.count(),1);self.assertEqual(CPPT.objects.count(),1);self.assertEqual(BillingItem.objects.count(),1)
        self.assertEqual(BillingItem.objects.get().subtotal,Decimal('200000'))
        self.assertEqual(CPPT.objects.get().status,'DRAFT');self.assertFalse(CPPT.objects.get().verifikasi_dpjp)
        self.assertEqual(TindakanAsesmen.objects.get().execution_cppt_id,result['cppt_id'])

    def test_same_request_replays_without_duplicate(self):
        from pasien.models import BillingItem
        self.price();data=self.intent();key=uuid4()
        first=self.execute(data,key=key);second=self.execute(data,key=key)
        self.assertEqual(first['billing_id'],second['billing_id']);self.assertTrue(second['replayed']);self.assertEqual(BillingItem.objects.count(),1)

    def test_second_key_same_plan_does_not_repeat(self):
        from pasien.models import TindakanAsesmen,CPPT,BillingItem
        line=TindakanAsesmen.objects.create(kunjungan=self.visit,urutan=1,jenis='BEBAS',kode=self.service.code,nama=self.service.name,execution_status='PLANNED',execution_team='MEDIS',tarif_penjamin=self.visit.penjamin)
        self.price();data=self.intent(line);first=self.execute(data);second=self.execute(data,version=first['version'])
        self.assertEqual(first['billing_id'],second['billing_id']);self.assertEqual(CPPT.objects.count(),1);self.assertEqual(BillingItem.objects.count(),1)

    def test_unpriced_pending_and_approved_free_differ(self):
        from pasien.models import BillingItem,TindakanAsesmen
        self.service.allow_unpriced=True;self.service.save()
        first=self.execute(self.intent());self.assertIsNone(first['billing_id']);self.assertEqual(TindakanAsesmen.objects.get().financial_status,'PENDING')
        self.price(free=True);second=self.execute(self.intent(),first['version'])
        self.assertIsNotNone(second['billing_id']);self.assertEqual(BillingItem.objects.get().subtotal,0)

    def test_changed_payor_rejects_quote_without_writes(self):
        from pasien.models import CPPT
        from pasien.services.igd_assessment_workflow import WorkflowConflict
        self.price();data=self.intent();self.visit.penjamin='BPJS';self.visit.save()
        with self.assertRaises(WorkflowConflict):self.execute(data)
        self.assertFalse(CPPT.objects.exists())

    def test_revoked_actor_cannot_replay(self):
        self.price();data=self.intent();key=uuid4();self.execute(data,key=key)
        self.spk.is_active=False;self.spk.save()
        with self.assertRaises(PermissionDenied):self.execute(data,key=key)
