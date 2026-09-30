from django.db import migrations


def run_setup(apps, schema_editor):
    from django.core.management import call_command
    call_command('setup_lab_units')


def reverse_setup(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0014_seed_pemetaan_akun_l4'),
    ]

    operations = [
        migrations.RunPython(run_setup, reverse_setup),
    ]
