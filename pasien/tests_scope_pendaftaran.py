"""Scope unit pada modul pasien: front-office dan kepemilikan pasien.

Latar belakang bug: petugas pendaftaran mengklik "Detail" pada pasien yang baru
ia daftarkan dan menerima 403, walaupun dasbor pendaftaran menampilkan pasien
itu beserta tautannya. Akar masalahnya: aturan "pasien ini milik unit mana"
ditulis ulang di beberapa tempat dengan cara berbeda, dan pemetaan lama hanya
mencari kata 'IGD'/'RAJAL'/'RANAP' di dalam kode unit — yang tidak pernah cocok
dengan kode unit nyata seperti 'PENDAFTARAN-ADMISSION', 'IRJ', atau 'POLI-ANAK'.

Aturan sekarang: satu pengguna melihat pasien yang kunjungannya sedang dilayani
oleh unitnya (atau turunannya). Kepemilikan dihitung oleh
``akreditasi.layanan_unit`` dari poliklinik/ruangan kunjungan — peta yang sama
dipakui blok LAYANAN dan angka EMR dasbor akreditasi. Unit front-office tidak
dikecualikan: pasien yang baru mereka daftarkan memang sedang berada di unit
mereka.

Yang dikunci di sini: front-office tetap terbatas unit, dan kunjungan yang
sudah dirouting keluar dari unitnya (ke POLI/IGD) ikut hilang dari pandangannya.
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
        # Poliklinik di bawah IRJ — unit yang benar-benar melayani RAJAL.
        self.unit_poli = UnitKerja.objects.get_or_create(
            code='POLI-SCOPE-ANAK',
            defaults={'name': 'Poliklinik Anak', 'level': 4,
                      'parent': self.unit_irj})[0]

        self.petugas = self._user('petugas.daftar', 'STAF_NON_NAKES',
                                  self.unit_pendaftaran)
        self.petugas_poli = self._user('dokter.poli', 'STAF_NAKES', self.unit_poli)
        self.petugas_irin = self._user('petugas.irin', 'STAF_NAKES', self.unit_irin)

        self.pasien = Pasien.objects.create(
            no_rm='RM-SCOPE-001', nik='3201010101010099',
            nama_lengkap='Pasien Baru Pendaftaran',
            tanggal_lahir=timezone.localdate() - timedelta(days=365 * 30),
            jenis_kelamin='L', alamat='Jl. Uji No. 1', no_hp='081200000000',
        )
        # Kunjungan yang baru didaftarkan: ``kunjungan_baru`` menstempel
        # unit_kerja ke unit petugas pendaftar (pasien/views.py), jadi fixture
        # harus meniru itu supaya menguji alur nyata, bukan jalur lain.
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='KJ-SCOPE-001',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(), status='DAFTAR',
            unit_kerja=self.unit_pendaftaran,
        )

    def _user(self, username, role, unit):
        user = User.objects.create_user(
            username=username, email=f'{username}@rs.test', password=self.password)
        UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
        return user

    def _login(self, username):
        self.assertTrue(
            self.client.login(username=username, password=self.password))

    def _routing_ke_poli(self):
        """Pasien diarahkan ke poliklinik — kepemilikan pindah ke POLI.

        Stamp unit pendaftaran dilepas: di alur nyata ``pendaftaran_route``
        tidak menstempel ulang, sehingga kepemilikan harus berasal dari
        poliklinik. Kalau stamp lama dipertahankan, tes ini hanya menguji
        fallback ``unit_kerja``, bukan kepemilikan poliklinik.
        """
        self.kunjungan.poliklinik = 'Poliklinik Anak'
        self.kunjungan.status = 'ASESMEN'
        self.kunjungan.unit_kerja = None
        self.kunjungan.save(update_fields=['poliklinik', 'status', 'unit_kerja'])

    def _routing_ke_igd(self):
        self.kunjungan.jenis_kunjungan = 'IGD'
        self.kunjungan.unit_kerja = self.unit_igd
        self.kunjungan.save(update_fields=['jenis_kunjungan', 'unit_kerja'])


class FrontOfficePatientDetailTest(_ScopeFixtures):
    """Petugas pendaftaran melihat pasien yang sedang berada di unitnya."""

    def test_detail_pasien_kunjungan_belum_dirouting(self):
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_daftar_pasien_menampilkan_pasien_di_unit_sendiri(self):
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pasien_daftar'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.pasien.no_rm)

    def test_pasien_milik_unit_lain_tidak_muncul(self):
        """Pendaftaran tidak boleh melihat pasien yang sedang di poliklinik lain."""
        self._routing_ke_poli()
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pasien_daftar'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.pasien.no_rm)

    def test_pasien_milik_unit_lain_ditolak_lewat_url_langsung(self):
        self._routing_ke_poli()
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertIn(resp.status_code, (403, 404))

    def test_rekam_klinis_kunjungan_unit_lain_tetap_ditolak(self):
        """Front-office memegang identitas pasien, BUKAN rekam klinis unit lain."""
        self._routing_ke_poli()
        self._login('petugas.daftar')
        resp = self.client.get(
            reverse('pasien:kunjungan_detail', args=[self.kunjungan.pk]))
        self.assertIn(resp.status_code, (403, 404))

    def test_rekam_klinis_kunjungan_unit_sendiri_boleh(self):
        """Kunjungan yang unitnya masih unit pendaftaran boleh dibuka rekamnya.

        Konsisten dengan aturan baru: unit front-office tidak dikecualikan dari
        pembatasan unit, dan kunjungan baru memang sedang berada di unit mereka.
        """
        self._login('petugas.daftar')
        resp = self.client.get(
            reverse('pasien:kunjungan_detail', args=[self.kunjungan.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_dasbor_hanya_menampilkan_kunjungan_unit_sendiri(self):
        """Tidak ada tombol Detail yang berakhir 403: daftar sudah disaring."""
        self._routing_ke_poli()
        self._login('petugas.daftar')
        resp = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.kunjungan.pk,
                         [k.pk for k in resp.context['kunjungan_hari_ini']])


class PoliOwnershipTest(_ScopeFixtures):
    """Kepemilikan mengikuti poliklinik, bukan jenis kunjungan."""

    def test_poliklinik_pemilik_melihat_pasiennya(self):
        self._routing_ke_poli()
        self._login('dokter.poli')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_poliklinik_lain_tidak_melihat_pasien_poli_anak(self):
        self._routing_ke_poli()
        self._login('petugas.irin')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertIn(resp.status_code, (403, 404))

    def test_petugas_irj_melihat_seluruh_poliklinik_dibawahnya(self):
        """IRJ adalah induk POLI-SCOPE-ANAK, jadi melihat kunjungan poliklinik itu."""
        self._routing_ke_poli()
        user = self._user('kepala.irj', 'STAF_NAKES', self.unit_irj)
        self.assertTrue(self.client.login(
            username=user.username, password=self.password))
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_poli_tidak_bisa_buka_rekam_klinis_igd(self):
        self._routing_ke_igd()
        self._login('dokter.poli')
        resp = self.client.get(
            reverse('pasien:kunjungan_detail', args=[self.kunjungan.pk]))
        self.assertIn(resp.status_code, (403, 404))

    def test_pasien_sudah_pulang_tidak_lagi_milik_unit(self):
        """Kunjungan berstatus selesai tidak lagi menjadi beban unit mana pun."""
        self._routing_ke_poli()
        self.kunjungan.status = 'PULANG'
        self.kunjungan.tanggal_keluar = timezone.now()
        self.kunjungan.save(update_fields=['status', 'tanggal_keluar'])
        self._login('dokter.poli')
        resp = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertIn(resp.status_code, (403, 404))
