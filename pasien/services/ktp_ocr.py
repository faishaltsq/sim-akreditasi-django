"""Optical Character Recognition (OCR) service for patient identity cards (KTP).

Extracts demographic data into structured patient registration fields.
Complies with STARKES SKP 1 (Two-Identifier Verification) and MRMIK standards.
"""
import re
from datetime import date
from akreditasi.ai_service import _call_deepseek, build_image_data_url
from pasien.services.ktp_validator import (
    parse_flexible_date,
    decode_nik,
    PROVINSI_KODE_MAP,
)

SYSTEM_PROMPT = (
    "Anda adalah mesin OCR spesialis membaca e-KTP Indonesia untuk SIMRS Rumah Sakit. "
    "Ekstrak teks gambar KTP secara presisi dan kembalikan HANYA JSON murni tanpa markdown/penjelasan, "
    "dengan kunci: 'nik', 'nama', 'tempat_lahir', 'tanggal_lahir', 'gender', 'golongan_darah', "
    "'alamat', 'rt_rw', 'kelurahan', 'kecamatan', 'kota_kabupaten', 'provinsi', 'agama', "
    "'status_perkawinan', 'pekerjaan'."
)


def _ai_disabled():
    from akreditasi.system_models import SystemConfig
    config = SystemConfig.get_solo()
    return not config.ai_enabled or not config.get_deepseek_api_key()


def _normalize_gender(val):
    v = (val or '').strip().upper()
    if v.startswith('P') or 'PEREMPUAN' in v or 'WANITA' in v:
        return 'P'
    if v.startswith('L') or 'LAKI' in v or 'PRIA' in v:
        return 'L'
    return ''


def _normalize_goldar(val):
    v = (val or '').strip().upper()
    for g in ('AB', 'A', 'B', 'O'):
        if g in v:
            return g
    return '-'


def _normalize_agama(val):
    v = (val or '').strip().upper()
    mapping = {
        'ISLAM': 'ISLAM',
        'KRISTEN': 'KRISTEN',
        'PROTESTAN': 'KRISTEN',
        'KATOLIK': 'KATOLIK',
        'HINDU': 'HINDU',
        'BUDDHA': 'BUDDHA',
        'BUDHA': 'BUDDHA',
        'KONGHUCU': 'KONGHUCU',
    }
    for k, target in mapping.items():
        if k in v:
            return target
    return 'ISLAM' if v else 'ISLAM'


def _normalize_status_kawin(val):
    v = (val or '').strip().upper()
    if 'BELUM' in v:
        return 'BELUM_MENIKAH'
    if 'KAWIN' in v or 'MENIKAH' in v:
        return 'MENIKAH'
    if 'CERAI' in v or 'JANDA' in v or 'DUDA' in v:
        return 'DUDA_JANDA'
    return 'MENIKAH'


def _ai_disabled_reason():
    """Return '' when the AI channel is usable, else a human-readable reason."""
    from akreditasi.system_models import SystemConfig
    config = SystemConfig.get_solo()
    if not config.ai_enabled:
        return 'Fitur AI sedang dinonaktifkan. Aktifkan di Pengaturan AI atau hubungi Super Admin.'
    if not config.get_deepseek_api_key():
        return 'API Key DeepSeek belum dikonfigurasi. Isi di Pengaturan AI atau hubungi Super Admin.'
    return ''


def _ai_disabled():
    return bool(_ai_disabled_reason())


def _empty_result():
    return {
        'nik': '',
        'nama_lengkap': '',
        'tempat_lahir': '',
        'tanggal_lahir': '',
        'tanggal_lahir_mdy': '',
        'tanggal_lahir_dmy': '',
        'jenis_kelamin': '',
        'golongan_darah': '-',
        'alamat': '',
        'rt_rw': '',
        'kelurahan': '',
        'kecamatan': '',
        'kota_kabupaten': '',
        'provinsi': '',
        'agama': 'ISLAM',
        'status_perkawinan': 'MENIKAH',
        'pekerjaan': '',
    }


def extract_ktp_pasien_detailed(image_bytes: bytes):
    """Extract patient fields and say *why* it failed when it fails.

    Returns ``(fields, error)``; ``error`` is '' on success. The silent-empty
    behaviour this replaces made every failure look like "OCR tidak bisa":
    a disabled key, a 401 and an unreadable photo all produced the same blank
    form with HTTP 200 and no message.
    """
    empty_result = _empty_result()

    if not image_bytes:
        return empty_result, 'Gambar KTP kosong atau tidak dapat dibaca.'

    disabled_reason = _ai_disabled_reason()
    if disabled_reason:
        return empty_result, disabled_reason

    try:
        prompt = (
            "Baca gambar KTP Indonesia yang dilampirkan dengan teliti. "
            "Kembalikan JSON dengan format persis:\n"
            "{\n"
            '  "nik": "16 digit angka",\n'
            '  "nama": "NAMA LENGKAP",\n'
            '  "tempat_lahir": "KOTA TEMPAT LAHIR",\n'
            '  "tanggal_lahir": "YYYY-MM-DD",\n'
            '  "gender": "L atau P",\n'
            '  "golongan_darah": "A/B/AB/O/-",\n'
            '  "alamat": "NAMA JALAN/GANG/NO RUMAH",\n'
            '  "rt_rw": "000/000",\n'
            '  "kelurahan": "NAMA DESA/KELURAHAN",\n'
            '  "kecamatan": "NAMA KECAMATAN",\n'
            '  "kota_kabupaten": "KOTA/KABUPATEN",\n'
            '  "provinsi": "PROVINSI",\n'
            '  "agama": "ISLAM/KRISTEN/KATOLIK/HINDU/BUDDHA/KONGHUCU",\n'
            '  "status_perkawinan": "BELUM KAWIN/KAWIN/CERAI HIDUP/CERAI MATI",\n'
            '  "pekerjaan": "PEKERJAAN"\n'
            "}"
        )
        ai_res = _call_deepseek(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.0,
                                max_tokens=700, timeout=90,
                                image_data_url=build_image_data_url(image_bytes))
    except Exception as exc:  # network, timeout, unreadable image
        return empty_result, f'Panggilan DeepSeek gagal: {exc}'

    if not ai_res.get('success'):
        return empty_result, ai_res.get('error') or 'DeepSeek tidak mengembalikan hasil.'

    d = ai_res.get('data')
    if not isinstance(d, dict):
        return empty_result, 'Respons DeepSeek bukan objek JSON yang valid.'

    nik_raw = re.sub(r'\D', '', str(d.get('nik') or ''))
    nama_raw = str(d.get('nama') or '').strip().upper()[:150]
    tempat_lahir = str(d.get('tempat_lahir') or '').strip().title()[:100]
    tgl_lahir_raw = str(d.get('tanggal_lahir') or '').strip()
    parsed_dob = parse_flexible_date(tgl_lahir_raw, prefer='DMY')

    res = {
        'nik': nik_raw,
        'nama_lengkap': nama_raw,
        'tempat_lahir': tempat_lahir,
        'tanggal_lahir': parsed_dob.isoformat() if parsed_dob else '',
        'tanggal_lahir_mdy': parsed_dob.strftime('%m/%d/%Y') if parsed_dob else '',
        'tanggal_lahir_dmy': parsed_dob.strftime('%d/%m/%Y') if parsed_dob else '',
        'jenis_kelamin': _normalize_gender(d.get('gender')),
        'golongan_darah': _normalize_goldar(d.get('golongan_darah')),
        'alamat': str(d.get('alamat') or '').strip()[:200],
        'rt_rw': str(d.get('rt_rw') or '').strip()[:20],
        'kelurahan': str(d.get('kelurahan') or '').strip().title()[:100],
        'kecamatan': str(d.get('kecamatan') or '').strip().title()[:100],
        'kota_kabupaten': str(d.get('kota_kabupaten') or '').strip().title()[:100],
        'provinsi': str(d.get('provinsi') or '').strip().title()[:100],
        'agama': _normalize_agama(d.get('agama')),
        'status_perkawinan': _normalize_status_kawin(d.get('status_perkawinan')),
        'pekerjaan': str(d.get('pekerjaan') or '').strip().title()[:100],
    }

    # Cross-verify and fill missing fields using decode_nik if NIK is valid 16 digits
    if len(nik_raw) == 16:
        nik_dec = decode_nik(nik_raw)
        if nik_dec['valid']:
            if not res['jenis_kelamin']:
                res['jenis_kelamin'] = nik_dec['jenis_kelamin']
            if not res['tanggal_lahir'] and nik_dec['tanggal_lahir']:
                dob = nik_dec['tanggal_lahir']
                res['tanggal_lahir'] = dob.isoformat()
                res['tanggal_lahir_mdy'] = dob.strftime('%m/%d/%Y')
                res['tanggal_lahir_dmy'] = dob.strftime('%d/%m/%Y')
            if not res['provinsi']:
                res['provinsi'] = nik_dec['nama_provinsi']

    if not res['nik'] and not res['nama_lengkap']:
        return empty_result, (
            'Tidak ada teks KTP yang terbaca. Pastikan foto terang, tidak blur, '
            'dan seluruh bagian KTP terlihat.'
        )

    return res, ''


def extract_ktp_pasien(image_bytes: bytes) -> dict:
    """Extract patient demographic fields from KTP image bytes.

    Returns structured dictionary with standard patient registration fields.
    Failures return blank fields; call :func:`extract_ktp_pasien_detailed`
    when the caller needs the reason.
    """
    data, _error = extract_ktp_pasien_detailed(image_bytes)
    return data
