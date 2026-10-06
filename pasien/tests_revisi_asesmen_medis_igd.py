from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien, OrderPenunjang
from akreditasi.models import UnitKerja
from accounts.models import UserProfile


class IgdMedicalAssessmentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('dr_jaga', password='password123')
        self.pasien = Pasien.objects.create(
            no_rm='RM-202610-0001', nama_lengkap='Budi Santoso',
            tanggal_lahir='1985-05-12', jenis_kelamin='L', alamat='Banjarnegara'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='IGD-20261006-0001',
            jenis_kunjungan='IGD', tanggal_masuk=timezone.now(), created_by=self.user
        )

    def test_assessment_and_triage_fields(self):
        self.kunjungan.cara_datang = 'AMBULANS'
        self.kunjungan.triase_kategori = 'KATEGORI_2'
        self.kunjungan.gcs_e = 4
        self.kunjungan.gcs_v = 5
        self.kunjungan.gcs_m = 6
        self.kunjungan.suhu_lokasi = 'Aksila'
        self.kunjungan.nadi_kekuatan = 'Kuat'
        self.kunjungan.nadi_irama = 'Reguler'
        self.kunjungan.pernapasan_pola = 'Spontan'
        self.kunjungan.spo2_alat = 'Udara Bebas'
        self.kunjungan.skala_nyeri_sifat = 'Akut'
        self.kunjungan.metode_risiko_jatuh = 'Morse Fall Scale'
        self.kunjungan.status_emosional = 'Kooperatif'
        self.kunjungan.hambatan_komunikasi = 'Tidak Ada'
        self.kunjungan.kebutuhan_spiritual = 'Tidak Ada'
        self.kunjungan.rpd_checklist = ['HT', 'DM']
        self.kunjungan.secondary_survey_detail = {
            'mata': {'konjungtiva': 'Normal', 'sklera': 'Normal', 'pupil': 'Isokor'},
            'tht': {'telinga': 'Lapang', 'hidung': 'Normal', 'tenggorokan': 'Tenang'},
            'kepala_leher': {'kepala': 'Normosefali', 'leher': 'Normal'},
            'thorax': {'paru': 'Vesikuler (+/+)', 'jantung': 'S1-S2 Reguler'},
            'abdomen': {'inspeksi': 'Datar', 'bising_usus': 'Normal', 'palpasi': 'Supel'},
            'ekstremitas': {'akral': 'Hangat', 'crt': '< 2 Detik', 'edema': 'Tidak Ada'}
        }
        self.kunjungan.sbar_situation = 'Pasien datang dengan nyeri dada kiri'
        self.kunjungan.sbar_background = 'Riwayat HT tidak terkontrol 3 tahun'
        self.kunjungan.sbar_assessment = 'Sindrom Koroner Akut (UAP) - Hemodinamik Stabil'
        self.kunjungan.sbar_recommendation = 'Rawat Inap Ruang ICCU / Bedah, pasang monitor vital'
        self.kunjungan.save()

        k = KunjunganPasien.objects.get(pk=self.kunjungan.pk)
        self.assertEqual(k.cara_datang, 'AMBULANS')
        self.assertEqual(k.triase_kategori, 'KATEGORI_2')
        self.assertEqual(k.gcs_e + k.gcs_v + k.gcs_m, 15)
        self.assertIn('HT', k.rpd_checklist)
        self.assertEqual(k.secondary_survey_detail['mata']['pupil'], 'Isokor')
        self.assertEqual(k.sbar_assessment, 'Sindrom Koroner Akut (UAP) - Hemodinamik Stabil')

    def test_order_penunjang_parameter_list(self):
        order = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan, jenis='LAB',
            nama_pemeriksaan='Panel Darah Lengkap', prioritas='CITO',
            parameter_list=[
                {'category': 'HEMATOLOGI', 'item': 'Darah Rutin (Hb, Ht, Leukosit, Trombosit, Ery)'},
                {'category': 'KIMIA KLINIK', 'item': 'Glukosa Darah Sewaktu (GDS)'},
                {'category': 'KIMIA KLINIK', 'item': 'Troponin T / Troponin I'}
            ]
        )
        self.assertEqual(len(order.parameter_list), 3)
        self.assertEqual(order.prioritas, 'CITO')


class IgdAsesmenMedisSaveViewTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 2})[0]
        self.user = User.objects.create_user('dr_medis', password='password123')
        UserProfile.objects.get_or_create(user=self.user, defaults={'role': 'DOKTER', 'unit_kerja': self.unit})
        self.pasien = Pasien.objects.create(
            no_rm='RM-MEDIS-0001', nama_lengkap='Siti Rahayu',
            tanggal_lahir='1990-03-20', jenis_kelamin='P', alamat='Purwokerto'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='IGD-MEDIS-0001',
            jenis_kunjungan='IGD', tanggal_masuk=timezone.now(), created_by=self.user
        )
        self.client.login(username='dr_medis', password='password123')

    def test_save_asesmen_medis_updates_10_sections(self):
        url = reverse('pasien:igd_asesmen_medis_save', args=[self.kunjungan.pk])
        response = self.client.post(url, {
            'cara_datang': 'RUJUKAN',
            'triase_kategori': 'KATEGORI_3',
            'gcs_e': '3', 'gcs_v': '4', 'gcs_m': '5',
            'ttv_sistole': '120', 'ttv_diastole': '80', 'ttv_nadi': '88',
            'ttv_rr': '18', 'ttv_suhu': '36.5', 'ttv_spo2': '98',
            'skala_nyeri': '4', 'skala_nyeri_sifat': 'Kronik',
            'metode_risiko_jatuh': 'Morse Fall Scale',
            'status_emosional': 'Cemas', 'hambatan_komunikasi': 'Tidak Ada',
            'kebutuhan_spiritual': 'Tidak Ada',
            'keluhan_utama': 'Sesak nafas berat',
            'anamnesis_rps': 'Sesak sejak 2 hari memberat',
            'rpd_check': ['Asma', 'HT'],
            'penunjang_ekg': 'Sinus Takikardia',
            'diagnosa_masuk': 'Asma Eksaserbasi Akut',
            'tatalaksana_resusitasi': 'O2 6 lpm NRM',
            'tatalaksana_tindakan': ['Oksigenasi', 'Pasang Infus'],
            'disposisi_kondisi_akhir': 'MEMBAIK',
            'disposisi_tindak_lanjut': 'RAWAT_INAP',
            'disposisi_ruang_rawat': 'Bangsal Dewasa / Kelas II',
            'sbar_situation': 'Pasien sesak berat',
            'sbar_background': 'Riwayat Asma 5 tahun',
            'sbar_assessment': 'Asma Eksaserbasi Berat',
            'sbar_recommendation': 'Rawat Inap, nebul 3x, monitor SpO2',
        }, follow=False)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.cara_datang, 'RUJUKAN')
        self.assertEqual(self.kunjungan.triase_kategori, 'KATEGORI_3')
        self.assertEqual(self.kunjungan.triage, 'KUNING')
        self.assertEqual(self.kunjungan.gcs_e, 3)
        self.assertEqual(self.kunjungan.gcs_v, 4)
        self.assertEqual(self.kunjungan.gcs_m, 5)
        self.assertEqual(self.kunjungan.ttv_spo2, 98)
        self.assertIn('Asma', self.kunjungan.rpd_checklist)
        self.assertEqual(self.kunjungan.catatan_admisi, 'Sesak nafas berat')
        self.assertEqual(self.kunjungan.diagnosa_masuk, 'Asma Eksaserbasi Akut')
        self.assertIn('Oksigenasi', self.kunjungan.tatalaksana_tindakan_check)
        self.assertEqual(self.kunjungan.disposisi_kondisi_akhir, 'MEMBAIK')
        self.assertEqual(self.kunjungan.sbar_situation, 'Pasien sesak berat')
        self.assertRedirects(response, reverse('pasien:igd_dashboard'), fetch_redirect_response=False)


class OrderLabCreateViewTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 2})[0]
        self.user = User.objects.create_user('dr_lab', password='password123')
        UserProfile.objects.get_or_create(user=self.user, defaults={'role': 'DOKTER', 'unit_kerja': self.unit})
        self.pasien = Pasien.objects.create(
            no_rm='RM-LAB-0001', nama_lengkap='Hasan Basri',
            tanggal_lahir='1975-11-08', jenis_kelamin='L', alamat='Cilacap'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='IGD-LAB-0001',
            jenis_kunjungan='IGD', tanggal_masuk=timezone.now(), created_by=self.user
        )
        self.client.login(username='dr_lab', password='password123')

    def test_create_order_lab(self):
        url = reverse('pasien:order_lab_create', args=[self.kunjungan.pk])
        response = self.client.post(url, {
            'prioritas': 'CITO',
            'kondisi_sampel': 'Tidak Puasa',
            'catatan_klinis': 'Curiga Sepsis',
            'dokter_pengirim': 'dr. Hendra Sp.PD',
            'parameters': [
                'HEMATOLOGI|Darah Rutin Lengkap',
                'KIMIA KLINIK|Ureum & Kreatinin',
                'KIMIA KLINIK|SGOT / SGPT',
            ],
        }, follow=False)
        self.assertEqual(OrderPenunjang.objects.filter(kunjungan=self.kunjungan, jenis='LAB').count(), 1)
        order = OrderPenunjang.objects.get(kunjungan=self.kunjungan, jenis='LAB')
        self.assertEqual(order.prioritas, 'CITO')
        self.assertEqual(order.kondisi_sampel, 'Tidak Puasa')
        self.assertEqual(len(order.parameter_list), 3)
        self.assertEqual(order.parameter_list[0]['category'], 'HEMATOLOGI')
        self.assertRedirects(response, reverse('pasien:igd_dashboard'), fetch_redirect_response=False)


class CetakAsesmenMedisIgdViewTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 2})[0]
        self.user = User.objects.create_user('dr_cetak', password='password123')
        UserProfile.objects.get_or_create(user=self.user, defaults={'role': 'DOKTER', 'unit_kerja': self.unit})
        self.pasien = Pasien.objects.create(
            no_rm='RM-CETAK-0001', nama_lengkap='Dewi Ratnasari',
            tanggal_lahir='1980-07-15', jenis_kelamin='P', alamat='Purbalingga'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='IGD-CETAK-0001',
            jenis_kunjungan='IGD', tanggal_masuk=timezone.now(), created_by=self.user,
            triase_kategori='KATEGORI_2', triage='MERAH',
            gcs_e=4, gcs_v=5, gcs_m=6,
            sbar_situation='Pasien tidak sadar',
            disposisi_tindak_lanjut='RAWAT_INAP',
        )
        self.client.login(username='dr_cetak', password='password123')

    def test_cetak_asesmen_medis_returns_200(self):
        url = reverse('pasien:cetak_asesmen_medis_igd', args=[self.kunjungan.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('kunjungan', response.context)
        self.assertIn('pasien', response.context)
        self.assertContains(response, 'FORMULIR ASESMEN MEDIS AWAL')

    def test_cetak_permintaan_lab_returns_200(self):
        order = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan, jenis='LAB',
            nama_pemeriksaan='Panel Sepsis', prioritas='CITO',
            parameter_list=[
                {'category': 'HEMATOLOGI', 'item': 'Darah Lengkap'},
                {'category': 'KIMIA KLINIK', 'item': 'Laktat'},
            ],
            kondisi_sampel='Tidak Puasa',
            dokter_pengirim='dr. Cetak Sp.EM',
        )
        url = reverse('pasien:cetak_permintaan_lab_order', args=[self.kunjungan.pk, order.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PERMINTAAN')
        self.assertContains(response, 'Darah Lengkap')
