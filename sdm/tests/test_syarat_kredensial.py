"""C-3: per-request supporting-document requirement checklist."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DokumenPegawai,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PengajuanKredensial,
    PeristiwaSDM,
    VersiDokumen,
)
from sdm.models.kredensial import DokumenSyaratKredensial
from sdm.services.syarat_kredensial import (
    DEFAULT_ROWS,
    evaluate_requirements,
    populate_requirements,
)


class SyaratBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Syarat', code='HC-SYR')
        self.manager = self._hc_user('syarat-manager')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Syarat', kategori='PPA', profesi='Perawat',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )
        self.application = PengajuanKredensial.objects.create(
            employee=self.employee, unit_kerja=self.unit, jenis='REKREDENSIAL',
            submitted_by=self.manager,
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
        HcGrant.objects.create(user=user, capability='can_view_hc', unit_kerja=self.unit)
        HcGrant.objects.create(
            user=user, capability='can_review_hc_credentials', unit_kerja=self.unit,
        )
        HcGrant.objects.create(
            user=user, capability='can_manage_hc_documents', unit_kerja=self.unit,
        )
        return user

    def _document(self, *, kind, document_type='CREDENTIAL', sensitivity='personnel',
                  status='VERIFIED', valid_until=None, title=None):
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type=document_type,
            jenis_berkas=kind, title=title or kind, sensitivity=sensitivity,
        )
        return VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='uji.pdf',
            storage_key=f'{sensitivity}/{self.employee.pk}/{document.pk}.pdf',
            sha256='c' * 64, size_bytes=10, content_type='application/pdf',
            status=status, valid_until=valid_until,
        )


class PopulateTests(SyaratBase):
    def test_populate_twice_yields_one_row_set(self):
        populate_requirements(self.application)
        first = set(
            DokumenSyaratKredensial.objects.filter(
                pengajuan=self.application
            ).values_list('jenis', flat=True)
        )
        populate_requirements(self.application)
        second = list(
            DokumenSyaratKredensial.objects.filter(
                pengajuan=self.application
            ).values_list('jenis', flat=True)
        )
        self.assertEqual(sorted(first), sorted(second))
        self.assertEqual(len(second), len(set(second)))

    def test_recredential_covers_all_six_domains(self):
        populate_requirements(self.application)
        domains = set(
            DokumenSyaratKredensial.objects.filter(
                pengajuan=self.application
            ).values_list('domain', flat=True)
        )
        self.assertEqual(domains, {'LEGA', 'KOMP', 'SEHAT', 'ETIK', 'KINE', 'PROS'})


class EvaluateTests(SyaratBase):
    def test_expired_version_does_not_satisfy(self):
        populate_requirements(self.application)
        self._document(
            kind='CV', valid_until=self.today - timedelta(days=1),
            title='CV kadaluarsa',
        )
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV'
        )
        self.assertEqual(row.status, 'KURANG')
        self.assertIsNone(row.document_version_id)

    def test_current_version_satisfies_and_links(self):
        populate_requirements(self.application)
        version = self._document(
            kind='CV', valid_until=self.today + timedelta(days=400),
        )
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV'
        )
        self.assertEqual(row.status, 'TERPENUHI')
        self.assertEqual(row.document_version_id, version.pk)

    def test_undated_document_still_satisfies(self):
        populate_requirements(self.application)
        version = self._document(kind='CV', valid_until=None)
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV'
        )
        self.assertEqual(row.status, 'TERPENUHI')
        self.assertEqual(row.document_version_id, version.pk)

    def test_health_kind_resolves_health_sensitivity_document(self):
        populate_requirements(self.application)
        self._document(
            kind='PSIKOLOGIS', document_type='HEALTH', sensitivity='health',
            valid_until=self.today + timedelta(days=400),
        )
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='SEHAT_PSIKOLOGIS'
        )
        self.assertEqual(row.status, 'TERPENUHI')

    def test_logbook_row_uses_structured_entries(self):
        from sdm.models import EntriLogbookKlinis, KatalogTindakan
        from sdm.models import MasterJenjangProfesi, MasterProfesiPegawai
        populate_requirements(self.application)
        profesi = MasterProfesiPegawai.objects.create(
            code='P-LOG', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        jenjang = MasterJenjangProfesi.objects.create(
            profesi=profesi, kode='PK-L', nama='Perawat I', urutan=1,
        )
        katalog = KatalogTindakan.objects.create(
            kode='PR-LOG', nama='Tindakan', jenjang=jenjang, tingkat_supervisi='M',
        )
        EntriLogbookKlinis.objects.create(
            employee=self.employee, tanggal=self.today,
            unit_kerja=self.unit, katalog_tindakan=katalog, jumlah_mandiri=3,
        )
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='LOGBOOK_36BULAN'
        )
        self.assertEqual(row.status, 'TERPENUHI')
        self.assertTrue(row.logbook_ok)

    def test_workflow_rows_are_informational(self):
        populate_requirements(self.application)
        evaluate_requirements(self.application)
        for jenis in ('SURAT_PERMOHONAN', 'BERITA_ACARA', 'REKOMENDASI_KOMITE'):
            row = DokumenSyaratKredensial.objects.get(
                pengajuan=self.application, jenis=jenis
            )
            self.assertEqual(row.status, 'INFO', jenis)

    def test_default_rows_map_to_known_kinds(self):
        kinds = {row['jenis'] for row in DEFAULT_ROWS}
        self.assertIn('CV', kinds)
        self.assertIn('SEHAT_PSIKOLOGIS', kinds)
        self.assertIn('BEBAS_SANKSI', kinds)

    def test_eligibility_today_counts_as_valid(self):
        populate_requirements(self.application)
        self._document(kind='CV', valid_until=self.today)
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV'
        )
        self.assertEqual(row.status, 'TERPENUHI')

    def test_rejected_latest_version_does_not_satisfy(self):
        populate_requirements(self.application)
        self._document(
            kind='CV', status='REJECTED',
            valid_until=self.today + timedelta(days=400),
        )
        evaluate_requirements(self.application)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV'
        )
        self.assertEqual(row.status, 'KURANG')


class SyaratModelTests(SyaratBase):
    def test_workflow_row_cannot_be_hand_ticked(self):
        from django.core.exceptions import ValidationError
        row = DokumenSyaratKredensial(
            pengajuan=self.application, domain='PROS', jenis='SURAT_PERMOHONAN',
            status='TERPENUHI',
        )
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_non_workflow_row_needs_evidence(self):
        from django.core.exceptions import ValidationError
        row = DokumenSyaratKredensial(
            pengajuan=self.application, domain='LEGA', jenis='CV', status='TERPENUHI',
        )
        with self.assertRaises(ValidationError):
            row.full_clean()


class SyaratRouteTests(SyaratBase):
    def setUp(self):
        super().setUp()
        populate_requirements(self.application)
        self.version = self._document(
            kind='CV', valid_until=self.today + timedelta(days=400),
        )

    def test_detail_shows_checklist_grouped_by_domain(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:kredensial_detail', args=[self.application.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kelengkapan Dokumen Pendukung')
        content = response.content.decode('utf-8')
        for label in ('Legalitas', 'Kompetensi', 'Kesehatan', 'Etik',
                      'Kinerja', 'Administrasi'):
            self.assertIn(label, content)

    def test_link_version_satisfies_row_and_writes_audit(self):
        self.client.force_login(self.manager)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV'
        )
        before = PeristiwaSDM.objects.filter(jenis_peristiwa='syarat_linked').count()
        response = self.client.post(
            reverse('sdm:kredensial_syarat_tautkan', args=[self.application.pk, row.pk]),
            {'document_version': str(self.version.pk)},
        )
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.document_version_id, self.version.pk)
        self.assertEqual(row.status, 'TERPENUHI')
        self.assertEqual(
            PeristiwaSDM.objects.filter(jenis_peristiwa='syarat_linked').count(),
            before + 1,
        )

    def test_linking_workflow_row_is_rejected(self):
        self.client.force_login(self.manager)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='SURAT_PERMOHONAN'
        )
        response = self.client.post(
            reverse('sdm:kredensial_syarat_tautkan', args=[self.application.pk, row.pk]),
            {'document_version': str(self.version.pk)},
        )
        self.assertEqual(response.status_code, 400)
        row.refresh_from_db()
        self.assertEqual(row.status, 'INFO')
        self.assertIsNone(row.document_version_id)

    def test_upload_stores_privately_and_links(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.manager)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV'
        )
        before = PeristiwaSDM.objects.filter(jenis_peristiwa='syarat_linked').count()
        upload = SimpleUploadedFile(
            'cv.pdf', b'%PDF-1.4 data', content_type='application/pdf',
        )
        response = self.client.post(
            reverse('sdm:kredensial_syarat_upload', args=[self.application.pk, row.pk]),
            {'berkas': upload},
        )
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertIsNotNone(row.document_version_id)
        version = row.document_version
        self.assertTrue(version.sha256)
        self.assertFalse(version.document.sensitivity != 'personnel')
        self.assertEqual(
            PeristiwaSDM.objects.filter(jenis_peristiwa='syarat_linked').count(),
            before + 1,
        )

    def test_outsider_cannot_link(self):
        outsider_unit = UnitKerja.objects.create(name='Unit Asing S', code='HC-SYO')
        outsider = get_user_model().objects.create_user(username='syarat-outsider')
        UserProfile.objects.create(user=outsider, role='ADMIN_RS', unit_kerja=outsider_unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_review_hc_credentials = True
        config.save(update_fields=[
            'can_view_hc', 'can_review_hc_credentials', 'updated_at',
        ])
        HcGrant.objects.create(user=outsider, capability='can_view_hc', unit_kerja=outsider_unit)
        HcGrant.objects.create(
            user=outsider, capability='can_review_hc_credentials', unit_kerja=outsider_unit,
        )
        self.client.force_login(outsider)
        row = DokumenSyaratKredensial.objects.get(
            pengajuan=self.application, jenis='CV'
        )
        response = self.client.post(
            reverse('sdm:kredensial_syarat_tautkan', args=[self.application.pk, row.pk]),
            {'document_version': str(self.version.pk)},
        )
        self.assertEqual(response.status_code, 404)


class BuktiAuditPrintTests(SyaratBase):
    def setUp(self):
        super().setUp()
        populate_requirements(self.application)
        self._document(kind='CV', valid_until=self.today + timedelta(days=400))

    def test_printed_sheet_lists_domain_status_and_renumbered_section(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:kredensial_bukti_audit', args=[self.application.pk])
        )
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('D. Kelengkapan Dokumen Pendukung', content)
        self.assertIn('E. Rincian Kewenangan Diajukan (RKK)', content)
        self.assertIn('Legalitas &amp; Identitas', content)
        self.assertIn('Terpenuhi', content)
        self.assertIn('Kurang', content)

    def test_info_rows_never_print_as_unmet(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:kredensial_bukti_audit', args=[self.application.pk])
        )
        content = response.content.decode('utf-8')
        surat_start = content.index('Surat Permohonan')
        window = content[surat_start:surat_start + 400]
        self.assertIn('Informasi', window)
        self.assertNotIn('Kurang', window)


class DecisionSoftGateTests(SyaratBase):
    """C-6: the checklist advises at decision time; it never blocks."""

    def setUp(self):
        super().setUp()
        populate_requirements(self.application)
        evaluate_requirements(self.application)
        self._document(kind='CV', valid_until=self.today + timedelta(days=400))

    def test_missing_rows_without_flag_blocks_and_saves_nothing(self):
        from sdm.models import KeputusanKredensial
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('sdm:kredensial_decide', args=[self.application.pk]),
            {'outcome': 'DISETUJUI', 'notes': 'lengkap'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            KeputusanKredensial.objects.filter(pengajuan=self.application).exists()
        )
        content = response.content.decode('utf-8')
        self.assertIn('Belum lengkap', content)

    def test_missing_rows_with_flag_proceeds_and_records_them(self):
        from sdm.models import KeputusanKredensial
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('sdm:kredensial_decide', args=[self.application.pk]),
            {'outcome': 'DISETUJUI', 'notes': 'rapat menyetujui', 'abaikan_syarat': '1'},
        )
        self.assertEqual(response.status_code, 302)
        decision = KeputusanKredensial.objects.get(pengajuan=self.application)
        self.assertEqual(decision.outcome, 'DISETUJUI')
        self.assertIn('rapat menyetujui', decision.notes)
        self.assertIn('Syarat belum lengkap', decision.notes)

    def test_all_rows_satisfied_needs_no_flag(self):
        from sdm.models import KeputusanKredensial
        from sdm.services.syarat_kredensial import DEFAULT_ROWS
        # Satisfy every evidence row so the gate has nothing to block on.
        for spec in DEFAULT_ROWS:
            if spec['jenis'] == 'LOGBOOK_36BULAN':
                from sdm.models import EntriLogbookKlinis, KatalogTindakan
                from sdm.models import MasterJenjangProfesi, MasterProfesiPegawai
                profesi = MasterProfesiPegawai.objects.create(
                    code='P-GATE', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
                )
                jenjang = MasterJenjangProfesi.objects.create(
                    profesi=profesi, kode='PK-G', nama='Perawat I', urutan=1,
                )
                katalog = KatalogTindakan.objects.create(
                    kode='PR-GATE', nama='Tindakan', jenjang=jenjang,
                    tingkat_supervisi='M',
                )
                EntriLogbookKlinis.objects.create(
                    employee=self.employee, tanggal=self.today,
                    unit_kerja=self.unit, katalog_tindakan=katalog,
                    jumlah_mandiri=1,
                )
            elif spec['kind']:
                self._document(
                    kind=spec['kind'],
                    document_type='HEALTH' if spec['health'] else 'CREDENTIAL',
                    sensitivity='health' if spec['health'] else 'personnel',
                    valid_until=self.today + timedelta(days=400),
                )
        evaluate_requirements(self.application)
        self.assertEqual(self._missing(), [])

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('sdm:kredensial_decide', args=[self.application.pk]),
            {'outcome': 'DISETUJUI', 'notes': 'lengkap'},
        )
        self.assertEqual(response.status_code, 302)
        decision = KeputusanKredensial.objects.get(pengajuan=self.application)
        self.assertNotIn('Syarat belum lengkap', decision.notes)

    def _missing(self):
        from sdm.models import DokumenSyaratKredensial
        return [
            row.get_jenis_display()
            for row in DokumenSyaratKredensial.objects.filter(
                pengajuan=self.application
            )
            if row.status == 'KURANG'
        ]


class EmployeeRequirementStateTests(SyaratBase):
    """D-2: pre-submission checklist reads three evidence states."""

    def _states(self):
        from sdm.services.syarat_kredensial import evaluate_employee_requirements
        return {row['jenis']: row for row in evaluate_employee_requirements(self.employee)}

    def test_no_document_reads_belum(self):
        states = self._states()
        self.assertEqual(states['CV']['evidence_state'], 'BELUM')
        self.assertIsNone(states['CV']['document_version'])

    def test_valid_document_reads_aktif(self):
        version = self._document(
            kind='CV', valid_until=self.today + timedelta(days=400),
        )
        states = self._states()
        self.assertEqual(states['CV']['evidence_state'], 'AKTIF')
        self.assertEqual(states['CV']['document_version'].pk, version.pk)

    def test_expired_only_reads_kadaluarsa(self):
        self._document(
            kind='CV', valid_until=self.today - timedelta(days=1),
        )
        self.assertEqual(self._states()['CV']['evidence_state'], 'KADALUARSA')

    def test_undated_document_reads_aktif(self):
        self._document(kind='CV', valid_until=None)
        self.assertEqual(self._states()['CV']['evidence_state'], 'AKTIF')

    def test_evaluation_writes_nothing(self):
        from sdm.models.kredensial import DokumenSyaratKredensial
        before = DokumenSyaratKredensial.objects.count()
        self._states()
        self.assertEqual(DokumenSyaratKredensial.objects.count(), before)

    def test_rows_cover_every_evidence_kind_without_workflow(self):
        states = self._states()
        self.assertIn('SEHAT_PSIKOLOGIS', states)
        self.assertNotIn('SURAT_PERMOHONAN', states)

    def test_row_carries_domain_and_label(self):
        states = self._states()
        self.assertEqual(states['SEHAT_JASMANI']['domain'], 'SEHAT')
        self.assertTrue(states['SEHAT_JASMANI']['label'])
