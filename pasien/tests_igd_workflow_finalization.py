from uuid import uuid4
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import UserProfile
from pasien import tests_igd_workflow as fixtures
from pasien.models import IgdAssessmentWorkflow, IgdAssessmentRevision, DischargeRecord


class IgdFinalizationTest(fixtures.IgdWorkflowTest):
    def action(self, op, data, version, key=None, user=None):
        from pasien.services.igd_actions import perform_action
        return perform_action(self.visit.pk, user or self.user, op, data, version, key or str(uuid4()))

    def ready(self):
        from pasien.services.igd_assessment_workflow import save_step
        version = 0
        for step, data in [
            (2, {'triase_skala':'ATS','triase_kategori':'KATEGORI_3','triage':'KUNING','cara_datang':'SENDIRI','fisik_airway':'Paten'}),
            (3, {'anamnesis_rps':'Keluhan sintetis','skrining_alergi_status':'TIDAK_ADA'}),
            (4, {'ttv_nadi':100,'ttv_skala_nyeri':0}),
            (6, {'fisik_lokalis':'Pemeriksaan sintetis'}),
            (8, {'diagnosa_masuk':'Diagnosis uji'}),
            (10, {'ttv_nadi':80,'disposisi_kondisi_akhir':'MEMBAIK','evaluasi_respon_terapi':'Keluhan berkurang'}),
            (11, {'disposisi_tindak_lanjut':'RAWAT_JALAN'}),
        ]:
            version = save_step(self.visit.pk,self.user,step,data,version).version
        return version

    def signed(self):
        return self.action('sign', {'section':'MEDIS','exemptions':{'nursing':'Tidak ada indikasi 3S pada kasus sintetis','screening':'Skrining tidak dapat diselesaikan pada uji','investigations':'Tidak ada indikasi penunjang','care':'Tidak ada tindakan pada uji'}}, self.ready())['version']

    def test_unsigned_finalization_rolls_back(self):
        from pasien.services.igd_assessment_workflow import WorkflowValidation
        version = self.ready()
        with self.assertRaises(WorkflowValidation):
            self.action('finalize', {'outcome':'PULANG','resume':'Resume sintetis'}, version)
        self.assertEqual(IgdAssessmentWorkflow.objects.get(kunjungan=self.visit).status,'DRAFT')
        self.assertFalse(DischargeRecord.objects.filter(kunjungan=self.visit).exists())

    def test_signed_finalization_replay_and_immutable_snapshot(self):
        version = self.signed()
        key = str(uuid4())
        result = self.action('finalize', {'outcome':'PULANG','resume':'Resume sintetis'}, version, key)
        replay = self.action('finalize', {'outcome':'PULANG','resume':'Resume sintetis'}, version, key)
        self.assertEqual(result['revision_id'], replay['revision_id'])
        self.assertEqual(IgdAssessmentRevision.objects.count(),1)
        self.assertEqual(DischargeRecord.objects.filter(kunjungan=self.visit).count(),1)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status,'PULANG')
        self.assertEqual(self.visit.discharge.status_clearance,'PROSES')
        revision = IgdAssessmentRevision.objects.get()
        self.assertEqual(revision.snapshot['patient']['nama_lengkap'],self.patient.nama_lengkap)
        self.patient.nama_lengkap = 'Nama diubah setelah final'
        self.patient.save()
        revision.refresh_from_db()
        self.assertNotEqual(revision.snapshot['patient']['nama_lengkap'],self.patient.nama_lengkap)

    def test_addendum_preserves_original_after_patient_left_igd(self):
        version = self.signed()
        result = self.action('finalize', {'outcome':'PULANG','resume':'Resume sintetis'}, version)
        original = IgdAssessmentRevision.objects.get(pk=result['revision_id']).snapshot
        newer = self.action('addendum', {'section':'MEDIS','reason':'Koreksi hasil pemeriksaan','text':'Keterangan tambahan terverifikasi'}, result['version'])
        self.assertEqual(IgdAssessmentRevision.objects.count(),2)
        self.assertEqual(IgdAssessmentRevision.objects.order_by('revision').first().snapshot,original)
        self.assertEqual(IgdAssessmentRevision.objects.get(pk=newer['revision_id']).snapshot['addenda'][-1]['text'],'Keterangan tambahan terverifikasi')

    def test_nurse_cannot_impersonate_medical_signer(self):
        from django.core.exceptions import PermissionDenied
        version = self.ready()
        nurse = User.objects.create_user('qa_signing_nurse')
        UserProfile.objects.update_or_create(user=nurse,defaults={'role':'STAF_NAKES','profesi':'PERAWAT','unit_kerja':self.unit})
        with self.assertRaises(PermissionDenied):
            self.action('sign', {'section':'MEDIS'}, version, user=nurse)

    def test_draft_change_invalidates_signature(self):
        from pasien.services.igd_assessment_workflow import save_step, WorkflowValidation
        version = self.signed()
        w = save_step(self.visit.pk,self.user,3,{'anamnesis_rps':'Perubahan setelah tanda tangan'},version)
        self.assertEqual(w.signatures,{})
        with self.assertRaises(WorkflowValidation):
            self.action('finalize',{'outcome':'PULANG','resume':'Resume'},w.version)

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_print_and_legacy_print_use_signed_snapshot(self):
        version = self.signed()
        self.action('finalize',{'outcome':'PULANG','resume':'Resume sintetis'},version)
        original_name = self.patient.nama_lengkap
        self.patient.nama_lengkap = 'Nama baru setelah final'
        self.patient.save()
        url = reverse('pasien:igd_workflow_resume',args=[self.visit.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,original_name)
        self.assertNotContains(response,'Nama baru setelah final')
        old = self.client.get(reverse('pasien:cetak_asesmen_medis_igd',args=[self.visit.pk]))
        self.assertRedirects(old,url,fetch_redirect_response=False)
