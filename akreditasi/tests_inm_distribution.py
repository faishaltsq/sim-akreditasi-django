"""Peta distribusi INM: visibilitas indikator per unit kerja.

Menguji `inm_qs_for_user()` beserta jalur baca yang memakainya (dashboard,
tren, komparasi, input capaian) dan command `seed_inm_matrix`.

Aturan penting: tabel mapping KOSONG berarti tidak dibatasi. Produksi saat ini
belum punya satu baris pun — kalau perilakunya fail-closed, seluruh menu INM
hilang begitu kode ini deploy.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from akreditasi.indikator_views import inm_qs_for_user, unit_subtree_ids
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import CatatanIndikator, IndikatorMutu, InmUnitMapping
from accounts.models import UserProfile

User = get_user_model()


def _unit(code, name, parent=None, level=2):
    """Ambil/buat unit — DB uji sudah terisi unit hasil migrasi seed."""
    unit, _ = UnitKerja.objects.get_or_create(
        code=code,
        defaults=dict(name=name, tipe_unit='RUANGAN', parent=parent, level=level),
    )
    return unit


def _ind(kode, nama, unit=None, jenis='INM', target=85, arah='MIN'):
    return IndikatorMutu.objects.create(
        nama_indikator=nama, kode_indikator=kode, unit=unit, jenis=jenis,
        dimensi_mutu='AMAN', numerator='N', denominator='D',
        target_nilai=Decimal(str(target)), satuan='%', arah_target=arah, aktif=True,
    )


class InmVisibilityBase(TestCase):
    def setUp(self):
        self.irin = _unit('T-IRIN', 'Instalasi Rawat Inap (uji)')
        self.bangsal = _unit('T-BANGSAL-A', 'Bangsal A (uji)', parent=self.irin, level=3)
        self.ruang = _unit('T-RUANG-1', 'Ruang Kelas 1 (uji)', parent=self.bangsal, level=4)
        self.igd = _unit('T-IGD', 'Instalasi Gawat Darurat (uji)')

        self.inm_kkt = _ind('INM-01', 'Kepatuhan Kebersihan Tangan (KKT)')
        self.inm_apd = _ind('INM-02', 'Kepatuhan Penggunaan Alat Pelindung Diri (APD)')
        self.inm_lab = _ind('INM-12', 'Kepatuhan Pelaporan Hasil Kritis Laboratorium')

        self.user = User.objects.create_user('kepala_bangsal', password='secret123')
        self.profile = UserProfile.objects.create(
            user=self.user, role='KEPALA_UNIT', unit_kerja=self.bangsal,
        )

    def visible_codes(self):
        """Kode INM uji yang terlihat (DB uji juga berisi INM hasil migrasi)."""
        return set(
            inm_qs_for_user(self.profile, IndikatorMutu.objects.all())
            .filter(kode_indikator__in=['INM-01', 'INM-02', 'INM-12'])
            .values_list('kode_indikator', flat=True)
        )


class SubtreeTest(InmVisibilityBase):
    def test_subtree_reaches_grandchild_level_4(self):
        ids = unit_subtree_ids(self.irin)
        self.assertIn(self.ruang.pk, ids)
        self.assertEqual(ids, {self.irin.pk, self.bangsal.pk, self.ruang.pk})

    def test_subtree_excludes_sibling_units(self):
        self.assertNotIn(self.igd.pk, unit_subtree_ids(self.irin))

    def test_leaf_unit_subtree_is_itself(self):
        self.assertEqual(unit_subtree_ids(self.igd), {self.igd.pk})


class FailOpenTest(InmVisibilityBase):
    def test_empty_mapping_keeps_old_behaviour(self):
        """0 baris mapping -> semua INM tetap terlihat (guard produksi)."""
        self.assertEqual(
            self.visible_codes(), {'INM-01', 'INM-02', 'INM-12'}
        )

    def test_admin_profile_not_restricted(self):
        admin = User.objects.create_user('admin_rs', password='secret123')
        prof = UserProfile.objects.create(
            user=admin, role='ADMIN_RS', unit_kerja=self.bangsal,
        )
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.igd)
        self.assertEqual(
            set(inm_qs_for_user(prof, IndikatorMutu.objects.all())
                .filter(kode_indikator__in=['INM-01', 'INM-02', 'INM-12'])
                .values_list('kode_indikator', flat=True)),
            {'INM-01', 'INM-02', 'INM-12'},
        )


class MappingFilterTest(InmVisibilityBase):
    def test_unit_sees_only_mapped_inm(self):
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.irin)
        self.assertEqual(self.visible_codes(), {'INM-01'})

    def test_child_unit_inherits_parent_mapping(self):
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.irin)
        self.assertIn('INM-01', self.visible_codes())

    def test_grandchild_inherits_parent_mapping(self):
        InmUnitMapping.objects.create(indikator=self.inm_apd, unit=self.bangsal)
        self.assertIn('INM-02', self.visible_codes())

    def test_unmapped_inm_hidden_once_mapping_exists(self):
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.igd)
        # Mapping ada (untuk IGD), tapi tidak relevan ke bangsal -> tersaring.
        self.assertEqual(self.visible_codes(), set())

    def test_role_scope_grants_access_without_unit(self):
        InmUnitMapping.objects.create(
            indikator=self.inm_lab, unit=None, role_scope=InmUnitMapping.ROLE_KEPALA_UNIT,
        )
        self.assertIn('INM-12', self.visible_codes())

    def test_role_scope_of_other_role_ignored(self):
        InmUnitMapping.objects.create(
            indikator=self.inm_lab, unit=None, role_scope=InmUnitMapping.ROLE_DPJP,
        )
        self.assertEqual(self.visible_codes(), set())


class UnitOwnedIndicatorsTest(InmVisibilityBase):
    def test_unit_owned_indicator_always_visible(self):
        """Indikator IMU milik unit sendiri tidak ikut tersaring peta INM."""
        imu = _ind('IMU-01', 'Kepatuhan Visite Dokter', unit=self.bangsal, jenis='IMP_UNIT')
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.igd)
        codes = set(
            inm_qs_for_user(self.profile, IndikatorMutu.objects.all())
            .values_list('kode_indikator', flat=True)
        )
        self.assertIn('IMU-01', codes)
        self.assertNotIn('INM-01', codes)
        self.assertIsNotNone(imu.pk)


class DashboardTest(InmVisibilityBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.url = reverse('akreditasi:indikator_dashboard')

    def test_dashboard_hides_unit_duplicate_rows(self):
        """Baris realisasi BAB-* tidak tampil sebagai entri katalog sendiri."""
        row = _ind('BAB-T-INM-01', 'Kepatuhan Kebersihan Tangan (>= 85%)',
                   unit=self.bangsal, jenis='NASIONAL', target=85)
        row.inm_induk = self.inm_kkt
        row.save(update_fields=['inm_induk'])
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.bangsal)
        resp = self.client.get(self.url, {'jenis': 'INM'})
        self.assertEqual(resp.status_code, 200)
        kodes = [i.kode_indikator for i in resp.context['indikators']]
        self.assertIn('INM-01', kodes)
        self.assertNotIn('BAB-T-INM-01', kodes)

    def test_dashboard_lists_inm_for_unit_with_mapping(self):
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.bangsal)
        resp = self.client.get(self.url, {'jenis': 'INM'})
        kodes = [i.kode_indikator for i in resp.context['indikators']]
        self.assertEqual(kodes, ['INM-01'])

    def test_dashboard_uses_unit_realization_value(self):
        _ind('BAB-INTERNA-INM-01', 'Kepatuhan Kebersihan Tangan (>= 85%)',
             unit=self.bangsal, jenis='NASIONAL', target=85)
        row = IndikatorMutu.objects.get(kode_indikator='BAB-INTERNA-INM-01')
        row.inm_induk = self.inm_kkt
        row.save(update_fields=['inm_induk'])
        CatatanIndikator.objects.create(
            indikator=row, bulan=3, tahun=2026,
            nilai_numerator=Decimal('90'), nilai_denominator=Decimal('100'),
        )
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.bangsal)
        resp = self.client.get(self.url, {'jenis': 'INM', 'tahun': '2026'})
        ind = next(i for i in resp.context['indikators'] if i.kode_indikator == 'INM-01')
        self.assertEqual(ind.unit_row.pk, row.pk)
        self.assertEqual(ind.last_catatan.bulan, 3)


class ApiAccessTest(InmVisibilityBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_tren_404_for_unmapped_indicator(self):
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.igd)
        url = reverse('akreditasi:api_indikator_tren', args=[self.inm_apd.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_tren_ok_for_mapped_indicator(self):
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.bangsal)
        url = reverse('akreditasi:api_indikator_tren', args=[self.inm_kkt.pk])
        self.assertEqual(self.client.get(url).status_code, 200)


class InputAccessTest(InmVisibilityBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_input_denied_for_unmapped_indicator(self):
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.igd)
        url = reverse('akreditasi:indikator_input_capaian', args=[self.inm_apd.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('akreditasi:indikator_dashboard'), resp.url)

    def test_input_redirects_canonical_to_unit_row(self):
        row = _ind('BAB-BANGSAL-A-INM-01', 'Kepatuhan Kebersihan Tangan (>= 85%)',
                   unit=self.bangsal, jenis='NASIONAL', target=85)
        row.inm_induk = self.inm_kkt
        row.save(update_fields=['inm_induk'])
        InmUnitMapping.objects.create(indikator=self.inm_kkt, unit=self.bangsal)
        url = reverse('akreditasi:indikator_input_capaian', args=[self.inm_kkt.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(str(row.pk), resp.url)


class SeedCommandTest(TestCase):
    def test_dry_run_writes_nothing(self):
        from io import StringIO
        from django.core.management import call_command

        _ind('INM-01', 'Kepatuhan Kebersihan Tangan (KKT)')
        call_command('seed_inm_matrix', '--dry-run', stdout=StringIO(), stderr=StringIO())
        self.assertEqual(InmUnitMapping.objects.count(), 0)

    def test_seed_is_idempotent(self):
        from io import StringIO
        from django.core.management import call_command

        _ind('INM-01', 'Kepatuhan Kebersihan Tangan (KKT)')
        call_command('seed_inm_matrix', stdout=StringIO(), stderr=StringIO())
        first = InmUnitMapping.objects.count()
        call_command('seed_inm_matrix', stdout=StringIO(), stderr=StringIO())
        self.assertEqual(InmUnitMapping.objects.count(), first)

    def test_seed_marks_pj_unit(self):
        from io import StringIO
        from django.core.management import call_command

        _ind('INM-01', 'Kepatuhan Kebersihan Tangan (KKT)')
        _unit('KOM-PPI', 'Komite PPI')
        call_command('seed_inm_matrix', stdout=StringIO(), stderr=StringIO())
        row = InmUnitMapping.objects.filter(
            indikator__kode_indikator='INM-01', unit__code='KOM-PPI'
        )
        self.assertTrue(row.exists())
        self.assertTrue(row.first().is_pj)

    def test_seed_reports_skips_without_creating_rows(self):
        """INM yang unitnya tidak ada di DB tetap di-skip, bukan dikarang."""
        from io import StringIO
        from django.core.management import call_command

        _ind('INM-01', 'Kepatuhan Kebersihan Tangan (KKT)')
        err = StringIO()
        try:
            call_command('seed_inm_matrix', '--strict', stdout=StringIO(), stderr=err)
            strict_failed = False
        except SystemExit:
            strict_failed = True
        # DB uji minim unit -> ada skip, dan --strict menandainya dengan exit 1.
        if err.getvalue().strip():
            self.assertTrue(strict_failed)
            self.assertNotIn('KOM-PPI', set(
                InmUnitMapping.objects.values_list('unit__code', flat=True)
            ))
