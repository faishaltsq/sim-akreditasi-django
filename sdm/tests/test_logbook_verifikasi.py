"""Fase 2: preseptor verification, queue, and locking of verified entries."""
from accounts.models import RolePermissionConfig
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from akreditasi.models import UnitKerja
from sdm.models import EntriLogbookKlinis, HcGrant
from sdm.models.logbook import VerifikasiLogbook
from sdm.services.logbook import entries_to_verify, verify_entry
from sdm.tests.test_logbook import LogbookBase


class VerifikasiLogbookTests(LogbookBase):
    def setUp(self):
        super().setUp()
        self.owner_user = self._plain_user('verif-owner')
        self.employee = self._employee(user=self.owner_user)
        self.katalog = self._katalog()
        self.entry = EntriLogbookKlinis.objects.create(
            employee=self.employee, tanggal=self.today, unit_kerja=self.unit,
            katalog_tindakan=self.katalog, jumlah_mandiri=2,
            created_by=self.reviewer,
        )

    def _outsider(self, unit):
        user = get_user_model().objects.create_user(username=f'out-{unit.code}')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=user, capability='can_review_hc_credentials', unit_kerja=unit,
        )
        return user

    def test_verifier_from_another_unit_is_refused(self):
        other_unit = UnitKerja.objects.create(name='Unit Preseptor Lain', code='HC-PSL')
        outsider = self._outsider(other_unit)
        with self.assertRaises(Exception):
            verify_entry(
                user=outsider, entry=self.entry, status=VerifikasiLogbook.VERIFIED,
            )
        self.assertFalse(VerifikasiLogbook.objects.filter(entri=self.entry).exists())

    def test_approving_twice_appends_two_rows_and_latest_wins(self):
        verify_entry(user=self.reviewer, entry=self.entry, status=VerifikasiLogbook.REJECTED)
        verify_entry(user=self.reviewer, entry=self.entry, status=VerifikasiLogbook.VERIFIED)
        rows = VerifikasiLogbook.objects.filter(entri=self.entry)
        self.assertEqual(rows.count(), 2)
        self.entry.refresh_from_db()
        self.assertTrue(self.entry.sudah_diverifikasi)
        self.assertEqual(self.entry.verifikasi_terakhir.status, VerifikasiLogbook.VERIFIED)

    def test_verified_entry_cannot_be_edited_or_deleted(self):
        verify_entry(user=self.reviewer, entry=self.entry, status=VerifikasiLogbook.VERIFIED)
        self.client.force_login(self.owner_user)
        edited = self.client.post(reverse('sdm:logbook_edit', args=[self.entry.pk]), {
            'tanggal': self.today.isoformat(),
            'unit_kerja': str(self.unit.pk),
            'modus': 'katalog',
            'katalog_tindakan': str(self.katalog.pk),
            'jumlah_mandiri': 9,
        })
        self.assertEqual(edited.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.jumlah_mandiri, 2)

        deleted = self.client.post(reverse('sdm:logbook_delete', args=[self.entry.pk]))
        self.assertEqual(deleted.status_code, 302)
        self.assertTrue(EntriLogbookKlinis.objects.filter(pk=self.entry.pk).exists())

    def test_unverified_entry_appears_in_queue(self):
        queue = entries_to_verify(self.reviewer)
        self.assertIn(self.entry, queue)
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('sdm:logbook_verifikasi'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.katalog.nama)

    def test_rejected_entry_returns_to_queue(self):
        self.client.force_login(self.reviewer)
        self.client.post(
            reverse('sdm:logbook_verifikasi_aksi', args=[self.entry.pk]),
            {'aksi': 'approve'},
        )
        self.entry.refresh_from_db()
        self.assertTrue(self.entry.sudah_diverifikasi)
        self.assertNotIn(self.entry, entries_to_verify(self.reviewer))

        self.client.post(
            reverse('sdm:logbook_verifikasi_aksi', args=[self.entry.pk]),
            {'aksi': 'reject', 'catatan': 'Belum sesuai'},
        )
        self.entry.refresh_from_db()
        self.assertFalse(self.entry.sudah_diverifikasi)
        self.assertIn(self.entry, entries_to_verify(self.reviewer))
        self.assertEqual(
            VerifikasiLogbook.objects.filter(entri=self.entry).count(), 2,
        )
        queue = self.client.get(reverse('sdm:logbook_verifikasi'))
        self.assertContains(queue, 'Ditolak')

    def test_queue_action_by_outsider_is_refused(self):
        other_unit = UnitKerja.objects.create(name='Unit Preseptor Asing', code='HC-PSA')
        outsider = self._outsider(other_unit)
        self.client.force_login(outsider)
        response = self.client.post(
            reverse('sdm:logbook_verifikasi_aksi', args=[self.entry.pk]),
            {'aksi': 'approve'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(VerifikasiLogbook.objects.filter(entri=self.entry).exists())


class LogbookCepatTests(LogbookBase):
    def setUp(self):
        super().setUp()
        self.owner_user = self._plain_user('cepat-owner')
        self.employee = self._employee(user=self.owner_user)
        self.katalog = self._katalog()
        self.employee.profesi_master = self.katalog.jenjang.profesi
        self.employee.save(update_fields=['profesi_master'])

    def test_owner_records_one_action_and_stays_on_list(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse('sdm:logbook_cepat'),
            {
                'tanggal': self.today.isoformat(),
                'unit_kerja': str(self.unit.pk),
                'modus': 'katalog',
                'katalog_tindakan': str(self.katalog.pk),
                'jumlah_mandiri': 1,
            },
            HTTP_REFERER=reverse('sdm:logbook_list'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('sdm:logbook_list'))
        self.assertTrue(
            EntriLogbookKlinis.objects.filter(
                employee=self.employee, katalog_tindakan=self.katalog,
            ).exists()
        )

    def test_quick_entry_preserves_pegawai_filter_for_reviewer(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(reverse('sdm:logbook_cepat'), {
            'pegawai': str(self.employee.pk),
            'tanggal': self.today.isoformat(),
            'unit_kerja': str(self.unit.pk),
            'modus': 'bebas',
            'tindakan': 'Pendampingan',
            'jumlah_supervisi': 2,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('sdm:logbook_list')}?pegawai={self.employee.pk}",
        )

    def test_quick_entry_refuses_unrelated_target(self):
        outsider_unit = UnitKerja.objects.create(name='Unit Asing Cepat', code='HC-ACP')
        outsider = get_user_model().objects.create_user(username='cepat-outsider')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=outsider, capability='can_review_hc_credentials',
            unit_kerja=outsider_unit,
        )
        self.client.force_login(outsider)
        response = self.client.post(reverse('sdm:logbook_cepat'), {
            'employee': str(self.employee.pk),
            'tanggal': self.today.isoformat(),
            'unit_kerja': str(self.unit.pk),
            'modus': 'bebas',
            'tindakan': 'Pendampingan',
            'jumlah_mandiri': 1,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            EntriLogbookKlinis.objects.filter(employee=self.employee).exists()
        )
