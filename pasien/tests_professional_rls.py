from unittest import skipUnless
from django.db import connection
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


@skipUnless(connection.vendor=='postgresql','RLS requires PostgreSQL')
class ProfessionalRlsTest(ProfessionalCareCase):
    def test_reader_role_cannot_read_signed_note_while_owner_can(self):
        from pasien.models import IgdAssessmentWorkflow,CpptRevision
        from pasien.services.professional_cppt import create_care_note,sign_care_note
        wf=IgdAssessmentWorkflow.objects.create(kunjungan=self.visit,origin_unit=self.unit)
        note=create_care_note(self.visit,wf,self.user,format_code='SOAP',payload={'subjektif':'Sintetis','objektif':'Sintetis','asesmen':'Sintetis','plan':'Sintetis'},context=self.context())
        sign_care_note(self.user,note.pk,note.version)
        self.assertEqual(CpptRevision.objects.count(),1)
        table=connection.ops.quote_name(CpptRevision._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',['qa_professional_reader'])
            if not cursor.fetchone():cursor.execute('CREATE ROLE qa_professional_reader NOLOGIN')
            cursor.execute('GRANT USAGE ON SCHEMA public TO qa_professional_reader')
            cursor.execute(f'GRANT SELECT ON TABLE {table} TO qa_professional_reader')
            cursor.execute('SET LOCAL ROLE qa_professional_reader')
            try:
                cursor.execute(f'SELECT count(*) FROM {table}')
                self.assertEqual(cursor.fetchone()[0],0)
            finally:cursor.execute('RESET ROLE')
        self.assertEqual(CpptRevision.objects.count(),1)

    def test_all_new_sensitive_tables_have_rls(self):
        from django.apps import apps
        names=[('klinis',n) for n in ('LayananProfesional','PemetaanKewenanganLayanan','ProfessionalCareGrant','TarifLayananProfesi','BatasanKewenanganProfesional')]+[('pasien',n) for n in ('CpptRevision','PenugasanDpjpEpisode','VerifikasiCppt','PembatalanTagihan')]
        with connection.cursor() as cursor:
            for app,name in names:
                table=apps.get_model(app,name)._meta.db_table
                cursor.execute('SELECT relrowsecurity FROM pg_class WHERE oid=%s::regclass',[table])
                self.assertTrue(cursor.fetchone()[0],table)
