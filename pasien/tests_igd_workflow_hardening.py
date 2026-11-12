from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.urls import reverse

from accounts.models import UserProfile
from pasien import tests_igd_workflow as fixtures
from pasien.models import IgdAssessmentWorkflow, TindakanAsesmen
from pasien.services.igd_actions import perform_action
from pasien.services.igd_assessment_workflow import save_step, WorkflowValidation
from pasien.services.igd_finalization import missing_sections


class IgdHardeningTest(fixtures.IgdWorkflowTest):
    def test_nurse_cannot_cancel_medical_plan(self):
        self.user.is_superuser = False
        self.user.save(update_fields=['is_superuser'])
        planned = perform_action(self.visit.pk, self.user, 'plan_action', {'jenis':'BEBAS','nama':'Rencana medis'}, 0, str(uuid4()))
        nurse = User.objects.create_user('qa_cancel_nurse')
        UserProfile.objects.update_or_create(user=nurse, defaults={'role':'STAF_NAKES','profesi':'PERAWAT','unit_kerja':self.unit})
        with self.assertRaises(PermissionDenied):
            perform_action(self.visit.pk, nurse, 'cancel_action', {'action_id':planned['action_id']}, planned['version'], str(uuid4()))
        self.assertEqual(TindakanAsesmen.objects.get(pk=planned['action_id']).execution_status, 'PLANNED')

    def test_empty_observations_are_not_complete_vitals(self):
        workflow = save_step(self.visit.pk, self.user, 4, {'ttv_nadi':''}, 0)
        workflow = save_step(self.visit.pk, self.user, 10, {'ttv_nadi':'','disposisi_kondisi_akhir':'MEMBAIK','evaluasi_respon_terapi':'Evaluasi sintetis'}, workflow.version)
        self.visit.refresh_from_db()
        missing = missing_sections(self.visit, workflow)
        self.assertIn('initial_vitals', missing)
        self.assertIn('evaluation', missing)

    def test_unassessed_allergy_is_not_complete_screening(self):
        workflow = save_step(self.visit.pk, self.user, 3, {'skrining_alergi_status':'BELUM'}, 0)
        workflow = save_step(self.visit.pk, self.user, 5, {'skrining_gizi_mst':0,'skrining_jatuh_skor':0}, workflow.version)
        self.visit.refresh_from_db()
        self.assertIn('screening', missing_sections(self.visit, workflow))

    def test_partial_morse_can_be_saved_without_inventing_score(self):
        workflow = save_step(self.visit.pk, self.user, 5, {'skrining_jatuh_detail':{'jatuh_riwayat':0}}, 0)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.skrining_jatuh_detail, {'jatuh_riwayat':0})
        self.assertIsNone(self.visit.skrining_jatuh_skor)
        self.assertEqual(workflow.version, 1)

    def test_complete_gcs_components_set_total_in_observation(self):
        workflow = save_step(self.visit.pk, self.user, 4, {'gcs_e':4,'gcs_v':5,'gcs_m':6}, 0)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.ttv_gcs, '15')
        self.assertEqual(workflow.observations.get().data['ttv_gcs'], '15')

    def test_observation_correction_appends_and_references_original(self):
        workflow = save_step(self.visit.pk, self.user, 4, {'ttv_nadi':100}, 0)
        original = workflow.observations.get()
        save_step(self.visit.pk, self.user, 4, {'ttv_nadi':90,'corrects_id':original.pk}, workflow.version)
        original.refresh_from_db()
        correction = workflow.observations.order_by('-pk').first()
        self.assertEqual(original.data['ttv_nadi'],100)
        self.assertEqual(correction.corrects_id,original.pk)
        self.assertEqual(correction.observed_at,original.observed_at)
        self.assertEqual(correction.data['ttv_nadi'],90)

    def test_administrator_can_explicitly_opt_in_to_igd_ai(self):
        from akreditasi.system_models import SystemConfig
        self.addCleanup(setattr, SystemConfig, '_solo_cache', None)
        profile = self.user.profile
        profile.role = 'SUPER_ADMIN'
        profile.save(update_fields=['role'])
        response = self.client.post(reverse('accounts:update_system_config'), {'ai_enable_igd':'true'})
        self.assertRedirects(response, reverse('accounts:admin_control_center'), fetch_redirect_response=False)
        self.assertTrue(SystemConfig.objects.get(pk=1).ai_enable_igd)
        SystemConfig._solo_cache = None

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_operational_forms_are_rendered_without_nested_forms(self):
        from html.parser import HTMLParser
        class Forms(HTMLParser):
            depth = 0
            nested = False
            def handle_starttag(self, tag, attrs):
                if tag == 'form':
                    self.nested |= self.depth > 0
                    self.depth += 1
            def handle_endtag(self, tag):
                if tag == 'form':
                    self.depth -= 1
        for step, expected in ((7,'data-operation="order"'),(8,'data-operation="plan_action"'),(9,'data-operation="cppt"'),(11,'data-operation="finalize"')):
            with self.subTest(step=step):
                response = self.client.get(reverse('pasien:igd_workflow', args=[self.visit.pk]) + f'?step={step}')
                self.assertContains(response, expected)
                parser = Forms()
                parser.feed(response.content.decode())
                self.assertFalse(parser.nested)
                self.assertEqual(parser.depth, 0)
