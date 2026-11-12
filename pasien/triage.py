"""Validasi kategori dan warna tanpa mengasumsikan konversi ATS/ESI."""
from .models import KunjunganPasien


def validate_triage(data):
    choices = {
        'triase_skala': {'', 'ATS', 'ESI', 'WARNA'},
        'triase_kategori': {'', *dict(KunjunganPasien.TRIASE_KATEGORI_CHOICES)},
        'triage': {'', *dict(KunjunganPasien.TRIAGE_CHOICES)},
    }
    values = {}
    for field, allowed in choices.items():
        if field not in data:
            continue
        value = str(data[field]).strip()
        if value not in allowed:
            raise ValueError(f'Nilai {field} tidak valid.')
        values[field] = value
    if values.get('triase_skala') == 'WARNA' and values.get('triase_kategori'):
        raise ValueError('Kategori numerik memerlukan skala ATS atau ESI.')
    return values
