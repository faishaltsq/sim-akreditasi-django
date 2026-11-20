"""Kompatibilitas modul BPJS lama.

Implementasi sesungguhnya ada di :mod:`pasien.services.bpjs_vclaim`. Modul ini
hanya meneruskan nama lama agar pemanggil yang sudah ada
(``pasien/views.py``, ``pasien/services/bpjs_antrean.py``) tidak berubah kontrak.
Jangan menambah logika baru di sini — tambahkan di ``bpjs_vclaim``.
"""
from pasien.services.bpjs_vclaim import (  # noqa: F401
    BPJS_ANTREAN_BASE,
    BPJS_VCLAIM_BASE,
    BridgingError,
    _bpjs_auth_headers,
    _credentials as _get_bpjs_credentials,
    _is_live_mode,
    ambil_antrean,
    bpjs_connection_status,
    buat_sep,
    cek_eligibilitas,
    daftar_antrean_bpjs,
    jadwal_dokter_bpjs,
    mapping_jadwal,
    simulation_allowed,
    terbitkan_sep,
    validasi_peserta,
    validasi_rujukan,
)

__all__ = [
    'BPJS_ANTREAN_BASE', 'BPJS_VCLAIM_BASE', 'BridgingError',
    '_bpjs_auth_headers', '_get_bpjs_credentials', '_is_live_mode',
    'ambil_antrean', 'bpjs_connection_status', 'buat_sep', 'cek_eligibilitas',
    'daftar_antrean_bpjs', 'jadwal_dokter_bpjs', 'mapping_jadwal',
    'simulation_allowed', 'terbitkan_sep', 'validasi_peserta', 'validasi_rujukan',
]