"""
Tests for Standar 5.15 Manajemen Risiko:
- 6 standard risk categories
- masalah and data_pendukung fields
- risiko_input view POST handling
- risiko_detail display
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import RisikoUnit


class Standar515KategoriDanFieldsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='risk.officer', password='password123')
        self.unit = UnitKerja.objects.create(name='Instalasi Farmasi Test', code='FARM-TEST-515', level=2)
        self.client = Client()
        self.client.login(username='risk.officer', password='password123')

    def test_all_6_categories_and_new_fields_saved(self):
        categories = [
            'KLINIS',
            'OPERASIONAL',
            'FINANSIAL',
            'REPUTASI',
            'HUKUM_KEPATUHAN',
            'FASILITAS_LINGKUNGAN',
        ]
        for cat in categories:
            r = RisikoUnit.objects.create(
                unit=self.unit,
                tahun=2026,
                periode='TRIWULAN_1',
                kategori_risiko=cat,
                jenis_risiko=f'Test Risiko {cat}',
                masalah='Terjadi peningkatan antrean dan komplain waktu tunggu',
                data_pendukung='Data log: waktu tunggu resep racikan rata-rata 65 menit (standar <30 menit)',
                deskripsi_risiko='Keterlambatan penyiapan obat mengakibatkan risiko ketidakpuasan pasien',
                dampak=3,
                probabilitas=4,
                strategi_mitigasi='KURANGI',
                rencana_aksi='Evaluasi alur dispensing dan tambah asisten apoteker jam sibuk',
                pj_mitigasi='Ka. Instalasi Farmasi',
                created_by=self.user,
            )
            self.assertEqual(r.kategori_risiko, cat, f"Category {cat} not saved correctly")
            self.assertEqual(r.masalah, 'Terjadi peningkatan antrean dan komplain waktu tunggu')
            self.assertIn('65 menit', r.data_pendukung)

    def test_legacy_manajerial_still_works(self):
        r = RisikoUnit.objects.create(
            unit=self.unit,
            tahun=2026,
            periode='TAHUNAN',
            kategori_risiko='MANAJERIAL',
            jenis_risiko='Legacy Risk Record',
            deskripsi_risiko='Legacy data backward compat test',
            dampak=2,
            probabilitas=2,
            strategi_mitigasi='TERIMA',
            rencana_aksi='Monitoring rutin',
            pj_mitigasi='Ka. Bagian Umum',
            created_by=self.user,
        )
        self.assertEqual(r.kategori_risiko, 'MANAJERIAL')
        self.assertEqual(r.masalah, '')
        self.assertEqual(r.data_pendukung, '')

    def test_risiko_input_view_post_saves_masalah_and_data(self):
        url = reverse('akreditasi:risiko_input')
        payload = {
            'unit': self.unit.id,
            'tahun': 2026,
            'periode': 'TRIWULAN_2',
            'kategori_risiko': 'OPERASIONAL',
            'jenis_risiko': 'Gangguan Jaringan Server IT ARIMA',
            'masalah': 'Server ARIMA lambat saat jam sibuk pelayanan pagi',
            'data': 'Uptime monitoring menunjukkan response time >5000ms pada pukul 08:00-10:00',
            'deskripsi_risiko': 'Kegagalan sistem server IT aplikasi ARIMA menghambat registrasi dan resep',
            'dampak': 4,
            'probabilitas': 3,
            'strategi_mitigasi': 'KURANGI',
            'pj_mitigasi': 'Tim IT & SIMRS',
            'rencana_aksi': 'Upgrade RAM server dan optimasi database PostgreSQL',
            'biaya_mitigasi': '5000000',
        }
        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        r = RisikoUnit.objects.filter(jenis_risiko='Gangguan Jaringan Server IT ARIMA').first()
        self.assertIsNotNone(r, "RisikoUnit not created via POST")
        self.assertEqual(r.kategori_risiko, 'OPERASIONAL')
        self.assertEqual(r.masalah, 'Server ARIMA lambat saat jam sibuk pelayanan pagi')
        self.assertIn('5000ms', r.data_pendukung)

    def test_risiko_detail_shows_masalah_and_data(self):
        r = RisikoUnit.objects.create(
            unit=self.unit,
            tahun=2026,
            periode='TRIWULAN_1',
            kategori_risiko='FASILITAS_LINGKUNGAN',
            jenis_risiko='Kegagalan Genset Saat OK Aktif',
            masalah='Genset otomatis sering terlambat menyala saat pemadaman PLN mendadak',
            data_pendukung='Hasil uji IPSRS: transfer switch mengalami delay 18 detik (standar <10 detik)',
            deskripsi_risiko='Risiko terhentinya pasokan listrik saat operasi darurat berlangsung',
            dampak=5,
            probabilitas=2,
            strategi_mitigasi='HINDARI',
            rencana_aksi='Penggantian modul ATS dan servis berkala genset',
            pj_mitigasi='Ka. IPSRS',
            created_by=self.user,
        )
        url = reverse('akreditasi:risiko_detail', kwargs={'risiko_id': r.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Genset otomatis sering terlambat menyala')
        self.assertContains(response, 'transfer switch mengalami delay 18 detik')

    def test_multi_jenis_risiko_property(self):
        r = RisikoUnit(
            unit=self.unit,
            tahun=2026,
            periode='TRIWULAN_1',
            kategori_risiko='KLINIS',
            jenis_risiko='Medication Error; Keterlambatan Pelayanan Farmasi; Resep Tidak Terbaca',
            dampak=3,
            probabilitas=3,
            strategi_mitigasi='KURANGI',
        )
        items = r.jenis_risiko_list
        self.assertEqual(len(items), 3)
        self.assertIn('Medication Error', items)
        self.assertIn('Keterlambatan Pelayanan Farmasi', items)
        self.assertIn('Resep Tidak Terbaca', items)

    def test_risiko_input_view_post_saves_multi_jenis_risiko(self):
        url = reverse('akreditasi:risiko_input')
        payload = {
            'unit': self.unit.id,
            'tahun': 2026,
            'periode': 'TRIWULAN_1',
            'kategori_risiko': 'KLINIS',
            'masalah': 'Sering terjadi salah baca resep dan antrean menumpuk',
            'data': 'Ada 3 laporan KNC per bulan dan waktu tunggu >45 menit',
            'jenis_risiko': ['Salah dosis racikan', 'Keterlambatan penyerahan obat'],
            'deskripsi_risiko': 'Risiko kesalahan terapi obat dan komplain pasien',
            'dampak': 4,
            'probabilitas': 3,
            'strategi_mitigasi': 'KURANGI',
            'pj_mitigasi': 'Ka Farmasi',
            'rencana_aksi': 'Double check resep dan penambahan staf jam sibuk',
            'biaya_mitigasi': '0',
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, 302)
        created = RisikoUnit.objects.latest('id')
        self.assertIn('Salah dosis racikan', created.jenis_risiko)
        self.assertIn('Keterlambatan penyerahan obat', created.jenis_risiko)
        self.assertEqual(len(created.jenis_risiko_list), 2)

    def test_api_ai_analisis_masalah_risiko_validation(self):
        import json
        url = reverse('akreditasi:api_ai_analisis_masalah_risiko')
        res = self.client.post(url, data=json.dumps({}), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_risiko_input_manual_indikator(self):
        url = reverse('akreditasi:risiko_input')
        payload = {
            'unit': self.unit.id,
            'tahun': 2026,
            'periode': 'TAHUNAN',
            'kategori_risiko': 'KLINIS',
            'jenis_risiko': 'Insiden Tertusuk Jarum',
            'masalah': 'Staf sering tertusuk jarum saat recapping',
            'data': 'Ada 3 laporan insiden needle stick injury dalam 3 bulan',
            'deskripsi_risiko': 'Potensi penularan penyakit bloodborne pada nakes',
            'indikator_mutu_manual': 'Angka Kejadian Tertusuk Jarum Suntik (NSI)',
            'dampak': 4,
            'probabilitas': 3,
            'strategi_mitigasi': 'KURANGI',
            'pj_mitigasi': 'Ka Farmasi',
            'rencana_aksi': 'Sosialisasi no-recapping dan penyediaan safety needle box',
            'biaya_mitigasi': '0',
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, 302)
        created = RisikoUnit.objects.latest('id')
        self.assertIn('[Indikator Mutu Manual: Angka Kejadian Tertusuk Jarum Suntik (NSI)]', created.deskripsi_risiko)



