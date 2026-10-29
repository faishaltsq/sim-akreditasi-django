"""Fase C2: portal pelamar publik — token, dokumen wajib, unggahan."""
import io
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import BerkasPelamar, Lamaran, Lowongan, Pelamar


def _pdf(name='berkas.pdf'):
    return SimpleUploadedFile(
        name, b'%PDF-1.4 smoke', content_type='application/pdf'
    )


class PortalPelamarBase(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Portal', code='HC-PTL')
        self.today = timezone.localdate()
        self.klinis = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Perawat IGD',
            jumlah_kebutuhan=2, status='DIBUKA', jalur='EKSTERNAL',
            tanggal_buka=self.today - timedelta(days=1),
            tanggal_tutup=self.today + timedelta(days=30),
        )
        self.nonklinis = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Staf Administrasi', judul='Staf TU',
            jumlah_kebutuhan=1, status='DIBUKA', jalur='EKSTERNAL',
        )
        self.ditutup = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Lowongan Tutup',
            jumlah_kebutuhan=1, status='DITUTUP', jalur='EKSTERNAL',
        )
        self.belum_buka = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Lowongan Belum',
            jumlah_kebutuhan=1, status='DIBUKA', jalur='EKSTERNAL',
            tanggal_buka=self.today + timedelta(days=5),
        )

    def _lamar(self, vacancy, **extra):
        data = {
            'nama_lengkap': 'Pelamar Uji', 'telepon': '0812',
            'berkas_ktp': _pdf(), 'berkas_ijazah': _pdf(), 'berkas_cv': _pdf(),
            'berkas_str': _pdf(), 'berkas_sip': _pdf(),
        }
        for key, value in extra.items():
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value
        return self.client.post(
            reverse('sdm:portal_daftar', args=[vacancy.pk]), data
        )


class LowonganPublikTests(PortalPelamarBase):
    def test_hanya_lowongan_yang_pendaftarannya_terbuka(self):
        response = self.client.get(reverse('sdm:portal_lowongan'))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Perawat IGD', html)
        self.assertIn('Staf TU', html)
        self.assertNotIn('Lowongan Tutup', html)
        self.assertNotIn('Lowongan Belum', html)


class DokumenWajibTests(PortalPelamarBase):
    def test_profesi_klinis_mewajibkan_str_sip(self):
        from sdm.services.rekrutmen_portal import dokumen_wajib
        self.assertEqual(
            dokumen_wajib(self.klinis), ['KTP', 'IJAZAH', 'CV', 'STR', 'SIP']
        )

    def test_profesi_non_klinis_tidak_mewajibkan_str_sip(self):
        from sdm.services.rekrutmen_portal import dokumen_wajib
        self.assertEqual(dokumen_wajib(self.nonklinis), ['KTP', 'IJAZAH', 'CV'])


class PengajuanPortalTests(PortalPelamarBase):
    def test_berkas_wajib_yang_hilang_memblokir_submit(self):
        response = self._lamar(self.klinis, berkas_ijazah=None)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Lamaran.objects.exists())
        self.assertFalse(Pelamar.objects.exists())

    def test_submit_lengkap_membuat_lamaran_dan_berkas(self):
        response = self._lamar(
            self.klinis, nama_lengkap='Siti', email='siti@x.id'
        )
        self.assertEqual(response.status_code, 302)
        lamaran = Lamaran.objects.get(nama_pelamar='Siti')
        self.assertEqual(lamaran.status, 'MASUK')
        self.assertEqual(lamaran.berkas.count(), 5)
        self.assertTrue(
            all(b.status == 'MENUNGGU' for b in lamaran.berkas.all())
        )

    def test_berkas_ekstensi_tidak_diizinkan_ditolak(self):
        response = self._lamar(
            self.klinis, nama_lengkap='Jahat',
            berkas_ktp=SimpleUploadedFile(
                'x.exe', b'MZ', content_type='application/octet-stream'
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Format berkas tidak didukung', response.content.decode())
        self.assertFalse(Lamaran.objects.exists())

    def test_berkas_terlalu_besar_ditolak(self):
        response = self._lamar(
            self.klinis, nama_lengkap='Besar',
            berkas_ktp=SimpleUploadedFile(
                'besar.pdf', b'x' * (6 * 1024 * 1024),
                content_type='application/pdf',
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('melebihi', response.content.decode())
        self.assertFalse(Lamaran.objects.exists())

    def test_lowongan_ditutup_tidak_bisa_dilamar(self):
        response = self._lamar(self.ditutup, nama_lengkap='Terlambat')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Lamaran.objects.exists())


class AksesTokenTests(PortalPelamarBase):
    def test_token_palsu_tidak_membocorkan_lamaran(self):
        response = self.client.get(
            reverse('sdm:portal_lamaran_status', args=['token-palsu'])
        )
        self.assertEqual(response.status_code, 404)

    def test_token_hanya_melihat_lamaran_sendiri(self):
        self._lamar(self.klinis, nama_lengkap='Siti')
        lamaran = Lamaran.objects.get(nama_pelamar='Siti')
        lain = Pelamar.objects.create(nama_lengkap='Orang Lain')

        response = self.client.get(
            reverse('sdm:portal_lamaran_status', args=[lain.token])
        )
        self.assertNotIn('Siti', response.content.decode())
        self.assertEqual(response.status_code, 302)

        response = self.client.get(
            reverse('sdm:portal_lamaran_status', args=[lamaran.pelamar.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Perawat IGD', response.content.decode())
        self.assertIn('KTP', response.content.decode())
