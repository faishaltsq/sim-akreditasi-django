from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from uuid import uuid4
import json

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pasien.tests_clinical_expansion import PrescriptionTest


class CatalogueImportTest(TestCase):
    def test_imports_are_dry_run_by_default_idempotent_and_inactive(self):
        for kind,model in [('penunjang','ItemPenunjang'),('medication','ProdukFarmasi')]:
            out=StringIO();call_command('import_'+kind+'_catalogue',stdout=out)
            self.assertFalse(json.loads(out.getvalue())['applied'])
            first=StringIO();call_command('import_'+kind+'_catalogue',apply=True,stdout=first)
            count=apps.get_model('klinis',model).objects.count()
            self.assertGreater(count,0)
            second=StringIO();call_command('import_'+kind+'_catalogue',apply=True,stdout=second)
            self.assertEqual(json.loads(second.getvalue())['created'],0)
            self.assertFalse(apps.get_model('klinis',model).objects.filter(active=True).exists())

    def test_catalogue_review_and_grant_admin_are_reachable(self):
        for app,name in [('klinis','ProdukFarmasi'),('klinis','ItemPenunjang'),('pasien','PharmacyServiceGrant')]:
            self.assertIn(apps.get_model(app,name),admin.site._registry)


class ExpansionSafetyTest(PrescriptionTest):
    def submit(self,result,acks=None):
        from pasien.services.igd_actions import perform_action
        self.visit.skrining_alergi_status='TIDAK_ADA';self.visit.save(update_fields=['skrining_alergi_status'])
        return perform_action(self.visit.pk,self.user,'prescription_submit',{'prescription_id':result['prescription_id'],'acknowledgements':acks or []},result['version'],str(uuid4()))

    def test_unstructured_history_is_not_a_negative_allergy_result(self):
        from pasien.services.medication_safety import evaluate_prescription
        result=self.create_draft(self.product())
        self.patient.alergi_obat='Riwayat alergi belum dipetakan';self.patient.save(update_fields=['alergi_obat'])
        self.visit.skrining_alergi_status='TIDAK_ADA';self.visit.save(update_fields=['skrining_alergi_status'])
        rx=apps.get_model('pasien','ResepElektronik').objects.get(pk=result['prescription_id'])
        self.assertIn('ALLERGY_UNRESOLVED',[r['code'] for r in evaluate_prescription(rx)])

    def test_ppra_hold_independent_review(self):
        from pasien.services.ppra_review import review_ppra
        product=self.product();product.flags=['PPRA'];product.save(update_fields=['flags'])
        apps.get_model('klinis','MedicationPolicy').objects.create(version='QA-policy',source='synthetic',rules={},active=True,reviewed_by=self.user)
        result=self.create_draft(product);held=self.submit(result)
        self.assertTrue(held['held'])
        request=apps.get_model('pasien','PpraReviewRequest').objects.get(pk=held['ppra_request_id'])
        with self.assertRaises(PermissionDenied):
            review_ppra(self.user,request.pk,'APPROVED','Alasan uji reviewer',request.digest)
        reviewer=User.objects.create_user('qa_ppra_reviewer')
        from accounts.models import UserProfile
        UserProfile.objects.create(user=reviewer,profesi='APOTEKER',role='STAF_NAKES',unit_kerja=self.unit)
        apps.get_model('pasien','PharmacyServiceGrant').objects.create(user=reviewer,unit=self.unit,can_ppra_review=True)
        review_ppra(reviewer,request.pk,'APPROVED','Persetujuan kebijakan uji',request.digest)
        rx=request.resep;rx.refresh_from_db();self.assertEqual(rx.status,'DRAFT')
        sent=self.submit({'prescription_id':rx.pk,'version':held['version']})
        rx.refresh_from_db();self.assertEqual(rx.status,'DIKIRIM')
        self.assertFalse(sent['held'])

    def test_pharmacy_denies_unassigned_actor_and_wrong_version(self):
        from pasien.services.prescriptions import transition_prescription
        result=self.create_draft(self.product());self.submit(result)
        rx=apps.get_model('pasien','ResepElektronik').objects.get(pk=result['prescription_id'])
        outsider=User.objects.create_user('qa_outsider_pharm')
        from accounts.models import UserProfile
        UserProfile.objects.create(user=outsider,profesi='APOTEKER',role='STAF_NAKES',unit_kerja=self.unit)
        with self.assertRaises(PermissionDenied):
            transition_prescription(outsider,rx.pk,'dispensing',rx.version,str(uuid4()))
        self.user.profile.profesi='APOTEKER';self.user.profile.save(update_fields=['profesi'])
        with self.assertRaises(ValueError):
            transition_prescription(self.user,rx.pk,'dispensing',rx.version-1,str(uuid4()))
        self.assertFalse(self.visit.billing.exists())

    def test_racikan_bmhp_and_fractional_quantity_persist(self):
        from pasien.services.igd_actions import perform_action
        product=self.product();apps.get_model('pasien','PharmacyServiceGrant').objects.create(user=self.user,unit=self.unit)
        payload={'serving_unit_id':self.unit.pk,'lines':[{'product_id':product.pk,'kind':'RACIKAN',
            'regimen':{'schema_version':1,'frequency':'FIXED','times_per_day':'2','dose':'1','dose_unit':'tablet','duration_days':'3','route':'PO'},
            'quantity':'6','quantity_reason':'Jumlah racikan ditinjau','compound_form':'PUYER','compound_instructions':'Bagi enam bungkus sesuai resep uji',
            'components':[{'product_id':product.pk,'amount':'3','unit':'tablet'}]}]}
        result=perform_action(self.visit.pk,self.user,'prescription_save',payload,0,str(uuid4()))
        rx=apps.get_model('pasien','ResepElektronik').objects.get(pk=result['prescription_id'])
        self.assertEqual(rx.items.get().components.count(),1)
        self.assertEqual(rx.items.get().product_snapshot['unit'],'bungkus')
        self.assertIsNone(rx.items.get().reference_price)
        self.assertEqual(rx.items.get().product_snapshot['components'][0]['amount'],'3')
        from pasien.services.medication_safety import evaluate_prescription
        from pasien.services.prescriptions import content_digest
        previous_digest=content_digest(rx)
        product.flags=['HIGH_ALERT'];product.save(update_fields=['flags'])
        self.assertNotEqual(content_digest(rx),previous_digest)
        self.assertIn('RISK_HIGH_ALERT',[finding['code'] for finding in evaluate_prescription(rx)])
        supply=self.product('SUPPLY-QA','supply');supply.kind='BMHP';supply.save(update_fields=['kind'])
        supply.generik.kelas.kind='BMHP';supply.generik.kelas.save(update_fields=['kind'])
        result=perform_action(self.visit.pk,self.user,'prescription_save',{'serving_unit_id':self.unit.pk,'lines':[{'product_id':supply.pk,'kind':'BMHP','regimen':{'schema_version':1,'frequency':'BMHP'},'quantity':'2','quantity_reason':'Dua unit kebutuhan uji'}]},result['version'],str(uuid4()))
        row=apps.get_model('pasien','ResepElektronik').objects.get(pk=result['prescription_id']).items.get()
        self.assertEqual(row.kind,'BMHP');self.assertEqual(row.quantity_decimal,2)

    def test_four_decimal_quantity_never_silently_rounds_into_legacy_ledger(self):
        from pasien.services.prescriptions import transition_prescription
        result=self.create_draft(self.product())
        rx=apps.get_model('pasien','ResepElektronik').objects.get(pk=result['prescription_id'])
        row=rx.items.get();row.quantity_decimal=Decimal('0.0001');row.save(update_fields=['quantity_decimal'])
        self.submit(result)
        self.user.profile.profesi='APOTEKER';self.user.profile.save(update_fields=['profesi'])
        rx.refresh_from_db();transition_prescription(self.user,rx.pk,'dispensing',rx.version,str(uuid4()))
        rx.refresh_from_db();completed=transition_prescription(self.user,rx.pk,'selesai',rx.version,str(uuid4()))
        self.assertTrue(completed['financial_pending'])
        self.assertFalse(self.visit.billing.exists())
        self.assertEqual(rx.items.get().quantity_decimal,Decimal('0.0001'))

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_legacy_free_text_route_does_not_send_or_charge(self):
        response=self.client.post(reverse('pasien:resep_buat',args=[self.visit.pk]),{'nama_obat[]':['Unmapped'],'harga_satuan[]':['1']})
        self.assertEqual(response.status_code,400)
        self.assertFalse(self.visit.resep_list.exists())
        self.assertFalse(self.visit.billing.exists())
