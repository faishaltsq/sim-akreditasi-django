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
        save_step(self.visit.pk, self.user, 7, {}, 0)
        self.assertFalse(OrderPenunjang.objects.filter(kunjungan=self.visit).exists())

    def test_step7_draft_rejects_retired_fields(self):
        from pasien.services.igd_assessment_workflow import WorkflowValidation, save_step
        with self.assertRaises(WorkflowValidation):
            save_step(self.visit.pk, self.user, 7, {'penunjang_ekg': 'Hasil eksternal'}, 0)
        self.visit.refresh_from_db()
        self.assertFalse(self.visit.penunjang_ekg)

    def test_snapshot_keeps_retired_penunjang_fields(self):
        from pasien.models import IgdAssessmentWorkflow
        from pasien.services.igd_assessment_workflow import save_step
        from pasien.services.igd_finalization import clinical_snapshot
        self.visit.penunjang_ekg = 'EKG irama sinus'
        self.visit.penunjang_hasil_kritis = 'Troponin meningkat'
        self.visit.save(update_fields=['penunjang_ekg', 'penunjang_hasil_kritis'])
        save_step(self.visit.pk, self.user, 7, {}, 0)
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        snapshot = clinical_snapshot(self.visit, workflow)
        self.assertEqual(snapshot['visit']['penunjang_ekg'], 'EKG irama sinus')
        self.assertEqual(snapshot['visit']['penunjang_hasil_kritis'], 'Troponin meningkat')

    def make_catalogue_item(self, kode='uji-lab-klinik-hematologi-1', required=('specimen',), variants=None):
        from klinis.models import ItemPenunjang, KategoriPenunjang
        l1, _ = KategoriPenunjang.objects.get_or_create(kode='uji-laboratorium', defaults={'nama': 'Uji Laboratorium', 'level': 1})
        l2, _ = KategoriPenunjang.objects.get_or_create(kode='uji-laboratorium-klinik', defaults={'nama': 'Uji Klinik', 'level': 2, 'parent': l1})
        l3, _ = KategoriPenunjang.objects.get_or_create(kode='uji-laboratorium-klinik-hematologi', defaults={'nama': 'Uji Hematologi', 'level': 3, 'parent': l2})
        return ItemPenunjang.objects.create(
            kode=kode, nama='Pemeriksaan uji katalog', group=l3, jenis_order='LAB',
            destination=self.unit, active=True, source_version='UJI-2026-11-17',
            reviewed_by=self.user, preparation_schema={'required': list(required)},
            variants=variants or {})

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_step7_has_no_legacy_menus(self):
        response = self.client.get(reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=7')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for retired in ('Catat hasil / pembaruan operasional', 'Lampiran Hasil / Dokumen', 'Unggah Lampiran', 'igd-upload-form'):
            self.assertNotIn(retired, html)
        self.assertIn('id="igd-ancillary"', html)
        self.assertIn('data-anc-level="4"', html)

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_step7_renders_cascade(self):
        html = self.client.get(reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=7').content.decode()
        for number in (1, 2, 3, 4):
            self.assertIn(f'id="anc-level-{number}"', html)
        for key in ('fasting', 'pregnancy', 'contrast_allergy', 'specimen', 'site', 'region',
                    'side', 'contrast', 'external_destination'):
            self.assertIn(f'id="anc-{key}"', html)
        self.assertIn('id="anc-basket"', html)
        self.assertIn('Kirim Semua Order Terpilih', html)

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_step7_has_no_save_buttons(self):
        html = self.client.get(reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=7').content.decode()
        self.assertNotIn('value="save"', html)
        self.assertNotIn('value="next"', html)
        self.assertIn('Lanjut ke Penetapan Diagnosis', html)

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_step7_draft_empty_payload_accepted(self):
        response = self.client.post(
            reverse('pasien:igd_workflow_draft', args=[self.visit.pk, 7]),
            json.dumps({'fields': {}, 'version': 0}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['step'], 7)

    def test_cascade_payload_carries_nine_keys(self):
        item = self.make_catalogue_item(required=('specimen', 'external_destination'))
        preparation = {'fasting': 'UNKNOWN', 'pregnancy': 'UNKNOWN', 'contrast_allergy': 'UNKNOWN',
                       'specimen': 'DARAH VENA', 'site': 'Sela iga 4', 'region': 'Toraks',
                       'side': 'DEXTER', 'contrast': 'POLOS', 'external_destination': 'RS Rujukan Uji'}
        result = self.action('order_batch', {'items': [{'item_id': item.pk, 'prioritas': 'CITO',
                                                        'indication': 'Indikasi klinis synthetic',
                                                        'preparation': preparation}]})
        order = OrderPenunjang.objects.get(pk=result['order_ids'][0])
        self.assertEqual(set(order.preparation), set(preparation))
        self.assertEqual(order.preparation['external_destination'], 'RS Rujukan Uji')
        self.assertEqual(order.destination, self.unit)

    def test_catalogue_requires_specimen_is_orderable(self):
        from klinis.services.penunjang_catalogue import list_choices
        item = self.make_catalogue_item()
        result = list_choices(self.user, parent_id=item.group_id)
        self.assertEqual([row['kode'] for row in result['results']], [item.kode])
        self.assertEqual(result['results'][0]['preparation_schema']['required'], ['specimen'])
        self.assertEqual(result['results'][0]['path'][-1]['kode'], item.group.kode)

    def test_variant_must_match_catalogue(self):
        item = self.make_catalogue_item(required=(), variants={'specimen': ['SERUM', 'PLASMA']})
        with self.assertRaises(ValueError):
            self.action('order_batch', {'items': [{'item_id': item.pk, 'prioritas': 'RUTIN',
                                                   'indication': 'Indikasi klinis synthetic',
                                                   'preparation': {'specimen': 'URIN'}}]})

    def test_empty_branch_hidden_from_cascade(self):
        from klinis.models import KategoriPenunjang
        from klinis.services.penunjang_catalogue import list_choices
        item = self.make_catalogue_item()
        empty = KategoriPenunjang.objects.create(kode='uji-laboratorium-klinik-kosong', nama='Kelompok Kosong',
                                                 level=3, parent=item.group.parent)
        with override_settings(IGD_PENUNJANG_HIDE_EMPTY_BRANCHES=True):
            hidden = [row['kode'] for row in list_choices(self.user, parent_id=item.group.parent_id)['results']]
        with override_settings(IGD_PENUNJANG_HIDE_EMPTY_BRANCHES=False):
            shown = [row['kode'] for row in list_choices(self.user, parent_id=item.group.parent_id)['results']]
        self.assertIn(item.group.kode, hidden)
        self.assertNotIn(empty.kode, hidden)
        self.assertIn(empty.kode, shown)

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
