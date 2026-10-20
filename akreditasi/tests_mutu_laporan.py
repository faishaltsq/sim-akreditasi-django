"""Laporan Capaian Indikator Mutu — bulanan, semesteran, tahunan.

Regresi kalender pelaporan (BAB I dokumen model laporan): laporan bulanan
maksimum tanggal 10 bulan berikutnya, semesteran maksimum 20 Juli (Sem I) dan
20 Januari (Sem II), tahunan maksimum 31 Januari.
"""
import json
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from akreditasi.mutu_laporan import (
    batas_waktu_laporan, benchmarking_laporan, rekap_ikp, seksi_laporan,
    terlambat_laporan, tren_indikator,
)

User = get_user_model()


class BatasWaktuLaporanTest(TestCase):
    def test_bulanan_normal(self):
        self.assertEqual(
            batas_waktu_laporan('BULANAN', tahun=2026, bulan=1),
            date(2026, 2, 10),
        )

    def test_bulanan_desember_berganti_tahun(self):
        self.assertEqual(
            batas_waktu_laporan('BULANAN', tahun=2026, bulan=12),
            date(2027, 1, 10),
        )

    def test_semester_1_dilaporkan_juli(self):
        self.assertEqual(
            batas_waktu_laporan('SEMESTER', tahun=2026, semester=1),
            date(2026, 7, 20),
        )

    def test_semester_2_dilaporkan_januari_berikut(self):
        self.assertEqual(
            batas_waktu_laporan('SEMESTER', tahun=2026, semester=2),
            date(2027, 1, 20),
        )

    def test_tahunan_dilaporkan_januari_berikut(self):
        self.assertEqual(
            batas_waktu_laporan('TAHUNAN', tahun=2026),
            date(2027, 1, 31),
        )


class ModelLaporanMutuTest(TestCase):
    """Batas unik periode + label/status dasar pada header laporan."""

    def setUp(self):
        from akreditasi.models import UnitKerja
        from akreditasi.risiko_models import LaporanMutu

        self.UnitKerja = UnitKerja
        self.LaporanMutu = LaporanMutu
        self.user = User.objects.create_user('pjl1', 'pjl1@rs.id', 'pass123')
        self.unit = UnitKerja.objects.create(
            code='T-LAP-1', name='Instalasi Laporan Mutu', level=2, is_active=True)

    def test_satu_periode_satu_laporan_per_unit(self):
        self.LaporanMutu.objects.create(
            jenis='BULANAN', tahun=2026, bulan=3, scope='UNIT', unit=self.unit,
            pembuat=self.user)
        with self.assertRaises(ValidationError):
            self.LaporanMutu.objects.create(
                jenis='BULANAN', tahun=2026, bulan=3, scope='UNIT',
                unit=self.unit, pembuat=self.user)

    def test_laporan_rumah_sakit_tanpa_unit_unik_per_jenis_periode(self):
        """Cakupan RS memakai unit=NULL — dua laporan RS periode sama tetap
        harus ditolak, bukan lolos karena NULL dianggap berbeda."""
        self.LaporanMutu.objects.create(
            jenis='TAHUNAN', tahun=2026, scope='RS', unit=None, pembuat=self.user)
        with self.assertRaises(ValidationError):
            self.LaporanMutu.objects.create(
                jenis='TAHUNAN', tahun=2026, scope='RS', unit=None,
                pembuat=self.user)

    def test_jenis_lain_periode_rumah_sakit_tetap_boleh(self):
        self.LaporanMutu.objects.create(
            jenis='BULANAN', tahun=2026, bulan=3, scope='RS', unit=None,
            pembuat=self.user)
        self.LaporanMutu.objects.create(
            jenis='TAHUNAN', tahun=2026, scope='RS', unit=None, pembuat=self.user)

    def test_periode_label(self):
        bulanan = self.LaporanMutu.objects.create(
            jenis='BULANAN', tahun=2026, bulan=1, scope='UNIT', unit=self.unit,
            pembuat=self.user)
        semester = self.LaporanMutu.objects.create(
            jenis='SEMESTER', tahun=2026, semester=2, scope='UNIT', unit=self.unit,
            pembuat=self.user)
        tahunan = self.LaporanMutu.objects.create(
            jenis='TAHUNAN', tahun=2026, scope='UNIT', unit=self.unit,
            pembuat=self.user)
        self.assertEqual(bulanan.periode_label, 'Januari 2026')
        self.assertEqual(semester.periode_label, 'Semester II 2026')
        self.assertEqual(tahunan.periode_label, 'Tahun 2026')

    def test_status_awal_draf_serta_mengunci_setelah_terbit(self):
        laporan = self.LaporanMutu.objects.create(
            jenis='BULANAN', tahun=2026, bulan=3, scope='UNIT', unit=self.unit,
            pembuat=self.user)
        self.assertTrue(laporan.boleh_ubah)
        laporan.status = 'TERBIT'
        laporan.save(update_fields=['status'])
        self.assertFalse(laporan.boleh_ubah)

class TerlambatLaporanTest(TestCase):
    """Terlambat dihitung terhadap tanggal hari ini, bukan terhadap
    tanggal pembuatan dokumen."""

    def test_saat_tepat_batas_belum_terlambat(self):
        self.assertFalse(
            terlambat_laporan('BULANAN', tahun=2026, bulan=1, hari_ini=date(2026, 2, 10))
        )

    def test_setelah_batas_terlambat(self):
        self.assertTrue(
            terlambat_laporan('BULANAN', tahun=2026, bulan=1, hari_ini=date(2026, 2, 11))
        )

    def test_sebelum_batas_belum_terlambat(self):
        self.assertFalse(
            terlambat_laporan('BULANAN', tahun=2026, bulan=1, hari_ini=date(2026, 2, 9))
        )

    def test_tahunan_setelah_31_januari(self):
        self.assertTrue(
            terlambat_laporan('TAHUNAN', tahun=2026, hari_ini=date(2027, 2, 1))
        )


# ---------------------------------------------------------------------------
# View: daftar, buat, detail, analisis, alur verifikasi, cetak/PDF
# ---------------------------------------------------------------------------

import itertools
from decimal import Decimal

from django.urls import reverse

from accounts.models import UserProfile
from akreditasi.models import AuditLog, UnitKerja
from akreditasi.risiko_models import CatatanIndikator, IndikatorMutu, LaporanMutu

_SEQ = itertools.count(1)


def _unit(code):
    return UnitKerja.objects.create(code=f'L{next(_SEQ)}-{code}',
                                    name=f'Unit Laporan {code}', level=3,
                                    is_active=True)


def _ind(unit, kode, target=Decimal('85.00'), nama=None):
    return IndikatorMutu.objects.create(
        kode_indikator=f'L{next(_SEQ)}-{kode}',
        nama_indikator=nama or f'Indikator {kode}',
        jenis='IMP_RS', dimensi_mutu='AMAN',
        numerator='Pasien terlayani', denominator='Total pasien',
        target_nilai=target, arah_target='MIN', satuan='%',
        unit=unit, aktif=True,
    )


def _user(username, role, unit=None):
    user = User.objects.create_user(username, f'{username}@rs.id', 'pass123')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = role
    profile.unit_kerja = unit
    profile.save()
    return user


class ViewLaporanMutuTest(TestCase):
    """Alur end-to-end: buat → bekukan → analisis → verifikasi → setujui → cetak."""

    def setUp(self):
        self.unit = _unit('TENAGA')
        self.ind_baik = _ind(self.unit, 'BAIK')
        self.ind_buruk = _ind(self.unit, 'BURUK')

        # Capaian Maret 2026: 90% (tercapai) dan 50% (tidak tercapai).
        CatatanIndikator.objects.create(
            indikator=self.ind_baik, tahun=2026, bulan=3,
            nilai_numerator=90, nilai_denominator=100)
        CatatanIndikator.objects.create(
            indikator=self.ind_buruk, tahun=2026, bulan=3,
            nilai_numerator=50, nilai_denominator=100)

        self.admin = _user('admin-lap', 'ADMIN_RS')
        self.kepala = _user('kepala-lap', 'KEPALA_UNIT', self.unit)
        self.staf = _user('staf-lap', 'STAF_NAKES', self.unit)
        self.pokja = _user('pokja-lap', 'KOORDINATOR_POKJA')
        self.asesor = _user('asesor-lap', 'ASESOR')

    def _buat_laporan(self, user=None, jenis='BULANAN', bulan='3',
                      scope='UNIT', tahun='2026'):
        payload = {'jenis': jenis, 'tahun': tahun, 'scope': scope,
                   'unit': self.unit.pk}
        if jenis == 'BULANAN':
            payload['bulan'] = bulan
        elif jenis == 'SEMESTER':
            payload['semester'] = '1'
        self.client.force_login(user or self.admin)
        return self.client.post(reverse('akreditasi:laporan_mutu_create'), payload)

    def _laporan_terakhir(self):
        return LaporanMutu.objects.latest('id')

    # ── pembuatan & snapshot ────────────────────────────────────────────

    def test_pembuatan_bulanan_membekukan_snapshot(self):
        res = self._buat_laporan()
        self.assertEqual(res.status_code, 302)
        laporan = self._laporan_terakhir()
        baris = list(laporan.baris.order_by('kode'))
        self.assertEqual(len(baris), 2)
        nilai = {b.kode: b.nilai_capaian for b in baris}
        self.assertEqual(str(nilai[self.ind_baik.kode_indikator]), '90.00')
        self.assertEqual(str(nilai[self.ind_buruk.kode_indikator]), '50.00')
        status = {b.kode: b.status_tercapai for b in baris}
        self.assertTrue(status[self.ind_baik.kode_indikator])
        self.assertFalse(status[self.ind_buruk.kode_indikator])
        # Angka N/D periode ikut dibekukan — kolom N/D di laporan menampilkan
        # angka, bukan deskripsi rumus dari master.
        n = {b.kode: b.nilai_numerator for b in baris}
        d = {b.kode: b.nilai_denominator for b in baris}
        self.assertEqual(str(n[self.ind_baik.kode_indikator]), '90.00')
        self.assertEqual(str(d[self.ind_baik.kode_indikator]), '100.00')

    def test_snapshot_tidak_berubah_ketika_data_dikoreksi(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        CatatanIndikator.objects.filter(indikator=self.ind_baik).update(
            nilai_numerator=10, nilai_denominator=100)
        baris = laporan.baris.get(kode=self.ind_baik.kode_indikator)
        self.assertEqual(str(baris.nilai_capaian), '90.00')

        # Regenerasi eksplisit (hanya draf) memakai data terbaru.
        self.client.post(reverse('akreditasi:laporan_mutu_regenerasi',
                                 args=[laporan.pk]))
        baris.refresh_from_db()
        self.assertEqual(str(baris.nilai_capaian), '10.00')

    def test_regenerasi_mempertahankan_analisis(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        baris = laporan.baris.get(kode=self.ind_buruk.kode_indikator)
        self.client.post(reverse('akreditasi:laporan_mutu_simpan_analisis',
                                 args=[laporan.pk]),
                         {'baris_id': baris.pk, 'analisis': 'Analisis awal',
                          'tindak_lanjut': 'Tindakan awal'})
        self.client.post(reverse('akreditasi:laporan_mutu_regenerasi',
                                 args=[laporan.pk]))
        baris.refresh_from_db()
        self.assertEqual(baris.analisis, 'Analisis awal')
        self.assertEqual(baris.tindak_lanjut, 'Tindakan awal')

    def test_periode_kembar_membalas_peringatan_bukan_500(self):
        self._buat_laporan()
        res = self._buat_laporan()
        self.assertEqual(res.status_code, 200)  # form ditampilkan ulang + peringatan
        self.assertEqual(LaporanMutu.objects.filter(jenis='BULANAN').count(), 1)
        self.assertIn('sudah ada', res.content.decode())

    def test_halaman_daftar_dan_detail_200(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.assertEqual(
            self.client.get(reverse('akreditasi:laporan_mutu_daftar')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('akreditasi:laporan_mutu_detail',
                                    args=[laporan.pk])).status_code, 200)

    def test_form_buat_tampil_untuk_pengelola(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('akreditasi:laporan_mutu_create'))
        self.assertEqual(res.status_code, 200)
        isi = res.content.decode()
        self.assertIn('BULANAN', isi)
        self.assertIn('TAHUNAN', isi)

    def test_daftar_memuat_tautan_laporan_mutu_di_sidebar(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('akreditasi:laporan_mutu_daftar'))
        self.assertIn('Laporan Mutu', res.content.decode())

    # ── analisis PDSA ───────────────────────────────────────────────────

    def test_analisis_tersimpan_pada_draf(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        baris = laporan.baris.get(kode=self.ind_buruk.kode_indikator)
        self.client.post(reverse('akreditasi:laporan_mutu_simpan_analisis',
                                 args=[laporan.pk]),
                         {'baris_id': baris.pk,
                          'analisis': 'Fishbone: faktor manusia',
                          'tindak_lanjut': 'Sosialisasi ulang SOP'})
        baris.refresh_from_db()
        self.assertEqual(baris.analisis, 'Fishbone: faktor manusia')
        self.assertEqual(baris.tindak_lanjut, 'Sosialisasi ulang SOP')

    def test_analisis_massal_menyimpan_banyak_baris(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        b1 = laporan.baris.get(kode=self.ind_baik.kode_indikator)
        b2 = laporan.baris.get(kode=self.ind_buruk.kode_indikator)
        payload = {
            f'analisis_{b1.pk}': 'Analisis baik',
            f'tindak_lanjut_{b1.pk}': 'Pertahankan',
            f'analisis_{b2.pk}': 'Analisis buruk',
            f'tindak_lanjut_{b2.pk}': 'Perbaiki',
        }
        res = self.client.post(
            reverse('akreditasi:laporan_mutu_simpan_analisis', args=[laporan.pk]),
            payload)
        self.assertEqual(res.status_code, 302)
        b1.refresh_from_db(); b2.refresh_from_db()
        self.assertEqual(b1.analisis, 'Analisis baik')
        self.assertEqual(b2.tindak_lanjut, 'Perbaiki')

    def test_analisis_ditolak_setelah_verifikasi(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        baris = laporan.baris.get(kode=self.ind_buruk.kode_indikator)
        baris.analisis = 'Analisis lama'
        baris.save(update_fields=['analisis'])

        self.client.post(reverse('akreditasi:laporan_mutu_verifikasi',
                                 args=[laporan.pk]), {'catatan': 'ok'})
        res = self.client.post(
            reverse('akreditasi:laporan_mutu_simpan_analisis', args=[laporan.pk]),
            {'baris_id': baris.pk, 'analisis': 'Perubahan ilegal'})
        self.assertEqual(res.status_code, 302)
        baris.refresh_from_db()
        self.assertEqual(baris.analisis, 'Analisis lama')

    # ── alur verifikasi L4 → L3 → L2 ───────────────────────────────────

    def test_rantai_verifikasi_lengkap_sampai_terbit(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        audit_awal = AuditLog.objects.count()

        self.client.force_login(self.kepala)
        res = self.client.post(reverse('akreditasi:laporan_mutu_verifikasi',
                                       args=[laporan.pk]), {'catatan': 'sesuai'})
        self.assertEqual(res.status_code, 302)
        laporan.refresh_from_db()
        self.assertEqual(laporan.status, 'DIVERIFIKASI')
        self.assertEqual(laporan.diverifikasi_oleh, self.kepala)
        self.assertIsNotNone(laporan.diverifikasi_pada)

        self.client.force_login(self.pokja)
        self.client.post(reverse('akreditasi:laporan_mutu_setujui',
                                 args=[laporan.pk]))
        laporan.refresh_from_db()
        self.assertEqual(laporan.status, 'DISETUJUI')
        self.assertEqual(laporan.disetujui_oleh, self.pokja)

        self.client.force_login(self.admin)
        self.client.post(reverse('akreditasi:laporan_mutu_setujui',
                                 args=[laporan.pk]))
        laporan.refresh_from_db()
        self.assertEqual(laporan.status, 'TERBIT')
        self.assertIsNotNone(laporan.terbit_pada)
        self.assertEqual(AuditLog.objects.count(), audit_awal + 3)

    def test_staf_nakes_tidak_boleh_memverifikasi(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.client.force_login(self.staf)
        res = self.client.post(reverse('akreditasi:laporan_mutu_verifikasi',
                                       args=[laporan.pk]))
        self.assertEqual(res.status_code, 403)
        laporan.refresh_from_db()
        self.assertEqual(laporan.status, 'DRAF')

    def test_lompatan_status_draf_ke_setujui_ditolak_400(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.client.force_login(self.pokja)
        res = self.client.post(reverse('akreditasi:laporan_mutu_setujui',
                                       args=[laporan.pk]))
        self.assertEqual(res.status_code, 400)
        laporan.refresh_from_db()
        self.assertEqual(laporan.status, 'DRAF')

    def test_staf_nakes_bukan_verifikator_pun_ditolak_400(self):
        """Diverifikasi dulu, lalu STAF_NAKES mencoba menyetujui → 403."""
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.client.force_login(self.kepala)
        self.client.post(reverse('akreditasi:laporan_mutu_verifikasi',
                                 args=[laporan.pk]))
        self.client.force_login(self.staf)
        res = self.client.post(reverse('akreditasi:laporan_mutu_setujui',
                                       args=[laporan.pk]))
        self.assertEqual(res.status_code, 403)

    def test_verifikasi_tidak_bisa_diulang(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.client.force_login(self.kepala)
        self.client.post(reverse('akreditasi:laporan_mutu_verifikasi',
                                 args=[laporan.pk]))
        res = self.client.post(reverse('akreditasi:laporan_mutu_verifikasi',
                                       args=[laporan.pk]))
        self.assertEqual(res.status_code, 400)

    # ── RBAC cakupan & ASESOR ───────────────────────────────────────────

    def test_asesor_hanya_melihat_laporan_terbit(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.client.force_login(self.asesor)
        self.assertEqual(
            self.client.get(reverse('akreditasi:laporan_mutu_detail',
                                    args=[laporan.pk])).status_code, 403)

        self.client.force_login(self.kepala)
        self.client.post(reverse('akreditasi:laporan_mutu_verifikasi',
                                 args=[laporan.pk]))
        self.client.force_login(self.pokja)
        self.client.post(reverse('akreditasi:laporan_mutu_setujui',
                                 args=[laporan.pk]))
        self.client.force_login(self.admin)
        self.client.post(reverse('akreditasi:laporan_mutu_setujui',
                                 args=[laporan.pk]))

        self.client.force_login(self.asesor)
        self.assertEqual(
            self.client.get(reverse('akreditasi:laporan_mutu_detail',
                                    args=[laporan.pk])).status_code, 200)

    def test_staf_dari_unit_lain_tidak_bisa_melihat(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        unit_lain = _unit('LAIN')
        penjaga = _user('kepala-lain', 'KEPALA_UNIT', unit_lain)
        self.client.force_login(penjaga)
        self.assertEqual(
            self.client.get(reverse('akreditasi:laporan_mutu_detail',
                                    args=[laporan.pk])).status_code, 403)

    def test_pembuatan_cakupan_rs_hanya_pengelola(self):
        res = self._buat_laporan(user=self.staf, scope='RS', jenis='TAHUNAN')
        self.assertEqual(res.status_code, 403)

    # ── cetak & PDF ─────────────────────────────────────────────────────

    def test_cetak_menampilkan_kop_dan_kode_indikator(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        res = self.client.get(reverse('akreditasi:laporan_mutu_cetak',
                                      args=[laporan.pk]))
        self.assertEqual(res.status_code, 200)
        isi = res.content.decode()
        self.assertIn(self.ind_baik.kode_indikator, isi)
        self.assertIn(laporan.periode_label, isi)
        self.assertIn('Diverifikasi Oleh', isi)

    # ── rekap IKP, benchmarking, narasi ─────────────────────────────────

    def test_rekap_ikp_lima_jenis_selalu_muncul(self):
        from akreditasi.risiko_models import InsidenKeselamatan
        InsidenKeselamatan.objects.create(
            unit=self.unit, tanggal_kejadian=date(2026, 3, 5),
            jenis_insiden='KTD', tingkat_keparahan='MINOR',
            lokasi_kejadian='IGD', deskripsi_kejadian='Salah dosis')
        InsidenKeselamatan.objects.create(
            unit=self.unit, tanggal_kejadian=date(2026, 3, 9),
            jenis_insiden='KNC', tingkat_keparahan='TIDAK_CEDERA',
            lokasi_kejadian='Rawat Inap', deskripsi_kejadian='Nyaris tertukar')

        hasil = rekap_ikp(2026, 3, 3, unit=self.unit)
        kode = [b['kode'] for b in hasil['baris']]
        self.assertEqual(kode, ['KTD', 'KNC', 'KTC', 'KPC', 'SENTINEL'])
        jumlah = {b['kode']: b['jumlah'] for b in hasil['baris']}
        self.assertEqual(jumlah['KTD'], 1)
        self.assertEqual(jumlah['KNC'], 1)
        self.assertEqual(jumlah['KTC'], 0)   # tidak ada kejadian → tetap 0
        self.assertEqual(jumlah['SENTINEL'], 0)
        self.assertEqual(hasil['total'], 2)

    def test_rekap_ikp_unit_lain_tidak_terhitung(self):
        from akreditasi.risiko_models import InsidenKeselamatan
        unit_lain = _unit('IKP-LAIN')
        InsidenKeselamatan.objects.create(
            unit=unit_lain, tanggal_kejadian=date(2026, 3, 7),
            jenis_insiden='KTD', tingkat_keparahan='MAYOR',
            lokasi_kejadian='OK', deskripsi_kejadian='Retensi instrumen')

        hasil = rekap_ikp(2026, 3, 3, unit=self.unit)
        self.assertEqual(hasil['total'], 0)

    def test_benchmark_membandingkan_dengan_capaian_rs(self):
        # Indikator yang sama diukur juga di unit lain (nama identik, kode beda).
        unit_lain = _unit('BENCH-LAIN')
        ind_lain = _ind(unit_lain, 'BAIK-LAIN', nama=self.ind_baik.nama_indikator)
        CatatanIndikator.objects.create(
            indikator=ind_lain, tahun=2026, bulan=3,
            nilai_numerator=60, nilai_denominator=100)

        self._buat_laporan()
        laporan = self._laporan_terakhir()
        bench = benchmarking_laporan(laporan)

        # ΣN/ΣD seluruh RS: (90 + 60) / (100 + 100) = 75.00
        self.assertEqual(str(bench[self.ind_baik.kode_indikator]['capaian_rs']),
                         '75.00')
        # Unit ini 90.00 → selisih +15.00 terhadap RS
        self.assertEqual(str(bench[self.ind_baik.kode_indikator]['selisih']),
                         '15.00')

    def test_seksi_tersimpan_dan_terbaca(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        res = self.client.post(
            reverse('akreditasi:laporan_mutu_simpan_seksi', args=[laporan.pk]),
            {'seksi_RINGKASAN_EKSEKUTIF': 'Capaian bulan ini membaik.',
             'seksi_KENDALA': 'Data unit X belum lengkap.'})
        self.assertEqual(res.status_code, 302)
        isi = {s['kunci']: s['isi'] for s in seksi_laporan(laporan)}
        self.assertEqual(isi['RINGKASAN_EKSEKUTIF'], 'Capaian bulan ini membaik.')
        self.assertEqual(isi['KENDALA'], 'Data unit X belum lengkap.')
        self.assertEqual(isi['REKOMENDASI'], '')  # belum diisi

    def test_seksi_ditolak_setelah_verifikasi(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.client.post(reverse('akreditasi:laporan_mutu_simpan_seksi',
                                 args=[laporan.pk]),
                         {'seksi_KENDALA': 'Kendala awal'})
        self.client.post(reverse('akreditasi:laporan_mutu_verifikasi',
                                 args=[laporan.pk]))
        self.client.post(reverse('akreditasi:laporan_mutu_simpan_seksi',
                                 args=[laporan.pk]),
                         {'seksi_KENDALA': 'Perubahan ilegal'})
        isi = {s['kunci']: s['isi'] for s in seksi_laporan(laporan)}
        self.assertEqual(isi['KENDALA'], 'Kendala awal')

    def test_detail_menampilkan_rekap_ikp_dan_narasi(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.client.post(reverse('akreditasi:laporan_mutu_simpan_seksi',
                                 args=[laporan.pk]),
                         {'seksi_KENDALA': 'Kendala uji tampilan'})
        res = self.client.get(reverse('akreditasi:laporan_mutu_detail',
                                      args=[laporan.pk]))
        isi = res.content.decode()
        self.assertIn('Rekap Kejadian IKP', isi)
        self.assertIn('Kendala uji tampilan', isi)

    def test_tren_kosong_untuk_laporan_bulanan(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        self.assertIsNone(tren_indikator(laporan))

    def test_tren_enam_bulan_untuk_laporan_semester(self):
        for bulan in range(1, 7):
            CatatanIndikator.objects.update_or_create(
                indikator=self.ind_baik, tahun=2026, bulan=bulan,
                defaults={'nilai_numerator': 70 + bulan,
                          'nilai_denominator': 100})

        self._buat_laporan(jenis='SEMESTER')
        laporan = self._laporan_terakhir()
        tren = tren_indikator(laporan)
        self.assertEqual(len(tren['bulan_header']), 6)
        baris = next(t for t in tren['baris']
                     if t['kode'] == self.ind_baik.kode_indikator)
        self.assertEqual(str(baris['nilai_bulan'][0]), '71.00')
        self.assertEqual(str(baris['nilai_bulan'][-1]), '76.00')
        self.assertEqual(str(baris['terendah']), '71.00')
        self.assertEqual(str(baris['tertinggi']), '76.00')
        self.assertEqual(baris['jumlah_bulan_terisi'], 6)

    def test_cetak_semester_memuat_tabel_tren(self):
        self._buat_laporan(jenis='SEMESTER')
        laporan = self._laporan_terakhir()
        res = self.client.get(reverse('akreditasi:laporan_mutu_cetak',
                                      args=[laporan.pk]))
        self.assertIn('Tren Capaian Bulanan', res.content.decode())

    def test_pdf_semester_memuat_grafik_tren(self):
        """PDF semester dengan indikator di bawah target harus > PDF bulanan."""
        self._buat_laporan(jenis='SEMESTER')
        lap_sem = self._laporan_terakhir()
        res_sem = self.client.get(reverse('akreditasi:laporan_mutu_pdf',
                                          args=[lap_sem.pk]))
        self.assertEqual(res_sem.status_code, 200)
        self.assertTrue(res_sem.content.startswith(b'%PDF'))

        LaporanMutu.objects.all().delete()
        self._buat_laporan()
        lap_bul = self._laporan_terakhir()
        res_bul = self.client.get(reverse('akreditasi:laporan_mutu_pdf',
                                          args=[lap_bul.pk]))
        self.assertGreater(len(res_sem.content), len(res_bul.content))

    def test_pdf_teks_terbaca_dari_layer_pdf(self):
        """Isi PDF harus bisa dibaca mesin, bukan sekadar byte %PDF."""
        import io

        from pypdf import PdfReader

        self._buat_laporan()
        laporan = self._laporan_terakhir()
        res = self.client.get(reverse('akreditasi:laporan_mutu_pdf',
                                      args=[laporan.pk]))
        teks = "\n".join(p.extract_text() or "" for p in
                          PdfReader(io.BytesIO(res.content)).pages)
        self.assertIn(self.ind_baik.kode_indikator, teks)
        self.assertIn(laporan.periode_label, teks)
        self.assertIn('REKAP KEJADIAN IKP', teks)

    def test_pdf_balas_application_pdf(self):
        self._buat_laporan()
        laporan = self._laporan_terakhir()
        res = self.client.get(reverse('akreditasi:laporan_mutu_pdf',
                                      args=[laporan.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))
        self.assertIn(b'Laporan Mutu', res.content)  # judul di metadata
        self.assertIn('attachment', res['Content-Disposition'])
        self.assertIn('.pdf', res['Content-Disposition'])


class MonevKeAnalisisLaporanTest(TestCase):
    """Analisis & tindak lanjut laporan diambil dari Monitoring-Evaluasi.

    Sumbernya RisikoUnit (halaman risiko/monitoring-evaluasi) yang indikatornya
    tertaut ke master; periode triwulan harus cocok dengan bulan laporan.
    """

    def setUp(self):
        from akreditasi.risiko_models import RisikoUnit

        self.unit = _unit('MONEV')
        self.ind = _ind(self.unit, 'MONEV-1', target=Decimal('85.00'))
        CatatanIndikator.objects.create(
            indikator=self.ind, tahun=2026, bulan=3,
            nilai_numerator=50, nilai_denominator=100)
        self.admin = _user('admin-monev', 'ADMIN_RS')

        self.risiko = RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='KLINIS',
            jenis_risiko='Kegagalan triase IGD',
            masalah='Response time > 5 menit',
            deskripsi_risiko='Response time triase melampaui standar',
            dampak=3, probabilitas=3, strategi_mitigasi='KURANGI',
            rencana_aksi='Sosialisasi SOP triase',
            pj_mitigasi='Ka. IGD',
            status='EVALUASI',
            indikator_mutu_terkait=self.ind,
            evaluasi_capaian='Capaian turun karena beban kunjungan naik.',
            akar_masalah_rca='Jumlah perawat triase kurang pada shift malam.',
            rencana_tindak_lanjut='Tambah satu perawat triase shift malam.',
            pj_rtl='Ka. IGD', status_rtl='PROSES',
        )

    def _laporan(self, jenis='BULANAN', bulan='3'):
        payload = {'jenis': jenis, 'tahun': '2026', 'scope': 'UNIT',
                   'unit': self.unit.pk}
        if jenis == 'BULANAN':
            payload['bulan'] = bulan
        elif jenis == 'SEMESTER':
            payload['semester'] = '1'
        self.client.force_login(self.admin)
        self.client.post(reverse('akreditasi:laporan_mutu_create'), payload)
        return LaporanMutu.objects.latest('id')

    def test_periode_monev_mengikuti_bulan_laporan(self):
        from akreditasi.mutu_laporan import periode_monev_relevan

        self.assertEqual(periode_monev_relevan('BULANAN', 3),
                         ['TRIWULAN_1', 'TAHUNAN'])
        self.assertEqual(periode_monev_relevan('BULANAN', 8),
                         ['TRIWULAN_3', 'TAHUNAN'])
        self.assertEqual(periode_monev_relevan('SEMESTER', semester=2),
                         ['TRIWULAN_3', 'TRIWULAN_4', 'TAHUNAN'])

    def test_tarik_monev_mengisi_analisis_dan_tindak_lanjut(self):
        laporan = self._laporan()
        res = self.client.post(
            reverse('akreditasi:laporan_mutu_tarik_monev', args=[laporan.pk]))
        self.assertEqual(res.status_code, 302)

        baris = laporan.baris.get(kode=self.ind.kode_indikator)
        self.assertIn('beban kunjungan naik', baris.analisis)
        self.assertIn('perawat triase kurang', baris.analisis)
        self.assertIn('Tambah satu perawat triase', baris.tindak_lanjut)
        self.assertIn('Ka. IGD', baris.tindak_lanjut)

    def test_tarik_monev_tidak_menimpa_tanpa_centang(self):
        laporan = self._laporan()
        baris = laporan.baris.get(kode=self.ind.kode_indikator)
        baris.analisis = 'Analisis manual petugas'
        baris.save(update_fields=['analisis'])

        self.client.post(
            reverse('akreditasi:laporan_mutu_tarik_monev', args=[laporan.pk]))
        baris.refresh_from_db()
        self.assertEqual(baris.analisis, 'Analisis manual petugas')
        # Kolom yang masih kosong tetap terisi.
        self.assertIn('Tambah satu perawat triase', baris.tindak_lanjut)

    def test_tarik_monev_dengan_timpa_mengganti_analisis_manual(self):
        laporan = self._laporan()
        baris = laporan.baris.get(kode=self.ind.kode_indikator)
        baris.analisis = 'Analisis manual petugas'
        baris.save(update_fields=['analisis'])

        self.client.post(
            reverse('akreditasi:laporan_mutu_tarik_monev', args=[laporan.pk]),
            {'timpa': '1'})
        baris.refresh_from_db()
        self.assertIn('beban kunjungan naik', baris.analisis)

    def test_tarik_monev_ditolak_setelah_verifikasi(self):
        laporan = self._laporan()
        laporan.status = 'DIVERIFIKASI'
        laporan.save(update_fields=['status'])

        self.client.post(
            reverse('akreditasi:laporan_mutu_tarik_monev', args=[laporan.pk]))
        baris = laporan.baris.get(kode=self.ind.kode_indikator)
        self.assertEqual(baris.analisis, '')

    def test_detail_menandai_baris_yang_punya_sumber_monev(self):
        laporan = self._laporan()
        res = self.client.get(
            reverse('akreditasi:laporan_mutu_detail', args=[laporan.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Tarik dari MONEV')
        self.assertContains(res, 'MONEV · Triwulan I')

    def test_laporan_bulan_di_luar_triwulan_tidak_menarik_analisis(self):
        """MONEV Triwulan I tidak boleh bocor ke laporan bulan April."""
        laporan = self._laporan(bulan='4')
        res = self.client.post(
            reverse('akreditasi:laporan_mutu_tarik_monev', args=[laporan.pk]))
        self.assertEqual(res.status_code, 302)
        baris = laporan.baris.get(kode=self.ind.kode_indikator)
        self.assertEqual(baris.analisis, '')

    def test_cetak_memakai_analisis_monev_tanpa_menyimpan(self):
        """Dokumen cetak menampilkan analisis MONEV walau baris masih kosong."""
        laporan = self._laporan()
        res = self.client.get(
            reverse('akreditasi:laporan_mutu_cetak', args=[laporan.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'beban kunjungan naik')
        self.assertContains(res, 'Tambah satu perawat triase')
        # Cetak tidak boleh menulis ke baris draf.
        baris = laporan.baris.get(kode=self.ind.kode_indikator)
        self.assertEqual(baris.analisis, '')
        self.assertEqual(baris.tindak_lanjut, '')

    def test_pdf_memuat_analisis_monev(self):
        import io

        from pypdf import PdfReader

        laporan = self._laporan()
        res = self.client.get(
            reverse('akreditasi:laporan_mutu_pdf', args=[laporan.pk]))
        teks = "\n".join(p.extract_text() or "" for p in
                          PdfReader(io.BytesIO(res.content)).pages)
        self.assertIn('beban kunjungan naik', teks)

    def test_monev_kosong_tidak_mengisi_apa_pun(self):
        """RisikoUnit tanpa evaluasi/RTL tidak boleh menulis teks sampah."""
        from akreditasi.risiko_models import RisikoUnit

        RisikoUnit.objects.filter(pk=self.risiko.pk).update(
            evaluasi_capaian='', akar_masalah_rca='', rca_fishbone={},
            failure_mode_fmea='', rca_ulang='',
            rencana_tindak_lanjut='', pj_rtl='', deadline_rtl=None)

        laporan = self._laporan()
        self.client.post(
            reverse('akreditasi:laporan_mutu_tarik_monev', args=[laporan.pk]))
        baris = laporan.baris.get(kode=self.ind.kode_indikator)
        self.assertEqual(baris.analisis, '')
        self.assertEqual(baris.tindak_lanjut, '')

        # Halaman detail pun tidak menandai baris itu punya sumber MONEV.
        res = self.client.get(
            reverse('akreditasi:laporan_mutu_detail', args=[laporan.pk]))
        self.assertNotContains(res, 'Tarik dari MONEV')


class AiNarasiLaporanTest(TestCase):
    """Bantuan AI untuk bagian naratif laporan (endpoint + tombol di halaman)."""

    def setUp(self):
        from django.core.cache import cache
        from akreditasi.system_models import SystemConfig
        cache.clear()          # rate-limit AI disimpan di cache

        self.unit = _unit('AINAR')
        self.unit_lain = _unit('AINAR2')
        self.ind = _ind(self.unit, 'AINAR')
        CatatanIndikator.objects.create(
            indikator=self.ind, tahun=2026, bulan=3,
            nilai_numerator=50, nilai_denominator=100)

        self.admin = _user('admin-narasi', 'ADMIN_RS')
        self.kepala = _user('kepala-narasi', 'KEPALA_UNIT', self.unit)
        self.kepala_lain = _user('kepala-narasi2', 'KEPALA_UNIT', self.unit_lain)

        self.config = SystemConfig.get_solo()
        self.config.ai_enabled = True
        self.config.ai_enable_laporan = True
        self.config.ai_api_key = 'sk-uji-narasi'
        self.config.save()

        self.laporan = LaporanMutu.objects.create(
            jenis='BULANAN', tahun=2026, bulan=3, scope='UNIT',
            unit=self.unit, pembuat=self.admin)
        # Snapshot baris dibangun seperti saat laporan dibuat lewat form —
        # tanpa baris, tidak ada angka yang bisa dikutip narasi.
        from akreditasi.mutu_laporan import build_baris
        build_baris(self.laporan)

    def _url(self):
        return reverse('akreditasi:api_ai_narasi_laporan')

    def _post(self, user=None, **payload):
        self.client.force_login(user or self.admin)
        body = {'laporan_id': self.laporan.pk, 'kunci': 'RINGKASAN_EKSEKUTIF'}
        body.update(payload)
        return self.client.post(self._url(), data=json.dumps(body),
                                content_type='application/json')

    def test_butuh_login(self):
        res = self.client.post(self._url(), data='{}',
                               content_type='application/json')
        self.assertEqual(res.status_code, 302)

    def test_laporan_tidak_ada_404(self):
        res = self._post(laporan_id=999999)
        self.assertEqual(res.status_code, 404)

    def test_bagian_tidak_dipakai_jenis_laporan_ditolak(self):
        res = self._post(kunci='BAB_II')       # BAB hanya ada di laporan tahunan
        self.assertEqual(res.status_code, 400)
        self.assertIn('tidak dipakai', res.json()['error'])

    def test_laporan_terkunci_ditolak(self):
        LaporanMutu.objects.filter(pk=self.laporan.pk).update(status='DIVERIFIKASI')
        res = self._post()
        self.assertEqual(res.status_code, 403)
        self.assertIn('terkunci', res.json()['error'])

    def test_unit_lain_ditolak(self):
        res = self._post(user=self.kepala_lain)
        self.assertEqual(res.status_code, 403)

    def test_ai_mati_ditolak(self):
        self.config.ai_enabled = False
        self.config.save()
        res = self._post()
        self.assertEqual(res.status_code, 400)
        self.assertIn('belum diaktifkan', res.json()['error'])

    def test_modul_laporan_dimatikan_ditolak(self):
        self.config.ai_enable_laporan = False
        self.config.save()
        res = self._post()
        self.assertEqual(res.status_code, 400)
        self.assertIn('Laporan Mutu', res.json()['error'])

    def test_sukses_mengembalikan_narasi_dan_mengirim_angka_laporan(self):
        ditangkap = {}

        def _palsu(prompt, **kwargs):
            ditangkap['prompt'] = prompt
            return {'success': True, 'error': None,
                    'data': {'narasi': 'Paragraf satu.\n\nParagraf dua.'}}

        with mock.patch('akreditasi.ai_service._call_deepseek', side_effect=_palsu):
            res = self._post(instruksi='tekankan kepatuhan hand hygiene')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['data']['narasi'],
                         'Paragraf satu.\n\nParagraf dua.')
        self.assertEqual(res.json()['data']['kunci'], 'RINGKASAN_EKSEKUTIF')
        prompt = ditangkap['prompt']
        # Angka diambil dari snapshot baris laporan, bukan dari klien.
        self.assertIn('50', prompt)
        self.assertIn('tidak mencapai target', prompt)
        self.assertIn('tekankan kepatuhan hand hygiene', prompt)
        # Setiap panggilan AI tercatat untuk audit akreditasi.
        self.assertTrue(AuditLog.objects.filter(model_name='AI_DEEPSEEK').exists())

    def test_balasan_ai_tanpa_narasi_ditolak(self):
        with mock.patch('akreditasi.ai_service._call_deepseek',
                        return_value={'success': True, 'error': None, 'data': {}}):
            res = self._post()
        self.assertEqual(res.status_code, 400)
        self.assertIn('tidak mengembalikan narasi', res.json()['error'])

    def test_halaman_detail_menampilkan_tombol_ai(self):
        self.client.force_login(self.kepala)
        res = self.client.get(
            reverse('akreditasi:laporan_mutu_detail', args=[self.laporan.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['ai_narasi_aktif'])
        self.assertContains(res, 'Bantu AI')
        self.assertContains(res, 'ai-instruksi-narasi')

    def test_tombol_ai_tersembunyi_saat_modul_dimatikan(self):
        self.config.ai_enable_laporan = False
        self.config.save()
        self.client.force_login(self.kepala)
        res = self.client.get(
            reverse('akreditasi:laporan_mutu_detail', args=[self.laporan.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['ai_narasi_aktif'])
        self.assertNotContains(res, 'Bantu AI')
