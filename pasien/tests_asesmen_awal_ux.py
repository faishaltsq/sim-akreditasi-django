from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from pasien.models import KunjunganPasien, Pasien


class MstAutoCalcTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('mstuser')
        self.client.force_login(self.user)
        self.pasien = Pasien.objects.create(
            no_rm='RM-MST-001', nik='3201000000000101', nama_lengkap='Mst Pasien',
            tanggal_lahir='1990-01-01', jenis_kelamin='L')
        self.k = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='IGD', no_kunjungan='IGD-MST-001',
            tanggal_masuk=timezone.now())

    def _post(self, **extra):
        return self.client.post(
            reverse('pasien:igd_asesmen_awal_save', args=[self.k.pk]),
            {'anamnesis_rps': 'Sakit', **extra})

    def test_mst_score_computed_from_two_questions(self):
        self._post(mst_q1='2', mst_q2='1')
        self.k.refresh_from_db()
        self.assertEqual(self.k.skrining_gizi_mst, 3)

    def test_mst_zero_when_no_risk_answers(self):
        self._post(mst_q1='0', mst_q2='0')
        self.k.refresh_from_db()
        self.assertEqual(self.k.skrining_gizi_mst, 0)

    def test_legacy_manual_score_still_accepted(self):
        self._post(skrining_gizi_mst='4')  # POST lama tanpa mst_q*
        self.k.refresh_from_db()
        self.assertEqual(self.k.skrining_gizi_mst, 4)

    def test_mst_inputs_rendered_in_igd_dashboard(self):
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertContains(res, 'name="mst_q1"')
        self.assertContains(res, 'name="mst_q2"')
        self.assertContains(res, f'mstResult_{self.k.pk}')


class SmartDefaultUiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('smartuser')
        self.client.force_login(self.user)
        self.pasien = Pasien.objects.create(
            no_rm='RM-SMART-001', nik='3201000000000104', nama_lengkap='Smart Pasien',
            tanggal_lahir='1995-05-05', jenis_kelamin='P')
        self.k = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='IGD', no_kunjungan='IGD-SMART-001',
            tanggal_masuk=timezone.now())

    def test_igd_dashboard_has_smart_default_and_pain_slider(self):
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertContains(res, 'setNormalAsesmen')
        self.assertContains(res, 'type="range"')
        self.assertContains(res, f'skorNyeriBadge_{self.k.pk}')
        self.assertContains(res, 'Set Normal / Baik')


class AlergiDanCopyPrevTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('asesmenuser')
        self.client.force_login(self.user)
        self.pasien = Pasien.objects.create(
            no_rm='RM-COPY-001', nik='3201000000000102',
            nama_lengkap='Copy Prev', tanggal_lahir='1985-03-03', jenis_kelamin='P',
            alergi_obat='Debu, Udang')
        self.prev = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='IGD',
            no_kunjungan='IGD-PREV', tanggal_masuk=timezone.now() - timedelta(days=5),
            anamnesis_rps='Batuk sejak seminggu', keadaan_umum='Sedang',
            kesadaran='Compos Mentis', skrining_gizi_mst=2, status_psikososial='Cemas / Gelisah')
        self.k = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='IGD',
            no_kunjungan='IGD-NEW', tanggal_masuk=timezone.now())

    def test_alergi_banner_shown_in_igd_dashboard(self):
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertContains(res, 'Debu, Udang')

    def test_copy_from_previous_assessment(self):
        res = self.client.get(reverse('pasien:igd_asesmen_copy_prev', args=[self.k.pk]))
        self.assertRedirects(res, reverse('pasien:igd_dashboard'))
        self.k.refresh_from_db()
        self.assertEqual(self.k.anamnesis_rps, 'Batuk sejak seminggu')
        self.assertEqual(self.k.keadaan_umum, 'Sedang')
        self.assertEqual(self.k.skrining_gizi_mst, 2)
        self.assertEqual(self.k.status_psikososial, 'Cemas / Gelisah')

    def test_copy_prev_no_previous_is_noop(self):
        k2 = KunjunganPasien.objects.create(
            pasien=Pasien.objects.create(
                no_rm='RM-COPY-002', nik='3201000000000103', nama_lengkap='No Prev',
                tanggal_lahir='1990-01-01', jenis_kelamin='L'),
            jenis_kunjungan='IGD', no_kunjungan='IGD-NOPREV', tanggal_masuk=timezone.now())
        res = self.client.get(reverse('pasien:igd_asesmen_copy_prev', args=[k2.pk]))
        self.assertEqual(res.status_code, 302)


class SidebarMenuTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('sidebaruser', 'sidebar@test.com', 'password123')
        self.profile = UserProfile.objects.create(user=self.user, role='ADMIN_RS')
        self.client.force_login(self.user)

    def test_sidebar_has_jadwal_logbook_menus(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(res, 'tab=shift')
        self.assertContains(res, 'Jadwal Dinas')

    def test_tab_shift_activated_by_query_param(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard') + '?tab=shift')
        content = res.content.decode()
        self.assertIn('id="tab-shift" data-bs-toggle="tab" data-bs-target="#pane-shift" type="button" role="tab"', content)
        self.assertIn('tab-shift" data-bs-toggle="tab" data-bs-target="#pane-shift" type="button" role="tab"', content)
        self.assertContains(res, 'id="pane-shift" role="tabpanel"')
        # check that tab-shift has active class
        self.assertTrue('active' in content[content.find('id="tab-shift"')-30:content.find('id="tab-shift"')+40])
        self.assertTrue('active' in content[content.find('id="pane-shift"')-30:content.find('id="pane-shift"')+40])
