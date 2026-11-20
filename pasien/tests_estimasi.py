"""Phase 5 tests — mesin estimasi waktu pemeriksaan (BL-05)."""
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import (
    JadwalDokterPoli, KonfigurasiApm, KunjunganPasien, Pasien, WhatsAppLog,
)
from pasien.services.estimasi import (
    EstimasiError, EstimasiOverflow, estimasi_kunjungan, hitung_estimasi,
    recompute_for_schedule,
)


def waktu(jam, menit=0):
    return datetime.time(jam, menit)


class HitungEstimasiTest(TestCase):
    def test_contoh_prd(self):
        hasil = hitung_estimasi(t_mulai=waktu(8), n=5, d_rata=10, t_buka_rs=waktu(7))
        self.assertEqual(hasil.t_periksa, waktu(8, 40))
        self.assertEqual(hasil.t_tiba, waktu(8, 10))
        self.assertFalse(hasil.tiba_di_clamp)

    def test_clamp_ke_jam_buka_rs(self):
        hasil = hitung_estimasi(t_mulai=waktu(8), n=1, d_rata=10, t_buka_rs=waktu(7, 45))
        self.assertEqual(hasil.t_periksa, waktu(8, 0))
        self.assertEqual(hasil.t_tiba, waktu(7, 45))
        self.assertTrue(hasil.tiba_di_clamp)

    def test_tepat_di_jam_buka_tidak_dianggap_clamp(self):
        hasil = hitung_estimasi(t_mulai=waktu(8), n=1, d_rata=10, t_buka_rs=waktu(7, 30))
        self.assertEqual(hasil.t_tiba, waktu(7, 30))
        self.assertFalse(hasil.tiba_di_clamp)

    def test_tanpa_clamp_bila_jam_buka_lebih_awal(self):
        hasil = hitung_estimasi(t_mulai=waktu(8), n=1, d_rata=10, t_buka_rs=waktu(6, 0))
        self.assertEqual(hasil.t_tiba, waktu(7, 30))
        self.assertFalse(hasil.tiba_di_clamp)

    def test_delta_geser_positif(self):
        hasil = hitung_estimasi(t_mulai=waktu(8), n=3, d_rata=10, delta_geser=15, t_buka_rs=waktu(7))
        self.assertEqual(hasil.t_periksa, waktu(8, 35))
        self.assertEqual(hasil.delta_geser_menit, 15)

    def test_delta_geser_negatif(self):
        hasil = hitung_estimasi(t_mulai=waktu(8), n=5, d_rata=10, delta_geser=-15, t_buka_rs=waktu(7))
        self.assertEqual(hasil.t_periksa, waktu(8, 25))

    def test_melewati_batas_hari_ditolak(self):
        with self.assertRaises(EstimasiOverflow):
            hitung_estimasi(t_mulai=waktu(23, 50), n=5, d_rata=10, t_buka_rs=waktu(7))

    def test_parameter_tidak_valid(self):
        for kwargs in (
            dict(t_mulai=waktu(8), n=0, d_rata=10),
            dict(t_mulai=waktu(8), n=1, d_rata=0),
            dict(t_mulai=waktu(8), n=1, d_rata=10, delta_geser=1.5),
            dict(t_mulai='08:00', n=1, d_rata=10),
        ):
            with self.assertRaises(EstimasiError):
                hitung_estimasi(**kwargs)

    def test_as_dict(self):
        data = hitung_estimasi(t_mulai=waktu(8), n=2, d_rata=10, t_buka_rs=waktu(7)).as_dict()
        self.assertEqual(data['t_periksa'], '08:10')
        self.assertEqual(data['t_tiba'], '07:40')


class ModelDelegationTest(TestCase):
    def test_model_memakai_service_yang_sama(self):
        jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Uji', poliklinik='POLI_JANTUNG',
            jam_mulai=waktu(8), jam_selesai=waktu(12), durasi_per_pasien_menit=15,
        )
        self.assertEqual(
            jadwal.hitung_estimasi_jam(5),
            hitung_estimasi(t_mulai=waktu(8), n=5, d_rata=15).t_periksa,
        )
        self.assertEqual(jadwal.hitung_estimasi_jam(2, delta_geser_menit=30), waktu(8, 45))


class RecomputeTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-EST-001', nama_lengkap='Pasien Estimasi',
            tanggal_lahir=datetime.date(1990, 5, 15), jenis_kelamin='L',
            no_hp='081200001111',
        )
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP', poliklinik='POLI_JANTUNG',
            jam_mulai=waktu(8), jam_selesai=waktu(12), durasi_per_pasien_menit=10,
            kode_poli_bpjs='JTG', kode_dokter_bpjs=12345,
        )
        self.tanggal = timezone.localdate()
        self.kunjungan = [
            self.buat_kunjungan(f'EST-{index}', estimasi=waktu(8, (index - 1) * 10))
            for index in (1, 2, 3)
        ]

    def buat_kunjungan(self, suffix, estimasi=None, status='MENUNGGU'):
        return KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan=f'REG-{suffix}', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP', nomor_antrean=f'JTG-00{suffix[-1]}',
            kode_booking=f'APM-{suffix}', is_apm=True,
            estimasi_pelayanan=estimasi, status_antrean=status,
        )

    def test_menghitung_ulang_semua_yang_menunggu(self):
        perubahan = recompute_for_schedule(self.jadwal, self.tanggal, 20)
        self.assertEqual(len(perubahan), 3)
        for item in self.kunjungan:
            item.refresh_from_db()
            self.assertEqual(item.delta_geser_menit, 20)
            self.assertEqual(item.estimasi_versi, 1)
        self.assertEqual(self.kunjungan[0].estimasi_pelayanan, waktu(8, 20))
        self.assertEqual(self.kunjungan[2].estimasi_pelayanan, waktu(8, 40))

    def test_pasien_sudah_dipanggil_tidak_dihitung_ulang(self):
        self.kunjungan[0].status_antrean = 'DIPANGGIL'
        self.kunjungan[0].save(update_fields=['status_antrean'])
        recompute_for_schedule(self.jadwal, self.tanggal, 20)
        self.kunjungan[0].refresh_from_db()
        self.assertEqual(self.kunjungan[0].estimasi_pelayanan, waktu(8, 0))
        self.assertEqual(self.kunjungan[0].estimasi_versi, 0)

    def test_ambang_notifikasi_14_menit_tidak_mengirim(self):
        dikirim = []
        recompute_for_schedule(
            self.jadwal, self.tanggal, 14,
            notifier=lambda *args: dikirim.append(args) or True,
        )
        self.assertEqual(dikirim, [])

    def test_ambang_notifikasi_15_menit_mengirim_per_pasien(self):
        dikirim = []
        recompute_for_schedule(
            self.jadwal, self.tanggal, 15,
            notifier=lambda *args: dikirim.append(args) or True,
        )
        self.assertEqual(len(dikirim), 3)

    def test_perhitungan_ulang_delta_sama_idempoten(self):
        recompute_for_schedule(self.jadwal, self.tanggal, 20)
        dikirim = []
        perubahan = recompute_for_schedule(
            self.jadwal, self.tanggal, 20,
            notifier=lambda *args: dikirim.append(args) or True,
        )
        self.assertEqual(dikirim, [])
        self.assertTrue(all(item['notifikasi'] is False for item in perubahan))
        for item in self.kunjungan:
            item.refresh_from_db()
            self.assertEqual(item.estimasi_versi, 1)

    def test_kunjungan_batal_diabaikan(self):
        self.kunjungan[1].status = 'BATAL'
        self.kunjungan[1].save(update_fields=['status'])
        perubahan = recompute_for_schedule(self.jadwal, self.tanggal, 20)
        self.assertEqual(len(perubahan), 2)


class EstimasiKunjunganTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-EST-002', nama_lengkap='Pasien Kedua',
            tanggal_lahir=datetime.date(1985, 1, 1), jenis_kelamin='P', no_hp='081200002222',
        )
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Indah, Sp.P', poliklinik='POLI_PARU',
            jam_mulai=waktu(9), jam_selesai=waktu(13), durasi_per_pasien_menit=15,
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-EST-010', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), poliklinik='POLI_PARU', dpjp='dr. Indah, Sp.P',
            nomor_antrean='PRU-001', kode_booking='APM-EST-010', is_apm=True,
        )

    def test_posisi_antrean_dihitung_dari_urutan_kunjungan(self):
        estimasi = estimasi_kunjungan(self.kunjungan)
        self.assertEqual(estimasi.nomor_antrean, 1)
        self.assertEqual(estimasi.t_periksa, waktu(9, 0))
        self.assertEqual(estimasi.t_tiba, waktu(8, 30))

    def test_clamp_jam_buka_rs_dari_konfigurasi(self):
        konf = KonfigurasiApm.get_solo()
        konf.t_buka_rs = waktu(8, 45)
        konf.save()
        estimasi = estimasi_kunjungan(self.kunjungan)
        self.assertEqual(estimasi.t_tiba, waktu(8, 45))
        self.assertTrue(estimasi.tiba_di_clamp)


class CheckinTerlambatTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-EST-003', nama_lengkap='Pasien Telat',
            tanggal_lahir=datetime.date(1980, 2, 2), jenis_kelamin='L', no_hp='081200003333',
        )
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP', poliklinik='POLI_JANTUNG',
            jam_mulai=waktu(8), jam_selesai=waktu(12), durasi_per_pasien_menit=10,
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-EST-020', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), poliklinik='POLI_JANTUNG', dpjp='dr. Faisal, Sp.JP',
            nomor_antrean='JTG-020', kode_booking='APM-EST-020', is_apm=True,
            estimasi_pelayanan=(timezone.localtime() - datetime.timedelta(minutes=45)).time(),
        )

    def test_checkin_terlambat_menghitung_ulang_dan_mengabari(self):
        response = self.client.post(reverse('pasien:apm_api_checkin'), {
            'kode': 'APM-EST-020',
            'nama_lengkap': 'Pasien Telat',
            'tanggal_lahir': '1980-02-02',
        })
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['terlambat'])
        self.assertIsNotNone(data['estimasi_baru'])
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.estimasi_versi, 1)
        self.assertTrue(WhatsAppLog.objects.filter(jenis_pesan='PERGESERAN_JADWAL').exists())

    def test_checkin_tepat_waktu_tidak_dihitung_ulang(self):
        self.kunjungan.estimasi_pelayanan = (timezone.localtime() + datetime.timedelta(hours=1)).time()
        self.kunjungan.save(update_fields=['estimasi_pelayanan'])
        response = self.client.post(reverse('pasien:apm_api_checkin'), {
            'kode': 'APM-EST-020',
            'nama_lengkap': 'Pasien Telat',
            'tanggal_lahir': '1980-02-02',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['terlambat'])
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.estimasi_versi, 0)