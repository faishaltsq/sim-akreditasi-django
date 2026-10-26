"""Guard transaksi untuk uji tulis: blok selalu di-rollback.

Dipakai HANYA pada fase regression tulis, terhadap DB asli.
"""
from contextlib import contextmanager

from django.db import transaction


@contextmanager
def rolled_back():
    """Jalankan blok dalam transaksi yang SELALU dibatalkan."""
    with transaction.atomic():
        yield
        transaction.set_rollback(True)


def table_counts(tables):
    """Hitung baris beberapa tabel, untuk verifikasi tidak ada perubahan."""
    from django.db import connection

    out = {}
    with connection.cursor() as cur:
        for t in tables:
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            out[t] = cur.fetchone()[0]
    return out
