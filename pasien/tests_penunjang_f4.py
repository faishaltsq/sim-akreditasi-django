"""F4 — Langkah 7 penunjang POLI-JANTUNG (ADR-5, ADR-4/ADR-10).

Satu modul untuk seluruh butir F4 supaya perilaku lintas butir (status, nilai
kritis, billing, worklist) diuji pada fixture yang sama. Setiap tes menyatakan
perilaku yang dapat diamati: baris ORM, isi ``fields`` galat, atau HTML.

F4.7 (quick-order bundle) sengaja tidak diuji karena isi paketnya tidak ada di
matriks S7-L2-02; dilaporkan sebagai AMBIGU-18, bukan dikarang.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from klinis.models import ItemPenunjang, KategoriPenunjang, TarifPenunjang
from pasien.models import BillingItem, KunjunganPasien, OrderPenunjang, Pasien
from pasien.services.igd_assessment_workflow import WorkflowConflict, WorkflowValidation
from pasien.services.penunjang_results import record_result


def make_hierarchy():
    """Satu cabang katalog 3 tingkat: Laboratorium → Hematologi → Darah Lengkap."""
    lab = KategoriPenunjang.objects.get_or_create(
        kode='QA-LAB', defaults={'nama': 'Laboratorium', 'level': 1})[0]
    hematologi = KategoriPenunjang.objects.get_or_create(
        kode='QA-LAB-HEM', defaults={'nama': 'Hematologi', 'level': 2, 'parent': lab})[0]
    kelompok = KategoriPenunjang.objects.get_or_create(
        kode='QA-LAB-HEM-DL', defaults={'nama': 'Darah Lengkap', 'level': 3, 'parent': hematologi})[0]
    return lab, hematologi, kelompok


class PenunjangF4Fixture(TestCase):
    """Order POLI-JANTUNG, unit LAB tujuan, dan akun pelaksana + pemesan."""

    @classmethod
    def setUpTestData(cls):
        cls.unit_poli = UnitKerja.objects.get_or_create(
            code='POLI-JANTUNG', defaults={'name': 'Poliklinik Jantung', 'level': 3})[0]
        cls.unit_lab = UnitKerja.objects.get_or_create(
            code='LAB-BDRS', defaults={'name': 'Laboratorium', 'level': 3})[0]
        cls.admin = User.objects.create_user('f4_admin', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=cls.admin, defaults={'role': 'ADMIN_RS', 'unit_kerja': cls.unit_poli})
        cls.doctor = cls.account('f4_dokter', 'DOKTER_SPESIALIS', cls.unit_poli, 'STAF_NAKES')
        cls.analyst = cls.account('f4_analis', 'ANALIS_LAB', cls.unit_lab, 'STAF_NAKES')
        cls.patient = Pasien.objects.create(
            no_rm='QA-F4-001', nama_lengkap='Pasien Penunjang',
            tanggal_lahir='1968-02-02', jenis_kelamin='P',
        )
        cls.visit = KunjunganPasien.objects.create(
            pasien=cls.patient, no_kunjungan='QA-F4-001', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), unit_kerja=cls.unit_poli,
            poliklinik='POLI-JANTUNG', penjamin='UMUM',
        )

    @classmethod
    def account(cls, username, profesi, unit, role):
        user = User.objects.create_user(username, password='fixture-only')
        UserProfile.objects.update_or_create(
            user=user, defaults={'role': role, 'profesi': profesi, 'unit_kerja': unit})
        return user

    def make_item(self, kode, nama, *, jenis='LAB', active=True, tarif=None):
        _, _, kelompok = make_hierarchy()
        item = ItemPenunjang.objects.create(
            kode=kode, nama=nama, group=kelompok, jenis_order=jenis,
            destination=self.unit_lab, active=active, source_version='QA-F4',
            reviewed_by=self.admin,
        )
        if tarif is not None:
            TarifPenunjang.objects.create(
                item=item, penjamin='UMUM', nominal=Decimal(tarif),
                valid_from=timezone.localdate() - timedelta(days=1),
            )
        return item

    def make_order(self, **kwargs):
        defaults = dict(
            kunjungan=self.visit, jenis='LAB', nama_pemeriksaan='Darah Lengkap',
            destination=self.unit_lab,
        )
        defaults.update(kwargs)
        return OrderPenunjang.objects.create(**defaults)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True)
class OrderStatusTest(PenunjangF4Fixture):
    """F4.2 (ADR-5): empat status; DIPROSES→SELESAI sah, SELESAI→DIPROSES ditolak."""

    def test_choices_are_the_four_values_from_the_adr(self):
        codes = [code for code, _ in OrderPenunjang.STATUS_CHOICES]
        self.assertEqual(codes, ['DRAFT', 'DIPROSES', 'SELESAI', 'BATAL'])
        self.assertEqual(OrderPenunjang._meta.get_field('status').default, 'DIPROSES')

    def test_new_order_starts_in_diproses(self):
        self.assertEqual(self.make_order().status, 'DIPROSES')

    def test_diproses_to_selesai_is_accepted(self):
        order = self.make_order()
        record_result(order.pk, self.analyst, {
            'status': 'SELESAI', 'hasil_pemeriksaan': 'Hb 13.5 g/dL',
            'interpretasi': 'Dalam batas normal',
        })
        order.refresh_from_db()
        self.assertEqual(order.status, 'SELESAI')

    def test_selesai_to_diproses_is_rejected(self):
        order = self.make_order(status='SELESAI', hasil_pemeriksaan='Hb 13.5')
        self.assertFalse(order.can_transition_to('DIPROSES'))
        with self.assertRaises(WorkflowConflict):
            record_result(order.pk, self.analyst, {'status': 'DIPROSES'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'SELESAI')

    def test_batal_is_terminal(self):
        order = self.make_order(status='BATAL')
        self.assertFalse(order.can_transition_to('DIPROSES'))
        self.assertFalse(order.can_transition_to('SELESAI'))

    def test_draft_can_be_sent_to_the_performing_unit(self):
        order = self.make_order(status='DRAFT')
        self.assertTrue(order.can_transition_to('DIPROSES'))

    def test_invalid_status_is_rejected_by_the_form(self):
        order = self.make_order()
        with self.assertRaises(WorkflowValidation):
            record_result(order.pk, self.analyst, {'status': 'ORDERED'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'DIPROSES')

    def test_worklist_filters_on_the_four_values(self):
        self.make_order(nama_pemeriksaan='Order diproses')
        self.make_order(nama_pemeriksaan='Order selesai', status='SELESAI')
        self.client.force_login(self.analyst)
        body = self.client.get(reverse('pasien:ancillary_worklist') + '?jenis=LAB&status=DIPROSES').content.decode()
        self.assertIn('Order diproses', body)
        self.assertNotIn('Order selesai', body)
        body = self.client.get(reverse('pasien:ancillary_worklist') + '?jenis=LAB&status=SELESAI').content.decode()
        self.assertIn('Order selesai', body)
        self.assertNotIn('Order diproses', body)
        self.assertEqual(
            self.client.get(reverse('pasien:ancillary_worklist') + '?jenis=LAB&status=ORDERED').status_code,
            400)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True)
class InterpretationLvefTest(PenunjangF4Fixture):
    """F4.3 (S7-L1-02/S7-L1-04): interpretasi + LVEF terpisah dari status."""

    def test_selesai_without_interpretation_is_rejected(self):
        order = self.make_order()
        with self.assertRaises(WorkflowValidation) as ctx:
            record_result(order.pk, self.analyst, {
                'status': 'SELESAI', 'hasil_pemeriksaan': 'Hb 13.5 g/dL'})
        self.assertIn('interpretasi', ctx.exception.errors)
        order.refresh_from_db()
        self.assertEqual(order.status, 'DIPROSES')

    def test_lvef_and_interpretation_are_stored_apart_from_status(self):
        order = self.make_order(jenis='EKG', nama_pemeriksaan='Ekokardiografi Transtorakal')
        record_result(order.pk, self.analyst, {
            'status': 'SELESAI',
            'hasil_pemeriksaan': 'EF 35%, hipokinetik global',
            'interpretasi': 'HFrEF',
            'lvef': 35,
        })
        order.refresh_from_db()
        self.assertEqual(order.status, 'SELESAI')
        self.assertEqual(order.interpretasi, 'HFrEF')
        self.assertEqual(order.lvef, 35)

    def test_lvef_outside_percent_range_is_rejected(self):
        order = self.make_order(jenis='EKG', nama_pemeriksaan='TTE')
        with self.assertRaises(WorkflowValidation) as ctx:
            record_result(order.pk, self.analyst, {
                'status': 'SELESAI', 'hasil_pemeriksaan': 'EF', 'interpretasi': 'Normal',
                'lvef': 140})
        self.assertIn('lvef', ctx.exception.errors)

    def test_interpretation_is_optional_while_still_in_progress(self):
        order = self.make_order()
        record_result(order.pk, self.analyst, {'status': 'DIPROSES', 'hasil_pemeriksaan': 'Sampel diterima'})
        order.refresh_from_db()
        self.assertEqual(order.interpretasi, '')


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True)
class CriticalReportingTest(PenunjangF4Fixture):
    """F4.4 (S7-L1-05, SKP 2/PP): nilai kritis wajib berjejak pelaporan + read-back."""

    def critical_payload(self, **kwargs):
        base = {
            'status': 'SELESAI',
            'hasil_pemeriksaan': 'K 6.8 mmol/L',
            'interpretasi': 'Hiperkalemia berat',
            'is_critical_value': True,
            'critical_value_catatan': 'Kalium kritis',
            'critical_found_at': timezone.now(),
            'critical_reported_at': timezone.now(),
            'critical_reported_to': 'dr. Cynthia Maharani, Sp.JP',
            'critical_readback_at': timezone.now(),
            'critical_readback_by': self.doctor.pk,
        }
        base.update(kwargs)
        return base

    def test_critical_without_reported_at_is_rejected(self):
        order = self.make_order()
        with self.assertRaises(WorkflowValidation) as ctx:
            record_result(order.pk, self.analyst, self.critical_payload(critical_reported_at=None))
        self.assertIn('critical_reported_at', ctx.exception.errors)
        order.refresh_from_db()
        self.assertFalse(order.is_critical_value)

    def test_critical_without_readback_is_rejected(self):
        order = self.make_order()
        with self.assertRaises(WorkflowValidation) as ctx:
            record_result(order.pk, self.analyst, self.critical_payload(critical_readback_by=None))
        self.assertIn('critical_readback_by', ctx.exception.errors)

    def test_complete_critical_report_is_stored(self):
        order = self.make_order()
        payload = self.critical_payload()
        record_result(order.pk, self.analyst, payload)
        order.refresh_from_db()
        self.assertTrue(order.is_critical_value)
        self.assertEqual(order.critical_reported_to, 'dr. Cynthia Maharani, Sp.JP')
        self.assertEqual(order.critical_readback_by, self.doctor)
        self.assertIsNotNone(order.critical_readback_at)
        self.assertEqual(order.critical_reporting_missing, [])

    def test_unknown_readback_verifier_is_rejected(self):
        order = self.make_order()
        with self.assertRaises(WorkflowValidation) as ctx:
            record_result(order.pk, self.analyst, self.critical_payload(critical_readback_by=999999))
        self.assertIn('critical_readback_by', ctx.exception.errors)

    def test_report_before_discovery_is_rejected(self):
        order = self.make_order()
        now = timezone.now()
        with self.assertRaises(WorkflowValidation) as ctx:
            record_result(order.pk, self.analyst, self.critical_payload(
                critical_found_at=now, critical_reported_at=now - timedelta(minutes=5)))
        self.assertIn('critical_reported_at', ctx.exception.errors)

    def test_worklist_shows_the_readback_columns(self):
        order = self.make_order()
        record_result(order.pk, self.analyst, self.critical_payload())
        self.client.force_login(self.analyst)
        body = self.client.get(reverse('pasien:ancillary_worklist') + '?jenis=LAB').content.decode()
        self.assertIn('Pelaporan Kritis', body)
        self.assertIn('dr. Cynthia Maharani, Sp.JP', body)
        self.assertIn('Read-back', body)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True)
class CriticalSlaTest(PenunjangF4Fixture):
    """F4.5: SLA lapor ≤30 menit → PATUH / TERLAMBAT."""

    def sla_order(self, minutes):
        found = timezone.now() - timedelta(hours=2)
        return self.make_order(
            status='SELESAI', is_critical_value=True,
            critical_found_at=found,
            critical_reported_at=found + timedelta(minutes=minutes),
        )

    def test_twelve_minutes_is_patuh(self):
        order = self.sla_order(12)
        self.assertEqual(order.critical_sla_menit, 12)
        self.assertEqual(order.critical_sla_status, 'PATUH')

    def test_forty_one_minutes_is_terlambat(self):
        order = self.sla_order(41)
        self.assertEqual(order.critical_sla_menit, 41)
        self.assertEqual(order.critical_sla_status, 'TERLAMBAT')

    def test_thirty_minutes_is_still_patuh(self):
        self.assertEqual(self.sla_order(30).critical_sla_status, 'PATUH')

    def test_missing_timestamp_is_not_scored_as_zero(self):
        order = self.make_order(status='SELESAI', is_critical_value=True)
        self.assertIsNone(order.critical_sla_menit)
        self.assertIsNone(order.critical_sla_status)

    def test_non_critical_order_has_no_sla(self):
        order = self.make_order(status='SELESAI')
        self.assertIsNone(order.critical_sla_status)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True)
class PenunjangBillingTest(PenunjangF4Fixture):
    """F4.6 (ADR-4/ADR-10): tagihan otomatis dari order katalog."""

    def batch(self, item_ids, priority='RUTIN'):
        from pasien.services.penunjang_orders import order_batch
        entries = [{'item_id': pk, 'prioritas': priority, 'indication': 'Nyeri dada tipikal'}
                   for pk in item_ids]
        return order_batch(self.visit, None, self.doctor, {'items': entries})

    def test_two_orders_produce_two_charges(self):
        a = self.make_item('QA-F4-A', 'Darah Lengkap', tarif='85000')
        b = self.make_item('QA-F4-B', 'Troponin I', tarif='150000')
        result = self.batch([a.pk, b.pk])
        rows = BillingItem.objects.filter(kunjungan=self.visit, sumber='PENUNJANG')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(
            set(rows.values_list('harga_satuan', flat=True)),
            {Decimal('85000.00'), Decimal('150000.00')})
        for order in OrderPenunjang.objects.filter(pk__in=result['order_ids']):
            self.assertIsNotNone(order.billing_item_id)
            self.assertEqual(order.billing_item.sumber, 'PENUNJANG')

    def test_item_without_tariff_does_not_charge(self):
        item = self.make_item('QA-F4-NOTARIF', 'Panel Lipid')
        result = self.batch([item.pk])
        order = OrderPenunjang.objects.get(pk=result['order_ids'][0])
        self.assertIsNone(order.billing_item_id)
        self.assertFalse(BillingItem.objects.filter(kunjungan=self.visit).exists())

    def test_replaying_the_same_batch_does_not_duplicate(self):
        item = self.make_item('QA-F4-C', 'Darah Lengkap', tarif='85000')
        first = self.batch([item.pk])
        from pasien.services.penunjang_billing import charge_batch
        charge_batch(first['order_ids'], self.doctor)
        charge_batch(first['order_ids'], self.doctor)
        self.assertEqual(
            BillingItem.objects.filter(kunjungan=self.visit, sumber='PENUNJANG').count(), 1)

    def test_tindakan_sync_keeps_penunjang_charges(self):
        """Bukti F4.6 + F4.0: sapuan tindakan tidak menghapus tagihan penunjang."""
        from klinis.models import MasterIcd9
        from klinis.services.tarif import refresh_acuan, sync_billing, sync_billing_tindakan
        from pasien.models import TindakanAsesmen
        item = self.make_item('QA-F4-D', 'Darah Lengkap', tarif='85000')
        self.batch([item.pk])
        self.assertEqual(
            BillingItem.objects.filter(kunjungan=self.visit, sumber='PENUNJANG').count(), 1)

        sync_billing(self.visit, ['89.52'], user=self.doctor)
        self.assertEqual(
            BillingItem.objects.filter(kunjungan=self.visit, sumber='PENUNJANG').count(), 1)

        line = TindakanAsesmen.objects.create(
            kunjungan=self.visit, urutan=1, jenis='ICD9',
            icd9=MasterIcd9.objects.filter(kode='99.18').first(), kode='99.18',
            nama='Pemasangan Infus', sumber_data='MASTER')
        refresh_acuan(self.visit, [line])
        line.save()
        sync_billing_tindakan(self.visit, [line], user=self.doctor)
        self.assertEqual(
            BillingItem.objects.filter(kunjungan=self.visit, sumber='PENUNJANG').count(), 1)

    def test_released_order_removes_only_its_own_charge(self):
        from pasien.services.penunjang_billing import release_order
        a = self.make_item('QA-F4-E', 'Darah Lengkap', tarif='85000')
        b = self.make_item('QA-F4-F', 'Troponin I', tarif='150000')
        result = self.batch([a.pk, b.pk])
        order_a = OrderPenunjang.objects.get(pk=result['order_ids'][0])
        self.assertTrue(release_order(order_a))
        self.assertEqual(
            BillingItem.objects.filter(kunjungan=self.visit, sumber='PENUNJANG').count(), 1)

    def test_batal_order_status_is_available_for_cancellation(self):
        item = self.make_item('QA-F4-G', 'Darah Lengkap', tarif='85000')
        result = self.batch([item.pk])
        order = OrderPenunjang.objects.get(pk=result['order_ids'][0])
        self.assertTrue(order.can_transition_to('BATAL'))


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True)
class WorklistUnitIsolationTest(PenunjangF4Fixture):
    """F4.8: unit LAB melihat order POLI-JANTUNG; unit lain tidak."""

    def test_lab_unit_sees_rajal_jantung_order(self):
        self.make_order(nama_pemeriksaan='Darah Lengkap POLI')
        self.client.force_login(self.analyst)
        body = self.client.get(reverse('pasien:ancillary_worklist') + '?jenis=LAB').content.decode()
        self.assertIn('Darah Lengkap POLI', body)

    def test_other_unit_does_not_see_it(self):
        other = UnitKerja.objects.create(code='QA-OTHER-UNIT', name='Unit Lain', level=3)
        outsider = self.account('f4_outsider', 'ANALIS_LAB', other, 'STAF_NAKES')
        self.make_order(nama_pemeriksaan='Darah Lengkap POLI')
        self.client.force_login(outsider)
        body = self.client.get(reverse('pasien:ancillary_worklist') + '?jenis=LAB').content.decode()
        self.assertNotIn('Darah Lengkap POLI', body)
