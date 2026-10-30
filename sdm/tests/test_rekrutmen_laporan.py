import json
import tempfile
from datetime import timedelta
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import BerkasPelamar, HasilMCU, HcGrant, Lamaran, Lowongan, PenilaianTahap
from sdm.rekrutmen_laporan_views import bukti_audit, dashboard_export
from sdm.services.rekrutmen_laporan import audit_package, dashboard_rows
from sdm.services.rekrutmen_laporan import dashboard_pdf
from reportlab.platypus import Table
from django.urls import resolve


class RecruitmentReportingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reporter')
        self.unit = UnitKerja.objects.create(name='Unit Rekrutmen', code='RPT')
        self.other = UnitKerja.objects.create(name='Unit Lain', code='OTHER')
        for capability in ('can_manage_hc_recruitment', 'can_export_hc'):
            HcGrant.objects.create(user=self.user, unit_kerja=self.unit, capability=capability)
        self.vacancy = Lowongan.objects.create(unit_kerja=self.unit, profesi='Perawat',
                                               judul='Perawat', jumlah_kebutuhan=2)
        self.application = Lamaran.objects.create(lowongan=self.vacancy, nama_pelamar='Pelamar')
        self.request = RequestFactory().get('/')
        self.request.user = self.user

    def test_latest_stage_verdict_counted_once_and_scope_applied(self):
        now = timezone.now()
        PenilaianTahap.objects.create(lamaran=self.application, tahap='SELEKSI_ADMIN',
                                      hasil='LULUS', dinilai_at=now - timedelta(days=1))
        PenilaianTahap.objects.create(lamaran=self.application, tahap='SELEKSI_ADMIN',
                                      hasil='TIDAK_LULUS', dinilai_at=now)
        Lowongan.objects.create(unit_kerja=self.other, profesi='Lain', judul='Rahasia')
        rows = dashboard_rows(UnitKerja.objects.filter(pk=self.unit.pk))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['cells'][4:7], (1, 0, 0))

    def test_pdf_uses_dashboard_rows(self):
        with patch('sdm.rekrutmen_laporan_views.dashboard_pdf', return_value=b'%PDF-') as pdf:
            response = dashboard_export(self.request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pdf.call_args.args[0][0]['cells'][0], str(self.vacancy.pk))

    def test_pdf_contains_same_table_values(self):
        rows = dashboard_rows(UnitKerja.objects.filter(pk=self.unit.pk))
        with patch('sdm.services.rekrutmen_laporan.Table', wraps=Table) as table:
            result = dashboard_pdf(rows)
        self.assertTrue(result.startswith(b'%PDF-'))
        cells = table.call_args.args[0][1]
        self.assertEqual([cell.getPlainText() for cell in cells],
                         [str(value) for value in rows[0]['cells']])

    def test_independent_routes_resolve(self):
        urlconf = 'sdm.rekrutmen_laporan_urls'
        self.assertEqual(resolve('/', urlconf=urlconf).url_name, 'dashboard')
        self.assertEqual(resolve('/rekap.pdf', urlconf=urlconf).url_name, 'dashboard_export')
        self.assertEqual(resolve(f'/lamaran/{self.application.pk}/bukti.zip',
                                 urlconf=urlconf).url_name, 'bukti_audit')

    def test_medical_grant_required_for_audit(self):
        with self.assertRaises(PermissionDenied):
            bukti_audit(self.request, self.application.pk)
        HcGrant.objects.create(user=self.user, unit_kerja=self.unit, capability='hc_health_read')
        response = bukti_audit(self.request, self.application.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(json.loads(archive.read('bukti.json'))['lamaran']['nama'], 'Pelamar')

    def test_cross_unit_audit_hidden(self):
        vacancy = Lowongan.objects.create(unit_kerja=self.other, profesi='Lain', judul='Lain')
        application = Lamaran.objects.create(lowongan=vacancy, nama_pelamar='Lain')
        with self.assertRaises(Http404):
            bukti_audit(self.request, application.pk)

    def test_archive_includes_uploaded_files_and_verification(self):
        with tempfile.TemporaryDirectory() as root, override_settings(MEDIA_ROOT=root):
            doc = BerkasPelamar(lamaran=self.application, jenis='STR', status='VALID')
            doc.berkas.save('str.pdf', ContentFile(b'STR'))
            mcu = HasilMCU(lamaran=self.application, status='FIT', catatan='Catatan')
            mcu.berkas.save('mcu.pdf', ContentFile(b'MCU'))
            with ZipFile(BytesIO(audit_package(self.application))) as archive:
                payload = json.loads(archive.read('bukti.json'))
                self.assertEqual(payload['berkas'][0]['status'], 'VALID')
                self.assertEqual(payload['mcu']['catatan'], 'Catatan')
                self.assertIn(b'STR', [archive.read(name) for name in archive.namelist()])
                self.assertIn(b'MCU', [archive.read(name) for name in archive.namelist()])
