import json
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


@override_settings(IGD_WORKFLOW_ENABLED=True,IGD_PROFESSIONAL_CARE_ENABLED=True)
class ProfessionalHttpTest(ProfessionalCareCase):
    def setUp(self):self.client.force_login(self.user)

    def test_catalogue_is_scoped_read_only(self):
        from pasien.models import IgdAssessmentWorkflow
        response=self.client.get(reverse('pasien:igd_professional_catalogue',args=[self.visit.pk]))
        self.assertEqual(response.status_code,200);self.assertIn(self.service.pk,[s['id'] for s in response.json()['services']])
        self.assertFalse(IgdAssessmentWorkflow.objects.exists());self.assertIn('no-store',response['Cache-Control'])

    def test_quote_get_creates_no_records(self):
        from pasien.models import BillingItem,CPPT
        response=self.client.get(reverse('pasien:igd_professional_quote',args=[self.visit.pk]),{'service':self.service.pk})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['quote']['status'],'UNPRICED')
        self.assertFalse(BillingItem.objects.exists());self.assertFalse(CPPT.objects.exists())

    @override_settings(IGD_PROFESSIONAL_CARE_ENABLED=False)
    def test_flag_off_lookup_unavailable(self):
        response=self.client.get(reverse('pasien:igd_professional_catalogue',args=[self.visit.pk]))
        self.assertEqual(response.status_code,404)

    def test_invalid_operation_payload_is_400_not_500(self):
        from uuid import uuid4
        response=self.client.post(reverse('pasien:igd_workflow_action',args=[self.visit.pk]),json.dumps({'operation':'professional_execute','fields':{'service_id':self.service.pk,'source':'DIRECT','quantity':'NaN'},'version':0,'request_id':str(uuid4())}),content_type='application/json')
        self.assertEqual(response.status_code,400)

    def test_purpose_scoped_panel_renders(self):
        response=self.client.get(reverse('pasien:igd_workflow',args=[self.visit.pk]),{'step':9})
        self.assertEqual(response.status_code,200);self.assertContains(response,'professional-care-panel')
        self.assertNotContains(response,'data-operation="cppt"')
