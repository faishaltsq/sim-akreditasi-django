"""RED tests for Task A3: legal EWS bands and reminders."""

from django.test import TestCase
from django.utils import timezone
import datetime

from akreditasi.models import UnitKerja
from sdm.models import Pegawai, PenempatanPegawai
from sdm.services.legalitas import legal_status, sync_legal_reminders


class LegalStatusTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit', code='UNIT-1')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Legal', kategori='PPA', profesi='Perawat',
            status='AKTIF', data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=1.00,
        )

    def _account(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username=f'legal-{self.employee.pk}-{User.objects.count()}'
        )

    def _izin(self, subtype, mode, berakhir=None, local=True, tanggal_terbit=None):
        from sdm.models import IzinProfesiPegawai
        if tanggal_terbit is None:
            tanggal_terbit = self.today
        return IzinProfesiPegawai.objects.create(
            pegawai=self.employee, subtype=subtype, nomor_izin=f'N-{subtype}',
            pemberi_izin='P', profesi='Perawat', validity_mode=mode,
            tanggal_terbit=tanggal_terbit, tanggal_berakhir=berakhir,
            is_local_rs=local,
        )

    def test_str_near_expiry_zero_seven_band(self):
        self._izin('STR', 'DATED', self.today + datetime.timedelta(days=5))
        status = legal_status(self.employee, as_of=self.today)
        items = status.by_subtype('STR')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['band'], '0-7')
        self.assertEqual(items[0]['state'], '0-7')

    def test_sip_expired_band(self):
        self._izin('SIP', 'DATED', self.today - datetime.timedelta(days=1),
                   tanggal_terbit=self.today - datetime.timedelta(days=60))
        status = legal_status(self.employee, as_of=self.today)
        items = status.by_subtype('SIP')
        self.assertEqual(items[0]['band'], 'expired')

    def test_lifetime_str_never_expires(self):
        self._izin('STR', 'LIFETIME', berakhir=None)
        status = legal_status(self.employee, as_of=self.today)
        items = status.by_subtype('STR')
        self.assertEqual(items[0]['band'], 'valid')

    def test_missing_license_reports_unknown(self):
        status = legal_status(self.employee, as_of=self.today)
        self.assertTrue(any(i['band'] == 'unknown' for i in status.items))

    def test_external_clinic_sip_excluded_for_local_rs(self):
        self._izin('SIP', 'DATED', self.today + datetime.timedelta(days=200), local=False)
        status = legal_status(self.employee, as_of=self.today, practice_site=self.unit)
        self.assertEqual(len(status.by_subtype('SIP')), 0)

    def test_sync_legal_reminders_creates_for_urgent(self):
        self.employee.akun = self._account()
        self.employee.save(update_fields=['akun'])
        self._izin('STR', 'DATED', self.today + datetime.timedelta(days=5))
        result = sync_legal_reminders(employee=self.employee, actor=None, as_of=self.today)
        self.assertGreaterEqual(result['created'], 1)

    def test_sync_legal_reminders_skips_employee_without_account(self):
        """Tanpa akun, tidak ada penerima in-app: sync harus aman, bukan error."""
        from sdm.models import PengingatSDM
        self._izin('STR', 'DATED', self.today + datetime.timedelta(days=5))
        result = sync_legal_reminders(employee=self.employee, actor=None, as_of=self.today)
        self.assertEqual(result['created'], 0)
        self.assertEqual(PengingatSDM.objects.filter(employee=self.employee).count(), 0)


class LegalReminderTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit', code='UNIT-2')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Reminder', kategori='NON_PPA', profesi='Admin',
            status='AKTIF', data_origin='MANUAL',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=1.00,
        )

    def _account(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(
            username=f'legal-{self.employee.pk}-{User.objects.count()}'
        )

    def test_replacement_reminder_updates_band(self):
        from sdm.models import IzinProfesiPegawai, PengingatSDM
        self.employee.akun = self._account()
        self.employee.save(update_fields=['akun'])
        izin = IzinProfesiPegawai.objects.create(
            pegawai=self.employee, subtype='STR', nomor_izin='N-R',
            pemberi_izin='P', profesi='Admin', validity_mode='DATED',
            tanggal_terbit=self.today, tanggal_berakhir=self.today + datetime.timedelta(days=40),
            is_local_rs=True,
        )
        r1 = sync_legal_reminders(employee=self.employee, actor=None, as_of=self.today)
        izin.tanggal_berakhir = self.today + datetime.timedelta(days=5)
        izin.save(update_fields=['tanggal_berakhir'])
        r2 = sync_legal_reminders(employee=self.employee, actor=None, as_of=self.today)
        key = PengingatSDM.build_key(
            employee_id=self.employee.pk,
            version_id=f"legal:izin_profesi:N-R",
            band='LT_30',
            target_type='DOCUMENT',
        )
        self.assertTrue(PengingatSDM.objects.filter(idempotency_key=key, band='LT_30').exists())
        self.assertGreaterEqual(r2['updated'], 0)
