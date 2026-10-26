"""Matriks ekspektasi status HTTP per role x URL.

Sumber: pengukuran 6 role x 82 endpoint pada DB dev (lihat plan
docs/superpowers/plans/2026-10-23-qa-fleet-1295-akun.md).

Aturan:
  - 403/302 sah bila role memang tidak berhak.
  - 400 sah bila endpoint butuh parameter wajib.
  - 405 sah bila endpoint POST-only diprobe dengan GET.
  - 500 TIDAK PERNAH sah.
  - 200 yang seharusnya 403 adalah temuan (role kehilangan haknya).
"""
import re

ROLES = [
    'SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA',
    'KEPALA_UNIT', 'STAF_NAKES', 'ASESOR',
]

# Endpoint yang statusnya berbeda antar role. Diukur, bukan diasumsikan.
# Format: url -> {role: {status yang sah}}
PER_ROLE = {
    '/accounts/kontrol/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {302}, 'KEPALA_UNIT': {302},
        'STAF_NAKES': {302}, 'ASESOR': {302},
    },
    '/accounts/users/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {302}, 'KEPALA_UNIT': {302},
        'STAF_NAKES': {302}, 'ASESOR': {302},
    },
    '/log/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {302}, 'KEPALA_UNIT': {302},
        'STAF_NAKES': {302}, 'ASESOR': {302},
    },
    '/pokja/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {302}, 'KEPALA_UNIT': {302},
        'STAF_NAKES': {302}, 'ASESOR': {302},
    },
    '/profil/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {302}, 'KEPALA_UNIT': {302},
        'STAF_NAKES': {302}, 'ASESOR': {302},
    },
    '/unit/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {302}, 'KEPALA_UNIT': {302},
        'STAF_NAKES': {302}, 'ASESOR': {302},
    },
    '/indikator-mutu/matriks-inm/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {200}, 'KEPALA_UNIT': {200},
        'STAF_NAKES': {403}, 'ASESOR': {403},
    },
    '/rekap-kps/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200}, 'KEPALA_UNIT': {200},
        'KOORDINATOR_POKJA': {403}, 'STAF_NAKES': {403}, 'ASESOR': {403},
    },
    '/rekap/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {200}, 'KEPALA_UNIT': {200},
        'STAF_NAKES': {403}, 'ASESOR': {403},
    },
    '/portal-nakes/': {
        'SUPER_ADMIN': {200}, 'ADMIN_RS': {200},
        'KOORDINATOR_POKJA': {302}, 'KEPALA_UNIT': {302},
        'ASESOR': {302}, 'STAF_NAKES': {200},
    },
}

# Modul Human Capital: 403 untuk semua kecuali SUPER_ADMIN & ADMIN_RS.
# Ini adalah temuan F-3, BUKAN bug baru — dicatat sekali di FINDINGS, tidak
# dilaporkan ulang per akun.
HC_URLS_403 = {
    '/human-capital/', '/human-capital/analitik/',
    '/human-capital/analitik/ekspor/', '/human-capital/diklat/',
    '/human-capital/formasi/', '/human-capital/kinerja/',
    '/human-capital/kredensial/', '/human-capital/orientasi/',
    '/human-capital/pegawai/', '/human-capital/rekrutmen/',
}

# Modul pasien yang dibatasi per unit, bukan per role. Status sah bergantung
# pada apakah unit user memang unit modul tersebut.
PATIENT_MODULE_URLS = {
    '/pasien/farmasi/': 'farmasi',
    '/pasien/laboratorium/': 'laboratorium',
    '/pasien/rajal/': 'rajal',
    '/pasien/igd/': 'igd',
    '/pasien/bed-management/': 'ranap',
}

# Pemetaan kode unit -> modul yang SEHARUSNYA boleh diakses.
# Sengaja diturunkan dari kode unit, bukan dari get_allowed_patient_modules():
# memakai fungsi itu sebagai ground truth bersifat sirkular, karena fungsi
# itulah yang sedang diuji (lihat F-2: matcher memakai 'IRJ'/'POLI'/'BANGSAL'
# sehingga RAJAL/RANAP/SEK-RAJAL-RANAP tidak pernah cocok).
EXPECTED_MODULE_BY_UNIT = {
    'farmasi': ('FARM', 'DEPO', 'APOTEK'),
    'laboratorium': ('LAB',),
    'rajal': ('RAJAL', 'IRJ', 'POLI'),
    'igd': ('IGD',),
    'ranap': ('RANAP', 'IRIN', 'BANGSAL', 'INTENSIF', 'RUANG'),
}


def unit_should_have_module(unit_code, module):
    """True bila kode unit menunjukkan unit ini berhak atas modul tersebut."""
    if not unit_code:
        return False
    code = unit_code.upper()
    return any(token in code for token in EXPECTED_MODULE_BY_UNIT.get(module, ()))


# Default: endpoint baca biasa.
DEFAULT_ALLOWED = {200}

# Status yang selalu sah untuk endpoint GET, apa pun role-nya.
ALWAYS_ALLOWED = {302, 400, 403, 405}


def expected_status(role, url, allowed_modules=None, unit_code=None):
    """Kembalikan set status yang dianggap benar untuk (role, url).

    `unit_code` dipakai untuk modul pasien yang dibatasi per unit; ekspektasi
    diturunkan dari kode unit, bukan dari hasil get_allowed_patient_modules().
    """
    if role in ('SUPER_ADMIN', 'ADMIN_RS'):
        return {200}

    if url in PER_ROLE:
        return PER_ROLE[url].get(role, DEFAULT_ALLOWED | ALWAYS_ALLOWED)

    if url in HC_URLS_403:
        return {403}

    if url in PATIENT_MODULE_URLS:
        module = PATIENT_MODULE_URLS[url]
        return {200} if unit_should_have_module(unit_code, module) else {403}

    return DEFAULT_ALLOWED | ALWAYS_ALLOWED


def is_expected(role, url, status, allowed_modules=None, unit_code=None):
    if status == 500:
        return False
    return status in expected_status(role, url, allowed_modules, unit_code)


def is_finding(role, url, status, allowed_modules=None, unit_code=None):
    """True bila status ini layak dilaporkan sebagai temuan.

    Fokus pada dua kelas yang benar-benar berbahaya:
      - 5xx dan exception
      - 403 pada modul yang seharusnya boleh diakses unit tersebut (F-2)
      - 200 pada modul HC yang seharusnya ditolak (kebocoran hak)
    """
    if isinstance(status, str):
        return True  # EXC:*
    if status == 500:
        return True
    if url in HC_URLS_403 and role not in ('SUPER_ADMIN', 'ADMIN_RS') and status == 200:
        return True
    if url in PATIENT_MODULE_URLS:
        module = PATIENT_MODULE_URLS[url]
        if unit_should_have_module(unit_code, module) and status == 403:
            return True
    return False
