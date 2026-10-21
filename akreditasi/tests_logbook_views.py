"""Test view & alur status Logbook Harian IGD / Rawat Inap."""

from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.logbook_models import (
    LogbookBukti, LogbookHarian, LogbookKejadian, LogbookPasien,
)
from accounts.models import UserProfile
from akreditasi.models import AuditLog, UnitKerja
from akreditasi.risiko_models import InsidenKeselamatan
from pasien.models import Bed, KunjunganPasien, Pasien, Ruangan

TANGGAL = date(2026, 10, 20)


def buat_unit(kode, nama, tipe='RUANGAN', parent=None):
    return UnitKerja.objects.create(code=kode, name=nama, level=2 if parent else 1,
                                    tipe_unit=tipe, parent=parent)


def buat_user(username, role, unit, password='x'):
    u = User.objects.create_user(username=username, password=password)
    UserProfile.objects.update_or_create(user=u, defaults={'role': role, 'unit_kerja': unit})
    return u


def buat_pasien(no_rm, nama='Pasien Uji', lahir=date(1980, 1, 1)):
    return Pasien.objects.create(no_rm=no_rm, nama_lengkap=nama,
                                 tanggal_lahir=lahir, jenis_kelamin='L')


def buat_kunjungan(pasien, jenis='IGD', masuk=None, keluar=None, **extra):
    return KunjunganPasien.objects.create(
        pasien=pasien,
        no_kunjungan=f'KJ-{pasien.no_rm}-{jenis}-{extra.get("triage", "")}-{timezone.now():%H%M%S%f}',
        jenis_kunjungan=jenis,
        tanggal_masuk=masuk or timezone.now(),
        tanggal_keluar=keluar,
        **extra)


def jam(h, m=0):
    """Waktu aware pada tanggal uji (timezone lokal → UTC oleh ORM)."""
    return timezone.make_aware(datetime.combine(TANGGAL, time(h, m)))


class LogbookViewBase(TestCase):
    def setUp(self):
        self.unit = buat_unit('IGD01', 'Instalasi Gawat Darurat')
        self.unit_lain = buat_unit('RANAP01', 'Ruang Melati')
        self.petugas = buat_user('petugas', 'STAF_NAKES', self.unit)
        self.admin = buat_user('adminrs', 'ADMIN_RS', None)
        self.kepala = buat_user('kepala', 'KEPALA_UNIT', self.unit)
        self.asesor = buat_user('asesor', 'ASESOR', None)
        self.pasien = buat_pasien('RM-001', 'Sutrisno')
        self.kunjungan = buat_kunjungan(
            self.pasien, jenis='IGD', triage='MERAH',
            masuk=jam(8, 15), keluar=jam(11, 45),
            waktu_asesmen_dokter='08:18',
            diagnosa_masuk='Chest pain', fungsional_adl='Mandiri',
            disposisi_tindak_lanjut='RAWAT_INAP')
        self.logbook = LogbookHarian.objects.create(
            jenis='IGD', unit=self.unit, tanggal=TANGGAL, shift='PAGI',
            dibuat_oleh=self.admin)


class AksesLogbookTest(LogbookViewBase):
    def test_harus_login(self):
        r = self.client.get(reverse('akreditasi:logbook_daftar'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login', r['Location'])

    def test_unit_scoped_hanya_melihat_unitnya(self):
        LogbookHarian.objects.create(jenis='RANAP', unit=self.unit_lain,
                                     tanggal=TANGGAL, shift='PAGI')
        self.client.force_login(self.petugas)
        r = self.client.get(reverse('akreditasi:logbook_daftar'))
        self.assertEqual(r.status_code, 200)
        daftar = r.context['daftar']
        self.assertEqual([lb.unit_id for lb in daftar], [self.unit.pk])

    def test_admin_rs_melihat_semua_unit(self):
        LogbookHarian.objects.create(jenis='RANAP', unit=self.unit_lain,
                                     tanggal=TANGGAL, shift='PAGI')
        self.client.force_login(self.admin)
        r = self.client.get(reverse('akreditasi:logbook_daftar'))
        self.assertEqual(len(r.context['daftar']), 2)

    def test_asesor_hanya_logbook_disetujui(self):
        LogbookHarian.objects.create(jenis='RANAP', unit=self.unit_lain,
                                     tanggal=TANGGAL, shift='PAGI', status='DISETUJUI')
        self.client.force_login(self.asesor)
        r = self.client.get(reverse('akreditasi:logbook_daftar'))
        self.assertEqual(len(r.context['daftar']), 1)
        self.assertEqual(r.context['daftar'][0].status, 'DISETUJUI')

    def test_detail_unit_lain_ditolak(self):
        lain = LogbookHarian.objects.create(jenis='RANAP', unit=self.unit_lain,
                                            tanggal=TANGGAL, shift='PAGI')
        self.client.force_login(self.petugas)
        r = self.client.get(reverse('akreditasi:logbook_detail', args=[lain.pk]))
        self.assertEqual(r.status_code, 403)


class BuatLogbookTest(LogbookViewBase):
    def test_buat_logbook_baru(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse('akreditasi:logbook_buat'), {
            'jenis': 'IGD', 'shift': 'SIANG', 'unit': self.unit.pk,
            'tanggal': TANGGAL.isoformat(), 'ruangan': '',
        })
        self.assertEqual(r.status_code, 302)
        lb = LogbookHarian.objects.get(jenis='IGD', shift='SIANG')
        self.assertEqual(lb.status, 'DRAF')
        self.assertTrue(AuditLog.objects.filter(model_name='LogbookHarian').exists())

    def test_buat_dua_kali_tidak_menduplikasi(self):
        self.client.force_login(self.admin)
        for _ in range(2):
            self.client.post(reverse('akreditasi:logbook_buat'), {
                'jenis': 'IGD', 'shift': 'PAGI', 'unit': self.unit.pk,
                'tanggal': TANGGAL.isoformat(), 'ruangan': '',
            })
        self.assertEqual(LogbookHarian.objects.filter(
            jenis='IGD', unit=self.unit, tanggal=TANGGAL, shift='PAGI').count(), 1)

    def test_tanggal_tidak_valid_ditolak(self):
        self.client.force_login(self.admin)
        sebelum = LogbookHarian.objects.count()
        r = self.client.post(reverse('akreditasi:logbook_buat'), {
            'jenis': 'IGD', 'shift': 'PAGI', 'unit': self.unit.pk, 'tanggal': '20-10-2026',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(LogbookHarian.objects.count(), sebelum)

    def test_role_tidak_berwenang_ditolak(self):
        self.client.force_login(self.asesor)
        r = self.client.get(reverse('akreditasi:logbook_buat'))
        self.assertEqual(r.status_code, 403)


class DetailLogbookTest(LogbookViewBase):
    def test_detail_menarik_pasien_dan_checklist(self):
        self.client.force_login(self.petugas)
        r = self.client.get(reverse('akreditasi:logbook_detail', args=[self.logbook.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['rekap']['jumlah_pasien'], 1)
        self.assertTrue(self.logbook.checklist.exists())
        self.assertEqual(r.context['rekap']['rt_rata2'], 3)  # 08.15 → 08.18

    def test_detail_menampilkan_lima_seksi(self):
        self.client.force_login(self.petugas)
        r = self.client.get(reverse('akreditasi:logbook_detail', args=[self.logbook.pk]))
        html = r.content.decode()
        for judul in ('I. Rekap Shift', 'II. Personel', 'III. Checklist',
                      'IV. Kejadian', 'V. Serah Terima'):
            self.assertIn(judul, html)


class SimpanPasienTest(LogbookViewBase):
    def setUp(self):
        super().setUp()
        self.logbook.tarik_pasien()
        self.baris = self.logbook.pasien.get()

    def test_simpan_isian_manual(self):
        self.client.force_login(self.petugas)
        r = self.client.post(reverse('akreditasi:logbook_simpan_pasien', args=[self.logbook.pk]), {
            f'baris_{self.baris.pk}_tindakan': 'EKG 12 lead',
            f'baris_{self.baris.pk}_catatan': 'Nyeri dada berkurang',
            f'baris_{self.baris.pk}_disposisi': 'RAWAT_INAP',
            f'baris_{self.baris.pk}_dependency': 'T',
            f'baris_{self.baris.pk}_jam_keluar': '12:30',
        })
        self.assertEqual(r.status_code, 302)
        self.baris.refresh_from_db()
        self.assertEqual(self.baris.tindakan, 'EKG 12 lead')
        self.assertEqual(self.baris.disposisi, 'RAWAT_INAP')
        self.assertEqual(self.baris.dependency, 'T')
        self.assertEqual(self.baris.jam_keluar, time(12, 30))

    def test_disposisi_tidak_dikenal_diabaikan(self):
        self.client.force_login(self.petugas)
        self.client.post(reverse('akreditasi:logbook_simpan_pasien', args=[self.logbook.pk]), {
            f'baris_{self.baris.pk}_tindakan': 'Observasi',
            f'baris_{self.baris.pk}_disposisi': 'HACK',
        })
        self.baris.refresh_from_db()
        self.assertEqual(self.baris.disposisi, 'RAWAT_INAP')

    def test_logbook_disetujui_tidak_bisa_diubah(self):
        self.logbook.status = 'DISETUJUI'
        self.logbook.save(update_fields=['status'])
        self.client.force_login(self.petugas)
        r = self.client.post(reverse('akreditasi:logbook_simpan_pasien', args=[self.logbook.pk]), {
            f'baris_{self.baris.pk}_tindakan': 'X',
        })
        self.assertEqual(r.status_code, 403)
        self.baris.refresh_from_db()
        self.assertEqual(self.baris.tindakan, '')


class SimpanChecklistTest(LogbookViewBase):
    def setUp(self):
        super().setUp()
        self.logbook.ensure_checklist()
        self.butir = self.logbook.checklist.first()

    def test_simpan_status_dan_keterangan(self):
        self.client.force_login(self.petugas)
        r = self.client.post(reverse('akreditasi:logbook_simpan_checklist', args=[self.logbook.pk]), {
            f'cek_{self.butir.kunci}': 'TERLAKSANA',
            f'ket_{self.butir.kunci}': 'Sudah dicek pukul 07.10',
        })
        self.assertEqual(r.status_code, 302)
        self.butir.refresh_from_db()
        self.assertEqual(self.butir.status, 'TERLAKSANA')
        self.assertIn('07.10', self.butir.keterangan)

    def test_nomor_segel_tersimpan_untuk_butir_yang_butuh(self):
        butir = self.logbook.checklist.filter(butuh_nomor_segel=True).first()
        self.assertIsNotNone(butir, 'checklist harus punya butir bernomor segel')
        self.client.force_login(self.petugas)
        self.client.post(reverse('akreditasi:logbook_simpan_checklist', args=[self.logbook.pk]), {
            f'cek_{butir.kunci}': 'TERLAKSANA',
            f'ket_{butir.kunci}': 'Segel baru',
            f'segel_{butir.kunci}': 'SGL-2026-0091',
        })
        butir.refresh_from_db()
        self.assertEqual(butir.nomor_segel, 'SGL-2026-0091')


class KejadianLogbookTest(LogbookViewBase):
    def test_kejadian_tertulis_ke_insiden_keselamatan(self):
        self.client.force_login(self.petugas)
        r = self.client.post(reverse('akreditasi:logbook_simpan_kejadian', args=[self.logbook.pk]), {
            'jenis_insiden': 'KTD',
            'tingkat_keparahan': 'SENTINEL',
            'waktu_kejadian': '09:30',
            'lokasi_kejadian': 'Ruang resusitasi',
            'deskripsi_kejadian': 'Keterlambatan obat trombolitik',
            'tindakan_segera': 'Lapor DPJP, obat diberikan',
            'pasien_terpapar': 'on',
        })
        self.assertEqual(r.status_code, 302)
        kj = LogbookKejadian.objects.get(logbook=self.logbook)
        self.assertTrue(kj.pasien_terpapar)
        self.assertIsNotNone(kj.insiden_id)
        insiden = InsidenKeselamatan.objects.get(pk=kj.insiden_id)
        self.assertEqual(insiden.unit_id, self.unit.pk)

    def test_field_wajib_kosong_ditolak(self):
        self.client.force_login(self.petugas)
        self.client.post(reverse('akreditasi:logbook_simpan_kejadian', args=[self.logbook.pk]), {
            'jenis_insiden': 'KTD', 'tingkat_keparahan': 'SENTINEL',
            'lokasi_kejadian': '', 'deskripsi_kejadian': '',
        })
        self.assertFalse(LogbookKejadian.objects.exists())

    def test_jenis_insiden_tidak_dikenal_ditolak(self):
        self.client.force_login(self.petugas)
        self.client.post(reverse('akreditasi:logbook_simpan_kejadian', args=[self.logbook.pk]), {
            'jenis_insiden': 'NGARANG', 'tingkat_keparahan': 'SENTINEL',
            'lokasi_kejadian': 'IGD', 'deskripsi_kejadian': 'x',
        })
        self.assertFalse(LogbookKejadian.objects.exists())


class NarasiLogbookTest(LogbookViewBase):
    def test_simpan_personel_dan_sbar(self):
        self.client.force_login(self.petugas)
        r = self.client.post(reverse('akreditasi:logbook_simpan_narasi', args=[self.logbook.pk]), {
            'pj_shift_nama': 'Ns. Ratna',
            'jumlah_perawat': '4',
            'rasio_perawat_pasien': '1:3',
            'pasien_kritis_nama': 'Bed 2 — Tn. S',
            'penunjang_pending': 'CT scan',
            'catatan_shift': 'Ruang penuh, 1 pasien menunggu kamar',
            'sbar_situation': 'IGD terisi 8 pasien',
            'sbar_background': '2 pasien kritis',
            'sbar_assessment': 'Stabil',
            'sbar_recommendation': 'Tambah perawat shift malam',
            'pasien_menunggu_kamar': '2',
        })
        self.assertEqual(r.status_code, 302)
        self.logbook.refresh_from_db()
        self.assertEqual(self.logbook.pj_shift_nama, 'Ns. Ratna')
        self.assertEqual(self.logbook.jumlah_perawat, 4)
        self.assertEqual(self.logbook.pasien_menunggu_kamar, 2)
        self.assertIn('Tambah perawat', self.logbook.sbar_recommendation)

    def test_jumlah_perawat_bukan_angka_diabaikan(self):
        self.client.force_login(self.petugas)
        self.client.post(reverse('akreditasi:logbook_simpan_narasi', args=[self.logbook.pk]), {
            'pj_shift_nama': 'Ns. Ratna', 'jumlah_perawat': 'empat',
        })
        self.logbook.refresh_from_db()
        self.assertIsNone(self.logbook.jumlah_perawat)


class AlurStatusTest(LogbookViewBase):
    def test_serah_terima_tanpa_nama_ditolak(self):
        self.client.force_login(self.petugas)
        self.client.post(reverse('akreditasi:logbook_serah_terima', args=[self.logbook.pk]),
                         {'ttd_perawat': '   '})
        self.logbook.refresh_from_db()
        self.assertEqual(self.logbook.status, 'DRAF')

    def test_serah_terima_lalu_setujui(self):
        self.client.force_login(self.petugas)
        self.client.post(reverse('akreditasi:logbook_serah_terima', args=[self.logbook.pk]),
                         {'ttd_perawat': 'Ns. Ratna'})
        self.logbook.refresh_from_db()
        self.assertEqual(self.logbook.status, 'DIISI')
        self.assertIsNotNone(self.logbook.diserahterimakan_pada)

        self.client.force_login(self.kepala)
        self.client.post(reverse('akreditasi:logbook_setujui', args=[self.logbook.pk]),
                         {'ttd_kepala_ruang': 'dr. Handoko'})
        self.logbook.refresh_from_db()
        self.assertEqual(self.logbook.status, 'DISETUJUI')
        self.assertTrue(self.logbook.terkunci)

    def test_setujui_tanpa_nama_kepala_ditolak(self):
        self.logbook.status = 'DIISI'
        self.logbook.save(update_fields=['status'])
        self.client.force_login(self.kepala)
        self.client.post(reverse('akreditasi:logbook_setujui', args=[self.logbook.pk]),
                         {'ttd_kepala_ruang': ''})
        self.logbook.refresh_from_db()
        self.assertEqual(self.logbook.status, 'DIISI')

    def test_staf_tidak_boleh_mengesahkan(self):
        self.logbook.status = 'DIISI'
        self.logbook.save(update_fields=['status'])
        self.client.force_login(self.petugas)
        r = self.client.post(reverse('akreditasi:logbook_setujui', args=[self.logbook.pk]),
                             {'ttd_kepala_ruang': 'dr. Handoko'})
        self.assertEqual(r.status_code, 403)
        self.logbook.refresh_from_db()
        self.assertEqual(self.logbook.status, 'DIISI')

    def test_serah_terima_get_ditolak(self):
        self.client.force_login(self.petugas)
        r = self.client.get(reverse('akreditasi:logbook_serah_terima', args=[self.logbook.pk]))
        self.assertEqual(r.status_code, 405)


class PdfLogbookTest(LogbookViewBase):
    def test_pdf_landscape_dibuat(self):
        self.logbook.ensure_checklist()
        self.logbook.tarik_pasien()
        self.client.force_login(self.petugas)
        r = self.client.get(reverse('akreditasi:logbook_pdf', args=[self.logbook.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertGreater(len(r.content), 2000)


class ScopingAksesTest(LogbookViewBase):
    def test_petugas_unit_lain_tidak_bisa_menyimpan(self):
        lain = LogbookHarian.objects.create(jenis='RANAP', unit=self.unit_lain,
                                            tanggal=TANGGAL, shift='PAGI')
        self.client.force_login(self.petugas)
        r = self.client.post(reverse('akreditasi:logbook_simpan_narasi', args=[lain.pk]),
                             {'pj_shift_nama': 'Ns. X'})
        self.assertEqual(r.status_code, 403)
        lain.refresh_from_db()
        self.assertEqual(lain.pj_shift_nama, '')
