from django.db import migrations


def run_setup(apps, schema_editor):
    from django.core.management import call_command
    call_command('setup_rekam_medis')


def reverse_setup(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0019_setup_cssd'),
    ]

    operations = [
        migrations.RunPython(run_setup, reverse_setup),
    ]
