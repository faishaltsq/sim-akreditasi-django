"""Tests for the Aktivitas (audit trail) module (Task 4).

PeristiwaSDM is immutable: the only permitted rewrite is backfill_kategori(),
which fills metadata rather than changing semantics.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
)
from sdm.services.aktivitas import (
    activity_metrics,
    activity_rows,
    kategori_for,
)


class KategoriMappingTests(TestCase):
    def test_known_prefixes_map_to_their_category(self):
        self.assertEqual(kategori_for('employee_updated'), 'UPDATE_PROFILE')
        self.assertEqual(kategori_for('riwayat_kepegawaian_created'), 'UPDATE_PROFILE')
        self.assertEqual(kategori_for('private_document_uploaded'), 'UPLOAD_DOC')
        self.assertEqual(kategori_for('psv_verified'), 'UPLOAD_DOC')
        self.assertEqual(kategori_for('logbook_entry_verified'), 'VERIFIKASI')
        self.assertEqual(kategori_for('credential_reviewed'), 'VERIFIKASI')
        self.assertEqual(kategori_for('recruitment_stage_moved'), 'VERIFIKASI')
        self.assertEqual(kategori_for('training_completed'), 'SYSTEM')
        self.assertEqual(kategori_for('formasi_submitted'), 'SYSTEM')

    def test_unknown_values_fall_back_to_system(self):
        self.assertEqual(kategori_for('something_unmapped'), 'SYSTEM')
        self.assertEqual(kategori_for(''), 'SYSTEM')
        self.assertEqual(kategori_for(None), 'SYSTEM')


class AktivitasServiceTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Aktivitas', code='HC-AKT')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Aktivitas', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=timezone.localdate() - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        self.actor = get_user_model().objects.create_user('pelaku-aktivitas')
        PeristiwaSDM.objects.create(
            actor=self.actor,
            jenis_peristiwa='employee_updated',
            kategori='UPDATE_PROFILE',
            judul='Alamat diperbarui',
            target_tipe='employee',
            target_id=str(self.employee.pk),
        )
        PeristiwaSDM.objects.create(
            actor=self.actor,
            jenis_peristiwa='private_document_uploaded',
            kategori='UPLOAD_DOC',
            judul='Ijazah diunggah',
            target_tipe='employee',
            target_id=str(self.employee.pk),
        )
        PeristiwaSDM.objects.create(
            actor=self.actor,
            jenis_peristiwa='health_check_recorded',
            kategori='SYSTEM',
            judul='Pemeriksaan kesehatan kerja',
            target_tipe='employee',
            target_id=str(self.employee.pk),
        )

    def test_rows_filter_by_kategori(self):
        rows = list(
            activity_rows(self.actor, employee=self.employee, kategori='UPDATE_PROFILE')
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].judul, 'Alamat diperbarui')

    def test_rows_search_matches_judul_and_actor(self):
        rows = list(
            activity_rows(self.actor, employee=self.employee, q='Ijazah')
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].judul, 'Ijazah diunggah')
        # The health row is excluded by design, so an actor-wide search that
        # would otherwise match all three rows returns two.
        rows = list(
            activity_rows(self.actor, employee=self.employee, q='pelaku-aktivitas')
        )
        self.assertEqual(len(rows), 2)

    def test_rows_exclude_health_events(self):
        rows = list(activity_rows(self.actor, employee=self.employee))
        self.assertEqual(len(rows), 2)
        self.assertFalse(
            any('health' in row.jenis_peristiwa for row in rows)
        )

    def test_metrics_count_total_and_categories(self):
        rows = activity_rows(self.actor, employee=self.employee)
        metrics = activity_metrics(rows)
        self.assertEqual(metrics['total'], 2)
        self.assertEqual(metrics['perubahan_data'], 1)
        self.assertEqual(metrics['unggah_berkas'], 1)
        self.assertEqual(metrics['verifikasi'], 0)
        self.assertIsNone(metrics['sesi_terakhir'])


class PeristiwaImmutabilityTests(TestCase):
    def setUp(self):
        self.row = PeristiwaSDM.objects.create(
            jenis_peristiwa='employee_updated',
            kategori='UPDATE_PROFILE',
            target_tipe='employee',
            target_id='00000000-0000-0000-0000-000000000001',
        )

    def test_saving_an_existing_row_is_refused(self):
        self.row.judul = 'Diubah'
        with self.assertRaises(ValidationError):
            self.row.save()

    def test_backfill_kategori_is_the_only_permitted_rewrite(self):
        legacy = PeristiwaSDM.objects.create(
            jenis_peristiwa='employee_updated',
            kategori='',
            target_tipe='employee',
            target_id='00000000-0000-0000-0000-000000000002',
        )
        legacy.backfill_kategori()
        legacy.refresh_from_db()
        self.assertEqual(legacy.kategori, 'UPDATE_PROFILE')

    def test_queryset_update_is_refused(self):
        with self.assertRaises(ValidationError):
            PeristiwaSDM.objects.filter(pk=self.row.pk).update(judul='x')


class AktivitasViewTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Tampilan', code='HC-ATV')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Tampilan', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=timezone.localdate() - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        self.manager = self._make_user(
            'manajer-aktivitas',
            ['can_view_hc', 'can_manage_hc_employees'],
        )
        self.viewer = self._make_user('peninjau-aktivitas', ['can_view_hc'])
        self.client.force_login(self.manager)

    def _make_user(self, username, caps):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(
            user=user, role='ADMIN_RS', unit_kerja=self.unit
        )
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        for cap in caps:
            setattr(config, cap, True)
        config.save(update_fields=list(caps) + ['updated_at'])
        for cap in caps:
            HcGrant.objects.create(
                user=user, capability=cap, unit_kerja=self.unit, granted_by=user
            )
        return user

    def test_manual_entry_creates_audit_row(self):
        response = self.client.post(
            reverse('sdm:aktivitas_manual', args=[self.employee.pk]),
            {
                'kategori': 'UPDATE_PROFILE',
                'judul': 'Koreksi nomor telepon',
                'deskripsi': 'Nomor telepon diperbaiki sesuai berkas.',
                'status': 'SUCCESS',
                'modul': 'Human Capital',
            },
        )
        self.assertEqual(response.status_code, 302)
        row = PeristiwaSDM.objects.get(judul='Koreksi nomor telepon')
        self.assertEqual(row.kategori, 'UPDATE_PROFILE')
        self.assertEqual(row.target_id, str(self.employee.pk))
        self.assertTrue(row.ip_address)
        self.assertEqual(row.actor, self.manager)

    def test_activity_page_lists_rows_and_metrics(self):
        PeristiwaSDM.objects.create(
            actor=self.manager,
            jenis_peristiwa='employee_updated',
            kategori='UPDATE_PROFILE',
            judul='Alamat diperbarui',
            target_tipe='employee',
            target_id=str(self.employee.pk),
        )
        response = self.client.get(
            reverse('sdm:pegawai_aktivitas', args=[self.employee.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['metrics']['total'], 1)
        self.assertEqual(len(response.context['rows']), 1)

    def test_viewer_without_capability_is_denied(self):
        """A user whose HC grant covers a different unit never sees this
        employee: visible_employees filters them out, so the lookup 404s
        before any capability check runs."""
        other_unit = UnitKerja.objects.create(
            name='Unit Lain', code='HC-OTR'
        )
        outsider = get_user_model().objects.create_user('akun-luar')
        UserProfile.objects.create(
            user=outsider, role='ADMIN_RS', unit_kerja=other_unit
        )
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=outsider, capability='can_view_hc',
            unit_kerja=other_unit, granted_by=outsider,
        )
        self.client.force_login(outsider)
        response = self.client.get(
            reverse('sdm:pegawai_aktivitas', args=[self.employee.pk])
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            reverse('sdm:aktivitas_manual', args=[self.employee.pk]),
            {
                'kategori': 'UPDATE_PROFILE',
                'judul': 'Coba',
                'deskripsi': 'Tanpa izin.',
                'status': 'SUCCESS',
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            PeristiwaSDM.objects.filter(judul='Coba').exists()
        )

    def test_viewer_with_read_capability_can_see_the_page(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse('sdm:pegawai_aktivitas', args=[self.employee.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_manage'])

    def test_viewer_cannot_record_manual_activity(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse('sdm:aktivitas_manual', args=[self.employee.pk]),
            {
                'kategori': 'UPDATE_PROFILE',
                'judul': 'Coba',
                'deskripsi': 'Tanpa izin.',
                'status': 'SUCCESS',
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            PeristiwaSDM.objects.filter(judul='Coba').exists()
        )

    def test_export_returns_csv_with_bom_and_header(self):
        PeristiwaSDM.objects.create(
            actor=self.manager,
            jenis_peristiwa='employee_updated',
            kategori='UPDATE_PROFILE',
            judul='Alamat diperbarui',
            target_tipe='employee',
            target_id=str(self.employee.pk),
        )
        response = self.client.get(
            reverse('sdm:pegawai_aktivitas_export', args=[self.employee.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        body = response.content.decode('utf-8')
        self.assertTrue(body.startswith('\ufeff'))
        self.assertIn('Kategori', body)
        self.assertIn('Alamat diperbarui', body)


class LoginSignalTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Login', code='HC-LGN')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Login', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=timezone.localdate() - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        self.employee.akun = get_user_model().objects.create_user('akun-pegawai')
        self.employee.save(update_fields=['akun'])

    def test_login_creates_row_for_employee_account(self):
        user_logged_in.send(
            sender=self.employee.akun.__class__,
            request=None,
            user=self.employee.akun,
        )
        row = PeristiwaSDM.objects.get(jenis_peristiwa='login')
        self.assertEqual(row.kategori, 'LOGIN')
        self.assertEqual(row.target_id, str(self.employee.pk))

    def test_login_without_employee_creates_nothing(self):
        plain = get_user_model().objects.create_user('akun-biasa')
        user_logged_in.send(
            sender=plain.__class__, request=None, user=plain
        )
        self.assertFalse(
            PeristiwaSDM.objects.filter(jenis_peristiwa='login').exists()
        )
