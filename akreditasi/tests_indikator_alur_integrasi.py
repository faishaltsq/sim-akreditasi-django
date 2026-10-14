from decimal import Decimal
from django.test import TestCase
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu, CatatanIndikator, RisikoUnit


class IndikatorAlurIntegrasiTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(
            name='Instalasi Farmasi',
            code='TEST-FARM',
            tipe_unit='PENUNJANG_MEDIS',
        )

    def test_indicator_types_support_inm_imrs_imu(self):
        """Model supports clean 3-tier codes: INM, IMRS, IMU."""
        inm = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Kebersihan Tangan',
            kode_indikator='INM-KKT-01',
            jenis='INM',
            dimensi_mutu='AMAN',
            numerator='Jumlah momen dilakukan cuci tangan',
            denominator='Jumlah peluang cuci tangan',
            target_nilai=Decimal('85.00'),
            arah_target='MIN',
        )
        self.assertEqual(inm.jenis, 'INM')
        self.assertEqual(inm.arah_target, 'MIN')

    def test_target_directionality_min_vs_max(self):
        """Minimal (>= target) vs Maksimal (<= target) directionality."""
        # 1. Higher is better (MIN)
        ind_min = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Penggunaan APD',
            kode_indikator='INM-APD-01',
            jenis='INM',
            dimensi_mutu='AMAN',
            numerator='Jumlah petugas tertib APD',
            denominator='Jumlah total observasi',
            target_nilai=Decimal('100.00'),
            arah_target='MIN',
        )
        # Capaian 95% < 100% -> Not achieved
        cat1 = CatatanIndikator.objects.create(
            indikator=ind_min, bulan=1, tahun=2026,
            nilai_numerator=Decimal('95'), nilai_denominator=Decimal('100')
        )
        self.assertFalse(cat1.tercapai)

        # 2. Lower is better (MAX) → model: kejadian / pasien * 100 = angka kejadian %
        # Target: angka kejadian pasien jatuh ≤ 2%
        ind_max = IndikatorMutu.objects.create(
            nama_indikator='Angka Kejadian Pasien Jatuh',
            kode_indikator='IMU-FAR-01',
            jenis='IMU',
            unit=self.unit,
            dimensi_mutu='AMAN',
            numerator='Jumlah kejadian jatuh',
            denominator='Jumlah pasien rawat',
            target_nilai=Decimal('2.00'),
            arah_target='MAX',
        )
        # 1/100 * 100 = 1.00% <= 2% → tercapai
        cat2 = CatatanIndikator.objects.create(
            indikator=ind_max, bulan=1, tahun=2026,
            nilai_numerator=Decimal('1'), nilai_denominator=Decimal('100')
        )
        self.assertTrue(cat2.tercapai)

        # 5/100 * 100 = 5.00% > 2% → tidak tercapai
        cat3 = CatatanIndikator.objects.create(
            indikator=ind_max, bulan=2, tahun=2026,
            nilai_numerator=Decimal('5'), nilai_denominator=Decimal('100')
        )
        self.assertFalse(cat3.tercapai)

    def test_backward_compatibility_legacy_choices(self):
        """Legacy values ('NASIONAL', 'IMP_RS', 'IMP_UNIT') mapped transparently."""
        ind_legacy = IndikatorMutu.objects.create(
            nama_indikator='Legacy Indikator RS',
            kode_indikator='LEGACY-01',
            jenis='IMP_RS',
            dimensi_mutu='EFEKTIF',
            numerator='A', denominator='B',
            target_nilai=Decimal('80.00'),
        )
        self.assertEqual(ind_legacy.jenis_standar, 'IMRS')

    # ------------------------------------------------------------------
    # Task 2: Auto risk trigger on failed indicator
    # ------------------------------------------------------------------

    def test_auto_risk_trigger_on_failed_catatan(self):
        """Saving CatatanIndikator below target auto-creates RisikoUnit draft."""
        ind = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Cuci Tangan',
            kode_indikator='INM-KKT-02',
            jenis='INM',
            unit=self.unit,
            dimensi_mutu='AMAN',
            numerator='Momen cuci tangan',
            denominator='Peluang cuci tangan',
            target_nilai=Decimal('85.00'),
            arah_target='MIN',
            rencana_aksi='Tingkatkan edukasi dan monitoring',
        )
        # 60% < 85% → auto-create draft risiko
        CatatanIndikator.objects.create(
            indikator=ind, bulan=3, tahun=2026,
            nilai_numerator=Decimal('60'), nilai_denominator=Decimal('100')
        )
        risiko = RisikoUnit.objects.filter(
            unit=self.unit, indikator_mutu_terkait=ind
        ).first()
        self.assertIsNotNone(risiko, "Auto-created RisikoUnit draft not found")
        self.assertIn('85', risiko.masalah or risiko.jenis_risiko)

    def test_auto_risk_no_duplicate(self):
        """Repeated failing saves don't create duplicate RisikoUnit entries."""
        ind = IndikatorMutu.objects.create(
            nama_indikator='Waktu Respon IGD',
            kode_indikator='IMU-IGD-01',
            jenis='IMU',
            unit=self.unit,
            dimensi_mutu='TEPAT_WAKTU',
            numerator='Pasien direspons <5 mnt',
            denominator='Total pasien IGD',
            target_nilai=Decimal('90.00'),
            arah_target='MIN',
        )
        CatatanIndikator.objects.create(
            indikator=ind, bulan=1, tahun=2026,
            nilai_numerator=Decimal('70'), nilai_denominator=Decimal('100')
        )
        CatatanIndikator.objects.create(
            indikator=ind, bulan=2, tahun=2026,
            nilai_numerator=Decimal('65'), nilai_denominator=Decimal('100')
        )
        count = RisikoUnit.objects.filter(unit=self.unit, indikator_mutu_terkait=ind).count()
        self.assertEqual(count, 1, f"Expected 1 risk draft, found {count}")

    def test_no_auto_risk_when_achieved(self):
        """Achieved targets must NOT create a RisikoUnit."""
        ind = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan APD 100%',
            kode_indikator='INM-APD-02',
            jenis='INM',
            unit=self.unit,
            dimensi_mutu='AMAN',
            numerator='A', denominator='B',
            target_nilai=Decimal('100.00'),
            arah_target='MIN',
        )
        CatatanIndikator.objects.create(
            indikator=ind, bulan=1, tahun=2026,
            nilai_numerator=Decimal('100'), nilai_denominator=Decimal('100')
        )
        count = RisikoUnit.objects.filter(indikator_mutu_terkait=ind).count()
        self.assertEqual(count, 0)
