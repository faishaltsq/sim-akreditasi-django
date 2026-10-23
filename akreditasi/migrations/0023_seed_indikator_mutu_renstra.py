from django.db import migrations


import sys


def _model_columns(schema_editor, model):
    """Kolom yang benar-benar ada di tabel pada titik migrasi ini."""
    with schema_editor.connection.cursor() as cursor:
        desc = schema_editor.connection.introspection.get_table_description(
            cursor, model._meta.db_table
        )
    return {col.name for col in desc}


def run_seed(apps, schema_editor):
    """Seed INM/IMP-RS Renstra.

    Perintah seed memakai model live, sedangkan pada titik ini skema historis
    belum tentu punya semua kolom yang model live harapkan (mis. `tipe_pengukuran`
    baru dibuat di 0041). Bila ada kolom yang belum ada, seeding dilewati agar
    `migrate` pada database kosong tidak gagal — datanya tetap masuk lewat
    `manage.py seed_indikator_mutu_renstra` setelah skema final.
    """
    if 'test' in sys.argv:
        return

    IndikatorMutu = apps.get_model('akreditasi', 'IndikatorMutu')
    ada = _model_columns(schema_editor, IndikatorMutu)

    from django.db import models as dj_models
    from akreditasi.risiko_models import IndikatorMutu as LiveModel

    dibutuhkan = {
        f.column for f in LiveModel._meta.concrete_fields
        if not isinstance(f, dj_models.AutoField)
    }
    kurang = sorted(dibutuhkan - ada)
    if kurang:
        print(
            '  ⚠ Seed indikator Renstra dilewati: skema historis belum punya kolom '
            '%s. Jalankan `manage.py seed_indikator_mutu_renstra` setelah migrate.'
            % ', '.join(kurang)
        )
        return

    from django.core.management import call_command
    call_command('seed_indikator_mutu_renstra')


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0022_setup_nakes_lain'),
    ]

    operations = [
        migrations.RunPython(run_seed, reverse_seed),
    ]
