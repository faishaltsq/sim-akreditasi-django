"""Matriks kewenangan 6 peran × 10 langkah POLI-JANTUNG (ADR-11, F1.10).

Kewenangan ditegakkan **di sini**, di jalur layanan, bukan di template. Setiap
penolakan adalah ``PermissionDenied`` yang diterjemahkan view menjadi HTTP 403.

ADR-11 menetapkan pembagian klinis vs administratif:

* Langkah administratif/penyiapan (registrasi, triase, penunjang, pelaksanaan
  asuhan) boleh diisi perawat dan peran non-DPJP sesuai matriks.
* Langkah penutup klinis (diagnosis & rencana, evaluasi akhir + kondisi pulang)
  dan finalisasi hanya DPJP.

**Otoritas DPJP.** ``require_doctor`` (``pasien/services/igd_actions.py``)
menerima dokter apa pun; itu bukan pemeriksaan DPJP. Sumber otoritas yang
dipakai di sini adalah ``PenugasanDpjpEpisode`` — FK ke akun dokter, terikat
unit episode, dengan masa berlaku. Kolom teks bebas ``KunjunganPasien.dpjp``
hanya untuk tampilan dan **tidak pernah** dipakai sebagai otoritas.

Konsekuensi: episode POLI-JANTUNG wajib punya satu penugasan DPJP aktif
sebelum langkah klinis dapat diisi. Bila tidak ada, seluruh penulisan ditolak
(ADR-11 butir 4). Penugasan ganda juga ditolak — ambigu berarti tidak ada
DPJP yang dapat dipertanggungjawabkan.
"""
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from pasien.models import PenugasanDpjpEpisode
from pasien.workflow_schemas import RAJAL_JANTUNG_STEP_NUMBERS

PERAWAT = 'PERAWAT'
DPJP = 'DPJP'
FARMASI = 'FARMASI'
GIZI = 'GIZI'
FISIOTERAPI = 'FISIOTERAPI'
KASIR = 'KASIR'
#: Dokter yang belum ditugaskan sebagai DPJP episode. Bukan salah satu dari 6
#: peran matriks; ada supaya penolakan ADR-11 dapat dinyatakan eksplisit.
DOKTER_NON_DPJP = 'DOKTER_NON_DPJP'
#: Asesor/viewer — baca saja, bukan anggota tim pelayanan.
VIEWER = 'VIEWER'

ROLE_LABELS = {
    PERAWAT: 'Perawat Poli',
    DPJP: 'DPJP Sp.JP',
    FARMASI: 'Farmasi',
    GIZI: 'Gizi',
    FISIOTERAPI: 'Fisioterapi',
    KASIR: 'Kasir / Rekam Medis',
    DOKTER_NON_DPJP: 'Dokter non-DPJP',
    VIEWER: 'Asesor / Viewer',
}

DOKTER_PROFESSIONS = frozenset({'DOKTER_UMUM', 'DOKTER_SPESIALIS', 'DOKTER_GIGI'})
NURSE_PROFESSIONS = frozenset({'PERAWAT', 'BIDAN'})
FARMASI_PROFESSIONS = frozenset({'APOTEKER', 'TTK'})
GIZI_PROFESSIONS = frozenset({'NUTRISIONIS'})
FISIOTERAPI_PROFESSIONS = frozenset({'FISIOTERAPIS'})
KASIR_PROFESSIONS = frozenset({'PEREKAM_MEDIS'})

_READ_ALL = frozenset({PERAWAT, DPJP, FARMASI, GIZI, FISIOTERAPI, KASIR, DOKTER_NON_DPJP, VIEWER})

#: Peran yang boleh **mengisi** tiap langkah.
FILL_ROLES = {
    1: frozenset({PERAWAT, DPJP}),
    2: frozenset({PERAWAT, DPJP}),
    3: frozenset({PERAWAT, DPJP}),
    4: frozenset({PERAWAT, DPJP}),
    5: frozenset({PERAWAT, DPJP, GIZI}),
    6: frozenset({PERAWAT, DPJP}),
    7: frozenset({PERAWAT, DPJP}),
    8: frozenset({DPJP}),
    9: frozenset({PERAWAT, DPJP, FARMASI, GIZI, FISIOTERAPI}),
    10: frozenset({DPJP}),
}

#: Verifikasi klinis per langkah — hanya DPJP.
VERIFY_ROLES = {number: frozenset({DPJP}) for number in RAJAL_JANTUNG_STEP_NUMBERS}

#: Baca — seluruh peran matriks; lingkup unit/modul tetap dijaga authorize_visit.
READ_ROLES = {number: _READ_ALL for number in RAJAL_JANTUNG_STEP_NUMBERS}

STEP_ACCESS = {'fill': FILL_ROLES, 'read': READ_ROLES, 'verify': VERIFY_ROLES}

ACTION_LABELS = {'fill': 'mengisi', 'read': 'membaca', 'verify': 'memverifikasi'}


def active_dpjp_assignments(visit, user=None):
    """Penugasan DPJP aktif untuk episode ini (opsional disaring per akun)."""
    if not visit.unit_kerja_id:
        return PenugasanDpjpEpisode.objects.none()
    day = timezone.localdate()
    qs = PenugasanDpjpEpisode.objects.filter(
        visit=visit, unit_id=visit.unit_kerja_id, is_active=True,
        valid_from__lte=day, valid_until__gte=day,
    )
    if user is not None:
        qs = qs.filter(doctor=user)
    return qs


def episode_dpjp(visit):
    """Penugasan DPJP tunggal yang aktif, atau ``PermissionDenied``."""
    rows = list(active_dpjp_assignments(visit)[:2])
    if not rows:
        raise PermissionDenied('Episode belum memiliki DPJP aktif; langkah klinis tidak dapat dimulai.')
    if len(rows) > 1:
        raise PermissionDenied('Penugasan DPJP ambigu; selesaikan penugasan sebelum mengisi asesmen.')
    return rows[0]


def resolve_role(user, visit):
    """Peta akun → peran matriks, atau ``None`` bila tidak berwenang."""
    profile = getattr(user, 'profile', None)
    if not getattr(user, 'is_authenticated', False) or profile is None:
        return None
    if profile.role == 'ASESOR':
        return VIEWER
    profesi = profile.profesi
    if profesi in DOKTER_PROFESSIONS:
        return DPJP if active_dpjp_assignments(visit, user).exists() else DOKTER_NON_DPJP
    if profesi in NURSE_PROFESSIONS:
        return PERAWAT
    if profesi in FARMASI_PROFESSIONS:
        return FARMASI
    if profesi in GIZI_PROFESSIONS:
        return GIZI
    if profesi in FISIOTERAPI_PROFESSIONS:
        return FISIOTERAPI
    if profesi in KASIR_PROFESSIONS:
        return KASIR
    return None


def can_write(visit, user):
    """Apakah akun ini peserta penulisan asesmen sama sekali (bukan viewer)."""
    return resolve_role(user, visit) not in (None, VIEWER)


def authorize_step(user, visit, step, action):
    """Tegakkan matriks; kembalikan peran yang lolos atau lempar 403."""
    role = resolve_role(user, visit)
    allowed = STEP_ACCESS.get(action, {}).get(step)
    if allowed is None:
        raise PermissionDenied('Langkah tidak dikenal pada matriks kewenangan.')
    if role is None or role not in allowed:
        label = ROLE_LABELS.get(role, 'Peran tidak dikenal')
        raise PermissionDenied(f'{label} tidak berwenang {ACTION_LABELS[action]} langkah {step}.')
    return role


def require_dpjp(user, visit):
    """ADR-11: hanya DPJP episode yang boleh menutup asesmen klinis."""
    role = resolve_role(user, visit)
    if role != DPJP:
        raise PermissionDenied('Finalisasi dan tanda tangan klinis hanya untuk DPJP episode.')
    return episode_dpjp(visit)
