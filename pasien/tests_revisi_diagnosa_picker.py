from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from pasien.models import KunjunganPasien, Pasien
from accounts.models import UserProfile
from akreditasi.models import UnitKerja

User = get_user_model()


class DiagnosaPickerTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dokter_picker', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='DOKTER',
            unit_kerja=self.unit_igd
        )
        self.client.login(username='dokter_picker', password='password123')

    def test_api_sdki_search(self):
        response = self.client.get(reverse('pasien:api_sdki') + '?q=nyeri')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any('Nyeri' in item['nama'] for item in data))

    def test_igd_ttv_update_saves_both_diagnoses(self):
        import datetime
        from django.utils import timezone
        pasien = Pasien.objects.create(nama_lengkap='Pasien Uji Diagnosa', no_rm='RM-998811', tanggal_lahir=datetime.date(1990, 1, 1))
        k = KunjunganPasien.objects.create(
            pasien=pasien,
            jenis_kunjungan='IGD',
            status='DAFTAR',
            tanggal_masuk=timezone.now()
        )
        url = reverse('pasien:igd_ttv_update', kwargs={'pk': k.pk})
        post_data = {
            'ttv_sistole': 120,
            'ttv_diastole': 80,
            'ttv_nadi': 80,
            'ttv_rr': 20,
            'ttv_suhu': 38.0,
            'ttv_spo2': 98,
            'ttv_gcs': '15',
            'ttv_skala_nyeri': 8,
            'diagnosa_masuk': 'A01.0 - Demam Tifoid',
            'diagnosa_keperawatan_sdki': 'D.0130 - Hipertermia',
            'icd9_tindakan': 'Pasang Infus RL',
        }
        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 302)
        k.refresh_from_db()
        self.assertEqual(k.diagnosa_masuk, 'A01.0 - Demam Tifoid')
        self.assertEqual(k.diagnosa_keperawatan_sdki, 'D.0130 - Hipertermia')
        self.assertEqual(k.icd9_tindakan, 'Pasang Infus RL')

    def test_igd_asesmen_medis_save_secondary_survey(self):
        import datetime
        from django.utils import timezone
        pasien = Pasien.objects.create(
            nama_lengkap='Pasien Uji Secondary',
            no_rm='RM-SEC-001',
            tanggal_lahir=datetime.date(1988, 5, 20)
        )
        k = KunjunganPasien.objects.create(
            pasien=pasien,
            jenis_kunjungan='IGD',
            status='ASESMEN',
            tanggal_masuk=timezone.now()
        )
        url = reverse('pasien:igd_asesmen_medis_save', kwargs={'pk': k.pk})
        post_data = {
            'mata_konjungtiva': 'Anemis (+/+)',
            'mata_sklera': 'Ikterik (+/+)',
            'mata_pupil': 'Anisokor',
            'mata_refleks_cahaya': '(+/-)',
            'tht_telinga_lapang': 'Serumen (+/+)',
            'tht_membran_timpani': 'Perforasi',
            'tht_napas_cuping': 'Ada (+)',
            'tht_mukosa_bibir': 'Sianosis / Pucat',
            'tht_faring': 'T2/T2 Hiperemis (+)',
            'kepala_kondisi': 'Hematoma / Jejas',
            'leher_jvp': 'Meningkat (R-JVP)',
            'leher_kgb': 'Pembesaran KGB (+)',
            'leher_kaku_kuduk': 'Positif (+)',
            'leher_trakea': 'Deviasi ke Kanan',
            'paru_inspeksi': 'Asimetris',
            'paru_retraksi': 'Ada Retraksi Interkostal',
            'paru_auskultasi': 'Bronkovesikuler',
            'paru_wheezing': '(+/+) Wheezing Ekspiratoir',
            'paru_ronkhi': '(+/+) Basah Kasar',
            'jantung_bunyi': 'S1-S2 Ireguler',
            'jantung_murmur': 'Systolic Murmur (+)',
            'jantung_gallop': 'Gallop S3 (+)',
            'abdomen_inspeksi': 'Distensi',
            'abdomen_bising_usus': 'Meningkat (Hiperaktif)',
            'abdomen_palpasi': 'Defans Muskular',
            'abdomen_organomegali': 'Hepatomegali (+)',
            'abdomen_perkusi': 'Redup / Ascites (+)',
            'ekstremitas_akral': 'Dingin, Basah, Pucat',
            'ekstremitas_crt': '> 2 Detik',
            'ekstremitas_edema_atas': '(+/+) Pitting Edema',
            'ekstremitas_edema_bawah': '(+/+) Pitting Edema',
            'ekstremitas_motorik_atas': '3/3 (Lemah)',
            'ekstremitas_motorik_bawah': '3/3 (Lemah)',
        }
        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 302)
        k.refresh_from_db()
        self.assertEqual(k.secondary_survey_detail['mata']['konjungtiva'], 'Anemis (+/+)')
        self.assertEqual(k.secondary_survey_detail['mata']['sklera'], 'Ikterik (+/+)')
        self.assertEqual(k.secondary_survey_detail['tht']['faring'], 'T2/T2 Hiperemis (+)')
        self.assertEqual(k.secondary_survey_detail['thorax']['paru_wheezing'], '(+/+) Wheezing Ekspiratoir')
        self.assertEqual(k.secondary_survey_detail['abdomen']['palpasi'], 'Defans Muskular')
        self.assertEqual(k.secondary_survey_detail['ekstremitas']['akral'], 'Dingin, Basah, Pucat')
