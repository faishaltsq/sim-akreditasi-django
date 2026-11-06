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


class KunjunganDetailAsesmenUxTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_asesmen', 'admin@example.com', 'password123')
        self.client.force_login(self.user)
        self.pasien = Pasien.objects.create(
            no_rm='RM-DET-001', nik='3201000000000999', nama_lengkap='Pasien Detail UX',
            tanggal_lahir='1985-05-15', jenis_kelamin='P')
        self.k = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='IGD', no_kunjungan='IGD-DET-001',
            tanggal_masuk=timezone.now())

    def test_detail_page_links_to_full_page_assessment(self):
        """Kontrak baru: detail halaman TIDAK lagi merender modal asesmen;
        tombolnya menjadi tautan ke halaman penuh yang memuat wizard."""
        res = self.client.get(reverse('pasien:kunjungan_detail', args=[self.k.pk]))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        # Modal dihapus; tombol menjadi tautan ke halaman asesmen penuh.
        self.assertNotIn('id="modalEditAsesmenAwal"', html)
        self.assertIn(reverse('pasien:kunjungan_asesmen_awal', args=[self.k.pk]), html)
        self.assertNotIn('pillsAsesmenDetailTab', html)

    def test_full_page_renders_4_step_tabs_and_ttv_fields(self):
        res = self.client.get(reverse('pasien:kunjungan_asesmen_awal', args=[self.k.pk]))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        # 4-step wizard tabs
        self.assertIn('pillsAsesmenDetailTab', content)
        self.assertIn('tab-ku-ttv-pane', content)
        self.assertIn('tab-nyeri-gizi-pane', content)
        self.assertIn('tab-fungsional-fisik-pane', content)
        self.assertIn('tab-diagnosa-risiko-pane', content)
        # TTV fields
        self.assertIn('name="ttv_sistole"', content)
        self.assertIn('name="ttv_diastole"', content)
        self.assertIn('name="ttv_nadi"', content)
        self.assertIn('name="ttv_rr"', content)
        self.assertIn('name="ttv_suhu"', content)
        self.assertIn('name="ttv_spo2"', content)
        self.assertIn('name="ttv_gcs"', content)
        # Smart default & buttons — action bar + form
        self.assertIn('setNormalDetail', content)
        self.assertIn('id="asesmenAwalForm"', content)
        self.assertIn('Simpan Draft', content)
        self.assertIn('Simpan &amp; Selesaikan Asesmen', content)
        self.assertIn('globalIcd10List', content)
        self.assertIn('globalSdkiList', content)

    def test_copy_returns_to_full_page(self):
        target = reverse('pasien:kunjungan_asesmen_awal', args=[self.k.pk])
        response = self.client.get(
            reverse('pasien:igd_asesmen_copy_prev', args=[self.k.pk]), {'next': target})
        self.assertRedirects(response, target)

    def test_post_save_asesmen_draft_updates_ttv_and_redirects(self):
        target = reverse('pasien:kunjungan_asesmen_awal', args=[self.k.pk])
        payload = {
            'next_url': target,
            'action_mode': 'draft',
            'ttv_sistole': '130',
            'ttv_diastole': '85',
            'ttv_nadi': '84',
            'ttv_rr': '20',
            'ttv_suhu': '36.8',
            'ttv_spo2': '98',
            'ttv_gcs': 'E4V5M6 (15)',
            'anamnesis_rps': 'Pasien pusing dan mual sejak tadi pagi',
            'keadaan_umum': 'Sedang',
            'kesadaran': 'Compos Mentis',
        }
        res = self.client.post(
            reverse('pasien:igd_asesmen_awal_save', args=[self.k.pk]),
            payload,
            follow=True,
        )
        self.assertRedirects(res, target)
        self.k.refresh_from_db()
        self.assertEqual(self.k.ttv_sistole, 130)
        self.assertEqual(self.k.ttv_diastole, 85)
        self.assertEqual(self.k.ttv_nadi, 84)
        self.assertEqual(self.k.ttv_rr, 20)
        self.assertEqual(float(self.k.ttv_suhu), 36.8)
        self.assertEqual(self.k.ttv_spo2, 98)
        self.assertEqual(self.k.ttv_gcs, 'E4V5M6 (15)')
        self.assertEqual(self.k.anamnesis_rps, 'Pasien pusing dan mual sejak tadi pagi')

    def test_post_save_asesmen_selesai_marks_complete(self):
        payload = {
            'action_mode': 'selesai',
            'keadaan_umum': 'Baik',
            'kesadaran': 'Compos Mentis',
            'ttv_sistole': '120',
            'ttv_diastole': '80',
            'ttv_nadi': '80',
            'ttv_rr': '18',
            'ttv_suhu': '36.5',
            'ttv_spo2': '98',
            'ttv_gcs': 'E4V5M6 (15)',
            'anamnesis_rps': 'Evaluasi rutin kondisi klinis',
            'ttv_skala_nyeri': '0',
            'nyeri_karakteristik': 'Tidak Nyeri',
            'mst_q1': '0',
            'mst_q2': '0',
            'fungsional_adl': 'Mandiri',
            'fisik_kepala_leher': 'Normosefali',
            'fisik_dada_toraks': 'Suara napas vesikuler',
            'fisik_abdomen': 'Supel',
            'fisik_ekstremitas': 'Akral hangat, CRT < 2d',
            'fisik_integumen_kulit': 'Turgor baik',
            'diagnosa_masuk': 'A09.9 - Gastroenteritis',
            'diagnosa_keperawatan_sdki': 'D.0023 - Nyeri Akut',
        }
        res = self.client.post(
            reverse('pasien:igd_asesmen_awal_save', args=[self.k.pk]),
            payload,
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.k.refresh_from_db()
        self.assertTrue(self.k.is_asesmen_awal_lengkap)
        messages = [m.message for m in res.context['messages']]
        self.assertTrue(any('selesai dan lengkap' in m for m in messages))

    def test_post_save_asesmen_with_comma_in_suhu(self):
        payload = {
            'action_mode': 'draft',
            'ttv_suhu': '36,5',
            'anamnesis_rps': 'Cek suhu dengan koma',
        }
        res = self.client.post(
            reverse('pasien:igd_asesmen_awal_save', args=[self.k.pk]),
            payload,
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.k.refresh_from_db()
        self.assertEqual(self.k.ttv_suhu, 36.5)

    def test_modal_placement_and_wizard_navigation(self):
        res = self.client.get(reverse('pasien:kunjungan_asesmen_awal', args=[self.k.pk]))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')

        # Halaman penuh: wizard ada di dalam form, bukan di dalam modal.
        self.assertIn('id="asesmenAwalForm"', html)
        self.assertNotIn('id="modalEditAsesmenAwal"', html)
        # Wizard buttons and tab controls
        self.assertIn('goToAsesmenTab', html)
        self.assertIn('data-bs-toggle="tab"', html)
        self.assertIn('id="globalIcd10List"', html)
        self.assertIn('id="globalSdkiList"', html)
