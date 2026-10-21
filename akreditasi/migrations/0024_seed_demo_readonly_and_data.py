from django.db import migrations


import sys

from ._schema_guard import kolom_hilang


def run_seed_demo(apps, schema_editor):
    if 'test' in sys.argv:
        return

    # `seed_demo_data` memakai model live; pada titik ini `RisikoUnit` historis
    # belum punya kolom `masalah` (ditambahkan di 0029). Lewati bila belum siap.
    from akreditasi.risiko_models import IndikatorMutu, RisikoUnit

    kurang = kolom_hilang(schema_editor, IndikatorMutu, RisikoUnit)
    if kurang:
        print(
            '  ⚠ Seed demo dilewati: skema historis belum punya kolom %s. '
            'Jalankan `manage.py seed_demo_data` setelah migrate.'
            % ', '.join(kurang)
        )
        return

    from django.core.management import call_command
    call_command('seed_demo_data')


def reverse_seed_demo(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0023_seed_indikator_mutu_renstra'),
    ]

    operations = [
        migrations.RunPython(run_seed_demo, reverse_seed_demo),
    ]
