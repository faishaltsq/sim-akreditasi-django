"""Fase C2: portal pelamar publik — token, dokumen wajib, unggahan."""
import io
from datetime import timedelta

import shutil
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.akses import HcGrant
from sdm.models import BerkasPelamar, Lamaran, Lowongan, Pelamar


def _pdf(name='berkas.pdf'):
    return SimpleUploadedFile(
        name, b'%PDF-1.4 smoke', content_type='application/pdf'
    )


class PortalPelamarBase(TestCase):
    """Unggahan diarahkan ke MEDIA_ROOT sementara: test tidak pernah
    menulis ke media nyata, dan tidak meninggalkan berkas untuk test lain."""

    def setUp(self):
        self._media_dir = tempfile.mkdtemp(prefix="rekrutmen-test-")
        self._media_override = override_settings(MEDIA_ROOT=self._media_dir)
        self._media_override.enable()
        super().setUp()

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


    def tearDown(self):
        super().tearDown()
        self._media_override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)
    def _lamar(self, vacancy, **extra):
        data = {
            'nama_lengkap': 'Pelamar Uji', 'telepon': '0812',
            'pendidikan_terakhir': 'S1', 'ipk': '3.00',
            'tanggal_lahir': '1995-05-17', 'pengalaman_bulan': '24',
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


class ScreeningTests(PortalPelamarBase):
    """Fase C3: matriks penapisan administrasi."""

    def setUp(self):
        super().setUp()
        self.vacancy = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Perawat IGD',
            jumlah_kebutuhan=2, status='DIBUKA', jalur='EKSTERNAL',
            kualifikasi_pendidikan='D3 Keperawatan', ipk_minimal='2.75',
            batas_usia=35, pengalaman_minimal_bulan=12,
        )
        self.user = get_user_model().objects.create_user(username='screener')
        UserProfile.objects.create(
            user=self.user, role='ADMIN_RS', unit_kerja=self.unit
        )
        # Grant saja tidak cukup: RolePermissionConfig untuk peran harus aktif.
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_recruitment = True
        config.save()
        HcGrant.objects.create(
            user=self.user, unit_kerja=self.unit,
            capability='can_view_hc',
        )
        HcGrant.objects.create(
            user=self.user, unit_kerja=self.unit,
            capability='can_manage_hc_recruitment',
        )
        self.client.force_login(self.user)

    def _lamaran(self, nama, **profil):
        pelamar = Pelamar.objects.create(
            nama_lengkap=nama, telepon='0812', **profil
        )
        lamaran = Lamaran.objects.create(
            lowongan=self.vacancy, pelamar=pelamar, nama_pelamar=nama
        )
        for jenis in ('KTP', 'IJAZAH', 'CV', 'STR', 'SIP'):
            BerkasPelamar.objects.create(
                lamaran=lamaran, jenis=jenis, berkas=_pdf(f'{jenis.lower()}.pdf')
            )
        return lamaran

    def test_kandidat_memenuhi_semua_kriteria_layak(self):
        from sdm.services.screening_rekrutmen import screen_application
        lamaran = self._lamaran(
            'Sempurna', pendidikan_terakhir='S1', ipk='3.50',
            tanggal_lahir=self.today - timedelta(days=25 * 365),
            pengalaman_bulan=24,
        )
        verdict = screen_application(lamaran)
        self.assertTrue(verdict['layak'])
        self.assertEqual(verdict['masalah'], [])

    def test_kriteria_tidak_terpenuhi_dilaporkan_bukan_dibuang(self):
        from sdm.services.screening_rekrutmen import screen_application
        lamaran = self._lamaran(
            'Kurang', pendidikan_terakhir='SMA_SMK', ipk='2.10',
            tanggal_lahir=self.today - timedelta(days=45 * 365),
            pengalaman_bulan=3,
        )
        verdict = screen_application(lamaran)
        self.assertFalse(verdict['layak'])
        self.assertEqual(len(verdict['masalah']), 4)
        # Baris tetap ada supaya jejak audit per tahap utuh.
        self.assertTrue(Lamaran.objects.filter(pk=lamaran.pk).exists())

    def test_data_kosong_dilaporkan_perlu_dilengkapi(self):
        from sdm.services.screening_rekrutmen import screen_application
        lamaran = self._lamaran('Kosong')
        verdict = screen_application(lamaran)
        self.assertFalse(verdict['layak'])
        self.assertTrue(verdict['perlu_dilengkapi'])

    def test_berkas_wajib_tanpa_baris_tidak_dianggap_lengkap(self):
        from sdm.services.screening_rekrutmen import screen_application
        pelamar = Pelamar.objects.create(
            nama_lengkap='Tanpa dokumen', telepon='0812',
            pendidikan_terakhir='S1', ipk='3.50',
            tanggal_lahir=self.today - timedelta(days=25 * 365),
            pengalaman_bulan=24,
        )
        lamaran = Lamaran.objects.create(
            lowongan=self.vacancy, pelamar=pelamar, nama_pelamar=pelamar.nama_lengkap,
        )
        verdict = screen_application(lamaran)
        self.assertFalse(verdict['layak'])
        self.assertIn('Berkas KTP belum diunggah.', verdict['masalah'])
        self.assertIn('Berkas STR belum diunggah.', verdict['masalah'])

    def test_berkas_belum_diunggah_terhitung_masalah(self):
        from sdm.services.screening_rekrutmen import screen_application
        lamaran = self._lamaran(
            'Tanpa Berkas', pendidikan_terakhir='S1', ipk='3.50',
            tanggal_lahir=self.today - timedelta(days=25 * 365),
            pengalaman_bulan=24,
        )
        lamaran.berkas.update(berkas='')
        verdict = screen_application(lamaran)
        self.assertFalse(verdict['layak'])
        # Semua berkas wajib kosong, jadi kelimanya dilaporkan.
        self.assertEqual(len(verdict['masalah']), 5)

    def test_matriks_tampil_dengan_usulan_per_pelamar(self):
        self._lamaran('Sempurna', pendidikan_terakhir='S1', ipk='3.50',
                      tanggal_lahir=self.today - timedelta(days=25 * 365),
                      pengalaman_bulan=24)
        self._lamaran('Kosong')
        response = self.client.get(
            reverse('sdm:rekrutmen_screening', args=[self.vacancy.pk])
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Sempurna', html)
        self.assertIn('Kosong', html)
        self.assertIn('Layak', html)
        self.assertIn('Perlu dilengkapi', html)

    def test_verifikasi_berkas_per_item(self):
        lamaran = self._lamaran('Satu', pendidikan_terakhir='S1', ipk='3.50')
        berkas = lamaran.berkas.first()
        response = self.client.post(
            reverse('sdm:rekrutmen_berkas_verifikasi',
                    args=[lamaran.pk, berkas.pk]),
            {'status': 'VALID', 'catatan': 'Sudah dicek'},
        )
        self.assertEqual(response.status_code, 302)
        berkas.refresh_from_db()
        self.assertEqual(berkas.status, 'VALID')
        self.assertEqual(berkas.diverifikasi_oleh, self.user)
        self.assertIsNotNone(berkas.diverifikasi_at)

    def test_status_verifikasi_tidak_dikenal_ditolak(self):
        lamaran = self._lamaran('Dua', pendidikan_terakhir='S1', ipk='3.50')
        berkas = lamaran.berkas.first()
        self.client.post(
            reverse('sdm:rekrutmen_berkas_verifikasi',
                    args=[lamaran.pk, berkas.pk]),
            {'status': 'NGAWUR'},
        )
        berkas.refresh_from_db()
        self.assertEqual(berkas.status, 'MENUNGGU')


class NotifikasiPenolakanTests(PortalPelamarBase):
    """C3.5: email penolakan otomatis saat lamaran ditolak."""

    def setUp(self):
        super().setUp()
        from accounts.models import RolePermissionConfig
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_recruitment = True
        config.save()
        self.user = get_user_model().objects.create_user(username='rejector')
        UserProfile.objects.create(
            user=self.user, role='ADMIN_RS', unit_kerja=self.unit
        )
        HcGrant.objects.create(
            user=self.user, unit_kerja=self.unit, capability='can_view_hc'
        )
        HcGrant.objects.create(
            user=self.user, unit_kerja=self.unit,
            capability='can_manage_hc_recruitment',
        )
        self.vacancy = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Perawat IGD',
            jumlah_kebutuhan=1, status='DIBUKA', jalur='EKSTERNAL',
        )
        self.pelamar = Pelamar.objects.create(
            nama_lengkap='Kandidat Email', email='kandidat@x.id',
            telepon='0812',
        )
        self.application = Lamaran.objects.create(
            lowongan=self.vacancy, pelamar=self.pelamar,
            nama_pelamar='Kandidat Email',
        )
        self.client.force_login(self.user)

    def test_penolakan_mengirim_email_ke_pelamar(self):
        from django.core import mail
        from sdm.services.rekrutmen import move_application
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            move_application(
                self.application, target='DITOLAK', actor=self.user,
                notes='IPK di bawah syarat',
            )
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['kandidat@x.id'])
        self.assertIn('Perawat IGD', sent.subject)
        self.assertIn('IPK di bawah syarat', sent.body)
        self.assertIn('Kandidat Email', sent.body)

    def test_penolakan_tanpa_email_tidak_error(self):
        from django.core import mail
        from sdm.services.rekrutmen import move_application
        self.pelamar.email = ''
        self.pelamar.save()
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            move_application(self.application, target='DITOLAK', actor=self.user)
        self.assertEqual(len(mail.outbox), 0)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'DITOLAK')

    def test_kegagalan_email_tidak_membatalkan_perpindahan_tahap(self):
        """Mail server mati tidak boleh mengembalikan tahap yang sudah berubah."""
        from unittest.mock import patch
        from sdm.services.rekrutmen import move_application

        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
        ):
            # Patch modul service, bukan django.core.mail global: menimpa
            # global akan bocor ke test lain dalam suite yang sama.
            with patch(
                'sdm.services.rekrutmen.send_mail',
                side_effect=OSError('mail server down'),
            ):
                move_application(
                    self.application, target='DITOLAK', actor=self.user
                )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'DITOLAK')
