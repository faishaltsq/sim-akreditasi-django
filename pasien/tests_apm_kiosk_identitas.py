"""Regresi APM kiosk: branding RS, input NIK, dan alur sampai nomor antrean.

Konteks keluhan lapangan (Nov 2026):
- header kiosk menampilkan "RSU PKU Muhammadiyah Gombong" / "Rumah Sakit ARima";
- NIK 15 digit tidak bisa masuk sama sekali (validasi HTML memblokir tanpa penjelasan);
- setelah memilih dokter, pasien berhenti di "Kembali ke identitas" dan tidak pernah
  menerima nomor antrean poliklinik spesialis jantung.
"""
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import RumahSakitProfile
from pasien.models import JadwalDokterPoli, KunjunganPasien, Pasien

NAMA_RS = 'RS Monsiskami Arima'


class KioskBrandingTest(TestCase):
    def setUp(self):
        self.profil = RumahSakitProfile.get_default()
        self.profil.name = NAMA_RS
        self.profil.save(update_fields=['name'])

    def test_kiosk_memakai_nama_rs_dari_profil(self):
        res = self.client.get(reverse('pasien:apm_kiosk'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, NAMA_RS)

    def test_kiosk_tidak_lagi_menampilkan_rs_lain(self):
        html = self.client.get(reverse('pasien:apm_kiosk')).content.decode()
        for terlarang in ('Muhammadiyah', 'Gombong', 'Rumah Sakit ARIMA', 'Rumah Sakit ARima'):
            self.assertNotIn(terlarang, html, f'branding lama masih muncul: {terlarang}')

    def test_papan_antrean_dan_struk_memakai_nama_rs_dari_profil(self):
        jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP', poliklinik='POLI_JANTUNG',
            jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 0),
            kuota_maksimal=10, status_ketersediaan='BUKA',
        )
        pasien = Pasien.objects.create(
            no_rm='RM-BRAND-001', nama_lengkap='Pasien Brand',
            tanggal_lahir=datetime.date(1990, 1, 1), jenis_kelamin='L',
        )
        kunjungan = KunjunganPasien.objects.create(
            pasien=pasien, no_kunjungan='REG-BRAND-001', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), nomor_antrean='JTG-001',
            poliklinik=jadwal.poliklinik, dpjp=jadwal.nama_dokter,
            kode_booking='APM-BRAND-001', token_batal='tok-brand',
            is_apm=True,
        )
        papan = self.client.get(reverse('pasien:antrean_display_board'))
        self.assertEqual(papan.status_code, 200)
        self.assertContains(papan, NAMA_RS)
        self.assertNotContains(papan, 'Muhammadiyah')

        from django.core import signing
        struk = self.client.get(
            reverse('pasien:apm_cetak_struk', kwargs={'pk': kunjungan.pk})
            + '?access=' + signing.dumps(kunjungan.pk, salt='apm-receipt')
        )
        self.assertEqual(struk.status_code, 200)
        self.assertContains(struk, NAMA_RS)


class KioskFormulirIdentitasTest(TestCase):
    """NIK tidak boleh memblokir langkah 1 tanpa penjelasan."""

    def setUp(self):
        self.html = self.client.get(reverse('pasien:apm_kiosk')).content.decode()

    def test_form_tidak_memakai_validasi_html_yang_memblokir(self):
        self.assertIn('id="identity-form" novalidate', self.html)
        self.assertNotIn('pattern="[0-9]{16}"', self.html)

    def test_ada_petunjuk_dan_hitung_digit_nik(self):
        self.assertIn('NIK (16 digit)', self.html)
        self.assertIn('id="nik-hint"', self.html)
        self.assertIn('id="identity-error"', self.html)

    def test_ada_tombol_lanjut_untuk_mengambil_nomor_antrean(self):
        self.assertIn('id="next-confirm"', self.html)
        self.assertIn('Ambil Nomor Antrean', self.html)


class DaftarKioskAlurTest(TestCase):
    """Alur end-to-end: identitas -> dokter -> nomor antrean."""

    url = reverse('pasien:apm_api_daftar')

    def setUp(self):
        self.jadwal = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Faisal, Sp.JP', poliklinik='POLI_JANTUNG',
            hari_praktik='Senin - Jumat',
            jam_mulai=datetime.time(8, 0), jam_selesai=datetime.time(12, 0),
            kuota_maksimal=20, status_ketersediaan='BUKA',
            kode_poli_bpjs='JTG', kode_dokter_bpjs=12345,
        )

    def payload(self, **kwargs):
        data = {
            'tipe_pasien': 'BARU', 'nama_lengkap': 'basirun',
            'tanggal_lahir': '1969-10-02', 'nik': '3305162919690002',
            'jenis_kelamin': 'L', 'alamat': 'mangli', 'no_wa': '081215416402',
            'jenis_layanan': 'RAJAL', 'poliklinik': 'POLI_JANTUNG',
            'jadwal_id': self.jadwal.pk, 'penjamin': 'UMUM',
        }
        data.update(kwargs)
        return data

    def test_nik_16_digit_mendapat_nomor_antrean_poli_jantung(self):
        response = self.client.post(self.url, self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body['success'])
        self.assertTrue(body['nomor_antrean'].startswith('JTG-'))
        self.assertEqual(body['dpjp'], 'dr. Faisal, Sp.JP')
        self.assertIn('Jantung', body['poliklinik'])
        self.assertTrue(body['struk_url'])

        pasien = Pasien.objects.get(nik='3305162919690002')
        self.assertEqual(pasien.nama_lengkap, 'basirun')
        kunjungan = KunjunganPasien.objects.get()
        self.assertTrue(kunjungan.is_apm)
        self.assertEqual(kunjungan.nomor_antrean, body['nomor_antrean'])

    def test_nik_15_digit_ditolak_dengan_pesan_jelas(self):
        response = self.client.post(
            self.url, self.payload(nik='330516291969000'), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400, response.content)
        pesan = response.json()['message']
        self.assertIn('16 digit', pesan)
        self.assertIn('15 digit', pesan)
        self.assertFalse(Pasien.objects.filter(nik='330516291969000').exists())
        self.assertFalse(KunjunganPasien.objects.exists())

    def test_nik_boleh_kosong_tetap_bisa_daftar(self):
        response = self.client.post(self.url, self.payload(nik=''), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['nomor_antrean'].startswith('JTG-'))

    def test_nik_terdaftar_dengan_nama_berbeda_dijelaskan(self):
        Pasien.objects.create(
            no_rm='RM-LAMA-001', nama_lengkap='Nama Lain',
            tanggal_lahir=datetime.date(1969, 10, 2), jenis_kelamin='L',
            nik='3305162919690002',
        )
        response = self.client.post(self.url, self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 403, response.content)
        pesan = response.json()['message']
        self.assertIn('sudah terdaftar', pesan)
        self.assertIn('Pasien Lama', pesan)
        self.assertFalse(KunjunganPasien.objects.exists())

    def test_dokter_penuh_tidak_mengeluarkan_nomor_antrean(self):
        self.jadwal.kuota_maksimal = 0
        self.jadwal.save(update_fields=['kuota_maksimal'])
        response = self.client.post(self.url, self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('penuh', response.json()['message'])
        self.assertFalse(KunjunganPasien.objects.exists())
