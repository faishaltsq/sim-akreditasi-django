"""Penyelesaian lingkup unit untuk Indikator Mutu.

Satu-satunya tempat yang menjawab "indikator apa yang boleh dilihat unit
ini". Dipakai oleh ``akreditasi.views.dashboard`` dan
``akreditasi.indikator_views`` agar keduanya tidak bisa memberi jawaban
berbeda untuk user yang sama.

Rationale: setiap baris ``IndikatorMutu`` membawa ``unit`` yang
benar-benar mengumpulkan datanya (terverifikasi 2026-10-19: 100% terisi,
dan INM diduplikasi per unit — "Kepatuhan Kebersihan Tangan" muncul 9x di
9 unit berbeda). Karena itu filter per-unit sudah menjawab kebutuhan
spesifikasi 19.10 tanpa tabel pemetaan tambahan.
"""

from .models import UnitKerja
from .risiko_models import IndikatorMutu

# Role yang wajib tetap melihat seluruh indikator rumah sakit, meski
# unit_kerja-nya terisi. Menghapus Q(jenis='NASIONAL') tanpa daftar ini
# menyembunyikan menu indikator dari 4 Koordinator Pokja + 1 Asesor
# (data 2026-10-19, 36 profil).
#
# Hanya berisi role yang benar-benar ada di UserProfile.ROLE_CHOICES.
# SUPER_ADMIN / ADMIN_RS sengaja TIDAK dimasukkan: ``_is_unit_scoped``
# sudah mengembalikan False untuk mereka, jadi entri di sini cuma menutupi
# radius ledakan yang sebenarnya. DIREKTUR dan SURVEYOR_INTERNAL tidak ada
# di ROLE_CHOICES — jangan ditulis ulang.
HOSPITAL_WIDE_ROLES = ('KOORDINATOR_POKJA', 'ASESOR')

_DESCENDANT_DEPTH = 2
_ANCESTOR_DEPTH = 2


def unit_scope_ids(unit):
    """PK unit ini, turunannya (2 level), dan leluhurnya (2 level).

    Turunan: kepala bangsal melihat indikator ruang di bawahnya.
    Leluhur: kepala bangsal melihat indikator milik instalasinya. Tanpa
    bagian ini Bangsal Perawatan Anak — nol indikator sendiri, induknya
    IRIN punya 3 IMP_RS — melihat daftar kosong. Konvensi yang sama sudah
    dipakai alur Evaluasi, lihat
    ``test_evaluasi_candidates_include_parent_unit_indicators``.
    """
    if unit is None:
        return set()

    ids = {unit.pk}
    frontier = {unit.pk}
    for _ in range(_DESCENDANT_DEPTH):
        frontier = set(
            UnitKerja.objects.filter(parent_id__in=frontier)
            .values_list('pk', flat=True)
        ) - ids
        if not frontier:
            break
        ids |= frontier

    parent = unit.parent
    for _ in range(_ANCESTOR_DEPTH):
        if parent is None:
            break
        ids.add(parent.pk)
        parent = parent.parent
    return ids


def indikator_aktif_scoped(profile):
    """QuerySet ``IndikatorMutu`` aktif yang berada dalam lingkup profile.

    ``aktif=True`` sudah diterapkan di sini — jangan ditambah lagi di
    pemanggil. Indikator ber-``unit`` NULL ikut terkecuali, karena
    ``IndikatorMutu.unit`` bersifat ``null=True`` dan tidak bisa
    dipasangkan dengan unit mana pun.
    """
    base = IndikatorMutu.objects.filter(aktif=True)

    if profile is None:
        return base
    if getattr(profile, 'role', None) in HOSPITAL_WIDE_ROLES:
        return base
    if not getattr(profile, 'is_unit_scoped', False):
        return base

    unit = getattr(profile, 'unit_kerja', None)
    if unit is None:
        return base
    return base.filter(unit_id__in=unit_scope_ids(unit))
