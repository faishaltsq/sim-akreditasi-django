import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AturanDokumen,
    DokumenPegawai,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    VersiDokumen,
)
from sdm.services.kepatuhan import (
    evaluate_employee_compliance,
    expiry_bands,
)


class ComplianceServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Aturan', kategori='PPA', profesi='Perawat'
        )

    def _rule(self, *, name='STR', document_type='CREDENTIAL', policy='EXPIRY_REQUIRED',
              profesi='', kategori='', version=1, is_active=True):
        return AturanDokumen.objects.create(
            document_type=document_type,
            name=name,
            profesi=profesi,
            kategori=kategori,
            validity_policy=policy,
            version=version,
            is_active=is_active,
        )

    def _version(self, *, status='VERIFIED', valid_until=None, document_type='CREDENTIAL'):
        document = DokumenPegawai.objects.create(
            employee=self.employee,
            document_type=document_type,
            title='Dokumen uji',
            sensitivity='personnel',
        )
        return VersiDokumen.objects.create(
            document=document,
            version_number=1,
            original_filename='uji.pdf',
            storage_key=f'personnel/{self.employee.pk}/{document.pk}.pdf',
            sha256='a' * 64,
            size_bytes=10,
            content_type='application/pdf',
            status=status,
            valid_until=valid_until,
        )

    def test_missing_rule_without_version_is_missing(self):
        self._rule()

        summary = evaluate_employee_compliance(self.employee, as_of=self.today)

        self.assertEqual(summary.completeness_pct, 0.0)
        self.assertEqual(summary.results[0].state, 'MISSING')

    def test_verified_but_expired_document_is_not_compliant(self):
        self._rule()
        self._version(valid_until=self.today - timedelta(days=1))

        summary = evaluate_employee_compliance(self.employee, as_of=self.today)

        self.assertEqual(summary.results[0].state, 'EXPIRED')
        self.assertEqual(summary.completeness_pct, 0.0)

    def test_rejected_future_dated_document_is_rejected_not_valid(self):
        self._rule()
        self._version(status='REJECTED', valid_until=self.today + timedelta(days=365))

        summary = evaluate_employee_compliance(self.employee, as_of=self.today)

        self.assertEqual(summary.results[0].state, 'REJECTED')

    def test_due_today_belongs_to_the_thirty_day_band(self):
        self._rule()
        self._version(valid_until=self.today)

        summary = evaluate_employee_compliance(self.employee, as_of=self.today)

        self.assertEqual(summary.results[0].state, 'EXPIRING')

    def test_lifetime_document_never_expires_and_is_valid(self):
        self._rule(policy='LIFETIME')
        self._version(valid_until=None)

        summary = evaluate_employee_compliance(self.employee, as_of=self.today)

        self.assertEqual(summary.results[0].state, 'VALID')

    def test_expiry_required_without_date_stays_pending_review(self):
        self._rule(policy='EXPIRY_REQUIRED')
        self._version(valid_until=None)

        summary = evaluate_employee_compliance(self.employee, as_of=self.today)

        self.assertEqual(summary.results[0].state, 'PENDING')

    def test_profession_specific_rule_is_not_applicable_to_other_professions(self):
        self._rule(profesi='Dokter')
        summary = evaluate_employee_compliance(self.employee, as_of=self.today)

        self.assertEqual(summary.results[0].state, 'NOT_APPLICABLE')
        self.assertFalse(summary.has_data)
        self.assertIsNone(summary.completeness_pct)

    def test_duplicate_versions_do_not_inflate_the_denominator(self):
        self._rule()
        document = DokumenPegawai.objects.create(
            employee=self.employee,
            document_type='CREDENTIAL',
            title='Dokumen ganda',
            sensitivity='personnel',
        )
        for number in (1, 2):
            VersiDokumen.objects.create(
                document=document,
                version_number=number,
                original_filename='uji.pdf',
                storage_key=f'personnel/{self.employee.pk}/{number}.pdf',
                sha256='b' * 64,
                size_bytes=10,
                content_type='application/pdf',
                status='VERIFIED' if number == 2 else 'SUPERSEDED',
                valid_until=self.today + timedelta(days=200),
            )

        summary = evaluate_employee_compliance(self.employee, as_of=self.today)

        self.assertEqual(len(summary.applicable), 1)
        self.assertEqual(summary.completeness_pct, 100.0)

    def test_expiry_bands_are_disjoint_and_exclude_lifetime(self):
        self._rule(policy='LIFETIME')
        self._version(valid_until=None)
        self._version(valid_until=self.today + timedelta(days=10))
        self._version(valid_until=self.today + timedelta(days=45))
        self._version(valid_until=self.today + timedelta(days=75))
        self._version(valid_until=self.today - timedelta(days=2))

        bands = expiry_bands(as_of=self.today)

        self.assertEqual(len(bands['lt_30']), 1)
        self.assertEqual(len(bands['lt_60']), 1)
        self.assertEqual(len(bands['lt_90']), 1)
        self.assertEqual(len(bands['expired']), 1)


class EmployeeDocumentViewTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit E-File', code='HC-EFILE')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai E-File', kategori='NON_PPA'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=5),
            alokasi_fte=Decimal('1.00'),
        )
        self.user = get_user_model().objects.create_user(username='hc-efile-user')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_documents = True
        config.save(update_fields=['can_view_hc', 'can_manage_hc_documents', 'updated_at'])
        for capability in ('can_view_hc', 'can_manage_hc_documents'):
            HcGrant.objects.create(
                user=self.user, capability=capability, unit_kerja=self.unit
            )
        self.document = DokumenPegawai.objects.create(
            employee=self.employee,
            document_type='CREDENTIAL',
            title='STR E-File',
            sensitivity='personnel',
        )
        self.version = VersiDokumen.objects.create(
            document=self.document,
            version_number=1,
            original_filename='str.pdf',
            storage_key=f'personnel/{self.employee.pk}/{self.document.pk}.pdf',
            sha256='c' * 64,
            size_bytes=12,
            content_type='application/pdf',
            status='PENDING',
        )
        AturanDokumen.objects.create(
            document_type='CREDENTIAL',
            name='STR',
            validity_policy='EXPIRY_REQUIRED',
            version=1,
        )

    def test_detail_shows_compliance_panel_and_review_control(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sdm:pegawai_detail', kwargs={'employee_id': self.employee.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kelengkapan Dokumen Wajib')
        self.assertContains(response, 'Menunggu tinjauan')

    def test_health_documents_are_not_listed_in_the_general_profile(self):
        health = DokumenPegawai.objects.create(
            employee=self.employee,
            document_type='HEALTH',
            title='MCU Rahasia',
            sensitivity='health',
        )
        VersiDokumen.objects.create(
            document=health,
            version_number=1,
            original_filename='mcu.pdf',
            storage_key=f'health/{self.employee.pk}/{health.pk}.pdf',
            sha256='d' * 64,
            size_bytes=12,
            content_type='application/pdf',
            status='VERIFIED',
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sdm:pegawai_detail', kwargs={'employee_id': self.employee.pk})
        )

        self.assertNotContains(response, 'MCU Rahasia')
        self.assertNotContains(response, 'health/')

    def test_health_version_download_is_rejected_from_the_general_route(self):
        health = DokumenPegawai.objects.create(
            employee=self.employee,
            document_type='HEALTH',
            title='MCU Rahasia',
            sensitivity='health',
        )
        health_version = VersiDokumen.objects.create(
            document=health,
            version_number=1,
            original_filename='mcu.pdf',
            storage_key=f'health/{self.employee.pk}/{health.pk}.pdf',
            sha256='e' * 64,
            size_bytes=12,
            content_type='application/pdf',
            status='VERIFIED',
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('sdm:dokumen_download', kwargs={'version_id': health_version.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_review_requires_independent_reviewer_grant(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sdm:dokumen_review', kwargs={'version_id': self.version.pk}),
            {'status': 'VERIFIED', 'notes': 'ok'},
        )

        self.assertEqual(response.status_code, 403)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, 'PENDING')

    def test_verified_str_cannot_satisfy_sip_or_spk(self):
        sip_rule = AturanDokumen.objects.create(
            document_type='CREDENTIAL', jenis_berkas_wajib='SIP',
            name='SIP', validity_policy='EXPIRY_REQUIRED', version=1,
        )
        spk_rule = AturanDokumen.objects.create(
            document_type='CREDENTIAL', jenis_berkas_wajib='SPK_RKK',
            name='SPK RKK', validity_policy='EXPIRY_REQUIRED', version=1,
        )
        document = DokumenPegawai.objects.create(
            employee=self.employee,
            document_type='CREDENTIAL', jenis_berkas='STR',
            title='STR', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1,
            original_filename='str.pdf',
            storage_key=f'personnel/{self.employee.pk}/1-{uuid.uuid4().hex}.pdf',
            sha256='e' * 64, size_bytes=10,
            content_type='application/pdf', status='VERIFIED',
            valid_until=self.today + timedelta(days=200),
        )
        summary = evaluate_employee_compliance(
            self.employee, as_of=self.today,
            ruleset=[sip_rule, spk_rule],
        )
        self.assertEqual(len(summary.applicable), 2)
        self.assertTrue(all(r.state == 'MISSING' for r in summary.applicable))
        self.assertEqual(summary.completeness_pct, 0.0)

    def test_photo_cannot_satisfy_ktp(self):
        ktp_rule = AturanDokumen.objects.create(
            document_type='IDENTITY', jenis_berkas_wajib='KTP',
            name='KTP', validity_policy='EXPIRY_REQUIRED', version=1,
        )
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='IDENTITY', jenis_berkas='FOTO',
            title='Foto', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1,
            original_filename='foto.jpg',
            storage_key=f'personnel/{self.employee.pk}/1-{uuid.uuid4().hex}.jpg',
            sha256='f' * 64, size_bytes=10,
            content_type='image/jpeg', status='VERIFIED',
            valid_until=self.today + timedelta(days=200),
        )
        summary = evaluate_employee_compliance(
            self.employee, as_of=self.today, ruleset=[ktp_rule],
        )
        self.assertEqual(summary.results[0].state, 'MISSING')

    def test_diploma_cannot_satisfy_transcript(self):
        transcript_rule = AturanDokumen.objects.create(
            document_type='EDUCATION', jenis_berkas_wajib='TRANSKRIP',
            name='Transkrip', validity_policy='NOT_APPLICABLE', version=1,
        )
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='EDUCATION', jenis_berkas='IJAZAH',
            title='Ijazah', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1,
            original_filename='ijazah.pdf',
            storage_key=f'personnel/{self.employee.pk}/1-{uuid.uuid4().hex}.pdf',
            sha256='g' * 64, size_bytes=10,
            content_type='application/pdf', status='VERIFIED',
        )
        summary = evaluate_employee_compliance(
            self.employee, as_of=self.today, ruleset=[transcript_rule],
        )
        self.assertEqual(summary.results[0].state, 'MISSING')

    def test_external_clinic_sip_does_not_satisfy_local_rs_sip(self):
        local_sip_rule = AturanDokumen.objects.create(
            document_type='CREDENTIAL', jenis_berkas_wajib='SIP',
            name='SIP RS Lokal', validity_policy='EXPIRY_REQUIRED', version=1,
        )
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL', jenis_berkas='STR',
            title='SIP Klinik Luar', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1,
            original_filename='sip.pdf',
            storage_key=f'personnel/{self.employee.pk}/1-{uuid.uuid4().hex}.pdf',
            sha256='h' * 64, size_bytes=10,
            content_type='application/pdf', status='VERIFIED',
            valid_until=self.today + timedelta(days=200),
        )
        summary = evaluate_employee_compliance(
            self.employee, as_of=self.today, ruleset=[local_sip_rule],
        )
        self.assertEqual(summary.results[0].state, 'MISSING')

    def test_higher_version_on_another_document_does_not_win_arbitrarily(self):
        str_rule = AturanDokumen.objects.create(
            document_type='CREDENTIAL', jenis_berkas_wajib='STR',
            name='STR Tinggi Versi', validity_policy='EXPIRY_REQUIRED', version=1,
        )
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL', jenis_berkas='STR',
            title='STR', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1,
            original_filename='str-v1.pdf',
            storage_key=f'personnel/{self.employee.pk}/1-{uuid.uuid4().hex}.pdf',
            sha256='i' * 64, size_bytes=10,
            content_type='application/pdf', status='REJECTED',
            valid_until=self.today + timedelta(days=200),
        )
        summary = evaluate_employee_compliance(
            self.employee, as_of=self.today, ruleset=[str_rule],
        )
        self.assertEqual(summary.results[0].state, 'REJECTED')


class DocumentVocabularyTests(TestCase):
    """C-1: new supporting-data kinds and health-rule sensitivity resolution."""

    def setUp(self):
        self.today = timezone.localdate()
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Kosakata', kategori='PPA', profesi='Perawat'
        )

    def _version(self, *, document_type, jenis_berkas, sensitivity, status='VERIFIED',
                 valid_until=None):
        document = DokumenPegawai.objects.create(
            employee=self.employee,
            document_type=document_type,
            jenis_berkas=jenis_berkas,
            title=f'{jenis_berkas} uji',
            sensitivity=sensitivity,
        )
        return VersiDokumen.objects.create(
            document=document,
            version_number=1,
            original_filename='uji.pdf',
            storage_key=f'{sensitivity}/{self.employee.pk}/{document.pk}.pdf',
            sha256='b' * 64,
            size_bytes=10,
            content_type='application/pdf',
            status=status,
            valid_until=valid_until,
        )

    def test_new_credential_kinds_are_registered(self):
        kinds = dict(DokumenPegawai.DOCUMENT_KIND_CHOICES)
        for kind in [
            'CV', 'SERTIFIKAT_KOMPETENSI', 'LOGBOOK', 'TRAINING_RECORD', 'MCU',
            'PSIKOLOGIS', 'BEBAS_SANKSI', 'MALPRACTICE_RECORD', 'KEANGGOTAAN',
            'PENGANTAR_KSM', 'BERITA_ACARA_RAPAT', 'REKOMENDASI_KOMITE',
        ]:
            self.assertIn(kind, kinds)

    def test_professional_document_type_registered(self):
        types = dict(DokumenPegawai.DOCUMENT_TYPE_CHOICES)
        self.assertEqual(types.get('PROFESSIONAL'), 'Rekam Profesi')

    def test_mcu_health_document_passes_full_clean(self):
        document = DokumenPegawai(
            employee=self.employee, document_type='HEALTH', jenis_berkas='MCU',
            title='Hasil MCU', sensitivity='health',
        )
        document.full_clean()  # must not raise

    def test_psikologis_health_document_passes_full_clean(self):
        document = DokumenPegawai(
            employee=self.employee, document_type='HEALTH', jenis_berkas='PSIKOLOGIS',
            title='Asesmen Psikologis', sensitivity='health',
        )
        document.full_clean()  # must not raise

    def test_personnel_sensitivity_with_health_type_still_rejected(self):
        document = DokumenPegawai(
            employee=self.employee, document_type='HEALTH', jenis_berkas='MCU',
            title='MCU salah klasifikasi', sensitivity='personnel',
        )
        with self.assertRaises(ValidationError):
            document.full_clean()

    def test_health_rule_resolves_health_sensitivity_version(self):
        rule = AturanDokumen.objects.create(
            document_type='HEALTH', jenis_berkas_wajib='MCU',
            name='MCU Berkala', validity_policy='EXPIRY_REQUIRED', version=1,
        )
        version = self._version(
            document_type='HEALTH', jenis_berkas='MCU', sensitivity='health',
            valid_until=self.today + timedelta(days=200),
        )
        from sdm.services.kepatuhan import evaluate_employee_compliance
        summary = evaluate_employee_compliance(self.employee, as_of=self.today, ruleset=[rule])
        self.assertEqual(summary.results[0].state, 'VALID')
        self.assertEqual(summary.results[0].version.pk, version.pk)

    def test_personnel_rule_still_resolves_personnel_version(self):
        rule = AturanDokumen.objects.create(
            document_type='CREDENTIAL', jenis_berkas_wajib='STR',
            name='STR Berkala', validity_policy='EXPIRY_REQUIRED', version=1,
        )
        version = self._version(
            document_type='CREDENTIAL', jenis_berkas='STR', sensitivity='personnel',
            valid_until=self.today + timedelta(days=200),
        )
        from sdm.services.kepatuhan import evaluate_employee_compliance
        summary = evaluate_employee_compliance(self.employee, as_of=self.today, ruleset=[rule])
        self.assertEqual(summary.results[0].state, 'VALID')
        self.assertEqual(summary.results[0].version.pk, version.pk)


class DocumentUploadAuthorizationTests(TestCase):
    """A save must fail loudly in the form, never as a bare 403 mid-request."""

    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Unggah', code='DOC-UP')
        self.user = self._hc_user('upload-admin', can_health=False)
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Unggah', kategori='PPA', profesi='Perawat',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )

    def _hc_user(self, username, *, can_health):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_documents = True
        if can_health:
            config.hc_health_write = True
        config.save()
        HcGrant.objects.create(user=user, capability='can_view_hc', unit_kerja=self.unit)
        HcGrant.objects.create(
            user=user, capability='can_manage_hc_documents', unit_kerja=self.unit,
        )
        if can_health:
            HcGrant.objects.create(
                user=user, capability='hc_health_write', unit_kerja=self.unit,
            )
        return user

    def _post(self, *, sensitivity, document_type):
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile(
            'berkas.pdf', b'%PDF-1.4 data', content_type='application/pdf',
        )
        return self.client.post(
            reverse('sdm:dokumen_upload', args=[self.employee.pk]),
            {
                'file': upload, 'title': 'Uji', 'document_type': document_type,
                'sensitivity': sensitivity, 'jenis_berkas': 'STR',
            },
        )

    def test_health_document_without_health_capability_is_a_form_error(self):
        self.client.force_login(self.user)
        response = self._post(sensitivity='health', document_type='HEALTH')
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'kesehatan', response.content.decode('utf-8').lower()
        )
        self.assertFalse(
            DokumenPegawai.objects.filter(employee=self.employee).exists()
        )

    def test_health_document_with_health_capability_is_saved(self):
        grantor = self._hc_user('health-writer', can_health=True)
        self.client.force_login(grantor)
        response = self._post(sensitivity='health', document_type='HEALTH')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            DokumenPegawai.objects.filter(
                employee=self.employee, sensitivity='health'
            ).exists()
        )

    def test_personnel_document_still_saves(self):
        self.client.force_login(self.user)
        response = self._post(sensitivity='personnel', document_type='CREDENTIAL')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            DokumenPegawai.objects.filter(employee=self.employee).exists()
        )


class DocumentKindFieldTests(TestCase):
    """The upload form must record which kind of document it stored."""

    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Jenis', code='DOC-KIND')
        self.user = get_user_model().objects.create_user(username='kind-admin')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_documents = True
        config.save()
        HcGrant.objects.create(
            user=self.user, capability='can_view_hc', unit_kerja=self.unit,
        )
        HcGrant.objects.create(
            user=self.user, capability='can_manage_hc_documents', unit_kerja=self.unit,
        )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Jenis', kategori='PPA',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )

    def test_form_offers_a_kind_field(self):
        from sdm.forms import DokumenForm
        form = DokumenForm()
        self.assertIn('jenis_berkas', form.fields)

    def test_upload_records_the_chosen_kind(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile(
            'str.pdf', b'%PDF-1.4 x', content_type='application/pdf',
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('sdm:dokumen_upload', args=[self.employee.pk]),
            {
                'file': upload, 'title': 'STR Uji', 'document_type': 'CREDENTIAL',
                'sensitivity': 'personnel', 'jenis_berkas': 'STR',
            },
        )
        self.assertEqual(response.status_code, 302)
        document = DokumenPegawai.objects.get(employee=self.employee)
        self.assertEqual(document.jenis_berkas, 'STR')

    def test_kind_is_required(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile(
            'x.pdf', b'%PDF-1.4 x', content_type='application/pdf',
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('sdm:dokumen_upload', args=[self.employee.pk]),
            {
                'file': upload, 'title': 'Tanpa Jenis',
                'document_type': 'CREDENTIAL', 'sensitivity': 'personnel',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            DokumenPegawai.objects.filter(employee=self.employee).exists()
        )
