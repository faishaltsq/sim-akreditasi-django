"""Invariant lokasi: badge Ruangan/Bed hanya tampil untuk kunjungan rawat inap.

Sebelumnya ``kunjungan_detail`` menampilkan badge setiap kali ``k.bed`` terpasang,
tanpa memeriksa apakah pasien benar-benar sudah diadmisikan — sehingga kunjungan
IGD yang (secara keliru) masih membawa bed bangsal menampilkan "Bangsal Mawar"
walaupun pasien belum pernah masuk bangsal. Invariantnya adalah: bed adalah
lokasi pasien hanya untuk rawat inap (``bed_aktif``), dan label ruangan tidak
mengulang kelas yang sudah tertulis di nama.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import Bed, KunjunganPasien, Pasien, Ruangan


class RuanganLabelTest(TestCase):
    def test_label_tidak_mengulang_kelas_di_nama(self):
        r = Ruangan(nama='Bangsal Mawar (Kelas I)', kelas='1')
        self.assertEqual(r.label, 'Bangsal Mawar (Kelas I)')

    def test_label_menambah_kelas_bila_belum_ada(self):
        r = Ruangan(nama='Bangsal Dahlia', kelas='2')
        self.assertEqual(r.label, 'Bangsal Dahlia (Kelas II)')

    def test_label_tanpa_kelas(self):
        r = Ruangan(nama='Ruang Resusitasi', kelas='IGD')
        self.assertEqual(r.label, 'Ruang Resusitasi (IGD)')


class BedAktifTest(TestCase):
    def setUp(self):
        self.ruangan = Ruangan.objects.create(
            kode='B-MAWAR', nama='Bangsal Mawar (Kelas I)', kelas='1', jenis='RANAP')
        self.bed = Bed.objects.create(ruangan=self.ruangan, kode_bed='01', status='TERISI')
        self.user = User.objects.create_superuser('lokasiadmin', 'lok@rs.id', 'pw')
        self.client.force_login(self.user)
        self.pasien = Pasien.objects.create(
            no_rm='RM-LOK-001', nik='3201000000000210', nama_lengkap='Pasien Lokasi',
            tanggal_lahir='1988-08-08', jenis_kelamin='L')

    def _visit(self, **kw):
        kw.setdefault('jenis_kunjungan', 'IGD')
        kw.setdefault('no_kunjungan', 'IGD-X')
        kw.setdefault('bed', self.bed)
        return KunjunganPasien.objects.create(
            pasien=self.pasien, tanggal_masuk=timezone.now(), **kw)

    def test_igd_triage_visit_hides_room_badge(self):
        """IGD yang membawa bed (data lama) TIDAK menampilkan badge ruangan."""
        k = self._visit(no_kunjungan='IGD-BED', status='TRIAGE', triage='HIJAU')
        self.assertIsNone(k.bed_aktif)
        res = self.client.get(reverse('pasien:kunjungan_detail', args=[k.pk]))
        self.assertNotContains(res, 'Bangsal Mawar')
        self.assertNotContains(res, 'Ruangan:')

    def test_ranap_visit_shows_room_badge(self):
        """Kunjungan rawat inap menampilkan badge ruangan + bed."""
        k = self._visit(no_kunjungan='RANAP-BED', jenis_kunjungan='RANAP', status='RANAP')
        self.assertIsNotNone(k.bed_aktif)
        res = self.client.get(reverse('pasien:kunjungan_detail', args=[k.pk]))
        self.assertContains(res, 'Bangsal Mawar (Kelas I)')
        self.assertContains(res, f'Bed: <strong>{self.bed.kode_bed}</strong>')

    def test_detail_dan_daftar_dan_pasien_pakai_bed_aktif(self):
        k = self._visit(no_kunjungan='RANAP-BED-2', jenis_kunjungan='RANAP', status='RANAP')
        res_d = self.client.get(reverse('pasien:kunjungan_detail', args=[k.pk]))
        self.assertContains(res_d, 'Bangsal Mawar (Kelas I)')
        res_l = self.client.get(reverse('pasien:kunjungan_daftar'))
        self.assertContains(res_l, 'Bangsal Mawar (Kelas I) / 01')
        res_p = self.client.get(reverse('pasien:pasien_detail', args=[self.pasien.pk]))
        self.assertContains(res_p, 'Bangsal Mawar (Kelas I)')


class AsesmenPageAuthTest(TestCase):
    """Halaman asesmen awal penuh wajib memakai guard unit scope yang sama
    dengan kunjungan_detail (bukan hanya login)."""

    def setUp(self):
        from accounts.models import UserProfile
        from akreditasi.models import UnitKerja
        UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 2})
        self.unit_a = UnitKerja.objects.create(code='POLI-A', name='Poli A', level=4)
        self.unit_b = UnitKerja.objects.create(code='POLI-B', name='Poli B', level=4)
        self.pasien = Pasien.objects.create(
            no_rm='RM-AUTH-001', nik='3201000000000221', nama_lengkap='Pasien Auth',
            tanggal_lahir='1991-01-01', jenis_kelamin='L')
        self.k = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='IGD-AUTH', jenis_kunjungan='IGD',
            unit_kerja=UnitKerja.objects.get(code='IGD'), tanggal_masuk=timezone.now(), status='TRIAGE')
        u = User.objects.create_user('staff.b', 'b@rs.id', 'x')
        UserProfile.objects.create(user=u, role='STAF_NAKES', unit_kerja=self.unit_b)
        self.client.force_login(u)

    def test_asesmen_page_denies_other_unit(self):
        res = self.client.get(reverse('pasien:kunjungan_asesmen_awal', args=[self.k.pk]))
        self.assertEqual(res.status_code, 403)

    def test_save_denies_other_unit(self):
        res = self.client.post(
            reverse('pasien:igd_asesmen_awal_save', args=[self.k.pk]),
            {'anamesis_rps': 'x', 'action_mode': 'draft'})
        self.assertEqual(res.status_code, 403)

    def test_copy_prev_denies_other_unit(self):
        res = self.client.get(
            reverse('pasien:igd_asesmen_copy_prev', args=[self.k.pk]))
        self.assertEqual(res.status_code, 403)
