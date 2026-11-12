from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from pasien import tests_igd_workflow as fixtures
from pasien import tests_igd_workflow_finalization as finalization_fixtures
from pasien.models import Bed, Ruangan, IgdAssessmentWorkflow, IgdAssessmentRevision, DischargeRecord
from pasien.services.igd_assessment_workflow import save_step, WorkflowValidation


@override_settings(IGD_WORKFLOW_ENABLED=True)
class IgdOutcomeTest(fixtures.IgdWorkflowTest):
    ready = finalization_fixtures.IgdFinalizationTest.ready
    signed = finalization_fixtures.IgdFinalizationTest.signed
    action = finalization_fixtures.IgdFinalizationTest.action

    def prepare(self, fields):
        version = self.signed()
        workflow = save_step(self.visit.pk, self.user, 11, fields, version)
        return self.action('sign', {'section':'MEDIS'}, workflow.version)['version']

    def bed(self, status='TERSEDIA'):
        room = Ruangan.objects.create(kode='QA-WARD', nama='Bangsal QA', kelas='3', jenis='RANAP', unit_kerja=self.unit)
        return Bed.objects.create(ruangan=room, kode_bed='QA-1', status=status)

    def test_document_finalization_does_not_discharge(self):
        result = self.action('finalize', {'outcome':'NONE','resume':'Dokumentasi selesai; layanan masih berlangsung'}, self.signed())
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status,'DAFTAR')
        self.assertFalse(DischargeRecord.objects.filter(kunjungan=self.visit).exists())
        self.assertEqual(IgdAssessmentWorkflow.objects.get(kunjungan=self.visit).status,'FINAL')

    def test_ranap_transfer_and_snapshot_survive_current_vital_changes(self):
        bed = self.bed()
        version = self.prepare({'disposisi_tindak_lanjut':'RAWAT_INAP'})
        self.action('finalize', {'outcome':'RANAP','resume':'Transfer sintetis','bed_id':bed.pk,'dpjp':'Dokter QA'}, version)
        self.visit.refresh_from_db(); bed.refresh_from_db()
        self.assertEqual(self.visit.jenis_kunjungan,'RANAP')
        self.assertEqual(bed.status,'TERISI')
        self.assertEqual(self.visit.bed_id,bed.pk)
        self.visit.ttv_nadi = 60
        self.visit.save(update_fields=['ttv_nadi'])
        response = self.client.get(reverse('pasien:igd_workflow',args=[self.visit.pk])+'?step=4')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['form']['ttv_nadi'].value(),100)
        response = self.client.post(reverse('pasien:cppt_tambah',args=[self.visit.pk]), {'profesi':'DOKTER','subjektif':'Perawatan lanjutan bangsal','objektif':'Stabil','asesmen':'Evaluasi','plan':'Observasi'})
        self.assertNotEqual(response.status_code,409)

    def test_unavailable_bed_rolls_back_finalization(self):
        bed = self.bed('TERISI')
        version = self.prepare({'disposisi_tindak_lanjut':'RAWAT_INAP'})
        with self.assertRaises(WorkflowValidation):
            self.action('finalize', {'outcome':'RANAP','resume':'Transfer sintetis','bed_id':bed.pk,'dpjp':'Dokter QA'}, version)
        self.assertFalse(IgdAssessmentRevision.objects.exists())
        self.assertEqual(IgdAssessmentWorkflow.objects.get(kunjungan=self.visit).status,'DRAFT')

    def test_consultation_keeps_igd_ownership(self):
        version = self.prepare({'disposisi_tindak_lanjut':'KONSUL','disposisi_kontrol_poli':'POLI_PENYAKIT_DALAM'})
        self.action('finalize', {'outcome':'CONSULT','resume':'Permintaan konsultasi'}, version)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.jenis_kunjungan,'IGD')
        self.assertEqual(self.visit.unit_kerja_id,self.unit.pk)
        self.assertEqual(self.visit.konsul_ke_poli,'POLI_PENYAKIT_DALAM')

    def test_poli_transfer_preserves_origin_read_access(self):
        self.user.is_superuser=False
        self.user.save(update_fields=['is_superuser'])
        version = self.prepare({'disposisi_tindak_lanjut':'TRANSFER','disposisi_kontrol_poli':'POLI_PENYAKIT_DALAM'})
        self.action('finalize', {'outcome':'TRANSFER','resume':'Transfer layanan poli'}, version)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.jenis_kunjungan,'RAJAL')
        self.assertNotEqual(self.visit.unit_kerja_id,self.unit.pk)
        self.assertEqual(self.client.get(reverse('pasien:igd_workflow_resume',args=[self.visit.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('pasien:igd_workflow',args=[self.visit.pk])).status_code,200)

    def test_external_referral_records_destination(self):
        version = self.prepare({'disposisi_tindak_lanjut':'RUJUK','disposisi_rujuk_rs':'RS Tujuan QA','disposisi_rujuk_alasan':'Kebutuhan fasilitas lanjutan'})
        self.action('finalize', {'outcome':'RUJUK','resume':'Rujukan sintetis'}, version)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status,'RUJUK')
        self.assertEqual(self.visit.sisrute_rs_tujuan,'RS Tujuan QA')
        self.assertEqual(self.visit.discharge.status_clearance,'PROSES')

    def test_death_requires_explicit_details(self):
        when = timezone.now()-timedelta(minutes=1)
        version = self.prepare({'disposisi_tindak_lanjut':'MENINGGAL','waktu_kematian':when.isoformat(),'penyebab_kematian':'Keterangan sintetis terverifikasi'})
        self.action('finalize', {'outcome':'MENINGGAL','resume':'Resume sintetis'}, version)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status,'MENINGGAL')
        self.assertEqual(self.visit.discharge.kondisi_pulang,'MENINGGAL')

    def test_paps_requires_reason_and_preserves_clearance(self):
        version = self.prepare({'disposisi_tindak_lanjut':'PAPS'})
        with self.assertRaises(WorkflowValidation):
            self.action('finalize', {'outcome':'PAPS','resume':'Resume sintetis'}, version)
        self.action('finalize', {'outcome':'PAPS','resume':'Resume sintetis','paps_alasan':'Penolakan setelah penjelasan','paps_nama_penolak':'Penanggung jawab QA'}, version)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.discharge.kondisi_pulang,'APS')
        self.assertEqual(self.visit.discharge.status_clearance,'PROSES')
