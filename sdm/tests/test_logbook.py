"""C-2: structured clinical logbook entries, recap, and route security."""
from datetime import timedelta
from decimal import Decimal

from accounts.models import RolePermissionConfig, UserProfile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import (
    HcGrant,
    KatalogTindakan,
    MasterJenjangProfesi,
    MasterProfesiPegawai,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
)
from sdm.models.logbook import EntriLogbookKlinis
from sdm.services.logbook import logbook_recap


class LogbookBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Logbook', code='HC-LOG')
        self.unit2 = UnitKerja.objects.create(name='Unit Lain', code='HC-LOG2')
        self.reviewer = self._hc_user('log-reviewer')

    def _hc_user(self, username):
        user = get_user_model().objects.create_user(username=username)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=user, capability='can_view_hc', unit_kerja=self.unit,
        )
        HcGrant.objects.create(
            user=user, capability='can_review_hc_credentials', unit_kerja=self.unit,
        )
        return user

    def _plain_user(self, username):
        return get_user_model().objects.create_user(username=username)

    def _employee(self, name='Perawat Logbook', user=None):
        employee = Pegawai.objects.create(
            nama_lengkap=name, kategori='PPA', profesi='Perawat', akun=user,
        )
        PenempatanPegawai.objects.create(
            pegawai=employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=3650),
            alokasi_fte=Decimal('1.00'),
        )
        return employee

    def _katalog(self, kode='PR-TES', nama='Tindakan Uji'):
        profesi = MasterProfesiPegawai.objects.create(
            code=f'P-{kode}', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        jenjang = MasterJenjangProfesi.objects.create(
            profesi=profesi, kode='PK-I', nama='Perawat I', urutan=1,
        )
        return KatalogTindakan.objects.create(
            kode=kode, nama=nama, jenjang=jenjang, tingkat_supervisi='M',
        )


class LogbookModelTests(LogbookBase):
    def test_xor_catalog_or_free_text_required(self):
        employee = self._employee()
        katalog = self._katalog()
        both = EntriLogbookKlinis(
            employee=employee, tanggal=self.today, unit_kerja=self.unit,
            katalog_tindakan=katalog, tindakan='Teks bebas', jumlah_mandiri=1,
        )
        with self.assertRaises(Exception):
            both.full_clean()

        neither = EntriLogbookKlinis(
            employee=employee, tanggal=self.today, unit_kerja=self.unit,
            jumlah_mandiri=1,
        )
        with self.assertRaises(Exception):
            neither.full_clean()

        valid = EntriLogbookKlinis(
            employee=employee, tanggal=self.today, unit_kerja=self.unit,
            katalog_tindakan=katalog, jumlah_mandiri=1,
        )
        valid.full_clean()  # must not raise

        free = EntriLogbookKlinis(
            employee=employee, tanggal=self.today, unit_kerja=self.unit,
            tindakan='Konsultasi lintas unit', jumlah_supervisi=2,
        )
        free.full_clean()  # must not raise

    def test_at_least_one_count_positive(self):
        employee = self._employee()
        katalog = self._katalog()
        zero = EntriLogbookKlinis(
            employee=employee, tanggal=self.today, unit_kerja=self.unit,
            katalog_tindakan=katalog,
        )
        with self.assertRaises(Exception):
            zero.full_clean()


class LogbookRecapTests(LogbookBase):
    def test_recap_math_across_units_and_actions(self):
        employee = self._employee()
        t1 = self._katalog('PR-A1', 'Pemasangan Infus')
        t2 = self._katalog('PR-B2', 'Konsultasi Gizi')
        other_unit = self.unit2
        EntriLogbookKlinis.objects.create(
            employee=employee, tanggal=self.today - timedelta(days=100),
            unit_kerja=self.unit, katalog_tindakan=t1,
            jumlah_mandiri=4, jumlah_supervisi=1,
        )
        EntriLogbookKlinis.objects.create(
            employee=employee, tanggal=self.today - timedelta(days=50),
            unit_kerja=other_unit, katalog_tindakan=t1, jumlah_mandiri=2,
        )
        EntriLogbookKlinis.objects.create(
            employee=employee, tanggal=self.today - timedelta(days=10),
            unit_kerja=self.unit, tindakan='Pelatihan internal', jumlah_supervisi=3,
        )
        EntriLogbookKlinis.objects.create(
            employee=employee, tanggal=self.today - timedelta(days=5),
            unit_kerja=self.unit, katalog_tindakan=t2, jumlah_mandiri=1,
        )
        # outside the 36-month window must be excluded (41 months back)
        EntriLogbookKlinis.objects.create(
            employee=employee, tanggal=self.today - timedelta(days=1250),
            unit_kerja=self.unit, katalog_tindakan=t1, jumlah_mandiri=99,
        )

        recap = logbook_recap(employee)

        self.assertEqual(recap['mandiri'], 7)
        self.assertEqual(recap['supervisi'], 4)
        self.assertEqual(recap['total'], 11)
        expected_from = self.today.replace(
            year=self.today.year - 3, day=min(self.today.day, 28)
        )
        self.assertEqual(recap['dari_tanggal'], expected_from)
        by_label = {row['label']: row for row in recap['per_tindakan']}
        self.assertEqual(by_label['Pemasangan Infus']['mandiri'], 6)
        self.assertEqual(by_label['Pemasangan Infus']['supervisi'], 1)
        self.assertEqual(by_label['Konsultasi Gizi']['mandiri'], 1)
        self.assertEqual(by_label['Pelatihan internal']['supervisi'], 3)

    def test_empty_recap_has_no_fabricated_percentage(self):
        employee = self._employee()
        recap = logbook_recap(employee)
        self.assertEqual(recap['mandiri'], 0)
        self.assertEqual(recap['supervisi'], 0)
        self.assertEqual(recap['total'], 0)
        self.assertEqual(recap['per_tindakan'], [])


class LogbookRouteTests(LogbookBase):
    def setUp(self):
        super().setUp()
        self.employee = self._employee(user=self._plain_user('log-owner'))
        self.katalog = self._katalog()
        self.employee.profesi_master = self.katalog.jenjang.profesi
        self.employee.save(update_fields=['profesi_master'])
        self.entry = EntriLogbookKlinis.objects.create(
            employee=self.employee, tanggal=self.today, unit_kerja=self.unit,
            katalog_tindakan=self.katalog, jumlah_mandiri=2,
            created_by=self.reviewer,
        )
        self.other_employee = self._employee('Perawat Lain')
        self.other_entry = EntriLogbookKlinis.objects.create(
            employee=self.other_employee, tanggal=self.today, unit_kerja=self.unit,
            katalog_tindakan=self.katalog, jumlah_mandiri=1,
            created_by=self.reviewer,
        )

    def test_create_requires_login(self):
        response = self.client.get(reverse('sdm:logbook_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_reviewer_lists_unit_entries(self):
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('sdm:logbook_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perawat Logbook')

    def test_create_by_reviewer_writes_entry_and_audit(self):
        self.client.force_login(self.reviewer)
        before = PeristiwaSDM.objects.filter(jenis_peristiwa='logbook_entry_created').count()
        response = self.client.post(reverse('sdm:logbook_create'), {
            'employee': str(self.employee.pk),
            'tanggal': self.today.isoformat(),
            'unit_kerja': str(self.unit.pk),
            'modus': 'katalog',
            'katalog_tindakan': str(self.katalog.pk),
            'jumlah_mandiri': 3,
            'jumlah_supervisi': 0,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            EntriLogbookKlinis.objects.filter(
                employee=self.employee, jumlah_mandiri=3
            ).exists()
        )
        self.assertEqual(
            PeristiwaSDM.objects.filter(jenis_peristiwa='logbook_entry_created').count(),
            before + 1,
        )

    def test_out_of_unit_reviewer_cannot_read_other_units_entries(self):
        outsider_unit = UnitKerja.objects.create(name='Unit Asing', code='HC-ASG')
        outsider = get_user_model().objects.create_user(username='outsider')
        cfg = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        cfg.can_view_hc = True
        cfg.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(user=outsider, capability='can_view_hc', unit_kerja=outsider_unit)
        HcGrant.objects.create(
            user=outsider, capability='can_review_hc_credentials',
            unit_kerja=outsider_unit,
        )
        self.client.force_login(outsider)
        response = self.client.get(
            reverse('sdm:logbook_list'), {'pegawai': str(self.employee.pk)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Perawat Logbook')

    def test_delete_by_creator_writes_audit_event(self):
        self.client.force_login(self.reviewer)
        before = PeristiwaSDM.objects.filter(jenis_peristiwa='logbook_entry_deleted').count()
        response = self.client.post(
            reverse('sdm:logbook_delete', args=[self.entry.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            EntriLogbookKlinis.objects.filter(pk=self.entry.pk).exists()
        )
        self.assertEqual(
            PeristiwaSDM.objects.filter(jenis_peristiwa='logbook_entry_deleted').count(),
            before + 1,
        )

    def test_delete_forbidden_to_unrelated_user(self):
        outsider_unit = UnitKerja.objects.create(name='Unit Asing 2', code='HC-AS2')
        outsider = get_user_model().objects.create_user(username='outsider2')
        cfg = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        cfg.can_view_hc = True
        cfg.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(user=outsider, capability='can_view_hc', unit_kerja=outsider_unit)
        HcGrant.objects.create(
            user=outsider, capability='can_review_hc_credentials',
            unit_kerja=outsider_unit,
        )
        self.client.force_login(outsider)
        response = self.client.post(
            reverse('sdm:logbook_delete', args=[self.entry.pk])
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertTrue(
            EntriLogbookKlinis.objects.filter(pk=self.entry.pk).exists()
        )

    def test_owner_sees_own_entries_without_hc_grant(self):
        self.client.force_login(self.employee.akun)
        response = self.client.get(reverse('sdm:logbook_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perawat Logbook')
        self.assertNotContains(response, 'Perawat Lain')

    def test_owner_cannot_read_other_employees_entries(self):
        self.client.force_login(self.employee.akun)
        response = self.client.post(
            reverse('sdm:logbook_delete', args=[self.other_entry.pk])
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertTrue(
            EntriLogbookKlinis.objects.filter(pk=self.other_entry.pk).exists()
        )
