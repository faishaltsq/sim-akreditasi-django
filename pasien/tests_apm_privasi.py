"""Hardening kanal publik APM: rate limit, audit struk, dan penyamaran data.

Tiga celah yang dikunci di sini:
1. ``api/cari-pasien`` tanpa batas percobaan -> bisa dipakai enumerasi pasien;
2. struk pasien bisa dibuka berulang tanpa jejak siapa yang membuka;
3. papan antrean TV menampilkan nama lengkap pasien di ruang tunggu publik.
"""
import datetime
import json

from django.core import signing
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pasien.models import ApmAksesStruk, KunjunganPasien, Pasien
from pasien.services.masking import mask_nama_papan


class MaskingUnitTest(TestCase):
    def test_nama_papan_hanya_nama_depan_dan_inisial(self):
        self.assertEqual(mask_nama_papan('Basirun Santoso'), 'Basirun S.')
        self.assertEqual(mask_nama_papan('Basirun'), 'Basirun')
        self.assertEqual(mask_nama_papan('  siti   aminah  '), 'siti a.')
        self.assertEqual(mask_nama_papan(''), '-')
        self.assertEqual(mask_nama_papan(None), '-')


class CariPasienRateLimitTest(TestCase):
    url = reverse('pasien:apm_api_cari_pasien')

    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-CARI-001', nama_lengkap='Basirun Santoso',
            tanggal_lahir=datetime.date(1969, 10, 2), jenis_kelamin='L',
            nik='3305162919690002',
        )

    def cari(self, **kwargs):
        data = {'q': '3305162919690002', 'nama_lengkap': 'Basirun Santoso', 'tanggal_lahir': '1969-10-02'}
        data.update(kwargs)
        return self.client.post(self.url, data, content_type='application/json')

    def test_pencarian_valid_mengembalikan_nama_tersamar(self):
        res = self.cari()
        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        self.assertTrue(body['found'])
        self.assertEqual(body['pasien']['nama_lengkap'], 'Bas***')
        self.assertEqual(body['pasien']['no_rm'], 'RM-CARI-001')

    def test_identitas_terlalu_pendek_ditolak(self):
        res = self.cari(q='33')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('terlalu pendek', res.json()['message'])

    def test_percobaan_beruntun_dibatasi(self):
        for _ in range(10):
            self.assertNotEqual(self.cari().status_code, 429)
        res = self.cari()
        self.assertEqual(res.status_code, 429, res.content)
        self.assertEqual(res['Retry-After'], '60')
        self.assertFalse(res.json()['success'])


class StrukAuditTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(
            no_rm='RM-STRUK-001', nama_lengkap='Basirun Santoso',
            tanggal_lahir=datetime.date(1969, 10, 2), jenis_kelamin='L',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-STRUK-001', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), nomor_antrean='JTG-001',
            poliklinik='POLI_JANTUNG', dpjp='dr. Faisal, Sp.JP',
            kode_booking='APM-STRUK-001', is_apm=True,
        )

    def token(self, pk=None):
        return signing.dumps(pk or self.kunjungan.pk, salt='apm-receipt')

    def url(self, access, pk=None):
        return reverse('pasien:apm_cetak_struk', kwargs={'pk': pk or self.kunjungan.pk}) + '?access=' + access

    def test_pembukaan_sah_tercatat_di_audit(self):
        res = self.client.get(self.url(self.token()), HTTP_USER_AGENT='kiosk-test')
        self.assertEqual(res.status_code, 200)
        log = ApmAksesStruk.objects.get()
        self.assertEqual(log.hasil, 'OK')
        self.assertEqual(log.kunjungan_id, self.kunjungan.pk)
        self.assertEqual(log.user_agent, 'kiosk-test')
        self.assertEqual(log.ip, '127.0.0.1')

    def test_token_tidak_valid_ditolak_dan_tercatat(self):
        res = self.client.get(self.url('token-palsu'))
        self.assertEqual(res.status_code, 403)
        log = ApmAksesStruk.objects.get()
        self.assertEqual(log.hasil, 'DITOLAK')
        self.assertIsNone(log.kunjungan_id)
        self.assertEqual(log.diminta_pk, self.kunjungan.pk)

    def test_token_kunjungan_lain_tidak_bisa_dipakai(self):
        lain = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='REG-STRUK-002', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), nomor_antrean='JTG-002',
            poliklinik='POLI_JANTUNG', dpjp='dr. Faisal, Sp.JP', is_apm=True,
        )
        res = self.client.get(self.url(self.token(lain.pk)))
        self.assertEqual(res.status_code, 403)
        self.assertEqual(ApmAksesStruk.objects.filter(hasil='DITOLAK').count(), 1)

    def test_token_punya_masa_berlaku(self):
        dipanggil = {}
        asli = signing.loads

        def rekam(token, **kwargs):
            dipanggil.update(kwargs)
            return asli(token, **kwargs)

        signing.loads = rekam
        try:
            self.client.get(self.url(self.token()))
        finally:
            signing.loads = asli
        self.assertEqual(dipanggil.get('max_age'), 900)
        self.assertEqual(dipanggil.get('salt'), 'apm-receipt')

    def test_pembukaan_beruntun_dibatasi(self):
        url = self.url(self.token())
        for _ in range(20):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 429)


class PapanAntreanMenyamarkanNamaTest(TestCase):
    def test_nama_lengkap_tidak_tampil_di_papan(self):
        pasien = Pasien.objects.create(
            no_rm='RM-PAPAN-001', nama_lengkap='Basirun Santoso',
            tanggal_lahir=datetime.date(1969, 10, 2), jenis_kelamin='L',
        )
        KunjunganPasien.objects.create(
            pasien=pasien, no_kunjungan='REG-PAPAN-001', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), nomor_antrean='JTG-007',
            poliklinik='POLI_JANTUNG', dpjp='dr. Faisal, Sp.JP',
            status_antrean='DIPANGGIL', is_apm=True,
        )
        res = self.client.get(reverse('pasien:antrean_display_api'))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertNotIn('Basirun Santoso', body)
        data = json.loads(body)
        poli = next(row for row in data['data'] if row['kode_poli'] == 'POLI_JANTUNG')
        self.assertEqual(poli['nama_pasien'], 'Basirun S.')
        self.assertEqual(poli['nomor_sekarang'], 'JTG-007')
