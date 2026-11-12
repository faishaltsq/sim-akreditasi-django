from unittest.mock import patch
from pasien import tests_igd_workflow as fixtures
from akreditasi.system_models import SystemConfig
from klinis.models import MasterIcd10


class IgdAiTest(fixtures.IgdWorkflowTest):
    def setUp(self):
        super().setUp()
        SystemConfig._solo_cache = None
        self.addCleanup(setattr, SystemConfig, '_solo_cache', None)

    def test_disabled_ai_does_not_call_provider(self):
        from klinis.services.ai_igd import generate_igd_suggestions
        with patch('klinis.services.ai_igd._call_deepseek') as transport:
            result = generate_igd_suggestions(self.visit,self.user)
        self.assertFalse(result['success'])
        transport.assert_not_called()

    def enable_ai(self):
        cfg = SystemConfig.get_solo()
        cfg.ai_enabled = True
        cfg.ai_enable_igd = True
        cfg.save()
        MasterIcd10.objects.get_or_create(kode='QA.TEST',defaults={'nama':'Nyeri uji'})

    def test_ai_payload_has_no_raw_patient_identity(self):
        self.enable_ai()
        from klinis.services.ai_igd import generate_igd_suggestions
        with patch('klinis.services.ai_igd._call_deepseek', return_value={'success':True,'data':{'medical':[{'kode':'QA.TEST','alasan':'Kandidat untuk ditinjau'}],'nursing':[]}}) as transport:
            result = generate_igd_suggestions(self.visit,self.user,query=self.patient.nama_lengkap+' 3273010101900001 nyeri')
        self.assertTrue(result['success'])
        prompt = transport.call_args.args[0]
        self.assertNotIn(self.patient.nama_lengkap,prompt)
        self.assertNotIn('3273010101900001',prompt)
        self.assertEqual(result['suggestions']['medical'][0]['kode'],'QA.TEST')

    def test_hallucinated_code_is_rejected_without_mutation(self):
        self.enable_ai()
        from klinis.services.ai_igd import generate_igd_suggestions
        with patch('klinis.services.ai_igd._call_deepseek', return_value={'success':True,'data':{'medical':[{'kode':'DOES.NOT.EXIST'}],'nursing':[]}}):
            result = generate_igd_suggestions(self.visit,self.user,query='nyeri')
        self.assertFalse(result['success'])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk,'')

    def test_accepted_medical_ai_preserves_unselected_manual_nursing(self):
        import json
        from django.test import override_settings
        from django.urls import reverse
        from pasien.services.igd_assessment_workflow import save_step
        self.enable_ai()
        workflow = save_step(self.visit.pk,self.user,8,{'diagnosis_mode':'MANUAL','diagnosa_keperawatan_sdki':'Diagnosis keperawatan manual'},0)
        with override_settings(IGD_WORKFLOW_ENABLED=True):
            with patch('klinis.services.ai_igd._call_deepseek',return_value={'success':True,'data':{'medical':[{'kode':'QA.TEST'}],'nursing':[]}}):
                response = self.client.post(reverse('pasien:igd_workflow_ai',args=[self.visit.pk]),json.dumps({'query':'nyeri'}),content_type='application/json')
            self.assertEqual(response.status_code,200)
            ticket = response.json()['ticket']
            response = self.client.post(reverse('pasien:igd_workflow_draft',args=[self.visit.pk,8]),json.dumps({'version':workflow.version,'fields':{'diagnosis_mode':'AI','diagnosa_masuk':'QA.TEST','ai_ticket':ticket}}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk,'QA.TEST — Nyeri uji')
        self.assertEqual(self.visit.diagnosa_keperawatan_sdki,'Diagnosis keperawatan manual')
        self.assertEqual(self.visit.diagnosis_provenance['mode'],'AI')
