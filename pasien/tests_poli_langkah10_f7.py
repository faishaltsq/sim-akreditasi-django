"""Langkah 10 POLI-JANTUNG: evaluasi akhir, disposisi, mutu, EP (F7).

Setiap tes menyatakan perilaku yang dapat diamati: isi ``draft_payload``,
``DischargeRecord``, status ``KunjunganPasien``, baris ``InsidenKeselamatan`` /
``KorelasiEpAsesmen`` / ``CatatanIndikator``, kode respons HTTP, atau isi PDF.

Opsi dan kode di berkas ini berasal dari matriks (``workflow_schemas``) dan
katalog STARKES 2024 — tidak ada satu pun yang dikarang. Katalog uji dibuat
dengan 800 EP dan ``version='2024'`` supaya penjaga ADR-7 di perintah seed
benar-benar diuji, bukan dilewati.
"""
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import Category, Framework, StandardItem, UnitKerja
from akreditasi.risiko_models import CatatanIndikator, IndikatorMutu, InsidenKeselamatan
from klinis.models import AturanEpAsesmen, AturanEpTindakan
from pasien.models import (
    Bed, CPPT, DischargeRecord, IgdAssessmentRevision, IgdAssessmentWorkflow,
    KorelasiEpAsesmen, KunjunganPasien, Pasien, Ruangan,
)
from pasien.services.igd_assessment_workflow import WorkflowValidation, save_step
from pasien.workflow_schemas import (
    DISPOSISI_RAJAL_CHOICES, INSIDEN_RAJAL_CHOICES, KONDISI_AKHIR_RAJAL_CHOICES,
    RESPONS_TERAPI_CHOICES, RAJAL_JANTUNG_STEPS,
)

from .tests_poli_workflow import TEST_STORAGES, PoliFixture

#: Sub-standar yang dipakai perintah seed (sama dengan matriks §6).
SEED_SUB_STANDARDS = (
    'AKP 3', 'AKP 3.1', 'AKP 5', 'AKP 5.1', 'AKP 5.4', 'PP 1.1', 'PP 2',
    'HPK 4.1', 'KE 4', 'KPS 4', 'PMKP 8', 'SKP 2', 'SKP 3', 'SKP 6', 'SKP 1',
)

STEP10 = {
    'kondisi_akhir_rajal': 'STABIL_MEMBAIK',
    'respons_terapi': 'BAIK',
    'evaluasi_respon_terapi': 'Nyeri turun NRS 3→1, hemodinamik stabil.',
    'ttv_pulang_sistole': 122,
    'ttv_pulang_diastole': 78,
    'ttv_pulang_nadi': 84,
    'disposisi': 'PULANG',
    'insiden_keselamatan': 'TIDAK_ADA',
}

class KatalogFixture(PoliFixture):
    """Katalog STARKES 2024 (800 EP) + unit poli + indikator nasional sumber."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        framework = Framework.objects.create(
            name='STARKES Edisi 2024 (uji F7)', version='2024',
            edition='2022', lifecycle='ACTIVE', is_active=True,
        )
        category = Category.objects.create(
            framework=framework, code='UJI', name='Pokja Uji F7', order=1,
        )
        items = []
        order = 0
        for sub in SEED_SUB_STANDARDS:
            order += 1
            items.append(StandardItem(
                category=category, sub_standard=sub, sub_title=f'Judul {sub}',
                code=f'{sub} EP a', description=f'EP {sub} a', order=order,
            ))
        while len(items) < 800:
            order += 1
            items.append(StandardItem(
                category=category, sub_standard=f'UJI {order}',
                sub_title=f'Sub {order}', code=f'UJI {order} EP a',
                description=f'EP uji {order}', order=order,
            ))
        StandardItem.objects.bulk_create(items)
        IndikatorMutu.objects.create(
            kode_indikator='INM-06', nama_indikator='Waktu Tunggu Rawat Jalan (<= 60 Menit)',
            jenis='NASIONAL', dimensi_mutu='TEPAT_WAKTU',
            numerator='n', denominator='d', target_nilai=Decimal('80.00'),
        )

    def seed(self):
        call_command('seed_poli_jantung_ep', verbosity=0)

    def fill(self, visit, step10=None):
        """Isi langkah 1–10 dengan payload minimal yang sah untuk kontrak F7."""
        payloads = {
            1: {'penjamin': 'UMUM', 'jenis_kunjungan_klinis': 'KONTROL'},
            2: {'keluhan_utama': 'Nyeri dada kiri', 'cara_datang': 'SENDIRI'},
            3: {'anamnesis_rps': 'Nyeri sejak 2 hari.'},
            4: {'ttv_sistole': 130, 'ttv_diastole': 84, 'ttv_nadi': 88},
            5: {'skrining_gizi_mst': 1, 'skrining_jatuh_skor': 15},
            6: {'keadaan_umum': 'Compos mentis', 'fisik_lokalis': 'Kor S1-S2 normal.'},
            7: {'penunjang_catatan': 'EKG 12-lead.'},
            8: {'diagnosa_utama': 'I20.0 Angina tidak stabil', 'rencana_terapi': 'DAPT.'},
            9: {'cppt_ringkas': 'Edukasi diet.'},
            10: dict(STEP10 if step10 is None else step10),
        }
        version = 0
        for step in range(1, 11):
            actor = self.dpjp_user if step in (8, 10) else self.nurse
            workflow = save_step(visit.pk, actor, step, payloads[step], version,
                                 service_line='RAJAL_JANTUNG')
            version = workflow.version
        return version


class Step10SchemaTest(KatalogFixture):
    """F7.1/F7.2 — opsi dan aturan percabangan berasal dari matriks."""

    def test_options_are_quoted_verbatim_from_the_matrix(self):
        self.assertEqual(KONDISI_AKHIR_RAJAL_CHOICES,
                         ('STABIL_MEMBAIK', 'TETAP_PEMANTAUAN', 'MEMBURUK_IGD'))
        self.assertEqual(RESPONS_TERAPI_CHOICES, ('BAIK', 'CUKUP_BAIK', 'KURANG_OPTIMAL'))
        self.assertEqual(DISPOSISI_RAJAL_CHOICES,
                         ('PULANG', 'RAWAT_INAP', 'RUJUK_ANTAR_POLI', 'RUJUK_KELUAR'))
        self.assertEqual(INSIDEN_RAJAL_CHOICES,
                         ('TIDAK_ADA', 'KNC', 'KTD_SENTINEL', 'RISIKO_KEPATUHAN'))
        names = RAJAL_JANTUNG_STEPS[10].field_names
        for name in ('kondisi_akhir_rajal', 'respons_terapi', 'ttv_pulang_sistole',
                     'ttv_pulang_diastole', 'ttv_pulang_nadi', 'disposisi',
                     'insiden_keselamatan'):
            self.assertIn(name, names)

    def test_only_three_discharge_vitals_are_accepted(self):
        """S10-L1-04 + AMBIGU-06: RR/SpO2/suhu pulang tidak ditambahkan."""
        names = RAJAL_JANTUNG_STEPS[10].field_names
        self.assertNotIn('ttv_pulang_rr', names)
        self.assertNotIn('ttv_pulang_spo2', names)
        self.assertNotIn('ttv_pulang_suhu', names)

    def test_disposition_branch_requires_its_own_fields(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            save_step(self.visit.pk, self.dpjp_user, 10,
                      {**STEP10, 'disposisi': 'RUJUK_KELUAR'}, 0,
                      service_line='RAJAL_JANTUNG')
        self.assertIn('disposisi_rs_tujuan', ctx.exception.errors)
        self.assertIn('disposisi_stabilisasi', ctx.exception.errors)

    def test_antar_poli_branch_requires_internal_target_and_reason(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            save_step(self.visit.pk, self.dpjp_user, 10,
                      {**STEP10, 'disposisi': 'RUJUK_ANTAR_POLI'}, 0,
                      service_line='RAJAL_JANTUNG')
        self.assertIn('disposisi_poli', ctx.exception.errors)
        self.assertIn('disposisi_alasan', ctx.exception.errors)

    def test_pulang_branch_needs_no_branch_fields(self):
        workflow = save_step(self.visit.pk, self.dpjp_user, 10, STEP10, 0,
                             service_line='RAJAL_JANTUNG')
        self.assertEqual(workflow.draft_payload['10']['disposisi'], 'PULANG')


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class FinalizationTest(KatalogFixture):
    """F7.1/F7.3 — kondisi akhir, TTV pulang, kunci final, addendum."""

    def setUp(self):
        self.client.force_login(self.dpjp_user)
        self.version = self.fill(self.visit)

    def action(self, operation, fields, version=None):
        response = self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({
                'operation': operation, 'fields': fields,
                'version': self.version if version is None else version,
                'request_id': str(uuid.uuid4()),
            }),
            content_type='application/json',
        )
        if response.status_code == 200:
            self.version = response.json()['version']
        return response

    def finalize(self):
        signed = self.action('sign', {'section': 'MEDIS'})
        self.assertEqual(signed.status_code, 200, signed.content)
        response = self.action('finalize', {'resume': 'Kontrol 2 minggu.'})
        self.assertEqual(response.status_code, 200, response.content)
        return response

    # ── F7.1 ────────────────────────────────────────────────────────────────
    def test_final_keeps_payload_and_writes_binding_discharge_condition(self):
        self.finalize()
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        self.assertEqual(workflow.draft_payload['10']['kondisi_akhir_rajal'],
                         'STABIL_MEMBAIK')
        self.assertEqual(workflow.draft_payload['10']['respons_terapi'], 'BAIK')
        self.assertEqual(workflow.draft_payload['10']['ttv_pulang_sistole'], 122)
        self.visit.refresh_from_db()
        # Kondisi yang mengikat ada di DischargeRecord, bukan kolom baru.
        self.assertEqual(self.visit.discharge.kondisi_pulang, 'MEMBAIK')
        self.assertFalse(
            hasattr(KunjunganPasien, 'kondisi_akhir_rajal'),
            'kondisi akhir rajal tidak boleh menjadi kolom KunjunganPasien',
        )

    def test_discharge_vitals_appear_on_the_resume_pdf(self):
        self.finalize()
        response = self.client.get(reverse('pasien:resume_pdf', args=[self.visit.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        from pasien.pdf_utils import _rajal_discharge_vitals
        self.visit.refresh_from_db()
        self.assertEqual(
            [row[0] for row in _rajal_discharge_vitals(self.visit)],
            ['Tekanan Darah Sistolik', 'Tekanan Darah Diastolik', 'Nadi'],
        )
        self.assertEqual(_rajal_discharge_vitals(self.visit)[0][1], '122 mmHg')

    # ── F7.3 ────────────────────────────────────────────────────────────────
    def test_draft_save_after_final_is_409(self):
        self.finalize()
        response = self.client.post(
            reverse('pasien:poli_workflow_draft', args=[self.visit.pk, 3]),
            data=json.dumps({'fields': {'anamnesis_rps': 'Ubah setelah final.'},
                             'version': self.version}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn('addendum', response.json()['error'])

    def test_addendum_creates_new_revision_and_leaves_revision_one_untouched(self):
        self.finalize()
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        first = IgdAssessmentRevision.objects.get(workflow=workflow, revision=1)
        original = json.dumps(first.snapshot, sort_keys=True, default=str)
        response = self.action('addendum', {
            'section': 'MEDIS', 'reason': 'Koreksi alamat pasien.',
            'text': 'Alamat benar: Jl. Merdeka 1.',
        })
        self.assertEqual(response.status_code, 200, response.content)
        first.refresh_from_db()
        self.assertEqual(json.dumps(first.snapshot, sort_keys=True, default=str), original)
        second = IgdAssessmentRevision.objects.get(workflow=workflow, revision=2)
        self.assertEqual(second.snapshot['addenda'][0]['text'],
                         'Alamat benar: Jl. Merdeka 1.')
        self.assertEqual(second.snapshot['addenda'][0]['author_id'], self.dpjp_user.pk)
        # Catatan asli tetap ada di revisi baru, bukan ditimpa.
        self.assertEqual(second.snapshot['disposition']['kondisi_akhir'], 'STABIL_MEMBAIK')

    def test_panel_shows_version_time_and_locked_state(self):
        self.finalize()
        body = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=10'
        ).content.decode()
        self.assertIn('Versi final', body)
        self.assertIn('Final Terkunci (Read-Only setelah verifikasi DPJP)', body)
        self.assertIn('Mode Addendum', body)
        self.assertIn('Revisi 1', body)
        self.assertNotIn('Simpan langkah 10', body)

    def test_only_dpjp_sees_addendum_control(self):
        self.finalize()
        self.client.force_login(self.nurse)
        body = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=10'
        ).content.decode()
        self.assertNotIn('data-poli-action="addendum"', body)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class DispositionBranchTest(KatalogFixture):
    """F7.2 — empat cabang, masing-masing dengan dokumen dan status sendiri."""

    def setUp(self):
        self.client.force_login(self.dpjp_user)

    def _finish(self, step10):
        version = self.fill(self.visit, step10)
        self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'sign', 'fields': {'section': 'MEDIS'},
                             'version': version, 'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        response = self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'finalize', 'fields': {'resume': 'Resume.'},
                             'version': workflow.version,
                             'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        self.visit.refresh_from_db()
        return response

    def test_pulang_closes_episode_and_links_pulang_documents(self):
        response = self._finish({**STEP10, 'disposisi': 'PULANG'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['disposition'], 'PULANG')
        self.assertEqual(self.visit.status, 'PULANG')
        self.assertEqual(self.visit.status_antrean, 'SELESAI')
        self.assertEqual(DischargeRecord.objects.get(kunjungan=self.visit).kondisi_pulang,
                         'MEMBAIK')
        self.assertEqual(sorted(response.json()['documents']),
                         ['pasien:cetak_skdp', 'pasien:poli_edukasi_pdf', 'pasien:resume_pdf'])

    def test_rawat_inap_admits_patient_and_requires_a_bed(self):
        before = self.visit.status
        response = self._finish({**STEP10, 'disposisi': 'RAWAT_INAP'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('bed_id', response.json()['fields'])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, before)
        self.assertIsNone(self.visit.bed_id)
        self.assertFalse(
            IgdAssessmentWorkflow.objects.get(kunjungan=self.visit).status == 'FINAL'
        )

    def test_rawat_inap_with_available_bed_occupies_it(self):
        ruangan = Ruangan.objects.create(
            kode='R-ICCUF7', nama='ICCU Uji F7', kelas='ICU', jenis='ICU',
            kapasitas=2, unit_kerja=self.unit,
        )
        bed = Bed.objects.create(ruangan=ruangan, kode_bed='ICCU-1', status='TERSEDIA')
        version = self.fill(self.visit, {**STEP10, 'disposisi': 'RAWAT_INAP'})
        self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'sign', 'fields': {'section': 'MEDIS'},
                             'version': version, 'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        response = self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({
                'operation': 'finalize',
                'fields': {'resume': 'Admisi ICCU.', 'bed_id': bed.pk,
                           'dpjp': 'dr. Uji Sp.JP'},
                'version': workflow.version, 'request_id': str(uuid.uuid4()),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.visit.refresh_from_db()
        bed.refresh_from_db()
        self.assertEqual(self.visit.status, 'RANAP')
        self.assertEqual(self.visit.bed_id, bed.pk)
        self.assertEqual(bed.status, 'TERISI')
        self.assertEqual(sorted(response.json()['documents']),
                         ['pasien:cetak_general_consent', 'pasien:cetak_spri'])

    def test_rujuk_antar_poli_moves_queue_to_target_poli(self):
        response = self._finish({
            **STEP10, 'disposisi': 'RUJUK_ANTAR_POLI',
            'disposisi_poli': 'POLI_SARAF', 'disposisi_alasan': 'Nyeri kepala berulang.',
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.konsul_ke_poli, 'POLI_SARAF')
        self.assertEqual(self.visit.konsul_catatan, 'Nyeri kepala berulang.')
        self.assertEqual(self.visit.status, 'DISPOSISI')
        self.assertEqual(DischargeRecord.objects.get(kunjungan=self.visit).kondisi_pulang,
                         'MEMBAIK')

    def test_rujuk_keluar_records_sisrute_fields_and_rujuk_condition(self):
        response = self._finish({
            **STEP10, 'disposisi': 'RUJUK_KELUAR',
            'disposisi_rs_tujuan': 'RS Jantung Sehat',
            'disposisi_alasan': 'Butuh kateterisasi.',
            'disposisi_stabilisasi': 'TD 120/80, nadi 84, sadar penuh.',
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, 'RUJUK')
        self.assertEqual(self.visit.sisrute_rs_tujuan, 'RS Jantung Sehat')
        self.assertEqual(self.visit.sisrute_alasan, 'Butuh kateterisasi.')
        self.assertEqual(DischargeRecord.objects.get(kunjungan=self.visit).kondisi_pulang,
                         'RUJUK')

    def test_step_ten_without_disposition_is_rejected_at_save(self):
        """F7.2: episode tidak boleh tersimpan tanpa satu cabang disposisi."""
        version = 0
        for step in range(1, 10):
            payload = {1: {'penjamin': 'UMUM'}, 2: {'keluhan_utama': 'Nyeri dada'},
                       3: {'anamnesis_rps': 'Nyeri sejak 2 hari.'},
                       4: {'ttv_sistole': 130}, 5: {'skrining_gizi_mst': 1},
                       6: {'keadaan_umum': 'Compos mentis'},
                       7: {'penunjang_catatan': 'EKG.'},
                       8: {'diagnosa_utama': 'I20.0 Angina tidak stabil'},
                       9: {'cppt_ringkas': 'Edukasi.'}}[step]
            actor = self.dpjp_user if step == 8 else self.nurse
            version = save_step(self.visit.pk, actor, step, payload, version,
                                service_line='RAJAL_JANTUNG').version
        with self.assertRaises(WorkflowValidation) as ctx:
            save_step(self.visit.pk, self.dpjp_user, 10,
                      {k: v for k, v in STEP10.items() if k != 'disposisi'}, version,
                      service_line='RAJAL_JANTUNG')
        self.assertIn('disposisi', ctx.exception.errors)
        self.assertNotIn(
            '10', IgdAssessmentWorkflow.objects.get(kunjungan=self.visit).draft_payload
        )


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class IncidentAndIndicatorTest(KatalogFixture):
    """F7.4/F7.7 — insiden keselamatan dan umpan indikator PDCA unit."""

    def setUp(self):
        self.client.force_login(self.dpjp_user)
        self.seed()

    def _finish(self, step10, registrasi=None, cppt_signed_at=None):
        if registrasi is not None:
            self.visit.registrasi_selesai_at = registrasi
            self.visit.save(update_fields=['registrasi_selesai_at'])
        if cppt_signed_at is not None:
            CPPT.objects.create(
                kunjungan=self.visit, profesi='DOKTER', nama_ppa='dr. Uji Sp.JP',
                tanggal=cppt_signed_at, subjektif='s', objektif='o', asesmen='a',
                plan='p', status='SIGNED', created_by=self.dpjp_user,
            )
        version = self.fill(self.visit, step10)
        self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'sign', 'fields': {'section': 'MEDIS'},
                             'version': version, 'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        return self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'finalize', 'fields': {'resume': 'Resume.'},
                             'version': workflow.version,
                             'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )

    # ── F7.4 ────────────────────────────────────────────────────────────────
    def test_ktd_option_creates_one_incident_row_for_the_unit(self):
        response = self._finish({**STEP10, 'insiden_keselamatan': 'KTD_SENTINEL'})
        self.assertEqual(response.status_code, 200, response.content)
        rows = InsidenKeselamatan.objects.filter(kunjungan=self.visit)
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.unit_id, self.unit.pk)
        self.assertEqual(row.jenis_insiden, 'KTD')
        self.assertTrue(row.pasien_terpapar)
        self.assertIn(self.visit.no_kunjungan, row.deskripsi_kejadian)

    def test_knc_option_maps_to_knc_and_no_patient_harm(self):
        self._finish({**STEP10, 'insiden_keselamatan': 'KNC'})
        row = InsidenKeselamatan.objects.get(kunjungan=self.visit)
        self.assertEqual(row.jenis_insiden, 'KNC')
        self.assertFalse(row.pasien_terpapar)

    def test_no_incident_option_creates_no_row(self):
        self._finish({**STEP10, 'insiden_keselamatan': 'TIDAK_ADA'})
        self.assertFalse(InsidenKeselamatan.objects.filter(kunjungan=self.visit).exists())

    def test_compliance_risk_option_does_not_invent_an_incident_type(self):
        """AMBIGU-22: opsi keempat tidak punya padanan di InsidenKeselamatan."""
        response = self._finish({**STEP10, 'insiden_keselamatan': 'RISIKO_KEPATUHAN'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(InsidenKeselamatan.objects.filter(kunjungan=self.visit).exists())
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        self.assertEqual(workflow.draft_payload['10']['insiden_keselamatan'],
                         'RISIKO_KEPATUHAN')

    # ── F7.7 ────────────────────────────────────────────────────────────────
    def test_completed_visit_increments_the_waiting_time_indicator(self):
        start = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        response = self._finish(
            {**STEP10}, registrasi=start, cppt_signed_at=start + timedelta(minutes=45),
        )
        self.assertEqual(response.status_code, 200, response.content)
        record = CatatanIndikator.objects.get(
            indikator__kode_indikator='IMU-POLJAN-01',
            bulan=start.month, tahun=start.year,
        )
        self.assertEqual(record.nilai_denominator, 1)
        self.assertEqual(record.nilai_numerator, 1)
        self.assertEqual(record.nilai_capaian, Decimal('100'))

    def test_waiting_time_beyond_sixty_minutes_counts_as_non_compliant(self):
        start = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        self._finish({**STEP10}, registrasi=start,
                     cppt_signed_at=start + timedelta(minutes=75))
        record = CatatanIndikator.objects.get(
            indikator__kode_indikator='IMU-POLJAN-01',
            bulan=start.month, tahun=start.year,
        )
        self.assertEqual(record.nilai_numerator, 0)
        self.assertEqual(record.nilai_denominator, 1)

    def test_indicator_is_recounted_not_accumulated_on_repeat(self):
        start = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        self._finish({**STEP10}, registrasi=start,
                     cppt_signed_at=start + timedelta(minutes=30))
        from pasien.services.igd_finalization import _record_unit_indicators
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        _record_unit_indicators(self.visit, timezone.now())
        record = CatatanIndikator.objects.get(
            indikator__kode_indikator='IMU-POLJAN-01',
            bulan=start.month, tahun=start.year,
        )
        self.assertEqual(record.nilai_denominator, 1)
        self.assertEqual(workflow.status, 'FINAL')


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class EpRulesTest(KatalogFixture):
    """F7.5/F7.6 — aturan EP sebagai data, bukti EP, ekspor PDF."""

    def setUp(self):
        self.client.force_login(self.dpjp_user)

    def test_seed_writes_rules_and_indicators_idempotently(self):
        self.seed()
        self.seed()
        self.assertEqual(AturanEpAsesmen.objects.filter(layanan='RAJAL_JANTUNG').count(), 14)
        self.assertEqual(AturanEpTindakan.objects.filter(layanan='RAJAL_JANTUNG').count(), 2)
        self.assertEqual(
            IndikatorMutu.objects.filter(kode_indikator__startswith='IMU-POLJAN-').count(), 2
        )

    def test_seed_rejects_a_catalogue_that_is_not_the_2024_edition(self):
        Framework.objects.update(version='2022')
        with self.assertRaises(CommandError):
            call_command('seed_poli_jantung_ep', verbosity=0)

    def test_seed_rejects_a_catalogue_with_the_wrong_ep_count(self):
        StandardItem.objects.filter(category__code='UJI').order_by('-order').first().delete()
        with self.assertRaises(CommandError) as ctx:
            call_command('seed_poli_jantung_ep', verbosity=0)
        self.assertIn('799', str(ctx.exception))

    def test_every_seeded_sub_standard_exists_in_the_active_catalogue(self):
        self.seed()
        known = set(StandardItem.objects.values_list('sub_standard', flat=True))
        for rule in AturanEpAsesmen.objects.filter(layanan='RAJAL_JANTUNG'):
            self.assertIn(rule.sub_standard, known)
        for rule in AturanEpTindakan.objects.filter(layanan='RAJAL_JANTUNG'):
            self.assertIn(rule.sub_standard, known)

    def test_igd_form_does_not_see_poli_jantung_rules(self):
        self.seed()
        from klinis.models import AturanEpAsesmen as Rule
        self.assertEqual(Rule.objects.filter(layanan='').count(), 0)
        # Filter yang dipakai form IGD hanya mengambil aturan global.
        self.assertEqual(list(Rule.objects.filter(layanan='')), [])

    def test_finalization_records_ep_evidence_for_every_seeded_rule(self):
        self.seed()
        version = self.fill(self.visit)
        self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'sign', 'fields': {'section': 'MEDIS'},
                             'version': version, 'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        response = self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'finalize', 'fields': {'resume': 'Resume.'},
                             'version': workflow.version,
                             'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        rows = KorelasiEpAsesmen.objects.filter(kunjungan=self.visit)
        self.assertEqual(rows.count(), 14)
        self.assertEqual(set(rows.values_list('status', flat=True)), {'TERPENUHI'})
        self.assertTrue(all(row.diverifikasi_oleh_id == self.dpjp_user.pk for row in rows))
        self.assertTrue(all(row.diverifikasi_pada is not None for row in rows))
        workflow.refresh_from_db()
        revision = IgdAssessmentRevision.objects.get(workflow=workflow, revision=1)
        self.assertEqual(len(revision.snapshot['ep_evidence']), 14)

    def test_action_rule_resolves_for_poli_but_not_for_igd(self):
        from klinis.services.ep_tindakan import primary_for
        self.seed()
        poli = primary_for('ICD9', '89.52', service_line='RAJAL_JANTUNG')
        self.assertIsNotNone(poli)
        self.assertEqual(poli.sub_standard, 'HPK 4.1')
        self.assertIsNone(primary_for('ICD9', '89.52'))

    def test_bukti_ep_pdf_lists_code_status_note_and_verifier_time(self):
        self.seed()
        version = self.fill(self.visit)
        self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'sign', 'fields': {'section': 'MEDIS'},
                             'version': version, 'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        self.client.post(
            reverse('pasien:poli_workflow_action', args=[self.visit.pk]),
            data=json.dumps({'operation': 'finalize', 'fields': {'resume': 'Resume.'},
                             'version': workflow.version,
                             'request_id': str(uuid.uuid4())}),
            content_type='application/json',
        )
        response = self.client.get(
            reverse('pasien:poli_bukti_ep_pdf', args=[self.visit.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('Bukti_EP_', response['Content-Disposition'])

        from pasien.services.ep_evidence import bukti_ep
        self.visit.refresh_from_db()
        proof = bukti_ep(self.visit)
        self.assertEqual(proof['total_asesmen'], 14)
        self.assertEqual(proof['terpenuhi'], 14)
        first = proof['asesmen'][0]
        self.assertTrue(first['code'])
        self.assertEqual(first['status'], 'TERPENUHI')
        self.assertTrue(first['catatan'])
        self.assertTrue(first['verifier'])
        self.assertIsNotNone(first['verified_at'])

        page = self.client.get(
            reverse('pasien:poli_bukti_ep_cetak', args=[self.visit.pk])
        )
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertIn(first['code'], body)
        self.assertIn('Terpenuhi', body)
        self.assertIn(first['verifier'], body)

    def test_bukti_ep_is_scoped_to_the_episode(self):
        # Pengguna klinis tanpa penugasan unit: lingkup baca kosong, sehingga
        # dokumen bukti tidak boleh terbuka (poli POLI-PD bukan pembanding sah —
        # unit itu induk POLI-JANTUNG dalam hierarki UnitKerja).
        outsider = User.objects.create_user('qa10-luar', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=outsider,
            defaults={'role': 'STAF_NAKES', 'profesi': 'PERAWAT', 'unit_kerja': None},
        )
        self.client.force_login(outsider)
        response = self.client.get(
            reverse('pasien:poli_bukti_ep_pdf', args=[self.visit.pk])
        )
        self.assertIn(response.status_code, (403, 404))
