"""Unit scope helper: kontrol akses berbasis unit kerja pada aplikasi pasien.

Aturan scope ditulis SEKALI di sini dan dipakai oleh tiga konsumen: queryset
daftar (``scope_*_qs``), pemeriksaan per-objek (``can_read_*``), dan penentu
tombol di template (``boleh_detail_kunjungan``). Sebelumnya aturan yang
sama ditulis ulang di ``pasien_detail`` dan ``kunjungan_detail``, sehingga
perbaikan di satu tempat tidak ikut memperbaiki tempat lain.

Kepemilikan pasien ("pasien sedang di unit mana") TIDAK ditebak di sini.
Satu-satunya pemegang jawaban itu adalah ``akreditasi.layanan_unit`` — peta
poliklinik→UnitKerja dan ruangan→UnitKerja yang sudah dipakai blok LAYANAN
serta angka EMR, supaya front-office, dasbor unit, dan KPI akreditasi tidak
bisa memberi jawaban berbeda untuk kunjungan yang sama. Modul ini hanya
menerjemahkan jawaban itu menjadi batas baca.

Dua lapisan otorisasi yang berlaku:

* Modul (``UserProfile.get_allowed_patient_modules``) — fungsi klinis/kerja.
* Unit (modul ini) — unit kerja yang berwenang atas rekam.

Keduanya harus sepakat. Unit front-office (pendaftaran/admisi/rekam medis)
memegang modul ``master_pasien`` tetapi tetap dibatasi unit: mereka hanya
melihat pasien yang sedang berada di unit layanan di bawah hierarkinya, bukan
seluruh rumah sakit.
"""

# Batas ukuran hasil daftar Pasien. ``scope_pasien_qs`` menyaring lewat JOIN
# ke KunjunganPasien dan karena relasinya one-to-many hasilnya harus
# ``.distinct()``; nilai ini menjaga agar JOIN itu tetap murah. Bukan
# pagination UI — pemotongan ``[:100]`` yang sudah ada tetap di view.
MAX_SCOPE_PASIEN = 100

# Kode unit kanonik per jenis — dipakai saat MENSTEMPEL kunjungan baru
# (``KunjunganPasien.save`` dan command backfill), bukan saat memeriksa akses.
# Hanya IGD yang punya unit kanonik: kunjungan RAJAL dimiliki oleh layanan
# rawat jalan (worklist per ``poliklinik``, lihat ``rajal_dashboard``), dan
# kunjungan RANAP mendapat unitnya dari bed/ruangan saat penempatan. Menstempel
# RAJAL ke unit IRJ atau RANAP ke IRIN akan menyembunyikan kunjungan itu dari
# sub-unit pemiliknya (POLI-* / bangsal), karena scope hanya berisi unit sendiri
# beserta turunannya. Nilai lama 'RAJAL'/'RANAP' juga tidak pernah ada sebagai
# kode UnitKerja, sehingga lookup-nya gagal senyap.
DEFAULT_UNIT_BY_JENIS = {
    'IGD': 'IGD',
}

UNRESTRICTED_ROLES = ('SUPER_ADMIN', 'ADMIN_RS', 'DIREKTUR')


def get_unit_scope(profile):
    """Return set of accessible UnitKerja instances, or None for unlimited (admin)."""
    if profile is None:
        return None
    user = getattr(profile, 'user', None)
    if profile.role in UNRESTRICTED_ROLES or getattr(user, 'is_superuser', False):
        return None  # Unrestricted
    if not profile.unit_kerja:
        return set()
    # Include unit_kerja and its descendants if hierarchical
    scope = {profile.unit_kerja}
    if hasattr(profile.unit_kerja, 'get_descendants'):
        scope.update(profile.unit_kerja.get_descendants())
    elif hasattr(profile.unit_kerja, 'children'):
        def collect(u):
            for c in u.children.all():
                if c not in scope:
                    scope.add(c)
                    collect(c)
        collect(profile.unit_kerja)
    return scope


def pasien_scope_q(profile):
    """Q untuk Pasien yang boleh dibaca profil, atau None bila tanpa batas.

    Seorang pengguna melihat pasien yang kunjungannya sedang dilayani oleh
    unitnya (atau turunannya). Kepemilikan dihitung oleh ``layanan_unit``
    berdasarkan poliklinik/ruangan kunjungan, bukan dari jenis kunjungan.
    """
    from django.db.models import Q

    scope = get_unit_scope(profile)
    if scope is None:
        return None
    if not scope:
        return Q(pk__in=[])
    return kunjungan_scope_q(profile)


def kunjungan_scope_q(profile):
    """Q untuk KunjunganPasien yang boleh dibaca profil, atau None bila tanpa batas.

    Satu kunjungan dianggap milik unit U bila ``layanan_unit.visit_unit_code``
    mengembalikan kode U atau salah satu turunannya. Karena kode itu dihitung
    per-baris (bukan ekspresi SQL), penyaringan dilakukan dengan memfilter
    daftar kunjungan terlebih dahulu lalu memakainya sebagai ``pk__in``.

    KEPEMILIKAN: stempel ``unit_kerja`` menang — itu yang menjawab "pasien
    sedang di unit mana" (``kunjungan_baru`` menstempel unit petugas pendaftar,
    ``KunjunganPasien.save`` menstempel unit IGD, bed/ruangan menentukan unit
    rawat inap). Peta poliklinik/ruangan hanya dipakai untuk kunjungan lama
    yang belum punya stempel.
    """
    from django.db.models import Q

    scope = get_unit_scope(profile)
    if scope is None:
        return None
    if not scope:
        return Q(pk__in=[])
    return Q(pk__in=scope_kunjungan_ids(profile))


def scope_kunjungan_qs(qs, profile):
    """Batasi queryset KunjunganPasien ke unit dalam scope profil."""
    q = kunjungan_scope_q(profile)
    return qs if q is None else qs.filter(q)


def scope_pasien_qs(qs, profile):
    """Batasi queryset Pasien ke unit dalam scope profil."""
    q = pasien_scope_q(profile)
    return qs if q is None else qs.filter(q).distinct()


def scope_kunjungan_ids(profile):
    """PK kunjungan yang dilayani unit dalam scope profil.

    Satu-satunya jembatan ke ``akreditasi.layanan_unit``: di sana letak peta
    poliklinik→unit dan ruangan→unit yang juga dipakai blok LAYANAN dan angka
    EMR dasbor akreditasi.
    """
    from akreditasi.kontrol_data import ACTIVE_VISIT_STATUSES
    from akreditasi.layanan_unit import resolve_visit_ids
    from .models import KunjunganPasien

    scope = get_unit_scope(profile)
    if scope is None or not scope:
        return []
    # Hanya kunjungan yang masih aktif, seperti blok EMR/Layanan dasbor
    # akreditasi: pasien yang sudah pulang/rujuk bukan lagi beban unit mana
    # pun, sehingga front-office pun berhenti melihatnya.
    qs = KunjunganPasien.objects.filter(
        status__in=ACTIVE_VISIT_STATUSES).select_related('bed__ruangan')
    return resolve_visit_ids(qs, profile.unit_kerja)


def can_read_pasien(pasien, profile):
    """True bila profil boleh membuka halaman identitas pasien ini."""
    from .models import Pasien

    q = pasien_scope_q(profile)
    if q is None:
        return True
    return Pasien.objects.filter(q, pk=pasien.pk).exists()


def can_read_kunjungan(kunjungan, profile):
    """True bila profil boleh membuka rekam klinis kunjungan ini."""
    from .models import KunjunganPasien

    q = kunjungan_scope_q(profile)
    if q is None:
        return True
    return KunjunganPasien.objects.filter(q, pk=kunjungan.pk).exists()


def boleh_detail_kunjungan(kunjungan, profile):
    """True bila profil boleh membuka rekam klinis kunjungan ini.

    Dipakai template untuk tidak menampilkan tautan yang pasti berakhir 403.
    Memakai jalur yang sama dengan ``kunjungan_detail`` (``can_read_kunjungan``)
    agar tombol dan pemeriksaan view tidak bisa berbeda pendapat.
    """
    return can_read_kunjungan(kunjungan, profile)
