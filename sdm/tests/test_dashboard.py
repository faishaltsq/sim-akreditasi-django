from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import resolve
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    AktivitasBebanKerja,
    AturanDokumen,
    DokumenPegawai,
    HcGrant,
    Pegawai,
    PengingatSDM,
    PenempatanPegawai,
    RencanaFormasi,
    VersiDokumen,
)
from sdm.models.pengingat import sync_expiry_reminders
from sdm.services.dashboard import build_hc_dashboard


class HumanCapitalDashboardTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Dasbor HC', code='HC-DASH')
        self.other = UnitKerja.objects.create(name='Unit Rahasia HC', code='HC-DASH-2')
        self.user = self._user('hc-dash-user', role='ADMIN_RS')
        self._grant(self.user, 'can_view_hc')
        self._grant(self.user, 'can_plan_hc_workforce')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Dasbor', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )

    def _user(self, username, *, role='ADMIN_RS'):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role=role, unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role(role)
        config.can_view_hc = True
        config.can_plan_hc_workforce = True
        config.save(update_fields=['can_view_hc', 'can_plan_hc_workforce', 'updated_at'])
        return user

    def _grant(self, user, capability, unit=None):
        return HcGrant.objects.create(
            user=user, capability=capability, unit_kerja=unit or self.unit
        )

    def test_dashboard_route_is_registered_with_exact_title(self):
        self.assertEqual(resolve('/human-capital/').view_name, 'sdm:dashboard')
        self.client.force_login(self.user)

        response = self.client.get('/human-capital/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Arima Human Capital')

    def test_dashboard_shows_unavailable_state_when_no_rules_exist(self):
        self.client.force_login(self.user)

        response = self.client.get('/human-capital/')

        self.assertContains(response, 'Belum dapat dihitung')

    def test_dashboard_reports_zero_only_with_a_real_denominator(self):
        AturanDokumen.objects.create(
            document_type='CREDENTIAL', name='STR', validity_policy='EXPIRY_REQUIRED'
        )
        self.client.force_login(self.user)

        response = self.client.get('/human-capital/')

        metrics = build_hc_dashboard(self.user, filters={})
        self.assertEqual(metrics['compliance_scope_count'], 1)
        self.assertEqual(metrics['compliance_pct'], 0.0)

    def test_dashboard_hides_employees_from_foreign_units(self):
        hidden = Pegawai.objects.create(
            nama_lengkap='Pegawai Rahasia', kategori='NON_PPA'
        )
        PenempatanPegawai.objects.create(
            pegawai=hidden, unit_kerja=self.other,
            tanggal_mulai=self.today - timedelta(days=5),
            alokasi_fte=Decimal('1.00'),
        )

        metrics = build_hc_dashboard(self.user, filters={})

        self.assertEqual(metrics['total_employees'], 1)

    def test_dashboard_never_exposes_health_documents(self):
        health = DokumenPegawai.objects.create(
            employee=self.employee, document_type='HEALTH',
            title='MCU Rahasia', sensitivity='health',
        )
        VersiDokumen.objects.create(
            document=health, version_number=1, original_filename='mcu.pdf',
            storage_key=f'health/{self.employee.pk}/{health.pk}.pdf',
            sha256='f' * 64, size_bytes=10, content_type='application/pdf',
            status='PENDING',
        )
        self.client.force_login(self.user)

        response = self.client.get('/human-capital/')

        self.assertNotContains(response, 'MCU Rahasia')
        self.assertEqual(response.context['pending_reviews'], 0)

    def test_user_without_grant_is_denied(self):
        outsider = get_user_model().objects.create_user(username='no-hc-grant')
        UserProfile.objects.create(user=outsider, role='ADMIN_RS')
        self.client.force_login(outsider)

        response = self.client.get('/human-capital/')

        self.assertEqual(response.status_code, 403)

    def test_approved_plan_appears_in_staffing_table(self):
        plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit, profesi='Perawat',
            periode_mulai=self.today, periode_selesai=self.today + timedelta(days=30),
            effective_minutes_per_employee=Decimal('1000.00'),
        )
        AktivitasBebanKerja.objects.create(
            rencana=plan, nama='Asuhan', volume=Decimal('100.00'),
            standard_minutes=Decimal('10.00'),
        )
        plan.status = 'APPROVED'
        plan.save(update_fields=['status'])
        from sdm.models import HasilFormasi

        HasilFormasi.objects.create(
            rencana=plan, calculation_version='activity-fte-v1',
            required_fte=Decimal('1.00'), required_headcount=1,
            actual_fte=Decimal('1.00'), gap_fte=Decimal('0.00'),
            sufficiency_pct=Decimal('100.00'), inputs_digest='a' * 64,
        )

        metrics = build_hc_dashboard(self.user, filters={})

        self.assertTrue(metrics['has_staffing'])
        self.assertEqual(metrics['staffing'][0]['sufficiency_pct'], Decimal('100.00'))


class ReminderTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Pengingat', code='HC-REM')
        self.owner = get_user_model().objects.create_user(username='reminder-owner')
        UserProfile.objects.create(user=self.owner, role='STAF_NAKES', unit_kerja=self.unit)
        self.employee = Pegawai.objects.create(
            akun=self.owner, nama_lengkap='Pemilik Pengingat', kategori='PPA'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )

    def _version(self, days):
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL',
            title='STR', sensitivity='personnel',
        )
        return VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='str.pdf',
            storage_key=f'personnel/{self.employee.pk}/{document.pk}.pdf',
            sha256='b' * 64, size_bytes=10, content_type='application/pdf',
            status='VERIFIED', valid_until=self.today + timedelta(days=days),
        )

    def test_repeated_runs_do_not_duplicate_reminders(self):
        self._version(10)

        first = sync_expiry_reminders(as_of=self.today)
        second = sync_expiry_reminders(as_of=self.today)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(PengingatSDM.objects.count(), 1)

    def test_bands_are_disjoint_and_expired_is_separate(self):
        self._version(10)
        self._version(45)
        self._version(75)
        self._version(-3)

        sync_expiry_reminders(as_of=self.today)

        self.assertEqual(
            set(PengingatSDM.objects.values_list('band', flat=True)),
            {'LT_30', 'LT_60', 'LT_90', 'EXPIRED'},
        )

    def test_lifetime_documents_never_produce_reminders(self):
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='EDUCATION',
            title='Ijazah', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='ijazah.pdf',
            storage_key=f'personnel/{self.employee.pk}/{document.pk}.pdf',
            sha256='c' * 64, size_bytes=10, content_type='application/pdf',
            status='VERIFIED', valid_until=None,
        )

        created = sync_expiry_reminders(as_of=self.today)

        self.assertEqual(created, 0)

    def test_command_reports_created_count(self):
        self._version(5)
        from io import StringIO

        output = StringIO()
        call_command('hc_reminders', stdout=output)

        self.assertIn('created=1', output.getvalue())


class DashboardCacheTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Cache', code='HC-CACHE')
        self.user = get_user_model().objects.create_user(username='cache-user')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=self.user, capability='can_view_hc', unit_kerja=self.unit
        )

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def _employee(self, name, number):
        employee = Pegawai.objects.create(
            nama_lengkap=name, nomor_pegawai=number, kategori='PPA'
        )
        PenempatanPegawai.objects.create(
            pegawai=employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=5),
            alokasi_fte=Decimal('1.00'),
        )
        return employee

    def test_new_employee_invalidates_the_cached_dashboard(self):
        self.client.force_login(self.user)
        first = self.client.get('/human-capital/')
        self.assertEqual(first.context['total_employees'], 0)

        self._employee('Pegawai Baru', 'CACHE-1')

        second = self.client.get('/human-capital/')
        self.assertEqual(second.context['total_employees'], 1)

    def test_cache_is_scoped_per_user(self):
        self.client.force_login(self.user)
        self.client.get('/human-capital/')
        other = get_user_model().objects.create_user(username='cache-other')
        UserProfile.objects.create(user=other, role='ADMIN_RS', unit_kerja=self.unit)
        self.client.force_login(other)

        response = self.client.get('/human-capital/')

        self.assertEqual(response.status_code, 403)


class ReminderTargetTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Tugas', code='HC-TASK')
        self.owner = get_user_model().objects.create_user(username='task-owner')
        UserProfile.objects.create(user=self.owner, role='STAF_NAKES', unit_kerja=self.unit)
        self.employee = Pegawai.objects.create(
            akun=self.owner, nama_lengkap='Pemilik Tugas', kategori='PPA'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )

    def test_overdue_orientation_creates_one_task_reminder(self):
        from sdm.models import (
            AktivitasOrientasi,
            PenugasanOrientasi,
            ProgramOrientasi,
        )
        from sdm.models.pengingat import sync_task_reminders

        program = ProgramOrientasi.objects.create(nama='Orientasi', berlaku_hari=7)
        AktivitasOrientasi.objects.create(program=program, nama='A', wajib=True)
        PenugasanOrientasi.objects.create(
            employee=self.employee, program=program, unit_kerja=self.unit,
            tenggat=self.today - timedelta(days=2),
        )

        first = sync_task_reminders(as_of=self.today)
        second = sync_task_reminders(as_of=self.today)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(
            PengingatSDM.objects.filter(target_type='ORIENTATION').count(), 1
        )

    def test_due_soon_appraisal_creates_a_task_reminder(self):
        from sdm.models import PenilaianKinerja, PeriodeKinerja
        from sdm.models.pengingat import sync_task_reminders

        period = PeriodeKinerja.objects.create(
            nama='P1', tanggal_mulai=self.today - timedelta(days=90),
            tanggal_selesai=self.today + timedelta(days=3),
        )
        PenilaianKinerja.objects.create(
            periode=period, employee=self.employee, reviewer=self.owner
        )

        created = sync_task_reminders(as_of=self.today)

        self.assertEqual(created, 1)
        self.assertTrue(
            PengingatSDM.objects.filter(
                target_type='APPRAISAL', band='TASK_DUE'
            ).exists()
        )


class NavigationResilienceTests(TestCase):
    """The processor runs on every page; a missing sdm table must not 500 the site."""

    def test_missing_table_degrades_to_no_menu(self):
        from unittest.mock import patch

        from django.db import DatabaseError

        from sdm.context_processors import hc_navigation

        user = get_user_model().objects.create_user(username='nav-resilient')
        request = type('Req', (), {'user': user})()

        with patch(
            'sdm.context_processors.granted_capabilities',
            side_effect=DatabaseError('no such table: sdm_hcgrant'),
        ):
            context = hc_navigation(request)

        self.assertFalse(any(context.values()))
        self.assertIn('nav_pegawai', context)


class HospitalScopeCacheKeyTests(TestCase):
    """A hospital-scope grant has unit_kerja=None; the cache key must still sort."""

    def test_dashboard_renders_with_hospital_scope_grant(self):
        from django.core.cache import cache

        cache.clear()
        unit = UnitKerja.objects.create(name='Unit Cache HS', code='HC-CHS')
        user = get_user_model().objects.create_user(username='hospital-scope')
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=None)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=user, capability='can_view_hc', unit_kerja=None
        )
        self.client.force_login(user)

        response = self.client.get('/human-capital/')

        self.assertEqual(response.status_code, 200)
        cache.clear()
