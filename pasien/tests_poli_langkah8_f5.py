"""Langkah 8 POLI-JANTUNG: diagnosis, klasifikasi, resep, GDMT, edukasi, SKDP (F5).

Setiap tes menyatakan perilaku yang dapat diamati: baris ORM, isi
``draft_payload``, status/kandungan respons HTTP, atau daftar kelompok
formularium. Pilihan klinis diambil dari matriks S8-L1-01..05, S8-L2-01..03 dan
S9-L1-19; tidak ada ambang, dosis, atau kelas obat yang dikarang di sini.

Kelompok GDMT yang **tidak** punya produk katalog diuji justru karena
ketiadaannya harus terlihat: panel menampilkan "belum ada di formularium", dan
``empty_gdmt_groups()`` menyebut kodenya.
"""
import re
import uuid
from decimal import Decimal

from django.apps import apps
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from klinis.models import GenerikObat, KelasTerapiObat, ProdukFarmasi
from pasien.models import (
    DiagnosisKunjungan, DischargeRecord, PharmacyServiceGrant, ResepDetail,
    ResepElektronik,
)
from pasien.services.gdmt import (
    GDMT_GROUPS, adjustment_choices, adjustment_note, empty_gdmt_groups, gdmt_panel,
)
from pasien.services.igd_actions import perform_action
from pasien.services.igd_assessment_workflow import WorkflowValidation, save_step
from pasien.services.skdp import jadwal_kontrol_tanggal, skdp_nomor
from pasien.workflow_schemas import (
    EDUKASI_KARDIO_CHOICES, GDMT_PENYESUAIAN_CHOICES, INPUT_MODE_CHOICES,
    JADWAL_KONTROL_CHOICES, KLASIFIKASI_FUNGSIONAL_CHOICES,
    RAJAL_JANTUNG_STEPS, RENCANA_TINDAK_LANJUT_CHOICES, TERAPI_STATUS_CHOICES,
)

from .tests_poli_workflow import TEST_STORAGES, PoliFixture

STEP8 = RAJAL_JANTUNG_STEPS[8]


def catalogue_product(*, kode, generik_nama, kelas_kode, pregnancy_class='', user,
                      price='1500', routes=('PO',), unit='tablet'):
    """Produk katalog minimal yang lolos ``product_snapshot``."""
    kelas, _ = KelasTerapiObat.objects.get_or_create(
        kode=kelas_kode, defaults={'nama': kelas_kode.title()},
    )
    generic = GenerikObat.objects.create(
        kode=kode, nama=generik_nama, kelas=kelas, bentuk='TABLET',
        dispense_unit=unit, conversion={},
    )
    return ProdukFarmasi.objects.create(
        kode=kode, nama=f'{generik_nama} (uji)', generik=generic, kind='OBAT',
        active=True, source_version='FIXTURE-F5', reviewed_by=user, price=Decimal(price),
        allowed_routes=list(routes), pregnancy_class=pregnancy_class,
        pregnancy_contra=bool(pregnancy_class),
    )


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class Langkah8Fixture(PoliFixture):
    def save(self, step, fields, version=None, user=None):
        if version is None:
            from pasien.models import IgdAssessmentWorkflow

            workflow = IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).first()
            version = workflow.version if workflow else 0
        return save_step(self.visit.pk, user or self.dpjp_user, step, fields, version,
                         service_line='RAJAL_JANTUNG')

    def set_diagnosis(self, changes):
        from pasien.models import IgdAssessmentWorkflow

        workflow = IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).first()
        return perform_action(
            self.visit.pk, self.dpjp_user, 'diagnosis_set', {'changes': changes},
            workflow.version if workflow else 0, str(uuid.uuid4()),
            service_line='RAJAL_JANTUNG',
        )


class DiagnosisPrimerTest(Langkah8Fixture):
    """F5.1 — primer/sekunder lewat ``DiagnosisKunjungan`` yang sudah ada."""

    def test_second_primary_switch_leaves_exactly_one_active_primary(self):
        first = self.set_diagnosis([
            {'op': 'upsert', 'temp_id': 'a', 'mode': 'MANUAL', 'text': 'Angina stabil',
             'code': '', 'is_primary': True},
            {'op': 'upsert', 'temp_id': 'b', 'mode': 'MANUAL', 'text': 'Hipertensi',
             'code': '', 'is_primary': False},
        ])
        self.assertEqual(self.visit.diagnoses.filter(active=True, is_primary=True).count(), 1)

        rows = list(self.visit.diagnoses.filter(active=True).order_by('pk'))
        # Pergantian primer dikirim sebagai satu permintaan: turunkan yang lama
        # dan naikkan yang baru. Server menolak dua primer dalam satu keadaan.
        self.set_diagnosis([
            {'op': 'upsert', 'id': rows[0].pk, 'mode': 'MANUAL',
             'text': 'Angina stabil', 'code': '', 'is_primary': False},
            {'op': 'upsert', 'id': rows[1].pk, 'mode': 'MANUAL',
             'text': 'Hipertensi', 'code': '', 'is_primary': True},
        ])
        primaries = self.visit.diagnoses.filter(active=True, is_primary=True)
        self.assertEqual(primaries.count(), 1)
        self.assertEqual(primaries.get().nama, 'Hipertensi')
        self.assertEqual(first['diagnosis_ids'][0], rows[0].pk)

    def test_secondary_diagnosis_is_stored_and_primary_label_written(self):
        self.set_diagnosis([
            {'op': 'upsert', 'temp_id': 'p', 'mode': 'MANUAL', 'text': 'Gagal jantung',
             'code': '', 'is_primary': True},
            {'op': 'upsert', 'temp_id': 's', 'mode': 'MANUAL', 'text': 'DM tipe 2',
             'code': '', 'is_primary': False},
        ])
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnoses.filter(active=True).count(), 2)
        self.assertEqual(self.visit.diagnosa_masuk, 'Gagal jantung')

    def test_step8_ui_disables_primary_when_one_is_active(self):
        self.set_diagnosis([
            {'op': 'upsert', 'temp_id': 'p', 'mode': 'MANUAL', 'text': 'Gagal jantung',
             'code': '', 'is_primary': True},
        ])
        self.client.force_login(self.dpjp_user)
        body = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=8'
        ).content.decode()
        # UI tidak menawarkan dua primer sekaligus: ia menyatakan bahwa primer
        # lama akan diturunkan dalam satu penyimpanan.
        self.assertIn('data-poli-primary-id="', body)
        self.assertIn('akan diturunkan menjadi sekunder', body)


class KlasifikasiFungsionalTest(Langkah8Fixture):
    """F5.2 — NYHA/CCS, stratifikasi risiko, dan rencana tindak lanjut."""

    def test_matrix_options_are_stored_in_draft_payload(self):
        workflow = self.save(8, {
            'klasifikasi_fungsional': 'NYHA_III',
            'rencana_tindak_lanjut': 'RAJAL_KONTROL_POLI',
            'terapi_status': 'RESEP_RAJAL',
            'input_mode': 'MANUAL',
        })
        payload = workflow.draft_payload['8']
        self.assertEqual(payload['klasifikasi_fungsional'], 'NYHA_III')
        self.assertEqual(payload['rencana_tindak_lanjut'], 'RAJAL_KONTROL_POLI')
        self.assertEqual(payload['terapi_status'], 'RESEP_RAJAL')

    def test_every_matrix_option_is_accepted(self):
        for code in KLASIFIKASI_FUNGSIONAL_CHOICES:
            with self.subTest(code=code):
                workflow = self.save(8, {'klasifikasi_fungsional': code})
                self.assertEqual(workflow.draft_payload['8']['klasifikasi_fungsional'], code)
        for code in RENCANA_TINDAK_LANJUT_CHOICES + TERAPI_STATUS_CHOICES:
            with self.subTest(code=code):
                field = ('rencana_tindak_lanjut' if code in RENCANA_TINDAK_LANJUT_CHOICES
                         else 'terapi_status')
                workflow = self.save(8, {field: code})
                self.assertEqual(workflow.draft_payload['8'][field], code)

    def test_value_outside_matrix_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(8, {'klasifikasi_fungsional': 'NYHA_V'})
        self.assertIn('klasifikasi_fungsional', ctx.exception.errors)
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(8, {'rencana_tindak_lanjut': 'PULANG_SENDIRI'})
        self.assertIn('rencana_tindak_lanjut', ctx.exception.errors)

    def test_no_new_kunjungan_columns_are_written(self):
        before = {k: v for k, v in
                  self.visit.__class__.objects.values().get(pk=self.visit.pk).items()
                  if k in ('diagnosa_masuk', 'diagnosa_keluar', 'jenis_kunjungan')}
        self.save(8, {'klasifikasi_fungsional': 'CCS_II'})
        after = {k: v for k, v in
                 self.visit.__class__.objects.values().get(pk=self.visit.pk).items()
                 if k in before}
        self.assertEqual(before, after)


class ResepRajalRouteTest(Langkah8Fixture):
    """F5.3 — jalur resep RAJAL memakai ``RAWAT_JALAN``, IGD tetap IGD."""

    def setUp(self):
        self.workflow = self.save(1, {'penjamin': 'UMUM'})
        PharmacyServiceGrant.objects.get_or_create(user=self.pharmacist, unit=self.unit)
        self.product = catalogue_product(
            kode='KARD-F5-1', generik_nama='Captopril 25 mg',
            kelas_kode='kardiovaskular-antihipertensi', pregnancy_class='ACEI',
            user=self.dpjp_user,
        )
        self.visit.skrining_alergi_status = 'TIDAK_ADA'
        self.visit.save(update_fields=['skrining_alergi_status'])

    def _save_rx(self):
        return perform_action(
            self.visit.pk, self.dpjp_user, 'prescription_save',
            {
                'serving_unit_id': self.unit.pk,
                'lines': [{
                    'product_id': self.product.pk,
                    'kind': 'OBAT',
                    'regimen': {
                        'schema_version': 1, 'frequency': 'FIXED', 'times_per_day': '2',
                        'dose': '1', 'dose_unit': 'tablet', 'duration_days': '30',
                        'route': 'PO',
                    },
                }],
            },
            self.workflow_for(self.visit).version, str(uuid.uuid4()),
            service_line='RAJAL_JANTUNG',
        )

    def test_resep_buat_redirects_rajal_episode_to_poli_step8(self):
        self.client.force_login(self.dpjp_user)
        response = self.client.get(reverse('pasien:resep_buat', args=[self.visit.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=8',
        )

    def test_resep_buat_keeps_igd_episode_on_igd_workflow(self):
        from akreditasi.models import UnitKerja
        from pasien.models import KunjunganPasien

        igd_unit = UnitKerja.objects.get_or_create(
            code='IGD', defaults={'name': 'IGD', 'level': 2})[0]
        igd_visit = KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='QA-F5-IGD', jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(), unit_kerja=igd_unit,
        )
        # Dokter unit IGD: gerbang modul ``igd`` diuji terpisah dari perutean.
        igd_doctor = self._account('dokter_igd_f5', 'DOKTER_SPESIALIS', igd_unit)
        self.client.force_login(igd_doctor)
        response = self.client.get(reverse('pasien:resep_buat', args=[igd_visit.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('pasien:igd_workflow', args=[igd_visit.pk]) + '?step=8',
        )

    def test_rajal_prescription_is_rawat_jalan_and_submits(self):
        saved = self._save_rx()
        rx = ResepElektronik.objects.get(pk=saved['prescription_id'])
        self.assertEqual(rx.jenis_resep, 'RAWAT_JALAN')
        self.assertEqual(rx.status, 'DRAFT')

        submitted = perform_action(
            self.visit.pk, self.dpjp_user, 'prescription_submit',
            {'prescription_id': rx.pk, 'acknowledgements': []},
            self.workflow_for(self.visit).version, str(uuid.uuid4()),
            service_line='RAJAL_JANTUNG',
        )
        rx.refresh_from_db()
        self.assertEqual(rx.status, 'DIKIRIM')
        self.assertFalse(submitted['held'])

    def test_submit_without_serving_unit_reports_clear_error(self):
        saved = self._save_rx()
        rx = ResepElektronik.objects.get(pk=saved['prescription_id'])
        rx.serving_unit = None
        rx.save(update_fields=['serving_unit'])
        with self.assertRaises(ValueError) as ctx:
            perform_action(
                self.visit.pk, self.dpjp_user, 'prescription_submit',
                {'prescription_id': rx.pk, 'acknowledgements': []},
                self.workflow_for(self.visit).version, str(uuid.uuid4()),
                service_line='RAJAL_JANTUNG',
            )
        self.assertIn('Depo farmasi', str(ctx.exception))


class GdmtPanelTest(TestCase):
    """F5.4 — panel GDMT dibaca dari katalog, kelompok kosong dinyatakan."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User

        cls.user = User.objects.create_user('gdmt_author', password='fixture-only')

    def test_groups_come_from_the_master_list_not_a_local_copy(self):
        from klinis.expansion_models import PREGNANCY_CLASS_CODES

        self.assertEqual(GDMT_GROUPS, PREGNANCY_CLASS_CODES)
        self.assertEqual([item['code'] for item in gdmt_panel()], list(GDMT_GROUPS))

    def test_group_without_catalogue_product_is_empty_and_named(self):
        catalogue_product(
            kode='KARD-F5-ACEI', generik_nama='Captopril 25 mg',
            kelas_kode='kardiovaskular-antihipertensi', pregnancy_class='ACEI',
            user=self.user,
        )
        panel = {item['code']: item for item in gdmt_panel()}
        self.assertFalse(panel['ACEI']['empty'])
        self.assertEqual(panel['ACEI']['products'][0]['generik'], 'Captopril 25 mg')
        for code in ('ARB', 'ARNI', 'STATIN', 'WARFARIN'):
            self.assertTrue(panel[code]['empty'], code)
            self.assertEqual(panel[code]['empty_label'], 'Belum ada di formularium')
        self.assertEqual(sorted(empty_gdmt_groups()), ['ARB', 'ARNI', 'STATIN', 'WARFARIN'])

    def test_adjustment_options_are_the_four_matrix_values(self):
        self.assertEqual([item['value'] for item in adjustment_choices()],
                         list(GDMT_PENYESUAIAN_CHOICES))
        self.assertEqual(adjustment_note('TITRASI_NAIK'),
                         'GDMT: Titrasi Naik')
        self.assertEqual(adjustment_note('TITRASI_NAIK', 'sesak membaik'),
                         'GDMT: Titrasi Naik — sesak membaik')
        with self.assertRaises(ValueError):
            adjustment_note('NAIKKAN_DUA_KALI')


class GdmtShortcutTest(Langkah8Fixture):
    """F5.4 — pintasan mengisi baris draf yang sama, bukan baris ganda."""

    def setUp(self):
        self.workflow = self.save(1, {'penjamin': 'UMUM'})
        PharmacyServiceGrant.objects.get_or_create(user=self.pharmacist, unit=self.unit)
        self.visit.skrining_alergi_status = 'TIDAK_ADA'
        self.visit.save(update_fields=['skrining_alergi_status'])
        self.product = catalogue_product(
            kode='KARD-F5-ARB', generik_nama='Valsartan 80 mg',
            kelas_kode='kardiovaskular-antihipertensi', pregnancy_class='ARB',
            user=self.dpjp_user,
        )

    def _line(self, dose, instructions=None):
        regimen = {
            'schema_version': 1, 'frequency': 'FIXED', 'times_per_day': '1',
            'dose': dose, 'dose_unit': 'tablet', 'duration_days': '30', 'route': 'PO',
        }
        if instructions:
            regimen['instructions'] = instructions
        return {'product_id': self.product.pk, 'kind': 'OBAT', 'regimen': regimen}

    def _save(self, lines, key, prescription_id=None):
        fields = {'serving_unit_id': self.unit.pk, 'lines': lines}
        if prescription_id is not None:
            fields['prescription_id'] = prescription_id
        return perform_action(
            self.visit.pk, self.dpjp_user, 'prescription_save',
            fields,
            self.workflow_for(self.visit).version, key, service_line='RAJAL_JANTUNG',
        )

    def test_shortcut_then_manual_same_drug_keeps_one_line_and_updates_dose(self):
        first = self._save([self._line('1', adjustment_note('MULAI_DOSIS_RENDAH'))], str(uuid.uuid4()))
        rx_id = first['prescription_id']
        self.assertEqual(ResepDetail.objects.filter(resep_id=rx_id).count(), 1)

        # Kiriman berikutnya memuat baris yang sama dua kali (pintasan lalu
        # penambahan manual). Server menyatukannya; dosis terakhir menang.
        self._save(
            [self._line('1', adjustment_note('MULAI_DOSIS_RENDAH')), self._line('2')],
            str(uuid.uuid4()), prescription_id=rx_id,
        )
        rows = ResepDetail.objects.filter(resep_id=rx_id)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().dosis, '2')

    def test_adjustment_note_is_persisted_in_regimen(self):
        saved = self._save([self._line('1', adjustment_note('TITRASI_NAIK', 'TD 110/70'))], str(uuid.uuid4()))
        row = ResepDetail.objects.get(resep_id=saved['prescription_id'])
        self.assertEqual(row.regimen['instructions'], 'GDMT: Titrasi Naik — TD 110/70')

    def test_step8_renders_empty_group_state_and_no_invented_drug(self):
        self.client.force_login(self.dpjp_user)
        body = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=8'
        ).content.decode()
        self.assertEqual(body.count('Belum ada di formularium'), 4)
        self.assertIn('Valsartan 80 mg', body)
        # Label kelompok memang memuat nama kelas; yang tidak boleh ada adalah
        # produk yang tidak ada di katalog.
        for absent in ('Atorvastatin', 'Sacubitril', 'Simvastatin'):
            self.assertNotIn(absent, body)


class EdukasiDanSkdpTest(Langkah8Fixture):
    """F5.5/F5.6 — bukti edukasi PDF dan e-SKDP dari jadwal kontrol."""

    def setUp(self):
        self.workflow = self.save(1, {'penjamin': 'UMUM'})

    def test_education_options_are_the_four_matrix_values(self):
        self.assertEqual(EDUKASI_KARDIO_CHOICES, (
            'POLA_HIDUP_MEROKOK',
            'DIET_RENDAH_GARAM_LEMAK_CAIRAN',
            'KEPATUHAN_GDMT_EFEK_SAMPING',
            'TANDA_BAHAYA_IGD',
        ))
        workflow = self.save(8, {
            'edukasi': list(EDUKASI_KARDIO_CHOICES),
            'edukasi_penerima': 'Istri pasien',
            'input_mode': 'MASTER',
        })
        self.assertEqual(workflow.draft_payload['8']['edukasi'], list(EDUKASI_KARDIO_CHOICES))
        with self.assertRaises(WorkflowValidation):
            self.save(8, {'edukasi': ['EDUKASI_KARANGAN']})

    def test_pdf_proof_returns_application_pdf(self):
        self.save(8, {'edukasi': ['TANDA_BAHAYA_IGD'], 'edukasi_penerima': 'Istri pasien',
                      'input_mode': 'MANUAL'})
        self.client.force_login(self.dpjp_user)
        response = self.client.get(reverse('pasien:poli_edukasi_pdf', args=[self.visit.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_print_page_carries_checklist_signatory_and_timestamp(self):
        self.save(8, {'edukasi': ['POLA_HIDUP_MEROKOK', 'TANDA_BAHAYA_IGD'],
                      'edukasi_penerima': 'Istri pasien', 'input_mode': 'MANUAL'})
        self.client.force_login(self.dpjp_user)
        body = self.client.get(
            reverse('pasien:poli_edukasi_cetak', args=[self.visit.pk])
        ).content.decode()
        self.assertIn('Pola Hidup Sehat &amp; Berhenti Merokok', body)
        self.assertIn('Tanda Bahaya (Red Flags) Kapan Harus ke IGD', body)
        self.assertIn('Istri pasien', body)
        self.assertIn(self.dpjp_user.get_full_name() or self.dpjp_user.username, body)
        self.assertRegex(body, r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}')

    def test_saving_follow_up_interval_issues_skdp_number(self):
        workflow = self.save(8, {'jadwal_kontrol': 'H30', 'diagnosa_utama': 'Gagal jantung',
                                 'rencana_terapi': 'GDMT lanjut', 'input_mode': 'MANUAL'})
        record = DischargeRecord.objects.get(kunjungan=self.visit)
        self.assertEqual(record.skdp_nomor, skdp_nomor(self.visit))
        self.assertRegex(record.skdp_nomor, rf'^SKDP-\d{{8}}-{self.visit.pk:04d}$')
        self.assertEqual(record.jadwal_kontrol, timezone.localdate() + timezone.timedelta(days=30))
        self.assertEqual(record.skdp_diagnosa, 'Gagal jantung')
        self.assertEqual(record.skdp_terapi, 'GDMT lanjut')
        self.assertEqual(workflow.draft_payload['8']['jadwal_kontrol'], 'H30')

    def test_option_without_interval_issues_number_but_no_date(self):
        self.save(8, {'jadwal_kontrol': 'SESUAI_JADWAL_TINDAKAN'})
        record = DischargeRecord.objects.get(kunjungan=self.visit)
        self.assertTrue(record.skdp_nomor)
        self.assertIsNone(record.jadwal_kontrol)
        self.assertIsNone(jadwal_kontrol_tanggal('SESUAI_JADWAL_TINDAKAN'))

    def test_skdp_number_reuses_existing_dashboard_scheme(self):
        today = timezone.localdate().strftime('%Y%m%d')
        self.assertEqual(skdp_nomor(self.visit), f'SKDP-{today}-{self.visit.pk:04d}')
        self.assertEqual(
            set(JADWAL_KONTROL_CHOICES),
            {'H7', 'H14', 'H30', 'SESUAI_JADWAL_TINDAKAN'},
        )


class ToolbarMetodeInputTest(Langkah8Fixture):
    """F5.7 — toolbar Manual/Master/AI dengan provenance berbeda, AI tertutup."""

    def setUp(self):
        self.workflow = self.save(1, {'penjamin': 'UMUM'})

    def test_toolbar_is_shared_by_steps_8_and_9(self):
        self.client.force_login(self.dpjp_user)
        for step in (8, 9):
            with self.subTest(step=step):
                body = self.client.get(
                    reverse('pasien:poli_workflow', args=[self.visit.pk]) + f'?step={step}'
                ).content.decode()
                self.assertIn('data-poli-toolbar', body)
                self.assertIn('Manual', body)
                self.assertIn('Master', body)

    def test_ai_mode_is_disabled_not_faked(self):
        self.client.force_login(self.dpjp_user)
        body = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=8'
        ).content.decode()
        self.assertIn('Bantuan AI', body)
        self.assertIn('belum tersedia', body)
        self.assertNotIn('data-poli-mode="AI"', body)

    def test_ai_mode_is_rejected_when_saved(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(8, {'input_mode': 'AI'})
        self.assertIn('input_mode', ctx.exception.errors)
        self.assertIn('F9', ctx.exception.errors['input_mode'][0])

    def test_each_step_records_its_own_mode(self):
        self.assertEqual(list(INPUT_MODE_CHOICES), ['MANUAL', 'MASTER', 'AI'])
        workflow = self.save(8, {'input_mode': 'MANUAL'})
        self.assertEqual(workflow.draft_payload['8']['input_mode'], 'MANUAL')
        workflow = self.save(9, {'input_mode': 'MASTER', 'cppt_ringkas': 'Asuhan hari ini'})
        self.assertEqual(workflow.draft_payload['8']['input_mode'], 'MANUAL')
        self.assertEqual(workflow.draft_payload['9']['input_mode'], 'MASTER')

    def test_diagnosis_mode_column_still_drives_master_provenance(self):
        """Mode Master pada diagnosis tetap memakai kolom ``DiagnosisKunjungan.mode``."""
        from klinis.models import MasterIcd10

        MasterIcd10.objects.create(kode='I50.0', nama='Congestive heart failure')
        perform_action(
            self.visit.pk, self.dpjp_user, 'diagnosis_set',
            {'changes': [{'op': 'upsert', 'temp_id': 'm', 'mode': 'MASTER',
                          'code': 'I50.0', 'text': '', 'is_primary': True}]},
            self.workflow_for(self.visit).version, str(uuid.uuid4()),
            service_line='RAJAL_JANTUNG',
        )
        row = self.visit.diagnoses.get(active=True)
        self.assertEqual(row.mode, 'MASTER')
        self.assertEqual(row.kode, 'I50.0')
        self.assertEqual(row.provenance['mode'], 'MASTER')
