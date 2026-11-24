"""Validasi penanda anatomi — satu aturan untuk jalur IGD dan rawat jalan.

Penanda disimpan sebagai daftar dict ``{'side','x','y','label','kind'}``:
``side`` FRONT/BACK, ``kind`` LUKA/NYERI/LAINNYA, ``label`` 1–200 karakter, dan
``x``/``y`` koordinat ternormalisasi 0–1 pada gambar anatomi. Maksimal 100
penanda per daftar.

Aturan ini sudah dipakai form IGD sejak sebelum F3 (``StepForm.clean``). Modul
ini memindahkannya ke satu tempat **tanpa mengubah satu pun batas atau pesan
galat**, supaya jalur rawat jalan jantung (F3.6) memakai validasi yang sama
persis dan tidak lahir tabel aturan kedua.

Modul ini tidak mengimpor Django atau model apa pun.
"""
import math

#: Batas jumlah penanda per episode.
MAX_MARKERS = 100
#: Batas panjang label penanda.
MAX_LABEL = 200
SIDES = ('FRONT', 'BACK')
KINDS = ('LUKA', 'NYERI', 'LAINNYA')
REQUIRED_KEYS = frozenset({'side', 'x', 'y', 'label', 'kind'})

ERROR_TOO_MANY = 'Maksimal 100 penanda dalam daftar.'
ERROR_INVALID = 'Koordinat/label penanda tidak valid.'

def _valid_marker(marker):
    if not isinstance(marker, dict) or set(marker) != REQUIRED_KEYS:
        return False
    if marker.get('side') not in SIDES or marker.get('kind') not in KINDS:
        return False
    label = marker.get('label')
    if not isinstance(label, str) or not 0 < len(label) <= MAX_LABEL:
        return False
    return all(
        type(marker.get(key)) in (int, float)
        and math.isfinite(marker[key])
        and 0 <= marker[key] <= 1
        for key in ('x', 'y')
    )

def validate_markers(value):
    """``(cleaned, error)`` untuk satu daftar penanda; ``error`` atau ``None``.

    ``None`` berarti tidak ada penanda (menjadi daftar kosong). Pesan galatnya
    sama dengan yang selama ini dipakai form IGD.
    """
    if value is None:
        return [], None
    if not isinstance(value, list) or len(value) > MAX_MARKERS:
        return None, ERROR_TOO_MANY
    for marker in value:
        if not _valid_marker(marker):
            return None, ERROR_INVALID
    return value, None
