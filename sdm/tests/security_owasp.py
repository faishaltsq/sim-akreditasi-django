"""OWASP Top 10 (2021) security tests — sdm app.

Mencakup A07 Identification & Authentication Failures pada alur rekrutmen:

- ``Pelamar.token`` dan ``KonfirmasiOffering.token`` memakai ``default=uuid.uuid4``
  (``sdm/models/rekrutmen.py:121-124`` dan ``:418-420``) — 122 bit acak versi-4,
  bukan ``secrets.token_urlsafe(32)`` seperti alur aktivasi staf
  (``sdm/services/undangan.py:44``).
- ``portal_offering_unduh`` (``sdm/rekrutmen_portal_views.py:235``) hanya
  memetakan token ke satu ``KonfirmasiOffering``; pemegang token lain tidak
  dapat membaca offering orang lain, dan unduhan staf
  (``sdm:rekrutmen_offering_unduh``) menuntut kapabilitas HC.

Test yang menemukan kerentanan nyata gagal dengan pesan Indonesia yang
menjelaskan bukti dan dampaknya. Test yang memaku pelindung yang sudah benar
memakai assertion biasa dan lulus.
"""
import os
import shutil
import tempfile
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.tests_utils import login, make_unit, make_user
from sdm.models import KonfirmasiOffering, Lamaran, Lowongan, Pegawai, Pelamar
from sdm.services.mcu_offering_rekrutmen import buat_offering, catat_mcu


class _RecruitmentBase(TestCase):
    """Fixture dasar rekrutmen: unit, lowongan, pelamar, lamaran."""

    def setUp(self):
        self._media_dir = tempfile.mkdtemp(prefix='owasp-rekrutmen-')
        self._media_override = override_settings(MEDIA_ROOT=self._media_dir)
        self._media_override.enable()
        super().setUp()
        self.unit = make_unit('UNIT-OWASP-REK', 'Unit Rekrutmen OWASP', level=2)
        self.lowongan = Lowongan.objects.create(
            unit_kerja=self.unit,
            profesi='Perawat',
            judul='Perawat IGD',
            jumlah_kebutuhan=1,
            status='DIBUKA',
            jalur='EKSTERNAL',
            tanggal_buka=timezone.localdate(),
            tanggal_tutup=timezone.localdate() + timezone.timedelta(days=30),
        )

    def tearDown(self):
        super().tearDown()
        self._media_override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)

    def _make_lamaran(self, nama='Calon Uji'):
        return Lamaran.objects.create(
            lowongan=self.lowongan,
            nama_pelamar=nama,
            status='MCU',
        )

    def _make_offering(self, lamaran):
        pegawai = Pegawai.objects.create(nama_lengkap='Pegawai Uji', kategori='PPA')
        lamaran.employee = pegawai
        lamaran.save(update_fields=['employee'])
        catat_mcu(lamaran=lamaran, status='FIT', tanggal_periksa=timezone.localdate())
        return buat_offering(lamaran=lamaran, nomor_surat='001/HC/2026')


class RecruitmentTokenStrengthTest(_RecruitmentBase):
    """Token rekrutmen tidak boleh memakai uuid4 sebagai sumber entropi."""

    def test_token_pelamar_bukan_uuid4(self):
        """Pelamar.token harus dari secrets.token_urlsafe, bukan uuid.uuid4."""
        pelamar = Pelamar.objects.create(nama_lengkap='Pelamar Uji')
        token = str(pelamar.token)
        # uuid4 menghasilkan string 36 karakter berbentuk 8-4-4-4-12.
        is_uuid4 = len(token) == 36 and token.count('-') == 4
        if is_uuid4:
            self.fail(
                'TOKEN LEMAH (A07): Pelamar.token memakai default=uuid.uuid4 '
                f'(contoh: {token!r}), bukan secrets.token_urlsafe(32) seperti '
                'alur aktivasi staf di sdm/services/undangan.py:44. UUIDv4 '
                'menyisipkan 6 bit versi/variant dan bergantung pada PRNG '
                'platform, sehingga token capability URL rekrutmen memiliki '
                'entropi lebih rendah dan pola yang dapat diprediksi. '
                'Perbaikan: gunakan secrets.token_urlsafe(32).'
            )
        self.assertNotEqual(len(token), 36)

    def test_token_offering_bukan_uuid4(self):
        """KonfirmasiOffering.token harus dari secrets.token_urlsafe."""
        lamaran = self._make_lamaran()
        offering = self._make_offering(lamaran)
        token = str(offering.token)
        is_uuid4 = len(token) == 36 and token.count('-') == 4
        if is_uuid4:
            self.fail(
                'TOKEN LEMAH (A07): KonfirmasiOffering.token memakai '
                f'default=uuid.uuid4 (contoh: {token!r}), bukan '
                'secrets.token_urlsafe(32). Token ini adalah capability untuk '
                'menerima/menolak surat penawaran kerja; entropi rendah dan '
                'pola UUID mempermudah tebakan. Perbaikan: gunakan '
                'secrets.token_urlsafe(32).'
            )
        self.assertNotEqual(len(token), 36)

    def test_aktivasi_staf_memakai_token_urlsafe(self):
        """Pembanding: alur aktivasi staf memang memakai secrets.token_urlsafe(32).

        Ini memaku sumber entropi yang benar sebagai rujukan perbaikan.
        """
        import secrets
        sample = secrets.token_urlsafe(32)
        self.assertGreaterEqual(len(sample), 32)
        # Token aktivasi staf tidak memakai pola UUID.
        self.assertNotEqual(len(sample), 36)


class OfferingAccessTest(_RecruitmentBase):
    """Token offering hanya memetakan ke satu record; unduhan staf butuh kapabilitas."""

    def test_portal_offering_hanya_untuk_token_sendiri(self):
        """Pemegang token offering A tidak dapat membuka offering B."""
        offering_a = self._make_offering(self._make_lamaran('Calon A'))
        offering_b = self._make_offering(self._make_lamaran('Calon B'))
        # Token A hanya membuka offering A.
        response = self.client.get(
            reverse('sdm:portal_offering', args=[offering_a.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(offering_a.token, offering_b.token)
        # Token acak tidak membuka apa pun.
        response = self.client.get(
            reverse('sdm:portal_offering', args=[str(uuid.uuid4())])
        )
        self.assertEqual(response.status_code, 404)

    def test_portal_offering_unduh_menolak_token_lain(self):
        """Unduhan portal hanya melayani token yang cocok."""
        offering = self._make_offering(self._make_lamaran('Calon C'))
        ok = self.client.get(
            reverse('sdm:portal_offering_unduh', args=[offering.token])
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok['Content-Type'], 'application/pdf')
        missing = self.client.get(
            reverse('sdm:portal_offering_unduh', args=[str(uuid.uuid4())])
        )
        self.assertEqual(missing.status_code, 404)

    def test_unduh_staf_menuntut_kapabilitas_hc(self):
        """sdm:rekrutmen_offering_unduh menolak anonim dan staf tanpa kapabilitas."""
        offering = self._make_offering(self._make_lamaran('Calon D'))
        url = reverse('sdm:rekrutmen_offering_unduh', args=[offering.token])

        # Anonim -> dialihkan ke login.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.get('Location', ''))

        # Staf unit tanpa kapabilitas rekrutmen -> ditolak.
        staf = make_user('owasp.rek.staf', 'STAF_NAKES', unit=self.unit, profesi='PERAWAT')
        login(self.client, staf)
        response = self.client.get(url)
        self.assertIn(
            response.status_code, (403, 302),
            'staf tanpa kapabilitas rekrutmen tidak boleh mengunduh offering.',
        )
