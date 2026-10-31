"""Object-level authorization tests for the pasien (patient) module.

``pasien/decorators.py`` defines ``require_patient_module(module_name)``, which
consults ``UserProfile.get_allowed_patient_modules()`` and raises
``PermissionDenied`` (403) when the module is outside the caller's unit/profesi
scope. ``pasien/views.py`` imports it at line 9.

The decorator is applied to only nine views::

    464  @require_patient_module('ranap')         bed_management
    604  @require_patient_module('farmasi')       farmasi_antrean
    751  @require_patient_module('pendaftaran')   pendaftaran_dashboard
    914  @require_patient_module('igd')           igd_dashboard
    1060 @require_patient_module('rajal')         rajal_dashboard
    1523 @require_patient_module('laboratorium')  laboratorium_dashboard
    1552 @require_patient_module('laboratorium')  order_penunjang_update
    1572 @require_patient_module('pendaftaran')   fast_track_igd
    1658 @require_patient_module('pendaftaran')   kunjungan_batal

Every core *read* view — ``dashboard``, ``pasien_daftar``, ``pasien_detail``,
``pasien_daftar_baru``, ``kunjungan_daftar``, ``kunjungan_detail``,
``kunjungan_baru``, ``api_cari_pasien``, ``api_cek_nik``, ``resume_pdf`` and the
``cetak_*`` family — carries only ``@login_required``. This module pins the
guarded views and documents the unguarded ones.

Note on scope semantics: ``get_allowed_patient_modules()`` gates by *module*
(clinical function), not by the unit that owns a particular record. Even the
guarded views therefore do not prevent a user in unit A from reading a record
belonging to unit B, provided both units map to the same module. That
horizontal gap is asserted separately below.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien


class _PatientFixturesMixin:
    password = 'pass123-rahasia'

    def _unit(self, code, name, level=3, parent=None):
        return UnitKerja.objects.create(
            code=code, name=name, level=level, parent=parent
        )

    def _make_user(self, username, role, *, unit=None, profesi=''):
        user = User.objects.create_user(
            username=username, email=f'{username}@rs.test', password=self.password
        )
        UserProfile.objects.create(
            user=user, role=role, unit_kerja=unit, profesi=profesi
        )
        return user

    def _make_pasien(self, no_rm, nama, nik=''):
        return Pasien.objects.create(
            no_rm=no_rm,
            nik=nik,
            nama_lengkap=nama,
            tanggal_lahir=timezone.localdate() - timedelta(days=365 * 40),
            jenis_kelamin='L',
            alamat='Jl. Rahasia No. 1',
            no_hp='081234567890',
            no_bpjs='0001234567890',
        )

    def _make_kunjungan(self, pasien, no_kunjungan, jenis='RANAP'):
        return KunjunganPasien.objects.create(
            pasien=pasien,
            no_kunjungan=no_kunjungan,
            jenis_kunjungan=jenis,
            tanggal_masuk=timezone.now(),
            status='DAFTAR',
        )

    def _login(self, user):
        self.assertTrue(
            self.client.login(username=user.username, password=self.password),
            f'login gagal untuk {user.username}',
        )


class PatientIdorTest(_PatientFixturesMixin, TestCase):
    """pasien_detail / kunjungan_detail expose records outside the caller's unit."""

    def setUp(self):
        # Unit A: IGD. Unit B: rawat inap (different clinical function).
        self.unit_igd = self._unit('IGD-AUTHZ', 'Instalasi Gawat Darurat', level=3)
        self.unit_ranap = self._unit('IRIN-AUTHZ', 'Ruang Rawat Inap', level=4)

        # Low-privilege nurse scoped to IGD only.
        self.nakes_igd = self._make_user(
            'nakes.igd', 'STAF_NAKES', unit=self.unit_igd, profesi='PERAWAT'
        )
        # Patient + visit belonging to the *other* unit.
        self.pasien_b = self._make_pasien('RM-B-001', 'Pasien Unit Lain', nik='3201010101010001')
        self.kunjungan_b = self._make_kunjungan(self.pasien_b, 'KJ-B-001', jenis='RANAP')

    def test_nakes_igd_cannot_read_pasien_detail_outside_unit(self):
        """A record outside the caller's unit must not be readable."""
        self._login(self.nakes_igd)
        response = self.client.get(
            reverse('pasien:pasien_detail', args=[self.pasien_b.pk])
        )
        if response.status_code == 200:
            self.fail(
                'IDOR DATA PASIEN: perawat unit IGD berhasil membuka detail '
                f'pasien "{self.pasien_b.nama_lengkap}" (no_rm={self.pasien_b.no_rm}) '
                'yang berada di unit rawat inap lain, melalui pasien:pasien_detail '
                'dengan menebak pk. View ini hanya memakai @login_required dan '
                'get_object_or_404(Pasien, pk=pk) tanpa pemeriksaan kepemilikan '
                'unit maupun panggilan require_patient_module(). Setiap pengguna '
                'yang login dapat membaca seluruh rekam medis dengan iterasi pk.'
            )
        self.assertIn(response.status_code, (403, 404))

    def test_nakes_igd_cannot_read_kunjungan_detail_outside_unit(self):
        """The visit detail view has the same gap."""
        self._login(self.nakes_igd)
        response = self.client.get(
            reverse('pasien:kunjungan_detail', args=[self.kunjungan_b.pk])
        )
        if response.status_code == 200:
            self.fail(
                'IDOR DATA KUNJUNGAN: perawat IGD berhasil membuka detail '
                f'kunjungan {self.kunjungan_b.no_kunjungan} milik unit lain '
                'melalui pasien:kunjungan_detail. View hanya dijaga '
                '@login_required tanpa cakupan unit, sehingga data klinis lintas '
                'unit (diagnosa, billing, CPPT) terekspos.'
            )
        self.assertIn(response.status_code, (403, 404))

    def test_pasien_daftar_lists_all_patients_regardless_of_unit(self):
        """The patient index must not enumerate the whole hospital."""
        self._login(self.nakes_igd)
        response = self.client.get(reverse('pasien:pasien_daftar'))
        self.assertEqual(response.status_code, 200)
        if self.pasien_b.no_rm in response.content.decode('utf-8'):
            self.fail(
                'ENUMERASI PASIEN: pasien:pasien_daftar menampilkan pasien '
                f'{self.pasien_b.no_rm} dari unit lain kepada perawat IGD. '
                'View memakai Pasien.objects.all() tanpa penyaringan unit.'
            )

    def test_anonymous_cannot_read_pasien_detail(self):
        """Anonymous access must redirect to login (guard is present)."""
        response = self.client.get(
            reverse('pasien:pasien_detail', args=[self.pasien_b.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.get('Location', ''))


class PatientPiiApiTest(_PatientFixturesMixin, TestCase):
    """api_cari_pasien / api_cek_nik leak PII to any authenticated user."""

    def setUp(self):
        self.unit_igd = self._unit('IGD-PII', 'Instalasi Gawat Darurat', level=3)
        self.unit_farm = self._unit('FARM-PII', 'Instalasi Farmasi', level=3)
        self.nakes_farmasi = self._make_user(
            'nakes.farmasi', 'STAF_NAKES', unit=self.unit_farm, profesi='APOTEKER'
        )
        self.pasien = self._make_pasien(
            'RM-PII-001', 'Pasien Rahasia', nik='3201010199990001'
        )

    def test_api_cari_pasien_leaks_pii_across_modules(self):
        """A pharmacy user must not pull IGD patient PII by name search."""
        self._login(self.nakes_farmasi)
        response = self.client.get(
            reverse('pasien:api_cari_pasien'), {'q': 'Pasien Rahasia'}
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        results = payload.get('results', [])
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
                'get_allowed_patient_modules().'
            )
        self.assertEqual(results, [])

    def test_api_cek_nik_leaks_pii(self):
        """api_cek_nik must not resolve an arbitrary NIK for any user."""
        self._login(self.nakes_farmasi)
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

    def test_anonymous_cannot_call_pii_api(self):
        """Anonymous access to the PII endpoints must redirect to login."""
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


class PatientModuleScopeTest(_PatientFixturesMixin, TestCase):
    """Which pasien views honour require_patient_module, and which do not."""

    def setUp(self):
        self.unit_igd = self._unit('IGD-MOD', 'Instalasi Gawat Darurat', level=3)
        self.unit_farm = self._unit('FARM-MOD', 'Instalasi Farmasi', level=3)

        # IGD nurse: allowed = {igd, pendaftaran, ranap, master_pasien, riwayat}
        self.nakes_igd = self._make_user(
            'mod.igd', 'STAF_NAKES', unit=self.unit_igd, profesi='PERAWAT'
        )
        # Pharmacy apoteker: allowed = {farmasi, master_pasien, riwayat}
        self.apoteker = self._make_user(
            'mod.farmasi', 'STAF_NAKES', unit=self.unit_farm, profesi='APOTEKER'
        )

    def test_module_matrix_matches_decorator_expectations(self):
        """Pin the module sets the decorator tests rely on."""
        igd_modules = self.nakes_igd.profile.get_allowed_patient_modules()
        self.assertIn('igd', igd_modules)
        self.assertIn('pendaftaran', igd_modules)
        self.assertNotIn('farmasi', igd_modules)
        self.assertNotIn('laboratorium', igd_modules)

        farm_modules = self.apoteker.profile.get_allowed_patient_modules()
        self.assertIn('farmasi', farm_modules)
        self.assertNotIn('igd', farm_modules)
        self.assertNotIn('rajal', farm_modules)

    def test_farmasi_view_is_guarded(self):
        """farmasi_antrean carries @require_patient_module('farmasi')."""
        self._login(self.apoteker)
        response = self.client.get(reverse('pasien:farmasi_antrean'))
        self.assertEqual(
            response.status_code, 200,
            'apoteker harus dapat membuka farmasi_antrean',
        )

    def test_igd_view_is_guarded_against_pharmacy_user(self):
        """igd_dashboard must reject a user whose modules exclude 'igd'."""
        self._login(self.apoteker)
        response = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(
            response.status_code, 403,
            'apoteker tanpa modul igd harus ditolak 403 oleh '
            '@require_patient_module("igd")',
        )

    def test_farmasi_view_is_guarded_against_igd_user(self):
        """farmasi_antrean must reject a user whose modules exclude 'farmasi'."""
        self._login(self.nakes_igd)
        response = self.client.get(reverse('pasien:farmasi_antrean'))
        self.assertEqual(
            response.status_code, 403,
            'perawat IGD tanpa modul farmasi harus ditolak 403 oleh '
            '@require_patient_module("farmasi")',
        )

    def test_core_read_views_are_unguarded(self):
        """pasien_detail must be module-scoped but is not.

        A pharmacy user's allowed set is {farmasi, master_pasien, riwayat}. The
        patient detail view is the 'master_pasien' index, which the pharmacy
        user legitimately holds, so this test instead proves the *absence* of
        any decorator by driving a view whose module the caller lacks.
        """
        self._login(self.apoteker)
        # igd_dashboard is guarded and returns 403 (pinned above). The core read
        # views return 200 for the same caller, proving they carry no module gate.
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
                'pasien_detail, kunjungan_daftar, kunjungan_detail, kunjungan_baru, '
                'api_cari_pasien, api_cek_nik).'
            )
        self.assertIn(unguarded.status_code, (403, 404))

    def test_dashboard_is_unguarded(self):
        """The module dashboard itself carries no patient-module gate."""
        self._login(self.apoteker)
        response = self.client.get(reverse('pasien:dashboard'))
        if response.status_code == 200:
            self.fail(
                'DEKORATOR TIDAK DITERAPKAN: pasien:dashboard terbuka (HTTP 200) '
                'untuk pengguna farmasi tanpa modul dashboard terkait. View hanya '
                'memakai @login_required.'
            )
        self.assertIn(response.status_code, (403, 404))
