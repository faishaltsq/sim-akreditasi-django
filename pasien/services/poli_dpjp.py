"""Penetapan DPJP episode — satu-satunya penulis penugasan DPJP (F0.11, ADR-12).

Sumber otoritas DPJP adalah ``PenugasanDpjpEpisode``: FK ke akun dokter,
terikat unit episode, dan punya masa berlaku. Kolom teks bebas
``KunjunganPasien.dpjp`` **diturunkan** dari penugasan aktif dan tidak pernah
dibaca sebagai otoritas — ``poli_rbac.episode_dpjp()`` yang memutuskan.

Kenapa pemilihnya berbasis akun dan bukan ``DPJP_CHOICES``: tidak ada satu pun
fungsi di repo yang memetakan string ``DPJP_CHOICES`` ke ``User``, dan pada
instalasi ini tidak ada akun berprofesi dokter sama sekali. Penugasan yang
menunjuk akun fiktif tidak dapat login, sehingga otoritas ADR-11 hanya nyata
bila DPJP dipilih dari akun yang benar-benar ada.

Modul ini sengaja tidak membatasi diri pada POLI-JANTUNG: jalur IGD memakai
``PenugasanDpjpEpisode`` yang sama untuk verifikasi CPPT profesional. Yang
dibatasi unit adalah *endpoint* dasbor rajal, bukan penulisnya.
"""
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from pasien.models import KunjunganPasien, PenugasanDpjpEpisode

#: Jaring pengaman operasional, bukan aturan klinis: ``valid_until`` wajib
#: (non-null) sedangkan tidak ada kebijakan produk untuk masa berlaku penugasan
#: per episode. Penggantian DPJP menonaktifkan baris lama secara eksplisit, jadi
#: angka ini hanya mencegah penugasan menggantung tanpa batas.
DEFAULT_ASSIGNMENT_DAYS = 30

#: Peran yang boleh menetapkan DPJP: administrasi unit, bukan klinisi (ADR-12).
ASSIGNER_ROLES = frozenset({'SUPER_ADMIN', 'ADMIN_RS', 'KEPALA_UNIT'})
#: Peran yang boleh menetapkan lintas unit.
CROSS_UNIT_ASSIGNER_ROLES = frozenset({'SUPER_ADMIN', 'ADMIN_RS'})

#: Kanal sumber penugasan; ikut ditulis ke ``source_version`` supaya asal
#: setiap baris dapat ditelusuri tanpa membuka log.
SOURCE_REGISTRATION = 'REGISTRASI'
SOURCE_RAJAL_DASHBOARD = 'DASBOR_RAJAL'

DOKTER_PROFESSIONS = frozenset({'DOKTER_UMUM', 'DOKTER_SPESIALIS', 'DOKTER_GIGI'})


def dpjp_display_name(user):
    """Nama tampilan akun dokter; tidak pernah kosong untuk akun berprofil."""
    profile = getattr(user, 'profile', None)
    for candidate in (getattr(profile, 'full_name', ''), user.get_full_name(), user.username):
        if candidate and candidate.strip():
            return candidate.strip()
    return str(user.pk)


def eligible_dpjp_accounts(unit=None):
    """Akun dokter aktif yang dapat ditugaskan (ADR-12 opsi b).

    ``unit`` menyaring lewat ``profile.unit_kerja`` bila diberikan. Akun tanpa
    profil atau tanpa profesi dokter tidak pernah ikut — pemilih DPJP tidak
    boleh menawarkan akun yang akan ditolak ``PenugasanDpjpEpisode.clean()``.
    """
    from django.contrib.auth import get_user_model

    qs = get_user_model().objects.filter(
        is_active=True, profile__profesi__in=DOKTER_PROFESSIONS,
    ).select_related('profile').order_by('profile__full_name', 'username')
    if unit is not None:
        qs = qs.filter(profile__unit_kerja=unit)
    return qs


def require_dpjp_assigner(user, visit):
    """ADR-12 butir 4: administrasi unit episode, bukan klinisi."""
    profile = getattr(user, 'profile', None)
    if not getattr(user, 'is_authenticated', False) or profile is None:
        raise PermissionDenied('Profil pengguna diperlukan untuk menetapkan DPJP.')
    if getattr(user, 'is_superuser', False) or profile.role in CROSS_UNIT_ASSIGNER_ROLES:
        return profile
    if profile.role in ASSIGNER_ROLES and visit.unit_kerja_id and profile.unit_kerja_id == visit.unit_kerja_id:
        return profile
    raise PermissionDenied('Penetapan DPJP hanya oleh administrasi unit episode.')


def can_assign_dpjp(user, visit):
    """Versi boolean ``require_dpjp_assigner`` untuk menyusun template."""
    try:
        require_dpjp_assigner(user, visit)
    except PermissionDenied:
        return False
    return True


def active_assignments(visit):
    """Seluruh penugasan aktif episode ini, urut waktu penetapan."""
    return PenugasanDpjpEpisode.objects.filter(visit=visit, is_active=True).order_by('pk')


def active_assignment(visit):
    """Penugasan aktif tunggal, atau ``None``. Ganda sengaja tidak dipilih diam-diam."""
    rows = list(active_assignments(visit)[:2])
    if len(rows) > 1:
        raise PermissionDenied('Penugasan DPJP ambigu; selesaikan penugasan sebelum melanjutkan.')
    return rows[0] if rows else None


def _source_version(channel, visit):
    """Jejak asal penugasan: kanal, nomor kunjungan, dan waktu penetapan."""
    stamp = timezone.now().isoformat(timespec='seconds')
    return f'{channel}:{visit.no_kunjungan}:{stamp}'


def _require_assignable_visit(visit):
    if visit.unit_kerja_id is None:
        raise PermissionDenied('Episode belum memiliki unit kerja; DPJP tidak dapat ditetapkan.')
    if visit.status in ('PULANG', 'RUJUK', 'MENINGGAL', 'BATAL'):
        raise PermissionDenied('Episode yang sudah ditutup tidak dapat diubah DPJP-nya.')


@transaction.atomic
def assign_dpjp(visit, doctor, actor, *, channel=SOURCE_RAJAL_DASHBOARD,
                valid_from=None, valid_until=None):
    """Tetapkan ``doctor`` sebagai DPJP aktif episode, ganti yang lama.

    Mengembalikan ``(assignment, created)``. Idempoten: bila penugasan aktif
    sudah menunjuk dokter yang sama dan masih berlaku, baris itu dikembalikan
    tanpa membuat baris baru (ADR-12 butir 6).

    Penugasan lama **tidak pernah dihapus** — hanya ``is_active=False``
    (requirement 2), sehingga riwayat siapa bertanggung jawab kapan tetap ada.
    """
    require_dpjp_assigner(actor, visit)
    _require_assignable_visit(visit)

    profile = getattr(doctor, 'profile', None)
    if profile is None or profile.profesi not in DOKTER_PROFESSIONS:
        raise PermissionDenied('DPJP harus akun dokter.')

    today = valid_from or timezone.localdate()
    until = valid_until or (today + timedelta(days=DEFAULT_ASSIGNMENT_DAYS))

    current = active_assignment(visit)
    if current is not None and current.doctor_id == doctor.pk and current.valid_from <= today <= current.valid_until:
        _sync_display(visit, doctor)
        return current, False

    # ``.update()`` melewati ``PenugasanDpjpEpisode.save()``: yang berubah hanya
    # ``is_active``, dan ``full_clean()`` pada baris lama akan menolak penugasan
    # yang unit episode-nya sudah berpindah. Identitas/sumber tidak pernah
    # ditimpa — baris baru yang mencatat DPJP berikutnya.
    PenugasanDpjpEpisode.objects.filter(visit=visit, is_active=True).update(is_active=False)

    assignment = PenugasanDpjpEpisode(
        visit=visit, doctor=doctor, unit_id=visit.unit_kerja_id,
        assignment_type='PRIMARY', valid_from=today, valid_until=until,
        is_active=True, source_version=_source_version(channel, visit),
        assigned_by=actor,
    )
    assignment.save()
    _sync_display(visit, doctor)
    return assignment, True


@transaction.atomic
def clear_dpjp(visit, actor, *, channel=SOURCE_RAJAL_DASHBOARD):
    """Cabut DPJP episode: tidak ada penugasan aktif dan string tampilan kosong."""
    require_dpjp_assigner(actor, visit)
    _require_assignable_visit(visit)
    deactivated = PenugasanDpjpEpisode.objects.filter(visit=visit, is_active=True).update(is_active=False)
    if (visit.dpjp or '') != '':
        KunjunganPasien.objects.filter(pk=visit.pk).update(dpjp='')
        visit.dpjp = ''
    return deactivated


def _sync_display(visit, doctor):
    """Turunkan ``visit.dpjp`` dari akun terpilih (ADR-12 butir 2)."""
    name = dpjp_display_name(doctor)
    if visit.dpjp != name:
        KunjunganPasien.objects.filter(pk=visit.pk).update(dpjp=name)
        visit.dpjp = name


def reconcile_dpjp_display(visit):
    """Pulihkan ``visit.dpjp`` dari penugasan aktif bila menyimpang.

    Arah kedua ADR-12: penugasan menang. Bila tidak ada penugasan aktif, string
    lama dibiarkan — ia anotasi tampilan tanpa otoritas (mis. kunjungan IGD
    yang DPJP-nya masih teks bebas).
    """
    assignment = active_assignment(visit)
    if assignment is None:
        return None
    _sync_display(visit, assignment.doctor)
    return visit.dpjp


def assert_display_writable(visit, value):
    """Tolak penulisan string lama yang membalik turunan penugasan.

    Dipanggil jalur tulis lama (pendaftaran/IGD). Inert bila episode belum
    punya penugasan aktif, sehingga perilaku IGD tidak bergeser.
    """
    assignment = active_assignment(visit)
    if assignment is None:
        return
    if (value or '').strip() != dpjp_display_name(assignment.doctor):
        raise PermissionDenied(
            'DPJP episode ini ditetapkan lewat penugasan; ubah penugasan, bukan teks DPJP.'
        )
