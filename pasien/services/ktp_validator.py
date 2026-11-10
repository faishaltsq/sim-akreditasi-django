"""Validation, normalization, and decoding utilities for KTP, NIK, and patient birthdates.

Adheres to STARKES SKP 1 (Two-Identifier Patient Verification) and MRMIK standards.
"""
import re
from datetime import date, datetime

PROVINSI_KODE_MAP = {
    '11': 'Aceh',
    '12': 'Sumatera Utara',
    '13': 'Sumatera Barat',
    '14': 'Riau',
    '15': 'Jambi',
    '16': 'Sumatera Selatan',
    '17': 'Bengkulu',
    '18': 'Lampung',
    '19': 'Kepulauan Bangka Belitung',
    '21': 'Kepulauan Riau',
    '31': 'DKI Jakarta',
    '32': 'Jawa Barat',
    '33': 'Jawa Tengah',
    '34': 'DI Yogyakarta',
    '35': 'Jawa Timur',
    '36': 'Banten',
    '51': 'Bali',
    '52': 'Nusa Tenggara Barat',
    '53': 'Nusa Tenggara Timur',
    '61': 'Kalimantan Barat',
    '62': 'Kalimantan Tengah',
    '63': 'Kalimantan Selatan',
    '64': 'Kalimantan Timur',
    '65': 'Kalimantan Utara',
    '71': 'Sulawesi Utara',
    '72': 'Sulawesi Tengah',
    '73': 'Sulawesi Selatan',
    '74': 'Sulawesi Tenggara',
    '75': 'Gorontalo',
    '76': 'Sulawesi Barat',
    '81': 'Maluku',
    '82': 'Maluku Utara',
    '91': 'Papua',
    '92': 'Papua Barat',
    '93': 'Papua Selatan',
    '94': 'Papua Tengah',
    '95': 'Papua Pegunungan',
    '96': 'Papua Barat Daya',
}


def parse_flexible_date(raw_str, prefer='MDY') -> date | None:
    """Parse flexible manual date inputs into a python datetime.date.

    Supports:
      - YYYY-MM-DD or YYYY/MM/DD
      - MM/DD/YY, MM/DD/YYYY (prefer='MDY')
      - DD/MM/YY, DD/MM/YYYY, DD-MM-YYYY (prefer='DMY')
      - 2-digit century expansion (pivot against current year).
    Returns None if empty or invalid date.
    """
    if isinstance(raw_str, date):
        return raw_str
    if not raw_str or not isinstance(raw_str, str):
        return None

    cleaned = raw_str.strip()
    if not cleaned:
        return None

    # 1. Standard ISO YYYY-MM-DD or YYYY/MM/DD
    match_iso = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', cleaned)
    if match_iso:
        y, m, d = int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3))
        try:
            return date(y, m, d)
        except ValueError:
            return None

    # 2. Part1 / Part2 / Year (2-digit or 4-digit)
    match_slash = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$', cleaned)
    if not match_slash:
        return None

    p1, p2, p3 = int(match_slash.group(1)), int(match_slash.group(2)), match_slash.group(3)

    # Century pivot for 2-digit year
    if len(p3) == 2:
        yy = int(p3)
        current_yy = date.today().year % 100
        year = (2000 + yy) if yy <= current_yy else (1900 + yy)
    else:
        year = int(p3)

    # Determine month vs day
    if p1 > 12 and p2 <= 12:
        # Unambiguous DD/MM
        day, month = p1, p2
    elif p2 > 12 and p1 <= 12:
        # Unambiguous MM/DD
        month, day = p1, p2
    else:
        # Both <= 12; use caller's preference
        if prefer.upper() == 'DMY':
            day, month = p1, p2
        else:
            month, day = p1, p2

    try:
        return date(year, month, day)
    except ValueError:
        return None


def decode_nik(nik_str: str) -> dict:
    """Decode Indonesian 16-digit NIK into demographic components.

    Structure:
      - [0:2] : Kode Provinsi
      - [2:4] : Kode Kota / Kabupaten
      - [4:6] : Kode Kecamatan
      - [6:8] : Tanggal (wanita +40)
      - [8:10]: Bulan
      - [10:12]: 2 digit tahun lahir
      - [12:16]: Nomor urut
    """
    digits = re.sub(r'\D', '', str(nik_str or ''))
    if len(digits) != 16:
        return {
            'valid': False,
            'error': f'NIK harus 16 digit angka (ditemukan {len(digits)} digit)',
            'nik': digits,
            'jenis_kelamin': '',
            'tanggal_lahir': None,
            'nama_provinsi': '',
        }

    prov_code = digits[:2]
    nama_provinsi = PROVINSI_KODE_MAP.get(prov_code, 'Provinsi Tidak Dikenal')

    try:
        raw_day = int(digits[6:8])
        month = int(digits[8:10])
        yy = int(digits[10:12])
    except ValueError:
        return {'valid': False, 'error': 'Komponen tanggal NIK bukan angka', 'nik': digits}

    if raw_day > 40:
        jenis_kelamin = 'P'
        day = raw_day - 40
    else:
        jenis_kelamin = 'L'
        day = raw_day

    current_yy = date.today().year % 100
    year = (2000 + yy) if yy <= current_yy else (1900 + yy)

    try:
        dob = date(year, month, day)
    except ValueError:
        return {
            'valid': False,
            'error': f'Tanggal lahir pada NIK ({day:02d}-{month:02d}-{year}) tidak valid kalender',
            'nik': digits,
            'jenis_kelamin': jenis_kelamin,
            'tanggal_lahir': None,
            'nama_provinsi': nama_provinsi,
        }

    return {
        'valid': True,
        'error': '',
        'nik': digits,
        'kode_provinsi': prov_code,
        'nama_provinsi': nama_provinsi,
        'kode_kabkota': digits[:4],
        'kode_kecamatan': digits[:6],
        'jenis_kelamin': jenis_kelamin,
        'tanggal_lahir': dob,
        'tanggal_lahir_iso': dob.isoformat(),
        'tanggal_lahir_mdy': dob.strftime('%m/%d/%Y'),
        'tanggal_lahir_dmy': dob.strftime('%d/%m/%Y'),
    }


def validate_nik_with_demographics(nik_str: str, jenis_kelamin: str = None, tanggal_lahir = None) -> dict:
    """Validate 16-digit NIK and compare with typed demographics."""
    decoded = decode_nik(nik_str)
    if not decoded['valid']:
        return {'valid': False, 'warnings': [decoded['error']], 'decoded': decoded}

    warnings = []

    # Check gender cross-match
    if jenis_kelamin:
        jk_input = 'P' if str(jenis_kelamin).upper().startswith('P') else 'L'
        if jk_input != decoded['jenis_kelamin']:
            gender_nama = 'Perempuan' if decoded['jenis_kelamin'] == 'P' else 'Laki-laki'
            warnings.append(
                f'Jenis kelamin tidak cocok dengan NIK (NIK terindikasi {gender_nama}).'
            )

    # Check date of birth cross-match
    if tanggal_lahir:
        parsed_dob = parse_flexible_date(tanggal_lahir) if isinstance(tanggal_lahir, str) else tanggal_lahir
        if parsed_dob and decoded['tanggal_lahir'] and parsed_dob != decoded['tanggal_lahir']:
            nik_tgl = decoded['tanggal_lahir'].strftime('%d/%m/%Y')
            warnings.append(
                f'Tanggal lahir tidak cocok dengan NIK (NIK terindikasi lahir {nik_tgl}).'
            )

    return {
        'valid': True,
        'warnings': warnings,
        'decoded': decoded,
    }
