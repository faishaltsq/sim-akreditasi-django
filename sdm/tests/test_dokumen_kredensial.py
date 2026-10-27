"""Fase 3: credential document drafts, generation, and checklist wiring."""
import hashlib
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DokumenPegawai,
    EntriLogbookKlinis,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PengajuanKredensial,
    VersiDokumen,
)
from sdm.models.kredensial import DokumenSyaratKredensial
from sdm.services.dokumen_kredensial import (
    REGISTRY,
    auto_fields,
    finalize,
    generate_draft,
    render_pdf,
)
from sdm.services.syarat_kredensial import evaluate_requirements, populate_requirements
from sdm.storage_backend import SupabasePrivateStorage
from sdm.tests.test_storage_backend import FakeResponse, FakeSession


def pdf_text(pdf):
    """Readable text of a generated PDF. Test-only: pypdf is transitive."""
    from pypdf import PdfReader

    return '\n'.join(
        page.extract_text() or '' for page in PdfReader(BytesIO(pdf)).pages
    )


class DokumenKredensialBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Ruang Anak', code='HC-ANK')
        self.future_unit = UnitKerja.objects.create(name='Ruang Bedah', code='HC-BDH')
        self.manager = self._hc_user('dok-manager')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Dokumen', kategori='PPA', profesi='Perawat',
            nomor_pegawai='PGW-0007', jabatan='Perawat Pelaksana',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.future_unit,
            tanggal_mulai=self.today + timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        self.application = PengajuanKredensial.objects.create(
            employee=self.employee, unit_kerja=self.unit, jenis='REKREDENSIAL',
            submitted_by=self.manager,
        )
        self.session = FakeSession(FakeResponse(200, {}))
        self.storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co',
            api_key='service-key',
            bucket='hc-private',
            session=self.session,
        )

    def _hc_user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_review_hc_credentials = True
        config.can_manage_hc_documents = True
        config.save(update_fields=[
            'can_view_hc', 'can_review_hc_credentials',
            'can_manage_hc_documents', 'updated_at',
        ])
        for capability in ('can_view_hc', 'can_manage_hc_documents'):
            HcGrant.objects.create(
                user=user, capability=capability, unit_kerja=self.unit,
            )
        return user


class RegistryTests(DokumenKredensialBase):
    def test_registry_covers_exactly_the_seven_generatable_types(self):
        self.assertEqual(set(REGISTRY), {
            'CV', 'LOGBOOK_36BULAN', 'PENGANTAR_KSM', 'KEANGGOTAAN',
            'MALPRACTICE_RECORD', 'BEBAS_SANKSI', 'SEHAT_PSIKOLOGIS',
        })
        known_jenis = {value for value, _label in DokumenSyaratKredensial.JENIS_CHOICES}
        known_kinds = {value for value, _label in DokumenPegawai.DOCUMENT_KIND_CHOICES}
        for jenis, spec in REGISTRY.items():
            self.assertIn(jenis, known_jenis)
            self.assertTrue(spec['title'])
            self.assertTrue(spec['signatory_role'])
            self.assertIn(spec['sertifikat_jenis'], known_kinds)

    def test_every_declared_field_has_a_real_source(self):
        for jenis, spec in REGISTRY.items():
            for field, source in spec['auto_fields'] + spec['manual_fields']:
                self.assertTrue(source and source.strip(), f'{jenis}.{field}')
                self.assertNotRegex(source.strip(), r'^-+$')


class AutoFieldsTests(DokumenKredensialBase):
    def test_auto_fields_return_number_profession_and_current_unit(self):
        data = auto_fields(self.employee)
        self.assertEqual(data['nomor_pegawai'], 'PGW-0007')
        self.assertEqual(data['profesi'], 'Perawat')
        self.assertEqual(data['unit_kerja'], 'Ruang Anak')
        self.assertEqual(data['unit_kerja_kode'], 'HC-ANK')
        self.assertEqual(data['tanggal_cetak'], '27 Oktober 2026')


class FinalizeTests(DokumenKredensialBase):
    def test_finalize_stores_pdf_and_satisfies_checklist(self):
        draft = generate_draft(self.employee, 'CV', user=self.manager)
        pdf = render_pdf(draft)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 0)

        rendered = {}

        def spy(draf):
            rendered['pdf'] = render_pdf(draf)
            return rendered['pdf']

        with patch('sdm.storage.get_private_storage', return_value=self.storage), \
                patch('sdm.services.dokumen_kredensial.render_pdf', side_effect=spy):
            version = finalize(draft, user=self.manager)

        draft.refresh_from_db()
        self.assertEqual(draft.status, 'FINAL')
        self.assertEqual(draft.versi_dokumen_id, version.pk)
        self.assertEqual(VersiDokumen.objects.count(), 1)
        self.assertEqual(version.document.jenis_berkas, 'CV')
        self.assertEqual(version.document.document_type, 'CREDENTIAL')
        self.assertEqual(version.status, 'PENDING')
        self.assertEqual(version.content_type, 'application/pdf')
        self.assertEqual(
            version.sha256, hashlib.sha256(rendered['pdf']).hexdigest(),
        )
        self.assertTrue(
            any(method == 'POST' for method, _url, _kw in self.session.calls),
            'PDF harus diunggah ke private storage',
        )

        populate_requirements(self.application)
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV',
        )
        self.assertEqual(row.status, 'TERPENUHI')
        self.assertEqual(row.document_version_id, version.pk)


    def test_regenerating_reuses_one_document_and_supersedes_old_version(self):
        draft = generate_draft(self.employee, 'CV', user=self.manager)
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            first = finalize(draft, user=self.manager)
            second = finalize(draft, user=self.manager)

        self.assertEqual(
            DokumenPegawai.objects.filter(
                employee=self.employee, jenis_berkas='CV',
            ).count(),
            1,
        )
        self.assertEqual(VersiDokumen.objects.count(), 2)
        self.assertEqual(first.document_id, second.document_id)

        draft.refresh_from_db()
        self.assertEqual(draft.versi_dokumen_id, second.pk)

        # store_document_version supersedes the replaced version itself.
        first.refresh_from_db()
        self.assertEqual(first.status, 'SUPERSEDED')
        self.assertEqual(second.status, 'PENDING')
        self.assertEqual(
            sorted(VersiDokumen.objects.values_list('version_number', flat=True)),
            [1, 2],
        )

        populate_requirements(self.application)
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV',
        )
        self.assertEqual(row.status, 'TERPENUHI')
        self.assertEqual(row.document_version_id, second.pk)


class LogbookRenderTests(DokumenKredensialBase):
    def test_target_column_is_header_only_and_empty(self):
        EntriLogbookKlinis.objects.create(
            employee=self.employee, tanggal=self.today - timedelta(days=20),
            unit_kerja=self.unit, tindakan='Tindakan Uji',
            jumlah_mandiri=3, jumlah_supervisi=2,
        )
        draft = generate_draft(self.employee, 'LOGBOOK_36BULAN', user=self.manager)
        pdf = render_pdf(draft)
        self.assertTrue(pdf.startswith(b'%PDF'))
        text = pdf_text(pdf)
        self.assertIn('Target 3 tahun', text)
        self.assertNotIn('Tercapai', text)
        self.assertNotIn('350', text)
        self.assertIn('belum dikonfigurasi', text)
        # Row order: label, empty target, realization, empty status.
        self.assertIn('Tindakan Uji\n5', text)


class StatementRenderTests(DokumenKredensialBase):
    def test_statement_document_labels_signatory_and_never_claims(self):
        draft = generate_draft(self.employee, 'BEBAS_SANKSI', user=self.manager)
        pdf = render_pdf(draft)
        self.assertTrue(pdf.startswith(b'%PDF'))
        text = pdf_text(pdf)
        self.assertIn('Ketua Komite Medik', text)
        self.assertIn('PERNYATAAN DIISI DAN DITANDATANGANI OLEH', text)
        # No affirmative claim generated by the system, in any form.
        lowered = text.lower()
        self.assertNotIn('tidak pernah', lowered)
        self.assertNotIn('bebas dari sanksi', lowered)
