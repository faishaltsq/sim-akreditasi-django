"""Staff intake service contracts (Task B2)."""

import re

from django.core.exceptions import ValidationError
from django.utils import timezone


NIK_RE = re.compile(r'^\d{16}$', re.ASCII)


def validate_personal_data(data: dict) -> dict:
    """Normalize and validate personal intake fields. Returns normalized values
    or raises ValidationError with field errors."""
    errors = {}
    cleaned = {}

    nik = (data.get('nik') or '').strip()
    if nik:
        if not NIK_RE.match(nik):
            errors['nik'] = 'NIK harus berupa 16 digit angka ASCII.'
        else:
            cleaned['nik'] = nik

    nama_depan = (data.get('nama_depan') or '').strip()
    nama_belakang = (data.get('nama_belakang') or '').strip()
    if not nama_depan and not nama_belakang:
        errors['nama_depan'] = 'Nama depan atau nama belakang wajib diisi.'
    cleaned['nama_depan'] = nama_depan
    cleaned['nama_belakang'] = nama_belakang

    gelar_depan = (data.get('gelar_depan') or '').strip()
    gelar_belakang = (data.get('gelar_belakang') or '').strip()
    cleaned['gelar_depan'] = gelar_depan
    cleaned['gelar_belakang'] = gelar_belakang

    tempat_lahir = (data.get('tempat_lahir') or '').strip()
    cleaned['tempat_lahir'] = tempat_lahir

    tanggal_lahir = data.get('tanggal_lahir')
    if tanggal_lahir:
        try:
            parsed = timezone.datetime.strptime(str(tanggal_lahir), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            errors['tanggal_lahir'] = 'Tanggal lahir harus dalam format YYYY-MM-DD.'
        else:
            today = timezone.localdate()
            if parsed > today:
                errors['tanggal_lahir'] = 'Tanggal lahir tidak boleh di masa depan.'
            cleaned['tanggal_lahir'] = parsed
    else:
        cleaned['tanggal_lahir'] = None

    gender = data.get('gender') or ''
    cleaned['gender'] = gender

    agama = data.get('agama') or ''
    cleaned['agama'] = agama

    status_pernikahan = data.get('status_pernikahan') or ''
    cleaned['status_pernikahan'] = status_pernikahan

    telepon = (data.get('telepon') or '').strip()
    cleaned['telepon'] = telepon

    email = (data.get('email_terverifikasi') or '').strip().lower()
    cleaned['email_terverifikasi'] = email

    alamat_ktp = (data.get('alamat_ktp') or '').strip()
    cleaned['alamat_ktp'] = alamat_ktp

    alamat_domisili = (data.get('alamat_domisili') or '').strip()
    cleaned['alamat_domisili'] = alamat_domisili

    alamat_sama = bool(data.get('alamat_sama_dengan_ktp', False))
    cleaned['alamat_sama_dengan_ktp'] = alamat_sama
    if alamat_sama and not alamat_domisili:
        cleaned['alamat_domisili'] = alamat_ktp

    if errors:
        raise ValidationError(errors)

    return cleaned
