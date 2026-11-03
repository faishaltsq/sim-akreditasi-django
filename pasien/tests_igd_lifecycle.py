from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien
from akreditasi.kontrol_data import ACTIVE_VISIT_STATUSES, _layanan_block
from akreditasi.models import UnitKerja
from accounts.models import UserProfile

User = get_user_model()


class IGDActiveStatusesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dokter_igd', password='password123')
        self.unit_igd, _ = UnitKerja.objects.get_or_create(
            code='IGD',
            defaults={'name': 'Instalasi Gawat Darurat', 'level': 3}
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.role = 'STAF_NAKES'
        self.profile.unit_kerja = self.unit_igd
        self.profile.save()

        self.pasien = Pasien.objects.create(
            no_rm='RM-STAT-01',
            nama_lengkap='Pasien Penunjang',
            tanggal_lahir='1990-01-01',
            jenis_kelamin='L'
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-STAT-01',
            jenis_kunjungan='IGD',
            status='PENUNJANG',
            triage='KUNING',
            tanggal_masuk=timezone.now()
        )

    def test_penunjang_and_tindakan_in_active_statuses(self):
        self.assertIn('PENUNJANG', ACTIVE_VISIT_STATUSES)
        self.assertIn('TINDAKAN', ACTIVE_VISIT_STATUSES)
        self.assertIn('DISPOSISI', ACTIVE_VISIT_STATUSES)

    def test_active_igd_patient_in_layanan_block(self):
        block = _layanan_block(self.unit_igd, on_date=timezone.localdate())
        no_kunjungan_list = [item['no_kunjungan'] for item in block['items']]
        self.assertIn('KUNJ-STAT-01', no_kunjungan_list)

    def test_edit_kunjungan_igd(self):
        self.client.force_login(self.user)
        url = reverse('pasien:igd_kunjungan_edit', kwargs={'pk': self.kunjungan.pk})
        response = self.client.post(url, {
            'catatan_admisi': 'Nyeri dada menjalar ke punggung',
            'dpjp': 'dr. Pratama',
            'triage': 'MERAH',
            'penjamin': 'BPJS',
            'diagnosa_masuk': 'I21.9 - Acute Myocardial Infarction'
        })
        self.assertEqual(response.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.triage, 'MERAH')
        self.assertEqual(self.kunjungan.penjamin, 'BPJS')
        self.assertEqual(self.kunjungan.catatan_admisi, 'Nyeri dada menjalar ke punggung')

    def test_batal_kunjungan_igd(self):
        self.client.force_login(self.user)
        url = reverse('pasien:igd_kunjungan_batal', kwargs={'pk': self.kunjungan.pk})
        response = self.client.post(url, {
            'alasan_batal': 'Salah input registrasi ganda'
        })
        self.assertEqual(response.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status, 'BATAL')
        self.assertIn('Salah input registrasi ganda', self.kunjungan.catatan_admisi)

    def test_update_status_kunjungan_igd(self):
        self.client.force_login(self.user)
        url = reverse('pasien:igd_status_update', kwargs={'pk': self.kunjungan.pk})
        response = self.client.post(url, {'status': 'TINDAKAN'})
        self.assertEqual(response.status_code, 302)
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status, 'TINDAKAN')

    def test_update_status_kunjungan_ajax(self):
        self.client.force_login(self.user)
        url = reverse('pasien:igd_status_update', kwargs={'pk': self.kunjungan.pk})
        response = self.client.post(url, {'status': 'DISPOSISI'}, headers={'x-requested-with': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.kunjungan.refresh_from_db()
        self.assertEqual(self.kunjungan.status, 'DISPOSISI')
