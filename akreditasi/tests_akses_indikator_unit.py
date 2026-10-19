"""Unit-scope resolution for IndikatorMutu — spec "Perubahan di bagian
dashboard unit untuk melihat indikator mutu" (19.10).

Three rules, pinned here so they cannot drift:
  1. Scope walks DOWN (descendants) and UP (ancestors), so a bangsal sees
     the indicators owned by its instalasi. Repo precedent: test
     eval ``test_evaluasi_candidates_include_parent_unit_indicators``
     already documents the Bangsal->IRIN convention for the Evaluasi flow.
  2. INM is filtered by unit like every other tier — no unconditional
     ``Q(jenis='NASIONAL')`` leak.
  3. ``KOORDINATOR_POKJA`` and ``ASESOR`` keep hospital-wide visibility
     even when they carry a unit_kerja.
"""
from decimal import Decimal
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from akreditasi.akses_indikator import (
    HOSPITAL_WIDE_ROLES,
    indikator_aktif_scoped,
    unit_scope_ids,
)
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu

User = get_user_model()

# Migrations seed the test DB with demo units (IRIN, BANGSAL-ANAK, ...), so
# both unique columns — UnitKerja.code and IndikatorMutu.kode_indikator —
# need a prefix the seeder will never produce.
_SEQ = itertools.count(1)


def _mk_unit(code, name, parent=None, level=3):
    return UnitKerja.objects.create(code=f'T{next(_SEQ)}-{code}', name=name,
                                    parent=parent, level=level, is_active=True)


def _mk_ind(unit, jenis, kode):
    return IndikatorMutu.objects.create(
        kode_indikator=f'T{next(_SEQ)}-{kode}',
        nama_indikator=kode,
        jenis=jenis,
        dimensi_mutu='AMAN',
        target_nilai=Decimal('85.00'),
        arah_target='MIN',
        satuan='%',
        unit=unit,
        aktif=True,
    )


def _user(username, unit, role='KEPALA_UNIT'):
    """Plain user with a unit attached — no scoping assertion."""
    user = User.objects.create_user(username, f'{username}@rs.id', 'pass123')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = role
    profile.unit_kerja = unit
    profile.save()
    return user


def _unit_scoped_user(username, unit, role='KEPALA_UNIT'):
    """Return a user for whom ``profile.is_unit_scoped`` is True.

    ``is_unit_scoped`` is a read-only property (not a field): it is True
    when the user is not a superuser, the role is outside
    SUPER_ADMIN/ADMIN_RS/DIREKTUR, and ``unit_kerja`` is set. Arrange
    those three inputs — never assign the property itself.

    Roles that are exempt by definition must use ``_user`` instead.
    """
    user = _user(username, unit, role)
    assert user.profile.is_unit_scoped, f'{username} is not unit-scoped'
    return user


class UnitScopeIdsTest(TestCase):
    def test_includes_self_and_two_levels_of_descendants(self):
        root = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        mid = _mk_unit('BANGSAL-ANAK', 'Bangsal Perawatan Anak', parent=root, level=3)
        leaf = _mk_unit('RUANG-ANAK', 'Ruang Perawatan Anak', parent=mid, level=4)
        self.assertEqual(unit_scope_ids(root), {root.pk, mid.pk, leaf.pk})

    def test_includes_ancestors(self):
        """The spec's own example: Bangsal Perawatan Anak owns 0 indicators,
        its parent IRIN owns 3 IMP_RS. Without the upward walk the bangsal
        sees an empty list."""
        root = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        mid = _mk_unit('BANGSAL-ANAK', 'Bangsal Perawatan Anak', parent=root, level=3)
        self.assertEqual(unit_scope_ids(mid), {mid.pk, root.pk})

    def test_stops_at_top_without_error(self):
        top = _mk_unit('PELAKSANA', 'Pelaksana Teknis', parent=None, level=1)
        self.assertEqual(unit_scope_ids(top), {top.pk})

    def test_none_returns_empty(self):
        self.assertEqual(unit_scope_ids(None), set())

    def test_sibling_subtree_not_included(self):
        """Scope is the unit's own subtree plus its ancestor chain.
        Siblings are not included: another bangsal's indicators belong to
        that bangsal, and the ancestor walk only lifts the shared parent.
        """
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        anak = _mk_unit('BANGSAL-ANAK', 'Anak', parent=irin, level=3)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', parent=irin, level=3)

        scope = unit_scope_ids(anak)
        self.assertEqual(scope, {anak.pk, irin.pk})
        self.assertNotIn(inter.pk, scope)


class IndikatorAktifScopedTest(TestCase):
    def test_unit_scoped_user_sees_own_and_parent_only(self):
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        anak = _mk_unit('BANGSAL-ANAK', 'Bangsal Anak', parent=irin, level=3)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        own = _mk_ind(anak, 'IMU', 'U-ANAK')
        parent = _mk_ind(irin, 'IMRS', 'RS-IRIN')
        _mk_ind(inter, 'IMRS', 'RS-INTERNA')

        user = _unit_scoped_user('kepala-anak', anak)
        got = set(indikator_aktif_scoped(user.profile)
                  .values_list('kode_indikator', flat=True))
        self.assertEqual(got, {own.kode_indikator, parent.kode_indikator})

    def test_nasional_is_filtered_by_unit_not_leaked(self):
        """Regression pin for the original bug: both views filtered with
        ``Q(unit_id__in=...) | Q(jenis='NASIONAL')``, which handed all 36
        active INM to every unit-scoped user regardless of involvement."""
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        anak = _mk_unit('BANGSAL-ANAK', 'Bangsal Anak', parent=irin, level=3)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        mine = _mk_ind(irin, 'INM', 'INM-IRIN')
        theirs = _mk_ind(inter, 'INM', 'INM-INTERNA')

        user = _unit_scoped_user('kepala-anak2', anak)
        got = list(indikator_aktif_scoped(user.profile)
                   .values_list('kode_indikator', flat=True))
        self.assertEqual(got, [mine.kode_indikator])
        self.assertNotIn(theirs.kode_indikator, got)

    def test_inm_duplicated_per_unit_resolves_per_unit(self):
        """INM rows are duplicated per collecting unit in the real data
        (36 rows, 21 unique names). Each unit must see only its own copy."""
        irin = _mk_unit('IRIN', 'IRIN', level=2)
        anak = _mk_unit('BANGSAL-ANAK', 'Anak', parent=irin, level=3)
        a = _mk_ind(irin, 'INM', 'KKT-IRIN')
        b = _mk_ind(anak, 'INM', 'KKT-ANAK')

        user = _unit_scoped_user('kepala-anak3', anak)
        got = set(indikator_aktif_scoped(user.profile)
                  .values_list('kode_indikator', flat=True))
        self.assertEqual(got, {a.kode_indikator, b.kode_indikator})

    def test_inactive_indicators_excluded(self):
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        ind = _mk_ind(irin, 'IMRS', 'RS-OFF')
        ind.aktif = False
        ind.save()
        user = _unit_scoped_user('kepala-irin', irin)
        self.assertEqual(indikator_aktif_scoped(user.profile).count(), 0)

    def test_null_unit_indicator_hidden_from_unit_scoped_user(self):
        """``IndikatorMutu.unit`` is null=True (risiko_models.py:579), so
        ``unit_id__in`` drops it. It belongs to no unit, therefore it is
        nobody's — pinned deliberately rather than left accidental."""
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        _mk_ind(irin, 'IMRS', 'RS-LOCAL')
        orphan = _mk_ind(None, 'INM', 'INM-ORPHAN')

        user = _unit_scoped_user('kepala-irin2', irin)
        got = list(indikator_aktif_scoped(user.profile)
                   .values_list('kode_indikator', flat=True))
        self.assertEqual(len(got), 1)
        self.assertNotIn(orphan.kode_indikator, got)
        self.assertIsNone(orphan.unit)

    def test_hospital_wide_roles_see_everything(self):
        """Koordinator Pokja (4 users) and Asesor (1 user) carry a
        unit_kerja in production but must keep the full hospital list."""
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMRS', 'RS-A')
        _mk_ind(inter, 'INM', 'INM-B')

        for role, uname in (('KOORDINATOR_POKJA', 'pokja'),
                            ('ASESOR', 'asesor')):
            with self.subTest(role=role):
                self.assertIn(role, HOSPITAL_WIDE_ROLES)
                user = _unit_scoped_user(uname, irin, role=role)
                self.assertEqual(indikator_aktif_scoped(user.profile).count(), 2)

    def test_kepala_unit_stays_scoped_despite_escape_hatch(self):
        """The audience of this spec must NOT be exempted."""
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMRS', 'RS-A')
        _mk_ind(inter, 'IMRS', 'RS-B')

        user = _unit_scoped_user('kepala-a', irin, role='KEPALA_UNIT')
        self.assertNotIn('KEPALA_UNIT', HOSPITAL_WIDE_ROLES)
        self.assertEqual(indikator_aktif_scoped(user.profile).count(), 1)

    def test_staf_nakes_stays_scoped(self):
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMRS', 'RS-A')
        _mk_ind(inter, 'IMRS', 'RS-B')

        user = _unit_scoped_user('staf-a', irin, role='STAF_NAKES')
        self.assertEqual(indikator_aktif_scoped(user.profile).count(), 1)

    def test_super_admin_role_sees_everything(self):
        """``_is_unit_scoped`` already returns False for SUPER_ADMIN, so
        the resolver never consults HOSPITAL_WIDE_ROLES for it."""
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMRS', 'RS-A')
        _mk_ind(inter, 'INM', 'INM-B')

        user = _user('admin1', irin, role='SUPER_ADMIN')
        self.assertFalse(user.profile.is_unit_scoped)
        self.assertEqual(indikator_aktif_scoped(user.profile).count(), 2)

    def test_superuser_sees_everything(self):
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMRS', 'RS-A')
        _mk_ind(inter, 'IMRS', 'RS-B')

        user = _unit_scoped_user('root', irin, role='KEPALA_UNIT')
        user.is_superuser = True
        user.save()
        self.assertFalse(user.profile.is_unit_scoped)
        self.assertEqual(indikator_aktif_scoped(user.profile).count(), 2)

    def test_unit_scoped_profile_without_unit_kerja_is_not_scoped(self):
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        inter = _mk_unit('BANGSAL-INTERNA', 'Interna', level=3)
        _mk_ind(irin, 'IMRS', 'RS-A')
        _mk_ind(inter, 'IMRS', 'RS-B')

        user = _unit_scoped_user('no-unit', irin, role='KEPALA_UNIT')
        user.profile.unit_kerja = None
        user.profile.save()
        self.assertFalse(user.profile.is_unit_scoped)
        self.assertEqual(indikator_aktif_scoped(user.profile).count(), 2)

    def test_none_profile_returns_base(self):
        irin = _mk_unit('IRIN', 'Instalasi Rawat Inap', level=2)
        _mk_ind(irin, 'IMRS', 'RS-A')
        self.assertEqual(indikator_aktif_scoped(None).count(), 1)
