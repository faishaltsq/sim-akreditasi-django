from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja, StandardItem
from pasien.models import BillingItem, KunjunganPasien, Pasien, TindakanAsesmen


class AsesmenAwalWireframeIntegrationTest(TestCase):
    """
    Test integrasi end-to-end upgrade antarmuka asesmen awal IGD v2 sesuai wireframe docx:
    - Seksi B: Dokter DPJP (ICD-10, saran AI, prosedur ICD-9)
    - Seksi C: Perawat Asuhan Klinis (SDKI, Cascading SLKI/SIKI, tindakan keperawatan)
    - Rekapitulasi biaya billing dan kepatuhan EP STARKES (ARK 3.1, PAP 2.1, SKP 2, PP 1.1)
    """

    @classmethod
    def setUpTestData(cls):
        UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'Instalasi Gawat Darurat', 'level': 3})
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.unit_igd = UnitKerja.objects.filter(code='IGD').first()
        self.user_dokter = User.objects.create_user(username='dokter.dpjp.v2', password='password123')
        self.user_perawat = User.objects.create_user(username='perawat.klinis.v2', password='password123')

        # Setup profiles with IGD unit
        profile_d, _ = UserProfile.objects.update_or_create(
            user=self.user_dokter,
            defaults={'role': 'ADMIN_RS', 'unit_kerja': self.unit_igd}
        )

        profile_p, _ = UserProfile.objects.update_or_create(
            user=self.user_perawat,
            defaults={'role': 'ADMIN_RS', 'unit_kerja': self.unit_igd}
        )

        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien Wireframe V2',
            no_rm='RM-WF-002',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='P',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='K-WF-002',
            jenis_kunjungan='IGD',
            unit_kerja=self.unit_igd,
            penjamin='BPJS',
            tanggal_masuk=timezone.now(),
            status='AKTIF',
        )

    def test_cascading_3s_endpoint_flow(self):
        """Verifikasi pemanggilan API /pasien/api/3s-cascade/ untuk diagnosis hipertermia/hipovolemia."""
        self.client.force_login(self.user_perawat)
        url = reverse('pasien:api_3s_cascade')
        resp = self.client.get(url, {'sdki': 'D.0023', 'kunjungan': self.kunjungan.pk})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['sdki']['kode'], 'D.0023')
        self.assertGreater(len(data['slki_list']), 0)
        self.assertGreater(len(data['siki_list']), 0)
        # SIKI harus memiliki ep_sub dan ep_status terpetakan
        first_siki = data['siki_list'][0]
        self.assertEqual(first_siki['ep_status'], 'TERPENUHI')
        self.assertTrue(first_siki['ep_sub'])

    def test_simpan_asesmen_terintegrasi_dokter_dan_perawat(self):
        """
        Simulasi penyimpanan komprehensif form asesmen awal:
        - Seksi B Dokter: Diagnosa A09 + Tindakan 89.52 (EKG) + 99.18 (Infus)
        - Seksi C Perawat: SDKI D.0023 + Luaran SLKI + Intervensi SIKI + Tindakan I.01011
        - Billing & EP Verification
        """
        self.client.force_login(self.user_dokter)
        save_url = reverse('pasien:igd_asesmen_medis_save', kwargs={'pk': self.kunjungan.pk})

        post_data = {
            # Seksi B: Dokter DPJP
            'diagnosa_masuk': 'A09 - Gastroenteritis Akut',
            # Seksi C: Perawat Asuhan Klinis
            'diagnosa_keperawatan_sdki': 'D.0023 - Hipovolemia',
            'luaran_keperawatan_slki': 'L.03028 - Status Cairan Membaik',
            'intervensi_keperawatan_siki': 'I.03116 - Manajemen Hipovolemia',
            # Tindakan Form Marker
            'tindakan_form': '1',
            # Row 0: Tindakan Medis ICD-9 (EKG)
            'tindakan_0_id': '',
            'tindakan_0_jenis': 'ICD9',
            'tindakan_0_kode': '89.52',
            'tindakan_0_nama': 'Perekaman Elektrokardiogram (EKG)',
            'tindakan_0_sumber': 'MASTER',
            'tindakan_0_tarif': '75000',
            'tindakan_0_catatan_tarif': 'Tarif disesuaikan penjamin BPJS',
            'tindakan_0_ep_sub': 'ARK 3.1',
            'tindakan_0_ep_status': 'TERPENUHI',
            'tindakan_0_ep_catatan': 'Hasil EKG 12-lead terlampir',
            # Row 1: Tindakan Medis ICD-9 (Infus)
            'tindakan_1_id': '',
            'tindakan_1_jenis': 'ICD9',
            'tindakan_1_kode': '99.18',
            'tindakan_1_nama': 'Injeksi / Infus Cairan Intravena',
            'tindakan_1_sumber': 'MASTER',
            'tindakan_1_tarif': '50000',
            'tindakan_1_catatan_tarif': 'Penyesuaian paket infus BPJS',
            'tindakan_1_ep_sub': 'PAP 3',
            'tindakan_1_ep_status': 'TERPENUHI',
            'tindakan_1_ep_catatan': 'Terpasang IVFD RL 20 tpm',
            # Row 2: Tindakan Keperawatan SIKI (Hasil Cascading)
            'tindakan_2_id': '',
            'tindakan_2_jenis': 'SIKI',
            'tindakan_2_kode': 'I.03116',
            'tindakan_2_nama': 'Manajemen Hipovolemia & Monitoring Intake/Output',
            'tindakan_2_sumber': 'SARAN',
            'tindakan_2_tarif': '25000',
            'tindakan_2_catatan_tarif': 'Tindakan asuhan perawat intensif',
            'tindakan_2_ep_sub': 'SKP 2',
            'tindakan_2_ep_status': 'TERPENUHI',
            'tindakan_2_ep_catatan': 'Catatan balance cairan 24 jam',
        }

        resp = self.client.post(save_url, post_data)
        self.assertEqual(resp.status_code, 302)

        # 1. Verifikasi data kunjungan tersimpan
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.diagnosa_masuk, 'A09 - Gastroenteritis Akut')
        self.assertEqual(self.kunjungan.diagnosa_keperawatan_sdki, 'D.0023 - Hipovolemia')
        self.assertEqual(self.kunjungan.luaran_keperawatan_slki, 'L.03028 - Status Cairan Membaik')
        self.assertEqual(self.kunjungan.intervensi_keperawatan_siki, 'I.03116 - Manajemen Hipovolemia')

        # 2. Verifikasi baris tindakan asesmen
        tindakan_list = TindakanAsesmen.objects.filter(kunjungan=self.kunjungan).order_by('pk')
        self.assertEqual(tindakan_list.count(), 3)

        # Medis 1: EKG
        t0 = tindakan_list[0]
        self.assertEqual(t0.kode, '89.52')
        self.assertEqual(t0.jenis, 'ICD9')
        self.assertEqual(t0.tarif, Decimal('75000'))
        self.assertEqual(t0.catatan_tarif, 'Tarif disesuaikan penjamin BPJS')
        self.assertEqual(t0.ep_status, 'TERPENUHI')
        self.assertIsNotNone(t0.standard_item)
        self.assertIn(t0.standard_item.sub_standard, ('ARK 3.1', 'ARK 3'))

        # Medis 2: Infus
        t1 = tindakan_list[1]
        self.assertEqual(t1.kode, '99.18')
        self.assertEqual(t1.jenis, 'ICD9')
        self.assertEqual(t1.tarif, Decimal('50000'))
        self.assertEqual(t1.ep_status, 'TERPENUHI')

        # Keperawatan: SIKI
        t2 = tindakan_list[2]
        self.assertEqual(t2.kode, 'I.03116')
        self.assertEqual(t2.jenis, 'SIKI')
        self.assertEqual(t2.tarif, Decimal('25000'))
        self.assertEqual(t2.ep_status, 'TERPENUHI')
        self.assertIsNotNone(t2.standard_item)
        self.assertIn(t2.standard_item.sub_standard, ('SKP 2', 'PAP 2.1', 'PAP 2'))

        # 3. Verifikasi Sinkronisasi Billing Kasir
        billing_items = BillingItem.objects.filter(kunjungan=self.kunjungan, sumber='ASESMEN')
        self.assertEqual(billing_items.count(), 3)
        total_billing = sum(item.subtotal for item in billing_items)
        self.assertEqual(total_billing, Decimal('150000'))  # 75.000 + 50.000 + 25.000
