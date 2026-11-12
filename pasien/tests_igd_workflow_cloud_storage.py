import hashlib
import json
import os
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from pasien import tests_igd_workflow as fixtures
from pasien.models import LampiranAsesmen, IgdAssessmentWorkflow
from pasien.services.igd_actions import perform_action
from pasien.services.igd_assessment_workflow import WorkflowValidation
from sdm.storage_backend import StoredPrivateObject


@override_settings(IGD_WORKFLOW_ENABLED=True,SUPABASE_URL='https://example.test',SUPABASE_KEY='fixture-only',STORAGES={'default':{'BACKEND':'akreditasi.storage.SupabaseMediaStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class IgdCloudAttachmentsTest(fixtures.IgdWorkflowTest):
    content = b'%PDF-1.4\nsynthetic fixture'

    def upload(self):
        file=SimpleUploadedFile('hasil.pdf',self.content,content_type='application/pdf')
        return perform_action(self.visit.pk,self.user,'attachment',{'jenis':'PENUNJANG','filename':'hasil.pdf','size':len(self.content),'sha256':hashlib.sha256(self.content).hexdigest()},0,str(uuid4()),attachment=file)

    def test_provider_failure_does_not_persist_an_attachment(self):
        response=Mock(status_code=503,text='synthetic unavailable')
        with patch.dict(os.environ,{'HC_PRIVATE_STORAGE_SERVICE_KEY':'fixture-only'}), patch('akreditasi.storage.SupabaseMediaStorage.exists',return_value=False), patch('requests.post',return_value=response), patch('requests.Session.request',return_value=response):
            with self.assertRaises(WorkflowValidation):self.upload()
        self.assertFalse(LampiranAsesmen.objects.filter(kunjungan=self.visit).exists())
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_cloud_object_uses_private_transport_and_scoped_download(self):
        key=f'health/{uuid4()}/{uuid4()}.pdf'
        backend=Mock()
        backend.upload.return_value=StoredPrivateObject(key,hashlib.sha256(self.content).hexdigest(),len(self.content),'application/pdf')
        backend.verify_anonymous_denial.return_value=True
        backend.fetch_object.return_value=self.content
        with patch('pasien.services.igd_attachments.private_storage',return_value=backend,create=True), patch('akreditasi.storage.SupabaseMediaStorage.exists',return_value=False), patch('requests.post',return_value=Mock(status_code=201)):
            result=self.upload()
            record=LampiranAsesmen.objects.get(pk=result['attachment_id'])
            self.assertEqual(record.file.name,'igd-private/'+key)
            backend.verify_anonymous_denial.assert_called_once_with(key)
            backend.verify_private_object.assert_called_once()
            response=self.client.get(reverse('pasien:igd_workflow_download',args=[self.visit.pk,record.pk]))
            self.assertEqual(response.status_code,200)
            self.assertEqual(b''.join(response.streaming_content),self.content)
            self.assertEqual(response['X-Content-Type-Options'],'nosniff')
            legacy=self.client.get(reverse('pasien:asesmen_lampiran_download',args=[self.visit.pk,record.pk]))
            self.assertEqual(legacy.status_code,200)
            self.assertEqual(b''.join(legacy.streaming_content),self.content)
            self.assertEqual(legacy['Cache-Control'],'no-store')

    def test_failed_privacy_check_rolls_back_and_deletes_uploaded_object(self):
        from sdm.storage_backend import PrivateStorageError
        key=f'health/{uuid4()}/{uuid4()}.pdf'
        backend=Mock()
        backend.upload.return_value=StoredPrivateObject(key,hashlib.sha256(self.content).hexdigest(),len(self.content),'application/pdf')
        backend.verify_anonymous_denial.side_effect=PrivateStorageError('Synthetic privacy failure')
        with patch('pasien.services.igd_attachments.private_storage',return_value=backend):
            with self.assertRaises(WorkflowValidation):self.upload()
        backend.delete.assert_called_once_with(key)
        self.assertFalse(LampiranAsesmen.objects.filter(kunjungan=self.visit).exists())
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())
