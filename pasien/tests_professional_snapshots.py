from uuid import uuid4
from django.test import override_settings
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


@override_settings(IGD_WORKFLOW_ENABLED=True,IGD_PROFESSIONAL_CARE_ENABLED=True)
class ProfessionalSnapshotTest(ProfessionalCareCase):
    def test_final_reader_uses_original_profession_and_content(self):
        from pasien.models import IgdAssessmentWorkflow,IgdAssessmentRevision
        from pasien.services.professional_cppt import create_care_note,sign_care_note
        from pasien.services.igd_finalization import clinical_snapshot
        from django.urls import reverse
        wf=IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit)
        note=create_care_note(self.visit,wf,self.user,format_code='SOAP',payload={'subjektif':'Keluhan saat ditandatangani','objektif':'Temuan lama','asesmen':'Asesmen lama','plan':'Rencana lama'},context=self.context())
        sign_care_note(self.user,note.pk,note.version)
        snapshot=clinical_snapshot(self.visit,wf)
        IgdAssessmentRevision.objects.create(workflow=wf,revision=1,snapshot=snapshot,signed_by=self.user)
        wf.status='FINAL';wf.save()
        self.employee.nama_lengkap='Nama master berubah';self.employee.save()
        self.grade.nama='Jenjang master berubah';self.grade.save()
        self.client.force_login(self.user)
        response=self.client.get(reverse('pasien:igd_workflow_resume',args=[self.visit.pk]))
        self.assertContains(response,'Keluhan saat ditandatangani');self.assertContains(response,'PPA Sintetis')
        self.assertNotContains(response,'Nama master berubah');self.assertNotContains(response,'Jenjang master berubah')

    def test_old_snapshot_never_backfills_new_live_note(self):
        from pasien.models import IgdAssessmentWorkflow,IgdAssessmentRevision,CPPT
        from django.urls import reverse
        wf=IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit,status='FINAL')
        snapshot={'visit':{},'cppt':[{'id':900,'nama_ppa':'Penulis historis','profesi':'DOKTER','tanggal':'2020-01-01','subjektif':'Isi historis asli','objektif':'','asesmen':'','plan':'','verifikasi_dpjp':True}]}
        IgdAssessmentRevision.objects.create(workflow=wf,revision=1,snapshot=snapshot,signed_by=self.user)
        CPPT.objects.create(kunjungan=self.visit,profesi='DOKTER',nama_ppa='Live lain',tanggal=timezone.now(),subjektif='Tidak boleh dibaca dari live',objektif='',asesmen='',plan='')
        self.client.force_login(self.user)
        response=self.client.get(reverse('pasien:igd_workflow_resume',args=[self.visit.pk]))
        self.assertContains(response,'Isi historis asli');self.assertNotContains(response,'Tidak boleh dibaca dari live')
        self.assertContains(response,'Verifikasi historis tanpa identitas/digest')
