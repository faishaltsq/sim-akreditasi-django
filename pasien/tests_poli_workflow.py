"""Regresi mesin asesmen generik + kerangka 10 langkah POLI-JANTUNG (F1).

Setiap tes menyatakan perilaku yang dapat diamati: status HTTP, baris ORM,
isi ``draft_payload``, atau nomor versi. Tidak ada tes yang hanya memeriksa
keberadaan simbol.
"""
import json
import re
import uuid

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.forms_igd_workflow import STEPS
from pasien.models import (
    CPPT, IgdAssessmentRevision, IgdAssessmentWorkflow, IgdWorkflowAction,
    KunjunganPasien, Pasien, PenugasanDpjpEpisode,
)
from pasien.services.igd_assessment_workflow import (
    WorkflowConflict, WorkflowValidation, get_visit, save_step,
)
from pasien.workflow_schemas import RAJAL_JANTUNG_STEPS, STEP_SCHEMAS

#: Manifest static storage tidak punya entri untuk berkas JS baru sampai
#: ``collectstatic`` dijalankan saat deploy; tes memakai storage polos seperti
#: tes integrasi IGD yang sudah ada.
TEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

#: Salinan literal ``STEPS`` sebelum F1 dipindah ke registri. Dibekukan di sini
#: supaya generalisasi yang mengubah satu field pun membuat tes merah.
STEPS_IGD_SNAPSHOT = {
    1: ('Identitas & Penjamin', ('penjamin',)),
    2: ('Triase & Cara Datang', ('triase_skala', 'triase_kategori', 'triage', 'cara_datang',
        'fisik_airway', 'fisik_breathing', 'fisik_circulation', 'fisik_disability', 'fisik_exposure')),
    3: ('Anamnesis & Riwayat', ('anamnesis_rps', 'anamnesis_rpd', 'anamnesis_rpk', 'anamnesis_obat', 'skrining_alergi_status', 'alergi_asesmen')),
    4: ('Tanda-Tanda Vital', ('ttv_sistole', 'ttv_diastole', 'ttv_nadi', 'ttv_rr', 'ttv_suhu',
        'ttv_spo2', 'ttv_gcs', 'ttv_skala_nyeri', 'gcs_e', 'gcs_v', 'gcs_m')),
    5: ('Biopsikososial, Spiritual & Skrining', ('status_psikososial', 'status_spiritual',
        'status_emosional', 'hambatan_komunikasi', 'kebutuhan_spiritual', 'skrining_gizi_mst',
        'metode_risiko_jatuh', 'skrining_jatuh_skor', 'skrining_jatuh_grade', 'skrining_jatuh_detail', 'hambatan_edukasi', 'skrining_gizi_detail')),
    6: ('Pemeriksaan Fisik Lengkap', ('keadaan_umum', 'kesadaran', 'fisik_head_to_toe', 'secondary_survey_detail', 'fisik_lokalis', 'penanda_anatomi')),
    7: ('Pemeriksaan Penunjang', ()),
    8: ('Penetapan Diagnosis & Rencana', ('diagnosa_masuk', 'diagnosa_keperawatan_sdki',
        'luaran_keperawatan_slki', 'intervensi_keperawatan_siki', 'diagnosis_mode')),
    9: ('Pelaksanaan Asuhan — CPPT & Billing', ()),
    10: ('Evaluasi Akhir IGD', ('disposisi_kondisi_akhir', 'evaluasi_respon_terapi',
         'ttv_sistole', 'ttv_diastole', 'ttv_nadi', 'ttv_rr', 'ttv_suhu',
         'ttv_spo2', 'ttv_gcs', 'ttv_skala_nyeri', 'gcs_e', 'gcs_v', 'gcs_m')),
    11: ('Disposisi & Resume Keluar', ('disposisi_tindak_lanjut', 'disposisi_ruang_rawat',
         'disposisi_kontrol_poli', 'disposisi_kontrol_tgl', 'disposisi_rujuk_rs', 'disposisi_rujuk_alasan',
         'sbar_situation', 'sbar_background', 'sbar_assessment', 'sbar_recommendation', 'waktu_kematian', 'penyebab_kematian')),
}

FULL_RAJAL_DRAFT = {
    '1': {'penjamin': 'UMUM', 'jenis_kunjungan_klinis': 'KONTROL'},
    '2': {'keluhan_utama': 'Nyeri dada kiri menjalar', 'cara_datang': 'SENDIRI'},
    '3': {'anamnesis_rps': 'Nyeri sejak 2 hari, memberat saat aktivitas.'},
    '4': {'ttv_sistole': 128, 'ttv_diastole': 82, 'ttv_nadi': 88, 'ttv_rr': 18,
          'ttv_suhu': 36.6, 'ttv_spo2': 98, 'ttv_skala_nyeri': 3},
    '5': {'skrining_gizi_mst': 1, 'skrining_jatuh_skor': 15},
    '6': {'keadaan_umum': 'Compos mentis, tampak nyeri ringan', 'fisik_lokalis': 'Kor S1-S2 normal.'},
    '7': {'penunjang_catatan': 'EKG 12-lead, TTE.'},
    '8': {'diagnosa_utama': 'I20.0 Angina tidak stabil', 'rencana_terapi': 'DAPT + evaluasi TTE.'},
    '9': {'cppt_ringkas': 'Edukasi diet rendah garam.'},
    '10': {'kondisi_akhir_rajal': 'MEMBAIK', 'evaluasi_respon_terapi': 'Nyeri turun NRS 3→1.'},
}


class PoliFixture(TestCase):
    """Fixture bersama: unit POLI-JANTUNG, DPJP tertugaskan, dan 5 peran lain."""

    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.get_or_create(
            code='POLI-JANTUNG', defaults={'name': 'Poliklinik Jantung', 'level': 3},
        )[0]
        cls.other_unit = UnitKerja.objects.get_or_create(
            code='POLI-PD', defaults={'name': 'Poliklinik Penyakit Dalam', 'level': 3},
        )[0]
        cls.admin = User.objects.create_user('admin_poli', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=cls.admin, defaults={'role': 'ADMIN_RS', 'unit_kerja': cls.unit},
        )
        cls.dpjp_user = cls._account('dpjp_jantung', 'DOKTER_SPESIALIS', cls.unit)
        cls.nurse = cls._account('perawat_poli', 'PERAWAT', cls.unit)
        cls.pharmacist = cls._account('apoteker_poli', 'APOTEKER', cls.unit)
        cls.nutritionist = cls._account('nutrisionis_poli', 'NUTRISIONIS', cls.unit)
        cls.physio = cls._account('fisioterapis_poli', 'FISIOTERAPIS', cls.unit)
        cls.records = cls._account('perekam_medis', 'PEREKAM_MEDIS', cls.unit)
        cls.other_doctor = cls._account('dokter_lain', 'DOKTER_SPESIALIS', cls.unit)
        cls.patient = Pasien.objects.create(
            no_rm='QA-POLI-JANTUNG', nama_lengkap='Pasien Uji Jantung',
            tanggal_lahir='1970-05-05', jenis_kelamin='L',
        )
        cls.visit = KunjunganPasien.objects.create(
            pasien=cls.patient, no_kunjungan='QA-POLI-JANTUNG',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            unit_kerja=cls.unit, poliklinik='POLI-JANTUNG',
        )
        cls._assign_dpjp(cls.visit, cls.dpjp_user)

    @classmethod
    def _account(cls, username, profesi, unit):
        user = User.objects.create_user(username, password='fixture-only')
        UserProfile.objects.update_or_create(
            user=user, defaults={'role': 'STAF_NAKES', 'profesi': profesi, 'unit_kerja': unit},
        )
        return user

    @classmethod
    def _assign_dpjp(cls, visit, doctor):
        today = timezone.localdate()
        PenugasanDpjpEpisode.objects.create(
            visit=visit, doctor=doctor, unit=visit.unit_kerja, assignment_type='PRIMARY',
            valid_from=today, valid_until=today + timezone.timedelta(days=30),
            is_active=True, source_version='TEST-POLI-1', assigned_by=cls.admin,
        )

    def make_visit(self, no_kunjungan, *, unit=None, dpjp=True):
        visit = KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan=no_kunjungan, jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), unit_kerja=unit or self.unit,
            poliklinik='POLI-JANTUNG',
        )
        if dpjp:
            self._assign_dpjp(visit, self.dpjp_user)
        return visit

    def workflow_for(self, visit):
        return IgdAssessmentWorkflow.objects.get(kunjungan=visit)


class SchemaRegistryTest(PoliFixture):
    def test_igd_schema_is_byte_identical_to_pre_f1_steps(self):
        self.assertEqual(STEP_SCHEMAS['IGD'], STEPS_IGD_SNAPSHOT)
        self.assertIs(STEPS, STEP_SCHEMAS['IGD'])

    def test_rajal_schema_declares_ten_steps_with_declared_field_kinds(self):
        self.assertEqual(sorted(RAJAL_JANTUNG_STEPS), list(range(1, 11)))
        for number, spec in RAJAL_JANTUNG_STEPS.items():
            self.assertEqual(spec.number, number)
            self.assertTrue(spec.title)
            for item in spec.fields:
                self.assertIn(item.kind, {'text', 'select', 'number', 'boolean'})

    def test_rajal_rejects_unknown_key(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            save_step(self.visit.pk, self.nurse, 1, {'diagnosa_utama': 'x'}, 0,
                      service_line='RAJAL_JANTUNG')
        self.assertIn('__all__', ctx.exception.errors)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_rajal_rejects_value_outside_declared_choices(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            save_step(self.visit.pk, self.nurse, 1, {'penjamin': 'GRATIS'}, 0,
                      service_line='RAJAL_JANTUNG')
        self.assertEqual(ctx.exception.errors['penjamin'],
                         ['Pilihan harus salah satu dari: UMUM, BPJS, ASURANSI.'])

    def test_rajal_rejects_numeric_value_outside_declared_range(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            save_step(self.visit.pk, self.nurse, 4, {'ttv_spo2': 140}, 0,
                      service_line='RAJAL_JANTUNG')
        self.assertEqual(ctx.exception.errors['ttv_spo2'], ['Nilai maksimal 100.'])


class RajalAuthorizationTest(PoliFixture):
    def test_rajal_visit_on_other_unit_is_denied(self):
        visit = self.make_visit('QA-POLI-PD', unit=self.other_unit)
        with self.assertRaises(PermissionDenied):
            get_visit(visit.pk, self.nurse, service_line='RAJAL_JANTUNG')

    def test_rajal_jantung_visit_with_clinical_profession_is_allowed(self):
        visit, workflow = get_visit(self.visit.pk, self.nurse, service_line='RAJAL_JANTUNG')
        self.assertEqual(visit.pk, self.visit.pk)
        self.assertIsNone(workflow)

    def test_igd_visit_cannot_enter_rajal_line(self):
        igd_unit = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 2})[0]
        igd_visit = KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='QA-IGD-CROSS', jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(), unit_kerja=igd_unit,
        )
        with self.assertRaises(PermissionDenied):
            get_visit(igd_visit.pk, self.nurse, service_line='RAJAL_JANTUNG')

    def test_episode_without_active_dpjp_cannot_enter_clinical_step(self):
        visit = self.make_visit('QA-NO-DPJP', dpjp=False)
        with self.assertRaises(PermissionDenied) as ctx:
            save_step(visit.pk, self.nurse, 1, {'penjamin': 'UMUM'}, 0,
                      service_line='RAJAL_JANTUNG')
        self.assertIn('DPJP', str(ctx.exception))


class RajalDraftTest(PoliFixture):
    def save(self, step, payload, version, user=None):
        return save_step(self.visit.pk, user or self.nurse, step, payload, version,
                         service_line='RAJAL_JANTUNG')

    def test_sequential_steps_raise_version_and_accumulate_payload(self):
        first = self.save(1, {'penjamin': 'UMUM'}, 0)
        self.assertEqual(first.version, 1)
        self.assertEqual(first.service_line, 'RAJAL_JANTUNG')
        self.assertEqual(first.schema_key, 'RAJAL_JANTUNG_V1')
        second = self.save(2, {'keluhan_utama': 'Nyeri dada'}, 1)
        self.assertEqual(second.version, 2)
        second.refresh_from_db()
        self.assertEqual(second.draft_payload['1'], {'penjamin': 'UMUM'})
        self.assertEqual(second.draft_payload['2'], {'keluhan_utama': 'Nyeri dada'})
        self.assertEqual(second.last_step, 2)

    def test_rajal_draft_does_not_write_kunjungan_columns(self):
        before = KunjunganPasien.objects.values().get(pk=self.visit.pk)
        self.save(4, {'ttv_sistole': 130, 'ttv_diastole': 84}, 0)
        after = KunjunganPasien.objects.values().get(pk=self.visit.pk)
        self.assertEqual(before, after)

    def test_stale_version_raises_workflow_conflict(self):
        self.save(1, {'penjamin': 'UMUM'}, 0)
        with self.assertRaises(WorkflowConflict):
            self.save(1, {'penjamin': 'BPJS'}, 0)
        self.assertEqual(self.workflow_for(self.visit).version, 1)

    def test_igd_save_step_still_writes_model_columns(self):
        igd_unit = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 2})[0]
        igd_nurse = self._account('perawat_igd', 'PERAWAT', igd_unit)
        igd_visit = KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='QA-IGD-ENGINE', jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(), unit_kerja=igd_unit,
        )
        workflow = save_step(igd_visit.pk, igd_nurse, 3, {'anamnesis_rps': 'Nyeri ulu hati'}, 0)
        igd_visit.refresh_from_db()
        self.assertEqual(igd_visit.anamnesis_rps, 'Nyeri ulu hati')
        self.assertEqual(workflow.service_line, 'IGD')
        self.assertEqual(workflow.draft_payload, {})


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class PoliRouteTest(PoliFixture):
    def setUp(self):
        self.client.force_login(self.nurse)

    def test_route_is_404_when_flag_disabled(self):
        self.client.force_login(self.dpjp_user)
        with override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=False):
            response = self.client.get(reverse('pasien:poli_workflow', args=[self.visit.pk]))
        self.assertEqual(response.status_code, 404)

    def test_every_step_one_to_ten_renders(self):
        for step in range(1, 11):
            response = self.client.get(
                reverse('pasien:poli_workflow', args=[self.visit.pk]) + f'?step={step}')
            self.assertEqual(response.status_code, 200, f'langkah {step}')
            self.assertEqual(response.context['step'], step)

    def test_step_eleven_is_bad_request(self):
        response = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=11')
        self.assertEqual(response.status_code, 400)

    def test_template_renders_ten_numbered_links_and_aria_current(self):
        body = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=3').content.decode()
        self.assertEqual(body.count('class="poli-steps"'), 1)
        for number in range(1, 11):
            self.assertIn(f'href="?step={number}"', body)
        self.assertEqual(len(re.findall(r'<a href="\?step=\d+" aria-current="step">', body)), 1)
        current = re.search(r'<a href="\?step=(\d+)" aria-current="step">', body)
        self.assertIsNotNone(current)
        self.assertEqual(current.group(1), '3')

    def test_post_draft_raises_version_and_returns_values(self):
        url = reverse('pasien:poli_workflow_draft', args=[self.visit.pk, 1])
        first = self.client.post(url, data=json.dumps({'fields': {'penjamin': 'BPJS'}, 'version': 0}),
                                 content_type='application/json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['version'], 1)
        self.assertEqual(first.json()['values'], {'penjamin': 'BPJS'})
        second = self.client.post(url, data=json.dumps({'fields': {'penjamin': 'UMUM'}, 'version': 1}),
                                  content_type='application/json')
        self.assertEqual(second.json()['version'], 2)
        self.assertEqual(self.workflow_for(self.visit).draft_payload['1'], {'penjamin': 'UMUM'})

    def test_post_draft_with_stale_version_is_409(self):
        url = reverse('pasien:poli_workflow_draft', args=[self.visit.pk, 1])
        self.client.post(url, data=json.dumps({'fields': {'penjamin': 'BPJS'}, 'version': 0}),
                         content_type='application/json')
        stale = self.client.post(url, data=json.dumps({'fields': {'penjamin': 'UMUM'}, 'version': 0}),
                                 content_type='application/json')
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.workflow_for(self.visit).version, 1)

    def test_non_json_body_is_400(self):
        response = self.client.post(
            reverse('pasien:poli_workflow_draft', args=[self.visit.pk, 1]),
            data='penjamin=UMUM', content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 400)

    def test_final_workflow_renders_read_only_and_hides_finalize_controls(self):
        workflow = save_step(self.visit.pk, self.dpjp_user, 1, {'penjamin': 'UMUM'}, 0,
                             service_line='RAJAL_JANTUNG')
        workflow.status = 'FINAL'
        workflow.save(update_fields=['status'])
        self.visit.status = 'PULANG'
        self.visit.save(update_fields=['status'])

        self.client.force_login(self.dpjp_user)
        body = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=1').content.decode()
        self.assertIn('Asesmen sudah final', body)
        self.assertIn('id="poli-field-penjamin" name="penjamin" disabled', body)
        self.assertNotIn('data-poli-action="finalize"', body)
        self.assertNotIn('Simpan langkah 1', body)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class PoliFinalizationTest(PoliFixture):
    def setUp(self):
        self.client.force_login(self.dpjp_user)
        self._fill_all_steps()

    def _fill_all_steps(self):
        version = 0
        for step in range(1, 11):
            # Langkah 8 & 10 adalah penutup klinis: hanya DPJP (ADR-11).
            actor = self.dpjp_user if step in (8, 10) else self.nurse
            workflow = save_step(self.visit.pk, actor, step, FULL_RAJAL_DRAFT[str(step)],
                                 version, service_line='RAJAL_JANTUNG')
            version = workflow.version
        self.version = version

    def action(self, operation, fields, version=None, request_id=None):
        response = self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({
                'operation': operation, 'fields': fields,
                'version': self.version if version is None else version,
                'request_id': request_id or str(uuid.uuid4()),
            }),
            content_type='application/json',
        )
        if response.status_code == 200:
            self.version = response.json()['version']
        return response

    def test_snapshot_covers_draft_payload_and_uses_rajal_schema_version(self):
        from pasien.services.igd_finalization import clinical_snapshot
        snapshot = clinical_snapshot(self.visit, self.workflow_for(self.visit))
        self.assertEqual(snapshot['schema_version'], 3)
        self.assertEqual(snapshot['draft_payload']['8']['diagnosa_utama'], 'I20.0 Angina tidak stabil')

    def test_sign_then_finalize_creates_revision_one_and_closes_episode(self):
        signed = self.action('sign', {'section': 'MEDIS'})
        self.assertEqual(signed.status_code, 200, signed.content)
        finalized = self.action('finalize', {'resume': 'Kontrol 2 minggu, DAPT dilanjutkan.'})
        self.assertEqual(finalized.status_code, 200, finalized.content)
        workflow = self.workflow_for(self.visit)
        self.assertEqual(workflow.status, 'FINAL')
        self.assertEqual(workflow.finalized_by_id, self.dpjp_user.pk)
        revision = IgdAssessmentRevision.objects.get(workflow=workflow)
        self.assertEqual(revision.revision, 1)
        self.assertEqual(revision.snapshot['disposition']['kondisi_akhir'], 'MEMBAIK')
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, 'PULANG')
        self.assertEqual(self.visit.discharge.kondisi_pulang, 'MEMBAIK')
        self.assertEqual(self.visit.discharge.resume_medis, 'Kontrol 2 minggu, DAPT dilanjutkan.')

    def test_addendum_creates_revision_two_without_touching_revision_one(self):
        self.action('sign', {'section': 'MEDIS'})
        self.action('finalize', {'resume': 'Resume awal.'})
        workflow = self.workflow_for(self.visit)
        first = IgdAssessmentRevision.objects.get(workflow=workflow, revision=1)
        original_snapshot = json.dumps(first.snapshot, sort_keys=True)
        response = self.action('addendum', {'section': 'MEDIS', 'reason': 'Koreksi alamat pasien.',
                                           'text': 'Alamat benar: Jl. Merdeka 1.'})
        self.assertEqual(response.status_code, 200, response.content)
        first.refresh_from_db()
        self.assertEqual(json.dumps(first.snapshot, sort_keys=True), original_snapshot)
        second = IgdAssessmentRevision.objects.get(workflow=workflow, revision=2)
        self.assertEqual(second.snapshot['addenda'][0]['text'], 'Alamat benar: Jl. Merdeka 1.')

    def test_draft_save_after_final_is_409(self):
        self.action('sign', {'section': 'MEDIS'})
        self.action('finalize', {'resume': 'Resume awal.'})
        response = self.client.post(
            reverse('pasien:poli_workflow_draft', args=[self.visit.pk, 3]),
            data=json.dumps({'fields': {'anamnesis_rps': 'Ubah setelah final.'},
                             'version': self.workflow_for(self.visit).version}),
            content_type='application/json')
        self.assertEqual(response.status_code, 409)

    def test_finalize_without_signature_lists_missing_signature(self):
        response = self.action('finalize', {'resume': 'Tanpa tanda tangan.'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Tanda tangan MEDIS untuk data terkini',
                      response.json()['fields']['finalisasi'])
        self.assertEqual(self.workflow_for(self.visit).status, 'DRAFT')

    def test_finalize_rejected_when_a_step_is_empty(self):
        self.action('sign', {'section': 'MEDIS'})
        workflow = self.workflow_for(self.visit)
        workflow.exemptions = {f'step_{n}': 'Tidak dapat dinilai pada kunjungan ini.'
                               for n in range(1, 11) if n != 7}
        workflow.save(update_fields=['exemptions'])
        # Tanda tangan dibatalkan oleh perubahan pengecualian; tanda tangani ulang.
        self.version = workflow.version
        self.action('sign', {'section': 'MEDIS'})
        workflow = self.workflow_for(self.visit)
        draft = dict(workflow.draft_payload)
        draft.pop('7', None)
        workflow.draft_payload = draft
        workflow.save(update_fields=['draft_payload'])
        response = self.action('finalize', {'resume': 'Langkah 7 kosong.'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('step_7', response.json()['fields']['finalisasi'])


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class LegacyWriterGateTest(PoliFixture):
    """F1.9 — gate urutan rilis: penunjang ditutup, CPPT/SOAP tetap terbuka."""

    def setUp(self):
        self.client.force_login(self.nurse)
        save_step(self.visit.pk, self.nurse, 1, {'penjamin': 'UMUM'}, 0,
                  service_line='RAJAL_JANTUNG')

    def test_order_penunjang_is_closed_for_rajal_jantung_workflow(self):
        response = self.client.post(
            reverse('pasien:order_penunjang_buat', args=[self.visit.pk]),
            data={'catalogue_item': '', 'prioritas': 'RUTIN'})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(self.visit.order_penunjang.exists())

    def test_cppt_tambah_still_writes_one_row(self):
        response = self.client.post(
            reverse('pasien:cppt_tambah', kwargs={'kunjungan_pk': self.visit.pk}),
            data={'profesi': 'DOKTER', 'nama_ppa': 'dr. Uji', 'tanggal': timezone.now().isoformat(),
                  'subjektif': 'Nyeri dada', 'objektif': 'TD 128/82', 'asesmen': 'Angina',
                  'plan': 'EKG'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CPPT.objects.filter(kunjungan=self.visit).count(), 1)

    def test_rajal_soap_simpan_still_writes_one_row(self):
        response = self.client.post(
            reverse('pasien:rajal_soap_simpan', args=[self.visit.pk]),
            data={'subjektif': 'Kontrol', 'objektif': 'Baik', 'asesmen': 'Stabil', 'plan': 'Lanjut obat'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CPPT.objects.filter(kunjungan=self.visit).count(), 1)

    def test_visit_without_workflow_keeps_all_legacy_writers_open(self):
        plain = self.make_visit('QA-POLI-PLAIN')
        self.client.post(
            reverse('pasien:cppt_tambah', kwargs={'kunjungan_pk': plain.pk}),
            data={'profesi': 'DOKTER', 'nama_ppa': 'dr. Uji', 'tanggal': timezone.now().isoformat(),
                  'subjektif': 'S', 'objektif': 'O', 'asesmen': 'A', 'plan': 'P'})
        self.assertEqual(CPPT.objects.filter(kunjungan=plain).count(), 1)
        order = self.client.post(
            reverse('pasien:order_penunjang_buat', args=[plain.pk]),
            data={'catalogue_item': '', 'prioritas': 'RUTIN'})
        self.assertNotEqual(order.status_code, 409)


class IdempotentActionTest(PoliFixture):
    def test_replayed_request_id_returns_identical_result_with_one_row(self):
        from pasien.services.igd_actions import perform_action
        request_id = str(uuid.uuid4())
        first = perform_action(self.visit.pk, self.dpjp_user, 'sign', {'section': 'MEDIS'}, 0,
                               request_id, service_line='RAJAL_JANTUNG')
        second = perform_action(self.visit.pk, self.dpjp_user, 'sign', {'section': 'MEDIS'}, 0,
                                request_id, service_line='RAJAL_JANTUNG')
        self.assertFalse(first['replayed'])
        self.assertTrue(second['replayed'])
        self.assertEqual(first['version'], second['version'])
        self.assertEqual(first['signed_section'], second['signed_section'])
        self.assertEqual(
            IgdWorkflowAction.objects.filter(workflow__kunjungan=self.visit).count(), 1)

    def test_same_request_id_with_different_payload_is_conflict(self):
        from pasien.services.igd_actions import perform_action
        request_id = str(uuid.uuid4())
        perform_action(self.visit.pk, self.dpjp_user, 'sign', {'section': 'MEDIS'}, 0,
                       request_id, service_line='RAJAL_JANTUNG')
        with self.assertRaises(WorkflowConflict):
            perform_action(self.visit.pk, self.dpjp_user, 'sign',
                           {'section': 'MEDIS', 'exemptions': {'step_1': 'Tidak dapat dinilai'}},
                           0, request_id, service_line='RAJAL_JANTUNG')
