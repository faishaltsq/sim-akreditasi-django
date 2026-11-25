"""F8 — dasbor antrean: deep-link langkah, indikator keselamatan, panel
longitudinal, dan matriks RBAC final 6 peran × 10 langkah.

Setiap tes menyatakan perilaku yang dapat diamati: ``href`` pada HTML yang
dirender, nilai pada konteks view, status HTTP, atau isi panel. Aturan
"asesmen terisi" (F8.2) diuji dua arah **dan** sebagai fungsi murni, supaya
tidak ada satu pun keputusan yang hanya hidup di template.

Tautan diuji lewat klien uji Django, yang tidak menjalankan JavaScript: tautan
yang hanya bekerja lewat handler JS akan gagal di sini.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from pasien.expansion_models import AlergiPasienTerstruktur
from pasien.models import (
    IgdAssessmentWorkflow, KunjunganPasien, OrderPenunjang,
    ResepDetail, ResepElektronik,
)
from pasien.services.igd_assessment_workflow import save_step
from pasien.services.poli_completeness import (
    EARLY_STEP_NUMBERS, SOAP_CLINICAL_STEP, SOAP_ENTRY_STEP,
    poli_completeness, step_minimally_filled,
)
from pasien.services.poli_rbac import (
    DPJP, FARMASI, FISIOTERAPI, GIZI, KASIR, PERAWAT,
    authorize_step, require_dpjp,
)

from .tests_poli_workflow import FULL_RAJAL_DRAFT, TEST_STORAGES, PoliFixture

STEP_PAYLOAD = {int(k): v for k, v in FULL_RAJAL_DRAFT.items()}
ALL_STEPS = tuple(range(1, 11))

class _DashboardFixture(PoliFixture):
    """Login perawat poli + helper render/fill/href."""

    def setUp(self):
        self.client.force_login(self.nurse)

    def render(self):
        response = self.client.get(reverse('pasien:rajal_dashboard'))
        self.assertEqual(response.status_code, 200)
        return response, response.content.decode()

    def fill_steps(self, steps, actor=None):
        version = 0
        for step in steps:
            version = save_step(
                self.visit.pk, actor or self.nurse, step, STEP_PAYLOAD[step],
                version, service_line='RAJAL_JANTUNG',
            ).version
        return version

    def href_for(self, html, label):
        """Ambil ``href`` dari tautan berlabel tertentu pada baris antrean."""
        index = html.find(f'>{label}')
        self.assertNotEqual(index, -1, f'tautan {label!r} tidak ditemukan')
        start = html.rfind('href="', 0, index)
        self.assertNotEqual(start, -1, f'tautan {label!r} tidak punya href')
        start += len('href="')
        return html[start:html.find('"', start)]

    def step_link(self, visit, step):
        return reverse('pasien:poli_workflow', args=[visit.pk]) + f'?step={step}'

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class DeepLinkTest(_DashboardFixture):
    """F8.1 — lima aksi dasbor menjadi tautan langkah yang benar."""

    def test_registration_penunjang_disposisi_links_point_at_their_steps(self):
        _, html = self.render()
        self.assertEqual(self.href_for(html, 'Registrasi'), self.step_link(self.visit, 1))
        self.assertEqual(self.href_for(html, 'Penunjang'), self.step_link(self.visit, 7))
        self.assertEqual(self.href_for(html, 'Disposisi'), self.step_link(self.visit, 10))

    def test_soap_link_opens_step_2_when_early_assessment_is_empty(self):
        _, html = self.render()
        self.assertEqual(self.href_for(html, 'SOAP'), self.step_link(self.visit, 2))

    def test_soap_link_opens_step_8_when_early_assessment_is_filled(self):
        self.fill_steps(range(1, 7))
        _, html = self.render()
        self.assertEqual(self.href_for(html, 'SOAP'), self.step_link(self.visit, 8))

    def test_every_deep_link_resolves_without_javascript(self):
        """Klien uji tidak menjalankan JS: 200 berarti tautan benar-benar jalan."""
        self.fill_steps(range(1, 7))
        _, html = self.render()
        for label, expected in (
            ('Registrasi', 1), ('SOAP', 8), ('Penunjang', 7), ('Disposisi', 10),
        ):
            href = self.href_for(html, label)
            response = self.client.get(href)
            self.assertEqual(response.status_code, 200, f'{label}: {href}')
            self.assertEqual(response.context['step'], expected, f'{label}: {href}')

    def test_primary_action_links_are_anchors_not_modal_toggles(self):
        _, html = self.render()
        body = html[html.find('<tbody>'):]
        row_start = body.find('<td class="text-center">')
        self.assertNotEqual(row_start, -1)
        # Sel aksi = dari <td> sampai menu "lebih"; menu itu sendiri dipotong.
        cell = body[row_start:body.find('MORE DROPDOWN', row_start)]
        for step in (1, 7, 10):
            self.assertIn(f'?step={step}', cell)
        self.assertNotIn('data-bs-toggle="modal"', cell)
        self.assertNotIn('<button', cell)

    def test_detail_link_opens_longitudinal_panel(self):
        _, html = self.render()
        expected = reverse('pasien:rajal_longitudinal', args=[self.visit.pk])
        self.assertIn(f'href="{expected}"', html)
        response = self.client.get(expected)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pratinjau Longitudinal RME')

    def test_deep_links_are_absent_when_rollout_flag_is_off(self):
        with override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=False):
            _, html = self.render()
        self.assertNotIn('?step=7', html)
        # Jalur lama tetap utuh: tombol modal SOAP masih ada.
        self.assertIn('data-bs-target="#modalSoap', html)

    def test_deep_links_are_absent_for_non_jantung_visit(self):
        """Baris unit lain tidak mendapat tautan asesmen POLI-JANTUNG."""
        admin_nurse = User.objects.create_user('admin_nurse_f8', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=admin_nurse,
            defaults={'role': 'ADMIN_RS', 'profesi': 'PERAWAT', 'unit_kerja': self.unit},
        )
        other = KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='QA-POLI-PD-F8',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            unit_kerja=self.other_unit, poliklinik='POLI-PD',
        )
        self.client.force_login(admin_nurse)
        response, html = self.render()
        rows = {row.pk: row for row in response.context['pasien_rajal_list']}
        self.assertIn(other.pk, rows)
        self.assertTrue(rows[self.visit.pk].poli_deep_link)
        self.assertFalse(rows[other.pk].poli_deep_link)
        self.assertNotIn(f'/kunjungan/{other.pk}/asesmen-poli/', html)

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class CompletenessRuleTest(_DashboardFixture):
    """F8.2 — aturan "asesmen terisi" diuji dua arah, bukan disimpulkan template."""

    def test_empty_assessment_targets_step_2(self):
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())
        self.assertEqual(poli_completeness(None).soap_step, SOAP_ENTRY_STEP)

    def test_filled_assessment_targets_step_8(self):
        self.fill_steps(range(1, 7))
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        self.assertEqual(poli_completeness(workflow).soap_step, SOAP_CLINICAL_STEP)

    def test_partial_fill_still_targets_step_2(self):
        self.fill_steps(range(1, 6))
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        result = poli_completeness(workflow)
        self.assertEqual(result.missing_steps, (6,))
        self.assertEqual(result.soap_step, SOAP_ENTRY_STEP)

    def test_one_value_counts_as_minimally_filled(self):
        """Definisi "minimal terisi" = satu nilai tidak kosong, bukan semua field."""
        self.assertTrue(step_minimally_filled({'keluhan_utama': 'Nyeri dada'}))
        for empty in (None, '', [], {}):
            self.assertFalse(step_minimally_filled({'keluhan_utama': empty}))
        self.assertFalse(step_minimally_filled(None))

    def test_step_exemption_counts_as_filled(self):
        self.fill_steps(range(1, 6))
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        workflow.exemptions = {'step_6': 'Tidak dilakukan pada episode ini.'}
        workflow.save(update_fields=['exemptions'])
        self.assertEqual(poli_completeness(workflow).soap_step, SOAP_CLINICAL_STEP)

    def test_rule_is_the_same_predicate_used_by_finalization(self):
        from pasien.services.igd_finalization import missing_rajal_sections

        self.fill_steps(range(1, 6))
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        early_missing = {f'step_{number}' for number in EARLY_STEP_NUMBERS}
        self.assertEqual(
            {f'step_{number}' for number in poli_completeness(workflow).missing_steps},
            {name for name in missing_rajal_sections(workflow) if name in early_missing},
        )

    def test_late_steps_do_not_change_the_soap_target(self):
        """Langkah 7–10 bukan bagian "asesmen awal"; mengisinya tidak memindah target."""
        self.fill_steps([7], actor=self.dpjp_user)
        workflow = IgdAssessmentWorkflow.objects.get(kunjungan=self.visit)
        self.assertEqual(poli_completeness(workflow).soap_step, SOAP_ENTRY_STEP)

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class SafetyIndicatorTest(_DashboardFixture):
    """F8.3 — kolom identitas melekat + ikon alergi dan nilai kritis."""

    def test_identity_column_is_sticky(self):
        _, html = self.render()
        self.assertIn('class="poli-ident-col', html)
        self.assertIn('position: sticky; left: 0', html)

    def test_allergy_badge_from_structured_allergy(self):
        AlergiPasienTerstruktur.objects.create(
            pasien=self.patient, ingredient_code='AMOXICILLIN',
            reaction='Anafilaksis', recorded_by=self.nurse, source='uji',
        )
        _, html = self.render()
        self.assertIn('data-safety-badge="allergy"', html)

    def test_allergy_badge_from_legacy_text_column(self):
        self.patient.alergi_obat = 'Kontras iodin'
        self.patient.save(update_fields=['alergi_obat'])
        _, html = self.render()
        self.assertIn('data-safety-badge="allergy"', html)

    def test_no_allergy_badge_without_any_allergy(self):
        _, html = self.render()
        self.assertNotIn('data-safety-badge="allergy"', html)

    def test_unread_critical_badge_when_readback_is_missing(self):
        OrderPenunjang.objects.create(
            kunjungan=self.visit, jenis='LAB', nama_pemeriksaan='Troponin I',
            is_critical_value=True, critical_value_catatan='Troponin 12 ng/mL',
        )
        _, html = self.render()
        self.assertIn('data-safety-badge="critical-unread"', html)

    def test_critical_badge_disappears_after_readback(self):
        OrderPenunjang.objects.create(
            kunjungan=self.visit, jenis='LAB', nama_pemeriksaan='Troponin I',
            is_critical_value=True, critical_readback_at=timezone.now(),
            critical_readback_by=self.dpjp_user,
        )
        _, html = self.render()
        self.assertNotIn('data-safety-badge="critical-unread"', html)

    def test_non_critical_order_does_not_raise_the_badge(self):
        OrderPenunjang.objects.create(
            kunjungan=self.visit, jenis='LAB', nama_pemeriksaan='Darah Lengkap',
        )
        _, html = self.render()
        self.assertNotIn('data-safety-badge="critical-unread"', html)

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class LongitudinalPanelTest(_DashboardFixture):
    """F8.4 — panel pratinjau membaca data yang sudah ada, tanpa entri karangan."""

    def make_previous_visit(self, no, days_ago, ttv):
        return KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan=no, jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now() - timedelta(days=days_ago),
            unit_kerja=self.unit, poliklinik='POLI-JANTUNG',
            ttv_sistole=ttv[0], ttv_diastole=ttv[1],
            ttv_nadi=ttv[2], ttv_spo2=ttv[3],
        )

    def panel_url(self, visit=None):
        return reverse('pasien:rajal_longitudinal', args=[(visit or self.visit).pk])

    def test_two_visits_produce_two_ttv_points(self):
        self.make_previous_visit('QA-F8-LAMA-01', 30, (150, 95, 96, 97))
        self.fill_steps([4])
        response = self.client.get(self.panel_url())
        self.assertEqual(response.status_code, 200)
        points = response.context['panel']['ttv_points']
        self.assertEqual(len(points), 2)
        # Tren urut lama → baru, dan TTV episode ini dibaca dari draft langkah 4.
        self.assertEqual(points[0]['values']['ttv_sistole'], 150)
        self.assertEqual(points[-1]['values']['ttv_sistole'], STEP_PAYLOAD[4]['ttv_sistole'])

    def test_lvef_points_only_include_orders_with_a_value(self):
        OrderPenunjang.objects.create(
            kunjungan=self.visit, jenis='RADIOLOGI',
            nama_pemeriksaan='Ekokardiografi', lvef=35,
        )
        OrderPenunjang.objects.create(
            kunjungan=self.visit, jenis='RADIOLOGI',
            nama_pemeriksaan='Ekokardiografi ulang',
        )
        response = self.client.get(self.panel_url())
        points = response.context['panel']['lvef_points']
        self.assertEqual([point['lvef'] for point in points], [35])
        self.assertContains(response, 'Ekokardiografi')

    def test_active_medications_come_from_last_completed_prescription(self):
        resep = ResepElektronik.objects.create(
            no_resep='RX-F8-001', kunjungan=self.visit, status='SELESAI',
            jenis_resep='RAWAT_JALAN', dokter_peresep=self.dpjp_user,
        )
        ResepDetail.objects.create(
            resep=resep, nama_obat='Bisoprolol 5 mg', dosis='5 mg',
            aturan_pakai='1x1 pagi', jumlah=30,
        )
        response = self.client.get(self.panel_url())
        names = [row['nama_obat'] for row in response.context['panel']['active_medications']]
        self.assertEqual(names, ['Bisoprolol 5 mg'])
        self.assertContains(response, 'Bisoprolol 5 mg')

    def test_unfinished_prescription_is_not_reported_as_active(self):
        resep = ResepElektronik.objects.create(
            no_resep='RX-F8-002', kunjungan=self.visit, status='DIKIRIM',
            jenis_resep='RAWAT_JALAN',
        )
        ResepDetail.objects.create(
            resep=resep, nama_obat='Furosemide 40 mg', dosis='40 mg',
            aturan_pakai='1x1 pagi', jumlah=10,
        )
        response = self.client.get(self.panel_url())
        self.assertEqual(response.context['panel']['active_medications'], [])

    def test_empty_gdmt_list_states_the_reason_instead_of_faking_rows(self):
        response = self.client.get(self.panel_url())
        panel = response.context['panel']
        self.assertEqual(panel['active_medications'], [])
        self.assertEqual(panel['prescribable_gdmt_products'], 0)
        self.assertContains(response, 'belum punya satu pun produk yang dapat diresepkan')

    def test_history_never_leaves_the_unit_scope(self):
        KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='QA-F8-LUAR-01', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now() - timedelta(days=5),
            unit_kerja=self.other_unit, poliklinik='POLI-PD',
        )
        response = self.client.get(self.panel_url())
        nos = {row['kunjungan'].no_kunjungan for row in response.context['panel']['history']}
        self.assertNotIn('QA-F8-LUAR-01', nos)
        self.assertIn(self.visit.no_kunjungan, nos)

    def test_panel_requires_the_rajal_module(self):
        outsider = User.objects.create_user('tanpa_rajal_f8', password='fixture-only')
        # Tanpa unit kerja, modul yang diberikan hanya master_pasien + riwayat.
        UserProfile.objects.update_or_create(
            user=outsider,
            defaults={'role': 'STAF_NAKES', 'profesi': 'PERAWAT', 'unit_kerja': None},
        )
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.panel_url()).status_code, 403)

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class RbacFinalMatrixTest(PoliFixture):
    """F8.5 — matriks 6 peran × 10 langkah ditegakkan tes, bukan dokumen.

    Tabel harapan ditulis ulang dari matriks §4 + ADR-11, bukan dibaca dari
    ``FILL_ROLES``: perubahan kode tanpa perubahan keputusan harus membuat tes
    merah. Sel "baca" mengikuti keputusan yang sudah diuji F1.10
    (``READ_ROLES`` memberi baca ke seluruh peran matriks; sel "tidak diatur"
    pada sumber dibaca sebagai "tidak dirinci", bukan larangan) — dinyatakan di
    sini supaya perbedaannya tidak tersembunyi.
    """

    #: peran → (langkah yang boleh diisi, langkah yang boleh diverifikasi).
    EXPECTED = {
        PERAWAT:     ({1, 2, 3, 4, 5, 6, 7, 9}, set()),
        DPJP:        ({1, 2, 3, 4, 5, 6, 7, 8, 9, 10}, set(ALL_STEPS)),
        FARMASI:     ({9}, set()),
        GIZI:        ({5, 9}, set()),
        FISIOTERAPI: ({9}, set()),
        KASIR:       (set(), set()),
    }

    def setUp(self):
        self.accounts = {
            PERAWAT: self.nurse,
            DPJP: self.dpjp_user,
            FARMASI: self.pharmacist,
            GIZI: self.nutritionist,
            FISIOTERAPI: self.physio,
            KASIR: self.records,
        }
        self.assertEqual(set(self.accounts), set(self.EXPECTED))

    def test_six_roles_by_ten_steps_fill_and_verify(self):
        checked = 0
        for role, (fill_steps, verify_steps) in self.EXPECTED.items():
            user = self.accounts[role]
            for step in ALL_STEPS:
                with self.subTest(role=role, step=step, action='fill'):
                    if step in fill_steps:
                        self.assertEqual(
                            authorize_step(user, self.visit, step, 'fill'), role)
                    else:
                        with self.assertRaises(PermissionDenied):
                            authorize_step(user, self.visit, step, 'fill')
                    checked += 1
                with self.subTest(role=role, step=step, action='verify'):
                    if step in verify_steps:
                        self.assertEqual(
                            authorize_step(user, self.visit, step, 'verify'), role)
                    else:
                        with self.assertRaises(PermissionDenied):
                            authorize_step(user, self.visit, step, 'verify')
                    checked += 1
        self.assertEqual(checked, 6 * 10 * 2)

    def test_every_role_may_read_all_ten_steps(self):
        for role, user in self.accounts.items():
            for step in ALL_STEPS:
                with self.subTest(role=role, step=step):
                    self.assertEqual(
                        authorize_step(user, self.visit, step, 'read'), role)

    def test_dpjp_only_finalization_holds_for_all_six_roles(self):
        for role, user in self.accounts.items():
            with self.subTest(role=role):
                if role == DPJP:
                    self.assertIsNotNone(require_dpjp(user, self.visit))
                else:
                    with self.assertRaises(PermissionDenied):
                        require_dpjp(user, self.visit)

    def test_matrix_matches_the_declared_tables(self):
        from pasien.services.poli_rbac import FILL_ROLES, READ_ROLES, VERIFY_ROLES

        for role, (fill_steps, verify_steps) in self.EXPECTED.items():
            self.assertEqual(
                {step for step, roles in FILL_ROLES.items() if role in roles},
                fill_steps, f'isi {role}')
            self.assertEqual(
                {step for step, roles in VERIFY_ROLES.items() if role in roles},
                verify_steps, f'verifikasi {role}')
            self.assertEqual(
                {step for step, roles in READ_ROLES.items() if role in roles},
                set(ALL_STEPS), f'baca {role}')
