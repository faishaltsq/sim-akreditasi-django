"""
Regresi bug 405 Method Not Allowed pada unggah dokumen Indikator Mutu.

Link "unggah" di tabel Dokumen Bukti /indikator-mutu/<id>/ mengarah ke view
upload_bukti yang dulu dibungkus @require_POST, sehingga klik link (GET) selalu
balas 405. View kini menerima GET sebagai halaman unggah, dan POST tetap
menyimpan berkas — dengan dukungan ?next= untuk kembali ke halaman pemicu.
"""
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from akreditasi.models import (
    Category, EvidenceFile, EvidenceReq, Framework, StandardItem,
)


class UploadBuktiViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username='admin_bukti', password='password123', email='bukti@test.com')
        fw = Framework.objects.create(name='STARKES UJI 405')
        cat = Category.objects.create(
            framework=fw, code='TKRS', name='Tata Kelola Rumah Sakit', order=1)
        cls.ep = StandardItem.objects.create(
            category=cat,
            sub_standard='TKRS 1',
            sub_title='Representasi Pemilik',
            code='TKRS-UJI-EP-405',
            description='Rumah sakit menetapkan upaya peningkatan mutu dan keselamatan pasien.',
        )
        cls.req = EvidenceReq.objects.create(
            standard_item=cls.ep,
            category_type='R',
            title='SK Direktur tentang Tim Mutu dan Keselamatan Pasien',
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)
        # Simpan berkas uji di direktori sementara, bukan media/ repo
        self._media = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        self._media.enable()
        self.addCleanup(self._media.disable)

    def _url(self, **params):
        from urllib.parse import urlencode
        base = reverse('akreditasi:upload_bukti', kwargs={'req_id': self.req.pk})
        return f"{base}?{urlencode(params)}" if params else base

    def test_get_renders_upload_page_instead_of_405(self):
        """GET ke endpoint unggah harus 200 (dulu 405 Method Not Allowed)."""
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Unggah Berkas Bukti')
        self.assertContains(resp, self.req.title)
        self.assertContains(resp, 'name="file"')

    def test_get_keeps_local_next_and_rejects_external_next(self):
        local_next = reverse('akreditasi:indikator_detail', kwargs={'indikator_id': 1})

        resp = self.client.get(self._url(next=local_next))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['back_url'], local_next)

        # Open redirect ditolak: jatuh kembali ke halaman detail EP
        resp = self.client.get(self._url(next='https://evil.example/pencuri'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.context['back_url'],
            reverse('akreditasi:ep_detail', kwargs={'item_id': self.ep.pk}),
        )

    def test_post_saves_file_and_returns_to_caller(self):
        target = reverse('akreditasi:indikator_detail', kwargs={'indikator_id': 7})
        uploaded = SimpleUploadedFile(
            'laporan_mutu.pdf', b'%PDF-1.4 laporan mutu', content_type='application/pdf')

        resp = self.client.post(self._url(next=target), {'file': uploaded})

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], target)
        self.assertTrue(EvidenceFile.objects.filter(file_name='laporan_mutu.pdf').exists())

    def test_post_without_next_falls_back_to_ep_detail(self):
        uploaded = SimpleUploadedFile(
            'bukti_lain.pdf', b'%PDF-1.4 bukti lain', content_type='application/pdf')

        resp = self.client.post(self._url(), {'file': uploaded})

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp['Location'],
            reverse('akreditasi:ep_detail', kwargs={'item_id': self.ep.pk}),
        )

    def test_indicator_detail_link_targets_upload_page(self):
        """Link unggah di halaman detail indikator harus membawa ?next=."""
        from akreditasi.risiko_models import IndikatorMutu
        from akreditasi.models import UnitKerja

        unit = UnitKerja.objects.create(name='Unit Mutu', code='MUTU')
        ind = IndikatorMutu.objects.create(
            kode_indikator='INM-UJI-01',
            nama_indikator='Kepatuhan Cuci Tangan',
            dimensi_mutu='AMAN',
            numerator='Patuh',
            denominator='Peluang',
            unit=unit,
            target_nilai=85.0,
            ep_terkait=self.ep,
        )
        ind_url = reverse('akreditasi:indikator_detail', kwargs={'indikator_id': ind.pk})

        resp = self.client.get(ind_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"{reverse('akreditasi:upload_bukti', kwargs={'req_id': self.req.pk})}?next=")
