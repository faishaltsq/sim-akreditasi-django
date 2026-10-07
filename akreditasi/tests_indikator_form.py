from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu

User = get_user_model()

class IndikatorFormViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_ind_test', 'admin@rs.id', 'password123')
        self.client = Client()
        self.client.force_login(self.user)
        self.unit = UnitKerja.objects.create(name='Instalasi Farmasi Uji', code='FARM-TEST-01', tipe_unit='DEPO')

    def test_get_tambah_indikator_page(self):
        url = reverse('akreditasi:indikator_tambah')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Form Indikator Mutu')

    def test_post_create_indikator_success(self):
        url = reverse('akreditasi:indikator_tambah')
        payload = {
            'nama_indikator': 'Kepatuhan Waktu Tunggu Resep Racikan',
            'kode_indikator': 'IMP-FARM-TEST-01',
            'unit': self.unit.id,
            'jenis': 'IMP_UNIT',
            'dimensi_mutu': 'TEPAT_WAKTU',
            'numerator': 'Jumlah resep racikan selesai <= 60 menit',
            'denominator': 'Total seluruh resep racikan',
            'target_nilai': '85.00',
            'satuan': '%',
            'rencana_aksi': 'Evaluasi alur compounding harian',
            'pj': 'Kepala Farmasi',
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(IndikatorMutu.objects.filter(kode_indikator='IMP-FARM-TEST-01').exists())

    def test_get_and_post_edit_indikator(self):
        ind = IndikatorMutu.objects.create(
            nama_indikator='Indikator Lama',
            kode_indikator='IMP-OLD-01',
            unit=self.unit,
            jenis='IMP_UNIT',
            dimensi_mutu='AMAN',
            numerator='Num',
            denominator='Den',
            target_nilai='100.00',
            satuan='%',
        )
        url_edit = reverse('akreditasi:indikator_edit', kwargs={'indikator_id': ind.pk})
        res_get = self.client.get(url_edit)
        self.assertEqual(res_get.status_code, 200)

        payload_edit = {
            'nama_indikator': 'Indikator Diedit',
            'kode_indikator': 'IMP-OLD-01',
            'unit': self.unit.id,
            'jenis': 'IMP_UNIT',
            'dimensi_mutu': 'EFEKTIF',
            'numerator': 'Num Baru',
            'denominator': 'Den Baru',
            'target_nilai': '95.00',
            'satuan': '%',
            'rencana_aksi': 'Rencana Baru',
            'pj': 'PJ Baru',
        }
        res_post = self.client.post(url_edit, payload_edit)
        self.assertEqual(res_post.status_code, 302)
        ind.refresh_from_db()
        self.assertEqual(ind.nama_indikator, 'Indikator Diedit')
        self.assertEqual(ind.dimensi_mutu, 'EFEKTIF')


class IndikatorAIEndpointTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser('admin_ai_test', 'ai@rs.id', 'password123')
        self.client = Client()
        self.client.force_login(self.user)

    def test_ai_endpoint_rejects_missing_nama(self):
        import json
        url = reverse('akreditasi:api_ai_rumus_indikator')
        res = self.client.post(url, data=json.dumps({}), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])
