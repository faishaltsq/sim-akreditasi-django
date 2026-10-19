"""Input Capaian / Edit Indikator shortcuts on Evaluasi & Monitoring pages."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu, RisikoUnit


class LinkedIndikatorPropertyTest(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='IGD Linked', code='IGD-LNK', level=3)
        self.ind = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Door-to-ECG', kode_indikator='LNK-01',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=Decimal('90.00'),
            satuan='%', arah_target='MIN',
        )

    def test_linked_indikator_none_when_not_tied(self):
        r = RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='KLINIS', jenis_risiko='Risiko tanpa indikator',
            masalah='m', deskripsi_risiko='d', dampak=3, probabilitas=3,
        )
        self.assertIsNone(r.linked_indikator)

    def test_linked_indikator_returns_linked_master(self):
        r = RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='KLINIS', jenis_risiko='Risiko tertaut',
            masalah='m', deskripsi_risiko='d', dampak=3, probabilitas=3,
            indikator_mutu_terkait=self.ind,
        )
        self.assertEqual(r.linked_indikator.pk, self.ind.pk)


class IndikatorActionsRenderTest(TestCase):
    """The two shortcut buttons render for managers only, on both pages."""

    def setUp(self):
        self.unit = UnitKerja.objects.create(name='ICU Act', code='ICU-ACT', level=3)
        self.ind = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Hand Hygiene', kode_indikator='ACT-02',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=Decimal('85.00'),
            satuan='%', arah_target='MIN',
        )
        self.risiko = RisikoUnit.objects.create(
            unit=self.unit, tahun=2026, periode='TRIWULAN_1',
            kategori_risiko='KLINIS', jenis_risiko='Risiko terkait indikator',
            masalah='m', deskripsi_risiko='d', dampak=3, probabilitas=3,
            indikator_mutu_terkait=self.ind,
        )
        self.manager = User.objects.create_superuser('act_admin', 'a@rs.id', 'password123')
        self.staf = User.objects.create_user('act_staf', 's@rs.id', 'password123')
        self.edit_url = f'/indikator-mutu/{self.ind.pk}/edit/'
        self.capaian_url = f'/indikator-mutu/{self.ind.pk}/capaian/'

    def _login(self, user):
        self.client.force_login(user)

    def test_evaluasi_manager_sees_both_buttons(self):
        self._login(self.manager)
        resp = self.client.get(reverse('akreditasi:risiko_evaluasi',
                                       kwargs={'risiko_id': self.risiko.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.edit_url)
        self.assertContains(resp, self.capaian_url)

    def test_evaluasi_non_manager_tidak_melihat_buttons(self):
        self._login(self.staf)
        resp = self.client.get(reverse('akreditasi:risiko_evaluasi',
                                       kwargs={'risiko_id': self.risiko.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.edit_url)
        self.assertNotContains(resp, self.capaian_url)

    def test_evaluasi_risiko_tanpa_indikator_menampilkan_hint(self):
        self.risiko.indikator_mutu_terkait = None
        self.risiko.save(update_fields=['indikator_mutu_terkait'])
        self._login(self.manager)
        resp = self.client.get(reverse('akreditasi:risiko_evaluasi',
                                       kwargs={'risiko_id': self.risiko.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Tautkan indikator mutu pada tahap perencanaan')
        self.assertNotContains(resp, 'name="capaian_nilai"')

    def test_monev_manager_sees_buttons_dan_link_detail(self):
        self._login(self.manager)
        resp = self.client.get(reverse('akreditasi:risiko_monev'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.edit_url)
        self.assertContains(resp, self.capaian_url)
        self.assertContains(resp, f'/indikator-mutu/{self.ind.pk}/')
        self.assertContains(resp, 'no-print')

    def test_monev_non_manager_tidak_melihat_buttons(self):
        self._login(self.staf)
        resp = self.client.get(reverse('akreditasi:risiko_monev'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.edit_url)
        self.assertNotContains(resp, self.capaian_url)
