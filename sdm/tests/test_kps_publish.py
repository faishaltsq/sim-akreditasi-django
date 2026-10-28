from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import Category, EvidenceFile, EvidenceReq, Framework, StandardItem
from akreditasi.models import UnitKerja
from sdm.models import (
    AturanDokumen,
    HcGrant,
    Pegawai,
    PemetaanStandarSDM,
    PeristiwaSDM,
)
from sdm.services.publikasi_bukti import build_kps_pack, publish_kps_artifact


class KpsPublishTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='kps-admin')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_export_hc = True
        config.can_verify_kps = True
        config.save(update_fields=['can_export_hc', 'can_verify_kps', 'updated_at'])
        self.unit = UnitKerja.objects.create(name='Unit KPS', code='KPS-UNIT')
        HcGrant.objects.create(
            user=self.user, capability='can_export_hc', unit_kerja=self.unit
        )
        self.framework = Framework.objects.create(
            name='STARKES 2024', version='2024', edition='2024', is_active=True
        )
        self.category = Category.objects.create(
            framework=self.framework, code='KPS', name='Kualifikasi & Pendidikan Staf'
        )
        self.item = StandardItem.objects.create(
            category=self.category, sub_standard='KPS 1', code='KPS 1 EP a'
        )
        self.requirement = EvidenceReq.objects.create(
            standard_item=self.item, category_type='D',
            title='Daftar riwayat kepegawaian', is_mandatory=True,
        )
        self.rule = AturanDokumen.objects.create(
            document_type='CREDENTIAL', name='STR', validity_policy='EXPIRY_REQUIRED'
        )
        PemetaanStandarSDM.objects.create(
            rule=self.rule, standard_item=self.item, framework=self.framework,
            reviewer_name='Ketua Pokja KPS',
        )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Ahmad', kategori='PPA', profesi='Perawat'
        )

    def _pack(self):
        return build_kps_pack(
            actor=self.user, employee_ids=[self.employee.pk],
            framework_id=self.framework.pk
        )

    def test_pack_contains_real_workbook_bytes(self):
        artifact = self._pack()
        self.assertGreater(len(artifact['workbook_bytes']), 0)
        self.assertTrue(artifact['workbook_hash'])

    def test_publish_creates_review_evidence_with_real_file(self):
        artifact = self._pack()
        evidence = publish_kps_artifact(
            actor=self.user, artifact=artifact, requirement_id=self.requirement.pk
        )
        self.assertEqual(evidence.status, 'REVIEW')
        self.assertEqual(evidence.requirement_id, self.requirement.pk)
        self.assertIn('pack-kps', evidence.file_name)
        self.assertTrue(evidence.file)
        self.assertEqual(evidence.file.size, len(artifact['workbook_bytes']))

    def test_publish_records_audit_event(self):
        artifact = self._pack()
        publish_kps_artifact(
            actor=self.user, artifact=artifact, requirement_id=self.requirement.pk
        )
        event = PeristiwaSDM.objects.get(jenis_peristiwa='kps_artifact_published')
        self.assertEqual(event.target_tipe, 'requirement')
        self.assertEqual(event.target_id, str(self.requirement.pk))

    def test_publish_requires_both_permissions(self):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_verify_kps = False
        config.save(update_fields=['can_verify_kps', 'updated_at'])
        artifact = self._pack()
        with self.assertRaises(PermissionDenied):
            publish_kps_artifact(
                actor=self.user, artifact=artifact, requirement_id=self.requirement.pk
            )
        self.assertFalse(EvidenceFile.objects.exists())

    def test_export_grant_alone_does_not_authorize_publication(self):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_export_hc = True
        config.can_verify_kps = False
        config.save(update_fields=['can_export_hc', 'can_verify_kps', 'updated_at'])
        artifact = self._pack()
        with self.assertRaises(PermissionDenied):
            publish_kps_artifact(
                actor=self.user, artifact=artifact, requirement_id=self.requirement.pk
            )
        self.assertFalse(EvidenceFile.objects.exists())

    def test_publish_rejects_unknown_requirement(self):
        artifact = self._pack()
        with self.assertRaises(ValidationError):
            publish_kps_artifact(
                actor=self.user, artifact=artifact, requirement_id=999999
            )

    def test_publish_rejects_empty_workbook(self):
        artifact = self._pack()
        artifact['workbook_bytes'] = b''
        with self.assertRaises(ValidationError):
            publish_kps_artifact(
                actor=self.user, artifact=artifact, requirement_id=self.requirement.pk
            )
        self.assertFalse(EvidenceFile.objects.exists())

    def test_preview_view_lists_mapped_requirements(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['kps_pack_artifact'] = {
            'generated_at': '2026-10-28T00:00:00+07:00',
            'framework_id': self.framework.pk,
            'framework_name': self.framework.name,
            'as_of': '2026-10-28',
            'actor_id': self.user.pk,
            'employee_count': 1,
            'workbook_hash': 'a' * 64,
        }
        session.save()
        response = self.client.get('/human-capital/laporan/kps/paket/preview/')
        self.assertEqual(response.status_code, 200)
        options = list(response.context['requirement_options'])
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].pk, self.requirement.pk)
