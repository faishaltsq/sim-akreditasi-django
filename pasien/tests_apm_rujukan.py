"""Phase 1 data-foundation tests for APM-BPJS multi-channel (plan 2026-11-19).

Covers: RujukanBpjs rules, KunjunganPasien APM fields, dynamic configuration,
append-only risk/biometric logs, and the BPJS code mapping on doctor schedules.
"""
import datetime
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from pasien.models import (
    JadwalDokterPoli,
    KonfigurasiApm,
    KonfigurasiBiometrikPoli,
    KunjunganPasien,
    LogBiometrik,
    LogRisikoApm,
    Pasien,
    RujukanBpjs,
    WhatsAppLog,
)

PPK_RS = '0123R001'


def buat_pasien(suffix='001'):
    return Pasien.objects.create(
        no_rm=f'RM-APM-{suffix}',
        nama_lengkap=f'Pasien Uji {suffix}',
        tanggal_lahir=datetime.date(1990, 5, 15),
        jenis_kelamin='L',
        no_hp='08123456789',
    )


def buat_kunjungan(pasien, suffix='001', **kwargs):
    data = dict(
        pasien=pasien,
        no_kunjungan=f'REG-APM-{suffix}',
        jenis_kunjungan='RAJAL',
        tanggal_masuk=timezone.now(),
        poliklinik='POLI_JANTUNG',
        dpjp='dr. Faisal, Sp.JP',
        is_apm=True,
    )
    data.update(kwargs)
    return KunjunganPasien.objects.create(**data)


class RujukanBpjsTest(TestCase):
    def setUp(self):
        self.pasien = buat_pasien('R01')

    def rujukan(self, **kwargs):
        data = dict(
            pasien=self.pasien,
            no_rujukan='0123456789012345678',
            jenis_rujukan='FKTP',
            tgl_rujukan=datetime.date(2026, 8, 1),
            tgl_kunjungan_rencana=datetime.date(2026, 11, 1),
            ppk_rujukan='0401B001',
            nama_ppk_rujukan='Puskesmas Uji',
            ppk_tujuan=PPK_RS,
            diagnosa_awal='I10',
            nama_diagnosa_awal='Hipertensi esensial',
        )
        data.update(kwargs)
        return RujukanBpjs.objects.create(**data)

    def test_masa_berlaku_dihitung_dari_tanggal_kunjungan(self):
        r = self.rujukan()
        harapan = (datetime.date(2026, 11, 1) - datetime.date(2026, 8, 1)).days
        self.assertEqual(r.masa_berlaku_hari(), harapan)
        self.assertGreater(harapan, 90)
        self.assertEqual(r.status_dari_aturan(ppk_rs=PPK_RS), 'KEDALUWARSA')

    def test_batas_90_hari_masih_valid(self):
        r = self.rujukan(tgl_kunjungan_rencana=datetime.date(2026, 10, 30))
        self.assertEqual(r.masa_berlaku_hari(), 90)
        self.assertEqual(r.status_dari_aturan(ppk_rs=PPK_RS), 'VALID')

    def test_hari_ke_91_kedaluwarsa(self):
        r = self.rujukan(tgl_kunjungan_rencana=datetime.date(2026, 10, 31))
        self.assertEqual(r.masa_berlaku_hari(), 91)
        self.assertEqual(r.status_dari_aturan(ppk_rs=PPK_RS), 'KEDALUWARSA')

    def test_beda_ppk_menang_atas_kedaluwarsa(self):
        r = self.rujukan(tgl_kunjungan_rencana=datetime.date(2027, 1, 1))
        self.assertEqual(r.status_dari_aturan(ppk_rs='9999R999'), 'BEDA_PPK')

    def test_perbandingan_ppk_tidak_peka_huruf_besar(self):
        r = self.rujukan(tgl_kunjungan_rencana=datetime.date(2026, 10, 1))
        self.assertEqual(r.masa_berlaku_hari(), 61)
        self.assertEqual(r.status_dari_aturan(ppk_rs='0123r001'), 'VALID')

    def test_tidak_ditemukan_menang_atas_semua(self):
        r = self.rujukan(ditemukan_di_vclaim=False, tgl_kunjungan_rencana=datetime.date(2027, 1, 1))
        self.assertEqual(r.status_dari_aturan(ppk_rs='9999R999', peserta_aktif=False), 'TIDAK_DITEMUKAN')

    def test_peserta_tidak_aktif_menang_atas_beda_ppk(self):
        r = self.rujukan()
        self.assertEqual(r.status_dari_aturan(ppk_rs='9999R999', peserta_aktif=False), 'TIDAK_AKTIF')

    def test_tanggal_rujukan_kosong_tidak_pernah_dianggap_valid(self):
        r = self.rujukan(tgl_rujukan=None)
        self.assertIsNone(r.masa_berlaku_hari())
        self.assertEqual(r.status_dari_aturan(ppk_rs=PPK_RS), 'KEDALUWARSA')

    def test_no_rujukan_unik(self):
        self.rujukan()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.rujukan(pasien=buat_pasien('R02'))


class KunjunganApmFieldsTest(TestCase):
    def setUp(self):
        self.pasien = buat_pasien('K01')

    def test_tanggal_kunjungan_mengikuti_tanggal_masuk(self):
        k = buat_kunjungan(self.pasien, 'K01')
        self.assertEqual(k.tanggal_kunjungan, timezone.localtime(k.tanggal_masuk).date())

    def test_tanggal_kunjungan_tidak_ditimpa_saat_sudah_diisi(self):
        target = datetime.date(2026, 12, 1)
        k = buat_kunjungan(self.pasien, 'K02', tanggal_kunjungan=target)
        k.catatan_admisi = 'ubah'
        k.save()
        k.refresh_from_db()
        self.assertEqual(k.tanggal_kunjungan, target)

    def test_sep_mode_default_belum(self):
        k = buat_kunjungan(self.pasien, 'K03')
        self.assertEqual(k.sep_mode, 'BELUM')
        self.assertEqual(k.no_sep, '')
        self.assertEqual(k.estimasi_versi, 0)
        self.assertEqual(k.delta_geser_menit, 0)
        self.assertEqual(k.biometrik_status, 'TIDAK_WAJIB')

    def test_no_sep_tidak_boleh_ganda(self):
        buat_kunjungan(self.pasien, 'K04', no_sep='SEP-UNIK-001', sep_mode='LIVE')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                buat_kunjungan(buat_pasien('K05'), 'K05', no_sep='SEP-UNIK-001', sep_mode='LIVE')

    def test_no_sep_kosong_boleh_berulang(self):
        buat_kunjungan(self.pasien, 'K06')
        buat_kunjungan(self.pasien, 'K07')
        self.assertEqual(KunjunganPasien.objects.filter(no_sep='').count(), 2)

    def test_kunjungan_bisa_merujuk_rujukan(self):
        r = RujukanBpjs.objects.create(
            pasien=self.pasien,
            no_rujukan='0123456789012345699',
            tgl_rujukan=datetime.date(2026, 11, 1),
            ppk_tujuan=PPK_RS,
        )
        k = buat_kunjungan(self.pasien, 'K08', rujukan=r)
        self.assertEqual(k.rujukan_id, r.id)
        self.assertIn(k, r.kunjungan.all())


class KonfigurasiApmTest(TestCase):
    def test_get_solo_selalu_mengembalikan_satu_baris(self):
        pertama = KonfigurasiApm.get_solo()
        kedua = KonfigurasiApm.get_solo()
        self.assertEqual(pertama.pk, kedua.pk)
        self.assertEqual(KonfigurasiApm.objects.count(), 1)

    def test_default_sesuai_prd(self):
        k = KonfigurasiApm.get_solo()
        self.assertEqual(k.buffer_tiba_menit, 30)
        self.assertEqual(k.ambang_geser_notif_menit, 15)
        self.assertEqual(k.idle_timeout_detik, 90)
        self.assertEqual(k.biometrik_maks_percobaan, 3)
        self.assertEqual(k.t_buka_rs, datetime.time(7, 0))
        self.assertEqual(k.wa_retry_maks, 3)
        self.assertEqual(k.wa_provider, 'FONNTE')

    def test_idle_timeout_di_luar_60_sampai_90_ditolak(self):
        k = KonfigurasiApm.get_solo()
        for nilai in (30, 59, 91, 300):
            k.idle_timeout_detik = nilai
            with self.assertRaises(ValidationError):
                k.full_clean()

    def test_idle_timeout_dalam_rentang_diterima(self):
        k = KonfigurasiApm.get_solo()
        for nilai in (60, 75, 90):
            k.idle_timeout_detik = nilai
            k.full_clean()


class KonfigurasiBiometrikPoliTest(TestCase):
    def test_default_wajib_dan_aktif(self):
        konf = KonfigurasiBiometrikPoli.objects.create(poliklinik='POLI_THT')
        self.assertTrue(konf.wajib_biometrik)
        self.assertTrue(konf.aktif)

    def test_poliklinik_unik(self):
        KonfigurasiBiometrikPoli.objects.create(poliklinik='POLI_MATA')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                KonfigurasiBiometrikPoli.objects.create(poliklinik='POLI_MATA')

    def test_pengecualian_usia(self):
        konf = KonfigurasiBiometrikPoli.objects.create(
            poliklinik='POLI_JANTUNG',
            usia_min_pengecualian=17,
            usia_max_pengecualian=70,
        )
        self.assertTrue(konf.is_exempt(usia=10))
        self.assertTrue(konf.is_exempt(usia=75))
        self.assertFalse(konf.is_exempt(usia=40))

    def test_pengecualian_status_peserta(self):
        konf = KonfigurasiBiometrikPoli.objects.create(
            poliklinik='REHAB_MEDIK',
            pengecualian_status_peserta=['PBI APBN'],
        )
        self.assertTrue(konf.is_exempt(status_peserta='pbi apbn'))
        self.assertFalse(konf.is_exempt(status_peserta='PPU'))

    def test_poli_tidak_aktif_tidak_mewajibkan(self):
        konf = KonfigurasiBiometrikPoli.objects.create(poliklinik='POLI_GIGI', aktif=False)
        self.assertFalse(konf.mewajibkan(usia=40))


class LogAppendOnlyTest(TestCase):
    def setUp(self):
        self.pasien = buat_pasien('L01')
        self.kunjungan = buat_kunjungan(self.pasien, 'L01')

    def test_kode_risiko_valid(self):
        log = LogRisikoApm(kode_risiko='RSK-APM-01', kanal='KIOSK', pemicu='IGD_FASTTRACK')
        log.full_clean()
        log.save()
        self.assertEqual(log.kode_risiko, 'RSK-APM-01')

    def test_kode_risiko_tidak_dikenal_ditolak(self):
        log = LogRisikoApm(kode_risiko='RSK-APM-99', kanal='KIOSK', pemicu='X')
        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_log_risiko_append_only(self):
        log = LogRisikoApm.objects.create(
            kode_risiko='RSK-APM-02', kanal='MOBILE', pemicu='RUJUKAN_KEDALUWARSA',
            kunjungan=self.kunjungan,
        )
        log.pemicu = 'DIUBAH'
        with self.assertRaises(ValidationError):
            log.save()

    def test_log_biometrik_append_only(self):
        log = LogBiometrik.objects.create(
            kunjungan=self.kunjungan, percobaan_ke=1, metode='FINGERPRINT', hasil='GAGAL',
        )
        self.assertEqual(log.mode, 'SIMULASI')
        log.hasil = 'VALID'
        with self.assertRaises(ValidationError):
            log.save()

    def test_log_risiko_terurut_terbaru(self):
        lama = LogRisikoApm.objects.create(kode_risiko='RSK-APM-03', kanal='KIOSK', pemicu='A')
        baru = LogRisikoApm.objects.create(kode_risiko='RSK-APM-04', kanal='KIOSK', pemicu='B')
        self.assertEqual(list(LogRisikoApm.objects.all()), [baru, lama])


class JadwalDokterMappingTest(TestCase):
    def test_kode_bpjs_kosong_secara_default(self):
        j = JadwalDokterPoli.objects.create(
            hari_praktik='Setiap hari',
            nama_dokter='dr. Uji', poliklinik='POLI_JANTUNG',
            jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 0),
        )
        self.assertEqual(j.kode_poli_bpjs, '')
        self.assertIsNone(j.kode_dokter_bpjs)
        self.assertFalse(j.siap_bridging_bpjs)

    def test_jam_praktek_format_bpjs(self):
        j = JadwalDokterPoli.objects.create(
            hari_praktik='Setiap hari',
            nama_dokter='dr. Uji', poliklinik='POLI_JANTUNG',
            jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 30),
            kode_poli_bpjs='JTG', kode_dokter_bpjs=12345,
        )
        self.assertEqual(j.jam_praktek_bpjs, '08:00-12:30')
        self.assertTrue(j.siap_bridging_bpjs)


class SeedKonfigurasiApmCommandTest(TestCase):
    def test_seed_idempoten_dan_tidak_menimpa_tanpa_force(self):
        call_command('seed_konfigurasi_apm', stdout=StringIO())
        self.assertEqual(KonfigurasiApm.objects.count(), 1)
        self.assertEqual(KonfigurasiBiometrikPoli.objects.count(), 4)

        KonfigurasiBiometrikPoli.objects.filter(poliklinik='POLI_THT').update(wajib_biometrik=False)
        call_command('seed_konfigurasi_apm', stdout=StringIO())
        self.assertFalse(
            KonfigurasiBiometrikPoli.objects.get(poliklinik='POLI_THT').wajib_biometrik,
            'Seed tanpa --force tidak boleh menimpa perubahan admin.',
        )

        call_command('seed_konfigurasi_apm', '--force', stdout=StringIO())
        self.assertTrue(KonfigurasiBiometrikPoli.objects.get(poliklinik='POLI_THT').wajib_biometrik)
        self.assertEqual(KonfigurasiApm.objects.count(), 1)
        self.assertEqual(KonfigurasiBiometrikPoli.objects.count(), 4)


class WhatsAppLogIdempotencyTest(TestCase):
    def test_idempotency_key_unik(self):
        WhatsAppLog.objects.create(
            nomor_tujuan='628123456789', jenis_pesan='TIKET_APM',
            pesan='x', idempotency_key='k-1',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WhatsAppLog.objects.create(
                    nomor_tujuan='628123456789', jenis_pesan='TIKET_APM',
                    pesan='x', idempotency_key='k-1',
                )

    def test_tanpa_idempotency_key_boleh_berulang(self):
        WhatsAppLog.objects.create(nomor_tujuan='628123456789', jenis_pesan='TIKET_APM', pesan='a')
        WhatsAppLog.objects.create(nomor_tujuan='628123456789', jenis_pesan='TIKET_APM', pesan='b')
        self.assertEqual(WhatsAppLog.objects.filter(idempotency_key=None).count(), 2)

    def test_jenis_pesan_baru_tersedia(self):
        for jenis in ('KONFIRMASI_BOOKING', 'CHECKIN_SEP', 'PERGESERAN_JADWAL', 'ESKALASI_BIOMETRIK'):
            log = WhatsAppLog(nomor_tujuan='628123456789', jenis_pesan=jenis, pesan='x')
            log.full_clean()