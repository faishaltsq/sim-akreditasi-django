from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    HcGrant,
    IzinProfesiPegawai,
    Pegawai,
    PengingatSDM,
    PenempatanPegawai,
)
from sdm.services.legalitas import sync_legal_reminders


class LegalBannerAndReminderTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Legal', code='LG-TEST')
        self.user = get_user_model().objects.create_user(username='lg-admin')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(user=self.user, capability='can_view_hc', unit_kerja=self.unit)
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Legal', kategori='PPA', profesi='Perawat',
            akun=get_user_model().objects.create_user(username='lg-pegawai'),
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=100),
            alokasi_fte=Decimal('1.00'),
        )

    def _izin(self, **kwargs):
        defaults = dict(
            pegawai=self.employee, subtype='STR', nomor_izin='STR-B',
            validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=200),
            tanggal_berakhir=self.today + timedelta(days=45),
        )
        defaults.update(kwargs)
        return IzinProfesiPegawai.objects.create(**defaults)

    def test_profile_shows_expiry_band_badge(self):
        self._izin()
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/')
        self.assertContains(response, '31–90 hari')

    def test_profile_shows_warning_banner_for_near_expiry(self):
        self._izin(tanggal_berakhir=self.today + timedelta(days=10))
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/')
        self.assertContains(response, 'alert-warning')

    def test_lifetime_license_shows_no_banner(self):
        self._izin(validity_mode='LIFETIME', tanggal_berakhir=None)
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/')
        self.assertNotContains(response, 'alert-warning')

    def test_sync_creates_one_reminder_with_declared_band(self):
        self._izin(tanggal_berakhir=self.today + timedelta(days=45))
        sync_legal_reminders(employee=self.employee, actor=self.user)
        reminders = PengingatSDM.objects.filter(employee=self.employee)
        self.assertEqual(reminders.count(), 1)
        self.assertIn(reminders.first().band, dict(PengingatSDM.BAND_CHOICES))

    def test_sync_is_idempotent(self):
        self._izin()
        sync_legal_reminders(employee=self.employee, actor=self.user)
        sync_legal_reminders(employee=self.employee, actor=self.user)
        self.assertEqual(
            PengingatSDM.objects.filter(employee=self.employee).count(), 1
        )

    def test_sync_skips_employee_without_account(self):
        lone = Pegawai.objects.create(nama_lengkap='Tanpa Akun', kategori='NON_PPA')
        IzinProfesiPegawai.objects.create(
            pegawai=lone, subtype='STR', nomor_izin='STR-X', validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=100),
            tanggal_berakhir=self.today + timedelta(days=20),
        )
        sync_legal_reminders(employee=lone, actor=self.user)
        self.assertEqual(PengingatSDM.objects.filter(employee=lone).count(), 0)

    def test_renewed_license_archives_stale_reminder(self):
        izin = self._izin(tanggal_berakhir=self.today + timedelta(days=20))
        sync_legal_reminders(employee=self.employee, actor=self.user)
        izin.tanggal_berakhir = self.today + timedelta(days=400)
        izin.save(update_fields=['tanggal_berakhir'])
        sync_legal_reminders(employee=self.employee, actor=self.user)
        self.assertEqual(
            PengingatSDM.objects.filter(
                employee=self.employee, read_at__isnull=True
            ).count(),
            0,
        )

    def test_document_reminder_is_not_archived_by_legal_sync(self):
        """Sinkron legalitas tidak boleh mengarsipkan pengingat dokumen lain."""
        from sdm.models import DokumenPegawai, VersiDokumen
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL',
            jenis_berkas='STR', title='STR Lama', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='str.pdf',
            storage_key='legal-test/str.pdf', sha256='0' * 64, size_bytes=1024,
            content_type='application/pdf', status='VERIFIED',
            valid_until=self.today + timedelta(days=15),
        )
        self._izin(tanggal_berakhir=self.today + timedelta(days=20))
        sync_legal_reminders(employee=self.employee, actor=self.user)
        doc_reminders = PengingatSDM.objects.filter(
            employee=self.employee, target_type='DOCUMENT', read_at__isnull=True,
        )
        self.assertEqual(doc_reminders.count(), 1)
        self.assertEqual(doc_reminders.first().band, 'LT_30')
