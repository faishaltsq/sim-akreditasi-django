from decimal import Decimal
from uuid import uuid4
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


@override_settings(IGD_WORKFLOW_ENABLED=True,IGD_PROFESSIONAL_CARE_ENABLED=True)
class ProfessionalBillingTest(ProfessionalCareCase):
    def test_performed_line_cannot_be_changed_by_a_generic_model_writer(self):
        from pasien.models import TindakanAsesmen
        from django.core.exceptions import ValidationError
        self.posted();line=TindakanAsesmen.objects.get();line.tarif=Decimal('1')
        with self.assertRaises(ValidationError):line.save()
    def test_legacy_reconciliation_cannot_delete_professional_charge(self):
        from klinis.services.tarif import sync_billing
        from pasien.models import BillingItem
        result=self.posted()
        sync_billing(self.visit,[],self.user)
        self.assertTrue(BillingItem.objects.filter(pk=result['billing_id']).exists())
    def test_line_subtotal_currency_rounding(self):
        from pasien.models import BillingItem
        item=BillingItem.objects.create(kunjungan=self.visit,kategori='JASA_MEDIS',nama_item='Kuantitas sintetis',kuantitas=Decimal('1.5'),harga_satuan=Decimal('.67'))
        self.assertEqual(item.subtotal,Decimal('1.01'))
    def posted(self):
        from klinis.models import TarifLayananProfesi
        from klinis.services.professional_tariffs import quote_professional_service
        from pasien.services.igd_actions import perform_action
        TarifLayananProfesi.objects.create(service=self.service,unit=self.unit,profession=self.profession,grade=self.grade,payor=self.visit.penjamin,valid_from=timezone.localdate(),jasa_sarana=50,jasa_pelayanan=150,is_free=False,review_state='APPROVED',is_active=True,reviewed_by=self.user,reviewed_at=timezone.now(),source_version='qa-fixture')
        quote=quote_professional_service(self.visit,self.context(),self.service,at=timezone.now())
        return perform_action(self.visit.pk,self.user,'professional_execute',{'source':'DIRECT','service_id':self.service.pk,'quantity':'1','quote_fingerprint':quote['fingerprint']},0,uuid4())

    def grant_void(self):
        from klinis.models import ProfessionalCareGrant
        reviewer=User.objects.create_user('qa-finance-reviewer')
        ProfessionalCareGrant.objects.create(user=self.user,unit=self.unit,capability='VOID_UNPAID_CHARGE',valid_from=timezone.localdate(),valid_until=timezone.localdate(),is_active=True,source_version='qa-fixture',reviewed_by=reviewer,reviewed_at=timezone.now())

    def test_ungranted_void_denied(self):
        from pasien.services.professional_billing import void_professional_charge
        result=self.posted()
        with self.assertRaises(PermissionDenied):void_professional_charge(self.user,result['billing_id'],result['version'],uuid4(),'Koreksi tagihan sintetis')

    def test_void_preserves_original_and_net_zero(self):
        from pasien.models import BillingItem,TindakanAsesmen
        from pasien.services.professional_billing import void_professional_charge,professional_billing_summary
        result=self.posted();self.grant_void();key=uuid4()
        void_professional_charge(self.user,result['billing_id'],result['version'],key,'Koreksi tagihan sintetis')
        item=BillingItem.objects.get();self.assertEqual(item.harga_satuan,Decimal('200'));self.assertEqual(item.subtotal,0)
        summary=professional_billing_summary(self.visit)
        self.assertEqual(summary['gross'],Decimal('200'));self.assertEqual(summary['void'],Decimal('200'));self.assertEqual(summary['net'],0)
        self.assertEqual(TindakanAsesmen.objects.get().execution_status,'PERFORMED')
        again=void_professional_charge(self.user,result['billing_id'],result['version'],key,'Koreksi tagihan sintetis')
        self.assertTrue(again['replayed']);self.assertEqual(item.void_record.amount,Decimal('200'))

    def test_summary_get_does_not_write(self):
        from pasien.models import BillingItem
        from pasien.services.professional_billing import professional_billing_summary
        BillingItem.objects.create(kunjungan=self.visit,kategori='OBAT',nama_item='Obat sintetis',kuantitas=2,harga_satuan=50)
        before=BillingItem.objects.count();summary=professional_billing_summary(self.visit)
        self.assertEqual(summary['net'],Decimal('100'));self.assertEqual(summary['categories']['DRUG_BMHP']['net'],Decimal('100'))
        self.assertEqual(BillingItem.objects.count(),before)
