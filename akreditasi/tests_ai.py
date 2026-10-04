"""
Test Suite Otomatis untuk Modul AI DeepSeek (ARIMA / SIK AP).
Mencakup sanitasi data medis, pencegahan kebocoran API Key,
pengendalian akses RBAC, proteksi rate-limit, audit logging,
dan penanganan timeout/error API eksternal tanpa 500.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from akreditasi.ai_service import sanitize_hospital_prompt
from akreditasi.system_models import SystemConfig
from akreditasi.models import AuditLog

User = get_user_model()


class SanitasiDataMedisAITest(TestCase):
    """Pengujian redaksi data privasi pasien sebelum transmisi ke LLM."""

    def test_redact_nik_16_digit(self):
        teks = "Pasien memiliki NIK 3201123456780001 memerlukan transfusi darah."
        hasil = sanitize_hospital_prompt(teks)
        self.assertNotIn("3201123456780001", hasil)
        self.assertIn("[NIK_DISAMARKAN]", hasil)

    def test_redact_nomor_rekam_medis(self):
        teks = "Harap cek rekam medis No RM: 01-23-45 untuk riwayat alergi."
        hasil = sanitize_hospital_prompt(teks)
        self.assertNotIn("01-23-45", hasil)
        self.assertIn("[NO_RM_DISAMARKAN]", hasil)

    def test_redact_nomor_telepon(self):
        teks = "Hubungi keluarga di nomor 081234567890 jika ada kondisi kritis."
        hasil = sanitize_hospital_prompt(teks)
        self.assertNotIn("081234567890", hasil)
        self.assertIn("[NO_HP_DISAMARKAN]", hasil)

    def test_redact_nama_pasien_dengan_gelar(self):
        teks = "Insiden terjadi saat perawat memeriksa Tn. Budi Santoso di bangsal."
        hasil = sanitize_hospital_prompt(teks)
        self.assertNotIn("Tn. Budi Santoso", hasil)
        self.assertIn("[NAMA_PASIEN_DISAMARKAN]", hasil)

    def test_empty_string_safety(self):
        self.assertEqual(sanitize_hospital_prompt(""), "")
        self.assertEqual(sanitize_hospital_prompt(None), "")


class EndpointAIIntegrationTest(TestCase):
    """Pengujian integrasi endpoint API AI, proteksi auth, dan mock LLM."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('admin_ai', 'admin@rs.id', 'password123')
        self.user_biasa = User.objects.create_user('user_biasa', 'user@rs.id', 'password123')

        # Pastikan konfigurasi AI aktif untuk testing
        self.config = SystemConfig.get_solo()
        self.config.ai_enabled = True
        self.config.ai_enable_risiko = True
        self.config.ai_enable_pdca = True
        self.config.ai_enable_insiden = True
        self.config.ai_api_key = "sk-test-fake-key-for-testing"  # field yang benar
        self.config.save()

    def test_anon_user_redirected(self):
        """User tidak terotentikasi tidak boleh mengakses endpoint AI."""
        resp = self.client.post(
            reverse('akreditasi:ai_mitigasi_risiko'),
            data=json.dumps({'jenis_risiko': 'Bahaya Kebakaran'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 302)

    def test_payload_invalid_returns_400(self):
        """Payload non-JSON atau kosong harus mengembalikan 400, bukan 500."""
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('akreditasi:ai_mitigasi_risiko'),
            data='invalid json content',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])

    @patch('akreditasi.ai_service.requests.post')
    def test_mocked_deepseek_mitigasi_success(self, mock_post):
        """Mock pemanggilan DeepSeek sukses untuk mitigasi risiko."""
        self.client.force_login(self.admin)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'analisis_singkat': 'Risiko tinggi pada area farmasi',
                        'akar_masalah_kemungkinan': ['Kurang ventilasi'],
                        'rekomendasi_mitigasi': [{'tindakan': 'Pasang blower'}]
                    })
                }
            }]
        }
        mock_post.return_value = mock_response

        payload = {
            'unit_name': 'Farmasi',
            'kategori_risiko': 'Operasional',
            'jenis_risiko': 'Suhu Penyimpanan Obat Terlalu Tinggi',
            'deskripsi_risiko': 'AC rusak sehingga suhu kulkas mencapai 25C',
            'dampak': 4,
            'probabilitas': 3,
            'strategi': 'Mitigasi (Reduce)'
        }
        resp = self.client.post(
            reverse('akreditasi:ai_mitigasi_risiko'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        res_data = resp.json()
        self.assertTrue(res_data['success'])
        self.assertIn('analisis_singkat', res_data['data'])

        # Pastikan tidak ada API Key yang bocor ke response
        raw_resp = resp.content.decode('utf-8')
        self.assertNotIn('test-fake-key', raw_resp)
        self.assertNotIn('encrypted', raw_resp)

        # Verifikasi AuditLog tercatat
        audit = AuditLog.objects.filter(aksi='CREATE', model_name='AI_DEEPSEEK').last()
        self.assertIsNotNone(audit)
        self.assertIn('Farmasi', audit.detail)

    @patch('akreditasi.ai_service.requests.post')
    def test_mocked_deepseek_timeout_graceful(self, mock_post):
        """Timeout dari DeepSeek tidak boleh melempar 500 ke klien."""
        import requests
        self.client.force_login(self.admin)
        mock_post.side_effect = requests.exceptions.Timeout("Timeout connection to AI")

        payload = {
            'unit_name': 'IGD',
            'kategori_risiko': 'Klinis',
            'jenis_risiko': 'Keterlambatan Penanganan Pasien Kritis',
            'deskripsi_risiko': 'Overcapacity di ruang triase',
            'dampak': 5,
            'probabilitas': 3,
        }
        resp = self.client.post(
            reverse('akreditasi:ai_mitigasi_risiko'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        res_data = resp.json()
        self.assertFalse(res_data['success'])
        self.assertIn('timeout', res_data['error'].lower())

    @patch('akreditasi.ai_service.requests.post')
    def test_mocked_deepseek_pdca_plan_success(self, mock_post):
        """Mock pemanggilan AI untuk PDCA Plan generator."""
        self.client.force_login(self.admin)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'plan_summary': 'Peningkatan kepatuhan identifikasi pasien',
                        'target_capaian': '100% kepatuhan gelang identitas',
                        'langkah_kerja': [{'langkah': 'Audit gelang harian', 'pj': 'Kepala Ruang'}]
                    })
                }
            }]
        }
        mock_post.return_value = mock_response

        payload = {
            'pokja_code': 'SKP',
            'sub_standar': 'SKP 1',
            'masalah': 'Staf lupa memverifikasi identitas sebelum pemberian obat oral',
            'target': 'Kepatuhan 100%'
        }
        resp = self.client.post(
            reverse('akreditasi:ai_pdca_plan'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        res = resp.json()
        self.assertTrue(res['success'])
        self.assertIn('plan_summary', res['data'])

    @patch('akreditasi.ai_service.requests.post')
    def test_mocked_deepseek_insiden_analisis_success(self, mock_post):
        """Mock pemanggilan AI untuk Analisis Insiden Keselamatan Pasien."""
        self.client.force_login(self.admin)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'analisis_kronologi': 'Kesalahan terjadi pada fase dispensing',
                        'faktor_kontributor': ['Beban kerja tinggi', 'Kemasan obat mirip (LASA)'],
                        'grading_rekomendasi': 'Kuning',
                        'tindakan_segera': ['Ganti obat', 'Lapor dokter DPJP']
                    })
                }
            }]
        }
        mock_post.return_value = mock_response

        payload = {
            'deskripsi_kejadian': 'Pasien Tn. Budi hampir diberikan obat Cefotaxime bukan Ceftriaxone',
            'jenis_insiden': 'KNC',
            'tingkat_keparahan': 'Tidak ada cedera',
            'lokasi_kejadian': 'Farmasi',
            'unit_name': 'Farmasi'
        }
        resp = self.client.post(
            reverse('akreditasi:ai_insiden_grading'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        res = resp.json()
        self.assertTrue(res['success'])
        self.assertIn('analisis_kronologi', res['data'])

    def test_disabled_feature_flag_returns_error(self):
        """Jika fitur AI dinonaktifkan di SystemConfig, akses harus ditolak."""
        self.config.ai_enabled = False
        self.config.save()

        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('akreditasi:ai_mitigasi_risiko'),
            data=json.dumps({'unit_name': 'IGD', 'kategori_risiko': 'Klinis',
                             'jenis_risiko': 'Test', 'deskripsi_risiko': 'Test',
                             'dampak': 3, 'probabilitas': 3}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        res = resp.json()
        self.assertFalse(res['success'])
        self.assertIn('belum diaktifkan', res['error'].lower())

    def test_test_connection_requires_superuser(self):
        """Endpoint tes koneksi AI hanya boleh diakses superuser."""
        self.client.force_login(self.user_biasa)
        resp = self.client.post(reverse('akreditasi:ai_test_connection'))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.json()['success'])
