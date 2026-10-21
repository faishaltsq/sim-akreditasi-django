"""Guard untuk migrasi data yang memanggil management command.

Command memakai model **live** (`akreditasi.models`), sedangkan pada titik
migrasi tertentu skema historis belum punya semua kolom yang model live
harapkan. Tanpa guard, `migrate` pada database kosong gagal dengan
`no such column` dan seluruh deploy ikut mati.

Pola pakai di dalam `RunPython`:

    from ._schema_guard import kolom_hilang
    kurang = kolom_hilang(schema_editor, IndikatorMutu, RisikoUnit)
    if kurang:
        print('  ⚠ seeding dilewati: ' + ', '.join(kurang))
        return
"""

from django.db import models as dj_models


def _kolom_tabel(schema_editor, table):
    with schema_editor.connection.cursor() as cursor:
        desc = schema_editor.connection.introspection.get_table_description(
            cursor, table
        )
    return {col.name for col in desc}


def kolom_hilang(schema_editor, *live_models):
    """Kembalikan daftar 'tabel.kolom' yang belum ada di skema saat ini."""
    hilang = []
    for model in live_models:
        ada = _kolom_tabel(schema_editor, model._meta.db_table)
        for field in model._meta.concrete_fields:
            if isinstance(field, dj_models.AutoField):
                continue
            if field.column not in ada:
                hilang.append('%s.%s' % (model._meta.db_table, field.column))
    return sorted(hilang)
