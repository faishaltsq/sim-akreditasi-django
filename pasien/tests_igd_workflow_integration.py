from uuid import uuid4
import json
from django.test import override_settings
from django.urls import reverse
from pasien import tests_igd_workflow as fixtures
from pasien.models import OrderPenunjang


class IgdWorkflowIntegrationTest(fixtures.IgdWorkflowTest):
    def action(self, operation, fields, version=0, key=None):
        from pasien.services.igd_actions import perform_action
        return perform_action(self.visit.pk, self.user, operation, fields, version, key or str(uuid4()))

    def test_order_submission_is_idempotent(self):
        key = str(uuid4())
        first = self.action('order', {'jenis':'LAB','nama_pemeriksaan':'Darah lengkap','prioritas':'CITO','catatan_klinis':'Indikasi klinis synthetic'}, key=key)
        repeated = self.action('order', {'jenis':'LAB','nama_pemeriksaan':'Darah lengkap','prioritas':'CITO','catatan_klinis':'Indikasi klinis synthetic'}, key=key)
        self.assertEqual(first['order_id'], repeated['order_id'])
        self.assertEqual(OrderPenunjang.objects.filter(kunjungan=self.visit).count(), 1)
        with self.assertRaises(ValueError):
            self.action('order', {'jenis':'LAB','nama_pemeriksaan':'Order berbeda','prioritas':'CITO','catatan_klinis':'Indikasi klinis synthetic'}, key=key)

    def test_draft_does_not_send_order(self):
        from pasien.services.igd_assessment_workflow import save_step
        save_step(self.visit.pk, self.user, 7, {'penunjang_ekg':'Hasil eksternal'}, 0)
        self.assertFalse(OrderPenunjang.objects.filter(kunjungan=self.visit).exists())

    def test_manual_order_requires_clinical_indication(self):
        with self.assertRaises(ValueError):
            self.action('order',{'jenis':'LAB','nama_pemeriksaan':'Synthetic manual','prioritas':'CITO'})
        self.assertFalse(self.visit.order_penunjang.exists())

    def test_plan_then_execute_links_cppt_and_one_bill(self):
        from pasien.models import TindakanAsesmen, BillingItem, CPPT
        planned = self.action('plan_action', {'jenis':'BEBAS','nama':'Perawatan uji','tarif':'12500','catatan_tarif':'Tarif manual disetujui','quantity':'1'})
        self.assertFalse(BillingItem.objects.filter(kunjungan=self.visit).exists())
        line = TindakanAsesmen.objects.get(pk=planned['action_id'])
        self.assertEqual(line.execution_status, 'PLANNED')
        key = str(uuid4())
        result = self.action('execute', {'action_id':line.pk}, planned['version'], key)
        replay = self.action('execute', {'action_id':line.pk}, planned['version'], key)
        self.assertEqual(result['billing_id'], replay['billing_id'])
        self.assertEqual(BillingItem.objects.filter(kunjungan=self.visit).count(), 1)
        self.assertEqual(CPPT.objects.filter(kunjungan=self.visit).count(), 1)
        line.refresh_from_db()
        self.assertEqual(line.performed_by, self.user)
        self.assertEqual(line.execution_status, 'PERFORMED')

    def test_partial_plan_does_not_erase_legacy_charge(self):
        from pasien.models import BillingItem
        bill = BillingItem.objects.create(kunjungan=self.visit, kategori='JASA_MEDIS', nama_item='Historis', harga_satuan=1000, sumber='ASESMEN')
        self.action('plan_action', {'jenis':'BEBAS','nama':'Rencana baru'})
        self.assertTrue(BillingItem.objects.filter(pk=bill.pk).exists())

    def test_tariff_edit_audits_before_and_after_amounts(self):
        from decimal import Decimal
        from akreditasi.models import AuditLog
        first = self.action('plan_action', {'jenis':'BEBAS','nama':'Tindakan tarif QA','tarif':'100','catatan_tarif':'Tarif awal disetujui'})
        self.action('plan_action', {'action_id':first['action_id'],'jenis':'BEBAS','nama':'Tindakan tarif QA','tarif':'150','catatan_tarif':'Revisi tarif disetujui'}, first['version'])
        audit = AuditLog.objects.filter(model_name='TindakanAsesmen',object_repr=f"Tindakan #{first['action_id']}").order_by('-pk').first()
        self.assertIsNotNone(audit)
        change = json.loads(audit.detail)
        self.assertEqual(Decimal(change['before']['tarif']),Decimal('100'))
        self.assertEqual(Decimal(change['after']['tarif']),Decimal('150'))
        self.assertEqual(change['reason'],'Revisi tarif disetujui')

    def test_cppt_does_not_accept_forged_profession(self):
        with self.assertRaises(ValueError):
            self.action('cppt', {'subjektif':'Uji','profesi':'DOKTER'})

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_http_order_and_scoped_catalogue(self):
        url = reverse('pasien:igd_workflow_action',args=[self.visit.pk])
        response = self.client.post(url,json.dumps({'operation':'order','fields':{'jenis':'EKG','nama_pemeriksaan':'EKG 12 lead','prioritas':'CITO','catatan_klinis':'Indikasi klinis synthetic'},'version':0,'request_id':str(uuid4())}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(OrderPenunjang.objects.get(kunjungan=self.visit).jenis,'EKG')
        response = self.client.get(reverse('pasien:igd_workflow_catalogue',args=[self.visit.pk])+'?type=ICD10&q=nyeri')
        self.assertEqual(response.status_code,200)
        self.assertIn('results',response.json())

    def test_result_is_scoped_and_explicitly_recorded(self):
        order = self.action('order',{'jenis':'EKG','nama_pemeriksaan':'EKG uji','prioritas':'RUTIN','catatan_klinis':'Indikasi klinis synthetic'})
        result = self.action('order_result',{'order_id':order['order_id'],'status':'SELESAI','hasil_pemeriksaan':'Hasil eksternal terverifikasi'},order['version'])
        record = OrderPenunjang.objects.get(pk=order['order_id'])
        self.assertEqual(record.status,'SELESAI')
        self.assertEqual(record.result_recorded_by,self.user)
        with self.assertRaises(ValueError):
            self.action('order_result',{'order_id':999999,'status':'SELESAI','hasil_pemeriksaan':'Salah pasien'},result['version'])

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_attachment_upload_and_download(self):
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from pasien.models import LampiranAsesmen
        with tempfile.TemporaryDirectory() as media:
            with override_settings(MEDIA_ROOT=media,STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}):
                url = reverse('pasien:igd_workflow_upload',args=[self.visit.pk])
                response = self.client.post(url,{'version':0,'request_id':str(uuid4()),'jenis':'PENUNJANG','file':SimpleUploadedFile('hasil.pdf',b'%PDF-1.4\nsynthetic fixture')})
                self.assertEqual(response.status_code,200)
                record = LampiranAsesmen.objects.get(kunjungan=self.visit)
                response = self.client.get(reverse('pasien:igd_workflow_download',args=[self.visit.pk,record.pk]))
                self.assertEqual(response.status_code,200)
                self.assertEqual(b''.join(response.streaming_content),b'%PDF-1.4\nsynthetic fixture')
