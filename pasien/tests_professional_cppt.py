from uuid import uuid4
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import SimpleTestCase
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


class NoteSchemaTest(SimpleTestCase):
    def test_format_rejects_unknown_fields(self):
        from pasien.services.professional_cppt import validate_note
        for fmt,payload in [('ADIME',{'subjektif':'SOAP'}),('SOAP',{'unknown':'x'}),('INVALID',{}),('SOAP',{'plan':'x'*10001}),('SOAP',{'plan':['not text']})]:
            with self.subTest(fmt=fmt),self.assertRaises(ValidationError):validate_note(fmt,payload)


class CareNoteTest(ProfessionalCareCase):
    def test_verified_staff_full_name_fits_note_schema(self):
        self.employee.nama_lengkap='N'*200;self.employee.save()
        note=self.note()
        note._meta.get_field('nama_ppa').clean(note.nama_ppa,note)
        self.assertEqual(note.nama_ppa,self.employee.nama_lengkap)
    def note(self,payload=None):
        from pasien.models import IgdAssessmentWorkflow
        from pasien.services.professional_cppt import create_care_note
        wf=IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit)
        return create_care_note(self.visit,wf,self.user,format_code='SOAP',payload=payload or {'subjektif':'Keluhan sintetis','objektif':'Temuan sintetis','asesmen':'Asesmen sintetis','plan':'Rencana sintetis'},context=self.context())

    def test_draft_not_auto_verified(self):
        note=self.note()
        self.assertEqual(note.status,'DRAFT');self.assertFalse(note.verifikasi_dpjp)
        self.assertEqual(note.created_by,self.user)

    def test_author_signs_immutable_revision(self):
        from pasien.services.professional_cppt import sign_care_note
        note=self.note();sign_care_note(self.user,note.pk,note.version)
        note.refresh_from_db();self.assertEqual(note.status,'SIGNED')
        revision=note.care_revisions.get();self.assertTrue(revision.digest)
        with self.assertRaises(ValidationError):revision.save()

    def test_event_only_draft_cannot_sign(self):
        from pasien.services.professional_cppt import sign_care_note
        note=self.note({'plan':'Rencana saja'})
        with self.assertRaises(ValidationError):sign_care_note(self.user,note.pk,note.version)

    def test_unsigned_verification_denied(self):
        from pasien.services.professional_cppt import verify_cppt
        note=self.note()
        with self.assertRaises((PermissionDenied,ValidationError)):verify_cppt(self.user,note.pk,note.version,uuid4())

    def test_correct_signed_content_retains_prior_revision(self):
        from pasien.services.professional_cppt import sign_care_note,correct_care_note
        note=self.note();sign_care_note(self.user,note.pk,note.version)
        note.refresh_from_db();old=note.care_revisions.get().snapshot
        correct_care_note(self.user,note.pk,note.version,{'subjektif':'Keluhan sintetis','objektif':'Temuan koreksi','asesmen':'Asesmen koreksi','plan':'Rencana koreksi'},'Koreksi dokumentasi sintetis')
        note.refresh_from_db();self.assertEqual(note.care_revisions.count(),2)
        self.assertEqual(note.care_revisions.order_by('version').first().snapshot,old)
        self.assertFalse(note.verifikasi_dpjp)
