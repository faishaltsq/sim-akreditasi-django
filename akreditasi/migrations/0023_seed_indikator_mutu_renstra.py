from django.db import migrations


def run_seed(apps, schema_editor):
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
