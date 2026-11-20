"""Penyamaran identitas untuk respons publik (BL-10).

Semua respons JSON kanal publik (kiosk & mobile) harus memakai fungsi di sini.
"""
from pasien.services.whatsapp import mask_nama, mask_nomor, mask_sep


def mask_nik(nik):
    bersih = str(nik or '').strip()
    if len(bersih) <= 8:
        return '****'
    return bersih[:4] + '*' * (len(bersih) - 8) + bersih[-4:]


def mask_no_bpjs(no_bpjs):
    bersih = str(no_bpjs or '').strip()
    if len(bersih) <= 4:
        return '****'
    return '*' * (len(bersih) - 4) + bersih[-4:]


__all__ = ['mask_nama', 'mask_nik', 'mask_no_bpjs', 'mask_nomor', 'mask_sep']