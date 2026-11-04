from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from django.urls import reverse
from pasien.bridging_services import BPJSVClaimService, SatuSehatService
from pasien.models import (
    DPJP_CHOICES, DPJP_POLI_MAP, POLIKLINIK_CHOICES,
    JadwalDinusAdmission, LogbookHarianAdmission, Pasien, KunjunganPasien,
)


class DPJPPoliMapTest(TestCase):
    def test_every_dpjp_mapped_to_at_least_one_poli(self):
        mapped = {dpjp for dpjps in DPJP_POLI_MAP.values() for dpjp in dpjps}
        for val, _label in DPJP_CHOICES:
            self.assertIn(val, mapped, f'{val} tidak ter-map ke poliklinik manapun')

    def test_map_contains_only_known_dpjp_and_poli(self):
        dpjp_vals = {val for val, _ in DPJP_CHOICES}
        poli_vals = {val for val, _ in POLIKLINIK_CHOICES}
        for poli, dpjps in DPJP_POLI_MAP.items():
            self.assertIn(poli, poli_vals)
            for dpjp in dpjps:
                self.assertIn(dpjp, dpjp_vals)

    def test_every_poli_has_at_least_one_dpjp(self):
        for poli, _label in POLIKLINIK_CHOICES:
            self.assertIn(poli, DPJP_POLI_MAP, f'{poli} tidak punya DPJP')
            self.assertTrue(DPJP_POLI_MAP[poli])


class AdmissionShiftLogbookModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas_loket', password='password123')

    def test_create_jadwal_dinus_defaults(self):
        j = JadwalDinusAdmission.objects.create(petugas=self.user, tanggal=date(2026, 11, 4), shift='PAGI')
        self.assertEqual(j.status_kehadiran, 'HADIR')
        self.assertEqual(str(j), f'{self.user.username} — 2026-11-04 Pagi (07:00 - 14:00)')

    def test_create_logbook_defaults(self):
        log = LogbookHarianAdmission.objects.create(
            petugas=self.user, kegiatan='Verifikasi berkas 12 pasien BPJS')
        self.assertEqual(log.tanggal, timezone.localdate())
        self.assertIsNotNone(log.jam_aktivitas)
        self.assertIn('Verifikasi berkas', str(log))


class BridgingServiceTest(TestCase):
    def test_vclaim_valid_nik_returns_simulated_payload(self):
        p = BPJSVClaimService.cek_peserta_by_nik('3201234567890001')
        self.assertEqual(p['nik'], '3201234567890001')
        self.assertIn(p['sex'], ('L', 'P'))
        self.assertEqual(p['statusPeserta'], 'AKTIF')
        date.fromisoformat(p['tglLahir'])  # raises if not ISO
        self.assertTrue(p['noKartu'])

    def test_vclaim_invalid_nik_raises(self):
        with self.assertRaises(ValueError):
            BPJSVClaimService.cek_peserta_by_nik('12345')
        with self.assertRaises(ValueError):
            BPJSVClaimService.cek_peserta_by_nik('32012345678900AB')

    def test_satusehat_patient_shape(self):
        p = SatuSehatService.get_patient_by_nik('3201234567890001')
        self.assertEqual(p['resourceType'], 'Patient')
        self.assertIn(p['gender'], ('male', 'female'))
        self.assertEqual(p['identifier'][0]['system'], 'https://fhir.kemkes.go.id/id/nik')
        self.assertEqual(p['identifier'][0]['value'], '3201234567890001')


class ApiBridgingPesertaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas_bridging', password='password123')
        self.client.login(username='petugas_bridging', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-BRIDGE-001', nik='3201000000000009', nama_lengkap='Siti Nurhaliza',
            tanggal_lahir='1988-02-02', jenis_kelamin='P', no_bpjs='0001234567890')

    def test_local_pasien_wins(self):
        res = self.client.get(reverse('pasien:api_bridging_peserta') + '?nik=3201000000000009')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['source'], 'LOKAL')
        self.assertEqual(data['peserta']['nama'], 'Siti Nurhaliza')
        self.assertEqual(data['peserta']['sex'], 'P')

    def test_unknown_nik_falls_back_to_vclaim_simulation(self):
        res = self.client.get(reverse('pasien:api_bridging_peserta') + '?nik=3209998887770001')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['source'], 'BPJS_VCLAIM')
        self.assertIn('tglLahir', data['peserta'])

    def test_missing_nik_returns_400(self):
        res = self.client.get(reverse('pasien:api_bridging_peserta'))
        self.assertEqual(res.status_code, 400)

    def test_short_nik_returns_400(self):
        res = self.client.get(reverse('pasien:api_bridging_peserta') + '?nik=123')
        self.assertEqual(res.status_code, 400)


class PendaftaranTtvAntreanTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='loket_ttv', password='password123')
        self.client.login(username='loket_ttv', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-TTV-001', nik='3201000000000011', nama_lengkap='Budi Harjanto',
            tanggal_lahir='1980-01-01', jenis_kelamin='L')
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='RAJAL', no_kunjungan='RAJAL-TTV-001',
            poliklinik='POLI_JANTUNG', dpjp='dr. Faisal, Sp.JP', penjamin='BPJS',
            tanggal_masuk=timezone.now())

    def test_ttv_saved_and_redirects_to_dashboard(self):
        res = self.client.post(reverse('pasien:pendaftaran_ttv_simpan', args=[self.kunjungan.pk]), {
            'ttv_sistole': '120', 'ttv_diastole': '80', 'ttv_nadi': '78',
            'ttv_rr': '18', 'ttv_suhu': '36.5', 'ttv_spo2': '98',
            'catatan_admisi': 'Keluhan nyeri dada sejak pagi',
        })
        self.assertRedirects(res, reverse('pasien:pendaftaran_dashboard'))
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.ttv_sistole, 120)
        self.assertEqual(self.kunjungan.ttv_diastole, 80)
        self.assertEqual(self.kunjungan.ttv_nadi, 78)
        self.assertEqual(self.kunjungan.ttv_rr, 18)
        self.assertEqual(float(self.kunjungan.ttv_suhu), 36.5)
        self.assertEqual(self.kunjungan.ttv_spo2, 98)
        self.assertEqual(self.kunjungan.catatan_admisi, 'Keluhan nyeri dada sejak pagi')

    def test_ttv_empty_values_become_null_not_error(self):
        res = self.client.post(reverse('pasien:pendaftaran_ttv_simpan', args=[self.kunjungan.pk]), {
            'ttv_sistole': '', 'ttv_diastole': '', 'ttv_nadi': '',
            'ttv_rr': '', 'ttv_suhu': '', 'ttv_spo2': '',
        })
        self.assertEqual(res.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertIsNone(self.kunjungan.ttv_sistole)

    def test_antrean_panggil_updates_status(self):
        res = self.client.post(reverse('pasien:pendaftaran_antrean_status', args=[self.kunjungan.pk]),
                               {'status_antrean': 'DIPANGGIL'})
        self.assertRedirects(res, reverse('pasien:pendaftaran_dashboard'))
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status_antrean, 'DIPANGGIL')

    def test_antrean_selesai_updates_status(self):
        res = self.client.post(reverse('pasien:pendaftaran_antrean_status', args=[self.kunjungan.pk]),
                               {'status_antrean': 'SELESAI'})
        self.assertEqual(res.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status_antrean, 'SELESAI')

    def test_antrean_invalid_status_ignored(self):
        res = self.client.post(reverse('pasien:pendaftaran_antrean_status', args=[self.kunjungan.pk]),
                               {'status_antrean': 'HANCUR'})
        self.assertEqual(res.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status_antrean, 'MENUNGGU')

    def test_ttv_get_not_allowed(self):
        res = self.client.get(reverse('pasien:pendaftaran_ttv_simpan', args=[self.kunjungan.pk]))
        self.assertEqual(res.status_code, 405)
