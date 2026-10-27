"""Parsing input HTTP menjadi tipe Python dengan batas kesalahan yang jelas.

Sebelum modul ini, `int()` mentah pada `request.GET`/`request.POST`/body JSON
melempar `ValueError` yang berakhir 500 setiap kali pengguna mengirim nilai
non-numerik (temuan QA 2026-10-27, 10 titik di 4 app). Fungsi di sini
mengembalikan `None` atau nilai default, bukan exception — pemanggil yang
memutuskan apakah `None` berarti 400, 404, atau "abaikan filter".
"""

import json

from django.http import JsonResponse


def parse_int(value, default=None):
    """`int(value)` tanpa exception. Kosong/`None`/tidak valid → ``default``."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def query_int(request, name, default=None):
    """Ambil parameter GET berupa int.

    Parameter yang TIDAK dikirim → ``default``. Parameter yang dikirim tetapi
    tidak valid → ``None`` juga, jadi pemanggil harus memeriksa
    ``request.GET.get(name)`` bila perlu membedakan keduanya (lihat
    ``invalid_query_int``).
    """
    value = request.GET.get(name)
    if value in (None, ''):
        return default
    return parse_int(value)


def invalid_query_int(request, name):
    """True bila parameter GET dikirim tetapi bukan bilangan bulat."""
    value = request.GET.get(name)
    return value not in (None, '') and parse_int(value) is None


def post_int(request, name, default=None):
    """Ambil field POST berupa int. Tidak valid → ``default``."""
    return parse_int(request.POST.get(name), default)


def json_body(request):
    """Body JSON sebagai dict. Body kosong/rusak/bukan objek → ``None``.

    Hanya ``json.JSONDecodeError`` dan tipe yang salah yang ditelan; error
    lain dibiarkan naik supaya tidak menyembunyikan bug sungguhan.
    """
    try:
        data = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def bad_request_json(message):
    """Response 400 standar untuk body JSON yang tidak bisa dibaca."""
    return JsonResponse({'success': False, 'error': message}, status=400)
