from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,close_old_connections
from django.test import TransactionTestCase,override_settings
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


@skipUnless(connection.vendor=='postgresql','PostgreSQL row-lock proof requires PostgreSQL')
@override_settings(IGD_WORKFLOW_ENABLED=True,IGD_PROFESSIONAL_CARE_ENABLED=True)
class ProfessionalPostgresRaceTest(TransactionTestCase):
    def setUp(self):ProfessionalCareCase.setUpTestData.__func__(type(self))

    def price(self,version=1):
        from klinis.models import TarifLayananProfesi
        return TarifLayananProfesi.objects.create(service=self.service,unit=self.unit,profession=self.profession,grade=self.grade,payor=self.visit.penjamin,valid_from=timezone.localdate(),jasa_sarana=50,jasa_pelayanan=150,is_free=False,review_state='APPROVED',is_active=True,reviewed_by=self.user,reviewed_at=timezone.now(),source_version='qa-fixture',version=version)

    def intent(self,action=None):
        from sdm.services.professional_care import resolve_professional_context
        from klinis.services.professional_tariffs import quote_professional_service
        context=resolve_professional_context(self.user,self.visit,self.service,at=timezone.now())
        quote=quote_professional_service(self.visit,context,self.service,at=timezone.now())
        return {'source':'PLANNED' if action else 'DIRECT','action_id':action.pk if action else None,'service_id':self.service.pk,'quantity':'1','quote_fingerprint':quote['fingerprint']}

    def race(self,functions):
        gate=Barrier(len(functions))
        def invoke(fn):
            close_old_connections()
            try:
                gate.wait(timeout=10)
                return ('ok',fn())
            except (ValidationError,PermissionDenied,ValueError) as exc:return ('denied',type(exc).__name__)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=len(functions)) as executor:
            futures=[executor.submit(invoke,fn) for fn in functions]
            return [f.result(timeout=30) for f in futures]

    def test_same_key_one_performance(self):
        from pasien.services.igd_actions import perform_action
        from pasien.models import TindakanAsesmen,CPPT,BillingItem
        self.price();data=self.intent();key=uuid4()
        def perform():return perform_action(self.visit.pk,User.objects.get(pk=self.user.pk),'professional_execute',data,0,key)
        results=self.race([perform,perform])
        self.assertEqual([r[0] for r in results],['ok','ok'])
        self.assertEqual(results[0][1]['billing_id'],results[1][1]['billing_id'])
        self.assertEqual(TindakanAsesmen.objects.count(),1);self.assertEqual(CPPT.objects.count(),1);self.assertEqual(BillingItem.objects.count(),1)

    def test_two_keys_one_planned_performance(self):
        from pasien.services.igd_actions import perform_action
        from pasien.models import TindakanAsesmen,CPPT,BillingItem
        self.price();line=TindakanAsesmen.objects.create(kunjungan=self.visit,urutan=1,jenis='BEBAS',kode=self.service.code,nama=self.service.name,execution_status='PLANNED',tarif_penjamin=self.visit.penjamin)
        data=self.intent(line)
        def perform():return perform_action(self.visit.pk,User.objects.get(pk=self.user.pk),'professional_execute',data,0,uuid4())
        results=self.race([perform,perform]);self.assertEqual(sorted(r[0] for r in results),['denied','ok'])
        self.assertEqual(CPPT.objects.count(),1);self.assertEqual(BillingItem.objects.count(),1)

    def test_competing_first_price_approvals_no_overlap(self):
        from klinis.models import TarifLayananProfesi
        results=self.race([lambda:self.price(1),lambda:self.price(2)])
        self.assertEqual(sorted(r[0] for r in results),['denied','ok']);self.assertEqual(TarifLayananProfesi.objects.count(),1)

    def test_two_void_keys_one_reversal(self):
        from klinis.models import ProfessionalCareGrant
        from pasien.models import PembatalanTagihan,BillingItem
        from pasien.services.professional_billing import void_professional_charge
        from pasien.services.igd_actions import perform_action
        self.price();data=self.intent();result=perform_action(self.visit.pk,self.user,'professional_execute',data,0,uuid4())
        reviewer=User.objects.create_user('qa-reviewer')
        ProfessionalCareGrant.objects.create(user=self.user,unit=self.unit,capability='VOID_UNPAID_CHARGE',valid_from=timezone.localdate(),valid_until=timezone.localdate(),is_active=True,source_version='qa-fixture',reviewed_by=reviewer,reviewed_at=timezone.now())
        def cancel():return void_professional_charge(User.objects.get(pk=self.user.pk),result['billing_id'],result['version'],uuid4(),'Koreksi tagihan sintetis')
        results=self.race([cancel,cancel]);self.assertEqual(sorted(r[0] for r in results),['denied','ok'])
        self.assertEqual(PembatalanTagihan.objects.count(),1);self.assertEqual(BillingItem.objects.get().subtotal,0)

    def test_revocation_serializes_and_blocks_subsequent_execution(self):
        from pasien.services.igd_actions import perform_action
        from pasien.models import BillingItem
        from sdm.models import PrivilegeSnapshot
        self.price();data=self.intent()
        def perform():return perform_action(self.visit.pk,User.objects.get(pk=self.user.pk),'professional_execute',data,0,uuid4())
        def revoke():return PrivilegeSnapshot.objects.filter(pk=self.snapshot.pk).update(revoked_at=timezone.now())
        results=self.race([perform,revoke]);self.assertEqual(results[1][0],'ok')
        self.assertIn(BillingItem.objects.count(),(0,1))
        with self.assertRaises(PermissionDenied):perform()

    def signed_note(self):
        from pasien.models import IgdAssessmentWorkflow,PenugasanDpjpEpisode
        from sdm.models import ClinicalActionCode,PrivilegeSnapshot
        from sdm.services.professional_care import resolve_professional_context
        from pasien.services.professional_cppt import create_care_note,sign_care_note
        reviewer=User.objects.create_superuser('qa-assigner')
        code=ClinicalActionCode.objects.create(code='verify_cppt',label='Verifikasi CPPT QA')
        PrivilegeSnapshot.objects.create(pegawai=self.employee,unit_kerja=self.unit,action_code=code,valid_from=timezone.localdate(),source_decision=self.spk)
        PenugasanDpjpEpisode.objects.create(visit=self.visit,doctor=self.user,unit=self.unit,assignment_type='PRIMARY',valid_from=timezone.localdate(),valid_until=timezone.localdate(),source_version='qa-assignment',assigned_by=reviewer,is_active=True)
        wf=IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit)
        context=resolve_professional_context(self.user,self.visit,self.service,at=timezone.now())
        payload={'subjektif':'Sintetis S','objektif':'Sintetis O','asesmen':'Sintetis A','plan':'Sintetis P'}
        note=create_care_note(self.visit,wf,self.user,format_code='SOAP',payload=payload,context=context)
        sign_care_note(self.user,note.pk,note.version);note.refresh_from_db()
        return note,payload

    def test_competing_dpjp_verifications_one_revision_signature(self):
        from pasien.services.professional_cppt import verify_cppt
        from pasien.models import VerifikasiCppt
        note,_=self.signed_note()
        def verify():return verify_cppt(User.objects.get(pk=self.user.pk),note.pk,note.version,uuid4())
        result=self.race([verify,verify]);self.assertEqual([r[0] for r in result],['ok','ok'])
        self.assertEqual(result[0][1]['verification_id'],result[1][1]['verification_id']);self.assertEqual(VerifikasiCppt.objects.count(),1)

    def test_verification_vs_correction_preserves_old_revision(self):
        from pasien.services.professional_cppt import verify_cppt,correct_care_note
        from pasien.models import VerifikasiCppt
        note,payload=self.signed_note();original=note.care_revisions.get().snapshot
        def verify():return verify_cppt(User.objects.get(pk=self.user.pk),note.pk,note.version,uuid4())
        def correct():return correct_care_note(User.objects.get(pk=self.user.pk),note.pk,note.version,{**payload,'objektif':'Temuan koreksi sintetis'},'Alasan koreksi sintetis')
        result=self.race([verify,correct]);self.assertEqual(result[1][0],'ok')
        note.refresh_from_db();self.assertFalse(note.verifikasi_dpjp);self.assertEqual(note.care_revisions.count(),2)
        self.assertEqual(note.care_revisions.order_by('version').first().snapshot,original)
        if VerifikasiCppt.objects.exists():self.assertEqual(VerifikasiCppt.objects.get().revision.snapshot,original)
