"""Scope unit pada modul pasien: alur front-office dan pemetaan jenis→unit.

Latar belakang bug: petugas pendaftaran mengklik "Detail" pada pasien yang baru
ia daftarkan dan menerima 403, walaupun dasbor pendaftaran menampilkan pasien
itu beserta tautannya. Penyebabnya dua lapis aturan yang saling bertentangan:

1. ``UserProfile.get_allowed_patient_modules`` memberi semua pengguna login
   modul ``master_pasien`` (indeks identitas pasien bersifat rumah-sakit-luas).
2. ``pasien_detail`` menolak berdasarkan unit kepemilikan kunjungan. Kunjungan
   yang baru didaftarkan punya ``unit_kerja`` kosong, dan pemetaan
   jenis→unit hanya mencari kata 'IGD'/'RAJAL'/'RANAP' di dalam kode unit
   petugas — tidak pernah cocok untuk 'PENDAFTARAN-ADMISSION', 'IRJ', atau
   'POLI-ANAK'.

Tes di sini mengunci pembagian wewenang yang benar: front-office boleh membaca
IDENTITAS pasien seluruh RS, tetapi REKAM KLINIS tetap dibatasi unit.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien


class _ScopeFixtures(TestCase):
    password = 'pass123-rahasia'

    def setUp(self):
        self.unit_pendaftaran = UnitKerja.objects.get_or_create(
            code='PENDAFTARAN-ADMISSION',
            defaults={'name': 'Unit Pendaftaran & Admission', 'level': 4})[0]
        self.unit_igd = UnitKerja.objects.get_or_create(
            code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})[0]
        self.unit_irj = UnitKerja.objects.get_or_create(
            code='IRJ', defaults={'name': 'Instalasi Rawat Jalan', 'level': 3})[0]
        self.unit_irin = UnitKerja.objects.get_or_create(
            code='IRIN', defaults={'name': 'Instalasi Rawat Inap', 'level': 2})[0]

        self.petugas = self._user('petugas.daftar', 'STAF_NON_NAKES',
                                  self.unit_pendaftaran)
        self.petugas_irj = self._user('petugas.irj', 'STAF_NON_NAKES', self.unit_irj)
        self.petugas_irin = self._user('petugas.irin', 'STAF_NAKES', self.unit_irin)

        self.pasien = Pasien.objects.create(
            no_rm='RM-SCOPE-001', nik='3201010101010099',
            nama_lengkap='Pasien Baru Pendaftaran',
            tanggal_lahir=timezone.localdate() - timedelta(days=365 * 30),
            jenis_kelamin='L', alamat='Jl. Uji No. 1', no_hp='081200000000',
        )
        # Kunjungan yang baru didaftarkan: belum dirouting, unit_kerja kosong.
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='KJ-SCOPE-001',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(), status='DAFTAR',
        )

    def _user(self, username, role, unit):
        user = User.objects.create_user(
            username=username, email=f'{username}@rs.test', password=self.password)
        UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
        return user

    def _login(self, username):
        self.assertTrue(
            self.client.login(username=username, password=self.password))

    def _routing_ke_igd(self):
        self.kunjungan.jenis_kunjungan = 'IGD'
        self.kunjungan.unit_kerja = self.unit_igd
        self.kunjungan.save(update_fields=['jenis_kunjungan', 'unit_kerja'])


class FrontOfficePatientDetailTest(_ScopeFixtures):
    """Petugas pendaftaran harus bisa membuka identitas pasien yang ia daftarkan."""

    def test_detail_pasien_kunjungan_belum_dirouting(self):
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_detail_pasien_kunjungan_sudah_dirouting_ke_igd(self):
        self._routing_ke_igd()
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_daftar_pasien_menampilkan_seluruh_indeks_identitas(self):
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pasien_daftar'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.pasien.no_rm)

    def test_rekam_klinis_kunjungan_lain_tetap_ditolak(self):
        """Front-office memegang identitas pasien, BUKAN rekam klinis unit lain."""
        self._routing_ke_igd()
        self._login('petugas.daftar')
        resp = self.client.get(
            reverse('pasien:kunjungan_detail', args=[self.kunjungan.pk]))
        self.assertIn(resp.status_code, (403, 404))

    def test_tombol_detail_rekam_medis_tidak_ditawarkan(self):
        """Dasbor tidak boleh menampilkan tautan yang pasti berakhir 403."""
        self._routing_ke_igd()
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['boleh_detail_igd'])


class JenisUnitTokenTest(_ScopeFixtures):
    """Pemetaan jenis→unit harus memakai kode unit nyata (IRJ/POLI/IRIN)."""

    def test_petugas_irj_melihat_kunjungan_rajal_tanpa_unit(self):
        self._login('petugas.irj')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_petugas_irin_tidak_melihat_kunjungan_rajal_tanpa_unit(self):
        self._login('petugas.irin')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertIn(resp.status_code, (403, 404))

    def test_poliklinik_anak_melihat_kunjungan_rajal_tanpa_unit(self):
        """Sub-unit poliklinik (L4) mewarisi wewenang RAJAL dari induknya."""
        poli = UnitKerja.objects.get_or_create(
            code='POLI-SCOPE-ANAK',
            defaults={'name': 'Poliklinik Anak (uji)', 'level': 4,
                      'parent': self.unit_irj})[0]
        user = self._user('dokter.poli', 'STAF_NAKES', poli)
        self.assertTrue(self.client.login(
            username=user.username, password=self.password))
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_petugas_irj_tidak_bisa_buka_rekam_klinis_igd(self):
        self._routing_ke_igd()
        self._login('petugas.irj')
        resp = self.client.get(
            reverse('pasien:kunjungan_detail', args=[self.kunjungan.pk]))
        self.assertIn(resp.status_code, (403, 404))
