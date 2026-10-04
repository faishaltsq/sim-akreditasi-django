from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from akreditasi.models import UnitKerja
from accounts.models import UserProfile
from pasien.models import Pasien, KunjunganPasien, OrderPenunjang

User = get_user_model()


class LaboratoriumViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.unit_lab, _ = UnitKerja.objects.get_or_create(
            code='LAB-BDRS', defaults={'name': 'Instalasi Laboratorium', 'level': 3}
        )
        self.lab_user = User.objects.create_user('analis_test', 'analis@rs.id', 'pass123')
        profile, _ = UserProfile.objects.get_or_create(user=self.lab_user)
        profile.role = 'STAF_NAKES'
        profile.profesi = 'ANALIS_LAB'
        profile.unit_kerja = self.unit_lab
        profile.save()

        self.pasien = Pasien.objects.create(
            no_rm='RM-LAB-99', nama_lengkap='Pasien Test Lab',
            jenis_kelamin='L', tanggal_lahir='1990-01-01'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-LAB-99',
            jenis_kunjungan='IGD',
            tanggal_masuk='2026-10-04 08:00:00',
            poliklinik='Laboratorium',
            status='RAWAT'
        )
        self.order = OrderPenunjang.objects.create(
            kunjungan=self.kunjungan, jenis='LAB', nama_pemeriksaan='Darah Lengkap Rutin',
            catatan_klinis='Cek leukosit dan hemoglobin', is_critical_value=True
        )

    def test_laboratorium_dashboard_accessible_by_lab_staff(self):
        self.client.force_login(self.lab_user)
        resp = self.client.get(reverse('pasien:laboratorium_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Darah Lengkap Rutin')
        self.assertContains(resp, 'RM-LAB-99')

    def test_update_order_lab_status(self):
        self.client.force_login(self.lab_user)
        resp = self.client.post(
            reverse('pasien:order_penunjang_update', args=[self.order.pk]),
            {'status': 'SELESAI', 'hasil_pemeriksaan': 'Hb 13.5 g/dL, Leukosit 8.200 /uL', 'is_critical_value': '0'}
        )
        self.assertEqual(resp.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'SELESAI')
        self.assertFalse(self.order.is_critical_value)
        self.assertIn('Hb 13.5', self.order.hasil_pemeriksaan)
