"""Test view Logbook Harian Non-Medis (daftar & buat)."""

from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from akreditasi.logbook_nonmedis_models import LogbookNonMedis
from akreditasi.models import AuditLog, UnitKerja
from sdm.models import Pegawai


def buat_unit(kode, nama, tipe='BAGIAN', parent=None):
    return UnitKerja.objects.create(code=kode, name=nama, level=2, tipe_unit=tipe, parent=parent)


def buat_user(username, role, unit=None):
    from accounts.models import UserProfile
    u = User.objects.create_user(username, password='x')
    UserProfile.objects.update_or_create(user=u, defaults={'role': role, 'unit_kerja': unit})
    return u


def buat_pegawai(nama):
    return Pegawai.objects.create(nama_lengkap=nama, kategori='NON_PPA', profesi='Administrasi')


class LogbookNonMedisDaftarTest(TestCase):

    def setUp(self):
        self.unit_a = buat_unit('PENDAFTARAN', 'Pendaftaran')
        self.unit_b = buat_unit('KEUANGAN', 'Keuangan')
        self.pegawai_a = buat_pegawai('Budi A')
        self.pegawai_b = buat_pegawai('Budi B')

        self.staf_a = buat_user('staf_a', 'STAF_NAKES', unit=self.unit_a)
        self.staf_b = buat_user('staf_b', 'STAF_NAKES', unit=self.unit_b)
        self.admin = buat_user('admin_nm', 'ADMIN_RS')
        self.asesor = buat_user('asesor_nm', 'ASESOR')

        self.e_a = LogbookNonMedis.objects.create(
            unit=self.unit_a, pegawai=self.pegawai_a, tanggal=date(2026, 11, 9),
            dibuat_oleh=self.staf_a)
        self.e_b = LogbookNonMedis.objects.create(
            unit=self.unit_b, pegawai=self.pegawai_b, tanggal=date(2026, 11, 9),
            dibuat_oleh=self.staf_b)

    def test_url_daftar_200(self):
        self.client.force_login(self.staf_a)
        resp = self.client.get(reverse('akreditasi:logbook_nonmedis_daftar'))
        self.assertEqual(resp.status_code, 200)

    def test_staf_hanya_melihat_unit_sendiri(self):
        self.client.force_login(self.staf_a)
        resp = self.client.get(reverse('akreditasi:logbook_nonmedis_daftar'))
        self.assertContains(resp, 'Pendaftaran')
        self.assertNotContains(resp, 'Keuangan')

    def test_admin_melihat_semua_unit(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('akreditasi:logbook_nonmedis_daftar'))
        self.assertContains(resp, 'Pendaftaran')
        self.assertContains(resp, 'Keuangan')

    def test_buat_logbook_unit_sendiri(self):
        self.client.force_login(self.staf_a)
        resp = self.client.post(reverse('akreditasi:logbook_nonmedis_buat'), {
            'unit': self.unit_a.pk,
            'pegawai': self.pegawai_a.pk,
            'tanggal': '2026-11-10',
            'shift': 'PAGI',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(LogbookNonMedis.objects.filter(unit=self.unit_a, tanggal=date(2026, 11, 10)).exists())

    def test_buat_logbook_unit_lain_ditolak(self):
        self.client.force_login(self.staf_a)
        resp = self.client.post(reverse('akreditasi:logbook_nonmedis_buat'), {
            'unit': self.unit_b.pk,
            'pegawai': self.pegawai_b.pk,
            'tanggal': '2026-11-10',
            'shift': 'PAGI',
        })
        # Unit B di luar lingkup staf A → 404 (get_object_or_404 pada _unit_pilihan)
        self.assertEqual(resp.status_code, 404)


class LogbookNonMedisDetailTest(TestCase):

    def setUp(self):
        self.unit = buat_unit('PENDAFTARAN', 'Pendaftaran')
        self.pegawai = buat_pegawai('Budi A')
        self.staf = buat_user('staf_det', 'STAF_NAKES', unit=self.unit)
        self.kepala = buat_user('kepala_det', 'KEPALA_UNIT', unit=self.unit)
        self.staf_lain = buat_user('staf_lain', 'STAF_NAKES', unit=buat_unit('LAIN', 'Unit Lain'))
        self.entry = LogbookNonMedis.objects.create(
            unit=self.unit, pegawai=self.pegawai, tanggal=date(2026, 11, 9),
            dibuat_oleh=self.staf)
        self.entry.ensure_checklist()

    def test_detail_render_seksi(self):
        self.client.force_login(self.staf)
        resp = self.client.get(reverse('akreditasi:logbook_nonmedis_detail', args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Uraian Aktivitas')
        self.assertContains(resp, 'Kesesuaian Prosedur Layanan dengan SOP')

    def test_detail_unit_lain_403(self):
        self.client.force_login(self.staf_lain)
        resp = self.client.get(reverse('akreditasi:logbook_nonmedis_detail', args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_simpan_checklist(self):
        self.client.force_login(self.staf)
        butir = self.entry.checklist.first()
        resp = self.client.post(
            reverse('akreditasi:logbook_nonmedis_simpan_checklist', args=[self.entry.pk]),
            {f'cek_{butir.kunci}': 'TERLAKSANA', f'ket_{butir.kunci}': 'SOP dipatuhi'})
        self.assertEqual(resp.status_code, 302)
        butir.refresh_from_db()
        self.assertEqual(butir.status, 'TERLAKSANA')
        self.assertEqual(butir.keterangan, 'SOP dipatuhi')

    def test_simpan_narasi_dan_risiko(self):
        self.client.force_login(self.staf)
        resp = self.client.post(
            reverse('akreditasi:logbook_nonmedis_simpan_narasi', args=[self.entry.pk]),
            {'uraian_aktivitas': 'Melayani pendaftaran pasien',
             'target_harian': '100 pasien',
             'risiko_identifikasi': 'Antrian panjang',
             'risiko_mitigasi': 'Tambah loket',
             'fokus_ep_teks': 'MFK 1'})
        self.assertEqual(resp.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.uraian_aktivitas, 'Melayani pendaftaran pasien')
        self.assertEqual(self.entry.risiko_mitigasi, 'Tambah loket')

    def test_unggah_bukti_valid(self):
        self.client.force_login(self.staf)
        berkas = SimpleUploadedFile('laporan.pdf', b'%PDF-1.4 dummy', content_type='application/pdf')
        resp = self.client.post(
            reverse('akreditasi:logbook_nonmedis_unggah_bukti', args=[self.entry.pk]),
            {'judul': 'Laporan Harian', 'berkas': berkas})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.entry.bukti.count(), 1)

    def test_unggah_bukti_ekstensi_ditolak(self):
        self.client.force_login(self.staf)
        berkas = SimpleUploadedFile('virus.exe', b'MZ dummy', content_type='application/octet-stream')
        resp = self.client.post(
            reverse('akreditasi:logbook_nonmedis_unggah_bukti', args=[self.entry.pk]),
            {'judul': 'Jahat', 'berkas': berkas})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.entry.bukti.count(), 0)


class LogbookNonMedisSetujuiTest(TestCase):

    def setUp(self):
        self.unit = buat_unit('PENDAFTARAN', 'Pendaftaran')
        self.unit_lain = buat_unit('LAIN', 'Unit Lain')
        self.pegawai = buat_pegawai('Budi A')
        self.staf = buat_user('staf_stj', 'STAF_NAKES', unit=self.unit)
        self.kepala = buat_user('kepala_stj', 'KEPALA_UNIT', unit=self.unit)
        self.kepala_lain = buat_user('kepala_lain', 'KEPALA_UNIT', unit=self.unit_lain)
        self.entry = LogbookNonMedis.objects.create(
            unit=self.unit, pegawai=self.pegawai, tanggal=date(2026, 11, 9),
            dibuat_oleh=self.staf)

    def test_setujui_staf_403(self):
        self.client.force_login(self.staf)
        resp = self.client.post(
            reverse('akreditasi:logbook_nonmedis_setujui', args=[self.entry.pk]), {})
        self.assertEqual(resp.status_code, 403)

    def test_setujui_kepala_unit_lain_403(self):
        self.client.force_login(self.kepala_lain)
        resp = self.client.post(
            reverse('akreditasi:logbook_nonmedis_setujui', args=[self.entry.pk]), {})
        self.assertEqual(resp.status_code, 403)

    def test_setujui_kepala_unit_sendiri(self):
        self.client.force_login(self.kepala)
        resp = self.client.post(
            reverse('akreditasi:logbook_nonmedis_setujui', args=[self.entry.pk]), {})
        self.assertEqual(resp.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, 'DISETUJUI')
        self.assertTrue(AuditLog.objects.filter(
            model_name='LogbookNonMedis', aksi='UPDATE').exists())

    def test_pdf_200(self):
        self.client.force_login(self.staf)
        resp = self.client.get(reverse('akreditasi:logbook_nonmedis_pdf', args=[self.entry.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
