import copy
import json

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from pasien import tests_igd_workflow as fixtures


def document(section='mata', findings=None, note='Bilateral', status='EXAMINED', reason=''):
    return {'schema_version':1,'sections':{section:{'status':status,'findings':findings or ['anemis'],'note':note,'reason':reason}}}


class PhysicalExamContractTest(SimpleTestCase):
    def test_normal_excludes_abnormal(self):
        from pasien.physical_exam import validate_exam
        with self.assertRaises(ValidationError):
            validate_exam(document(findings=['normal','anemis']))

    def test_secondary_only_reader_preserves_original(self):
        from pasien.physical_exam import exam_context
        secondary={'mata':{'konjungtiva':'Temuan historis bilateral'}}
        original=copy.deepcopy(secondary)
        context=exam_context({},secondary,{})
        self.assertIn('Temuan historis bilateral',str(context['legacy']))
        self.assertEqual(secondary,original)
        self.assertEqual(len(context['sections']),11)

    def test_empty_scaffolding_is_not_an_exam(self):
        from pasien.physical_exam import exam_present
        self.assertFalse(exam_present({}, {'head_to_toe':{'schema_version':1,'sections':{}}}, ''))

    def test_merge_projects_strings_and_retains_provenance_twice(self):
        from pasien.physical_exam import prepare_exam
        old_head={'mata':'Catatan sebelum adopsi','unknown':'Tetap'}
        old_secondary={'thorax':{'paru_auskultasi':'Historis'}}
        secondary,head=prepare_exam(old_secondary,old_head,{'head_to_toe':document()},old_head)
        self.assertIn('Bilateral',head['mata'])
        self.assertEqual(head['unknown'],'Tetap')
        self.assertEqual(secondary['thorax'],old_secondary['thorax'])
        self.assertIn('Catatan sebelum adopsi',str(secondary['head_to_toe']['legacy_before_adoption']))
        again,projection=prepare_exam(secondary,head,secondary,head)
        self.assertEqual(again,secondary)
        self.assertEqual(projection,head)

    def test_repeated_new_exam_save_does_not_invent_legacy(self):
        from pasien.physical_exam import prepare_exam
        secondary,head=prepare_exam({}, {}, {'head_to_toe':document()}, {})
        again,projection=prepare_exam(secondary,head,secondary,head)
        self.assertEqual(again,secondary)
        self.assertNotIn('legacy_before_adoption',again['head_to_toe'])

    def test_invalid_shapes_and_codes(self):
        from pasien.physical_exam import validate_exam
        bad=[None,[],{}, {'schema_version':True,'sections':{}}, {'schema_version':2,'sections':{}},
             {'schema_version':1,'sections':{'unknown':{}}}, document(findings=['bogus']),
             document(findings=['anemis','anemis']),document(findings=[{}]),
             document(findings=['lainnya'],note=''),document(note='a'*2001),
             document(status='NOT_EXAMINED',reason='')]
        for value in bad:
            with self.subTest(value=str(value)[:80]), self.assertRaises(ValidationError):
                validate_exam(value)

    def test_conflicting_flat_edit_is_not_silently_ignored(self):
        from pasien.physical_exam import prepare_exam
        secondary,head=prepare_exam({}, {}, {'head_to_toe':document()}, {})
        with self.assertRaises(ValidationError):
            prepare_exam(secondary,head,secondary,{**head,'mata':'Kontradiksi klinis'})

    def test_explicit_null_namespace_is_rejected(self):
        from pasien.physical_exam import prepare_exam
        with self.assertRaises(ValidationError):
            prepare_exam({}, {}, {'head_to_toe':None}, {})


@override_settings(IGD_WORKFLOW_ENABLED=True)
class PhysicalExamPersistenceTest(fixtures.IgdWorkflowTest):
    def save(self, fields, version=0):
        return self.client.post(reverse('pasien:igd_workflow_draft',args=[self.visit.pk,6]),
            json.dumps({'version':version,'fields':fields}),content_type='application/json')

    def test_selection_projects_and_reopens(self):
        result=self.save({'secondary_survey_detail':{'head_to_toe':document()}})
        self.assertEqual(result.status_code,200)
        self.visit.refresh_from_db()
        self.assertIn('Bilateral',self.visit.fisik_head_to_toe['mata'])
        self.assertEqual(result.json()['values']['fisik_head_to_toe'],self.visit.fisik_head_to_toe)
        page=self.client.get(reverse('pasien:igd_workflow',args=[self.visit.pk])+'?step=6')
        self.assertContains(page,'id="igd-physical-exam"')
        self.assertContains(page,'Bilateral')

    def test_general_state_does_not_create_vitals(self):
        response=self.save({'keadaan_umum':'Tampak sakit sedang','kesadaran':'Somnolen'})
        self.assertEqual(response.status_code,200)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.kesadaran,'Somnolen')
        self.assertFalse(self.visit.igd_workflow.observations.exists())

    def test_secondary_only_display_never_writes(self):
        from pasien.models import IgdAssessmentWorkflow
        self.visit.secondary_survey_detail={'mata':{'konjungtiva':'Temuan historis tersimpan'}}
        self.visit.save()
        page=self.client.get(reverse('pasien:igd_workflow',args=[self.visit.pk])+'?step=6')
        self.assertContains(page,'Temuan historis tersimpan')
        self.assertEqual(len(page.context['physical_exam']['sections']),11)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_invalid_choice_rolls_back(self):
        from pasien.models import IgdAssessmentWorkflow
        response=self.save({'secondary_survey_detail':{'head_to_toe':document(findings=['normal','anemis'])}})
        self.assertEqual(response.status_code,400)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_schema_scaffolding_does_not_satisfy_finalization(self):
        from pasien.services.igd_assessment_workflow import save_step
        from pasien.services.igd_finalization import missing_sections
        workflow=save_step(self.visit.pk,self.user,6,{'secondary_survey_detail':{'head_to_toe':{'schema_version':1,'sections':{}}}},0)
        self.visit.refresh_from_db()
        self.assertIn('physical_exam',missing_sections(self.visit,workflow))

    def test_stale_request_preserves_saved_exam(self):
        first=self.save({'secondary_survey_detail':{'head_to_toe':document()}})
        stale=self.save({'secondary_survey_detail':{'head_to_toe':document(note='Timpa')}})
        self.assertEqual(first.status_code,200)
        self.assertEqual(stale.status_code,409)
        self.visit.refresh_from_db()
        self.assertIn('Bilateral',self.visit.secondary_survey_detail['head_to_toe_summary'])

    def test_stale_signature_is_explained_on_review(self):
        from pasien.models import IgdAssessmentWorkflow
        IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit,
            signatures={'MEDIS':{'name':'Dokter Uji','content_digest':'old-format'}})
        response=self.client.get(reverse('pasien:igd_workflow',args=[self.visit.pk])+'?step=11')
        self.assertContains(response,'Persetujuan perlu ditinjau ulang')

    def test_partial_patch_keeps_anatomical_marker_and_legacy_general(self):
        self.visit.keadaan_umum='Lemah'
        self.visit.penanda_anatomi=[{'side':'FRONT','x':0.2,'y':0.3,'kind':'LUKA','label':'Lokal'}]
        self.visit.save()
        first=self.save({'secondary_survey_detail':{'head_to_toe':document()}})
        second=self.save({'secondary_survey_detail':{'head_to_toe':document('paru',['rhonki'],'Basal kanan')}},first.json()['version'])
        self.assertEqual(second.status_code,200)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.keadaan_umum,'Lemah')
        self.assertEqual(self.visit.penanda_anatomi[0]['label'],'Lokal')
        self.assertEqual(set(self.visit.secondary_survey_detail['head_to_toe']['sections']),{'mata','paru'})

    def test_print_escapes_notes_and_keeps_blank_unassessed(self):
        result=self.save({'secondary_survey_detail':{'head_to_toe':document(note='<script>evil()</script>')}})
        self.assertEqual(result.status_code,200)
        response=self.client.get(reverse('pasien:cetak_asesmen_medis_igd',args=[self.visit.pk]))
        self.assertContains(response,'&lt;script&gt;evil()&lt;/script&gt;')
        self.assertNotContains(response,'<script>evil()</script>')
        self.assertContains(response,'Belum dikaji')

    def test_old_final_snapshot_does_not_show_live_general_values(self):
        from pasien.models import IgdAssessmentWorkflow,IgdAssessmentRevision
        from django.utils import timezone
        workflow=IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit,status='FINAL')
        IgdAssessmentRevision.objects.create(workflow=workflow,revision=1,snapshot={'visit':{'secondary_survey_detail':{'mata':{'konjungtiva':'FINAL-HISTORIS'}},'fisik_head_to_toe':{}}},signed_at=timezone.now(),signed_by=self.user)
        self.visit.keadaan_umum='LIVE-ONLY-JANGAN-TAMPIL'
        self.visit.kesadaran='LIVE-ONLY-KESADARAN'
        self.visit.save()
        for route,suffix in [('pasien:igd_workflow','?step=6'),('pasien:igd_workflow_resume','')]:
            response=self.client.get(reverse(route,args=[self.visit.pk])+suffix)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'FINAL-HISTORIS')
            self.assertNotContains(response,'LIVE-ONLY-')
            self.assertContains(response,'Tidak dicatat pada snapshot')
