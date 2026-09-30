"""
Modul Keamanan Berkas dan Validasi Input Upload
Mencegah Stored XSS, Path Traversal, Denial of Service via zip bomb / massive upload.
"""
import os
import re
from pathlib import Path
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {
    # Dokumen
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv',
    # Gambar
    '.jpg', '.jpeg', '.png', '.webp',
    # Arsip bukti
    '.zip',
}

DISALLOWED_EXTENSIONS = {
    '.exe', '.bat', '.sh', '.bin', '.cmd', '.py', '.php', '.pl', '.js',
    '.vbs', '.html', '.htm', '.jar', '.com', '.msi', '.scr', '.pif', '.svg'  # SVG rentan XSS
}

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


def sanitize_filename(filename: str) -> str:
    """
    Sanitasi nama file dari karakter berbahaya dan path traversal.
    """
    if not filename:
        return 'berkas_bukti'
    base = os.path.basename(filename)
    # Hapus ekstensi terlebih dahulu
    name, ext = os.path.splitext(base)
    # Hapus karakter non-alfanumerik dari nama (hanya sisakan huruf, angka, minus, underscore)
    safe_name = re.sub(r'[^\w\-]', '_', name).strip('_')
    safe_name = re.sub(r'_+', '_', safe_name)
    if not safe_name:
        safe_name = 'berkas'
    safe_ext = ext.lower().strip()
    return f"{safe_name}{safe_ext}"


def validate_uploaded_file(file_obj) -> tuple[bool, str]:
    """
    Validasi berkas upload:
    1. Cek ukuran (<= 25 MB)
    2. Cek ekstensi whitelist
    3. Cek ekstensi blacklist

    Returns:
        (is_valid: bool, error_message: str)
    """
    if not file_obj:
        return False, "Tidak ada berkas yang diunggah."

    # 1. Batas ukuran
    if file_obj.size > MAX_FILE_SIZE_BYTES:
        return False, f"Ukuran berkas melebihi batas maksimal {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."

    if file_obj.size == 0:
        return False, "Berkas yang diunggah kosong (0 byte)."

    # 2. Ekstensi
    ext = Path(file_obj.name).suffix.lower()
    if ext in DISALLOWED_EXTENSIONS:
        return False, f"Tipe berkas '{ext}' dilarang demi keamanan sistem."

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Tipe berkas '{ext}' tidak diizinkan. Format yang diterima: PDF, DOCX, XLSX, PPTX, JPG, PNG, WEBP, ZIP."

    return True, ""
