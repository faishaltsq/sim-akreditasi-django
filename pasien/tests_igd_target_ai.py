from unittest.mock import patch
from django.test import override_settings
from django.urls import reverse
from pasien.tests_igd_workflow_ai import IgdAiTest


class TargetAiTest(IgdAiTest):
    def test_target_gate_and_candidate_validation(self):
        from klinis.services.ai_igd_targets import generate_target
        with patch('klinis.services.ai_igd_targets._call_deepseek') as transport:
            result=generate_target(self.visit,self.user,'medical','nyeri')
        self.assertFalse(result['success']);transport.assert_not_called()
        self.enable_ai()
        with patch('klinis.services.ai_igd_targets._call_deepseek',return_value={'success':True,'data':{'candidates':[{'kode':'QA.TEST','alasan':'Uji'}]}}):
            result=generate_target(self.visit,self.user,'medical','nyeri')
        self.assertTrue(result['success'])
        self.assertEqual(result['candidates'][0]['kode'],'QA.TEST')
        with patch('klinis.services.ai_igd_targets._call_deepseek',return_value={'success':True,'data':{'candidates':[{'kode':'FAKE','alasan':'Uji'}]}}):
            self.assertFalse(generate_target(self.visit,self.user,'medical','nyeri')['success'])

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_medical_target_ticket_is_accepted_only_as_diagnosis(self):
        import json
        from uuid import uuid4
        self.enable_ai()
        with patch('klinis.services.ai_igd_targets._call_deepseek',return_value={'success':True,'data':{'candidates':[{'kode':'QA.TEST'}]}}):
            response=self.client.post(reverse('pasien:igd_workflow_ai',args=[self.visit.pk]),json.dumps({'target':'medical','query':'nyeri'}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        result=response.json()
        from pasien.services.igd_actions import perform_action
        saved=perform_action(self.visit.pk,self.user,'diagnosis_set',{'changes':[{'op':'upsert','temp_id':'a','mode':'AI','code':'QA.TEST','is_primary':True,'ai_ticket':result['ticket']}]},0,str(uuid4()))
        self.assertEqual(self.visit.diagnoses.get().mode,'AI')
        with self.assertRaises(ValueError):
            perform_action(self.visit.pk,self.user,'plan_action',{'jenis':'ICD9','kode':'QA.TEST','mode':'AI','ai_ticket':result['ticket']},saved['version'],str(uuid4()))
