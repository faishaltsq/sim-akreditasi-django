import copy
import json
import subprocess
from pathlib import Path
from django.test import SimpleTestCase
from html.parser import HTMLParser
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse

from accounts.models import UserProfile
from pasien.forms_igd_workflow import LEGACY_STEP8_FIELDS, STEPS, snapshot_visit_fields
from pasien.models import IgdAssessmentRevision, IgdAssessmentWorkflow
from pasien.services.igd_actions import digest, perform_action
from pasien.services.igd_finalization import EXEMPTIONS, clinical_snapshot
from pasien.tests_igd_workflow import IgdWorkflowTest


class WorkflowMarkup(HTMLParser):
    void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, response):
        super().__init__()
        self.nodes = []
        self.stack = []
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'parents': tuple(self.stack)}
        self.nodes.append(node)
        if tag not in self.void_tags:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]
                break

    def by_id(self, identifier):
        return next(node for node in self.nodes if node['attrs'].get('id') == identifier)

    def within(self, parent):
        return [node for node in self.nodes if any(ancestor is parent for ancestor in node['parents'])]

    def content_nodes(self):
        content = next(node for node in self.nodes if 'igd-content' in node['attrs'].get('class', '').split())
        return self.within(content)


@override_settings(IGD_WORKFLOW_ENABLED=True)
class Step8ReplacementTest(IgdWorkflowTest):
    def test_replacement_has_no_obsolete_editors(self):
        self.visit.tatalaksana_resusitasi = 'Historical stabilization note'
        self.visit.tatalaksana_terapi = 'Historical medication note'
        self.visit.save(update_fields=['tatalaksana_resusitasi', 'tatalaksana_terapi'])
        response = self.client.get(
            reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=8'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="tatalaksana_resusitasi"')
        self.assertNotContains(response, 'name="tatalaksana_terapi"')
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.tatalaksana_resusitasi, 'Historical stabilization note')
        self.assertEqual(self.visit.tatalaksana_terapi, 'Historical medication note')

    def page(self, step=8):
        response = self.client.get(reverse('pasien:igd_workflow', args=[self.visit.pk]), {'step': step})
        self.assertEqual(response.status_code, 200)
        return response

    def draft(self, fields, version=0):
        return self.client.post(
            reverse('pasien:igd_workflow_draft', args=[self.visit.pk, 8]),
            json.dumps({'version': version, 'fields': fields}), content_type='application/json',
        )

    def actor(self, profession, role='STAF_NAKES'):
        user = User.objects.create_user('s8_' + profession + '_' + role)
        UserProfile.objects.update_or_create(user=user, defaults={
            'role': role, 'profesi': profession, 'unit_kerja': self.unit,
        })
        return user

    def historical_notes(self):
        self.visit.tatalaksana_resusitasi = 'Historical stabilization note'
        self.visit.tatalaksana_terapi = 'Historical medication note'
        self.visit.save(update_fields=list(LEGACY_STEP8_FIELDS))

    def test_ordered_surface_and_independent_forms(self):
        markup = WorkflowMarkup(self.page())
        content = markup.content_nodes()
        identifiers = [node['attrs'].get('id') for node in content]
        ordered = ['igd-diagnoses', 'igd-care-heading', 'igd-action-panel', 'igd-medications', 'igd-step-form', 'igd-nursing-plan']
        self.assertEqual([identifiers.count(name) for name in ordered], [1] * len(ordered))
        self.assertEqual(sorted(identifiers.index(name) for name in ordered), [identifiers.index(name) for name in ordered])
        for node in content:
            if node['tag'] == 'form':
                self.assertFalse(any(parent['tag'] == 'form' for parent in node['parents']))
        for name in ('igd-diagnosis-form', 'plan_action-form', 'medication-form'):
            self.assertIn(name, identifiers)
            self.assertFalse(any(parent['attrs'].get('id') == 'igd-step-form' for parent in markup.by_id(name)['parents']))
        main = markup.by_id('igd-step-form')
        self.assertEqual(main['attrs']['data-step'], '8')
        self.assertEqual(main['attrs']['data-version'], '0')
        fields = [node['attrs']['name'] for node in markup.within(main) if node['attrs'].get('name')]
        self.assertEqual(set(fields), {'csrfmiddlewaretoken', 'diagnosa_masuk', 'diagnosa_keperawatan_sdki', 'luaran_keperawatan_slki', 'intervensi_keperawatan_siki', 'intent'})
        self.assertEqual(len(fields), 7)  # Save and next submitters share intent.
        tabs = [node for node in content if 'data-care-tab' in node['attrs']]
        self.assertEqual({node['attrs']['data-care-tab']: node['attrs']['aria-controls'] for node in tabs}, {'actions': 'igd-action-panel', 'medications': 'igd-medications'})
        self.assertTrue(all(node['attrs']['type'] == 'button' for node in tabs))
        self.assertNotIn('hidden', markup.by_id('igd-action-panel')['attrs'])
        self.assertNotIn('hidden', markup.by_id('igd-medications')['attrs'])
        self.assertFalse(any(node['attrs'].get('data-operation') in ('execute', 'professional_execute', 'cppt') for node in content))

    def test_segments_keep_canonical_selects_and_no_duplicate_mode_names(self):
        markup = WorkflowMarkup(self.page())
        controls = [node for node in markup.content_nodes() if 'data-mode-control' in node['attrs']]
        self.assertEqual(len(controls), 5)
        for control in controls:
            nodes = markup.within(control)
            selects = [node for node in nodes if 'data-mode-select' in node['attrs']]
            self.assertEqual(len(selects), 1)
            self.assertNotIn('hidden', selects[0]['attrs'])
            segment = next(node for node in nodes if 'data-mode-segments' in node['attrs'])
            self.assertIn('hidden', segment['attrs'])
            self.assertTrue(segment['attrs'].get('aria-label'))
            buttons = [node for node in nodes if 'data-mode-value' in node['attrs']]
            self.assertEqual([node['attrs']['data-mode-value'] for node in buttons], ['MANUAL', 'MASTER', 'AI'])
            self.assertTrue(all(node['attrs'].get('type') == 'button' and 'name' not in node['attrs'] for node in buttons))
            self.assertTrue(any(node['tag'] == 'noscript' for node in nodes))
        for form_id in ('igd-diagnosis-form', 'plan_action-form'):
            mode_inputs = [node for node in markup.within(markup.by_id(form_id)) if node['attrs'].get('name') == 'mode']
            self.assertEqual(len(mode_inputs), 1)
            self.assertEqual(mode_inputs[0]['tag'], 'select')
        plan_fields = {node['attrs']['name'] for node in markup.within(markup.by_id('plan_action-form')) if node['attrs'].get('name')}
        self.assertEqual(plan_fields, {'csrfmiddlewaretoken', *self.page().context['plan_form'].fields})

    def test_nursing_save_reload_is_separate_and_preserves_history(self):
        self.historical_notes()
        self.client.force_login(self.actor('PERAWAT'))
        fields = {'diagnosa_keperawatan_sdki': 'Diagnosis keperawatan uji', 'luaran_keperawatan_slki': 'Luaran uji', 'intervensi_keperawatan_siki': 'Intervensi uji'}
        response = self.draft({**fields, 'component_modes': {'sdki': 'MANUAL', 'slki': 'MANUAL', 'siki': 'MANUAL'}})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['version'], 1)
        page = self.page()
        for name, value in fields.items():
            self.assertEqual(page.context['form'][name].value(), value)
            self.assertFalse(page.context['form'].fields[name].disabled)
        self.assertEqual(page.context['version'], 1)
        self.assertEqual([component['mode'] for component in page.context['planning_components']], ['MANUAL'] * 3)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.tatalaksana_resusitasi, 'Historical stabilization note')
        self.assertEqual(self.visit.tatalaksana_terapi, 'Historical medication note')
        self.assertEqual(self.visit.diagnosa_masuk, '')
        self.assertFalse(self.visit.tindakan_asesmen.exists())
        self.assertFalse(self.visit.cppt.exists())
        self.assertFalse(self.visit.billing.exists())
        stale = self.draft({'diagnosa_keperawatan_sdki': 'Stale overwrite'})
        self.assertEqual(stale.status_code, 409)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_keperawatan_sdki, fields['diagnosa_keperawatan_sdki'])

    def test_retired_field_posts_rejected_atomically(self):
        self.historical_notes()
        for name in LEGACY_STEP8_FIELDS:
            with self.subTest(name=name):
                response = self.draft({name: 'Forbidden overwrite', 'diagnosa_masuk': 'Must roll back'})
                self.assertEqual(response.status_code, 400)
                self.assertIn('Field tidak dimiliki langkah ini.', response.json()['fields']['__all__'])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.tatalaksana_resusitasi, 'Historical stabilization note')
        self.assertEqual(self.visit.tatalaksana_terapi, 'Historical medication note')
        self.assertEqual(self.visit.diagnosa_masuk, '')
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())
        self.assertTrue(set(LEGACY_STEP8_FIELDS).isdisjoint(STEPS[8][1]))
        self.assertTrue(set(LEGACY_STEP8_FIELDS).issubset(snapshot_visit_fields()))

    def test_legacy_nonworkflow_form_still_saves_retired_fields(self):
        response = self.client.post(reverse('pasien:igd_asesmen_medis_save', args=[self.visit.pk]), {
            'tatalaksana_resusitasi': 'Legacy stabilization', 'tatalaksana_terapi': 'Legacy therapy',
        })
        self.assertEqual(response.status_code, 302)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.tatalaksana_resusitasi, 'Legacy stabilization')
        self.assertEqual(self.visit.tatalaksana_terapi, 'Legacy therapy')
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_history_is_nonempty_labelled_and_not_an_editor(self):
        self.assertNotIn('igd-step8-history', [node['attrs'].get('id') for node in WorkflowMarkup(self.page()).content_nodes()])
        self.historical_notes()
        response = self.page()
        markup = WorkflowMarkup(response)
        history = markup.by_id('igd-step8-history')
        self.assertFalse(any(node['tag'] in ('input', 'textarea', 'select', 'form') for node in markup.within(history)))
        self.assertEqual(len(response.context['legacy_step8_notes']), 2)
        self.assertContains(response, 'Catatan tata laksana historis — hanya baca')
        self.assertContains(response, 'Historical stabilization note')
        self.assertContains(response, 'Historical medication note')

    def test_signed_content_digest_and_revision_history_stay_stable(self):
        self.historical_notes()
        workflow = IgdAssessmentWorkflow.objects.create(kunjungan=self.visit, origin_unit=self.unit,
            exemptions={name: 'Tidak diindikasikan pada kasus sintetis' for name in EXEMPTIONS})
        previous_fields = sorted({name for _, names in STEPS.values() for name in names} | {'tatalaksana_resusitasi', 'tatalaksana_terapi'})
        with patch('pasien.services.igd_finalization.snapshot_visit_fields', return_value=previous_fields):
            previous = clinical_snapshot(self.visit, workflow)
            signed = perform_action(self.visit.pk, self.user, 'sign', {'section': 'MEDIS'}, 0, str(uuid4()))
        workflow.refresh_from_db()
        self.assertEqual(clinical_snapshot(self.visit, workflow), previous)
        self.assertEqual(digest(previous), workflow.signatures['MEDIS']['content_digest'])
        finalized = perform_action(self.visit.pk, self.user, 'finalize', {'outcome': 'NONE', 'resume': 'Snapshot uji'}, signed['version'], str(uuid4()))
        revision = IgdAssessmentRevision.objects.get(pk=finalized['revision_id'])
        original = copy.deepcopy(revision.snapshot)
        self.assertEqual(revision.snapshot['visit']['tatalaksana_resusitasi'], 'Historical stabilization note')
        self.assertEqual(revision.snapshot['visit']['tatalaksana_terapi'], 'Historical medication note')
        self.visit.tatalaksana_resusitasi = 'Live note must not leak'
        self.visit.tatalaksana_terapi = 'Live therapy must not leak'
        self.visit.save(update_fields=list(LEGACY_STEP8_FIELDS))
        for url in (reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=8', reverse('pasien:igd_workflow_resume', args=[self.visit.pk])):
            response = self.client.get(url)
            self.assertContains(response, 'Historical stabilization note')
            self.assertContains(response, 'Historical medication note')
            self.assertNotContains(response, 'Live note must not leak')
            self.assertNotContains(response, 'Live therapy must not leak')
        perform_action(self.visit.pk, self.user, 'addendum', {'section': 'MEDIS', 'reason': 'Koreksi catatan historis', 'text': 'Tambahan terverifikasi'}, finalized['version'], str(uuid4()))
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot, original)
        self.assertEqual(IgdAssessmentRevision.objects.get(workflow=workflow, revision=2).snapshot['visit'], original['visit'])
        old = self.client.get(reverse('pasien:igd_workflow_resume', args=[self.visit.pk]), {'revision': 1})
        self.assertContains(old, 'Historical stabilization note')
        self.assertNotContains(old, 'Tambahan terverifikasi')

    def test_old_snapshot_missing_retired_fields_never_uses_live_fallback(self):
        self.historical_notes()
        workflow = IgdAssessmentWorkflow.objects.create(kunjungan=self.visit, origin_unit=self.unit, status='FINAL')
        snapshot = clinical_snapshot(self.visit, workflow)
        for name in LEGACY_STEP8_FIELDS:
            snapshot['visit'].pop(name)
        revision = IgdAssessmentRevision.objects.create(workflow=workflow, revision=1, snapshot=snapshot, signed_by=self.user)
        for url in (reverse('pasien:igd_workflow', args=[self.visit.pk]) + '?step=8', reverse('pasien:igd_workflow_resume', args=[self.visit.pk])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['legacy_step8_notes'], [])
            self.assertNotContains(response, 'Historical stabilization note')
            self.assertNotContains(response, 'Historical medication note')
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot, snapshot)

    def test_profession_and_viewer_authorization_remains_unchanged(self):
        fields = {'diagnosa_keperawatan_sdki': 'Unauthorized change'}
        response = self.draft(fields)
        self.assertEqual(response.status_code, 403)
        for profession, role in (('PERAWAT', 'STAF_NAKES'), ('NON_NAKES', 'ADMIN_RS'), ('PERAWAT', 'ASESOR')):
            with self.subTest(profession=profession, role=role):
                self.client.force_login(self.actor(profession, role))
                page = self.page()
                self.assertNotIn('igd-diagnosis-form', [node['attrs'].get('id') for node in WorkflowMarkup(page).content_nodes()])
                if role == 'STAF_NAKES':
                    response = self.draft({'diagnosa_masuk': 'Nurse cannot edit medical diagnosis'})
                else:
                    self.assertTrue(page.context['readonly'])
                    response = self.draft(fields)
                self.assertEqual(response.status_code, 403)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk, '')
        self.assertEqual(self.visit.diagnosa_keperawatan_sdki, '')

    def test_action_request_replay_version_and_persistence_contract(self):
        fields = {'mode': 'MANUAL', 'jenis': 'BEBAS', 'nama': 'Rencana sintetis', 'quantity': '1', 'tarif': '10000', 'catatan_tarif': 'Tarif uji', 'ep_status': 'BELUM'}
        payload = {'operation': 'plan_action', 'fields': fields, 'version': 0, 'request_id': str(uuid4())}
        url = reverse('pasien:igd_workflow_action', args=[self.visit.pk])
        first = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200, first.content)
        replay = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(replay.status_code, 200)
        self.assertFalse(first.json()['replayed'])
        self.assertTrue(replay.json()['replayed'])
        self.assertEqual(replay.json(), {**first.json(), 'replayed': True})
        self.assertEqual(self.visit.tindakan_asesmen.count(), 1)
        self.assertEqual(self.visit.tindakan_asesmen.get().execution_status, 'PLANNED')
        self.assertFalse(self.visit.cppt.exists())
        self.assertFalse(self.visit.billing.exists())
        self.assertEqual(self.page().context['version'], first.json()['version'])
        stale = self.client.post(url, json.dumps({**payload, 'request_id': str(uuid4())}), content_type='application/json')
        self.assertEqual(stale.status_code, 409)

    @override_settings(IGD_PROFESSIONAL_CARE_ENABLED=True)
    def test_step9_professional_controls_stay_outside_step8(self):
        step8 = WorkflowMarkup(self.page())
        self.assertNotIn('professional-care-panel', [node['attrs'].get('id') for node in step8.content_nodes()])
        step9 = WorkflowMarkup(self.page(9))
        identifiers = [node['attrs'].get('id') for node in step9.content_nodes()]
        for name in ('professional-care-panel', 'professional-execution-form', 'professional-profession', 'professional-performer', 'professional-preview'):
            self.assertIn(name, identifiers)
        self.assertNotIn('igd-nursing-plan', identifiers)
        self.assertFalse(any(node['attrs'].get('data-operation') == 'cppt' for node in step9.content_nodes()))
        for node in step9.content_nodes():
            if node['tag'] == 'form':
                self.assertFalse(any(parent['tag'] == 'form' for parent in node['parents']))
        self.assertFalse(self.visit.cppt.exists())
        self.assertFalse(self.visit.billing.exists())
        self.assertFalse(self.visit.tindakan_asesmen.exists())

    def mapped_diagnosis(self):
        from klinis.models import MasterIcd10, MasterIcd9, KelompokLayanan, KasusTersering, KasusTindakan
        from pasien.models import DiagnosisKunjungan
        icd10 = MasterIcd10.objects.create(kode='Z.MAP', nama='Diagnosis sintetis')
        group, _ = KelompokLayanan.objects.get_or_create(kode='IGD', defaults={'nama': 'IGD'})
        case = KasusTersering.objects.create(kelompok=group, icd10=icd10, urutan=901)
        procedure = MasterIcd9.objects.create(kode='M.IGD', nama='Nama kanonis tindakan')
        KasusTindakan.objects.create(kasus=case, icd9=procedure, tarif_umum='12000.50')
        return DiagnosisKunjungan.objects.create(kunjungan=self.visit, icd10=icd10, kode=icd10.kode,
            nama=icd10.nama, mode='MASTER', is_primary=True)

    def mapping(self, diagnosis_id, **query):
        return self.client.get(reverse('pasien:igd_workflow_catalogue', args=[self.visit.pk]),
            {'type': 'ICD9', 'diagnosis_id': diagnosis_id, **query})

    def test_saved_diagnosis_mapping_and_explicit_canonical_plan(self):
        diagnosis = self.mapped_diagnosis()
        response = self.mapping(diagnosis.pk)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['source'], 'KASUS_MASTER')
        self.assertTrue(data['mapping_available'])
        self.assertEqual([r['kode'] for r in data['results']], ['M.IGD'])
        self.assertEqual(data['results'][0]['tarif'], '12000.50')
        self.assertEqual(self.mapping(diagnosis.pk, q='not-present').json()['results'], [])
        self.assertTrue(self.mapping(diagnosis.pk, q='not-present').json()['mapping_available'])
        self.assertFalse(self.visit.tindakan_asesmen.exists())
        fields = {'mode': 'MASTER', 'jenis': 'ICD9', 'kode': 'M.IGD', 'nama': 'Client name ignored',
            'quantity': '2', 'lokasi_anatomis': 'Lengan kiri', 'catatan_klinis': 'Indikasi sintetis', 'ep_status': 'BELUM'}
        result = perform_action(self.visit.pk, self.user, 'plan_action', fields, 0, str(uuid4()))
        self.assertEqual(result['version'], 1)
        line = self.visit.tindakan_asesmen.get()
        self.assertEqual(line.nama, 'Nama kanonis tindakan')
        self.assertEqual(str(line.quantity), '2.00')
        self.assertEqual(line.lokasi_anatomis, 'Lengan kiri')
        self.assertEqual(line.catatan_klinis, 'Indikasi sintetis')
        self.assertEqual(line.execution_status, 'PLANNED')
        self.assertFalse(self.visit.cppt.exists())
        self.assertFalse(self.visit.billing.exists())

    def test_mapping_rejects_invalid_cancelled_and_foreign_diagnoses(self):
        from pasien.models import DiagnosisKunjungan, KunjunganPasien
        diagnosis = self.mapped_diagnosis()
        for invalid in ('', '0', '-1', '1.0', 'true', ' 1', '1e2', '9' * 100):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.mapping(invalid).status_code, 400)
        from django.utils import timezone
        foreign_visit = KunjunganPasien.objects.create(pasien=self.visit.pasien, no_kunjungan='FOREIGN-MAPPING',
            jenis_kunjungan='IGD', unit_kerja=self.unit, tanggal_masuk=timezone.now())
        foreign = DiagnosisKunjungan.objects.create(kunjungan=foreign_visit, kode=diagnosis.kode, nama='Other visit', mode='MASTER')
        self.assertEqual(self.mapping(foreign.pk).status_code, 404)
        diagnosis.active = False
        diagnosis.save(update_fields=['active'])
        self.assertEqual(self.mapping(diagnosis.pk).status_code, 404)

    def test_manual_unmapped_and_global_catalogue_remain_separate(self):
        from pasien.models import DiagnosisKunjungan
        diagnosis = self.mapped_diagnosis()
        manual = DiagnosisKunjungan.objects.create(kunjungan=self.visit, nama='Manual diagnosis', mode='MANUAL')
        self.assertEqual(self.mapping(manual.pk).json(), {'results': [], 'mapping_available': False, 'source': 'KASUS_MASTER'})
        diagnosis.kode = 'Z.NO-MAP'
        diagnosis.save(update_fields=['kode'])
        self.assertFalse(self.mapping(diagnosis.pk).json()['mapping_available'])
        response = self.client.get(reverse('pasien:igd_workflow_catalogue', args=[self.visit.pk]), {'type': 'ICD9', 'q': 'M.IGD'})
        self.assertEqual(response.json(), {'results': [{'kode': 'M.IGD', 'nama': 'Nama kanonis tindakan'}]})

    def test_mapping_markup_primary_secondary_and_manual_kind_default(self):
        from pasien.models import DiagnosisKunjungan
        diagnosis = self.mapped_diagnosis()
        secondary = DiagnosisKunjungan.objects.create(kunjungan=self.visit, icd10=diagnosis.icd10,
            kode=diagnosis.kode, nama='Secondary coded', mode='MASTER')
        DiagnosisKunjungan.objects.create(kunjungan=self.visit, nama='Manual excluded', mode='MANUAL')
        DiagnosisKunjungan.objects.create(kunjungan=self.visit, kode='Z.INACTIVE', nama='Inactive excluded', mode='MASTER', active=False)
        markup = WorkflowMarkup(self.page())
        form = markup.by_id('plan_action-form')
        self.assertEqual(form['attrs']['data-master-kind'], 'ICD9')
        self.assertEqual(self.page().context['plan_form']['jenis'].value(), 'BEBAS')
        select = markup.by_id('igd-action-diagnosis')
        self.assertFalse(any(p is form for p in select['parents']))
        options = [n for n in markup.within(select) if n['tag'] == 'option' and n['attrs'].get('value')]
        self.assertEqual([n['attrs']['value'] for n in options], [str(diagnosis.pk), str(secondary.pk)])
        self.assertIn('selected', options[0]['attrs'])
        self.assertNotIn('selected', options[1]['attrs'])
        for identifier in ('igd-action-source', 'igd-action-query', 'igd-action-results', 'igd-action-mapping-status'):
            markup.by_id(identifier)
        self.assertContains(self.page(), 'Saran Master')
        self.assertContains(self.page(), 'Pelaksana dan waktu aktual dicatat pada Langkah 9')
        diagnosis.is_primary = False
        diagnosis.save(update_fields=['is_primary'])
        markup = WorkflowMarkup(self.page())
        self.assertFalse(any('selected' in n['attrs'] and n['attrs'].get('value') for n in markup.within(markup.by_id('igd-action-diagnosis'))))
        self.client.force_login(self.actor('PERAWAT'))
        self.assertEqual(WorkflowMarkup(self.page()).by_id('plan_action-form')['attrs']['data-master-kind'], 'SIKI')


class ActionMappingAdapterTest(SimpleTestCase):
    def test_mode_mapping_races_and_explicit_selection_without_persistence(self):
        script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(value=''){this.value=value;this.dataset={};this.handlers={};this.children=[];this.options=[];this.hidden=false;}
  addEventListener(name,fn){(this.handlers[name]??=[]).push(fn);}
  dispatchEvent(event){for(const fn of this.handlers[event.type]||[])fn(event);return true;}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  querySelectorAll(){return [];}
  querySelector(){return null;}
  setAttribute(name,value){this[name]=value;}
}
const elements=Object.fromEntries(['mode','jenis','kode','nama','ai_ticket','action_id','quantity','tarif','catatan_tarif'].map(k=>[k,new Element()]));
elements.mode.value='MANUAL';elements.jenis.value='ICD9';elements.quantity.value='3';elements.tarif.value='999';
const form=new Element();form.dataset.masterKind='ICD9';form.elements={namedItem:n=>elements[n]};
const root=new Element();root.dataset.catalogue='/catalogue';root.dataset.ai='/ai';const main=new Element();main.elements={namedItem:()=>null};
const ids={'igd-workflow':root,'igd-step-form':main,'igd-errors':new Element(),'plan_action-form':form,
  'igd-action-source':new Element('DIAGNOSIS'),'igd-action-diagnosis':new Element('1'),'igd-action-query':new Element(),
  'igd-action-results':new Element(),'igd-action-mapping-status':new Element()};
const document={getElementById:id=>ids[id]||null,querySelectorAll:()=>[],querySelector:()=>null,createElement:()=>new Element(),dispatchEvent:()=>{}};
const pending=[];const fetch=url=>new Promise(resolve=>pending.push({url:String(url),resolve}));
const context={document,window:{addEventListener(){},setTimeout,clearTimeout},location:{origin:'http://testserver'},URL,Event,AbortController,
  setTimeout:(fn,delay)=>delay===250?setTimeout(fn,0):setTimeout(fn,delay),clearTimeout,fetch,console};
vm.runInNewContext(fs.readFileSync('static/js/igd-clinical-expansion.js','utf8'),context);
const fire=(node,type='change')=>node.dispatchEvent(new Event(type));
const tick=()=>new Promise(resolve=>setTimeout(resolve,15));
const reply=(req,rows)=>req.resolve({ok:true,json:async()=>({results:rows,mapping_available:rows.length>0,source:'KASUS_MASTER'})});
(async()=>{
  assert.equal(elements.jenis.value,'BEBAS','Manual initializes a free-text kind');
  elements.mode.value='MASTER';fire(elements.mode);assert.equal(elements.jenis.value,'ICD9');
  elements.ai_ticket.value='old';elements.mode.value='MANUAL';fire(elements.mode);assert.equal(elements.jenis.value,'BEBAS');assert.equal(elements.ai_ticket.value,'');
  form.dataset.masterKind='SIKI';elements.mode.value='MASTER';fire(elements.mode);assert.equal(elements.jenis.value,'SIKI');
  elements.mode.value='AI';elements.ai_ticket.value='valid';fire(elements.mode);assert.equal(elements.jenis.value,'SIKI');assert.equal(elements.ai_ticket.value,'valid');
  form.dataset.masterKind='ICD9';
  await tick();assert.ok(pending.length);const first=pending.at(-1);assert.ok(first.url.includes('diagnosis_id=1'));
  ids['igd-action-diagnosis'].value='2';fire(ids['igd-action-diagnosis']);await tick();const second=pending.at(-1);
  reply(second,[{kode:'02',nama:'Current canonical'}]);await tick();
  reply(first,[{kode:'01',nama:'Stale'}]);await tick();
  const results=ids['igd-action-results'];assert.equal(results.children.length,1);assert.ok(results.children[0].textContent.includes('Current canonical'));
  fire(results.children[0],'click');assert.equal(elements.kode.value,'02');assert.equal(elements.nama.value,'Current canonical');
  assert.equal(elements.mode.value,'MASTER');assert.equal(elements.jenis.value,'ICD9');assert.equal(elements.ai_ticket.value,'');
  assert.equal(elements.quantity.value,'3');assert.equal(elements.tarif.value,'999');assert.equal(elements.action_id.value,'');
  ids['igd-action-query'].value='old';fire(ids['igd-action-query'],'input');await tick();const oldQuery=pending.at(-1);
  ids['igd-action-query'].value='new';fire(ids['igd-action-query'],'input');await tick();const newQuery=pending.at(-1);
  reply(newQuery,[]);await tick();reply(oldQuery,[{kode:'03',nama:'Stale query'}]);await tick();
  assert.equal(results.children.length,0);assert.ok(ids['igd-action-mapping-status'].textContent.includes('Belum ada pemetaan tindakan untuk diagnosis ini.'));
  ids['igd-action-source'].value='GLOBAL';fire(ids['igd-action-source']);await tick();assert.ok(!pending.at(-1).url.includes('diagnosis_id'));
  console.log('PASS manual/master/AI modes; diagnosis/query stale responses; master selection without POST');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result = subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
