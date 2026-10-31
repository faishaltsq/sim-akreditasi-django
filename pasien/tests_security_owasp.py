"""OWASP Top 10 (2021) security tests — pasien app.

Mencakup A01 Broken Access Control:
- IDOR data pasien pada pasien_detail / kunjungan_detail (tanpa filter unit).
- Kebocoran PII lintas unit via api_cari_pasien / api_cek_nik.
- Cakupan decorator require_patient_module (mana view yang dijaga, mana yang tidak).

Test yang menemukan kerentanan nyata gagal dengan pesan Indonesia yang
menjelaskan bukti dan dampaknya. Test yang memaku pelindung yang sudah benar
memakai assertion biasa dan lulus.
"""
from django.test import TestCase
from django.urls import reverse

from akreditasi.tests_utils import (
    login, make_kunjungan, make_pasien, make_unit, make_user,
)


class PatientPiiIdorTest(TestCase):
    """pasien_detail / kunjungan_detail membocorkan record lintas unit."""

    def setUp(self):
        # Unit A: IGD (kode memuat 'IGD'). Unit B: rawat inap (kode 'IRIN').
        self.unit_a = make_unit('IGD-AUTHZ', 'Instalasi Gawat Darurat', level=3)
        self.unit_b = make_unit('IRIN-AUTHZ', 'Ruang Rawat Inap', level=4)
        # Staf unit A: perawat IGD, modul = {igd, pendaftaran, ranap, master_pasien, riwayat}.
        self.staf_a = make_user(
            'owasp.staf.igd', 'STAF_NAKES', unit=self.unit_a, profesi='PERAWAT',
        )
        # Pasien + kunjungan milik unit B.
        self.pasien_b = make_pasien(
            'RM-B-001', 'Pasien Unit Lain', nik='3201010101010001',
        )
        self.kunj_b = make_kunjungan(self.pasien_b, 'KJ-B-001', jenis='RANAP')

    def test_pasien_detail_lintas_unit_ditolak(self):
        """Perawat IGD membaca detail pasien unit lain -> harus ditolak."""
        login(self.client, self.staf_a)
        response = self.client.get(
            reverse('pasien:pasien_detail', args=[self.pasien_b.pk])
        )
        if response.status_code == 200:
            self.fail(
                'IDOR DATA PASIEN: perawat unit IGD berhasil membuka detail '
                f'pasien "{self.pasien_b.nama_lengkap}" '
                f'(no_rm={self.pasien_b.no_rm}) yang berada di unit rawat inap '
                'lain melalui pasien:pasien_detail dengan menebak pk. View hanya '
                'memakai @login_required dan get_object_or_404(Pasien, pk=pk) '
                'tanpa pemeriksaan kepemilikan unit. Setiap pengguna yang login '
                'dapat membaca seluruh rekam medis dengan iterasi pk.'
            )
        self.assertIn(response.status_code, (403, 404))

    def test_kunjungan_detail_lintas_unit_ditolak(self):
        """Perawat IGD membaca detail kunjungan unit lain -> harus ditolak."""
        login(self.client, self.staf_a)
        response = self.client.get(
            reverse('pasien:kunjungan_detail', args=[self.kunj_b.pk])
        )
        if response.status_code == 200:
            self.fail(
                'IDOR DATA KUNJUNGAN: perawat IGD berhasil membuka detail '
                f'kunjungan {self.kunj_b.no_kunjungan} milik unit lain melalui '
                'pasien:kunjungan_detail. View hanya dijaga @login_required '
                'tanpa cakupan unit, sehingga data klinis lintas unit '
                '(diagnosa, billing, CPPT, resep) terekspos.'
            )
        self.assertIn(response.status_code, (403, 404))

    def test_anonymous_tidak_dapat_membaca_pasien_detail(self):
        """Akses anonim harus dialihkan ke login (pelindung ada)."""
        response = self.client.get(
            reverse('pasien:pasien_detail', args=[self.pasien_b.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.get('Location', ''))


class PatientSearchApiLeakageTest(TestCase):
    """api_cari_pasien / api_cek_nik membocorkan PII ke user lintas unit."""

    def setUp(self):
        self.unit_igd = make_unit('IGD-PII', 'Instalasi Gawat Darurat', level=3)
        self.unit_farm = make_unit('FARM-PII', 'Instalasi Farmasi', level=3)
        # Apoteker farmasi: modul = {farmasi, master_pasien, riwayat}.
        self.apoteker = make_user(
            'owasp.pii.farmasi', 'STAF_NAKES', unit=self.unit_farm, profesi='APOTEKER',
        )
        self.pasien = make_pasien(
            'RM-PII-001', 'Pasien Rahasia', nik='3201010199990001',
        )

    def test_api_cari_pasien_membocorkan_pii(self):
        """Apoteker menarik PII pasien IGD via pencarian nama."""
        login(self.client, self.apoteker)
        response = self.client.get(
            reverse('pasien:api_cari_pasien'), {'q': 'Pasien Rahasia'}
        )
        self.assertEqual(response.status_code, 200)
        results = response.json().get('results', [])
        if results:
            leaked = results[0]
            self.fail(
                'KEBOCORAN PII LEWAT API: pengguna farmasi berhasil menarik data '
                'pasien melalui pasien:api_cari_pasien. Field yang terekspos: '
                f'nik={leaked.get("nik")!r}, no_rm={leaked.get("no_rm")!r}, '
                f'alamat={leaked.get("alamat")!r}, no_hp={leaked.get("no_hp")!r}, '
                f'no_bpjs={leaked.get("no_bpjs")!r}. Endpoint hanya dijaga '
                '@login_required dan mengembalikan NIK, alamat, nomor HP, dan '
                'nomor BPJS ke setiap pengguna yang login tanpa pemeriksaan '
                'get_allowed_patient_modules() atau cakupan unit.'
            )
        self.assertEqual(results, [])

    def test_api_cek_nik_membocorkan_pii(self):
        """api_cek_nik menyelesaikan NIK sembarang untuk user mana pun."""
        login(self.client, self.apoteker)
        response = self.client.get(
            reverse('pasien:api_cek_nik'), {'nik': '3201010199990001'}
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        if payload.get('exists'):
            pasien = payload.get('pasien', {})
            self.fail(
                'KEBOCORAN PII LEWAT API: pasien:api_cek_nik mengembalikan data '
                f'pasien untuk NIK sembarang (nama={pasien.get("nama")!r}, '
                f'nik={pasien.get("nik")!r}, alamat={pasien.get("alamat")!r}, '
                f'no_bpjs={pasien.get("no_bpjs")!r}). Endpoint dapat dipakai '
                'untuk enumerasi NIK dan pengumpulan data pribadi tanpa batas '
                'unit maupun pembatasan laju.'
            )
        self.assertFalse(payload.get('exists'))

    def test_anonymous_tidak_dapat_memanggil_api_pii(self):
        """Akses anonim ke endpoint PII harus dialihkan ke login."""
        for url_name, params in (
            ('pasien:api_cari_pasien', {'q': 'Pasien'}),
            ('pasien:api_cek_nik', {'nik': '3201010199990001'}),
        ):
            response = self.client.get(reverse(url_name), params)
            self.assertEqual(
                response.status_code, 302,
                f'{url_name} harus mengalihkan pengguna anonim',
            )
            self.assertIn('login', response.get('Location', ''))


class PatientModuleDecoratorCoverageTest(TestCase):
    """require_patient_module ada tetapi tidak dipasang pada view baca inti.

    ``pasien/decorators.py`` mendefinisikan ``require_patient_module`` dan
    ``pasien/views.py`` memasangnya pada sembilan view (farmasi_antrean,
    igd_dashboard, rajal_dashboard, laboratorium_dashboard, dst). View baca inti
    — dashboard, pasien_daftar, pasien_detail, kunjungan_detail, api_cari_pasien,
    api_cek_nik — hanya memakai @login_required.
    """

    def setUp(self):
        self.unit_igd = make_unit('IGD-MOD', 'Instalasi Gawat Darurat', level=3)
        self.unit_farm = make_unit('FARM-MOD', 'Instalasi Farmasi', level=3)
        self.nakes_igd = make_user(
            'owasp.mod.igd', 'STAF_NAKES', unit=self.unit_igd, profesi='PERAWAT',
        )
        self.apoteker = make_user(
            'owasp.mod.farmasi', 'STAF_NAKES', unit=self.unit_farm, profesi='APOTEKER',
        )

    def test_module_matrix_sesuai_ekspektasi_dekorator(self):
        """Memaku himpunan modul yang menjadi dasar uji dekorator."""
        igd_modules = self.nakes_igd.profile.get_allowed_patient_modules()
        self.assertIn('igd', igd_modules)
        self.assertIn('pendaftaran', igd_modules)
        self.assertNotIn('farmasi', igd_modules)
        self.assertNotIn('laboratorium', igd_modules)

        farm_modules = self.apoteker.profile.get_allowed_patient_modules()
        self.assertIn('farmasi', farm_modules)
        self.assertNotIn('igd', farm_modules)
        self.assertNotIn('rajal', farm_modules)

    def test_view_ber_guard_menolak_modul_luar(self):
        """igd_dashboard dijaga @require_patient_module('igd') -> apoteker 403."""
        login(self.client, self.apoteker)
        response = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(
            response.status_code, 403,
            'apoteker tanpa modul igd harus ditolak 403 oleh '
            "@require_patient_module('igd')",
        )

    def test_view_ber_guard_diizinkan_modul_sesuai(self):
        """farmasi_antrean dijaga @require_patient_module('farmasi') -> apoteker 200."""
        login(self.client, self.apoteker)
        response = self.client.get(reverse('pasien:farmasi_antrean'))
        self.assertEqual(
            response.status_code, 200,
            'apoteker harus dapat membuka farmasi_antrean',
        )

    def test_view_baca_inti_tanpa_guard(self):
        """pasien_daftar terbuka untuk modul yang tidak mencakup pendaftaran.

        Apoteker (modul {farmasi, master_pasien, riwayat}) membuka pasien_daftar
        dan mendapat 200, sementara igd_dashboard menolaknya 403. Ini membuktikan
        require_patient_module ada tetapi tidak dipasang pada view baca inti.
        """
        login(self.client, self.apoteker)
        guarded = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(guarded.status_code, 403)
        unguarded = self.client.get(reverse('pasien:pasien_daftar'))
        if unguarded.status_code == 200:
            self.fail(
                'DEKORATOR TIDAK DITERAPKAN: pasien:pasien_daftar mengembalikan '
                'HTTP 200 untuk pengguna yang modulnya tidak mencakup '
                'pendaftaran/igd, sementara pasien:igd_dashboard menolak dengan '
                '403. Ini membuktikan require_patient_module() ada tetapi tidak '
                'dipasang pada view baca inti (dashboard, pasien_daftar, '
                'pasien_detail, kunjungan_daftar, kunjungan_detail, '
                'api_cari_pasien, api_cek_nik).'
            )
        self.assertIn(unguarded.status_code, (403, 404))
