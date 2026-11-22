"""Tests for the cross-rumpun Pola Ketenagaan gap analysis.

The gap table must read only approved (immutable) formasi results, so a
printed staffing report never changes colour after assumptions are revised.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    HasilFormasi,
    HcGrant,
    MasterProfesiPegawai,
    Pegawai,
    PenempatanPegawai,
    RencanaFormasi,
)
from sdm.services.pola_ketenagaan import (
    hitung_gap_ketenagaan,
    hitung_ringkasan_pola,
    klasifikasi_gap,
    ringkasan_per_rumpun,
)


class KlasifikasiGapTests(TestCase):
    def test_surplus_above_zero(self):
        self.assertEqual(klasifikasi_gap(Decimal('2.00')), ('Surplus', 'info'))

    def test_exact_match_is_sesuai_standar(self):
        self.assertEqual(
            klasifikasi_gap(Decimal('0.00')), ('Sesuai Standar', 'success')
        )

    def test_minus_one_is_still_ringan(self):
        self.assertEqual(
            klasifikasi_gap(Decimal('-1.00')), ('Defisit Ringan', 'warning')
        )

    def test_beyond_minus_one_is_kritis(self):
        self.assertEqual(
            klasifikasi_gap(Decimal('-1.01')), ('Defisit Kritis', 'danger')
        )

    def test_none_is_treated_as_zero(self):
        self.assertEqual(
            klasifikasi_gap(None), ('Sesuai Standar', 'success')
        )


class PolaKetenagaanServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_plan_hc_workforce = True
        config.can_export_hc = True
        config.save()

        cls.unit = UnitKerja.objects.create(name='Poli Dalam', code='T-PD')
        cls.profesi = MasterProfesiPegawai.objects.create(
            code='T-SPPD', nama='Dokter Spesialis Penyakit Dalam', keluarga='MEDIS',
        )
        for i in range(2):
            pegawai = Pegawai.objects.create(
                nama_lengkap=f'dr. Pola {i}', kategori='PPA',
                profesi='Dokter Spesialis Penyakit Dalam',
                profesi_master=cls.profesi,
            )
            # Placement is what puts an employee inside a unit's visibility
            # scope; without it visible_employees() correctly returns nothing.
            PenempatanPegawai.objects.create(
                pegawai=pegawai, unit_kerja=cls.unit,
                tanggal_mulai=date(2026, 1, 1), alokasi_fte='1.00',
            )
        User = get_user_model()
        cls.user = User.objects.create_user(username='pola-viewer', password='x')
        UserProfile.objects.create(user=cls.user, role='ADMIN_RS', unit_kerja=cls.unit)
        HcGrant.objects.create(
            user=cls.user, capability='can_view_hc', unit_kerja=cls.unit,
        )
        HcGrant.objects.create(
            user=cls.user, capability='can_plan_hc_workforce', unit_kerja=cls.unit,
        )
        HcGrant.objects.create(
            user=cls.user, capability='can_export_hc', unit_kerja=cls.unit,
        )

    def _plan(self, *, status='APPROVED', with_result=True, actual=Decimal('2.0000')):
        """Rencana + hasil formasi (standar 5 FTE).

        ``HasilFormasi.gap_fte`` = required - actual, jadi defisit 3 FTE berarti
        nilai repositori +3.0 dan nilai tampilan -3.0.
        """
        plan = RencanaFormasi.objects.create(
            unit_kerja=self.unit,
            profesi='Dokter Spesialis Penyakit Dalam',
            periode_mulai=date(2026, 1, 1),
            periode_selesai=date(2026, 12, 31),
            effective_minutes_per_employee=Decimal('75000.00'),
            status=status,
        )
        if with_result:
            required = Decimal('5.0000')
            HasilFormasi.objects.create(
                rencana=plan,
                calculation_version=plan.calculation_version,
                required_fte=required,
                required_headcount=5,
                actual_fte=actual,
                gap_fte=required - actual,
                sufficiency_pct=Decimal('40.00'),
                inputs_digest='x' * 64,
                status_risiko='DEFISIT_KRITIS',
            )
        return plan

    def test_approved_plan_yields_a_row(self):
        self._plan()
        baris = hitung_gap_ketenagaan(self.user)
        self.assertEqual(len(baris), 1)
        self.assertEqual(baris[0]['rumpun'], 'MEDIS')
        self.assertEqual(baris[0]['status'], 'Defisit Kritis')
        self.assertEqual(baris[0]['unit_kode'], 'T-PD')

    def test_repository_gap_sign_is_converted_for_display(self):
        """required - actual = +3 berarti kurang 3 FTE, ditampilkan sebagai -3."""
        self._plan()
        baris = hitung_gap_ketenagaan(self.user)[0]
        self.assertEqual(baris['gap_repo_fte'], Decimal('3.0000'))
        self.assertEqual(baris['gap_fte'], Decimal('-3.0000'))
        self.assertEqual(baris['status'], 'Defisit Kritis')

    def test_surplus_plan_is_labelled_surplus(self):
        """Actual melebihi standar harus terbaca Surplus, bukan defisit."""
        self._plan(actual=Decimal('7.0000'))
        baris = hitung_gap_ketenagaan(self.user)[0]
        self.assertEqual(baris['gap_fte'], Decimal('2.0000'))
        self.assertEqual(baris['status'], 'Surplus')

    def test_draft_plan_is_excluded(self):
        self._plan(status='DRAFT')
        self.assertEqual(hitung_gap_ketenagaan(self.user), [])

    def test_approved_plan_without_result_is_excluded(self):
        self._plan(with_result=False)
        self.assertEqual(hitung_gap_ketenagaan(self.user), [])

    def test_ringkasan_counts_critical_units_and_totals(self):
        self._plan()
        ringkasan = hitung_ringkasan_pola(self.user)
        self.assertTrue(ringkasan['pola_ada_data'])
        self.assertEqual(ringkasan['pola_jumlah_kritis'], 1)
        self.assertEqual(ringkasan['pola_total_standar'], Decimal('5.0000'))
        self.assertEqual(ringkasan['pola_total_eksisting'], Decimal('2.0000'))

    def test_distribution_reports_every_rumpun_bucket(self):
        distribusi = ringkasan_per_rumpun(self.user)
        kode = [d['kode'] for d in distribusi]
        self.assertEqual(
            kode, ['MEDIS', 'KEPERAWATAN_KEBIDANAN', 'NAKES_LAIN', 'NON_KLINIS']
        )
        medis = next(d for d in distribusi if d['kode'] == 'MEDIS')
        self.assertEqual(medis['jumlah'], 2)
        self.assertEqual(medis['persen'], 100.0)

    def test_dashboard_renders_gap_section(self):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_plan_hc_workforce = True
        config.save()
        self._plan()
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Peta Pemenuhan Pola Ketenagaan')
        self.assertContains(response, 'Defisit Kritis')

    # ── eskalasi ke Risk Register ──────────────────────────────────────────

    def test_eskalasi_creates_risk_register_entry(self):
        from akreditasi.models import RisikoUnit
        from sdm.services.eskalasi_risiko import eskalasi_gap_ke_risiko

        self._plan()
        baris = hitung_gap_ketenagaan(self.user)[0]
        risiko, created = eskalasi_gap_ke_risiko(baris, user=self.user)

        self.assertTrue(created)
        self.assertEqual(RisikoUnit.objects.count(), 1)
        self.assertEqual(risiko.unit, self.unit)
        self.assertEqual(risiko.kategori_risiko, 'OPERASIONAL')
        self.assertIn('Defisit pola ketenagaan', risiko.jenis_risiko)
        # Defisit 3 FTE -> dampak 5, probabilitas 4
        self.assertEqual(risiko.dampak, 5)
        self.assertEqual(risiko.probabilitas, 4)

    def test_eskalasi_is_idempotent(self):
        from akreditasi.models import RisikoUnit
        from sdm.services.eskalasi_risiko import eskalasi_gap_ke_risiko

        self._plan()
        baris = hitung_gap_ketenagaan(self.user)[0]
        eskalasi_gap_ke_risiko(baris, user=self.user)
        _, created_again = eskalasi_gap_ke_risiko(baris, user=self.user)

        self.assertFalse(created_again)
        self.assertEqual(RisikoUnit.objects.count(), 1)

    def test_eskalasi_rejects_surplus_row(self):
        from django.core.exceptions import ValidationError
        from sdm.services.eskalasi_risiko import eskalasi_gap_ke_risiko

        plan = self._plan()
        baris = {
            'formasi_id': plan.pk, 'profesi': plan.profesi,
            'standar_fte': Decimal('1.0000'), 'eksisting_fte': Decimal('5.0000'),
            'gap_fte': Decimal('4.0000'), 'sufficiency_pct': Decimal('500.00'),
            'unit_kode': 'T-PD',
        }
        with self.assertRaises(ValidationError):
            eskalasi_gap_ke_risiko(baris, user=self.user)

    def test_eskalasi_view_posts_and_redirects(self):
        from akreditasi.models import RisikoUnit

        self._plan()
        plan = RencanaFormasi.objects.get()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('sdm:pola_ketenagaan_eskalasi', args=[plan.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RisikoUnit.objects.count(), 1)

    # ── dokumen SK Pola Ketenagaan ─────────────────────────────────────────

    def test_sk_pdf_returns_pdf_bytes(self):
        from sdm.services.pola_ketenagaan import render_sk_pola_pdf

        self._plan()
        pdf = render_sk_pola_pdf(self.user)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 1000)

    def test_sk_pdf_view_sets_content_type_and_disposition(self):
        self._plan()
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:pola_ketenagaan_sk_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))
