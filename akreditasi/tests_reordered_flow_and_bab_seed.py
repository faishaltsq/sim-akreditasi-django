"""
Test suite untuk Restrukturisasi Formulir Manajemen Risiko ARIMA A-G
dan Seeding 132 Indikator & 55 Risiko Klinis 11 Unit (BAB Indikator Risiko Klinis).
"""
from decimal import Decimal
from io import StringIO
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from akreditasi.models import UnitKerja
from akreditasi.risiko_models import RisikoUnit, IndikatorMutu


class ReorderedRiskFlowModelTest(TestCase):
    """Test model fields & properties untuk urutan A-G."""

    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(code='TEST-BEDAH', name='Bangsal Bedah Uji')

    def test_rpn_calculation_three_parameters(self):
        """RPN FMEA dihitung S x O x D."""
        risiko = RisikoUnit.objects.create(
            unit=self.unit,
            tahun=2026,
            periode='TAHUNAN',
            kategori_risiko='KLINIS',
            jenis_risiko='Infeksi Luka Operasi (ILO)',
            deskripsi_risiko='Infeksi pasca bedah akibat kontaminasi',
            dampak=4,  # Severity
            probabilitas=3,  # Occurrence
            metode_evaluasi='FMEA',
            deteksi_fmea=4,  # Detection
            pengendalian_ada='SPO bundle IDO, profilaksis antibiotik tepat waktu',
            strategi_mitigasi='KURANGI',
            rencana_aksi='Audit kepatuhan bundle ILO',
            pj_mitigasi='Ka. Tim Bedah',
        )
        self.assertEqual(risiko.rpn_calc, 48)  # 4 * 3 * 4 = 48
        self.assertEqual(risiko.skor_inherent, 12)
        self.assertTrue(risiko.is_fmea)
        self.assertFalse(risiko.is_rca)

    def test_residual_rpn_calculation(self):
        """RPN residual dihitung S_res x O_res x D_res."""
        risiko = RisikoUnit.objects.create(
            unit=self.unit,
            tahun=2026,
            periode='TAHUNAN',
            kategori_risiko='KLINIS',
            jenis_risiko='Salah penandaan lokasi operasi',
            deskripsi_risiko='Salah sisi operasi',
            dampak=5,
            probabilitas=2,
            metode_evaluasi='FMEA',
            deteksi_fmea=3,
            dampak_residual=2,
            probabilitas_residual=1,
            deteksi_residual=2,
            pengendalian_ada='Site marking oleh operator di ruangan',
            strategi_mitigasi='CEGAH',
            rencana_aksi='Double check sign in checklist keselamatan operasi',
            pj_mitigasi='Ka. IBS',
            evaluasi_capaian='Kepatuhan checklist surgical safety 100%',
            rencana_tindak_lanjut='Supervisi berkala Komite Mutu',
            pj_rtl='Subkomite Keselamatan Pasien',
        )
        self.assertEqual(risiko.rpn_calc, 30)  # 5 * 2 * 3
        self.assertEqual(risiko.rpn_residual_calc, 4)  # 2 * 1 * 2
        self.assertEqual(risiko.skor_residual, 2)  # 2 * 1
        self.assertEqual(risiko.pj_rtl, 'Subkomite Keselamatan Pasien')


class ReorderedRiskViewsTest(TestCase):
    """Test HTTP views untuk alur formulir A-G dan evaluasi."""

    def setUp(self):
        self.client = Client()
        self.unit = UnitKerja.objects.create(code='TEST-VK', name='Kamar Bersalin Uji')
        self.user = User.objects.create_superuser('admin_uji', 'admin@uji.local', 'password123')
        self.client.force_login(self.user)

        self.ind = IndikatorMutu.objects.create(
            unit=self.unit,
            jenis='NASIONAL',
            kode_indikator='INM-VK-01',
            nama_indikator='Kepatuhan Kebersihan Tangan di Kamar Bersalin',
            target_nilai=Decimal('85.00'),
            satuan='%',
        )

    def test_api_indikator_by_unit_includes_jenis_code(self):
        """Endpoint api_indikator_by_unit mengembalikan jenis_code untuk badge kategori."""
        resp = self.client.get(f'/risiko/api/indikator-by-unit/?unit_id={self.unit.id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        indicators = data.get('indikator', [])
        self.assertEqual(len(indicators), 1)
        self.assertEqual(indicators[0]['jenis_code'], 'NASIONAL')
        self.assertEqual(indicators[0]['kode'], 'INM-VK-01')

    def test_risiko_input_post_section_a_to_g(self):
        """POST risiko_input menyimpan field A-G secara menyeluruh."""
        payload = {
            'unit': self.unit.id,
            'tahun': 2026,
            'periode': 'TAHUNAN',
            'kategori_risiko': 'KLINIS',
            'jenis_risiko': 'Perdarahan Pasca Persalinan (HPP) Terlambat Tertangani',
            'deskripsi_risiko': 'Keterlambatan penanganan syok hipovolemik',
            'masalah': 'Stok uterotonika lini kedua sering menipis saat malam',
            'data_pendukung': '1 kasus rujukan tertunda triwulan lalu',
            # Section B
            'dampak': 5,
            'probabilitas': 3,
            'pengendalian_ada': 'Tersedia troli emergency HPP di VK',
            # Section C
            'metode_evaluasi': 'FMEA',
            'deteksi_fmea': 3,
            'tim_evaluasi_fmea': 'Ka. VK, Dokter Sp.OG, Bidan Koordinator',
            'failure_mode_fmea': 'Mode kegagalan: Deteksi atonia uteri terlambat; Efek: Syok perdarahan',
            'tanggal_evaluasi': '2026-10-10',
            # Section D
            'indikator_mutu_terkait': self.ind.id,
            'target_capaian_indikator': '100.00',
            # Section E
            'strategi_mitigasi': 'KURANGI',
            'pj_mitigasi': 'Ka. Instalasi VK',
            'biaya_mitigasi': 2500000,
            'rencana_aksi': 'Simulasi berkala drill code blue obstetric & pembaruan kit HPP',
            # Section F (Target Residu)
            'dampak_residual': 3,
            'probabilitas_residual': 1,
            'deteksi_residual': 2,
            # Section G (Evaluasi & RTL)
            'evaluasi_capaian': 'Waktu tanggap HPP tercapai < 10 menit pada simulasi internal',
            'rencana_tindak_lanjut': 'Pengadaan USG portabel bedside VK',
            'pj_rtl': 'Koordinator Alat Medis',
        }
        resp = self.client.post(reverse('akreditasi:risiko_input'), payload)
        self.assertEqual(resp.status_code, 302)  # Redirect ke risiko_detail

        r = RisikoUnit.objects.filter(jenis_risiko__icontains='Perdarahan Pasca Persalinan').first()
        self.assertIsNotNone(r)
        self.assertEqual(r.pengendalian_ada, 'Tersedia troli emergency HPP di VK')
        self.assertEqual(r.metode_evaluasi, 'FMEA')
        self.assertEqual(r.deteksi_fmea, 3)
        self.assertEqual(r.rpn_calc, 45)  # 5 * 3 * 3 = 45
        self.assertEqual(r.dampak_residual, 3)
        self.assertEqual(r.probabilitas_residual, 1)
        self.assertEqual(r.deteksi_residual, 2)
        self.assertEqual(r.rpn_residual_calc, 6)  # 3 * 1 * 2 = 6
        self.assertEqual(r.evaluasi_capaian, 'Waktu tanggap HPP tercapai < 10 menit pada simulasi internal')
        self.assertEqual(r.rencana_tindak_lanjut, 'Pengadaan USG portabel bedside VK')
        self.assertEqual(r.pj_rtl, 'Koordinator Alat Medis')

    def test_risiko_evaluasi_post_updates_residual_and_rtl(self):
        """POST risiko_evaluasi memperbarui nilai residual dan RTL."""
        r = RisikoUnit.objects.create(
            unit=self.unit,
            tahun=2026,
            periode='TAHUNAN',
            kategori_risiko='KLINIS',
            jenis_risiko='Aspirasi Meconium Bayi Baru Lahir',
            deskripsi_risiko='Asfiksia berat pada bayi air ketuban keruh',
            dampak=5,
            probabilitas=3,
            metode_evaluasi='FMEA',
            deteksi_fmea=4,
            strategi_mitigasi='KURANGI',
            rencana_aksi='Penyiapan suction dan tim resusitasi neonatal',
            pj_mitigasi='Bidan Jaga',
        )

        resp = self.client.post(reverse('akreditasi:risiko_evaluasi', args=[r.pk]), {
            'dampak_residual': 2,
            'probabilitas_residual': 1,
            'deteksi_residual': 2,
            'evaluasi_capaian': 'Seluruh bayi meconium tertangani tanpa komplikasi',
            'rca_ulang': '',
            'rencana_tindak_lanjut': 'Refresh pelatihan resusitasi neonatus setiap 6 bulan',
            'pj_rtl': 'Ka. Ruang VK & Perinatologi',
        })
        self.assertEqual(resp.status_code, 302)

        r.refresh_from_db()
        self.assertEqual(r.status, 'EVALUASI')
        self.assertEqual(r.dampak_residual, 2)
        self.assertEqual(r.probabilitas_residual, 1)
        self.assertEqual(r.deteksi_residual, 2)
        self.assertEqual(r.rpn_residual, 4)  # 2 * 1 * 2 = 4
        self.assertEqual(r.rpn_residual_calc, 4)
        self.assertEqual(r.evaluasi_capaian, 'Seluruh bayi meconium tertangani tanpa komplikasi')
        self.assertEqual(r.rencana_tindak_lanjut, 'Refresh pelatihan resusitasi neonatus setiap 6 bulan')
        self.assertEqual(r.pj_rtl, 'Ka. Ruang VK & Perinatologi')


class SeedBabClinicalIndicatorsTest(TestCase):
    """Test management command seed_bab_clinical_indicators."""

    def test_seed_command_execution_and_idempotency(self):
        from django.core.management import call_command

        # Bersihkan data uji untuk seed BAB
        RisikoUnit.objects.all().delete()
        IndikatorMutu.objects.all().delete()

        out = StringIO()
        call_command('seed_bab_clinical_indicators', stdout=out)

        # 55 risiko klinis 11 unit
        risiko_count = RisikoUnit.objects.filter(kategori_risiko='KLINIS').count()
        self.assertEqual(risiko_count, 55, f'Expected 55 risiko klinis, got {risiko_count}')

        # 132 indikator mutu (11 unit x (2 INM + 5 RS + 5 Unit))
        ind_count = IndikatorMutu.objects.count()
        self.assertEqual(ind_count, 132, f'Expected 132 indikator mutu, got {ind_count}')

        # Setiap unit memiliki 5 risiko dan 12 indikator
        units = UnitKerja.objects.filter(risikounit__kategori_risiko='KLINIS').distinct()
        self.assertEqual(units.count(), 11)

        for u in units:
            u_risiko = RisikoUnit.objects.filter(unit=u, kategori_risiko='KLINIS').count()
            self.assertEqual(u_risiko, 5, f'Unit {u.code} expected 5 risiko, got {u_risiko}')
            u_ind = IndikatorMutu.objects.filter(unit=u).count()
            self.assertEqual(u_ind, 12, f'Unit {u.code} expected 12 indikator, got {u_ind}')

        # Cek bahwa setiap risiko memiliki existing control (pengendalian_ada)
        for r in RisikoUnit.objects.filter(kategori_risiko='KLINIS'):
            self.assertTrue(r.pengendalian_ada, f'{r.jenis_risiko} harus punya pengendalian_ada')
            self.assertTrue(r.masalah, f'{r.jenis_risiko} harus punya masalah')
            self.assertTrue(r.rencana_aksi, f'{r.jenis_risiko} harus punya rencana_aksi')
            self.assertIsNotNone(r.indikator_mutu_terkait, f'{r.jenis_risiko} harus terhubung ke indikator')

        # Idempotency check: jalankan ulang tidak menduplikasi
        call_command('seed_bab_clinical_indicators', stdout=StringIO())
        self.assertEqual(RisikoUnit.objects.filter(kategori_risiko='KLINIS').count(), 55)
        self.assertEqual(IndikatorMutu.objects.count(), 132)
