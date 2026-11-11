from django.test import TestCase, Client
from django.urls import reverse
from django.core import signing
from pasien.models import Pasien, KunjunganPasien, JadwalDokterPoli
from django.utils import timezone
from datetime import date, time

class ApmUiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.pasien = Pasien.objects.create(
            no_rm='RM-UI-001',
            nama_lengkap='Pasien UI',
            tanggal_lahir=date(1991, 7, 20),
            jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='REG-UI-001',
            jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(),
            nomor_antrean='JTG-001',
            poliklinik='POLI_JANTUNG',
            dpjp='dr. Faisal, Sp.JP',
            kode_booking='APM-UI-001',
            token_batal='tok-ui-test',
            estimasi_pelayanan=time(9, 30),
            is_apm=True
        )

    def test_kiosk_page_renders_steps(self):
        res = self.client.get(reverse('pasien:apm_kiosk'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Anjungan Pendaftaran Mandiri')
        self.assertContains(res, 'Pasien Baru')
        self.assertContains(res, 'Pasien Lama')
        self.assertContains(res, 'Check-In')
        self.assertContains(res, 'IGD')

    def test_struk_thermal_renders(self):
        res = self.client.get(reverse('pasien:apm_cetak_struk', kwargs={'pk': self.kunjungan.pk}),
                              {'access': signing.dumps(self.kunjungan.pk, salt='apm-receipt')})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'STRUK BUKTI ANTREAN')
        self.assertContains(res, 'JTG-001')
        self.assertContains(res, 'Pasien UI')

    def test_thermal_receipt_has_real_inline_qr_and_paper_sizes(self):
        url = reverse('pasien:apm_cetak_struk', kwargs={'pk': self.kunjungan.pk})
        for width in ('58', '80'):
            with self.subTest(width=width):
                response = self.client.get(url, {'width': width, 'noprint': '1',
                                                 'access': signing.dumps(self.kunjungan.pk, salt='apm-receipt')})
                self.assertContains(response, '<svg')
                self.assertContains(response, f'width: {int(width) - 2}mm')
                self.assertNotContains(response, 'qr-placeholder')

    def test_kiosk_wires_registration_and_checkin(self):
        response = self.client.get(reverse('pasien:apm_kiosk'))
        for name in ('apm_api_cari_pasien', 'apm_api_jadwal_dokter', 'apm_api_daftar', 'apm_api_checkin'):
            self.assertContains(response, reverse('pasien:' + name))
        self.assertContains(response, 'id="register"')
        self.assertContains(response, 'id="checkin-form"')

    def test_batal_page_renders(self):
        res = self.client.get(reverse('pasien:apm_batal_mandiri'), {'token': 'tok-ui-test'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Pembatalan Janji')
        self.assertContains(res, 'Pasien UI')

    def test_admission_dashboard_links_to_kiosk_and_board(self):
        from django.contrib.auth.models import User
        user = User.objects.create_superuser(username='apm-nav-test', email='')
        self.client.force_login(user)
        response = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Layanan mandiri"')
        self.assertContains(response, reverse('pasien:apm_kiosk'))
        self.assertContains(response, reverse('pasien:antrean_display_board'))

    def test_display_board_renders(self):
        res = self.client.get(reverse('pasien:antrean_display_board'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Papan Antrean Poliklinik')
        self.assertContains(res, 'speechSynthesis')
