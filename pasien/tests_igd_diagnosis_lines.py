from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse

from klinis.models import MasterIcd10
from pasien.models import IgdAssessmentWorkflow
from pasien.tests_igd_workflow import IgdWorkflowTest


class DiagnosisLinesTest(IgdWorkflowTest):
    def action(self, changes, version=0, key=None):
        from pasien.services.igd_actions import perform_action
        return perform_action(self.visit.pk, self.user, 'diagnosis_set',
                              {'changes': changes}, version, key or str(uuid4()))

    def line(self, text='Diagnosis kerja', primary=True, temp='new'):
        return {'op': 'upsert', 'temp_id': temp, 'mode': 'MANUAL',
                'text': text, 'is_primary': primary}

    def test_primary_and_secondary_round_trip(self):
        result = self.action([self.line(), self.line('Diagnosis sekunder', False, 'second')])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk, 'Diagnosis kerja')
        self.assertEqual(self.visit.diagnoses.filter(active=True).count(), 2)
        self.assertEqual(result['version'], 1)
        self.assertEqual(len(result['diagnosis_ids']), 2)
        self.assertEqual(self.visit.diagnoses.filter(is_primary=True, active=True).count(), 1)

    def test_two_primary_rows_roll_back(self):
        from pasien.services.igd_actions import HANDLERS
        self.assertIn('diagnosis_set', HANDLERS)
        with self.assertRaises(ValueError):
            self.action([self.line(), self.line('B', True, 'b')])
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_replay_returns_same_ids(self):
        key = str(uuid4())
        first = self.action([self.line()], key=key)
        second = self.action([self.line()], key=key)
        self.assertEqual(first['diagnosis_ids'], second['diagnosis_ids'])
        self.assertEqual(self.visit.diagnoses.count(), 1)
        with self.assertRaises(ValueError):
            self.action([self.line('Changed')], key=key)

    def test_omission_preserves_existing_rows_and_primary_switch(self):
        first = self.action([self.line(), self.line('Secondary', False, 'b')])
        a, b = first['diagnosis_ids']
        self.action([
            {'op': 'upsert', 'id': a, 'mode': 'MANUAL', 'text': 'A', 'is_primary': False},
            {'op': 'upsert', 'id': b, 'mode': 'MANUAL', 'text': 'B', 'is_primary': True},
        ], first['version'])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk, 'B')
        self.assertEqual(self.visit.diagnoses.filter(active=True).count(), 2)

    def test_master_label_is_server_owned(self):
        MasterIcd10.objects.create(kode='QAT.1', nama='Label master uji')
        self.action([{'op': 'upsert', 'temp_id': 'a', 'mode': 'MASTER',
                      'code': 'QAT.1', 'text': 'Forged label', 'is_primary': True}])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk, 'QAT.1 — Label master uji')
        row = self.visit.diagnoses.get()
        self.assertEqual(row.nama, 'Label master uji')
        self.assertEqual(row.updated_by, self.user)

    def test_invalid_codes_payload_types_and_fake_ai_do_not_write(self):
        from pasien.services.igd_actions import HANDLERS
        self.assertIn('diagnosis_set', HANDLERS)
        for change in [
            {**self.line(), 'mode': 'MASTER', 'code': 'NOTREAL'},
            {**self.line(), 'mode': 'AI', 'code': 'NOTREAL'},
            {**self.line(), 'is_primary': 'true'},
            {**self.line(), 'text': ''},
            {**self.line(), 'provenance': {'accepted_by': 123}},
            {**self.line(), 'id': True},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.action([change])
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_stale_and_final_writes_fail(self):
        first = self.action([self.line()])
        with self.assertRaises(ValueError):
            self.action([self.line('Stale', False, 'b')])
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        workflow.status = 'FINAL'
        workflow.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            self.action([self.line('Final')], first['version'])
        self.assertEqual(self.visit.diagnoses.count(), 1)

    def test_nurse_cannot_set_medical_diagnoses(self):
        self.user.profile.profesi = 'PERAWAT'
        self.user.profile.save(update_fields=['profesi'])
        with self.assertRaises(PermissionDenied):
            self.action([self.line()])

    def test_cancel_primary_preserves_history_and_clears_projection(self):
        first = self.action([self.line()])
        self.action([{'op': 'cancel', 'id': first['diagnosis_ids'][0]}], first['version'])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk, '')
        self.assertEqual(self.visit.diagnoses.count(), 1)
        self.assertFalse(self.visit.diagnoses.get().active)

    def test_snapshot_freezes_structured_labels(self):
        from pasien.services.igd_finalization import clinical_snapshot
        first = self.action([self.line()])
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        snapshot = clinical_snapshot(self.visit, workflow)
        self.assertEqual(snapshot['diagnoses'][0]['nama'], 'Diagnosis kerja')
        self.action([{'op': 'upsert', 'id': first['diagnosis_ids'][0], 'mode': 'MANUAL',
                      'text': 'Koreksi', 'is_primary': True}], first['version'])
        self.assertEqual(snapshot['diagnoses'][0]['nama'], 'Diagnosis kerja')

    def test_changes_have_before_after_audit(self):
        from akreditasi.models import AuditLog
        first = self.action([self.line()])
        self.action([{'op': 'upsert', 'id': first['diagnosis_ids'][0], 'mode': 'MANUAL',
                      'text': 'Koreksi tercatat', 'is_primary': True}], first['version'])
        audit = AuditLog.objects.filter(model_name='DiagnosisKunjungan').order_by('-pk').first()
        self.assertIsNotNone(audit)
        import json
        detail = json.loads(audit.detail)
        self.assertEqual(detail['before'][0]['nama'], 'Diagnosis kerja')
        self.assertEqual(detail['after'][0]['nama'], 'Koreksi tercatat')

    def test_cross_visit_row_cannot_be_changed(self):
        from pasien.models import KunjunganPasien
        other = KunjunganPasien.objects.create(pasien=self.patient, no_kunjungan='QA-OTHER-DIAG',
            jenis_kunjungan='IGD', tanggal_masuk=self.visit.tanggal_masuk, unit_kerja=self.unit)
        first = self.action([self.line()])
        from pasien.services.igd_actions import perform_action
        with self.assertRaises(ValueError):
            perform_action(other.pk, self.user, 'diagnosis_set', {'changes': [
                {'op': 'cancel', 'id': first['diagnosis_ids'][0]},
            ]}, 0, str(uuid4()))
        self.assertTrue(self.visit.diagnoses.get().active)

    def test_database_constraint_rejects_second_primary(self):
        self.action([self.line()])
        from pasien.models import DiagnosisKunjungan
        with self.assertRaises(IntegrityError), transaction.atomic():
            DiagnosisKunjungan.objects.create(kunjungan=self.visit, mode='MANUAL', nama='B',
                                              is_primary=True, active=True)

    def test_legacy_step_cannot_overwrite_adopted_diagnoses(self):
        from pasien.services.igd_assessment_workflow import save_step
        first = self.action([self.line()])
        with self.assertRaises(ValueError):
            save_step(self.visit.pk, self.user, 8, {'diagnosa_masuk': 'Legacy overwrite'}, first['version'])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk, 'Diagnosis kerja')

    @override_settings(IGD_WORKFLOW_ENABLED=True)
    def test_http_action_and_rendered_primary_secondary_controls(self):
        import json
        response = self.client.post(reverse('pasien:igd_workflow_action', args=[self.visit.pk]),
            json.dumps({'operation': 'diagnosis_set', 'fields': {'changes': [self.line()]},
                        'version': 0, 'request_id': str(uuid4())}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=8')
        self.assertContains(response, 'id="igd-diagnoses"')
        self.assertContains(response, 'Diagnosis Utama')
        self.assertContains(response, 'Diagnosis Sekunder')
        self.assertContains(response, 'Diagnosis kerja')
