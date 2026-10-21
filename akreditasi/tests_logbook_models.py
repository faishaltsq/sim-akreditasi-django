"""Test model & helper Logbook Harian IGD / Rawat Inap."""

from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from akreditasi.logbook_models import (
    CHECKLIST_IGD, CHECKLIST_RANAP, LogbookChecklist, LogbookHarian,
    LogbookKejadian, LogbookPasien, dependency_kode, kunjungan_shift,
    los_menit, parse_jam, response_time_menit, shift_window,
)
from akreditasi.models import UnitKerja
from pasien.models import Bed, KunjunganPasien, Pasien, Ruangan

TANGGAL = date(2026, 10, 20)


def buat_unit(kode, nama, tipe='RUANGAN', parent=None):
    return UnitKerja.objects.create(code=kode, name=nama, level=2 if parent else 1,
                                    tipe_unit=tipe, parent=parent)


def buat_user(username, role, unit):
    u = User.objects.create_user(username=username, password='x')
    u.profile.role = role
    u.profile.unit_kerja = unit
    u.profile.save()
    return u


def buat_pasien(no_rm, nama='Pasien Uji', lahir=date(1980, 1, 1)):
    return Pasien.objects.create(no_rm=no_rm, nama_lengkap=nama,
                                 tanggal_lahir=lahir, jenis_kelamin='L')


def buat_kunjungan(pasien, jenis='IGD', masuk=None, keluar=None, **extra):
    return KunjunganPasien.objects.create(
        pasien=pasien,
        no_kunjungan=f'KJ-{pasien.no_rm}-{jenis}-{extra.get("triage", "")}-{masuk:%H%M%S}',
        jenis_kunjungan=jenis,
        tanggal_masuk=masuk or timezone.now(),
        tanggal_keluar=keluar,
        **extra)


class ShiftWindowTest(TestCase):
    def test_shift_pagi_tujuh_jam(self):
        awal, akhir = shift_window(TANGGAL, 'PAGI')
        self.assertEqual(awal.hour, 7)
        self.assertEqual(akhir.hour, 14)
        self.assertEqual((akhir - awal), timedelta(hours=7))
        self.assertEqual(awal.date(), TANGGAL)

    def test_shift_siang(self):
        awal, akhir = shift_window(TANGGAL, 'SIANG')
        self.assertEqual((awal.hour, akhir.hour), (14, 21))

    def test_shift_malam_lintas_tanggal(self):
        """Shift malam 21.00 berakhir 07.00 hari berikutnya, bukan hari yang sama."""
        awal, akhir = shift_window(TANGGAL, 'MALAM')
        self.assertEqual(awal.date(), TANGGAL)
        self.assertEqual(akhir.date(), TANGGAL + timedelta(days=1))
        self.assertEqual(akhir.hour, 7)
        self.assertEqual((akhir - awal), timedelta(hours=10))

    def test_shift_tidak_dikenal(self):
        with self.assertRaises(ValueError):
            shift_window(TANGGAL, 'SORE')


class ParseJamTest(TestCase):
    def test_titik_dari_formulir_cetak(self):
        self.assertEqual(parse_jam('9.05'), time(9, 5))

    def test_titik_dua(self):
        self.assertEqual(parse_jam('09:05'), time(9, 5))
        self.assertEqual(parse_jam('21:30'), time(21, 30))

    def test_menit_satu_digit(self):
        self.assertEqual(parse_jam('9.5'), time(9, 5))

    def test_kosong_dan_sampah(self):
        for nilai in (None, '', '   ', 'abc', '25:00', '10:75', '-1:00'):
            self.assertIsNone(parse_jam(nilai), msg=f'nilai={nilai!r}')

    def test_ber_spasi(self):
        self.assertEqual(parse_jam(' 7.00 '), time(7, 0))


class ResponseTimeTest(TestCase):
    def setUp(self):
        self.pasien = buat_pasien('RM-RT1')

    def test_hitung_menit(self):
        k = buat_kunjungan(
            self.pasien,
            masuk=timezone.make_aware(datetime(2026, 10, 20, 8, 0)),
            waktu_asesmen_dokter='8.25')
        self.assertEqual(response_time_menit(k), 25)

    def test_asesmen_lewat_tengah_malam_tidak_negatif(self):
        k = buat_kunjungan(
            self.pasien,
            masuk=timezone.make_aware(datetime(2026, 10, 20, 23, 50)),
            waktu_asesmen_dokter='00.10')
        self.assertEqual(response_time_menit(k), 20)

    def test_tanpa_jam_asesmen(self):
        k = buat_kunjungan(self.pasien,
                           masuk=timezone.make_aware(datetime(2026, 10, 20, 8, 0)))
        self.assertIsNone(response_time_menit(k))


class LosTest(TestCase):
    def test_pasien_sudah_pulang(self):
        p = buat_pasien('RM-LOS1')
        k = buat_kunjungan(
            p, jenis='RANAP',
            masuk=timezone.make_aware(datetime(2026, 10, 20, 8, 0)),
            keluar=timezone.make_aware(datetime(2026, 10, 20, 12, 30)))
        self.assertEqual(los_menit(k), 270)


class DependencyTest(TestCase):
    def test_pemetaan_teks_adl(self):
        self.assertEqual(dependency_kode('Mandiri'), 'M')
        self.assertEqual(dependency_kode('Bantuan Parsial'), 'P')
        self.assertEqual(dependency_kode('Ketergantungan Total'), 'T')

    def test_kosong_tidak_diasumsikan_mandiri(self):
        self.assertEqual(dependency_kode(''), '?')
        self.assertEqual(dependency_kode(None), '?')
        self.assertEqual(dependency_kode('Lain-lain'), '?')


class KunjunganShiftTest(TestCase):
    def setUp(self):
        self.unit = buat_unit('LB-UNIT', 'Instalasi Rawat Inap')
        self.ruangan = Ruangan.objects.create(kode='LB-R1', nama='Bangsal Uji',
                                             kelas='1', jenis='RANAP', kapasitas=2)
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='01')

    def test_igd_hanya_jendela_shift(self):
        p1, p2 = buat_pasien('RM-KS1'), buat_pasien('RM-KS2')
        buat_kunjungan(p1, masuk=timezone.make_aware(datetime(2026, 10, 20, 9, 0)))
        buat_kunjungan(p2, masuk=timezone.make_aware(datetime(2026, 10, 20, 15, 0)))
        hasil = kunjungan_shift('IGD', TANGGAL, 'PAGI')
        self.assertEqual(hasil.count(), 1)

    def test_shift_malam_menangkap_dini_hari(self):
        """Pasien masuk 02.00 tanggal 21 tetap bagian shift malam tanggal 20."""
        p = buat_pasien('RM-KS3')
        buat_kunjungan(p, masuk=timezone.make_aware(datetime(2026, 10, 21, 2, 0)))
        self.assertEqual(kunjungan_shift('IGD', TANGGAL, 'MALAM').count(), 1)
        self.assertEqual(kunjungan_shift('IGD', TANGGAL, 'PAGI').count(), 0)

    def test_ranap_termasuk_pasien_masuk_sebelum_shift(self):
        p = buat_pasien('RM-KS4')
        buat_kunjungan(p, jenis='RANAP', bed=self.bed,
                       masuk=timezone.make_aware(datetime(2026, 10, 18, 10, 0)))
        hasil = kunjungan_shift('RANAP', TANGGAL, 'PAGI', self.ruangan)
        self.assertEqual(hasil.count(), 1)

    def test_ranap_pasien_sudah_pulang_tidak_masuk(self):
        p = buat_pasien('RM-KS5')
        buat_kunjungan(p, jenis='RANAP', bed=self.bed,
                       masuk=timezone.make_aware(datetime(2026, 10, 18, 10, 0)),
                       keluar=timezone.make_aware(datetime(2026, 10, 19, 10, 0)))
        hasil = kunjungan_shift('RANAP', TANGGAL, 'PAGI', self.ruangan)
        self.assertEqual(hasil.count(), 0)


class LogbookHarianTest(TestCase):
    def setUp(self):
        self.unit = buat_unit('LB-IRIN', 'Instalasi Rawat Inap', tipe='INSTALASI')
        self.ruangan = Ruangan.objects.create(kode='LB-R2', nama='Bangsal Melati',
                                              kelas='1', jenis='RANAP', kapasitas=2)
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='A1')
        self.bed2 = Bed.objects.create(ruangan=self.ruangan, kode_bed='A2')

    def _logbook(self, jenis='RANAP', shift='PAGI'):
        return LogbookHarian.objects.create(
            jenis=jenis, unit=self.unit, ruangan=self.ruangan,
            tanggal=TANGGAL, shift=shift)

    def test_unik_per_unit_tanggal_shift(self):
        from django.db import IntegrityError
        self._logbook()
        with self.assertRaises(IntegrityError):
            self._logbook()

    def test_tarik_pasien_idempoten(self):
        p = buat_pasien('RM-TP1')
        buat_kunjungan(p, jenis='RANAP', bed=self.bed,
                       masuk=timezone.make_aware(datetime(2026, 10, 19, 9, 0)),
                       fungsional_adl='Mandiri')
        lb = self._logbook()
        self.assertEqual(lb.tarik_pasien(), 1)
        self.assertEqual(lb.tarik_pasien(), 0)
        self.assertEqual(lb.pasien.count(), 1)
        self.assertEqual(lb.pasien.first().dependency, 'M')

    def test_pasien_tanpa_bed_tetap_masuk_baris(self):
        """Pasien sudah dirawat tapi belum dibagi bed — kolom bed kosong, bukan crash.

        Pasien tanpa bed tidak bisa diatribusikan ke satu ruangan, jadi ia
        muncul di logbook tingkat unit (``ruangan=None``), bukan di logbook
        ruangan. Yang diuji: rekap & baris tetap terbentuk dengan ``no_bed``
        kosong, bukan melempar AttributeError.
        """
        p = buat_pasien('RM-TP2')
        buat_kunjungan(p, jenis='RANAP', bed=None,
                       masuk=timezone.make_aware(datetime(2026, 10, 19, 9, 0)))
        lb = LogbookHarian.objects.create(jenis='RANAP', unit=self.unit, ruangan=None,
                                          tanggal=TANGGAL, shift='PAGI')
        self.assertEqual(lb.tarik_pasien(), 1)
        baris = lb.pasien.get()
        self.assertEqual(baris.no_bed, '')
        self.assertIsNone(baris.kunjungan.bed)
        self.assertEqual(lb.rekap()['jumlah_pasien'], 1)
        self.assertIsNone(lb.rekap()['bor_persen'])

    def test_ensure_checklist_idempoten_dan_lengkap(self):
        lb = self._logbook()
        self.assertEqual(lb.ensure_checklist(), len(CHECKLIST_RANAP))
        self.assertEqual(lb.ensure_checklist(), 0)
        self.assertEqual(lb.checklist.count(), len(CHECKLIST_RANAP))
        self.assertTrue(lb.checklist.filter(butuh_nomor_segel=True).exists())

    def test_checklist_igd_berbeda_kunci(self):
        lb = self._logbook(jenis='IGD')
        lb.ensure_checklist()
        kunci = set(lb.checklist.values_list('kunci', flat=True))
        self.assertEqual(kunci, {k[0] for k in CHECKLIST_IGD})
        self.assertFalse(kunci & {k[0] for k in CHECKLIST_RANAP})

    def test_rekap_dihitung_dari_pasien(self):
        lb = self._logbook(jenis='IGD')
        p1, p2, p3 = buat_pasien('RM-RK1'), buat_pasien('RM-RK2'), buat_pasien('RM-RK3')
        buat_kunjungan(p1, triage='MERAH', waktu_asesmen_dokter='08.03',
                       disposisi_tindak_lanjut='RAWAT_INAP',
                       masuk=timezone.make_aware(datetime(2026, 10, 20, 8, 0)))
        buat_kunjungan(p2, triage='KUNING', waktu_asesmen_dokter='08.40',
                       disposisi_tindak_lanjut='RUJUK',
                       masuk=timezone.make_aware(datetime(2026, 10, 20, 8, 5)))
        buat_kunjungan(p3, triage='MERAH', waktu_asesmen_dokter='',
                       disposisi_tindak_lanjut='PAPS',
                       masuk=timezone.make_aware(datetime(2026, 10, 20, 9, 0)))
        lb.tarik_pasien()
        rekap = lb.rekap()
        self.assertEqual(rekap['jumlah_pasien'], 3)
        self.assertEqual(rekap['triage']['MERAH'], 2)
        self.assertEqual(rekap['triage']['KUNING'], 1)
        self.assertEqual(rekap['disposisi']['RAWAT_INAP'], 1)
        self.assertEqual(rekap['disposisi']['RUJUK'], 1)
        self.assertEqual(rekap['disposisi']['PAPS'], 1)
        self.assertEqual(rekap['rt_terisi'], 2)
        self.assertEqual(rekap['rt_terlambat'], 1)

    def test_bor_none_tanpa_ruangan(self):
        lb = LogbookHarian.objects.create(jenis='IGD', unit=self.unit, ruangan=None,
                                          tanggal=TANGGAL, shift='PAGI')
        self.assertIsNone(lb.rekap()['bor_persen'])

    def test_bor_persen_ruangan(self):
        lb = self._logbook()
        p = buat_pasien('RM-BOR1')
        buat_kunjungan(p, jenis='RANAP', bed=self.bed,
                       masuk=timezone.make_aware(datetime(2026, 10, 19, 9, 0)))
        lb.tarik_pasien()
        self.assertEqual(lb.rekap()['bor_persen'], 50.0)


class LogbookKejadianTest(TestCase):
    def setUp(self):
        self.unit = buat_unit('LB-IRIN2', 'Instalasi Rawat Inap', tipe='INSTALASI')
        self.logbook = LogbookHarian.objects.create(
            jenis='RANAP', unit=self.unit, tanggal=TANGGAL, shift='SIANG')

    def test_sync_ke_ikp_membuat_insiden(self):
        k = LogbookKejadian.objects.create(
            logbook=self.logbook, jenis_insiden='KNC', tingkat_keparahan='TIDAK_CEDERA',
            waktu_kejadian=time(15, 30), lokasi_kejadian='Bangsal Melati',
            deskripsi_kejadian='Pasien nyaris terjatuh dari bed.')
        insiden = k.sync_ke_ikp()
        self.assertEqual(insiden.jenis_insiden, 'KNC')
        self.assertEqual(insiden.unit_id, self.unit.pk)
        self.assertEqual(insiden.tanggal_kejadian, TANGGAL)
        k.refresh_from_db()
        self.assertEqual(k.insiden_id, insiden.pk)

    def test_sync_idempoten(self):
        k = LogbookKejadian.objects.create(
            logbook=self.logbook, jenis_insiden='KTD', tingkat_keparahan='MINOR',
            lokasi_kejadian='Bangsal Melati', deskripsi_kejadian='Salah dosis obat.')
        a = k.sync_ke_ikp()
        b = k.sync_ke_ikp()
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(type(a).objects.count(), 1)
