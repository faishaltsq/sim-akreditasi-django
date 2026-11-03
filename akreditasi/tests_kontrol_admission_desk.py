"""Kontrak dasbor Integrated Control untuk loket Pendaftaran & Admission.

Loket bukan unit klinis: layanan dan KPI dibaca RS-wide, pintasan pendaftaran
muncul lewat entitlement, dan aksi baris SEP tidak boleh bisa dipicu GET.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien


def _pasien(no_rm):
    return Pasien.objects.create(
        no_rm=no_rm, nama_lengkap='Pasien ' + no_rm,
        tanggal_lahir='1990-01-01', jenis_kelamin='L')


class AdmissionDeskDashboardTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.unit, _ = UnitKerja.objects.get_or_create(
            code='ADMISI',
            defaults={'name': 'Unit Pendaftaran & Admisi Pasien', 'level': 4})
        user = get_user_model().objects.create_user('desk-dash')
        UserProfile.objects.create(user=user, role='STAF', unit_kerja=self.unit)
        self.client.force_login(user)
        cache.clear()

    def _emr(self):
        return self.client.get(
            reverse('akreditasi:kontrol_emr'), {'unit': self.unit.pk})

    def test_desk_copy_states_hospital_scope(self):
        body = self._emr().content.decode()
        self.assertIn('mencakup seluruh rumah sakit', body)
        self.assertNotIn('belum memiliki pemetaan layanan klinis', body)

    def test_active_visits_kpi_links_to_daily_list(self):
        KunjunganPasien.objects.create(
            pasien=_pasien('RM-KPI'), no_kunjungan='KPI-1',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            poliklinik='Poli Penyakit Dalam', status='DAFTAR')
        res = self._emr()
        self.assertContains(res, 'data-kpi-link="layanan"')
        self.assertContains(res, reverse('akreditasi:kontrol_layanan'))

    def test_active_visits_kpi_unlinked_when_zero(self):
        res = self._emr()
        self.assertNotContains(res, 'data-kpi-link="layanan"')

    def test_sep_action_is_post_only_for_bpjs_rows(self):
        k = KunjunganPasien.objects.create(
            pasien=_pasien('RM-SEP'), no_kunjungan='SEP-1',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            poliklinik='Poli Penyakit Dalam', penjamin='BPJS',
            status='DAFTAR')
        body = self.client.get(
            reverse('akreditasi:kontrol_layanan'),
            {'unit': self.unit.pk}).content.decode()
        sep_url = reverse('pasien:bpjs_buat_sep', args=[k.pk])
        self.assertIn(f'action="{sep_url}"', body)
        self.assertIn('method="post"', body.lower())
        self.assertIn(reverse('pasien:kunjungan_detail', args=[k.pk]), body)

    def test_sep_action_omitted_for_non_bpjs_rows(self):
        k = KunjunganPasien.objects.create(
            pasien=_pasien('RM-UMUM'), no_kunjungan='UMUM-1',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            poliklinik='Poli Penyakit Dalam', penjamin='UMUM',
            status='DAFTAR')
        body = self.client.get(
            reverse('akreditasi:kontrol_layanan'),
            {'unit': self.unit.pk}).content.decode()
        sep_url = reverse('pasien:bpjs_buat_sep', args=[k.pk])
        self.assertNotIn(sep_url, body)
        self.assertIn(reverse('pasien:kunjungan_detail', args=[k.pk]), body)

    def test_staff_panel_lists_placed_employees(self):
        from sdm.models import Pegawai, PenempatanPegawai

        pegawai = Pegawai.objects.create(
            nama_lengkap='Petugas Uji', kategori='NON_PPA')
        PenempatanPegawai.objects.create(
            pegawai=pegawai, unit_kerja=self.unit,
            tanggal_mulai=date(2025, 1, 1), alokasi_fte=1)
        body = self._emr().content.decode()
        self.assertIn('Petugas Uji', body)

    def test_staff_panel_empty_state_without_placement(self):
        body = self._emr().content.decode()
        self.assertIn('Belum ada petugas yang ditempatkan', body)

    # Pintasan `Akses modul` dan gerbang entitlement-nya diuji di
    # `akreditasi/tests_kontrol_workspace.py` (rumah yang benar untuk
    # `module_actions`); tidak diduplikasi di sini.
