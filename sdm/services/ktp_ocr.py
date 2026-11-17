"""OCR extraction of Indonesian KTP fields via the existing DeepSeek channel.

Runs on demand after a KTP is staged; raw OCR text is never stored. Returned
fields are suggestions only — persistence still flows through
validate_personal_data, so a bad read fails exactly where a manual typo would,
and the operator reviews everything before saving (spec: Verifikasi Pengguna).
"""
import re

from akreditasi.ai_service import _call_deepseek, build_image_data_url

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


def _ai_disabled_reason():
    from akreditasi.system_models import SystemConfig

    config = SystemConfig.get_solo()
    if not config.ai_enabled:
        return 'Fitur AI sedang dinonaktifkan.'
    if not config.get_deepseek_api_key():
        return 'API Key DeepSeek belum dikonfigurasi.'
    return ''


def _ai_disabled():
    return bool(_ai_disabled_reason())


def extract_ktp_fields_detailed(image_bytes: bytes, *, actor):
    """Return ``(fields, error)`` so the caller can tell the operator why.

    ``error`` is '' when the read succeeded. A silent all-blank result is
    indistinguishable from "the operator left the form empty", which is why
    every failure used to look like a broken feature.
    """
    fields = {key: '' for key in KTP_OCR_FIELDS}
    if not image_bytes:
        return fields, 'Berkas KTP kosong.'

    disabled_reason = _ai_disabled_reason()
    if disabled_reason:
        return fields, disabled_reason

    prompt = (
        'Baca KTP Indonesia pada gambar yang dilampirkan dan kembalikan JSON '
        'persis dengan kunci: '
        '{"nik": str, "nama": str, "ttl": str, "gender": str, "alamat": str}. '
        'nik = 16 digit NIK. ttl = "Tempat, DD-MM-YYYY". gender = "L" atau "P". '
        'alamat = satu baris lengkap termasuk RT/RW, Kelurahan, Kecamatan, '
        'Kabupaten/Kota, Provinsi. Gunakan "" untuk bagian tidak terbaca.'
    )
    try:
        result = _call_deepseek(prompt, system_prompt=SYSTEM_PROMPT,
                                temperature=0.0, max_tokens=600, timeout=90,
                                image_data_url=build_image_data_url(image_bytes))
    except Exception as exc:
        return fields, f'Panggilan DeepSeek gagal: {exc}'

    if not result.get('success'):
        return fields, result.get('error') or 'DeepSeek tidak mengembalikan hasil.'
    data = result.get('data')
    if not isinstance(data, dict):
        return fields, 'Respons DeepSeek bukan objek JSON yang valid.'

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

    if not any(fields.values()):
        return fields, 'Tidak ada teks KTP yang terbaca. Pastikan foto terang dan tidak blur.'
    return fields, ''


def extract_ktp_fields(image_bytes: bytes, *, actor) -> dict:
    """Return suggested KTP fields; every value '' when unreadable/off.

    ``actor`` is accepted for call-site symmetry with other HC services and is
    not used for authorization — the caller already gated the upload. Use
    :func:`extract_ktp_fields_detailed` when the caller needs the reason.
    """
    fields, _error = extract_ktp_fields_detailed(image_bytes, actor=actor)
    return fields
