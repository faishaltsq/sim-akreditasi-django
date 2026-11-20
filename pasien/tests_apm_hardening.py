"""Phase 10 & 11 tests — rate limit, masking, idle timeout, indikator mutu."""
import datetime
import json
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import (
    KunjunganPasien, LogBiometrik, LogRisikoApm, Pasien, RujukanBpjs, WhatsAppLog,
)
from pasien.services.indikator import hitung_indikator
from pasien.services.throttle import cek


class AdminRegistrationTest(TestCase):
    def test_semua_model_apm_terdaftar_di_admin(self):
        from django.contrib import admin

        from pasien.models import (
            AntreanBpjsTaskLog, JadwalDokterPoli, KonfigurasiApm, KonfigurasiBiometrikPoli,
            LogBiometrik, LogRisikoApm, RujukanBpjs, WhatsAppLog,
        )

        for model in (
            JadwalDokterPoli, RujukanBpjs, KonfigurasiApm, KonfigurasiBiometrikPoli,
            LogBiometrik, LogRisikoApm, WhatsAppLog, AntreanBpjsTaskLog,
        ):
            self.assertIn(model, admin.site._registry, f'{model.__name__} belum terdaftar di admin')

    def test_jadwal_dokter_bisa_diubah_dari_admin(self):
        from django.contrib import admin

        from pasien.models import JadwalDokterPoli

        model_admin = admin.site._registry[JadwalDokterPoli]
        self.assertIn('kode_poli_bpjs', model_admin.list_display)
        self.assertIn('kode_dokter_bpjs', model_admin.list_display)


class ThrottleTest(TestCase):
    def test_batas_terlampaui(self):
        for _ in range(3):
            self.assertTrue(cek('uji', 'kunci', limit=3, window_detik=60))
        self.assertFalse(cek('uji', 'kunci', limit=3, window_detik=60))

    def test_kunci_berbeda_tidak_saling_mempengaruhi(self):
        cek('uji', 'a', limit=1, window_detik=60)
        self.assertFalse(cek('uji', 'a', limit=1, window_detik=60))
        self.assertTrue(cek('uji', 'b', limit=1, window_detik=60))

    def test_endpoint_publik_mengembalikan_429(self):
        url = reverse('pasien:mandiri_verifikasi')
        status = []
        for _ in range(6):
            response = self.client.post(url, {
                'identitas': '0000000000001', 'tanggal_lahir': '01/01/1990', 'no_wa': '081200000000',
            })
            status.append(response.status_code)
        self.assertIn(429, status)
        self.assertEqual(status[-1], 429)


class MaskingTest(TestCase):
    def test_rujukan_validasi_menyamarkan_nama(self):
        from unittest.mock import patch

        pasien = Pasien.objects.create(
            no_rm='RM-MASK-001', nama_lengkap='Budi Hartono',
            tanggal_lahir=datetime.date(1990, 1, 1), jenis_kelamin='L',
            no_hp='081200000001', no_bpjs='0001234567890',
        )
        data = {
            'mode': 'LIVE', 'ditemukan': True, 'no_rujukan': '0123456789012345678',
            'jenis_rujukan': 'FKTP', 'tgl_rujukan': timezone.localdate(),
            'ppk_rujukan': '0401B001', 'ppk_tujuan': '0123R001', 'diagnosa_awal': 'I10',
        }
        with patch('pasien.services.bpjs_vclaim.validasi_rujukan', return_value=data):
            response = self.client.post(reverse('pasien:apm_api_rujukan_validasi'), {
                'identitas': '0001234567890', 'nama_lengkap': 'Budi Hartono',
                'tanggal_lahir': '01/01/1990', 'no_rujukan': '0123456789012345678',
            }, content_type='application/json')
        body = response.json()
        self.assertTrue(body['success'], body)
        self.assertNotIn('Hartono', json.dumps(body))
        self.assertIn('Bud', body['pasien']['nama_lengkap'])

    def test_helper_masking(self):
        from pasien.services.masking import mask_nik, mask_no_bpjs

        self.assertEqual(mask_nik('3201234567890123'), '3201********0123')
        self.assertEqual(mask_no_bpjs('0001234567890'), '*********7890')


class IdleTimeoutTest(TestCase):
    def test_kiosk_memuat_idle_dan_endpoint_reset(self):
        html = self.client.get(reverse('pasien:apm_kiosk')).content.decode()
        self.assertIn('IDLE_DETIK', html)
        self.assertIn('/pasien/apm/api/sesi/reset/', html)
        self.assertIn('resetIdle', html)


class IndikatorTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-IND-001', nama_lengkap='Pasien Indikator',
            tanggal_lahir=datetime.date(1990, 1, 1), jenis_kelamin='L', no_hp='081200000002',
        )
        mulai = timezone.now() - datetime.timedelta(seconds=90)
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-IND-001', jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(), poliklinik='IGD', dpjp='Dokter Jaga IGD',
            is_apm=True, sep_mode='LIVE', no_sep='SEP-IND-1',
            registrasi_mulai_at=mulai, registrasi_selesai_at=mulai + datetime.timedelta(seconds=90),
        )
        LogBiometrik.objects.create(kunjungan=self.kunjungan, percobaan_ke=1, hasil='VALID')
        LogBiometrik.objects.create(kunjungan=self.kunjungan, percobaan_ke=2, hasil='GAGAL')
        LogRisikoApm.objects.create(
            kode_risiko='RSK-APM-02', kanal='KIOSK', pemicu='RUJUKAN_KEDALUWARSA',
            kunjungan=self.kunjungan,
        )
        WhatsAppLog.objects.create(nomor_tujuan='6281200000002', jenis_pesan='CHECKIN_SEP', pesan='x', status='SENT')

    def test_menghitung_durasi_dan_kepatuhan(self):
        data = hitung_indikator(timezone.localdate().year, timezone.localdate().month)
        self.assertEqual(data['kunjungan']['total'], 1)
        self.assertEqual(data['kunjungan']['igd'], 1)
        self.assertEqual(data['registrasi']['igd']['median_detik'], 90.0)
        self.assertEqual(data['biometrik']['VALID'], 1)
        self.assertEqual(data['biometrik']['kepatuhan_persen'], 50.0)
        self.assertEqual(data['sep']['live'], 1)
        self.assertEqual(data['rujukan_blokir']['RUJUKAN_KEDALUWARSA'], 1)
        self.assertEqual(data['whatsapp']['CHECKIN_SEP:SENT'], 1)

    def test_command_menghasilkan_json(self):
        out = StringIO()
        call_command('apm_indikator', stdout=out)
        data = json.loads(out.getvalue())
        self.assertIn('registrasi', data)
        self.assertIn('biometrik', data)

    def test_view_staf_memerlukan_login(self):
        url = reverse('pasien:apm_indikator')
        self.assertEqual(self.client.get(url).status_code, 302)
        User.objects.create_user('mutu', password='x')
        self.client.login(username='mutu', password='x')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])