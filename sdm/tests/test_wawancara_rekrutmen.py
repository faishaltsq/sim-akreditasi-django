"""Fase C5: jadwal wawancara, undangan, scorecard, skor gabungan."""
from datetime import timedelta
from decimal import Decimal

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
    JadwalWawancara,
    Lamaran,
    Lowongan,
    Pelamar,
    PenilaianTahap,
    ScorecardWawancara,
)
from sdm.services.wawancara_rekrutmen import (
    bobot_terkonfigurasi,
    buat_jadwal,
    catat_scorecard,
    kirim_undangan,
    nilai_wawancara,
    skor_gabungan,
)
import sdm.services.wawancara_rekrutmen as wr


class WawancaraBase(TestCase):
    """Unggahan diarahkan ke MEDIA_ROOT sementara."""

    def setUp(self):
        self._media_dir = tempfile.mkdtemp(prefix="wcr-test-")
        self._media_override = override_settings(MEDIA_ROOT=self._media_dir)
        self._media_override.enable()
        super().setUp()

        self.unit = UnitKerja.objects.create(name='Unit WCR', code='HC-WCR')
        self.vacancy = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Perawat IGD',
            jumlah_kebutuhan=2, status='DIBUKA', jalur='EKSTERNAL',
        )
        self.lamaran = self._lamaran('Budi')
        self.penguji = get_user_model().objects.create_user(
            username='penguji', email='penguji@x.id'
        )
        self.waktu = timezone.now() + timedelta(days=3)
        # locmem outbox is process-global; a sibling test may have left mail
        # behind, so start every email assertion from a clean box.
        from django.core import mail
        mail.outbox = []


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
        user = get_user_model().objects.create_user(username='admin-wcr')
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


class JadwalTests(WawancaraBase):
    def test_jadwal_bentrok_ditolak_di_lowongan_sama(self):
        buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        lain = self._lamaran('Siti')
        with self.assertRaises(Exception):
            buat_jadwal(lamaran=lain, waktu=self.waktu)

    def test_undangan_dikirim_ke_pelamar_dan_penguji(self):
        jadwal = buat_jadwal(
            lamaran=self.lamaran, waktu=self.waktu, mode='LURING',
            penguji=[self.penguji],
        )
        with override_settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
        ):
            from django.core import mail
            mail.outbox = []
            terkirim = kirim_undangan(jadwal)
        # send_mail menggabungkan semua penerima dalam satu pesan.
        self.assertEqual(terkirim, 1)
        self.assertEqual(len(mail.outbox), 1)
        penerima = sorted(mail.outbox[0].to)
        self.assertEqual(penerima, ['budi@x.id', 'penguji@x.id'])
        jadwal.refresh_from_db()
        self.assertIsNotNone(jadwal.undangan_terkirim_at)

    def test_undangan_tanpa_email_tidak_mengirim(self):
        pelamar = self.lamaran.pelamar
        pelamar.email = ''
        pelamar.save()
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        with override_settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
        ):
            from django.core import mail
            mail.outbox = []
            terkirim = kirim_undangan(jadwal)
        self.assertEqual(terkirim, 0)
        jadwal.refresh_from_db()
        self.assertIsNone(jadwal.undangan_terkirim_at)


class ScorecardTests(WawancaraBase):
    def test_rata_rata_indikator_yang_diisi(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        sheet = catat_scorecard(
            jadwal=jadwal, penguji=self.penguji,
            kompetensi_teknis='80.00', soft_skill='90.00',
            ketahanan_beban_kerja='70.00', integritas='85.00',
            pemahaman_visi='75.00',
        )
        self.assertEqual(sheet.rata_rata(), Decimal('80.00'))
        self.assertEqual(nilai_wawancara(self.lamaran), 80.0)

    def test_nilai_string_dari_form_dinormalkan(self):
        """Nilai datang sebagai teks dari form; rata-rata tidak boleh error."""
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        sheet = catat_scorecard(
            jadwal=jadwal, penguji=self.penguji,
            kompetensi_teknis='100', soft_skill='50',
        )
        self.assertEqual(sheet.rata_rata(), Decimal('75.00'))

    def test_indikator_kosong_tidak_dihitung(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        sheet = catat_scorecard(
            jadwal=jadwal, penguji=self.penguji,
            kompetensi_teknis='90.00', soft_skill='',
        )
        self.assertEqual(sheet.rata_rata(), Decimal('90.00'))

    def test_invalid_scores_do_not_replace_existing_scorecard(self):
        from django.core.exceptions import ValidationError
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji, soft_skill='50')
        for invalid in ('-1', '101', 'NaN', 'Infinity', '1.001', 'abc'):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                catat_scorecard(jadwal=jadwal, penguji=self.penguji, soft_skill=invalid)
        self.assertEqual(
            ScorecardWawancara.objects.get(jadwal=jadwal).soft_skill, Decimal('50')
        )

    def test_positive_user_weight_does_not_return_partial_score(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji, soft_skill='80')
        from unittest.mock import patch
        with patch.dict(wr.BOBOT_SKOR_GABUNGAN, {
            'SELEKSI_BERKAS': 0, 'TES_KOMPETENSI': 0,
            'WAWANCARA_HRD': 50, 'WAWANCARA_USER': 50,
        }):
            self.assertIsNone(skor_gabungan(self.lamaran))

    def test_kategori_terpisah_dan_riwayat_tidak_ditebak(self):
        from unittest.mock import patch
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        user = get_user_model().objects.create_user(username='user-panel')
        legacy = get_user_model().objects.create_user(username='legacy-panel')
        hrd2 = get_user_model().objects.create_user(username='hrd-panel-2')
        catat_scorecard(jadwal=jadwal, penguji=self.penguji, jenis='HRD', soft_skill='80')
        catat_scorecard(jadwal=jadwal, penguji=user, jenis='USER', soft_skill='60')
        catat_scorecard(jadwal=jadwal, penguji=hrd2, jenis='HRD', soft_skill='100')
        catat_scorecard(jadwal=jadwal, penguji=legacy, soft_skill='100')
        with patch.dict(wr.BOBOT_SKOR_GABUNGAN, {
            'SELEKSI_BERKAS': 0, 'TES_KOMPETENSI': 0,
            'WAWANCARA_HRD': 25, 'WAWANCARA_USER': 75,
        }):
            self.assertEqual(nilai_wawancara(self.lamaran, 'HRD'), 90.0)
            self.assertEqual(nilai_wawancara(self.lamaran, 'USER'), 60.0)
            self.assertEqual(skor_gabungan(self.lamaran), 67.5)

    def test_riwayat_tanpa_kategori_tidak_memenuhi_bobot_hrd(self):
        from unittest.mock import patch
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji, soft_skill='80')
        with patch.dict(wr.BOBOT_SKOR_GABUNGAN, {
            'SELEKSI_BERKAS': 0, 'TES_KOMPETENSI': 0,
            'WAWANCARA_HRD': 100, 'WAWANCARA_USER': 0,
        }):
            self.assertIsNone(skor_gabungan(self.lamaran))

    def test_kategori_tidak_valid_tidak_mengubah_scorecard(self):
        from django.core.exceptions import ValidationError
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji, jenis='HRD', soft_skill='80')
        with self.assertRaises(ValidationError):
            catat_scorecard(jadwal=jadwal, penguji=self.penguji, jenis='SALAH', soft_skill='20')
        sheet = ScorecardWawancara.objects.get(jadwal=jadwal)
        self.assertEqual(sheet.jenis, 'HRD')
        self.assertEqual(sheet.soft_skill, Decimal('80'))


class SkorGabunganTests(WawancaraBase):
    def test_tanpa_bobot_tidak_menghasilkan_angka(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji,
                        kompetensi_teknis='80.00')
        self.assertFalse(bobot_terkonfigurasi())
        self.assertIsNone(skor_gabungan(self.lamaran))

    def test_komponen_berbobot_yang_hilang_memblokir_skor(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji,
                        kompetensi_teknis='80.00')
        wr.BOBOT_SKOR_GABUNGAN.update({
            'SELEKSI_BERKAS': 10, 'TES_KOMPETENSI': 40,
            'WAWANCARA_HRD': 50, 'WAWANCARA_USER': 0,
        })
        self.assertTrue(bobot_terkonfigurasi())
        # Berkas dan CBT belum ada, keduanya berbobot -> skor tidak ditampilkan.
        self.assertIsNone(skor_gabungan(self.lamaran))

    def test_komponen_tanpa_bobot_tidak_dituntut(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji, jenis='HRD',
                        kompetensi_teknis='80.00')
        wr.BOBOT_SKOR_GABUNGAN.update({
            'SELEKSI_BERKAS': 0, 'TES_KOMPETENSI': 0,
            'WAWANCARA_HRD': 100, 'WAWANCARA_USER': 0,
        })
        self.assertEqual(skor_gabungan(self.lamaran), 80.0)

    def test_skor_gabungan_menghitung_semua_komponen(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji, jenis='HRD',
                        kompetensi_teknis='80.00')
        PenilaianTahap.objects.create(
            lamaran=self.lamaran, tahap='SELEKSI_ADMIN', hasil='LULUS',
            skor='90.00',
        )
        from sdm.models import PaketSoal, Soal, SesiUjian
        from sdm.services.ujian_rekrutmen import (
            buat_sesi, catat_jawaban, selesaikan_sesi,
        )
        paket = PaketSoal.objects.create(
            lowongan=self.vacancy, nama='P', durasi_menit=30
        )
        for i in range(1, 4):
            Soal.objects.create(
                paket=paket, nomor=i, pertanyaan=f'Q{i}',
                pilihan_a='a', pilihan_b='b', pilihan_c='c', pilihan_d='d',
                jawaban_benar='A', bobot='1.00',
            )
        sesi = buat_sesi(self.lamaran, paket=paket)
        for soal in paket.soal.all():
            catat_jawaban(sesi, str(soal.pk), 'A')
        selesaikan_sesi(sesi)
        wr.BOBOT_SKOR_GABUNGAN.update({
            'SELEKSI_BERKAS': 10, 'TES_KOMPETENSI': 40,
            'WAWANCARA_HRD': 50, 'WAWANCARA_USER': 0,
        })
        # 90*0.1 + 100*0.4 + 80*0.5 = 89.0
        self.assertEqual(skor_gabungan(self.lamaran), 89.0)

    def tearDown(self):
        wr.BOBOT_SKOR_GABUNGAN.update({
            'SELEKSI_BERKAS': None, 'TES_KOMPETENSI': None,
            'WAWANCARA_HRD': None, 'WAWANCARA_USER': None,
        })


class WawancaraViewTests(WawancaraBase):
    def test_halaman_wawancara_menampilkan_nilai_dengan_format_lokal(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu)
        catat_scorecard(jadwal=jadwal, penguji=self.penguji, jenis='HRD',
                        kompetensi_teknis='80.00')
        admin = self._admin()
        self.client.force_login(admin)
        response = self.client.get(
            reverse('sdm:rekrutmen_wawancara', args=[self.vacancy.pk])
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Budi', html)
        # Locale id memakai koma sebagai separator desimal.
        self.assertIn('80,0', html)
        self.assertIn('belum ditetapkan', html)

    def test_buat_jadwal_lewat_ui(self):
        admin = self._admin()
        self.client.force_login(admin)
        response = self.client.post(
            reverse('sdm:rekrutmen_jadwal_buat', args=[self.lamaran.pk]),
            {
                'lamaran_id': str(self.lamaran.pk),
                'waktu': (timezone.now() + timedelta(days=5)).strftime(
                    '%Y-%m-%dT%H:%M'
                ),
                'mode': 'DARING',
                'lokasi_tautan': 'https://meet.example/abc',
                'penguji': [str(self.penguji.pk)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            JadwalWawancara.objects.filter(lamaran=self.lamaran).exists()
        )

    def test_scorecard_lewat_ui(self):
        admin = self._admin()
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu, penguji=[admin])
        self.client.force_login(admin)
        response = self.client.post(
            reverse('sdm:rekrutmen_scorecard_simpan', args=[jadwal.pk]),
            {'jenis': 'USER', 'kompetensi_teknis': '70', 'soft_skill': '80', 'catatan': 'UI'},
        )
        self.assertEqual(response.status_code, 302)
        sheet = ScorecardWawancara.objects.get(jadwal=jadwal, penguji=admin)
        self.assertEqual(sheet.jenis, 'USER')
        self.assertEqual(sheet.rata_rata(), Decimal('75.00'))
        response = self.client.get(reverse('sdm:rekrutmen_wawancara', args=[self.vacancy.pk]))
        self.assertContains(response, 'value="70.00"')
        self.assertContains(response, 'value="80.00"')

    def test_scorecard_mewajibkan_jenis_valid(self):
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu, penguji=[self.penguji])
        self.client.force_login(self.penguji)
        url = reverse('sdm:rekrutmen_scorecard_simpan', args=[jadwal.pk])
        for jenis in ('', 'INVALID'):
            self.client.post(url, {'jenis': jenis, 'soft_skill': '80'})
            self.assertFalse(ScorecardWawancara.objects.filter(jadwal=jadwal).exists())

    def test_empty_vacancy_and_interviewer_selection(self):
        self.lamaran.delete()
        admin = self._admin()
        self.client.force_login(admin)
        url = reverse('sdm:rekrutmen_wawancara', args=[self.vacancy.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        application = self._lamaran('Siti')
        response = self.client.get(url)
        self.assertContains(response, 'name="penguji"')
        self.client.post(reverse('sdm:rekrutmen_jadwal_buat', args=[application.pk]), {
            'lamaran_id': str(application.pk),
            'waktu': self.waktu.strftime('%Y-%m-%dT%H:%M'),
            'penguji': [str(self.penguji.pk)],
        })
        self.assertTrue(application.jadwal_wawancara.penguji.filter(pk=self.penguji.pk).exists())

    def test_only_assigned_interviewer_can_score(self):
        admin = self._admin()
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu, penguji=[self.penguji])
        url = reverse('sdm:rekrutmen_scorecard_simpan', args=[jadwal.pk])
        self.client.force_login(admin)
        self.assertEqual(self.client.post(url, {'soft_skill': '80'}).status_code, 403)
        self.client.force_login(self.penguji)
        self.assertEqual(self.client.get(reverse('sdm:rekrutmen_wawancara', args=[self.vacancy.pk])).status_code, 200)
        self.assertEqual(self.client.post(url, {'jenis': 'HRD', 'soft_skill': '80'}).status_code, 302)
        self.assertTrue(ScorecardWawancara.objects.filter(jadwal=jadwal, penguji=self.penguji).exists())

    def test_invalid_score_is_not_saved_from_ui(self):
        admin = self._admin()
        jadwal = buat_jadwal(lamaran=self.lamaran, waktu=self.waktu, penguji=[admin])
        self.client.force_login(admin)
        self.client.post(reverse('sdm:rekrutmen_scorecard_simpan', args=[jadwal.pk]), {'soft_skill': '101'})
        self.assertFalse(ScorecardWawancara.objects.filter(jadwal=jadwal).exists())

    def test_scheduling_requires_application_and_interviewer(self):
        self.client.force_login(self._admin())
        url = reverse('sdm:rekrutmen_jadwal_buat', args=[self.lamaran.pk])
        waktu = self.waktu.strftime('%Y-%m-%dT%H:%M')
        self.client.post(url, {'waktu': waktu, 'penguji': [str(self.penguji.pk)]})
        self.client.post(url, {'waktu': waktu, 'lamaran_id': str(self.lamaran.pk)})
        self.assertFalse(JadwalWawancara.objects.filter(lamaran=self.lamaran).exists())
