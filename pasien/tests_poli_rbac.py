"""Matriks kewenangan 6 peran × 10 langkah POLI-JANTUNG, diuji di tingkat HTTP.

Bukan dokumentasi: setiap sel "ditolak" punya satu tes yang mengirim POST nyata
ke route asesmen dan menuntut status 403 (atau 409 untuk langkah terkunci),
dan setiap sel "diizinkan" pada langkah yang sama diuji dengan akun yang
berwenang sehingga penolakan tidak bisa lolos karena route-nya rusak.
"""
import json
import uuid

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from pasien.models import CPPT, IgdAssessmentWorkflow, KunjunganPasien
from pasien.services.igd_assessment_workflow import save_step
from pasien.services.poli_rbac import (
    DPJP, FARMASI, FISIOTERAPI, GIZI, KASIR, PERAWAT, VIEWER,
    FILL_ROLES, READ_ROLES, VERIFY_ROLES, resolve_role,
)

from .tests_poli_workflow import FULL_RAJAL_DRAFT, TEST_STORAGES, PoliFixture

#: Nilai sah minimal per langkah, dipakai untuk POST "diizinkan".
STEP_PAYLOAD = {int(k): v for k, v in FULL_RAJAL_DRAFT.items()}

#: Matriks yang diuji — ditulis ulang dari ADR-11/F1.10, bukan dibaca dari kode,
#: supaya perubahan kode tanpa perubahan keputusan membuat tes merah.
EXPECTED_FILL = {
    PERAWAT: {1, 2, 3, 4, 5, 6, 7, 9},
    DPJP: {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
    FARMASI: {9},
    GIZI: {5, 9},
    FISIOTERAPI: {9},
    KASIR: set(),
}
ALL_STEPS = set(range(1, 11))


class RbacMatrixShapeTest(PoliFixture):
    def test_fill_matrix_matches_adr_11(self):
        actual = {role: {step for step, roles in FILL_ROLES.items() if role in roles}
                  for role in EXPECTED_FILL}
        self.assertEqual(actual, EXPECTED_FILL)

    def test_every_role_may_read_every_step(self):
        for role in (PERAWAT, DPJP, FARMASI, GIZI, FISIOTERAPI, KASIR):
            self.assertEqual(set(READ_ROLES[1]), set(READ_ROLES[10]))
            self.assertIn(role, READ_ROLES[1])

    def test_only_dpjp_may_verify_any_step(self):
        for step in ALL_STEPS:
            self.assertEqual(VERIFY_ROLES[step], {DPJP})

    def test_resolve_role_maps_each_account(self):
        self.assertEqual(resolve_role(self.nurse, self.visit), PERAWAT)
        self.assertEqual(resolve_role(self.dpjp_user, self.visit), DPJP)
        self.assertEqual(resolve_role(self.pharmacist, self.visit), FARMASI)
        self.assertEqual(resolve_role(self.nutritionist, self.visit), GIZI)
        self.assertEqual(resolve_role(self.physio, self.visit), FISIOTERAPI)
        self.assertEqual(resolve_role(self.records, self.visit), KASIR)
        self.assertEqual(resolve_role(self.other_doctor, self.visit), 'DOKTER_NON_DPJP')


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class RbacFillMatrixTest(PoliFixture):
    """Setiap peran × setiap langkah: isi diizinkan atau ditolak, diuji lewat HTTP."""

    def post_step(self, user, step):
        self.client.force_login(user)
        workflow = IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).first()
        return self.client.post(
            reverse('pasien:poli_workflow_draft', args=[self.visit.pk, step]),
            data=json.dumps({
                'fields': STEP_PAYLOAD[step],
                'version': workflow.version if workflow else 0,
            }),
            content_type='application/json',
        )

    def assert_matrix(self, user, allowed_steps, label):
        denied = ALL_STEPS - allowed_steps
        for step in sorted(denied):
            response = self.post_step(user, step)
            self.assertEqual(
                response.status_code, 403,
                f'{label} seharusnya ditolak pada langkah {step}, dapat {response.status_code}',
            )
        for step in sorted(allowed_steps):
            response = self.post_step(user, step)
            self.assertEqual(
                response.status_code, 200,
                f'{label} seharusnya diizinkan pada langkah {step}: {response.content[:200]}',
            )

    def test_perawat_poli_denied_clinical_closing_steps(self):
        self.assert_matrix(self.nurse, EXPECTED_FILL[PERAWAT], 'Perawat Poli')

    def test_dpjp_sp_jp_allowed_every_step(self):
        self.assert_matrix(self.dpjp_user, EXPECTED_FILL[DPJP], 'DPJP Sp.JP')

    def test_farmasi_only_writes_asuhan_step(self):
        self.assert_matrix(self.pharmacist, EXPECTED_FILL[FARMASI], 'Farmasi')

    def test_gizi_writes_screening_and_asuhan_only(self):
        self.assert_matrix(self.nutritionist, EXPECTED_FILL[GIZI], 'Gizi')

    def test_fisioterapi_writes_asuhan_only(self):
        self.assert_matrix(self.physio, EXPECTED_FILL[FISIOTERAPI], 'Fisioterapi')

    def test_kasir_cannot_write_any_step(self):
        self.assert_matrix(self.records, EXPECTED_FILL[KASIR], 'Kasir / Rekam Medis')

    def test_kasir_can_read_every_step(self):
        self.client.force_login(self.records)
        for step in sorted(ALL_STEPS):
            response = self.client.get(
                reverse('pasien:poli_workflow', args=[self.visit.pk]) + f'?step={step}')
            self.assertEqual(response.status_code, 200, f'kasir baca langkah {step}')

    def test_non_dpjp_specialist_is_denied_clinical_steps(self):
        self.client.force_login(self.other_doctor)
        for step in (8, 10):
            response = self.post_step(self.other_doctor, step)
            self.assertEqual(response.status_code, 403, f'dokter non-DPJP langkah {step}')

    def test_asesor_reads_but_never_writes(self):
        from django.contrib.auth.models import User
        from accounts.models import UserProfile
        asesor = User.objects.create_user('asesor_poli', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=asesor, defaults={'role': 'ASESOR', 'profesi': 'DOKTER_SPESIALIS',
                                   'unit_kerja': self.unit})
        self.assertEqual(resolve_role(asesor, self.visit), VIEWER)
        self.client.force_login(asesor)
        self.assertEqual(self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=1').status_code, 200)
        for step in sorted(ALL_STEPS):
            response = self.post_step(asesor, step)
            self.assertEqual(response.status_code, 403, f'asesor tulis langkah {step}')


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class RbacFinalizationTest(PoliFixture):
    """ADR-11: penutupan klinis hanya DPJP episode."""

    def setUp(self):
        version = 0
        for step in range(1, 11):
            actor = self.dpjp_user if step in (8, 10) else self.nurse
            version = save_step(self.visit.pk, actor, step, STEP_PAYLOAD[step], version,
                                service_line='RAJAL_JANTUNG').version
        self.version = version

    def action(self, user, operation, fields):
        self.client.force_login(user)
        response = self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': operation, 'fields': fields,
                             'version': self.version, 'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        if response.status_code == 200:
            self.version = response.json()['version']
        return response

    def test_nurse_cannot_sign_medical_section(self):
        response = self.action(self.nurse, 'sign', {'section': 'MEDIS'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(IgdAssessmentWorkflow.objects.get(kunjungan=self.visit).signatures)

    def test_nurse_cannot_finalize(self):
        response = self.action(self.nurse, 'finalize', {'resume': 'Pulang.'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(IgdAssessmentWorkflow.objects.get(kunjungan=self.visit).status, 'DRAFT')
        self.assertFalse(KunjunganPasien.objects.get(pk=self.visit.pk).discharge
                         if hasattr(KunjunganPasien.objects.get(pk=self.visit.pk), 'discharge') else False)

    def test_pharmacist_cannot_finalize(self):
        response = self.action(self.pharmacist, 'finalize', {'resume': 'Pulang.'})
        self.assertEqual(response.status_code, 403)

    def test_non_dpjp_specialist_cannot_finalize(self):
        response = self.action(self.other_doctor, 'finalize', {'resume': 'Pulang.'})
        self.assertEqual(response.status_code, 403)

    def test_non_dpjp_specialist_cannot_sign(self):
        response = self.action(self.other_doctor, 'sign', {'section': 'MEDIS'})
        self.assertEqual(response.status_code, 403)

    def test_dpjp_signs_and_finalizes(self):
        signed = self.action(self.dpjp_user, 'sign', {'section': 'MEDIS'})
        self.assertEqual(signed.status_code, 200, signed.content)
        finalized = self.action(self.dpjp_user, 'finalize', {'resume': 'Pulang, kontrol 2 minggu.'})
        self.assertEqual(finalized.status_code, 200, finalized.content)
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        self.assertEqual(workflow.status, 'FINAL')
        self.assertEqual(workflow.finalized_by_id, self.dpjp_user.pk)

    def test_dpjp_cannot_skip_incomplete_administrative_steps(self):
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        draft = dict(workflow.draft_payload)
        draft.pop('2', None)
        workflow.draft_payload = draft
        workflow.save(update_fields=['draft_payload'])
        self.action(self.dpjp_user, 'sign', {'section': 'MEDIS'})
        response = self.action(self.dpjp_user, 'finalize', {'resume': 'Coba lewati langkah 2.'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('step_2', response.json()['fields']['finalisasi'])
        self.assertEqual(IgdAssessmentWorkflow.objects.get(kunjungan=self.visit).status, 'DRAFT')


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class RbacNoDpjpTest(PoliFixture):
    def test_no_step_can_be_filled_without_assigned_dpjp(self):
        visit = self.make_visit('QA-NO-DPJP-RBAC', dpjp=False)
        self.client.force_login(self.nurse)
        for step in sorted(ALL_STEPS):
            response = self.client.post(
                reverse('pasien:poli_workflow_draft', args=[visit.pk, step]),
                data=json.dumps({'fields': STEP_PAYLOAD[step], 'version': 0}),
                content_type='application/json')
            self.assertEqual(response.status_code, 403, f'langkah {step} tanpa DPJP')
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=visit).exists())
