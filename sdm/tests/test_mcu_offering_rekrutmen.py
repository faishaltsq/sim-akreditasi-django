"""Fase C6: MCU pra-kerja, surat penawaran, dan konfirmasi kandidat."""
from datetime import timedelta

from django.contrib.auth import get_user_model
import shutil
import tempfile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.akses import HcGrant
from sdm.models import (
    HasilMCU,
    KonfirmasiOffering,
    Lamaran,
    Lowongan,
    Pelamar,
)
from sdm.services.mcu_offering_rekrutmen import (
    boleh_menawarkan,
    buat_offering,
    catat_mcu,
    konfirmasi_offering,
)


class McuOfferingBase(TestCase):
    """Unggahan diarahkan ke MEDIA_ROOT sementara."""

    def setUp(self):
        self._media_dir = tempfile.mkdtemp(prefix="mcu-test-")
        self._media_override = override_settings(MEDIA_ROOT=self._media_dir)
        self._media_override.enable()
        super().setUp()

        self.unit = UnitKerja.objects.create(name='Unit MCU', code='HC-MCU')
        self.vacancy = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Perawat IGD',
            jumlah_kebutuhan=2, status='DIBUKA', jalur='EKSTERNAL',
        )
        self.lamaran = self._lamaran('Budi')
        self.actor = get_user_model().objects.create_user(username='pemeriksa')


    def tearDown(self):
        super().tearDown()
        self._media_override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)
    def _lamaran(self, nama):
        pelamar = Pelamar.objects.create(
            nama_lengkap=nama, email=f'{nama.lower()}@x.id', telepon='08'
        )
        return Lamaran.objects.create(
            lowongan=self.vacancy, pelamar=pelamar, nama_pelamar=nama
        )

    def _admin(self):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_recruitment = True
        config.save()
        user = get_user_model().objects.create_user(username='admin-mcu')
        UserProfile.objects.create(
            user=user, role='ADMIN_RS', unit_kerja=self.unit
        )
        HcGrant.objects.create(
            user=user, unit_kerja=self.unit, capability='can_view_hc'
        )
        HcGrant.objects.create(
            user=user, unit_kerja=self.unit,
            capability='can_manage_hc_recruitment',
        )
        return user
    def _health_grant(self, user, capability):
        HcGrant.objects.create(user=user, unit_kerja=self.unit, capability=capability)



class McuTests(McuOfferingBase):
    def test_unfit_memblokir_penawaran(self):
        catat_mcu(lamaran=self.lamaran, status='UNFIT',
                  catatan='Tekanan darah tinggi')
        self.assertFalse(boleh_menawarkan(self.lamaran))
        with self.assertRaises(Exception):
            buat_offering(lamaran=self.lamaran)

    def test_fit_note_mengizinkan_penawaran(self):
        catat_mcu(lamaran=self.lamaran, status='FIT_NOTE',
                  tanggal_periksa=timezone.localdate(),
                  penyelenggara='Lab K3RS')
        self.assertTrue(boleh_menawarkan(self.lamaran))

    def test_tanpa_mcu_tidak_boleh_menawarkan(self):
        self.assertFalse(boleh_menawarkan(self.lamaran))

    def test_status_tidak_dikenal_ditolak(self):
        with self.assertRaises(Exception):
            catat_mcu(lamaran=self.lamaran, status='NGAWUR')

    def test_mcu_diperbarui_bukan_doppel(self):
        catat_mcu(lamaran=self.lamaran, status='UNFIT')
        catat_mcu(lamaran=self.lamaran, status='FIT',
                  tanggal_periksa=timezone.localdate())
        self.assertEqual(HasilMCU.objects.filter(lamaran=self.lamaran).count(), 1)
        # Verifikasi terbaca segar setelah diperbarui dalam request yang sama.
        self.assertTrue(boleh_menawarkan(self.lamaran))


class OfferingTests(McuOfferingBase):
    def setUp(self):
        super().setUp()
        catat_mcu(lamaran=self.lamaran, status='FIT',
                  tanggal_periksa=timezone.localdate())

    def test_offering_menghasilkan_pdf(self):
        offering = buat_offering(
            lamaran=self.lamaran, nomor_surat='123/HC-RS/2026',
            actor=self.actor,
        )
        self.assertTrue(offering.berkas)
        self.assertEqual(
            offering.berkas.open('rb').read(5), b'%PDF-'
        )
        self.assertEqual(offering.nomor_surat, '123/HC-RS/2026')

    def test_offering_idempoten(self):
        pertama = buat_offering(lamaran=self.lamaran)
        kedua = buat_offering(lamaran=self.lamaran)
        self.assertEqual(pertama.pk, kedua.pk)

    def test_offering_tanpa_nomor_surat_tidak_mengarang(self):
        offering = buat_offering(lamaran=self.lamaran)
        self.assertEqual(offering.nomor_surat, '')


class KonfirmasiTests(McuOfferingBase):
    def setUp(self):
        super().setUp()
        catat_mcu(lamaran=self.lamaran, status='FIT',
                  tanggal_periksa=timezone.localdate())
        self.offering = buat_offering(lamaran=self.lamaran)

    def test_persetujuan_tercatat_dengan_waktu(self):
        konfirmasi_offering(
            token=self.offering.token, setuju=True, ip='10.0.0.1',
            catatan='Siap bergabung',
        )
        self.offering.refresh_from_db()
        self.assertTrue(self.offering.disetujui)
        self.assertIsNotNone(self.offering.disetujui_at)
        self.assertEqual(self.offering.catatan_kandidat, 'Siap bergabung')

    def test_konfirmasi_ganda_ditolak(self):
        konfirmasi_offering(token=self.offering.token, setuju=True)
        with self.assertRaises(Exception):
            konfirmasi_offering(token=self.offering.token, setuju=False)

    def test_token_palsu_ditolak(self):
        with self.assertRaises(Exception):
            konfirmasi_offering(token='tidak-ada', setuju=True)

    def test_invalid_decision_is_rejected(self):
        from django.core.exceptions import ValidationError
        for decision in (None, '', 'false', 0):
            with self.subTest(decision=decision), self.assertRaises(ValidationError):
                konfirmasi_offering(token=self.offering.token, setuju=decision)
        self.offering.refresh_from_db()
        self.assertIsNone(self.offering.disetujui)

    def test_missing_or_invalid_portal_decision_does_not_decline(self):
        url = reverse('sdm:portal_offering', args=[self.offering.token])
        for data in ({}, {'keputusan': 'other'}):
            self.client.post(url, data)
            self.offering.refresh_from_db()
            self.assertIsNone(self.offering.disetujui)

    def test_candidate_can_download_with_token(self):
        page = self.client.get(reverse('sdm:portal_offering', args=[self.offering.token]))
        url = reverse('sdm:portal_offering_unduh', args=[self.offering.token])
        self.assertContains(page, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertEqual(self.client.get(reverse('sdm:portal_offering_unduh', args=['invalid'])).status_code, 404)

    def test_candidate_can_accept_or_decline_explicitly(self):
        url = reverse('sdm:portal_offering', args=[self.offering.token])
        self.client.post(url, {'keputusan': 'tolak'})
        self.offering.refresh_from_db()
        self.assertIs(self.offering.disetujui, False)



class OfferingViewTests(McuOfferingBase):
    def test_halaman_konfirmasi_menampilkan_surat(self):
        catat_mcu(lamaran=self.lamaran, status='FIT',
                  tanggal_periksa=timezone.localdate())
        offering = buat_offering(
            lamaran=self.lamaran, nomor_surat='123/HC-RS/2026'
        )
        response = self.client.get(
            reverse('sdm:portal_offering', args=[offering.token])
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('menyetujui penawaran', html)
        self.assertIn('123/HC-RS/2026', html)

    def test_unduh_surat_butuh_hak_hc(self):
        catat_mcu(lamaran=self.lamaran, status='FIT',
                  tanggal_periksa=timezone.localdate())
        offering = buat_offering(lamaran=self.lamaran)
        url = reverse('sdm:rekrutmen_offering_unduh', args=[offering.token])
        self.client.get(url)  # anonim -> dialihkan ke login
        self.assertEqual(self.client.get(url).status_code, 302)

        admin = self._admin()
        self.client.force_login(admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_creator_without_recruitment_grant_cannot_use_staff_download(self):
        catat_mcu(lamaran=self.lamaran, status='FIT')
        offering = buat_offering(lamaran=self.lamaran, actor=self.actor)
        self.client.force_login(self.actor)
        response = self.client.get(
            reverse('sdm:rekrutmen_offering_unduh', args=[offering.token])
        )
        self.assertEqual(response.status_code, 403)

    def test_mcu_dicatat_lewat_ui(self):
        admin = self._admin()
        self._health_grant(admin, 'hc_health_write')
        self.client.force_login(admin)
        response = self.client.post(
            reverse('sdm:rekrutmen_mcu_simpan', args=[self.lamaran.pk]),
            {
                'status': 'FIT_NOTE',
                'tanggal_periksa': timezone.localdate().strftime('%Y-%m-%d'),
                'penyelenggara': 'Lab K3RS',
                'catatan': 'Kontrol berkala',
            },
        )
        self.assertEqual(response.status_code, 302)
        mcu = HasilMCU.objects.get(lamaran=self.lamaran)
        self.assertEqual(mcu.status, 'FIT_NOTE')
        self.assertEqual(mcu.penyelenggara, 'Lab K3RS')
        self.assertEqual(mcu.diperiksa_oleh, admin)

    def test_mcu_requires_health_permissions(self):
        admin = self._admin()
        self.client.force_login(admin)
        catat_mcu(lamaran=self.lamaran, status='FIT', catatan='rahasia medis')
        detail = reverse('sdm:rekrutmen_detail', args=[self.vacancy.pk])
        post = reverse('sdm:rekrutmen_mcu_simpan', args=[self.lamaran.pk])
        self.assertNotContains(self.client.get(detail), 'rahasia medis')
        self.assertEqual(self.client.post(post, {'status': 'UNFIT'}).status_code, 403)
        self._health_grant(admin, 'hc_health_read')
        self.assertContains(self.client.get(detail), 'rahasia medis')
        self.assertEqual(self.client.post(post, {'status': 'UNFIT'}).status_code, 403)
        self._health_grant(admin, 'hc_health_write')
        self.assertEqual(self.client.post(post, {'status': 'UNFIT'}).status_code, 302)

    def test_empty_mcu_form_does_not_default_to_fit(self):
        admin = self._admin()
        self._health_grant(admin, 'hc_health_read')
        self._health_grant(admin, 'hc_health_write')
        self.client.force_login(admin)
        response = self.client.get(reverse('sdm:rekrutmen_detail', args=[self.vacancy.pk]))
        self.assertContains(response, 'value="" selected')
        self.assertContains(response, 'value="FIT"')
        self.client.post(reverse('sdm:rekrutmen_mcu_simpan', args=[self.lamaran.pk]), {})
        self.assertFalse(HasilMCU.objects.filter(lamaran=self.lamaran).exists())
