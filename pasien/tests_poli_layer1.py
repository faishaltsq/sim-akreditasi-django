"""Langkah 1–6 Lapis 1 POLI-JANTUNG, nilai turunan, dan red flag (F2).

Tiga lapisan diuji terpisah karena gagalnya berbeda arti:

* fungsi murni (IMT, MAP, alert TTV) diuji di batas ambang, tanpa fixture;
* sinkronisasi kolom ``red_flag_*`` diuji lewat ``save_step`` (jalur layanan);
* tampilan dan badge door-to-ECG diuji lewat HTTP pada route asesmen.

Tidak ada tes yang hanya memeriksa keberadaan simbol.
"""
import datetime
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from pasien.forms_igd_workflow import morse_score, mst_score
from pasien.models import (
    IgdAssessmentWorkflow, KunjunganPasien, OrderPenunjang, Pasien,
    hitung_imt, hitung_map, imt_kategori, map_kategori, ttv_alerts,
)
from pasien.services.igd_assessment_workflow import save_step
from pasien.workflow_schemas import RAJAL_JANTUNG_STEPS

from .tests_poli_workflow import TEST_STORAGES, PoliFixture

class ImtTest(TestCase):
    """F2.2: IMT + kategori Asia-Pasifik."""

    def test_plan_example_58kg_160cm_is_normal(self):
        self.assertEqual(hitung_imt(58, 160), 22.66)
        self.assertEqual(imt_kategori(22.66), 'NORMAL')

    def test_plan_example_70kg_160cm_is_obesitas_one(self):
        self.assertEqual(hitung_imt(70, 160), 27.34)
        self.assertEqual(imt_kategori(27.34), 'OBESITAS_I')

    def test_asia_pacific_band_edges(self):
        cases = [
            (18.49, 'UNDERWEIGHT'), (18.5, 'NORMAL'), (22.9, 'NORMAL'),
            (23.0, 'OVERWEIGHT'), (24.9, 'OVERWEIGHT'), (25.0, 'OBESITAS_I'),
            (29.9, 'OBESITAS_I'), (30.0, 'OBESITAS_II'),
        ]
        for imt, expected in cases:
            self.assertEqual(imt_kategori(imt), expected, f'IMT {imt}')

    def test_missing_or_zero_measurements_yield_none(self):
        self.assertIsNone(hitung_imt(None, 160))
        self.assertIsNone(hitung_imt(58, None))
        self.assertIsNone(hitung_imt(58, 0))  # tidak boleh ZeroDivisionError
        self.assertEqual(imt_kategori(None), '')

class MapTest(TestCase):
    """F2.3: MAP = (S + 2D)/3 + kategori."""

    def test_formula(self):
        self.assertEqual(hitung_map(118, 74), 88.7)

    def test_categories_at_declared_edges(self):
        self.assertEqual(map_kategori(185, 125), 'KRISIS')
        self.assertEqual(map_kategori(180, 80), 'KRISIS')     # sistole >= 180
        self.assertEqual(map_kategori(150, 120), 'KRISIS')    # diastole >= 120
        self.assertEqual(map_kategori(85, 55), 'HIPOTENSI')
        self.assertEqual(map_kategori(89, 60), 'HIPOTENSI')
        self.assertEqual(map_kategori(90, 60), 'NORMAL')      # batas bawah normal
        self.assertEqual(map_kategori(118, 74), 'NORMAL')
        self.assertEqual(map_kategori(140, 90), 'HIPERTENSI')
        self.assertEqual(map_kategori(159, 99), 'HIPERTENSI')

    def test_missing_measurement_yields_no_category(self):
        self.assertIsNone(hitung_map(None, 74))
        self.assertEqual(map_kategori(None, 74), '')

class TtvAlertsTest(TestCase):
    """F2.4: ambang tepi, bukan hanya nilai tengah."""

    def codes(self, **kwargs):
        return [alert['code'] for alert in ttv_alerts(**kwargs)]

    def test_tachycardia_boundary_100_is_normal_101_alerts(self):
        self.assertNotIn('TAKIKARDIA', self.codes(nadi=100))
        self.assertIn('TAKIKARDIA', self.codes(nadi=101))

    def test_bradycardia_boundary_50_is_normal_49_alerts(self):
        self.assertNotIn('BRADIKARDIA', self.codes(nadi=50))
        self.assertIn('BRADIKARDIA', self.codes(nadi=49))

    def test_hypoxia_boundary_92_is_normal_91_alerts(self):
        self.assertNotIn('HIPOKSIA', self.codes(spo2=92))
        self.assertIn('HIPOKSIA', self.codes(spo2=91))

    def test_no_alert_for_respiratory_rate_or_temperature(self):
        # Sumber tidak menetapkan ambang RR/suhu (S4-L1-04, S4-L1-06).
        alerts = ttv_alerts(nadi=80, spo2=98)
        self.assertEqual(alerts, [])

    def test_crisis_beats_hypotension_and_hypertension(self):
        self.assertIn('KRISIS_HIPERTENSI', self.codes(sistole=185, diastole=125))
        self.assertNotIn('HIPERTENSI', self.codes(sistole=185, diastole=125))
        self.assertIn('HIPOTENSI', self.codes(sistole=85, diastole=55))
        self.assertNotIn('HIPERTENSI', self.codes(sistole=150, diastole=95))

    def test_pain_alert_at_nrs_four(self):
        self.assertNotIn('NYERI', self.codes(skala_nyeri=3))
        self.assertIn('NYERI', self.codes(skala_nyeri=4))

class ScreeningReuseTest(TestCase):
    """F2.7: Morse/MST memakai tabel dan ambang yang sudah ada."""

    def test_morse_45_is_high_and_25_is_medium(self):
        self.assertEqual(morse_score({'jatuh_riwayat': 25, 'jatuh_diagnosis': 15,
                                      'jatuh_alat': 0, 'jatuh_infus': 0,
                                      'jatuh_jalan': 0, 'jatuh_mental': 5}), (45, 'TINGGI'))
        self.assertEqual(morse_score({'jatuh_riwayat': 25, 'jatuh_diagnosis': 0,
                                      'jatuh_alat': 0, 'jatuh_infus': 0,
                                      'jatuh_jalan': 0, 'jatuh_mental': 0}), (25, 'SEDANG'))

    def test_morse_incomplete_answers_yield_none(self):
        self.assertEqual(morse_score({'jatuh_riwayat': 25}), (None, ''))
        self.assertEqual(morse_score(None), (None, ''))

    def test_mst_three_is_at_risk_and_zero_is_not(self):
        self.assertEqual(mst_score({'berat_badan': 2, 'nafsu_makan': 1}), (3, True))
        self.assertEqual(mst_score({'berat_badan': 0, 'nafsu_makan': 0}), (0, False))
        self.assertEqual(mst_score({'berat_badan': 1, 'nafsu_makan': 0}), (1, False))
        self.assertEqual(mst_score({'berat_badan': 1, 'nafsu_makan': 1}), (2, True))

    def test_mst_threshold_matches_existing_templates(self):
        # Tiga template lama memakai >= 2; konstanta modul harus sama.
        from pasien.forms_igd_workflow import MST_BERISIKO_MIN
        self.assertEqual(MST_BERISIKO_MIN, 2)

    def test_mst_incomplete_answers_yield_none(self):
        self.assertEqual(mst_score({'berat_badan': 2}), (None, None))
        self.assertEqual(mst_score(None), (None, None))

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class LayerOneSchemaTest(PoliFixture):
    """F2.1: field Lapis 1 tersimpan di draft_payload, bukan kolom baru."""

    def save(self, step, fields, version):
        return save_step(self.visit.pk, self.nurse, step, fields, version,
                         service_line='RAJAL_JANTUNG')

    def test_step_one_stores_referral_fields_in_payload(self):
        workflow = self.save(1, {'penjamin': 'BPJS', 'jenis_kunjungan_klinis': 'BARU',
                                 'asal_rujukan': 'FKTP', 'status_rujukan': 'AKTIF_TERVERIFIKASI'}, 0)
        self.assertEqual(workflow.draft_payload['1']['asal_rujukan'], 'FKTP')
        self.assertEqual(workflow.draft_payload['1']['status_rujukan'], 'AKTIF_TERVERIFIKASI')

    def test_step_one_rejects_code_outside_matrix_options(self):
        from pasien.services.igd_assessment_workflow import WorkflowValidation
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(1, {'asal_rujukan': 'GOOGLE'}, 0)
        self.assertIn('asal_rujukan', ctx.exception.errors)

    def test_step_three_and_six_store_cardiology_fields(self):
        workflow = self.save(3, {'keluhan_utama_kardio': 'NYERI_DADA',
                                 'nyeri_karakteristik_kardio': 'TERTEKAN',
                                 'nyeri_penjalaran': 'LENGAN_KIRI'}, 0)
        workflow = self.save(6, {'iktus_kordis': 'BERGESER',
                                 'bunyi_jantung': 'REGULER_MURMUR',
                                 'bunyi_napas': 'RONKI_BASAL'}, workflow.version)
        self.assertEqual(workflow.draft_payload['3']['nyeri_penjalaran'], 'LENGAN_KIRI')
        self.assertEqual(workflow.draft_payload['6']['bunyi_jantung'], 'REGULER_MURMUR')

    def test_body_measurements_stay_in_payload_and_feed_imt(self):
        workflow = self.save(4, {'ttv_sistole': 118, 'ttv_diastole': 74,
                                 'berat_badan': 70, 'tinggi_badan': 160}, 0)
        self.assertEqual(workflow.draft_payload['4']['berat_badan'], 70)
        self.assertFalse(hasattr(KunjunganPasien, 'berat_badan'))
        self.assertEqual(hitung_imt(70, 160), 27.34)

    def test_only_red_flag_columns_exist_beyond_payload(self):
        new_columns = {'red_flag_kardio', 'red_flag_at'}
        for name in ('asal_rujukan', 'status_rujukan', 'mobilitas_datang', 'alur_awal',
                     'keluhan_utama_kardio', 'nyeri_karakteristik_kardio', 'nyeri_penjalaran',
                     'irama_nadi', 'berat_badan', 'tinggi_badan', 'status_fungsional',
                     'dukungan_sosial', 'iktus_kordis', 'bunyi_jantung', 'bunyi_napas'):
            self.assertNotIn(name, new_columns)
            self.assertFalse(
                any(f.name == name for f in KunjunganPasien._meta.get_fields()),
                f'{name} seharusnya tinggal di draft_payload',
            )

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class RedFlagSyncTest(PoliFixture):
    """F2.5: red flag menulis kolom nyata; alur awal tetap di payload."""

    def save_step_two(self, fields, version=0):
        return save_step(self.visit.pk, self.nurse, 2, fields, version,
                         service_line='RAJAL_JANTUNG')

    def test_angina_sets_code_and_timestamp(self):
        self.save_step_two({'red_flag_kardio': 'ANGINA', 'alur_awal': 'RUJUK_IGD_CITO'})
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.red_flag_kardio, 'ANGINA')
        self.assertIsNotNone(self.visit.red_flag_at)

    def test_non_trigger_red_flag_sets_code_without_timestamp(self):
        self.save_step_two({'red_flag_kardio': 'SINKOP'})
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.red_flag_kardio, 'SINKOP')
        self.assertIsNone(self.visit.red_flag_at)

    def test_changing_to_non_trigger_clears_timestamp(self):
        workflow = self.save_step_two({'red_flag_kardio': 'ANGINA'})
        self.visit.refresh_from_db()
        self.assertIsNotNone(self.visit.red_flag_at)
        self.save_step_two({'red_flag_kardio': 'SINKOP'}, workflow.version)
        self.visit.refresh_from_db()
        self.assertIsNone(self.visit.red_flag_at)

    def test_resaving_trigger_does_not_move_the_clock(self):
        workflow = self.save_step_two({'red_flag_kardio': 'SESAK_BERAT'})
        self.visit.refresh_from_db()
        first = self.visit.red_flag_at
        self.save_step_two({'red_flag_kardio': 'SESAK_BERAT'}, workflow.version)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.red_flag_at, first)

    def test_clearing_red_flag_clears_columns(self):
        workflow = self.save_step_two({'red_flag_kardio': 'ANGINA'})
        self.save_step_two({'red_flag_kardio': ''}, workflow.version)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.red_flag_kardio, '')
        self.assertIsNone(self.visit.red_flag_at)

    def test_alur_awal_is_read_from_payload_not_a_column(self):
        workflow = self.save_step_two({'alur_awal': 'LANJUT_POLI'})
        self.assertEqual(workflow.draft_payload['2']['alur_awal'], 'LANJUT_POLI')
        self.assertFalse(any(f.name == 'alur_awal' for f in KunjunganPasien._meta.get_fields()))

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class DoorToEcgTest(PoliFixture):
    """F2.6: PATUH <= 10 menit, TERLAMBAT selebihnya."""

    def order_ekg(self, minutes_after):
        # ``created_at`` memakai ``auto_now_add``: nilai eksplisit saat create
        # diabaikan Django, jadi jam order digeser lewat ``update()`` — persis
        # seperti order nyata yang tercatat pada jam kedatangan.
        order = OrderPenunjang.objects.create(
            kunjungan=self.visit, jenis='EKG', nama_pemeriksaan='EKG 12-lead')
        base = self.visit.red_flag_at or timezone.now()
        OrderPenunjang.objects.filter(pk=order.pk).update(
            created_at=base + datetime.timedelta(minutes=minutes_after))
        order.refresh_from_db()
        return order

    def set_red_flag(self):
        self.visit.red_flag_kardio = 'ANGINA'
        self.visit.red_flag_at = timezone.now()
        self.visit.save(update_fields=['red_flag_kardio', 'red_flag_at'])

    def test_seven_minutes_is_patuh(self):
        self.set_red_flag()
        self.order_ekg(7)
        indicator = self.visit.door_to_ecg_indicator()
        self.assertEqual(indicator['status'], 'PATUH')
        self.assertAlmostEqual(indicator['minutes'], 7, places=1)

    def test_fourteen_minutes_is_terlambat(self):
        self.set_red_flag()
        self.order_ekg(14)
        self.assertEqual(self.visit.door_to_ecg_indicator()['status'], 'TERLAMBAT')

    def test_ten_minutes_exactly_is_patuh(self):
        self.set_red_flag()
        self.order_ekg(10)
        self.assertEqual(self.visit.door_to_ecg_indicator()['status'], 'PATUH')

    def test_no_red_flag_means_no_indicator(self):
        self.order_ekg(3)
        self.assertIsNone(self.visit.door_to_ecg_indicator())

    def test_red_flag_without_order_is_belum(self):
        self.set_red_flag()
        self.assertEqual(self.visit.door_to_ecg_indicator()['status'], 'BELUM')

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class LayerOneHttpTest(PoliFixture):
    """Tampilan: banner merah, badge, dan nilai turunan dirender lewat HTTP."""

    def setUp(self):
        self.client.force_login(self.nurse)

    def get_step(self, step):
        return self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + f'?step={step}')

    def test_select_options_render_labels_not_codes(self):
        body = self.get_step(1).content.decode()
        self.assertIn('value="FKTP"', body)
        self.assertIn('FKTP / Puskesmas', body)
        self.assertIn('value="AKTIF_TERVERIFIKASI"', body)

    def test_red_flag_renders_banner_and_transfer_button(self):
        save_step(self.visit.pk, self.nurse, 2, {'red_flag_kardio': 'ANGINA'}, 0,
                  service_line='RAJAL_JANTUNG')
        body = self.get_step(2).content.decode()
        self.assertIn('Red flag:', body)
        self.assertIn('Nyeri Dada Khas Angina (Suspek SKA)', body)
        self.assertIn(reverse('pasien:igd_dashboard'), body)
        self.assertIn('EKG belum diorder', body)

    def test_door_to_ecg_badge_is_patuh_when_order_is_within_ten_minutes(self):
        save_step(self.visit.pk, self.nurse, 2, {'red_flag_kardio': 'ANGINA'}, 0,
                  service_line='RAJAL_JANTUNG')
        self.visit.refresh_from_db()
        order = OrderPenunjang.objects.create(
            kunjungan=self.visit, jenis='EKG', nama_pemeriksaan='EKG 12-lead')
        OrderPenunjang.objects.filter(pk=order.pk).update(
            created_at=self.visit.red_flag_at + datetime.timedelta(minutes=7))
        body = self.get_step(2).content.decode()
        self.assertIn('EKG PATUH', body)

    def test_door_to_ecg_badge_is_terlambat_after_ten_minutes(self):
        save_step(self.visit.pk, self.nurse, 2, {'red_flag_kardio': 'SESAK_BERAT'}, 0,
                  service_line='RAJAL_JANTUNG')
        self.visit.refresh_from_db()
        order = OrderPenunjang.objects.create(
            kunjungan=self.visit, jenis='EKG', nama_pemeriksaan='EKG 12-lead')
        OrderPenunjang.objects.filter(pk=order.pk).update(
            created_at=self.visit.red_flag_at + datetime.timedelta(minutes=14))
        self.assertIn('EKG TERLAMBAT', self.get_step(2).content.decode())

    def test_step_four_panel_shows_map_imt_and_alerts(self):
        save_step(self.visit.pk, self.nurse, 4, {
            'ttv_sistole': 185, 'ttv_diastole': 125, 'ttv_nadi': 101,
            'ttv_spo2': 91, 'berat_badan': 70, 'tinggi_badan': 160,
        }, 0, service_line='RAJAL_JANTUNG')
        body = self.get_step(4).content.decode()
        self.assertIn('145,0 mmHg', body)          # (185 + 2*125)/3
        self.assertIn('KRISIS', body)
        self.assertIn('27,34 kg/m²', body)
        self.assertIn('OBESITAS_I', body)
        self.assertIn('Takikardia', body)
        self.assertIn('Hipoksia', body)

    def test_step_five_panel_shows_screening_grades(self):
        save_step(self.visit.pk, self.nurse, 5, {
            'skrining_jatuh_skor': 45, 'skrining_gizi_mst': 3,
        }, 0, service_line='RAJAL_JANTUNG')
        body = self.get_step(5).content.decode()
        self.assertIn('TINGGI', body)
        self.assertIn('Risiko Malnutrisi', body)
        self.assertIn('Skor 3', body)

    def test_no_alert_for_normal_vitals(self):
        save_step(self.visit.pk, self.nurse, 4, {
            'ttv_sistole': 118, 'ttv_diastole': 74, 'ttv_nadi': 88, 'ttv_spo2': 98,
        }, 0, service_line='RAJAL_JANTUNG')
        body = self.get_step(4).content.decode()
        self.assertIn('88,7 mmHg', body)
        self.assertNotIn('Takikardia', body)
        self.assertNotIn('Hipoksia', body)
