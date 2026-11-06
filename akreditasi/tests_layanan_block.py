"""Blok LAYANAN dasbor kontrol harus memakai resolver kepemilikan yang sama
dengan front-office, dasbor unit, dan EMR (``layanan_unit.visit_unit_code``).

Sebelumnya blok ini punya aturan sendiri — peta poliklinik menang atas stempel
``unit_kerja`` — sehingga kunjungan yang baru didaftarkan (masih di loket
admisi, poliklinik sudah dipilih) muncul di layanan poliklinik tujuan. Satu
pasien terlihat di dua unit, dan front-office kehilangan kunjungannya sendiri.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.kontrol_data import _layanan_block
from akreditasi.layanan_unit import resolve_visit_ids
from pasien.models import KunjunganPasien, Pasien

User = get_user_model()


def _unit(code, name, level=4, parent=None):
    from akreditasi.models import UnitKerja
    unit, _ = UnitKerja.objects.get_or_create(
        code=code, defaults={'name': name, 'level': level, 'parent': parent})
    return unit


def _pasien():
    return Pasien.objects.create(
        no_rm='RM-LAYANAN', nik='321', nama_lengkap='Pasien Layanan',
        tanggal_lahir='1990-01-01', jenis_kelamin='L')


class LayananBlockResolverTest(TestCase):
    def setUp(self):
        self.poli = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah')
        self.admisi = _unit('ADMISI', 'Unit Pendaftaran & Admisi', 3)
        self.pasien = _pasien()
        # Kunjungan baru: poliklinik sudah dipilih, stempel unit = loket admisi.
        self.k = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-ADMISI', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah', unit_kerja=self.admisi,
            tanggal_masuk=timezone.now(), status='DAFTAR')
        self.igd_unit = _unit('IGD', 'Instalasi Gawat Darurat', 2)
        self.k_igd = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-IGD', jenis_kunjungan='IGD',
            poliklinik='IGD', unit_kerja=self.igd_unit, triage='HIJAU',
            tanggal_masuk=timezone.now(), status='TRIAGE')

    def _nos(self, unit):
        return [i['no_kunjungan'] for i in _layanan_block(unit)['items']]

    def test_visit_belongs_to_stamped_unit_bukan_poliklinik_tujuan(self):
        """Kunjungan yang masih di loket admisi tidak muncul di layanan poli."""
        self.assertIn('K-ADMISI', self._nos(self.admisi))
        self.assertNotIn('K-ADMISI', self._nos(self.poli))

    def test_layanan_block_setuju_dengan_resolve_visit_ids(self):
        """Kedua jalur harus memberi jawaban yang sama untuk unit layanan.

        Loket pendaftaran/admisi tidak ikut dibandingkan: blok LAYANAN
        sengaja ``hospital_wide`` di sana (seluruh kunjungan RS), sedangkan
        ``resolve_visit_ids`` hanya mengenal kepemilikan layanan.
        """
        from akreditasi.kontrol_data import ACTIVE_VISIT_STATUSES
        qs = KunjunganPasien.objects.filter(status__in=ACTIVE_VISIT_STATUSES)
        for unit in (self.poli,):
            expected = {
                KunjunganPasien.objects.get(pk=i).no_kunjungan
                for i in resolve_visit_ids(qs, unit)}
            self.assertEqual(set(self._nos(unit)), expected, unit.name)

    def test_igd_visit_hanya_muncul_di_unit_igd(self):
        self.assertIn('K-IGD', self._nos(self.igd_unit))
        self.assertNotIn('K-IGD', self._nos(self.poli))

    def test_loket_admisi_tetap_melihat_seluruh_kunjungan_rs(self):
        """``hospital_wide`` harus tetap dipertahankan."""
        self.assertIn('K-ADMISI', self._nos(self.admisi))
        self.assertIn('K-IGD', self._nos(self.admisi))


class LayananBlockLinkTest(TestCase):
    """Baris IGD harus menuju dasbor IGD, bukan rekam klinis kunjungan."""

    def setUp(self):
        from accounts.models import UserProfile
        self.igd_unit = _unit('IGD', 'Instalasi Gawat Darurat', 2)
        self.pasien = _pasien()
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-IGD', jenis_kunjungan='IGD',
            poliklinik='IGD', unit_kerja=self.igd_unit, triage='HIJAU',
            tanggal_masuk=timezone.now(), status='TRIAGE')
        user = User.objects.create_user('kep.igd', 'igd@rs.id', 'x')
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=None)
        self.client.force_login(user)

    def test_baris_igd_tautan_ke_dasbor_igd(self):
        res = self.client.get(reverse('akreditasi:kontrol_layanan'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('/pasien/igd/', res.content.decode())

    def test_row_actions_are_contextual(self):
        from django.template.loader import render_to_string
        from akreditasi.kontrol_data import SNAPSHOT_CACHE_VERSION
        self.assertEqual(SNAPSHOT_CACHE_VERSION, 'v4')
        for jenis, destination in (
            ('IGD', reverse('pasien:igd_dashboard')),
            ('Rawat Jalan', reverse('pasien:kunjungan_detail', args=[123])),
        ):
            html = render_to_string('akreditasi/kontrol/layanan.html', {
                'layanan': {'mapped': True},
                'items': [{'pk': 123, 'jenis': jenis, 'penjamin_code': 'BPJS'}],
            })
            import re
            links = re.findall(r'<a class="kontrol-ghost" href="([^"]+)"', html.split('<tbody>')[1].split('</tbody>')[0])
            self.assertEqual(links, [destination])
            self.assertIn('?format=json', html)
            self.assertIn('event.preventDefault()', html)
            self.assertIn("feedback.setAttribute('role', 'status')", html)
