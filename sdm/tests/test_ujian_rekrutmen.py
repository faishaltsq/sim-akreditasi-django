"""Fase C4: mesin CBT rekrutmen — pengacakan, timer, scoring, ranking."""
from datetime import timedelta

import shutil
import tempfile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import (
    JawabanUjian,
    Lamaran,
    Lowongan,
    PaketSoal,
    Pelamar,
    SesiUjian,
    Soal,
)
from sdm.services.ujian_rekrutmen import (
    buat_sesi,
    catat_jawaban,
    catat_pindah_fokus,
    nilai_sesi,
    ranking_lowongan,
    selesaikan_sesi,
)


class CbtBase(TestCase):
    """Unggahan diarahkan ke MEDIA_ROOT sementara."""

    def setUp(self):
        self._media_dir = tempfile.mkdtemp(prefix="cbt-test-")
        self._media_override = override_settings(MEDIA_ROOT=self._media_dir)
        self._media_override.enable()
        super().setUp()

        self.unit = UnitKerja.objects.create(name='Unit CBT', code='HC-CBT')
        self.vacancy = Lowongan.objects.create(
            unit_kerja=self.unit, profesi='Perawat', judul='Perawat IGD',
            jumlah_kebutuhan=2, status='DIBUKA', jalur='EKSTERNAL',
        )
        self.paket = PaketSoal.objects.create(
            lowongan=self.vacancy, nama='Paket Uji', durasi_menit=60,
            passing_grade='70.00',
        )
        for i in range(1, 6):
            Soal.objects.create(
                paket=self.paket, nomor=i, pertanyaan=f'Soal {i}',
                pilihan_a='a', pilihan_b='b', pilihan_c='c', pilihan_d='d',
                jawaban_benar='A', bobot='1.00',
            )


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

    def _jawab(self, sesi, jumlah_benar):
        for i, soal in enumerate(self.paket.soal.order_by('nomor')):
            catat_jawaban(
                sesi, str(soal.pk), 'A' if i < jumlah_benar else 'B'
            )


class SesiUjianTests(CbtBase):
    def test_sesi_tidak_dibuka_dua_kali(self):
        lamaran = self._lamaran('Budi')
        pertama = buat_sesi(lamaran, paket=self.paket)
        kedua = buat_sesi(lamaran, paket=self.paket)
        self.assertEqual(pertama.pk, kedua.pk)

    def test_batas_waktu_dihitung_dari_durasi_paket(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        selisih = (sesi.batas_waktu - sesi.mulai_at).total_seconds()
        self.assertEqual(selisih, 60 * 60)

    def test_urutan_soal_teracak_dan_tetap_per_sesi(self):
        sesi_a = buat_sesi(self._lamaran('A'), paket=self.paket)
        sesi_b = buat_sesi(self._lamaran('B'), paket=self.paket)
        self.assertEqual(len(sesi_a.urutan_soal), 5)
        # Kertas setiap kandidat dikocak sendiri-sendiri.
        self.assertNotEqual(sesi_a.urutan_soal, sesi_b.urutan_soal)
        # Urutan tersimpan, jadi me-refresh tidak mengocok ulang.
        sesi_a.refresh_from_db()
        self.assertEqual(sesi_a.urutan_soal, sesi_a.urutan_soal)


class PenilaianUjianTests(CbtBase):
    def test_nilai_mengikuti_bobot_bukan_jumlah_benar(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        self._jawab(sesi, 4)
        self.assertEqual(nilai_sesi(sesi), 80.0)

    def test_lulus_mengikuti_passing_grade_paket(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        self._jawab(sesi, 4)
        selesaikan_sesi(sesi)
        sesi.refresh_from_db()
        self.assertTrue(sesi.lulus)
        self.assertEqual(sesi.status, 'SELESAI')

    def test_tidak_lulus_bila_di_bawah_passing_grade(self):
        sesi = buat_sesi(self._lamaran('Siti'), paket=self.paket)
        self._jawab(sesi, 2)
        selesaikan_sesi(sesi)
        sesi.refresh_from_db()
        self.assertFalse(sesi.lulus)
        self.assertEqual(sesi.nilai, 40.0)

    def test_passing_grade_belum_ditetapkan_tidak_menghasilkan_keputusan(self):
        self.paket.passing_grade = None
        self.paket.save(update_fields=['passing_grade'])
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        self._jawab(sesi, 4)
        selesaikan_sesi(sesi)
        sesi.refresh_from_db()
        self.assertEqual(sesi.nilai, 80)
        self.assertIsNone(sesi.lulus)
        response = self.client.get(reverse(
            'sdm:portal_ujian', args=[sesi.lamaran.pelamar.token, sesi.pk]
        ))
        self.assertContains(response, 'Belum ditetapkan')
        self.assertNotContains(response, 'Tidak lulus')

    def test_passing_grade_nol_tetap_dihormati(self):
        self.paket.passing_grade = 0
        self.paket.save(update_fields=['passing_grade'])
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        selesaikan_sesi(sesi)
        self.assertTrue(sesi.lulus)

    def test_paket_baru_tidak_memiliki_passing_grade_bawaan(self):
        paket = PaketSoal.objects.create(
            lowongan=self.vacancy, nama='Tanpa ambang', durasi_menit=30
        )
        self.assertIsNone(paket.passing_grade)

    def test_waktu_habis_menandai_kedaluwarsa_dan_menghitung_nilai(self):
        sesi = buat_sesi(self._lamaran('Lambat'), paket=self.paket)
        self._jawab(sesi, 5)
        SesiUjian.objects.filter(pk=sesi.pk).update(
            batas_waktu=timezone.now() - timedelta(minutes=1)
        )
        sesi.refresh_from_db()
        self.assertTrue(sesi.is_kedaluwarsa())
        self.assertEqual(sesi.sisa_detik(), 0)
        selesaikan_sesi(sesi, paksa=True)
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'KEDALUWARSA')
        self.assertEqual(sesi.nilai, 100.0)

    def test_jawaban_setelah_selesai_ditolak(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        self._jawab(sesi, 5)
        selesaikan_sesi(sesi)
        soal = self.paket.soal.first()
        with self.assertRaises(PermissionError):
            catat_jawaban(sesi, str(soal.pk), 'A')

    def test_jawaban_setelah_waktu_habis_ditolak(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        SesiUjian.objects.filter(pk=sesi.pk).update(
            batas_waktu=timezone.now() - timedelta(minutes=1)
        )
        sesi.refresh_from_db()
        soal = self.paket.soal.first()
        with self.assertRaises(PermissionError):
            catat_jawaban(sesi, str(soal.pk), 'A')

    def test_soal_dari_paket_lain_ditolak(self):
        lain = PaketSoal.objects.create(
            lowongan=self.vacancy, nama='Paket Lain', durasi_menit=30
        )
        soal_lain = Soal.objects.create(
            paket=lain, nomor=1, pertanyaan='X',
            pilihan_a='a', pilihan_b='b', pilihan_c='c', pilihan_d='d',
            jawaban_benar='A',
        )
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        with self.assertRaises(ValueError):
            catat_jawaban(sesi, str(soal_lain.pk), 'A')
        with self.assertRaises(ValueError):
            catat_jawaban(sesi, 'not-a-uuid', 'A')


class RankingTests(CbtBase):
    def test_peringkat_berdasarkan_nilai_tertinggi(self):
        tinggi = buat_sesi(self._lamaran('Tinggi'), paket=self.paket)
        self._jawab(tinggi, 5)
        selesaikan_sesi(tinggi)
        rendah = buat_sesi(self._lamaran('Rendah'), paket=self.paket)
        self._jawab(rendah, 2)
        selesaikan_sesi(rendah)
        # Sesi berjalan tidak masuk peringkat.
        buat_sesi(self._lamaran('Berjalan'), paket=self.paket)

        ranking = ranking_lowongan(self.vacancy)
        self.assertEqual(
            [s.lamaran.nama_pelamar for s in ranking], ['Tinggi', 'Rendah']
        )
        self.assertEqual(ranking[0].nilai, 100.0)

class AntiCheatingTests(CbtBase):
    def test_pindah_fokus_terhitung(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        catat_pindah_fokus(sesi)
        catat_pindah_fokus(sesi)
        sesi.refresh_from_db()
        self.assertEqual(sesi.pindah_fokus, 2)


class PortalUjianViewTests(CbtBase):
    def test_halaman_ujian_hanya_untuk_pemilik_token(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        lain = Pelamar.objects.create(
            nama_lengkap='Orang Lain', email='lain@x.id'
        )
        response = self.client.get(
            reverse('sdm:portal_ujian', args=[lain.token, sesi.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_halaman_ujian_menampilkan_soal_dan_timer(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        response = self.client.get(
            reverse('sdm:portal_ujian', args=[sesi.lamaran.pelamar.token, sesi.pk])
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Soal 1', html)
        self.assertIn('ujian-sisa', html)
        self.assertIn('data-fokus-url', html)

    def test_halaman_selesai_menampilkan_nilai(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        self._jawab(sesi, 4)
        selesaikan_sesi(sesi)
        response = self.client.get(
            reverse('sdm:portal_ujian', args=[sesi.lamaran.pelamar.token, sesi.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('80', response.content.decode())

    def test_simpan_lanjut_dan_kirim_jawaban_independen(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        token = sesi.lamaran.pelamar.token
        soal = list(self.paket.soal.order_by('nomor'))
        page = reverse('sdm:portal_ujian', args=[token, sesi.pk])
        jawab = reverse('sdm:portal_ujian_jawab', args=[token, sesi.pk])
        status = reverse('sdm:portal_lamaran_status', args=[token])
        response = self.client.get(status)
        self.assertContains(response, page)
        response = self.client.get(page)
        for item in soal:
            self.assertContains(response, f'name="jawaban_{item.pk}"', count=4)

        payload = {f'jawaban_{soal[0].pk}': 'A', f'jawaban_{soal[1].pk}': 'B'}
        self.client.post(jawab, {**payload, 'save': '1'})
        response = self.client.get(page)
        self.assertContains(response, f'name="jawaban_{soal[0].pk}" value="A" checked')
        self.assertContains(response, f'name="jawaban_{soal[1].pk}" value="B" checked')
        payload[f'jawaban_{soal[2].pk}'] = 'A'
        self.client.post(jawab, {**payload, 'submit': '1'})
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'SELESAI')
        self.assertEqual(sesi.nilai, 40)
        self.assertEqual(sesi.jawaban.count(), 3)
        self.assertNotContains(self.client.get(status), page)

    def test_token_lain_tidak_dapat_mengubah_atau_melihat_sesi(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        lain = self._lamaran('Siti')
        soal = self.paket.soal.first()
        for name in ('portal_ujian', 'portal_ujian_jawab', 'portal_ujian_fokus'):
            url = reverse(f'sdm:{name}', args=[lain.pelamar.token, sesi.pk])
            self.assertEqual(self.client.post(url, {
                f'jawaban_{soal.pk}': 'A', 'submit': '1'
            }).status_code, 404)
        self.assertFalse(sesi.jawaban.exists())
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'BERLANGSUNG')
        self.assertEqual(sesi.pindah_fokus, 0)
        status = reverse('sdm:portal_lamaran_status', args=[lain.pelamar.token])
        self.assertNotContains(self.client.get(status), str(sesi.pk))

    def test_jawaban_asing_atau_tidak_valid_ditolak_tanpa_simpan(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        url = reverse('sdm:portal_ujian_jawab', args=[sesi.lamaran.pelamar.token, sesi.pk])
        soal = self.paket.soal.first()
        paket_lain = PaketSoal.objects.create(
            lowongan=self.vacancy, nama='Lain', durasi_menit=30
        )
        soal_lain = Soal.objects.create(
            paket=paket_lain, nomor=1, pertanyaan='Lain',
            pilihan_a='a', pilihan_b='b', pilihan_c='c', pilihan_d='d',
            jawaban_benar='A',
        )
        for field, value in [
            ('jawaban_not-a-uuid', 'A'), (f'jawaban_{soal.pk}', 'Z'),
            (f'jawaban_{soal_lain.pk}', 'A'),
        ]:
            self.client.post(url, {field: value, 'submit': '1'})
            sesi.refresh_from_db()
            self.assertEqual(sesi.status, 'BERLANGSUNG')
            self.assertFalse(sesi.jawaban.exists())

    def test_sesi_kedaluwarsa_dinilai_tanpa_jawaban_terlambat(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        soal = self.paket.soal.first()
        SesiUjian.objects.filter(pk=sesi.pk).update(
            batas_waktu=timezone.now() - timedelta(seconds=1)
        )
        url = reverse('sdm:portal_ujian_jawab', args=[sesi.lamaran.pelamar.token, sesi.pk])
        self.client.post(url, {f'jawaban_{soal.pk}': 'A', 'submit': '1'})
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'KEDALUWARSA')
        self.assertFalse(sesi.jawaban.exists())

    def test_halaman_kedaluwarsa_menyelesaikan_sesi(self):
        sesi = buat_sesi(self._lamaran('Budi'), paket=self.paket)
        SesiUjian.objects.filter(pk=sesi.pk).update(
            batas_waktu=timezone.now() - timedelta(seconds=1)
        )
        url = reverse('sdm:portal_ujian', args=[sesi.lamaran.pelamar.token, sesi.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        sesi.refresh_from_db()
        self.assertEqual(sesi.status, 'KEDALUWARSA')
