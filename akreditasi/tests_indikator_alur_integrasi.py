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

    # ------------------------------------------------------------------
    # Task 3 & 4: API JSON Endpoints for charts
    # ------------------------------------------------------------------

    def test_api_tren_endpoint(self):
        """API tren returns 12-month series with target and direction."""
        from django.contrib.auth.models import User
        user = User.objects.create_user('testuser', password='password123')
        self.client.login(username='testuser', password='password123')

        ind = IndikatorMutu.objects.create(
            nama_indikator='Waktu Tanggap Operasi SC',
            kode_indikator='INM-SC-01',
            jenis='INM',
            dimensi_mutu='TEPAT_WAKTU',
            numerator='A', denominator='B',
            target_nilai=Decimal('80.00'),
            arah_target='MIN',
        )
        CatatanIndikator.objects.create(
            indikator=ind, bulan=1, tahun=2026,
            nilai_numerator=Decimal('75'), nilai_denominator=Decimal('100')
        )
        resp = self.client.get(f'/indikator-mutu/api/tren/{ind.pk}/?tahun=2026')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload['kode'], 'INM-SC-01')
        self.assertEqual(payload['target'], 80.0)
        self.assertEqual(payload['data'][0], 75.0)
        self.assertIsNone(payload['data'][1])  # Bulan 2 belum ada data

    def test_api_komparasi_unit_endpoint(self):
        """API komparasi unit returns cross-unit indicators for a month."""
        from django.contrib.auth.models import User
        user = User.objects.create_user('testuser2', password='password123')
        self.client.login(username='testuser2', password='password123')

        ind = IndikatorMutu.objects.create(
            nama_indikator='Kepuasan Pasien Farmasi',
            kode_indikator='IMU-FAR-99',
            jenis='IMU',
            unit=self.unit,
            dimensi_mutu='BERORIENTASI_PASIEN',
            numerator='A', denominator='B',
            target_nilai=Decimal('90.00'),
            arah_target='MIN',
        )
        CatatanIndikator.objects.create(
            indikator=ind, bulan=1, tahun=2026,
            nilai_numerator=Decimal('92'), nilai_denominator=Decimal('100')
        )
        resp = self.client.get('/indikator-mutu/api/komparasi-unit/?jenis=IMU&bulan=1&tahun=2026')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload['jenis'], 'IMU')
        self.assertTrue(len(payload['items']) >= 1)
        found = [i for i in payload['items'] if i['kode'] == 'IMU-FAR-99']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['capaian'], 92.0)
        self.assertTrue(found[0]['tercapai'])

    # ------------------------------------------------------------------
    # Task 5: Renstra FK link + Auto-tag RDWOS evidence
    # ------------------------------------------------------------------

    def test_indikator_sasaran_strategis_fk(self):
        """IndikatorMutu.sasaran_strategis links to RenstraRoadmap."""
        from akreditasi.risiko_models import RenstraRoadmap
        roadmap = RenstraRoadmap.objects.create(
            tahun=2026,
            isu_strategis='Consolidation & Digital Foundation',
        )
        ind = IndikatorMutu.objects.create(
            nama_indikator='Uptime SIMRS',
            kode_indikator='IMRS-SIM-01',
            jenis='IMRS',
            dimensi_mutu='EFISIEN',
            numerator='Jam uptime', denominator='Total jam',
            target_nilai=Decimal('99.50'),
            arah_target='MIN',
            sasaran_strategis=roadmap,
        )
        self.assertEqual(ind.sasaran_strategis.tahun, 2026)
        # Reverse relation
        self.assertIn(ind, roadmap.indikator_list.all())

    def test_auto_evidence_tag_on_achieved_indicator(self):
        """When indicator achieves target and has ep_terkait, auto-update QualityRecord."""
        from akreditasi.models import Framework, Category, StandardItem, QualityRecord
        fw = Framework.objects.create(name='STARKES 2022')
        cat = Category.objects.create(name='TKRS', code='TKRS', order=1, framework=fw)
        ep = StandardItem.objects.create(
            category=cat,
            code='TKRS-AUTOTEST-01',
            sub_standard='TKRS 1',
            sub_title='Tata Kelola RS',
            description='Bukti indikator mutu tercapai',
            order=1,
        )
        ind = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Clinical Pathway',
            kode_indikator='IMRS-CP-01',
            jenis='IMRS',
            unit=self.unit,
            dimensi_mutu='EFEKTIF',
            numerator='A', denominator='B',
            target_nilai=Decimal('80.00'),
            arah_target='MIN',
            ep_terkait=ep,
        )
        # Create QualityRecord for the EP
        qr = QualityRecord.objects.create(
            standard_item=ep,
            unit=self.unit,
            score=0,
        )
        # Achieve target: 90% >= 80%
        CatatanIndikator.objects.create(
            indikator=ind, bulan=6, tahun=2026,
            nilai_numerator=Decimal('90'), nilai_denominator=Decimal('100')
        )
        qr.refresh_from_db()
        self.assertEqual(qr.score, 10)
        self.assertIn('IMRS-CP-01', qr.quality_target)
        self.assertIn('90.0', qr.quality_target)

    # ------------------------------------------------------------------
    # Integrasi System ARIMA: Unit Dashboard PDCA Breakdown & ERM
    # ------------------------------------------------------------------

    def test_unit_dashboard_risiko_pdca_breakdown(self):
        """Unit dashboard context must include risiko_plan, risiko_do, risiko_rtl counts."""
        from akreditasi.risiko_models import RisikoUnit
        from django.contrib.auth.models import User
        from accounts.models import UserProfile

        user = User.objects.create_user(username='dashtest', password='password123')
        up, _ = UserProfile.objects.get_or_create(user=user)
        up.unit_kerja = self.unit
        up.role = 'KEPALA_UNIT'
        up.save()

        RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='OPERASIONAL', jenis_risiko='Test Plan',
            masalah='m', dampak=2, probabilitas=2,
            strategi_mitigasi='KURANGI', status='PLAN',
        )
        RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='OPERASIONAL', jenis_risiko='Test Do',
            masalah='m', dampak=2, probabilitas=2,
            strategi_mitigasi='KURANGI', status='DO',
        )
        RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='OPERASIONAL', jenis_risiko='Test RTL Selesai',
            masalah='m', dampak=2, probabilitas=2,
            strategi_mitigasi='KURANGI', status='SELESAI',
        )
        RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='OPERASIONAL', jenis_risiko='Test RTL Accepted',
            masalah='m', dampak=2, probabilitas=2,
            strategi_mitigasi='KURANGI', status='ACCEPTED',
        )

        self.client.force_login(user)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['risiko_plan'], 1)
        self.assertEqual(resp.context['risiko_do'], 1)
        self.assertEqual(resp.context['risiko_rtl'], 2)  # SELESAI + ACCEPTED
