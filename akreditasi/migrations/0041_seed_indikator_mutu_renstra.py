"""Jalankan seed indikator mutu, renstra, dan data demo setelah skema lengkap.

Dulu ``0023`` dan ``0024`` memanggil ``call_command`` dari dalam migrasi. Itu
rapuh: management command mengimpor model hidup (bukan model historis dari
``apps``), sehingga setiap kolom yang ditambahkan setelah migrasi tersebut
membuat ``migrate`` pada database baru gagal. Kasus yang tercatat:
``no such column: akreditasi_indikatormutu.rencana_aksi`` — kolom itu baru ada
di ``0027``, sementara seed-nya berjalan di ``0023``.

Seed-nya dipindah ke sini supaya berjalan setelah seluruh skema siap. Kedua
command bersifat idempotent (``update_or_create``), jadi aman dijalankan pada
database yang sudah berisi data.
"""

import sys

from django.core.management import call_command
from django.db import migrations

SEEDS = ('seed_indikator_mutu_renstra', 'seed_demo_data')


def run_seeds(apps, schema_editor):
    # Test runner membangun database dari nol untuk setiap suite; seed demo
    # hanya memperlambat dan tidak dipakai assertion mana pun.
    if 'test' in sys.argv:
        return
    for name in SEEDS:
        call_command(name, verbosity=0)


def noop(apps, schema_editor):
    """Seed tidak dibalik: menghapus data akreditasi bukan operasi aman."""


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0040_standarditem_scoped_code_unique'),
        ('akreditasi', '0057_repair_starkes_2024_edition_identity'),
    ]

    operations = [
        migrations.RunPython(run_seeds, noop),
    ]
