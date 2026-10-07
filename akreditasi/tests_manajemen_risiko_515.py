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
