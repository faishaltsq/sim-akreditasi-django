from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import override_settings
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


@override_settings(IGD_WORKFLOW_ENABLED=True,IGD_PROFESSIONAL_CARE_ENABLED=True)
class ProfessionalHardeningTest(ProfessionalCareCase):
    def test_dpjp_assignment_identity_cannot_be_rewritten(self):
        from pasien.models import PenugasanDpjpEpisode
        reviewer=User.objects.create_superuser('qa-assignment-owner')
        assignment=PenugasanDpjpEpisode.objects.create(visit=self.visit,doctor=self.user,unit=self.unit,assignment_type='PRIMARY',valid_from=timezone.localdate(),valid_until=timezone.localdate(),source_version='qa-original-source',assigned_by=reviewer,is_active=True)
        assignment.source_version='Klaim sumber lain'
        with self.assertRaises(ValidationError):assignment.save()
    def test_dentist_with_personal_mandate_gets_only_professional_operations(self):
        from pasien.services.igd_actions import perform_action
        self.user.profile.profesi='DOKTER_GIGI';self.user.profile.save()
        self.assertEqual(self.context()['profile_profession'],'DOKTER_GIGI')
        with self.assertRaises(PermissionDenied):perform_action(self.visit.pk,self.user,'sign',{'section':'MEDIS'},0,uuid4())
    def test_limited_mandate_needs_reviewed_executable_limits(self):
        mentor=self.mentor()
        self.privilege.status_spk='DISETUJUI_MANDIRI_TERBATAS';self.privilege.batasan='Batas kuantitas sintetis wajib ditinjau';self.privilege.save()
        with self.assertRaises(PermissionDenied):self.context(supervisor=mentor.pk)

    def test_supervised_author_can_complete_own_note(self):
        from pasien.models import IgdAssessmentWorkflow
        from pasien.services.professional_cppt import create_care_note,sign_care_note
        mentor=self.mentor();self.privilege.status_spk='DISETUJUI_SUPERVISI';self.privilege.save()
        wf=IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit)
        note=create_care_note(self.visit,wf,self.user,format_code='SOAP',payload={'subjektif':'Uji','objektif':'Uji','asesmen':'Uji','plan':'Uji'},context=self.context(supervisor=mentor.pk))
        sign_care_note(self.user,note.pk,note.version)
        note.refresh_from_db();self.assertEqual(note.status,'SIGNED')
    def test_same_day_individual_revocation_denied(self):
        from sdm.services.clinical_access import revoke_spk
        self.context()
        with patch('sdm.services.clinical_access.require_hc_capability'):
            revoke_spk(actor=self.user,employee=self.employee,unit=self.unit,action_codes=['professional_care'],reason='Penarikan sintetis')
        with self.assertRaises(PermissionDenied):self.context()

    def test_legacy_cppt_writer_cannot_bypass_before_adoption(self):
        from django.urls import reverse
        from pasien.models import CPPT
        self.client.force_login(self.user)
        response=self.client.post(reverse('pasien:cppt_tambah',args=[self.visit.pk]),{'profesi':'DOKTER','nama_ppa':'Klaim palsu','subjektif':'x','objektif':'x','asesmen':'x','plan':'x','verifikasi_dpjp':'on'})
        self.assertEqual(response.status_code,409);self.assertFalse(CPPT.objects.exists())

    def test_assigned_dpjp_verifies_exact_revision_then_correction_unverifies(self):
        from pasien.models import IgdAssessmentWorkflow,PenugasanDpjpEpisode,VerifikasiCppt
        from pasien.services.professional_cppt import create_care_note,sign_care_note,verify_cppt,correct_care_note
        from sdm.models import ClinicalActionCode,PrivilegeSnapshot
        reviewer=User.objects.create_superuser('qa-assigner')
        code=ClinicalActionCode.objects.create(code='verify_cppt',label='Verifikasi catatan QA')
        PrivilegeSnapshot.objects.create(pegawai=self.employee,unit_kerja=self.unit,action_code=code,valid_from=timezone.localdate(),source_decision=self.spk)
        assignment=PenugasanDpjpEpisode.objects.create(visit=self.visit,doctor=self.user,unit=self.unit,assignment_type='PRIMARY',valid_from=timezone.localdate(),valid_until=timezone.localdate(),source_version='qa-reviewed-assignment',assigned_by=reviewer,is_active=True)
        wf=IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit)
        payload={'subjektif':'Keluhan sintetis','objektif':'Temuan sintetis','asesmen':'Asesmen sintetis','plan':'Rencana sintetis'}
        note=create_care_note(self.visit,wf,self.user,format_code='SOAP',payload=payload,context=self.context())
        sign_care_note(self.user,note.pk,note.version);note.refresh_from_db();key=uuid4()
        result=verify_cppt(self.user,note.pk,note.version,key)
        self.assertEqual(result['verification_id'],verify_cppt(self.user,note.pk,note.version,key)['verification_id'])
        verification=VerifikasiCppt.objects.get();original=verification.revision.snapshot
        correct_care_note(self.user,note.pk,note.version,{**payload,'objektif':'Temuan koreksi'},'Alasan koreksi sintetis')
        note.refresh_from_db();self.assertFalse(note.verifikasi_dpjp)
        self.assertEqual(VerifikasiCppt.objects.get().revision.snapshot,original)
        assignment.is_active=False;assignment.save()
        with self.assertRaises(PermissionDenied):verify_cppt(self.user,note.pk,note.version,uuid4())

    def switch_profession(self,code,family,profile):
        from sdm.models import MasterProfesiPegawai,MasterJenjangProfesi
        master,_=MasterProfesiPegawai.objects.get_or_create(code=code,defaults={'nama':code,'keluarga':family})
        master.keluarga=family;master.reviewed_by=self.user;master.reviewed_at=timezone.now();master.is_active=True;master.save()
        grade=MasterJenjangProfesi.objects.create(profesi=master,kode='QA',nama='Jenjang QA',urutan=1)
        self.employee.profesi_master=master;self.employee.jenjang_master=grade;self.employee.save()
        self.catalogue.jenjang=grade;self.catalogue.save()
        self.user.profile.profesi=profile;self.user.profile.save()

    def test_nutrition_author_can_sign_adime_but_not_medical_episode(self):
        from pasien.services.igd_actions import perform_action
        from pasien.models import CPPT
        self.switch_profession('DIET','NAKES_LAIN','NUTRISIONIS')
        self.service.note_format='ADIME';self.service.group='OTHER_PPA';self.service.save()
        payload={k:'Catatan gizi sintetis' for k in ('asesmen_gizi','diagnosis_gizi','intervensi','monitoring','evaluasi')}
        result=perform_action(self.visit.pk,self.user,'cppt_create',{'service_id':self.service.pk,'format_code':'ADIME','payload':payload},0,uuid4())
        signed=perform_action(self.visit.pk,self.user,'cppt_sign',{'note_id':result['cppt_id'],'note_version':result['note_version']},result['version'],uuid4())
        self.assertEqual(CPPT.objects.get().status,'SIGNED')
        with self.assertRaises(PermissionDenied):perform_action(self.visit.pk,self.user,'sign',{'section':'MEDIS'},signed['version'],uuid4())
        with self.assertRaises(PermissionDenied):perform_action(self.visit.pk,self.user,'prescription_save',{},signed['version'],uuid4())

    def test_spiritual_assignment_is_not_a_medical_privilege(self):
        from klinis.models import ProfessionalCareGrant
        from pasien.services.igd_actions import perform_action
        self.switch_profession('QA-ROHANI','NON_KLINIS','LAINNYA')
        self.employee.kategori='NON_PPA';self.employee.save()
        self.service.authority_kind='SUPPORT';self.service.note_format='SPIRITUAL';self.service.group='OTHER_PPA';self.service.save()
        reviewer=User.objects.create_user('qa-support-reviewer')
        ProfessionalCareGrant.objects.create(user=self.user,unit=self.unit,service=self.service,capability='SUPPORT_SERVICE',valid_from=timezone.localdate(),valid_until=timezone.localdate(),source_version='qa-reviewed-competency',reviewed_by=reviewer,reviewed_at=timezone.now(),is_active=True)
        payload={k:'Pendampingan sintetis' for k in ('kondisi_psikospiritual','pendampingan','respon_pasien')}
        result=perform_action(self.visit.pk,self.user,'cppt_create',{'service_id':self.service.pk,'format_code':'SPIRITUAL','payload':payload},0,uuid4())
        self.assertTrue(result['cppt_id'])
        with self.assertRaises(PermissionDenied):perform_action(self.visit.pk,self.user,'diagnosis_set',{},result['version'],uuid4())
