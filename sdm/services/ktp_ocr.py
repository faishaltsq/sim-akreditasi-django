"""OCR extraction of Indonesian KTP fields via the existing DeepSeek channel.

Runs on demand after a KTP is staged; raw OCR text is never stored. Returned
fields are suggestions only — persistence still flows through
validate_personal_data, so a bad read fails exactly where a manual typo would,
and the operator reviews everything before saving (spec: Verifikasi Pengguna).
"""
import base64
import re

from akreditasi.ai_service import _call_deepseek

KTP_OCR_FIELDS = (
    'nik', 'nama_lengkap', 'tempat_lahir', 'tanggal_lahir', 'gender', 'alamat',
)

_DDMMYYYY = re.compile(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$')

SYSTEM_PROMPT = (
    'Anda mesin ekstraksi data dari gambar KTP Indonesia. '
    'Balas HANYA JSON sesuai skema yang diminta, tanpa penjelasan.'
)


def _normalize_tanggal(raw):
    if not isinstance(raw, str):
        return ''
    match = _DDMMYYYY.match(raw.strip())
    if not match:
        return ''
    day, month, year = match.groups()
    return f'{year}-{int(month):02d}-{int(day):02d}'


def _normalize_gender(raw):
    token = (raw or '').strip().upper()
    if token.startswith('L'):
        return 'LAKI_LAKI'
    if token.startswith('P'):
        return 'PEREMPUAN'
    return ''


def _ai_disabled():
    from akreditasi.system_models import SystemConfig

    config = SystemConfig.get_solo()
    return not config.ai_enabled or not config.get_deepseek_api_key()


def extract_ktp_fields(image_bytes: bytes, *, actor) -> dict:
    """Return suggested KTP fields; every value '' when unreadable/off.

    ``actor`` is accepted for call-site symmetry with other HC services and is
    not used for authorization — the caller already gated the upload.
    """
    fields = {key: '' for key in KTP_OCR_FIELDS}
    if not image_bytes or _ai_disabled():
        return fields
    data_url = 'data:image/jpeg;base64,' + base64.b64encode(image_bytes).decode()
    prompt = (
        f'Gambar KTP (data URL): {data_url}\n'
        'Baca KTP Indonesia di atas dan kembalikan JSON persis dengan kunci: '
        '{"nik": str, "nama": str, "ttl": str, "gender": str, "alamat": str}. '
        'nik = 16 digit NIK. ttl = "Tempat, DD-MM-YYYY". gender = "L" atau "P". '
        'alamat = satu baris lengkap termasuk RT/RW, Kelurahan, Kecamatan, '
        'Kabupaten/Kota, Provinsi. Gunakan "" untuk bagian tidak terbaca.'
    )
    result = _call_deepseek(prompt, system_prompt=SYSTEM_PROMPT,
                            temperature=0.0, max_tokens=600)
    if not result.get('success') or not isinstance(result.get('data'), dict):
        return fields
    data = result['data']
    nik = str(data.get('nik') or '').strip()
    fields['nik'] = nik if nik.isdigit() else ''
    fields['nama_lengkap'] = str(data.get('nama') or '').strip()[:100]
    ttl = str(data.get('ttl') or '').strip()
    if ',' in ttl:
        place, _, raw_date = ttl.partition(',')
        fields['tempat_lahir'] = place.strip()[:100]
    else:
        raw_date = ttl
    fields['tanggal_lahir'] = _normalize_tanggal(raw_date)
    fields['gender'] = _normalize_gender(data.get('gender'))
    fields['alamat'] = str(data.get('alamat') or '').strip()[:500]
    return fields
