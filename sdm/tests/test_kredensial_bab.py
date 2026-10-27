"""BAB KREDENSIAL integration tests: seed, bestari panel, SPK issuance,
e-RKK printing, SPK EWS reminders, new routes, and landing cards."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    ClinicalActionCode,
    DokumenPegawai,
    HcGrant,
    KatalogTindakan,
    MasterJenjangProfesi,
    MasterProfesiPegawai,
    Pegawai,
    PenempatanPegawai,
    PengajuanKredensial,
    PengingatSDM,
    PenilaianTindakan,
    PenugasanKlinis,
    PeristiwaSDM,
    PrivilegeSnapshot,
    RincianKewenangan,
    VersiDokumen,
)
from sdm.models.pengingat import sync_all_reminders
from sdm.services.rekrutmen import decide_credential, terbitkan_spk_lengkap


class KredensialBABBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit BAB', code='HC-BAB')
        self.manager = self._user('cred-manager')

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_review_hc_credentials = True
        config.save(update_fields=['can_review_hc_credentials', 'updated_at'])
        HcGrant.objects.create(
            user=user, capability='can_review_hc_credentials', unit_kerja=self.unit,
        )
        return user

    def _placement(self, employee):
        PenempatanPegawai.objects.create(
            pegawai=employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )

    def _application(self, name='Perawat Katalog'):
        employee = Pegawai.objects.create(
            nama_lengkap=name, kategori='PPA', profesi='Perawat',
        )
        self._placement(employee)
        document = DokumenPegawai.objects.create(
            employee=employee, document_type='CREDENTIAL',
            title='STR', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='str.pdf',
            storage_key=f'personnel/{employee.pk}/{document.pk}.pdf',
            sha256='a' * 64, size_bytes=10, content_type='application/pdf',
            status='VERIFIED', valid_until=self.today + timedelta(days=365),
        )
        application = PengajuanKredensial.objects.create(
            employee=employee, unit_kerja=self.unit, submitted_by=self.manager,
        )
        return application


class SeedKatalogTests(TestCase):
    def test_seed_is_idempotent_across_two_runs(self):
        call_command('seed_katalog_rkk', '--apply', stdout=StringIO())
        first = (
            MasterProfesiPegawai.objects.count(),
            MasterJenjangProfesi.objects.count(),
            KatalogTindakan.objects.count(),
        )
        call_command('seed_katalog_rkk', '--apply', stdout=StringIO())
        second = (
            MasterProfesiPegawai.objects.count(),
            MasterJenjangProfesi.objects.count(),
            KatalogTindakan.objects.count(),
        )
        self.assertEqual(first, (23, 81, 273))
        self.assertEqual(first, second)
        self.assertEqual(
            KatalogTindakan.objects.filter(
                jenjang__profesi__code='KPR', jenjang__kode='PK-II'
            ).count(),
            5,
        )


class BestariPanelTests(KredensialBABBase):
    def setUp(self):
        super().setUp()
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Bestari', kategori='PPA', profesi='Perawat',
        )
        self._placement(self.employee)
        self.application = PengajuanKredensial.objects.create(
            employee=self.employee, unit_kerja=self.unit,
            submitted_by=self.manager,
        )
        self.rincian = RincianKewenangan.objects.create(
            pengajuan=self.application, kewenangan='Pemasangan infus',
            usulan='MANDIRI',
        )

    def test_posting_peer_review_marks_request_ditinjau(self):
        self.client.force_login(self.manager)
        url = reverse('sdm:kredensial_panel_bestari', args=[self.application.pk])
        response = self.client.post(url, {
            'penilaian_tindakan-TOTAL_FORMS': '1',
            'penilaian_tindakan-INITIAL_FORMS': '0',
            'penilaian_tindakan-MIN_NUM_FORMS': '0',
            'penilaian_tindakan-MAX_NUM_FORMS': '1000',
            'penilaian_tindakan-0-rincian': str(self.rincian.pk),
            'penilaian_tindakan-0-rekomendasi': 'MANDIRI',
            'penilaian_tindakan-0-catatan_khusus': 'Sudah cukup logbook',
        })

        self.assertRedirects(
            response, reverse('sdm:kredensial_detail', args=[self.application.pk])
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'DITINJAU')
        penilaian = PenilaianTindakan.objects.get(
            pengajuan=self.application, rincian=self.rincian,
        )
        self.assertEqual(penilaian.rekomendasi, 'MANDIRI')
        self.assertEqual(penilaian.reviewed_by, self.manager)
        self.assertTrue(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='peer_review_submitted',
                target_id=str(self.application.pk),
            ).exists()
        )


class TerbitkanSPKTests(KredensialBABBase):
    def setUp(self):
        super().setUp()
        self.application = self._application_with_lines()
        decide_credential(
            self.application, actor=self.manager, outcome='DISETUJUI',
        )

    def _application_with_lines(self):
        employee = Pegawai.objects.create(
            nama_lengkap='Perawat SPK', kategori='PPA', profesi='Perawat',
        )
        self._placement(employee)
        document = DokumenPegawai.objects.create(
            employee=employee, document_type='CREDENTIAL',
            title='STR', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='str.pdf',
            storage_key=f'personnel/{employee.pk}/{document.pk}.pdf',
            sha256='a' * 64, size_bytes=10, content_type='application/pdf',
            status='VERIFIED', valid_until=self.today + timedelta(days=365),
        )
        application = PengajuanKredensial.objects.create(
            employee=employee, unit_kerja=self.unit, submitted_by=self.manager,
        )
        # A granted line must carry a catalog item; EXT-* fallback is refused.
        self.catalog_infus = KatalogTindakan.objects.create(
            kode='K-TEST-INFUS', nama='Pemasangan infus', tingkat_supervisi='M',
            jenjang=self._jenjang('Perawat'),
        )
        self.catalog_respirasi = KatalogTindakan.objects.create(
            kode='K-TEST-RESP', nama='Terapi respirasi manual',
            tingkat_supervisi='S', jenjang=self._jenjang('Perawat'),
        )
        RincianKewenangan.objects.create(
            pengajuan=application, kewenangan='Pemasangan infus',
            catalog_item=self.catalog_infus,
            usulan='MANDIRI', rekomendasi='MANDIRI',
            status_spk='DISETUJUI_MANDIRI',
        )
        RincianKewenangan.objects.create(
            pengajuan=application, kewenangan='Terapi respirasi manual',
            catalog_item=self.catalog_respirasi,
            usulan='SUPERVISI', rekomendasi='DITOLAK',
            status_spk='TIDAK_DIBERIKAN',
        )
        return application

    def _jenjang(self, profesi_nama):
        profesi, _ = MasterProfesiPegawai.objects.get_or_create(
            code=f'TEST-{profesi_nama.upper()[:10]}',
            defaults={'nama': profesi_nama, 'keluarga': 'KEPERAWATAN_KEBIDANAN'},
        )
        jenjang, _ = MasterJenjangProfesi.objects.get_or_create(
            profesi=profesi, kode='PK-II',
            defaults={'nama': 'Perawat Klinis II', 'urutan': 2},
        )
        return jenjang

    def test_terbitkan_spk_route_creates_assignment_and_snapshots(self):
        self.client.force_login(self.manager)
        url = reverse('sdm:kredensial_terbitkan_spk', args=[self.application.pk])
        response = self.client.post(url, {
            'nomor_spk': 'SPK-BAB-001',
            'berlaku_mulai': self.today.isoformat(),
            'berlaku_sampai': (self.today + timedelta(days=365)).isoformat(),
        })

        self.assertRedirects(
            response, reverse('sdm:kredensial_detail', args=[self.application.pk])
        )
        assignment = PenugasanKlinis.objects.get(nomor_spk='SPK-BAB-001')
        self.assertEqual(assignment.decision.pengajuan, self.application)
        # Only the approved line gets a snapshot; TIDAK_DIBERIKAN does not.
        self.assertEqual(PrivilegeSnapshot.objects.count(), 1)
        snapshot = PrivilegeSnapshot.objects.get()
        self.assertEqual(snapshot.action_code.code, self.catalog_infus.kode)
        self.assertEqual(snapshot.valid_until, self.today + timedelta(days=365))

    def test_cetak_rkk_shows_tidak_diberikan_rows(self):
        terbitkan_spk_lengkap(
            self.application, actor=self.manager, nomor_spk='SPK-BAB-002',
            berlaku_mulai=self.today,
            berlaku_sampai=self.today + timedelta(days=365),
        )
        assignment = PenugasanKlinis.objects.get(nomor_spk='SPK-BAB-002')
        self.client.force_login(self.manager)
        url = reverse('sdm:kredensial_cetak_rkk', args=[assignment.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Tidak Diberikan', content)
        self.assertIn('Pemasangan infus', content)
        self.assertTrue(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='rkk_printed',
                target_id=str(assignment.pk),
            ).exists()
        )

    def test_cabut_spk_closes_privilege_snapshots(self):
        terbitkan_spk_lengkap(
            self.application, actor=self.manager, nomor_spk='SPK-BAB-003',
            berlaku_mulai=self.today,
        )
        assignment = PenugasanKlinis.objects.get(nomor_spk='SPK-BAB-003')
        self.client.force_login(self.manager)
        url = reverse('sdm:kredensial_cabut_spk', args=[assignment.pk])
        response = self.client.post(url, {'alasan': 'rotasi unit'})

        self.assertRedirects(
            response,
            reverse(
                'sdm:kredensial_detail',
                args=[assignment.decision.pengajuan_id],
            ),
        )
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)
        self.assertEqual(
            PrivilegeSnapshot.objects.filter(
                source_decision=assignment, valid_until=None,
            ).count(),
            0,
        )


class CatalogBindingTests(KredensialBABBase):
    """RKK lines must come from the employee's profession catalog."""

    def setUp(self):
        super().setUp()
        self.profesi = MasterProfesiPegawai.objects.create(
            code='UJI-KPR', nama='Perawat Uji', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        self.jenjang = MasterJenjangProfesi.objects.create(
            profesi=self.profesi, kode='PK-II', nama='Perawat Klinis II', urutan=2,
        )
        self.other_profesi = MasterProfesiPegawai.objects.create(
            code='UJI-RAD', nama='Radiografer Uji', keluarga='NAKES_LAIN',
        )
        self.other_jenjang = MasterJenjangProfesi.objects.create(
            profesi=self.other_profesi, kode='PRATAMA', nama='Pratama', urutan=1,
        )
        self.item_own = KatalogTindakan.objects.create(
            kode='K-UJI-001', nama='Pemasangan infus', tingkat_supervisi='M',
            jenjang=self.jenjang,
        )
        self.item_other = KatalogTindakan.objects.create(
            kode='K-UJI-002', nama='Foto toraks', tingkat_supervisi='S',
            jenjang=self.other_jenjang,
        )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Uji', kategori='PPA', profesi='Perawat Uji',
            profesi_master=self.profesi,
        )
        self._placement(self.employee)
        self.application = PengajuanKredensial.objects.create(
            employee=self.employee, unit_kerja=self.unit,
            submitted_by=self.manager,
        )

    def test_detail_page_lists_only_the_employee_profession_catalog(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:kredensial_detail', args=[self.application.pk])
        )

        self.assertEqual(response.status_code, 200)
        catalog = list(response.context['katalog'])
        self.assertEqual(catalog, [self.item_own])
        self.assertIn('Perawat Klinis II', response.context['jenjang_labels'])

    def test_adding_catalog_line_derives_level_from_catalog(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('sdm:kredensial_add_privilege', args=[self.application.pk]),
            {'catalog_item': str(self.item_own.pk)},
        )

        self.assertRedirects(
            response, reverse('sdm:kredensial_detail', args=[self.application.pk])
        )
        rincian = RincianKewenangan.objects.get(pengajuan=self.application)
        self.assertEqual(rincian.catalog_item, self.item_own)
        self.assertEqual(rincian.kewenangan, 'Pemasangan infus')
        self.assertEqual(rincian.usulan, 'MANDIRI')

    def test_adding_a_foreign_profession_item_is_rejected(self):
        self.client.force_login(self.manager)
        self.client.post(
            reverse('sdm:kredensial_add_privilege', args=[self.application.pk]),
            {'catalog_item': str(self.item_other.pk)},
        )

        self.assertFalse(
            RincianKewenangan.objects.filter(pengajuan=self.application).exists()
        )

    def test_manual_line_requires_a_name_or_an_unknown_item(self):
        self.client.force_login(self.manager)
        self.client.post(
            reverse('sdm:kredensial_add_privilege', args=[self.application.pk]),
            {'catalog_item': '', 'kewenangan': ''},
        )
        self.assertFalse(
            RincianKewenangan.objects.filter(pengajuan=self.application).exists()
        )

        self.client.post(
            reverse('sdm:kredensial_add_privilege', args=[self.application.pk]),
            {'catalog_item': '', 'kewenangan': 'Tindakan khusus unit'},
        )
        rincian = RincianKewenangan.objects.get(pengajuan=self.application)
        self.assertIsNone(rincian.catalog_item_id)

    def test_audit_sheet_names_catalog_code_and_jenjang(self):
        RincianKewenangan.objects.create(
            pengajuan=self.application, kewenangan=self.item_own.nama,
            catalog_item=self.item_own, usulan='MANDIRI',
            rekomendasi='MANDIRI', status_spk='DISETUJUI_MANDIRI',
        )
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:kredensial_bukti_audit', args=[self.application.pk])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn(self.item_own.kode, content)
        self.assertIn('Perawat Klinis II', content)
        self.assertIn('Perawat Uji', content)

    def test_mandiri_terbatas_line_issues_its_own_snapshot(self):
        item = KatalogTindakan.objects.create(
            kode='K-UJI-MT', nama='Menyiapkan sediaan steril', tingkat_supervisi='MT',
            jenjang=self.jenjang,
        )
        decide_credential(
            self.application, actor=self.manager, outcome='DISETUJUI',
        )
        rincian = RincianKewenangan.objects.create(
            pengajuan=self.application, kewenangan=item.nama, catalog_item=item,
            usulan='MANDIRI_TERBATAS', rekomendasi='MANDIRI_TERBATAS',
            status_spk='DISETUJUI_MANDIRI_TERBATAS',
        )

        terbitkan_spk_lengkap(
            self.application, actor=self.manager, nomor_spk='SPK-UJI-MT',
            berlaku_mulai=self.today,
        )

        snapshot = PrivilegeSnapshot.objects.get(action_code__code='K-UJI-MT')
        self.assertEqual(snapshot.action_code.code, item.kode)
        self.assertEqual(rincian.get_status_spk_display(), 'Disetujui Mandiri Terbatas')

    def test_issuance_refuses_a_granted_line_without_catalog_link(self):
        decide_credential(
            self.application, actor=self.manager, outcome='DISETUJUI',
        )
        RincianKewenangan.objects.create(
            pengajuan=self.application, kewenangan='Tindakan manual',
            usulan='MANDIRI', rekomendasi='MANDIRI',
            status_spk='DISETUJUI_MANDIRI',
        )

        with self.assertRaisesMessage(Exception, 'belum ditautkan ke katalog'):
            terbitkan_spk_lengkap(
                self.application, actor=self.manager, nomor_spk='SPK-UJI-001',
                berlaku_mulai=self.today,
            )
        self.assertFalse(PenugasanKlinis.objects.filter(nomor_spk='SPK-UJI-001').exists())
        self.assertFalse(ClinicalActionCode.objects.filter(code__startswith='EXT-').exists())


class SPKReminderTests(KredensialBABBase):
    def test_expiring_spk_creates_lt90_reminder(self):
        employee = Pegawai.objects.create(
            nama_lengkap='Perawat EWS', kategori='PPA', profesi='Perawat',
        )
        self._placement(employee)
        application = PengajuanKredensial.objects.create(
            employee=employee, unit_kerja=self.unit, submitted_by=self.manager,
        )
        decide_credential(
            application, actor=self.manager, outcome='DISETUJUI',
        )
        PenugasanKlinis.objects.create(
            employee=employee, unit_kerja=self.unit,
            decision=application.decision, nomor_spk='SPK-EWS-001',
            berlaku_mulai=self.today - timedelta(days=10),
            berlaku_sampai=self.today + timedelta(days=60),
            issued_by=self.manager,
        )

        created = sync_all_reminders()

        self.assertGreaterEqual(
            PengingatSDM.objects.filter(target_type='SPK').count(), 1
        )
        reminder = PengingatSDM.objects.filter(target_type='SPK').first()
        self.assertEqual(reminder.band, 'LT_90')
        self.assertEqual(reminder.target_type, 'SPK')


class NewRoutesTests(KredensialBABBase):
    ROUTES = (
        'sdm:kredensial_katalog',
        'sdm:kredensial_pengajuan_sendiri',
        'sdm:kredensial_daftar_pengajuan',
        'sdm:kredensial_spk_list',
        'sdm:kredensial_akses_rme',
        'sdm:kredensial_peta',
    )

    def test_all_new_routes_render_for_granted_user(self):
        employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Portal', kategori='PPA', profesi='Perawat',
        )
        self._placement(employee)
        employee.akun = self.manager
        employee.save(update_fields=['akun'])
        self.client.force_login(self.manager)
        for name in self.ROUTES:
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200, name)

    def test_new_routes_denied_without_grants(self):
        outsider = get_user_model().objects.create_user(username='outsider-bab')
        self.client.force_login(outsider)
        for name in self.ROUTES:
            response = self.client.get(reverse(name))
            if name == 'sdm:kredensial_pengajuan_sendiri':
                # C-5: the self-service portal is open to own-employee staff;
                # a user without a linked employee is redirected, not granted.
                self.assertEqual(response.status_code, 302, name)
                continue
            self.assertEqual(response.status_code, 403, name)


class LandingPageTests(KredensialBABBase):
    def test_landing_shows_six_submenu_cards(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('sdm:kredensial_list'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        for label in (
            'Master Katalog RKK', 'Pengajuan Mandiri',
            'Verifikasi &amp; Mitra Bestari',
            'E-SPK &amp; E-RKK', 'Kontrol Akses RME',
            'Peta &amp; Direktori Kewenangan',
        ):
            self.assertIn(label, content)


class BeritaAcaraRapatTests(KredensialBABBase):
    """C-4: committee minutes print-only artifact."""

    def setUp(self):
        super().setUp()
        self.application = self._application('Perawat Berita Acara')
        KatalogTindakan.objects.create(
            kode='K-BA-001', nama='Pemasangan infus',
            tingkat_supervisi='M',
            jenjang=MasterJenjangProfesi.objects.create(
                profesi=MasterProfesiPegawai.objects.create(
                    code='P-BA', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
                ),
                kode='PK-BA', nama='Perawat Klinis I', urutan=1,
            ),
        )
        RincianKewenangan.objects.create(
            pengajuan=self.application, kewenangan='Pemasangan infus',
            usulan='MANDIRI',
        )

    def test_unauthenticated_print_redirects_to_login(self):
        response = self.client.get(
            reverse('sdm:kredensial_berita_acara_rapat', args=[self.application.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_prints_employee_privileges_and_outcome(self):
        decide_credential(
            self.application, actor=self.manager, outcome='DISETUJUI', notes='ok',
        )
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:kredensial_berita_acara_rapat', args=[self.application.pk])
        )
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('BERITA ACARA RAPAT KREDENSIAL', content)
        self.assertIn('Perawat Berita Acara', content)
        self.assertIn('Pemasangan infus', content)
        self.assertIn('Disetujui', content)

    def test_print_writes_one_event(self):
        self.client.force_login(self.manager)
        before = PeristiwaSDM.objects.filter(
            jenis_peristiwa='berita_acara_rapat_printed'
        ).count()
        self.client.get(
            reverse('sdm:kredensial_berita_acara_rapat', args=[self.application.pk])
        )
        self.assertEqual(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='berita_acara_rapat_printed'
            ).count(),
            before + 1,
        )

    def test_wrong_unit_reviewer_gets_404(self):
        other_unit = UnitKerja.objects.create(name='Unit Asing BA', code='HC-BAO')
        outsider = get_user_model().objects.create_user(username='ba-outsider')
        UserProfile.objects.create(user=outsider, role='ADMIN_RS', unit_kerja=other_unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_review_hc_credentials = True
        config.save(update_fields=['can_view_hc', 'can_review_hc_credentials', 'updated_at'])
        HcGrant.objects.create(
            user=outsider, capability='can_view_hc', unit_kerja=other_unit,
        )
        HcGrant.objects.create(
            user=outsider, capability='can_review_hc_credentials', unit_kerja=other_unit,
        )
        self.client.force_login(outsider)
        response = self.client.get(
            reverse('sdm:kredensial_berita_acara_rapat', args=[self.application.pk])
        )
        self.assertEqual(response.status_code, 404)
