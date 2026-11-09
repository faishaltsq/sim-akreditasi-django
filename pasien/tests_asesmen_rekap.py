from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from akreditasi.models import UnitKerja, StandardItem, AuditLog, Category
from accounts.models import UserProfile
from pasien.models import (
    Pasien, KunjunganPasien, BillingItem,
    KorelasiEpAsesmen, LampiranAsesmen, CPPT, OrderPenunjang
)


class AsesmenRekapBaseTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dokter_igd', password='password123', is_staff=True
        )
        self.unit_igd = UnitKerja.objects.filter(code='IGD').first()
        if not self.unit_igd:
            self.unit_igd = UnitKerja.objects.create(code='IGD', name='Instalasi Gawat Darurat', level=3)
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='KEPALA_UNIT',
            unit_kerja=self.unit_igd,
        )
        self.pasien = Pasien.objects.create(
            no_rm='RM-REKAP-01',
            nama_lengkap='Pasien Rekap Satu',
            nik='3201010101010099',
            jenis_kelamin='L',
            tanggal_lahir='1990-01-01',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-REKAP-001',
            unit_kerja=self.unit_igd,
            jenis_kunjungan='IGD',
            penjamin='UMUM',
            status='ASESMEN',
            tanggal_masuk=timezone.now(),
            anamnesis_rps='Pasien mengeluh nyeri dada kiri menjalar ke punggung sejak 2 jam lalu.',
            diagnosa_masuk='I21.9 - Acute myocardial infarction',
            diagnosa_keperawatan_sdki='D.0077 - Nyeri Akut',
            skrining_jatuh_grade='SEDANG',
            skrining_jatuh_skor=35,
            skrining_jatuh_detail={'jatuh_riwayat': 25, 'jatuh_alat': 10},
        )
        self.std_item = StandardItem.objects.filter(sub_standard='ARK 1').first()
        if not self.std_item:
            cat, _ = Category.objects.get_or_create(code='ARK', defaults={'name': 'Akses dan Kontinuitas'})
            self.std_item = StandardItem.objects.create(
                category=cat,
                code='ARK 1 EP a',
                sub_standard='ARK 1',
                description='Regulasi skrining pasien di IGD',
            )
        self.korelasi_ep = KorelasiEpAsesmen.objects.create(
            kunjungan=self.kunjungan,
            standard_item=self.std_item,
            status='TERPENUHI',
            catatan='Skrining terpenuhi sesuai regulasi',
        )
        dummy_file = SimpleUploadedFile("ekg.pdf", b"%PDF-1.4 dummy ekg content", content_type="application/pdf")
        self.lampiran = LampiranAsesmen.objects.create(
            kunjungan=self.kunjungan,
            file=dummy_file,
            nama_asli='ekg.pdf',
            ukuran=len(dummy_file.read()),
            jenis='ASESMEN',
        )
        self.billing_asesmen = BillingItem.objects.create(
            kunjungan=self.kunjungan,
            kategori='JASA_MEDIS',
            nama_item='EKG 12 Lead',
            kode_icd='89.52',
            harga_satuan=120000,
            kuantitas=1,
            sumber='ASESMEN',
        )
        self.billing_manual = BillingItem.objects.create(
            kunjungan=self.kunjungan,
            kategori='JASA_MEDIS',
            nama_item='Konsul dr SpJP',
            kode_icd='',
            harga_satuan=200000,
            kuantitas=1,
            sumber='MANUAL',
        )
        self.cppt = CPPT.objects.create(
            kunjungan=self.kunjungan,
            nama_ppa='dr. Jaga',
            profesi='DOKTER',
            tanggal=timezone.now(),
            subjektif='Nyeri dada agak berkurang',
            objektif='TD 130/80',
            asesmen='UAP',
            plan='Lanjut ISDN',
        )
        self.order_lab = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan,
            jenis='LAB',
            nama_pemeriksaan='Troponin I CITO',
            prioritas='CITO',
            status='ORDERED',
        )
        self.client.login(username='dokter_igd', password='password123')


class AsesmenRekapViewTest(AsesmenRekapBaseTest):
    def test_rekap_list_status_code(self):
        url = reverse('pasien:asesmen_rekap')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Pasien Rekap Satu')
        self.assertContains(res, 'RM-REKAP-01')

    def test_only_rows_with_assessment_included(self):
        # Buat kunjungan baru tanpa anamnesis_rps
        pasien2 = Pasien.objects.create(
            no_rm='RM-KOSONG-02',
            nama_lengkap='Pasien Tanpa Asesmen',
            nik='3201010101010098',
            jenis_kelamin='P',
            tanggal_lahir='1995-05-05',
        )
        k2 = KunjunganPasien.objects.create(
            pasien=pasien2,
            no_kunjungan='KUNJ-KOSONG-002',
            unit_kerja=self.unit_igd,
            jenis_kunjungan='IGD',
            status='TRIAGE',
            tanggal_masuk=timezone.now(),
            anamnesis_rps='',  # KOSONG
        )
        url = reverse('pasien:asesmen_rekap')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Pasien Rekap Satu')
        self.assertNotContains(res, 'Pasien Tanpa Asesmen')

    def test_tarif_column_sums_only_asesmen_source(self):
        url = reverse('pasien:asesmen_rekap')
        res = self.client.get(url)
        # Billing asesmen = 120.000, billing manual = 200.000.
        # Kolom tarif asesmen harus menampilkan 120000 (Rp 120000)
        self.assertContains(res, '120000')
        self.assertNotContains(res, '320000')

    def test_missing_tariff_renders_dash(self):
        # Kunjungan punya asesmen tapi belum ada billing ASESMEN
        pasien3 = Pasien.objects.create(
            no_rm='RM-NOTARIF-03',
            nama_lengkap='Pasien Tanpa Tarif Asesmen',
            nik='3201010101010097',
            jenis_kelamin='L',
            tanggal_lahir='2000-01-01',
        )
        KunjunganPasien.objects.create(
            pasien=pasien3,
            no_kunjungan='KUNJ-NOTARIF-003',
            unit_kerja=self.unit_igd,
            jenis_kunjungan='IGD',
            status='ASESMEN',
            tanggal_masuk=timezone.now(),
            anamnesis_rps='Keluhan demam 3 hari.',
            diagnosa_masuk='A01.0 - Typhoid fever',
        )
        url = reverse('pasien:asesmen_rekap')
        res = self.client.get(url)
        self.assertContains(res, 'Pasien Tanpa Tarif Asesmen')
        self.assertContains(res, '—')

    def test_filter_search_q(self):
        url = reverse('pasien:asesmen_rekap') + '?q=REKAP-01'
        res = self.client.get(url)
        self.assertContains(res, 'Pasien Rekap Satu')

        url_not_found = reverse('pasien:asesmen_rekap') + '?q=NOMATCHXYZ'
        res_nf = self.client.get(url_not_found)
        self.assertNotContains(res_nf, 'Pasien Rekap Satu')

    def test_detail_view_success(self):
        url = reverse('pasien:asesmen_detail', kwargs={'pk': self.kunjungan.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Pasien Rekap Satu')
        self.assertContains(res, 'EKG 12 Lead')
        self.assertContains(res, 'ARK 1')
        self.assertContains(res, 'ekg.pdf')


class AsesmenHapusTest(AsesmenRekapBaseTest):
    def test_requires_post(self):
        url = reverse('pasien:asesmen_hapus', kwargs={'pk': self.kunjungan.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 405)

    def test_requires_konfirmasi_token(self):
        url = reverse('pasien:asesmen_hapus', kwargs={'pk': self.kunjungan.pk})
        res = self.client.post(url, {'konfirmasi': 'SALAH'})
        self.assertRedirects(res, reverse('pasien:asesmen_rekap'))
        # Data tidak boleh terhapus
        self.kunjungan.refresh_from_db()
        self.assertTrue(self.kunjungan.anamnesis_rps)
        self.assertEqual(self.kunjungan.billing.filter(sumber='ASESMEN').count(), 1)

    def test_clears_assessment_fields_and_deletes_artifacts(self):
        url = reverse('pasien:asesmen_hapus', kwargs={'pk': self.kunjungan.pk})
        res = self.client.post(url, {'konfirmasi': 'HAPUS'})
        self.assertRedirects(res, reverse('pasien:asesmen_rekap'))

        # 1. KunjunganPasien tetap ada (TIDAK terhapus)
        k = KunjunganPasien.objects.get(pk=self.kunjungan.pk)
        self.assertEqual(k.anamnesis_rps, '')
        self.assertEqual(k.diagnosa_masuk, '')
        self.assertEqual(k.diagnosa_keperawatan_sdki, '')
        self.assertEqual(k.skrining_jatuh_grade, '')
        self.assertIsNone(k.skrining_jatuh_skor)
        self.assertEqual(k.skrining_jatuh_detail, {})

        # 2. Artefak korelasi EP, lampiran, dan billing ASESMEN terhapus
        self.assertEqual(k.korelasi_ep.count(), 0)
        self.assertEqual(k.lampiran_asesmen.count(), 0)
        self.assertEqual(k.billing.filter(sumber='ASESMEN').count(), 0)

        # 3. CPPT, Order Lab, dan Billing MANUAL tetap UTUH
        self.assertEqual(CPPT.objects.filter(kunjungan=k).count(), 1)
        self.assertEqual(OrderPenunjang.objects.filter(kunjungan=k).count(), 1)
        self.assertEqual(k.billing.filter(sumber='MANUAL').count(), 1)

        # 4. Audit Log tercatat
        log = AuditLog.objects.filter(model_name='AsesmenKlinis', aksi='DELETE').first()
        self.assertIsNotNone(log)
        self.assertIn(f"Kunjungan #{k.pk}", log.object_repr)

    def test_row_disappears_from_rekap_after_delete(self):
        url_hapus = reverse('pasien:asesmen_hapus', kwargs={'pk': self.kunjungan.pk})
        self.client.post(url_hapus, {'konfirmasi': 'HAPUS'})

        url_rekap = reverse('pasien:asesmen_rekap')
        res = self.client.get(url_rekap)
        self.assertEqual(len(res.context['page_obj']), 0)
        self.assertNotContains(res, 'RM-REKAP-01')
        self.assertNotContains(res, 'I21.9 - Acute myocardial infarction')
