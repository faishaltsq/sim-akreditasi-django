from django.db import migrations


def run_setup(apps, schema_editor):
    from django.core.management import call_command
    call_command('setup_sdm_diklat')


def reverse_setup(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0016_setup_ranap_rajal_igd'),
    ]

    operations = [
        migrations.RunPython(run_setup, reverse_setup),
    ]
