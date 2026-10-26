"""D-3: additive staged workflow for credential requests."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai, PenempatanPegawai, PengajuanKredensial, PeristiwaSDM
from sdm.models.kredensial import TahapKredensial
from sdm.services.workflow_kredensial import advance_stage, current_stage


class StageBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Tahap D3', code='HC-D3')
        self.sdm = self._user('d3-sdm', 'can_manage_hc_documents')
        self.subkomite = self._user('d3-sub', 'hc_review_subkomite')
        self.ketua = self._user('d3-ketua', 'hc_recommend_komite')
        self.direktur = self._user('d3-dir', 'hc_approve_credentials')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Tahap', kategori='PPA', profesi='Perawat',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )
        self.application = PengajuanKredensial.objects.create(
            employee=self.employee, unit_kerja=self.unit, submitted_by=self.sdm,
        )

    def _user(self, username, capability):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        setattr(config, capability, True)
        config.save(update_fields=[capability, 'updated_at'])
        HcGrant.objects.create(
            user=user, capability=capability, unit_kerja=self.unit,
        )
        return user


class StageModelTests(StageBase):
    def test_new_status_values_are_additive(self):
        values = dict(PengajuanKredensial.STATUS_CHOICES)
        for legacy in ('DIAJUKAN', 'DITINJAU', 'DIREKOMENDASI',
                       'DISETUJUI', 'DITOLAK', 'DICABUT'):
            self.assertIn(legacy, values)
        for staged in ('DRAFT', 'VERIFIKASI_SDM', 'REVIEW_SUBKOMITE',
                       'REKOMENDASI_KETUA_KOMITE', 'BERKAS_LENGKAP',
                       'DIAJUKAN_DIREKTUR'):
            self.assertIn(staged, values)

    def test_stage_rows_are_append_only(self):
        advance_stage(self.application, actor=self.sdm, tahap='VERIFIKASI_SDM')
        row = TahapKredensial.objects.get()
        with self.assertRaises(ValidationError):
            row.delete()

    def test_each_transition_writes_one_audit_event(self):
        before = PeristiwaSDM.objects.filter(
            jenis_peristiwa='credential_stage_advanced'
        ).count()
        advance_stage(self.application, actor=self.sdm, tahap='VERIFIKASI_SDM')
        self.assertEqual(
            PeristiwaSDM.objects.filter(
                jenis_peristiwa='credential_stage_advanced'
            ).count(),
            before + 1,
        )


class StageTransitionTests(StageBase):
    def test_sdm_cannot_skip_to_subkomite(self):
        with self.assertRaises(PermissionDenied):
            advance_stage(self.application, actor=self.sdm, tahap='REVIEW_SUBKOMITE')

    def test_forward_chain_is_legal(self):
        advance_stage(self.application, actor=self.sdm, tahap='VERIFIKASI_SDM')
        advance_stage(self.application, actor=self.subkomite, tahap='REVIEW_SUBKOMITE')
        advance_stage(
            self.application, actor=self.ketua, tahap='REKOMENDASI_KETUA_KOMITE',
        )
        self.assertEqual(current_stage(self.application), 'REKOMENDASI_KETUA_KOMITE')

    def test_out_of_order_backwards_is_rejected(self):
        advance_stage(self.application, actor=self.sdm, tahap='VERIFIKASI_SDM')
        advance_stage(self.application, actor=self.subkomite, tahap='REVIEW_SUBKOMITE')
        with self.assertRaises(ValidationError):
            advance_stage(self.application, actor=self.sdm, tahap='VERIFIKASI_SDM')

    def test_kekurangan_is_recorded_and_returned(self):
        advance_stage(
            self.application, actor=self.sdm, tahap='VERIFIKASI_SDM',
            kekurangan='STR kedaluwarsa',
        )
        self.assertIn('STR kedaluwarsa', current_stage_row(self.application).kekurangan)

    def test_current_stage_is_none_before_any_transition(self):
        self.assertIsNone(current_stage(self.application))

    def test_wrong_unit_actor_is_denied(self):
        other_unit = UnitKerja.objects.create(name='Unit Lain D3', code='HC-D3B')
        outsider = get_user_model().objects.create_user(username='d3-outsider')
        UserProfile.objects.create(user=outsider, role='ADMIN_RS', unit_kerja=other_unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_manage_hc_documents = True
        config.save(update_fields=['can_manage_hc_documents', 'updated_at'])
        HcGrant.objects.create(
            user=outsider, capability='can_manage_hc_documents', unit_kerja=other_unit,
        )
        with self.assertRaises(PermissionDenied):
            advance_stage(self.application, actor=outsider, tahap='VERIFIKASI_SDM')


class StageViewTests(StageBase):
    def test_detail_page_shows_stepper(self):
        advance_stage(self.application, actor=self.sdm, tahap='VERIFIKASI_SDM')
        # Reviewer capability needed only to render the detail page.
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_review_hc_credentials = True
        config.can_view_hc = True
        config.save(update_fields=[
            'can_review_hc_credentials', 'can_view_hc', 'updated_at',
        ])
        for user in (self.sdm,):
            HcGrant.objects.create(
                user=user, capability='can_view_hc', unit_kerja=self.unit,
            )
            HcGrant.objects.create(
                user=user, capability='can_review_hc_credentials',
                unit_kerja=self.unit,
            )
        self.client.force_login(self.sdm)
        response = self.client.get(
            reverse('sdm:kredensial_detail', args=[self.application.pk])
        )
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Tahap Kredensial', content)
        self.assertIn('Verifikasi SDM', content)

    def test_stage_action_route_advances(self):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_review_hc_credentials = True
        config.save(update_fields=[
            'can_view_hc', 'can_review_hc_credentials', 'updated_at',
        ])
        HcGrant.objects.create(
            user=self.sdm, capability='can_view_hc', unit_kerja=self.unit,
        )
        HcGrant.objects.create(
            user=self.sdm, capability='can_review_hc_credentials',
            unit_kerja=self.unit,
        )
        self.client.force_login(self.sdm)
        response = self.client.post(
            reverse('sdm:kredensial_tahap', args=[self.application.pk]),
            {'tahap': 'VERIFIKASI_SDM', 'kekurangan': 'MCU belum ada'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(current_stage(self.application), 'VERIFIKASI_SDM')


def current_stage_row(application):
    from sdm.models.kredensial import TahapKredensial
    return TahapKredensial.objects.filter(pengajuan=application).order_by(
        '-created_at', '-pk'
    ).first()
