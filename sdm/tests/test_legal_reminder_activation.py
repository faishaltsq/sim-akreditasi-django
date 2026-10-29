"""Production wiring for legal reminders: hc_reminders must scan STR/SIP too."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from sdm.models import (
    DokumenPegawai,
    IzinProfesiPegawai,
    Pegawai,
    PengingatSDM,
    VersiDokumen,
)
from sdm.services.legalitas import sync_legal_reminders_all


class LegalReminderActivationTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = get_user_model().objects.create_user(username='legal-act')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Aktif', kategori='PPA', profesi='Perawat',
            akun=self.user,
        )

    def _izin(self, **kwargs):
        defaults = dict(
            pegawai=self.employee, subtype='STR', nomor_izin='STR-ACT',
            validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=100),
            tanggal_berakhir=self.today + timedelta(days=20),
            is_local_rs=True,
        )
        defaults.update(kwargs)
        return IzinProfesiPegawai.objects.create(**defaults)

    def test_command_creates_reminder_for_urgent_str(self):
        self._izin()
        out = StringIO()
        call_command('hc_reminders', stdout=out)
        reminder = PengingatSDM.objects.get(employee=self.employee)
        self.assertEqual(reminder.band, 'LT_30')
        self.assertIn('STR-ACT', reminder.alasan)

    def test_command_is_idempotent(self):
        self._izin()
        call_command('hc_reminders', stdout=StringIO())
        call_command('hc_reminders', stdout=StringIO())
        self.assertEqual(
            PengingatSDM.objects.filter(employee=self.employee).count(), 1
        )

    def test_expired_str_maps_to_expired_band(self):
        self._izin(tanggal_berakhir=self.today - timedelta(days=3))
        sync_legal_reminders_all()
        self.assertEqual(
            PengingatSDM.objects.get(employee=self.employee).band, 'EXPIRED'
        )

    def test_employee_without_account_is_skipped(self):
        lone = Pegawai.objects.create(nama_lengkap='Tanpa Akun', kategori='NON_PPA')
        IzinProfesiPegawai.objects.create(
            pegawai=lone, subtype='STR', nomor_izin='STR-LONE',
            validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=100),
            tanggal_berakhir=self.today + timedelta(days=20),
            is_local_rs=True,
        )
        sync_legal_reminders_all()
        self.assertEqual(PengingatSDM.objects.filter(employee=lone).count(), 0)

    def test_inactive_account_is_skipped(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self._izin()
        sync_legal_reminders_all()
        self.assertEqual(
            PengingatSDM.objects.filter(employee=self.employee).count(), 0
        )

    def test_document_reminder_survives_legal_sync(self):
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL',
            jenis_berkas='STR', title='STR Dokumen', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='str.pdf',
            storage_key='act-test/str.pdf', sha256='0' * 64, size_bytes=1024,
            content_type='application/pdf', status='VERIFIED',
            valid_until=self.today + timedelta(days=15),
        )
        self._izin()
        call_command('hc_reminders', stdout=StringIO())
        keys = set(
            PengingatSDM.objects.filter(
                employee=self.employee, read_at__isnull=True
            ).values_list('idempotency_key', flat=True)
        )
        self.assertEqual(len(keys), 2, keys)
        self.assertTrue(any(':legal:' in k for k in keys))
        self.assertTrue(
            any(k.endswith(':LT_30') and ':legal:' not in k for k in keys)
        )
