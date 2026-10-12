import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import InsidenKeselamatan

User = get_user_model()


class InsidenManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='test_komite', password='Password@123')
        self.unit = UnitKerja.objects.create(code='IGD01', name='Instalasi Gawat Darurat')

        # Create sample incident
        self.insiden = InsidenKeselamatan.objects.create(
            unit=self.unit,
            tanggal_kejadian=datetime.date.today(),
            jenis_insiden='KTD',
            tingkat_keparahan='MODERAT',
            lokasi_kejadian='Ruang Resusitasi IGD',
            deskripsi_kejadian='Pasien salah menerima dosis obat analgesik',
            tindakan_segera='Dokter jaga segera memberikan penawar dan observasi TTV',
            pasien_terpapar=True,
            pelapor_anonim=True,
        )

    def test_insiden_daftar_login_required(self):
        """Unauthenticated access must redirect to login."""
        resp = self.client.get(reverse('akreditasi:insiden_daftar'))
        self.assertEqual(resp.status_code, 302)

    def test_insiden_daftar_authenticated(self):
        """Authenticated user can see the incident register."""
        self.client.login(username='test_komite', password='Password@123')
        resp = self.client.get(reverse('akreditasi:insiden_daftar'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Register Insiden')
        self.assertContains(resp, 'Ruang Resusitasi IGD')
        self.assertContains(resp, 'KTD')
        self.assertEqual(resp.context['stats']['total'], 1)
        self.assertEqual(resp.context['stats']['ktd'], 1)

    def test_insiden_detail_view(self):
        """Detail view renders incident breakdown and pita risiko."""
        self.client.login(username='test_komite', password='Password@123')
        resp = self.client.get(reverse('akreditasi:insiden_detail', kwargs={'pk': self.insiden.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Pita Risiko: Kuning')
        self.assertContains(resp, 'Investigasi komprehensif / RCA')

    def test_insiden_update_status(self):
        """Posting to update status successfully updates the incident."""
        self.client.login(username='test_komite', password='Password@123')
        url = reverse('akreditasi:insiden_update_status', kwargs={'pk': self.insiden.pk})
        resp = self.client.post(url, {
            'status_investigasi': 'INVESTIGASI',
            'pj_investigasi': self.user.pk,
            'rca_dilakukan': 'on',
            'catatan_investigasi': 'Tim sedang melakukan wawancara dengan perawat jaga.',
        })
        self.assertEqual(resp.status_code, 302)

        self.insiden.refresh_from_db()
        self.assertEqual(self.insiden.status_investigasi, 'INVESTIGASI')
        self.assertEqual(self.insiden.pj_investigasi, self.user)
        self.assertTrue(self.insiden.rca_dilakukan)
