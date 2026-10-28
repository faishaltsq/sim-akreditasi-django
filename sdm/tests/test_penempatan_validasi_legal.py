from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from akreditasi.models import UnitKerja
from sdm.models import IzinProfesiPegawai, Pegawai, PenempatanPegawai
from sdm.services.legalitas import placement_legal_blockers
from sdm.services.penempatan import save_assignment


class PlacementLegalValidationTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='ICU', code='ICU-TEST')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Suster ICU', kategori='PPA', profesi='Perawat'
        )

    def _izin(self, **kwargs):
        defaults = dict(
            pegawai=self.employee, subtype='STR', nomor_izin='STR-1',
            validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=365),
            tanggal_berakhir=self.today + timedelta(days=365),
        )
        defaults.update(kwargs)
        return IzinProfesiPegawai.objects.create(**defaults)

    def test_valid_str_produces_no_blocker(self):
        self._izin()
        self.assertEqual(
            placement_legal_blockers(self.employee, unit_kerja=self.unit), []
        )

    def test_expired_str_blocks_placement(self):
        self._izin(tanggal_berakhir=self.today - timedelta(days=1))
        blockers = placement_legal_blockers(self.employee, unit_kerja=self.unit)
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]['subtype'], 'STR')

    def test_lifetime_str_never_blocks(self):
        self._izin(validity_mode='LIFETIME', tanggal_berakhir=None)
        self.assertEqual(
            placement_legal_blockers(self.employee, unit_kerja=self.unit), []
        )

    def test_missing_expiry_date_is_unknown_and_does_not_block(self):
        self._izin(tanggal_berakhir=None)
        self.assertEqual(
            placement_legal_blockers(self.employee, unit_kerja=self.unit), []
        )

    def test_sip_expiring_within_ninety_days_blocks(self):
        self._izin(
            subtype='SIP', nomor_izin='SIP-1',
            tanggal_berakhir=self.today + timedelta(days=45),
        )
        blockers = placement_legal_blockers(self.employee, unit_kerja=self.unit)
        self.assertEqual(blockers[0]['subtype'], 'SIP')

    def test_blocker_message_names_the_license(self):
        self._izin(
            nomor_izin='STR-999', tanggal_berakhir=self.today - timedelta(days=5)
        )
        blockers = placement_legal_blockers(self.employee, unit_kerja=self.unit)
        self.assertIn('STR-999', blockers[0]['alasan'])

    def test_save_assignment_refuses_expired_str(self):
        self._izin(tanggal_berakhir=self.today - timedelta(days=5))
        assignment = PenempatanPegawai(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=Decimal('1.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            save_assignment(assignment)
        self.assertIn('legalitas', str(ctx.exception.message_dict))
        self.assertFalse(
            PenempatanPegawai.objects.filter(pegawai=self.employee).exists()
        )

    def test_save_assignment_allows_valid_str(self):
        self._izin()
        assignment = save_assignment(PenempatanPegawai(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=Decimal('1.00'),
        ))
        self.assertIsNotNone(assignment.pk)

    def test_existing_placement_is_not_retroactively_blocked(self):
        self._izin()
        assignment = save_assignment(PenempatanPegawai(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=Decimal('1.00'),
        ))
        izin = self.employee.izin_profesi.get()
        izin.tanggal_berakhir = self.today - timedelta(days=1)
        izin.save(update_fields=['tanggal_berakhir'])
        assignment.alokasi_fte = Decimal('0.50')
        saved = save_assignment(assignment)
        self.assertEqual(saved.alokasi_fte, Decimal('0.50'))
