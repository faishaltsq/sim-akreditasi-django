import json

from django.test import Client, override_settings
from django.urls import reverse

from pasien.models import IgdAssessmentWorkflow
from pasien import tests_igd_workflow as workflow_tests


@override_settings(IGD_WORKFLOW_ENABLED=True)
class IgdWorkflowPageTest(workflow_tests.IgdWorkflowTest):
    def url(self):
        return reverse('pasien:igd_workflow', args=[self.visit.pk])

    def test_get_renders_eleven_steps_without_database_writes(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['steps']), 11)
        self.assertContains(response, self.patient.no_rm)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_enabled_dashboard_shortcuts_use_the_workflow(self):
        response = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(response.status_code,200)
        for step in (7,9,11):
            self.assertContains(response,self.url()+f'?step={step}')
        self.assertNotContains(response,f'data-bs-target="#modalCPPT{self.visit.pk}"')

    def test_draft_save_and_reopen(self):
        url = reverse('pasien:igd_workflow_draft', args=[self.visit.pk, 3])
        response = self.client.post(url, json.dumps({'version': 0, 'fields': {'anamnesis_rps': 'Keluhan tersimpan'}}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['version'], 1)
        page = self.client.get(self.url() + '?step=3')
        self.assertContains(page, 'Keluhan tersimpan')
        stale = self.client.post(url, json.dumps({'version': 0, 'fields': {'anamnesis_rps': 'Timpa'}}), content_type='application/json')
        self.assertEqual(stale.status_code, 409)

    def test_gate_defaults_off_without_affecting_legacy(self):
        with override_settings(IGD_WORKFLOW_ENABLED=False):
            self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.get(reverse('pasien:igd_dashboard')).status_code, 200)

    def test_mutation_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse('pasien:igd_workflow_draft', args=[self.visit.pk, 3])
        response = client.post(url, json.dumps({'version': 0, 'fields': {'anamnesis_rps': 'Tanpa CSRF'}}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_unknown_step_and_malformed_payload_are_rejected(self):
        self.assertEqual(self.client.get(self.url() + '?step=12').status_code, 400)
        url = reverse('pasien:igd_workflow_draft', args=[self.visit.pk, 3])
        for data in ('[]', 'null', '{bad', '{"fields":[]}'):
            with self.subTest(data=data):
                self.assertEqual(self.client.post(url, data, content_type='application/json').status_code, 400)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_cannot_mass_assign_visit_status(self):
        url = reverse('pasien:igd_workflow_draft', args=[self.visit.pk, 3])
        response = self.client.post(url, json.dumps({'version': 0, 'fields': {'status': 'PULANG'}}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, 'DAFTAR')

    def test_initial_form_keeps_initial_values_after_evaluation(self):
        from pasien.services.igd_assessment_workflow import save_step
        workflow = save_step(self.visit.pk, self.user, 4, {'ttv_nadi': '100'}, 0)
        save_step(self.visit.pk, self.user, 10, {'ttv_nadi': '80'}, workflow.version)
        initial = self.client.get(self.url() + '?step=4')
        evaluation = self.client.get(self.url() + '?step=10')
        self.assertEqual(initial.context['form']['ttv_nadi'].value(), 100)
        self.assertEqual(evaluation.context['form']['ttv_nadi'].value(), 80)

    def test_print_does_not_conflate_triage_with_death(self):
        response = self.client.get(reverse('pasien:cetak_asesmen_medis_igd', args=[self.visit.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Rutin / Hitam / DOA')

    def test_mobile_navigation_and_nonoverlapping_action_layout(self):
        response = self.client.get(self.url())
        self.assertContains(response, 'id="igd-step-select"')
        self.assertNotContains(response, 'position:sticky')

    def test_viewer_can_read_but_cannot_write_clinical_draft(self):
        from django.contrib.auth.models import User
        from accounts.models import UserProfile
        user = User.objects.create_user('workflow_viewer')
        UserProfile.objects.update_or_create(user=user, defaults={'role': 'ASESOR', 'unit_kerja': self.unit})
        self.client.force_login(user)
        response = self.client.get(self.url() + '?step=3')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['readonly'])
        self.assertTrue(response.context['form'].fields['anamnesis_rps'].disabled)
        url = reverse('pasien:igd_workflow_draft', args=[self.visit.pk, 3])
        response = self.client.post(url, json.dumps({'version': 0, 'fields': {'anamnesis_rps': 'Tidak boleh'}}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_new_numeric_triage_requires_explicit_system(self):
        url = reverse('pasien:igd_workflow_draft', args=[self.visit.pk, 2])
        response = self.client.post(url, json.dumps({'version': 0, 'fields': {'triase_kategori': 'KATEGORI_3'}}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())
