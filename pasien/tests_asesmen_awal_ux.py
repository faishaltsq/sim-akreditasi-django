from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
