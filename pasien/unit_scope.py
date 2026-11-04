"""Unit scope helper: kontrol akses berbasis unit kerja pada aplikasi pasien.

Aturan scope ditulis SEKALI di sini dan dipakai oleh tiga konsumen: queryset
daftar (``scope_*_qs``), pemeriksaan per-objek (``can_read_*``), dan penentu
tombol di template (``boleh_baca_kunjungan_jenis``). Sebelumnya aturan yang
sama ditulis ulang di ``pasien_detail`` dan ``kunjungan_detail``, sehingga
perbaikan di satu tempat tidak ikut memperbaiki tempat lain.

Dua lapisan otorisasi yang berlaku:

* Modul (``UserProfile.get_allowed_patient_modules``) — fungsi klinis/kerja.
* Unit (modul ini) — unit kerja yang berwenang atas rekam.

Keduanya harus sepakat. ``master_pasien`` (indeks identitas pasien) diberikan
ke semua pengguna login, sehingga halaman identitas pasien bersifat
rumah-sakit-luas; yang dibatasi unit adalah REKAM KLINIS (kunjungan, CPPT,
diagnosa, billing).
"""

# Jenis kunjungan → penanda kode unit yang berwenang atas jenis itu.
# Token sengaja mengikuti kosakata yang sudah dipakai
# UserProfile.get_allowed_patient_modules() ('IGD', 'IRJ'/'POLI', 'IRIN'/
# 'BANGSAL'/'INTENSIF'/'RUANG') supaya lapisan modul dan lapisan unit tidak
# saling bertentangan. Versi lama hanya mencari kata 'IGD'/'RAJAL'/'RANAP',
# yang tidak pernah cocok dengan kode unit nyata seperti 'IRJ' atau 'POLI-ANAK'.
JENIS_UNIT_TOKENS = {
    'IGD':   ('IGD',),
    'RAJAL': ('IRJ', 'POLI', 'RAJAL'),
    'RANAP': ('IRIN', 'BANGSAL', 'INTENSIF', 'RUANG', 'RANAP'),
}

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

# Unit front-office (pendaftaran/admisi/rekam medis). Mereka memegang modul
# 'pendaftaran' dan 'master_pasien' — yaitu indeks identitas pasien — tetapi
# bukan wewenang atas rekam klinis unit lain.
FRONT_OFFICE_TOKENS = ('ADMISI', 'PENDAFTARAN', 'REKAM-MEDIS', 'REKAM MEDIS')

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


def _scope_codes(scope):
    return {u.code.upper() for u in scope if u.code}


def _ancestor_codes(profile):
    """Kode unit profil beserta seluruh leluhurnya (hierarki UnitKerja)."""
    codes = set()
    curr = getattr(profile, 'unit_kerja', None)
    while curr:
        if curr.code:
            codes.add(curr.code.upper())
        curr = curr.parent
    return codes


def _visible_jenis(scope_codes):
    """Jenis kunjungan yang boleh dibaca berdasarkan kode unit dalam scope."""
    return {
        jenis for jenis, tokens in JENIS_UNIT_TOKENS.items()
        if any(token in code for code in scope_codes for token in tokens)
    }


def is_front_office(profile):
    """True bila pengguna bertugas di pendaftaran/admisi/rekam medis."""
    if profile is None:
        return False
    if get_unit_scope(profile) is None:
        return False  # sudah tanpa batas, bukan kasus front-office
    if not profile.unit_kerja:
        return False
    return any(
        token in code
        for token in FRONT_OFFICE_TOKENS
        for code in _ancestor_codes(profile)
    )


def has_hospital_wide_pasien_read(profile):
    """True bila pengguna boleh membaca indeks identitas pasien seluruh RS."""
    if get_unit_scope(profile) is None:
        return True
    return is_front_office(profile)


def pasien_scope_q(profile):
    """Q untuk Pasien yang boleh dibaca profil, atau None bila tanpa batas."""
    from django.db.models import Q

    scope = get_unit_scope(profile)
    if scope is None:
        return None
    if has_hospital_wide_pasien_read(profile):
        return None
    if not scope:
        return Q(pk__in=[])
    jenis = _visible_jenis(_scope_codes(scope))
    return (
        Q(kunjungan__unit_kerja__in=scope)
        | Q(kunjungan__unit_kerja__isnull=True, kunjungan__jenis_kunjungan__in=jenis)
    )


def kunjungan_scope_q(profile):
    """Q untuk KunjunganPasien yang boleh dibaca profil, atau None bila tanpa batas."""
    from django.db.models import Q

    scope = get_unit_scope(profile)
    if scope is None:
        return None
    if not scope:
        return Q(pk__in=[])
    jenis = _visible_jenis(_scope_codes(scope))
    return (
        Q(unit_kerja__in=scope)
        | Q(unit_kerja__isnull=True, jenis_kunjungan__in=jenis)
    )


def scope_kunjungan_qs(qs, profile):
    """Batasi queryset KunjunganPasien ke unit dalam scope profil."""
    q = kunjungan_scope_q(profile)
    return qs if q is None else qs.filter(q)


def scope_pasien_qs(qs, profile):
    """Batasi queryset Pasien ke unit dalam scope profil."""
    q = pasien_scope_q(profile)
    return qs if q is None else qs.filter(q).distinct()


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


def boleh_baca_kunjungan_jenis(profile, jenis):
    """True bila profil boleh membaca kunjungan berjenis tertentu.

    Dipakai template untuk tidak menampilkan tautan yang pasti berakhir 403.
    """
    scope = get_unit_scope(profile)
    if scope is None:
        return True
    if not scope:
        return False
    return jenis in _visible_jenis(_scope_codes(scope))
