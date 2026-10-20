"""Regresi dasbor eksekutif 'ARIMA Hospital Integrated Control'.

Yang dijaga di sini:
- halaman hero tampil tanpa sidebar (shell sendiri), sedangkan modul lama tetap
  memakai sidebar;
- unit aktif diambil dari ?unit= dan dihormati, kecuali akun unit-scoped;
- halaman tidak meledak saat belum ada data (tampil "Belum ada data", bukan 0%);
- endpoint ringkasan AI menolak portal asing dan hanya menerima POST;
- anggaran query tetap wajar karena snapshot di-cache.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from akreditasi.models import UnitKerja

User = get_user_model()


class KontrolBaseMixin:
    def setUp(self):
        cache.clear()
        self.unit = UnitKerja.objects.create(
            code='KTRL-1', name='Instalasi Kontrol', level=2, is_active=True)
        self.user = User.objects.create_user('kepala.kontrol', 'kk@rs.id', 'pass123')
        from accounts.models import UserProfile
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=None)
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()


class KontrolHubTest(KontrolBaseMixin, TestCase):
    def test_hub_tampil_tanpa_sidebar(self):
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('Hospital Integrated Control', body)
        # shell sendiri: sidebar desktop & offcanvas milik base.html tidak ikut
        self.assertNotIn('sidebar-desktop', body)
        self.assertNotIn('id="mobileSidebar"', body)
        self.assertIn('static/css/kontrol.', body)

    def test_hub_menampilkan_tiga_subdasbor(self):
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        body = res.content.decode()
        for title in (
            'Integrated Risk &amp; Patient Safety Control',
            'Smart EMR &amp; Clinical Quality STARKES',
            'Electronic Accreditation Document',
        ):
            self.assertIn(title, body)

    def test_hub_tanpa_unit_aktif_memberi_empty_state(self):
        UnitKerja.objects.all().update(is_active=False)
        cache.clear()
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Belum ada unit kerja aktif', res.content.decode())

    def test_anonymous_dialihkan_ke_login(self):
        self.client.logout()
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res['Location'].lower())


class KontrolSubDashboardTest(KontrolBaseMixin, TestCase):
    def test_tiga_subdasbor_terbuka(self):
        for name in ('kontrol_risiko', 'kontrol_emr', 'kontrol_dokumen'):
            with self.subTest(name=name):
                res = self.client.get(reverse(f'akreditasi:{name}'))
                self.assertEqual(res.status_code, 200)
                body = res.content.decode()
                self.assertNotIn('sidebar-desktop', body)
                self.assertIn(reverse('akreditasi:kontrol_hub'), body)
                self.assertIn('kontrol-ai', body)

    def test_tanpa_data_tidak_menampilkan_nol_persen(self):
        """Empty ≠ zero: tanpa denominator, cakupan EP harus '—', bukan 0%."""
        res = self.client.get(reverse('akreditasi:kontrol_dokumen'))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertNotIn('<strong class="kpi-value">0%</strong>', body)
        self.assertIn('gauge', body)

    def test_unit_scoped_dipaksa_ke_unitnya(self):
        other = UnitKerja.objects.create(
            code='KTRL-2', name='Unit Lain', level=2, is_active=True)
        profile = self.user.profile
        profile.role = 'KEPALA_UNIT'
        profile.unit_kerja = self.unit
        profile.save()
        cache.clear()

        res = self.client.get(
            reverse('akreditasi:kontrol_risiko'), {'unit': other.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['unit'].pk, self.unit.pk)


class KontrolQueryBudgetTest(KontrolBaseMixin, TestCase):
    """Snapshot di-cache 60 detik: request kedua tidak boleh menembak DB lagi."""

    BUDGET = 12

    def _queries(self, url):
        self.client.get(url)  # hangatkan snapshot & daftar unit
        with CaptureQueriesContext(connection) as ctx:
            res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        return len(ctx.captured_queries)

    def test_subdasbor_setelah_cache_hangat(self):
        used = self._queries(reverse('akreditasi:kontrol_emr'))
        self.assertLessEqual(used, self.BUDGET, f'{used} query, anggaran {self.BUDGET}')

    def test_hub_setelah_cache_hangat(self):
        used = self._queries(reverse('akreditasi:kontrol_hub'))
        self.assertLessEqual(used, self.BUDGET, f'{used} query, anggaran {self.BUDGET}')


class KontrolRingkasanAiTest(KontrolBaseMixin, TestCase):
    def test_get_ditolak(self):
        res = self.client.get(reverse('akreditasi:kontrol_ringkasan_ai'))
        self.assertEqual(res.status_code, 405)

    def test_portal_asing_ditolak(self):
        res = self.client.post(
            reverse('akreditasi:kontrol_ringkasan_ai'), {'portal': 'asing'})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])

    def test_anonymous_tidak_bisa_menembak(self):
        self.client.logout()
        res = self.client.post(
            reverse('akreditasi:kontrol_ringkasan_ai'), {'portal': 'risiko'})
        self.assertEqual(res.status_code, 302)


class SampleUnitTest(TestCase):
    def test_unit_dengan_data_didahulukan(self):
        from akreditasi.kontrol_data import sample_units
        from akreditasi.risiko_models import RisikoUnit

        kosong = UnitKerja.objects.create(
            code='AAA-KOSONG', name='Tanpa Data', level=1, is_active=True)
        berisi = UnitKerja.objects.create(
            code='ZZZ-BERISI', name='Punya Risiko', level=3, is_active=True)
        RisikoUnit.objects.create(
            unit=berisi, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='KLINIS', jenis_risiko='Risiko uji',
            deskripsi_risiko='Uji dasbor', dampak=3, probabilitas=3,
            strategi_mitigasi='KURANGI', rencana_aksi='Pantau',
            pj_mitigasi='Kepala Unit')
        cache.clear()
        units = sample_units(1000)
        self.assertIn(berisi.pk, [u.pk for u in units])
        # unit tanpa risiko/indikator/EP tidak boleh masuk 'Unit Contoh'
        self.assertNotIn(kosong.pk, [u.pk for u in units])
