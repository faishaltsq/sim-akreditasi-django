"""Ambang hipertensi sebagai konfigurasi, bukan konstanta tersembunyi (ADR-14).

Yang dikunci di sini: mengubah konfigurasi mengubah kategori **tanpa**
menyentuh kode, sumber ambang ikut dinyatakan, dan ambang yang berangka pada
matriks (krisis ≥180/120, hipotensi <90) tidak ikut dapat dikonfigurasi.
"""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from pasien.clinical_thresholds import (
    DEFAULT_HT_DIASTOLE, DEFAULT_HT_SISTOLE, HT_THRESHOLD_ADR,
    SETTING_HT_DIASTOLE, SETTING_HT_SISTOLE,
    hipertensi_threshold_source, hipertensi_thresholds,
)
from pasien.models import (
    HIPOTENSI_SISTOLE, KRISIS_DIASTOLE, KRISIS_SISTOLE, map_kategori, ttv_alerts,
)

class ThresholdDefaultsTest(SimpleTestCase):
    """Tanpa konfigurasi, default operasional ADR-14 yang berlaku."""

    def test_defaults_are_the_operational_140_over_90(self):
        self.assertEqual(hipertensi_thresholds(), (140, 90))
        self.assertEqual((DEFAULT_HT_SISTOLE, DEFAULT_HT_DIASTOLE), (140, 90))

    def test_source_names_configuration_keys_adr_and_ratification_status(self):
        source = hipertensi_threshold_source()
        self.assertIn(SETTING_HT_SISTOLE, source)
        self.assertIn(SETTING_HT_DIASTOLE, source)
        self.assertIn('140/90', source)
        self.assertIn(HT_THRESHOLD_ADR, source)
        self.assertIn('belum diratifikasi Komite Medis', source)

class ThresholdConfigurationTest(SimpleTestCase):
    """Perubahan konfigurasi mengubah kategori; logika tidak disentuh."""

    @override_settings(CLINICAL_HT_SISTOLE=130, CLINICAL_HT_DIASTOLE=85)
    def test_stricter_configuration_promotes_a_previously_normal_reading(self):
        # 135/88 normal pada default 140/90, hipertensi pada 130/85.
        self.assertEqual(map_kategori(135, 88), 'HIPERTENSI')
        self.assertEqual(hipertensi_thresholds(), (130, 85))
        self.assertIn('130/85', hipertensi_threshold_source())

    @override_settings(CLINICAL_HT_SISTOLE=160, CLINICAL_HT_DIASTOLE=100)
    def test_looser_configuration_demotes_a_previously_hypertensive_reading(self):
        # 145/92 hipertensi pada default 140/90, normal pada 160/100.
        self.assertEqual(map_kategori(145, 92), 'NORMAL')
        self.assertEqual(map_kategori(160, 100), 'HIPERTENSI')

    @override_settings(CLINICAL_HT_SISTOLE=135, CLINICAL_HT_DIASTOLE=88)
    def test_configuration_alone_changes_the_alert_set(self):
        # Alert KRISIS_HIPERTENSI tetap dipicu ambang sumber; kategori berubah.
        codes = [alert['code'] for alert in ttv_alerts(sistole=138, diastole=86)]
        self.assertNotIn('KRISIS_HIPERTENSI', codes)

    def test_default_configuration_keeps_documented_categories(self):
        self.assertEqual(map_kategori(118, 74), 'NORMAL')
        self.assertEqual(map_kategori(139, 89), 'NORMAL')
        self.assertEqual(map_kategori(140, 89), 'HIPERTENSI')
        self.assertEqual(map_kategori(120, 90), 'HIPERTENSI')

class SourcedThresholdsStayLiteralTest(SimpleTestCase):
    """Krisis dan hipotensi berangka pada matriks — tidak konfigurabel."""

    def test_crisis_and_hypotension_constants_are_the_matrix_values(self):
        self.assertEqual((KRISIS_SISTOLE, KRISIS_DIASTOLE), (180, 120))
        self.assertEqual(HIPOTENSI_SISTOLE, 90)

    @override_settings(CLINICAL_HT_SISTOLE=100, CLINICAL_HT_DIASTOLE=60)
    def test_loosened_hypertension_configuration_cannot_move_crisis_or_hypotension(self):
        self.assertEqual(map_kategori(180, 120), 'KRISIS')
        self.assertEqual(map_kategori(200, 130), 'KRISIS')
        self.assertEqual(map_kategori(85, 55), 'HIPOTENSI')

    @override_settings(CLINICAL_HT_SISTOLE=250, CLINICAL_HT_DIASTOLE=150)
    def test_raised_hypertension_configuration_cannot_hide_crisis(self):
        self.assertEqual(map_kategori(185, 125), 'KRISIS')

class InvalidConfigurationTest(SimpleTestCase):
    """Konfigurasi rusak ditolak jelas, bukan diam-diam memakai default."""

    @override_settings(CLINICAL_HT_SISTOLE='abc')
    def test_non_integer_setting_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            hipertensi_thresholds()

    @override_settings(CLINICAL_HT_DIASTOLE=0)
    def test_non_positive_setting_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            hipertensi_thresholds()
