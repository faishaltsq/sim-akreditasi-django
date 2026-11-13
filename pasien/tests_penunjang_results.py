from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from accounts.models import UserProfile
from akreditasi.models import UnitKerja,AuditLog
from pasien import tests_laboratorium as legacy
from pasien.models import OrderPenunjang
from pasien.services.penunjang_results import record_result


class ResultBoundaryTest(legacy.LaboratoriumViewTest):
    def test_assigned_service_reads_cross_requesting_unit_only(self):
        self.order.destination=self.unit_lab;self.order.save(update_fields=['destination'])
        other=UnitKerja.objects.create(code='QA-OTHER-LAB',name='Other lab',level=3)
        hidden=OrderPenunjang.objects.create(kunjungan=self.kunjungan,jenis='LAB',nama_pemeriksaan='Other destination',destination=other)
        self.client.force_login(self.lab_user)
        response=self.client.get(reverse('pasien:ancillary_worklist'))
        self.assertContains(response,self.order.nama_pemeriksaan)
        self.assertNotContains(response,hidden.nama_pemeriksaan)
        self.assertEqual(self.client.post(reverse('pasien:ancillary_result',args=[hidden.pk]),{'status':'SELESAI','hasil_pemeriksaan':'Forged'}).status_code,404)
        hidden.refresh_from_db();self.assertEqual(hidden.status,'ORDERED')

    def test_invalid_complete_and_critical_metadata_rejected_through_legacy_route(self):
        self.client.force_login(self.lab_user)
        for fields in [{'status':'INVALID'},{'status':'SELESAI'},{'status':'SELESAI','hasil_pemeriksaan':'Synthetic','is_critical_value':'1'}]:
            response=self.client.post(reverse('pasien:order_penunjang_update',args=[self.order.pk]),fields)
            self.assertEqual(response.status_code,302)
            self.order.refresh_from_db();self.assertEqual(self.order.status,'ORDERED')
        self.assertEqual(self.client.get(reverse('pasien:order_penunjang_update',args=[self.order.pk])).status_code,405)

    def test_completed_correction_has_reason_and_before_after_audit(self):
        record_result(self.order.pk,self.lab_user,{'status':'SELESAI','hasil_pemeriksaan':'Initial synthetic result'})
        with self.assertRaises(ValueError):
            record_result(self.order.pk,self.lab_user,{'status':'SELESAI','hasil_pemeriksaan':'Corrected synthetic result'})
        record_result(self.order.pk,self.lab_user,{'status':'SELESAI','hasil_pemeriksaan':'Corrected synthetic result'},correction_reason='Instrument verification correction')
        self.order.refresh_from_db()
        self.assertEqual(self.order.result_recorded_by,self.lab_user)
        audit=AuditLog.objects.filter(model_name='OrderPenunjang',user=self.lab_user).latest('pk')
        self.assertIn('Initial synthetic result',audit.detail)
        self.assertIn('Corrected synthetic result',audit.detail)
        self.assertIn('Instrument verification correction',audit.detail)

    def test_administrative_role_without_clinical_profession_has_no_bypass(self):
        actor=User.objects.create_user('nonclinical_result_admin',is_superuser=True)
        UserProfile.objects.create(user=actor,role='ADMIN_RS',profesi='',unit_kerja=self.unit_lab)
        self.client.force_login(actor)
        response=self.client.get(reverse('pasien:laboratorium_dashboard'))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'data-order-id=')
        with self.assertRaises(PermissionDenied):
            record_result(self.order.pk,actor,{'status':'SELESAI','hasil_pemeriksaan':'Forged'})

    def test_more_than_fifty_orders_are_reachable(self):
        OrderPenunjang.objects.bulk_create([OrderPenunjang(kunjungan=self.kunjungan,jenis='LAB',nama_pemeriksaan=f'Paged synthetic {i}') for i in range(51)])
        self.client.force_login(self.lab_user)
        response=self.client.get(reverse('pasien:ancillary_worklist')+'?page=2')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['page_obj'].paginator.count,52)
        self.assertEqual(len(response.context['orders']),2)
