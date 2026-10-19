"""Ekspor CSV pelaksanaan: header dan baris harus sepanjang sama."""
import csv
import io

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from akreditasi.tests_pelaksanaan_bukti_ep import _mk_category, _mk_ep, _mk_risiko
from akreditasi.risiko_models import TindakLanjutRisiko


class PelaksanaanCsvTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('csv-u', 'c@x.id', 'x')
        self.client = Client()
        self.client.force_login(self.user)
        self.cat = _mk_category()
        self.ep = _mk_ep(self.cat)
        self.risiko = _mk_risiko()
        TindakLanjutRisiko.objects.create(
            risiko=self.risiko, urutan=1, aksi='Aksi CSV', status_aksi='SEDANG',
            standar_terkait=self.cat, ep_terkait=self.ep)

    def _rows(self):
        res = self.client.get(reverse('akreditasi:risiko_pelaksanaan_export_csv'),
                              {'unit': self.risiko.unit_id, 'tahun': 2026})
        self.assertEqual(res.status_code, 200)
        return list(csv.reader(io.StringIO(res.content.decode('utf-8-sig'))))

    def test_header_and_body_have_equal_length(self):
        rows = self._rows()
        hdr = [r for r in rows if r and r[0] == 'No'][0]
        body = [r for r in rows if r and r[0].isdigit()]
        self.assertTrue(body, 'ekspor tidak menghasilkan baris data')
        for b in body:
            self.assertEqual(len(b), len(hdr))

    def test_no_duplicate_evidence_column(self):
        """'Bukti Dokumen' sudah ada; kolom 'ada_bukti' duplikat tidak boleh muncul."""
        hdr = [r for r in self._rows() if r and r[0] == 'No'][0]
        self.assertEqual(hdr.count('Bukti Dokumen'), 1)
        self.assertNotIn('ada_bukti', hdr)

    def test_standar_and_ep_columns_are_last(self):
        rows = self._rows()
        hdr = [r for r in rows if r and r[0] == 'No'][0]
        self.assertEqual(hdr[-3:], ['standar', 'kode_ep', 'judul_ep'])
        body = [r for r in rows if r and r[0].isdigit()][0]
        self.assertEqual(body[-3:], [self.cat.code, self.ep.code, self.ep.description])
